"""Document ingestion, parsing, redaction, and embedding pipeline processor."""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from src.infrastructure.config import settings
from src.infrastructure.database import get_connection
from src.infrastructure.logging import logger
from src.worker.adapter import extract_candidate_profile
from src.worker.embedding import embed_texts
from src.worker.redaction import extract_identity_and_redact
from src.worker.sanitizer import sanitize_file


async def process_document(doc_id: uuid.UUID) -> dict[str, Any]:
    logger.info(f"Starting processing for document {doc_id}...")
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT id, tenant_id, job_id, original_filename, size_bytes, sha256, storage_key, status
            FROM documents
            WHERE id = %s
            """,
            (doc_id,),
        )
        doc = await cur.fetchone()
        if not doc:
            logger.error(f"Document {doc_id} not found")
            return {"status": "NOT_FOUND"}

        vault_file = Path(settings.STORAGE_VAULT_PATH) / str(doc["tenant_id"]) / doc["storage_key"]
        if not vault_file.exists():
            logger.error(f"Vault file {vault_file} missing on disk")
            await cur.execute(
                "UPDATE documents SET status = 'REJECTED', reasons = ARRAY['File missing in storage'] WHERE id = %s",
                (doc_id,),
            )
            await conn.commit()
            return {"status": "REJECTED", "error": "file_missing"}

        content = vault_file.read_bytes()
        filename = doc["original_filename"]

        # 1. Sanitize file & inspect edge cases
        san = sanitize_file(content, filename)
        if not san.is_valid or san.status == "REJECTED":
            await cur.execute(
                """
                UPDATE documents
                SET status = 'REJECTED', reasons = %s, flags = %s
                WHERE id = %s
                """,
                (san.reasons, san.flags, doc_id),
            )
            await conn.commit()
            logger.info(f"Document {filename} REJECTED: {san.reasons}")
            return {"status": "REJECTED", "reasons": san.reasons}

        # 2. Check Deduplication against other documents in the same job
        await cur.execute(
            """
            SELECT id, original_filename
            FROM documents
            WHERE job_id = %s AND sha256 = %s AND id != %s AND status IN ('READY', 'RECEIVED', 'NEEDS_REVIEW')
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (doc["job_id"], doc["sha256"], doc_id),
        )
        dup_row = await cur.fetchone()
        if dup_row:
            await cur.execute(
                """
                UPDATE documents
                SET status = 'DUPLICATE', duplicate_of = %s
                WHERE id = %s
                """,
                (dup_row["id"], doc_id),
            )
            await conn.commit()
            logger.info(f"Document {filename} marked as DUPLICATE of {dup_row['original_filename']}")
            return {"status": "DUPLICATE", "duplicate_of": dup_row["original_filename"]}

        # If empty content or not a CV -> mark NEEDS_REVIEW
        if san.status == "NEEDS_REVIEW":
            await cur.execute(
                """
                UPDATE documents
                SET status = 'NEEDS_REVIEW', reasons = %s, flags = %s
                WHERE id = %s
                """,
                (san.reasons, san.flags, doc_id),
            )
            await conn.commit()
            logger.info(f"Document {filename} marked as NEEDS_REVIEW: {san.reasons}")
            return {"status": "NEEDS_REVIEW", "reasons": san.reasons}

        # 3. Extract Candidate Profile via production adapter
        raw_profile = extract_candidate_profile(content, filename)

        # 4. Separate Identity and Redact Matching Profile
        identity_rec, matching_profile, chunks = extract_identity_and_redact(raw_profile)

        # 5. Create Candidate record
        await cur.execute(
            "SELECT count(*) as cnt FROM candidates WHERE tenant_id = %s",
            (doc["tenant_id"],),
        )
        cnt_row = await cur.fetchone()
        code_num = (cnt_row["cnt"] if cnt_row else 0) + 1
        candidate_code = f"C-{code_num:04d}"

        candidate_id = uuid.uuid4()
        await cur.execute(
            """
            INSERT INTO candidates (id, tenant_id, candidate_code, status)
            VALUES (%s, %s, %s, 'ACTIVE')
            """,
            (candidate_id, doc["tenant_id"], candidate_code),
        )

        # 6. Save Identity
        other_p_bytes = json.dumps(identity_rec["other_personal"]).encode("utf-8")
        await cur.execute(
            """
            INSERT INTO candidate_identities (
                candidate_id, tenant_id, full_name, email, phone, location_raw, other_personal
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                candidate_id,
                doc["tenant_id"],
                identity_rec["full_name"],
                identity_rec["email"],
                identity_rec["phone"],
                identity_rec["location_raw"],
                other_p_bytes,
            ),
        )

        # 7. Save Candidate Profile
        profile_id = uuid.uuid4()
        quality_flags = list(set(san.flags + raw_profile.get("quality", {}).get("warnings", [])))
        await cur.execute(
            """
            INSERT INTO candidate_profiles (
                id, tenant_id, document_id, profile, matching_profile, extractor_version, quality
            )
            VALUES (%s, %s, %s, %s, %s, 'cv-extractor-1.0.0', %s)
            """,
            (
                profile_id,
                doc["tenant_id"],
                doc_id,
                json.dumps(raw_profile),
                json.dumps(matching_profile),
                json.dumps({"flags": quality_flags, "confidence": san.is_valid}),
            ),
        )

        # 8. Generate & Insert Profile Chunks with Embeddings
        chunk_texts = [c["text_redacted"] for c in chunks]
        embeddings = embed_texts(chunk_texts)

        for c, emb in zip(chunks, embeddings):
            c_hash = hashlib.sha256(c["text_redacted"].encode()).hexdigest()
            await cur.execute(
                """
                INSERT INTO profile_chunks (
                    tenant_id, profile_id, kind, entry_ref, text_redacted, chunk_hash, embedding, embedding_model
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    doc["tenant_id"],
                    profile_id,
                    c["kind"],
                    c["entry_ref"],
                    c["text_redacted"],
                    c_hash,
                    emb,
                    settings.EMBEDDING_MODEL,
                ),
            )

        # 9. Link Candidate ID and Mark Document READY
        doc_status = "READY"
        await cur.execute(
            """
            UPDATE documents
            SET status = %s, candidate_id = %s, flags = %s, reasons = '{}'::text[]
            WHERE id = %s
            """,
            (doc_status, candidate_id, quality_flags, doc_id),
        )
        await conn.commit()
        logger.info(f"Successfully ingested and processed document {filename} (status: {doc_status})")
        return {"status": doc_status, "profile_id": str(profile_id), "candidate_code": candidate_code}
