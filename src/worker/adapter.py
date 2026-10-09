"""Production adapter converting raw cv-extractor output into CandidateProfile with provenance."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

# Ensure cv_extractor is accessible
CV_EXTRACTOR_SRC = Path("/srv/hermes-control/services/cv-extractor/src")
if str(CV_EXTRACTOR_SRC) not in sys.path:
    sys.path.insert(0, str(CV_EXTRACTOR_SRC))

from cv_extractor.application.config import LlmConfig, OcrConfig, PipelineConfig
from cv_extractor.bootstrap import build_service

MONTHS_MAP = {
    "jan": "01",
    "januari": "01",
    "january": "01",
    "feb": "02",
    "februari": "02",
    "pebruari": "02",
    "february": "02",
    "mar": "03",
    "maret": "03",
    "march": "03",
    "apr": "04",
    "april": "04",
    "mei": "05",
    "may": "05",
    "jun": "06",
    "juni": "06",
    "june": "06",
    "jul": "07",
    "juli": "07",
    "july": "07",
    "agu": "08",
    "agt": "08",
    "agus": "08",
    "agustus": "08",
    "aug": "08",
    "august": "08",
    "sep": "09",
    "sept": "09",
    "september": "09",
    "okt": "10",
    "oktober": "10",
    "oct": "10",
    "october": "10",
    "nov": "11",
    "nopember": "11",
    "november": "11",
    "des": "12",
    "desember": "12",
    "dec": "12",
    "december": "12",
}

PRESENT_SET = {"sekarang", "saat ini", "kini", "present", "now", "current", "currently", "to date"}
MONTHS_REGEX_STR = r"(?:jan(?:uari|uary)?|feb(?:ruari|ruary)?|mar(?:et|ch)?|apr(?:il)?|mei|may|jun(?:i|e)?|jul(?:i|y)?|agu(?:stus)?|aug(?:ust)?|sep(?:t(?:ember)?)?|okt(?:ober)?|oct(?:ober)?|nov(?:ember)?|des(?:ember)?|dec(?:ember)?)"

RANGE_REGEX = re.compile(
    rf"({MONTHS_REGEX_STR}\s+\d{{4}}|\d{{1,2}}/\d{{4}}|\b\d{{4}}\b)\s*(?:[-–—=]|s/d|sd|to|sampai|hingga|until)\s*({MONTHS_REGEX_STR}(?:\s+\d{{4}})?|\d{{1,2}}/\d{{4}}|\b\d{{4}}\b|sekarang|present|saat ini|current|now)",
    re.IGNORECASE,
)

_extractor_service = None


def get_extractor_service():
    global _extractor_service
    if _extractor_service is None:
        _extractor_service = build_service(PipelineConfig(ocr=OcrConfig(), llm=LlmConfig(enabled=False)))
    return _extractor_service


def norm_single_date(s: str, is_end: bool = False, ref_year: str = "") -> dict[str, Any]:
    s_clean = s.strip().lower()
    if any(p in s_clean for p in PRESENT_SET):
        return {"raw": s.strip(), "value": "present", "precision": "month", "kind": "FACT"}

    m = re.match(r"(\d{1,2})/(\d{4})", s_clean)
    if m:
        val = f"{m.group(2)}-{int(m.group(1)):02d}"
        return {"raw": s.strip(), "value": val, "precision": "month", "kind": "FACT"}

    m = re.match(rf"({MONTHS_REGEX_STR})\s+(\d{{4}})", s_clean)
    if m:
        mname = m.group(1)
        year = m.group(2)
        mcode = MONTHS_MAP.get(mname[:3], "01")
        return {"raw": s.strip(), "value": f"{year}-{mcode}", "precision": "month", "kind": "FACT"}

    m = re.match(rf"^({MONTHS_REGEX_STR})$", s_clean)
    if m and ref_year:
        mname = m.group(1)
        mcode = MONTHS_MAP.get(mname[:3], "01")
        year_num = int(ref_year) + (1 if is_end else 0)
        return {"raw": s.strip(), "value": f"{year_num}-{mcode}", "precision": "month", "kind": "FACT"}

    m = re.match(r"^\d{4}$", s_clean)
    if m:
        y = m.group(0)
        val = f"{y}-07" if not is_end else f"{y}-06"
        return {"raw": s.strip(), "value": val, "precision": "year", "kind": "INFERENCE"}

    return {"raw": s.strip(), "value": None, "precision": "unknown", "kind": "FACT"}


def find_provenance(full_text: str, quote: str, default_page: int = 1) -> dict[str, Any]:
    if not quote or not full_text:
        return {"page": default_page, "char_start": 0, "char_end": 0, "text": quote, "verified": False}
    clean_q = quote.strip()
    idx = full_text.find(clean_q)
    if idx >= 0:
        return {
            "page": default_page,
            "char_start": idx,
            "char_end": idx + len(clean_q),
            "text": clean_q,
            "verified": True,
        }
    return {"page": default_page, "char_start": 0, "char_end": 0, "text": clean_q, "verified": False}


def parse_experiences(section_text: str, full_doc_text: str) -> list[dict[str, Any]]:
    lines = [l.strip() for l in section_text.splitlines() if l.strip()]
    entries: list[dict[str, Any]] = []

    date_lines = []
    for idx, l in enumerate(lines):
        m = RANGE_REGEX.search(l)
        if m:
            date_lines.append((idx, m.group(1), m.group(2), m.start(), m.end()))

    for i, (idx, raw_start, raw_end, m_start, _m_end) in enumerate(date_lines):
        ref_y = ""
        m_y = re.search(r"\b(\d{4})\b", raw_start)
        if m_y:
            ref_y = m_y.group(1)

        start_date = norm_single_date(raw_start, is_end=False, ref_year=ref_y)
        end_date = norm_single_date(raw_end, is_end=True, ref_year=ref_y)

        curr_line = lines[idx]
        pre_text = curr_line[:m_start].strip()

        title = ""
        org = ""

        if pre_text:
            parts = re.split(r"[—|]", pre_text)
            if len(parts) >= 2:
                title = parts[0].strip()
                org = parts[1].strip().split(",")[0].strip()
            else:
                title = pre_text.strip()
        elif idx > 0:
            prev_line = lines[idx - 1]
            parts = re.split(r"[—|]", prev_line)
            if len(parts) >= 2:
                title = parts[0].strip()
                org = parts[1].strip().split(",")[0].strip()
            else:
                title = prev_line.strip()
                if idx > 1:
                    org = lines[idx - 2].strip()

        next_idx = date_lines[i + 1][0] if i + 1 < len(date_lines) else len(lines)
        bullet_lines = lines[idx + 1 : next_idx]
        block_text = " ".join([curr_line] + bullet_lines).lower()

        # Context & employment type classification
        emp_type = "full_time"
        context_type = "experience"
        if "intern" in block_text or "magang" in block_text:
            emp_type = "internship"
            context_type = "internship"
        elif "freelance" in block_text or "lepas" in block_text:
            emp_type = "freelance"
            context_type = "freelance"
        elif "kontrak" in block_text or "contract" in block_text:
            emp_type = "contract"
        elif "part-time" in block_text or "paruh waktu" in block_text:
            emp_type = "part_time"

        bullets = []
        for bl in bullet_lines:
            bl_clean = bl.lstrip("•-* ").strip()
            if len(bl_clean) > 5 and not RANGE_REGEX.search(bl):
                bullets.append(
                    {
                        "text": bl_clean,
                        "source": find_provenance(full_doc_text, bl_clean),
                        "has_quantified_result": bool(
                            re.search(r"\d+[%kKmM]|meningkatkan|menurunkan|cut|reduced", bl_clean)
                        ),
                    }
                )

        if title:
            title = re.split(r"[—|]", title)[0].strip()
            entries.append(
                {
                    "entry_id": f"exp_{len(entries) + 1}",
                    "title": title,
                    "organization": org,
                    "start": start_date,
                    "end": end_date,
                    "context": context_type,
                    "employment_type": emp_type,
                    "bullets": bullets,
                    "source": find_provenance(full_doc_text, title),
                }
            )

    return entries


def parse_skills(section_text: str) -> list[str]:
    items = re.split(r"[,•\n\r]+", section_text)
    cleaned = []
    for it in items:
        s = it.strip().strip("-*").strip()
        if s and len(s) < 50 and not s.lower().startswith("keahlian"):
            cleaned.append(s)
    return cleaned


def parse_certifications(ce_text: str, ed_text: str) -> list[str]:
    combined = ce_text
    if "sertifikasi" in ed_text.lower() or "certification" in ed_text.lower():
        parts = re.split(r"~?\s*(?:sertifikasi|certifications?)\b", ed_text, flags=re.IGNORECASE)
        if len(parts) > 1:
            combined += "\n" + parts[1]

    lines = [l.strip().lstrip("-•*~ ").strip() for l in combined.splitlines() if l.strip()]
    merged = []
    curr = ""
    for l in lines:
        if curr and (
            l.startswith("Developer")
            or l.startswith("Engineer")
            or l.startswith("(")
            or l.startswith("—")
            or l.startswith("-")
        ):
            curr += " " + l
        else:
            if curr:
                merged.append(curr)
            curr = l
    if curr:
        merged.append(curr)

    return [
        l for l in merged if len(l) > 3 and not l.lower().startswith("keahlian") and not l.lower().startswith("skills")
    ]


def parse_education(section_text: str, full_doc_text: str) -> list[dict[str, Any]]:
    levels = []
    t = section_text.lower()
    if re.search(r"\bs1\b|sarjana|bachelor", t):
        levels.append("S1")
    if re.search(r"\bs2\b|magister|master", t):
        levels.append("S2")
    if re.search(r"\bd3\b|diploma 3|diploma iii", t):
        levels.append("D3")
    if re.search(r"\bd4\b|diploma 4|diploma iv", t):
        levels.append("D4")
    if re.search(r"\bsmk\b", t):
        levels.append("SMK")
    if re.search(r"\bsma\b", t):
        levels.append("SMA")
    if not levels and re.search(r"universitas|institut|politeknik|college", t):
        levels.append("S1")

    entries = []
    for idx, lvl in enumerate(levels):
        entries.append(
            {
                "entry_id": f"edu_{idx + 1}",
                "level": lvl,
                "degree_raw": section_text.splitlines()[0] if section_text else lvl,
                "institution": section_text.splitlines()[1] if len(section_text.splitlines()) > 1 else "",
                "source": find_provenance(full_doc_text, lvl),
            }
        )
    return entries


def extract_candidate_profile(content: bytes, filename: str) -> dict[str, Any]:
    service = get_extractor_service()
    raw = service.extract(content, filename).to_dict()

    sec_map: dict[str, list[str]] = {}
    for s in raw.get("sections", []):
        sec_map.setdefault(s["label"], []).append(s.get("text", ""))

    exp_text = "\n".join(sec_map.get("experience", []))
    sk_text = "\n".join(sec_map.get("skills", []))
    ce_text = "\n".join(sec_map.get("certifications", []))
    ed_text = "\n".join(sec_map.get("education", []))
    sum_text = "\n".join(sec_map.get("summary", []))
    prj_text = "\n".join(sec_map.get("projects", []))
    org_text = "\n".join(sec_map.get("organizations", []))

    full_text = "\n".join(s.get("text", "") for s in raw.get("sections", []))

    # Parse sections
    experiences = parse_experiences(exp_text, full_text)
    education = parse_education(ed_text, full_text)
    certifications = parse_certifications(ce_text, ed_text)
    skills = parse_skills(sk_text)

    # Demographics & Identity
    contact = raw.get("contact", {})
    emails = contact.get("emails", [])
    phones = contact.get("phones", [])
    links = contact.get("urls", [])
    if contact.get("linkedin"):
        links.append(contact["linkedin"])

    # Look for demographic lines in full text
    other_personal = {}
    m_gender = re.search(r"jenis\s+kelamin\s*:\s*([^\n]+)", full_text, re.IGNORECASE)
    if m_gender:
        other_personal["gender"] = m_gender.group(1).strip()
    m_rel = re.search(r"agama\s*:\s*([^\n]+)", full_text, re.IGNORECASE)
    if m_rel:
        other_personal["religion"] = m_rel.group(1).strip()
    m_dob = re.search(r"tanggal\s+lahir\s*:\s*([^\n]+)", full_text, re.IGNORECASE)
    if m_dob:
        other_personal["date_of_birth"] = m_dob.group(1).strip()
    m_mar = re.search(r"status(?:\s+pernikahan)?\s*:\s*([^\n]+)", full_text, re.IGNORECASE)
    if m_mar:
        other_personal["marital_status"] = m_mar.group(1).strip()

    identity = {
        "full_name": raw.get("name"),
        "email": emails[0] if emails else None,
        "phone": phones[0] if phones else None,
        "location_raw": contact.get("location"),
        "links": links,
        "other_personal": other_personal,
    }

    projects = []
    if prj_text:
        projects.append(
            {
                "entry_id": "prj_1",
                "title": prj_text.splitlines()[0] if prj_text else "Proyek",
                "text": prj_text,
                "source": find_provenance(full_text, prj_text[:40]),
            }
        )

    organizations = []
    if org_text:
        organizations.append(
            {
                "entry_id": "org_1",
                "title": org_text.splitlines()[0] if org_text else "Organisasi",
                "text": org_text,
                "source": find_provenance(full_text, org_text[:40]),
            }
        )

    profile = {
        "document_id": filename,
        "extractor": {
            "name": "cv-extractor",
            "version": "1.0.0",
            "ocr_used": raw.get("meta", {}).get("llm_used", False)
            or any(p.get("source") == "ocr" for p in raw.get("meta", {}).get("pages", [])),
        },
        "language": ["id"],
        "identity": identity,
        "headline": raw.get("headline"),
        "summary": sum_text,
        "experiences": experiences,
        "education": education,
        "certifications": certifications,
        "skills": skills,
        "projects": projects,
        "organizations": organizations,
        "quality": {
            "confidence": raw.get("meta", {}).get("confidence", 1.0),
            "warnings": raw.get("meta", {}).get("warnings", []),
        },
    }
    return profile
