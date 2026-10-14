"""Administrative Eligibility Gate evaluation module (FX-24 Revision 2).

Enforces:
- I-1: Competency scores (skills, experience, education) are 100% blind and unaffected.
- I-2: Demographic data (DOB, gender) NEVER enters LLM prompts or scoring rubrics.
- I-3: Zero automated rejection (Human-in-the-Loop only via badges/filters).
- I-4: Modern CVs without DOB/gender get UNKNOWN status (never disqualified).
- I-5: Explicit candidate data only (no graduation inference or photo/name guessing).
- I-6: Requires HR written justification (min 30 chars) and ADMIN approval.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

DATE_FORMATS = [
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%d %B %Y",
    "%d %b %Y",
]

INDONESIAN_MONTHS = {
    "januari": "january",
    "februari": "february",
    "maret": "march",
    "april": "april",
    "mei": "may",
    "juni": "june",
    "juli": "july",
    "agustus": "august",
    "september": "september",
    "oktober": "october",
    "november": "november",
    "desember": "december",
}


def parse_date_of_birth(val: Any) -> date | None:
    """Parses explicit date of birth string into date object."""
    if not val:
        return None
    if isinstance(val, date):
        return val

    s = str(val).strip().lower()
    for id_mo, en_mo in INDONESIAN_MONTHS.items():
        s = s.replace(id_mo, en_mo)

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue

    # Try matching YYYY-MM-DD pattern
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # Try matching DD-MM-YYYY pattern
    m_rev = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", s)
    if m_rev:
        try:
            return date(int(m_rev.group(3)), int(m_rev.group(2)), int(m_rev.group(1)))
        except ValueError:
            pass

    return None


def calculate_age(dob: date, as_of: date) -> int:
    """Calculates integer age exactly as of reference date."""
    return as_of.year - dob.year - ((as_of.month, as_of.day) < (dob.month, dob.day))


def normalize_gender(val: Any) -> str | None:
    """Normalizes gender string into 'M' (Male/Laki-laki) or 'F' (Female/Perempuan)."""
    if not val:
        return None
    s = str(val).strip().lower()
    if s in ("l", "laki-laki", "pria", "male", "m"):
        return "M"
    if s in ("p", "perempuan", "wanita", "female", "f"):
        return "F"
    return None


def evaluate_candidate_eligibility(
    identity_data: dict[str, Any],
    rules: list[dict[str, Any]],
    as_of: date,
) -> dict[str, Any]:
    """Evaluates an explicit candidate identity against active administrative eligibility rules.

    Returns:
    {
        "overall_status": "ELIGIBLE" | "NOT_ELIGIBLE" | "UNKNOWN",
        "reference_date": as_of.isoformat(),
        "evaluations": [
            {
                "rule_id": str,
                "category": "AGE" | "GENDER",
                "status": "ELIGIBLE" | "NOT_ELIGIBLE" | "UNKNOWN",
                "reason": str
            }
        ]
    }
    """
    if not rules:
        return {
            "overall_status": "ELIGIBLE",
            "reference_date": as_of.isoformat(),
            "evaluations": [],
        }

    other_personal = identity_data.get("other_personal") or {}
    if isinstance(other_personal, str):
        import json

        try:
            other_personal = json.loads(other_personal)
        except Exception:
            other_personal = {}

    dob_val = identity_data.get("date_of_birth") or other_personal.get("date_of_birth") or other_personal.get("dob")
    raw_gender = identity_data.get("gender") or other_personal.get("gender")

    dob = parse_date_of_birth(dob_val)
    gender = normalize_gender(raw_gender)
    calculated_age = calculate_age(dob, as_of) if dob else None

    evaluations: list[dict[str, Any]] = []
    has_not_eligible = False
    has_unknown = False

    for rule in rules:
        if not rule.get("is_active"):
            continue

        category = rule.get("category")
        rule_type = rule.get("rule_type")
        params = rule.get("parameters") or {}
        rule_id = str(rule.get("id"))

        if category == "AGE":
            if calculated_age is None:
                eval_status = "UNKNOWN"
                reason = "Tanggal lahir tidak dicantumkan di CV"
            else:
                if rule_type == "MAX_AGE":
                    max_age = int(params.get("max_age", 99))
                    if calculated_age <= max_age:
                        eval_status = "ELIGIBLE"
                        reason = f"Usia kandidat {calculated_age} tahun memenuhi batas maksimal {max_age} tahun"
                    else:
                        eval_status = "NOT_ELIGIBLE"
                        reason = f"Usia kandidat {calculated_age} tahun melebihi batas maksimal {max_age} tahun"
                elif rule_type == "MIN_AGE":
                    min_age = int(params.get("min_age", 0))
                    if calculated_age >= min_age:
                        eval_status = "ELIGIBLE"
                        reason = f"Usia kandidat {calculated_age} tahun memenuhi batas minimal {min_age} tahun"
                    else:
                        eval_status = "NOT_ELIGIBLE"
                        reason = f"Usia kandidat {calculated_age} tahun di bawah batas minimal {min_age} tahun"
                elif rule_type == "AGE_RANGE":
                    min_age = int(params.get("min_age", 0))
                    max_age = int(params.get("max_age", 99))
                    if min_age <= calculated_age <= max_age:
                        eval_status = "ELIGIBLE"
                        reason = f"Usia kandidat {calculated_age} tahun berada dalam rentang {min_age}-{max_age} tahun"
                    else:
                        eval_status = "NOT_ELIGIBLE"
                        reason = f"Usia kandidat {calculated_age} tahun di luar rentang {min_age}-{max_age} tahun"
                else:
                    eval_status = "UNKNOWN"
                    reason = f"Tipe aturan usia {rule_type} tidak dikenali"

        elif category == "GENDER":
            if gender is None:
                eval_status = "UNKNOWN"
                reason = "Informasi jenis kelamin tidak dicantumkan di CV"
            else:
                target_gender = normalize_gender(params.get("gender") or params.get("target_gender"))
                if target_gender and gender == target_gender:
                    eval_status = "ELIGIBLE"
                    reason = "Jenis kelamin kandidat sesuai kualifikasi lowongan"
                else:
                    eval_status = "NOT_ELIGIBLE"
                    reason = "Jenis kelamin kandidat tidak sesuai kualifikasi lowongan"
        else:
            eval_status = "UNKNOWN"
            reason = f"Kategori aturan {category} tidak didukung"

        if eval_status == "NOT_ELIGIBLE":
            has_not_eligible = True
        elif eval_status == "UNKNOWN":
            has_unknown = True

        evaluations.append(
            {
                "rule_id": rule_id,
                "category": category,
                "rule_type": rule_type,
                "status": eval_status,
                "reason": reason,
                "reference_date": as_of.isoformat(),
            }
        )

    if has_not_eligible:
        overall_status = "NOT_ELIGIBLE"
    elif has_unknown:
        overall_status = "UNKNOWN"
    else:
        overall_status = "ELIGIBLE"

    return {
        "overall_status": overall_status,
        "reference_date": as_of.isoformat(),
        "evaluations": evaluations,
    }
