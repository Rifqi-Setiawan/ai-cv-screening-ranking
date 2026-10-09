"""LLM Verifier for ambiguous requirements (02_SCORING Section 5)."""

from __future__ import annotations

import contextlib
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from src.infrastructure.gateway import call_dev_llm

VALID_STATES = {"STRONG", "PARTIAL", "NOT_DEMONSTRATED"}
CACHE_FILE = Path("data/verifier_cache.json")


def _get_cache() -> dict[str, Any]:
    if CACHE_FILE.exists():
        with contextlib.suppress(Exception):
            return json.loads(CACHE_FILE.read_text())
    return {}


def _save_cache(cache: dict[str, Any]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(Exception):
        CACHE_FILE.write_text(json.dumps(cache, indent=2))


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
    5. Cache lookup to avoid redundant calls.
    """
    if not cv_full_text or not snippets:
        return rule_state, "", []

    cache_key = hashlib.sha256(
        f"{requirement.get('requirement_id')}:{requirement.get('kind')}:{rule_state}:{':'.join(snippets)}".encode()
    ).hexdigest()

    cache = _get_cache()
    if cache_key in cache:
        item = cache[cache_key]
        return item["state"], item["quote"], item["flags"]

    prompt = f"""Kamu adalah verifier kualifikasi kandidat CV.
Tugas: Periksa apakah bukti CV mendukung kualifikasi berikut.

Kriteria: {requirement.get("description", "")}
Kategori: {requirement.get("category", "")}
Kind: {requirement.get("kind", "")}

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
    system_prompt = "Kamu adalah JSON-only assistant. Jawab HANYA dalam JSON valid tanpa markdown formatting."

    resp = call_dev_llm(prompt, system_prompt=system_prompt)
    if not resp or resp.get("status") != "SUCCESS":
        return rule_state, "", []

    raw_text = resp.get("response", "")

    try:
        # Handle dict or string wrapping
        if isinstance(raw_text, str):
            try:
                top_data = json.loads(raw_text)
            except Exception:
                top_data = raw_text
        else:
            top_data = raw_text

        text_to_parse = top_data
        if isinstance(top_data, dict):
            if "raw_content" in top_data:
                text_to_parse = top_data["raw_content"]
            elif "state" in top_data:
                data = top_data
                text_to_parse = None

        if text_to_parse is not None:
            text_str = str(text_to_parse).strip()
            # Strip code fences
            m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text_str)
            if m:
                text_str = m.group(1).strip()
            data = json.loads(text_str)

        state = str(data.get("state", "")).upper()
        quote = str(data.get("quote", "")).strip()

        if state not in VALID_STATES:
            return rule_state, "", ["INVALID_LLM_STATE"]

        # Code-level grounding check: quote must be in cv_full_text
        if quote and quote.lower() in cv_full_text.lower():
            cache[cache_key] = {"state": state, "quote": quote, "flags": []}
            _save_cache(cache)
            return state, quote, []
        else:
            # Grounding failed: fallback to rule_state with GROUNDING_FAIL flag
            cache[cache_key] = {"state": rule_state, "quote": "", "flags": ["GROUNDING_FAIL"]}
            _save_cache(cache)
            return rule_state, "", ["GROUNDING_FAIL"]

    except Exception:
        return rule_state, "", ["LLM_PARSE_ERROR"]
