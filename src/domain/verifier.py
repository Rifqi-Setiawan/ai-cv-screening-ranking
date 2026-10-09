"""LLM Verifier for ambiguous requirements (02_SCORING Section 5)."""
from __future__ import annotations

import json
from typing import Any

from src.infrastructure.gateway import call_dev_llm

VALID_STATES = {"STRONG", "PARTIAL", "NOT_DEMONSTRATED"}


def verify_requirement_with_llm(
    cv_full_text: str,
    requirement: dict[str, Any],
    rule_state: str,
    snippets: list[str],
) -> tuple[str, str, list[str]]:
    """Verifies ambiguous requirement using LLM via 9Router.

    Enforces:
    1. Closed choices (STRONG, PARTIAL, NOT_DEMONSTRATED).
    2. Code-level grounding verification (quote must exist in raw CV text).
    3. Grounding failure fallbacks cleanly to rule_state + GROUNDING_FAIL flag.
    4. LLM NEVER outputs numeric scores.
    """
    if not cv_full_text or not snippets:
        return rule_state, "", []

    prompt = f"""Kamu adalah verifier kualifikasi kandidat CV.
Tugas: Periksa apakah bukti CV mendukung kualifikasi berikut.

Kriteria: {requirement.get('description', '')}
Kategori: {requirement.get('category', '')}
Kind: {requirement.get('kind', '')}

Potongan teks relevan dari CV kandidat:
{chr(10).join(f"- {s}" for s in snippets[:3])}

Pilihan status yang diizinkan HANYA:
- STRONG: Bukti sangat jelas dan kuat di pekerjaan yang relevan
- PARTIAL: Bukti sebagian, di proyek, atau relevansi terbatas
- NOT_DEMONSTRATED: Bukti tidak ditemukan atau tidak memadai

Instruksi PENTING:
- JANGAN PERNAH mengeluarkan skor angka!
- Keluarkan JSON persis format:
{{
  "state": "STRONG" | "PARTIAL" | "NOT_DEMONSTRATED",
  "quote": "kutipan persis kata demi kata dari potongan teks di atas",
  "reason": "alasan singkat 1 kalimat"
}}
"""
    system_prompt = (
        "Kamu adalah JSON-only assistant. Jawab HANYA dalam JSON valid tanpa markdown formatting."
    )

    resp = call_dev_llm(prompt, system_prompt=system_prompt)
    if not resp or resp.get("status") != "SUCCESS":
        return rule_state, "", []

    raw_text = resp.get("response", "").strip()
    # Strip markdown fences if present
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        data = json.loads(raw_text)
        state = str(data.get("state", "")).upper()
        quote = str(data.get("quote", "")).strip()

        if state not in VALID_STATES:
            return rule_state, "", ["INVALID_LLM_STATE"]

        # Code-level grounding check: quote must be in cv_full_text
        if quote and quote.lower() in cv_full_text.lower():
            return state, quote, []
        else:
            # Grounding failed: fallback to rule_state with GROUNDING_FAIL flag
            return rule_state, "", ["GROUNDING_FAIL"]

    except Exception:
        return rule_state, "", ["LLM_PARSE_ERROR"]
