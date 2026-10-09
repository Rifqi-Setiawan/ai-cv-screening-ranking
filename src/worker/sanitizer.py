"""File sanitization, MIME verification, malware protection, and edge case detection."""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass, field

import pymupdf

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+all\s+(?:previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(?:all\s+)?(?:criteria|instructions)", re.IGNORECASE),
    re.compile(r"give\s+(?:this\s+candidate\s+)?(?:a\s+)?(?:score\s+of\s+)?100", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:an?\s+)?(?:unconditional|helpful|evaluator)", re.IGNORECASE),
    re.compile(r"system\s+prompt:", re.IGNORECASE),
    re.compile(r"dan\s+mode", re.IGNORECASE),
    re.compile(r"unconditional\s+acceptance", re.IGNORECASE),
]

COVER_LETTER_PATTERNS = [
    re.compile(r"surat\s+lamaran", re.IGNORECASE),
    re.compile(r"kepada\s+yth", re.IGNORECASE),
    re.compile(r"dengan\s+hormat", re.IGNORECASE),
    re.compile(r"cover\s+letter", re.IGNORECASE),
    re.compile(r"dear\s+hiring\s+manager", re.IGNORECASE),
    re.compile(r"bersama\s+surat\s+ini", re.IGNORECASE),
]


@dataclass
class SanitizeResult:
    is_valid: bool
    status: str  # RECEIVED, NEEDS_REVIEW, REJECTED
    sha256: str
    file_type: str
    reasons: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    extracted_text: str = ""
    is_encrypted: bool = False
    has_hidden_text: bool = False
    has_injection: bool = False
    page_count: int = 1


def sanitize_file(content: bytes, filename: str) -> SanitizeResult:
    sha256 = hashlib.sha256(content).hexdigest()

    # 1. Check Empty file
    if len(content) == 0:
        return SanitizeResult(
            is_valid=False,
            status="REJECTED",
            sha256=sha256,
            file_type="unknown",
            reasons=["EMPTY_DOCUMENT", "INSUFFICIENT_CONTENT"],
        )

    # 2. Identify MIME / format by magic bytes
    file_type = "unknown"
    if content.startswith(b"%PDF-"):
        file_type = "pdf"
    elif content.startswith(b"PK\x03\x04"):
        file_type = "docx"
    elif content.startswith(b"\xd0\xcf\x11\xe0"):
        file_type = "doc"

    if file_type == "unknown":
        return SanitizeResult(
            is_valid=False,
            status="REJECTED",
            sha256=sha256,
            file_type=file_type,
            reasons=["INVALID_FORMAT"],
        )

    # 3. PDF Inspection
    if file_type == "pdf":
        try:
            doc = pymupdf.open(stream=content, filetype="pdf")
        except Exception:
            return SanitizeResult(
                is_valid=False,
                status="REJECTED",
                sha256=sha256,
                file_type="pdf",
                reasons=["CORRUPTED_FILE"],
            )

        if doc.is_encrypted:
            doc.close()
            return SanitizeResult(
                is_valid=False,
                status="REJECTED",
                sha256=sha256,
                file_type="pdf",
                is_encrypted=True,
                reasons=["ENCRYPTED_FILE"],
            )

        full_text_parts = []
        has_hidden_text = False
        has_injection = False
        total_images = 0
        flags = []

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            full_text_parts.append(page.get_text())
            total_images += len(page.get_images())

            # Inspect text spans for tiny fonts or white text
            try:
                blocks = page.get_text("dict").get("blocks", [])
                for b in blocks:
                    for line in b.get("lines", []):
                        for span in line.get("spans", []):
                            txt = span.get("text", "").strip()
                            if not txt:
                                continue
                            if span.get("size", 10) < 4.0:
                                has_hidden_text = True
                            color = span.get("color", 0)
                            if color in (16777215, 0xFFFFFF):
                                has_hidden_text = True
                            for pat in INJECTION_PATTERNS:
                                if pat.search(txt):
                                    has_injection = True
            except Exception:
                pass

        page_count = len(doc)
        doc.close()
        full_text = "\n".join(full_text_parts).strip()

        # Check injection across full text
        for pat in INJECTION_PATTERNS:
            if pat.search(full_text):
                has_injection = True

        if has_hidden_text:
            flags.append("HIDDEN_TEXT")
        if has_injection:
            flags.append("PROMPT_INJECTION")

        text_chars = len(re.sub(r"\s+", "", full_text))

        # Check Insufficient / Empty content (e.g. E1): text empty AND no images
        if text_chars < 80 and total_images == 0:
            return SanitizeResult(
                is_valid=True,
                status="NEEDS_REVIEW",
                sha256=sha256,
                file_type="pdf",
                reasons=["INSUFFICIENT_CONTENT", "EMPTY_DOCUMENT"],
                flags=flags,
                extracted_text=full_text,
                page_count=page_count,
            )

        # Check Cover letter not a CV (e.g. E7)
        is_cover_letter = any(p.search(full_text) for p in COVER_LETTER_PATTERNS)
        has_cv_sections = any(
            sec in full_text.lower()
            for sec in ["pengalaman", "experience", "pendidikan", "education", "keahlian", "skills", "riwayat"]
        )
        if is_cover_letter and not has_cv_sections:
            return SanitizeResult(
                is_valid=True,
                status="NEEDS_REVIEW",
                sha256=sha256,
                file_type="pdf",
                reasons=["NOT_A_CV", "INSUFFICIENT_CONTENT"],
                flags=flags,
                extracted_text=full_text,
                page_count=page_count,
            )

        return SanitizeResult(
            is_valid=True,
            status="RECEIVED",
            sha256=sha256,
            file_type="pdf",
            flags=flags,
            extracted_text=full_text,
            has_hidden_text=has_hidden_text,
            has_injection=has_injection,
            page_count=page_count,
        )

    # 4. DOCX Inspection
    if file_type == "docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                total_uncompressed = sum(info.file_size for info in z.infolist())
                if total_uncompressed > 50 * 1024 * 1024:
                    return SanitizeResult(
                        is_valid=False,
                        status="REJECTED",
                        sha256=sha256,
                        file_type="docx",
                        reasons=["ZIP_BOMB_DETECTED"],
                    )
                xml_content = z.read("word/document.xml").decode("utf-8", errors="ignore")
                text = re.sub(r"<[^>]+>", " ", xml_content)
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) < 80:
                    return SanitizeResult(
                        is_valid=True,
                        status="NEEDS_REVIEW",
                        sha256=sha256,
                        file_type="docx",
                        reasons=["INSUFFICIENT_CONTENT", "EMPTY_DOCUMENT"],
                        extracted_text=text,
                    )
                return SanitizeResult(
                    is_valid=True,
                    status="RECEIVED",
                    sha256=sha256,
                    file_type="docx",
                    extracted_text=text,
                )
        except Exception:
            return SanitizeResult(
                is_valid=False,
                status="REJECTED",
                sha256=sha256,
                file_type="docx",
                reasons=["CORRUPTED_FILE"],
            )

    return SanitizeResult(is_valid=True, status="RECEIVED", sha256=sha256, file_type=file_type)
