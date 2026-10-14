"""Job description compiler parsing JD text into structured requirements with concept mapping."""

from __future__ import annotations

import re
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.domain.policy_linter import lint_text
from src.infrastructure.gateway import gateway
from src.infrastructure.logging import logger

VALID_IMPORTANCE = {"MUST_HAVE", "STRONG_PREFERENCE", "NICE_TO_HAVE"}
VALID_CATEGORIES = {"EXPERIENCE", "HARD_SKILLS", "EDUCATION_CERT", "ACHIEVEMENT"}
MUST_HAVE_KEYWORDS = {"wajib", "harus", "must", "required", "minimum", "minimal", "essential"}
NICE_TO_HAVE_KEYWORDS = {"nilai tambah", "plus", "preferred", "nice to have", "diutamakan", "keuntungan"}


class CompiledRequirement(BaseModel):
    requirement_id: str
    description: str
    category: str = "HARD_SKILLS"
    kind: str = "SKILL"
    importance: Literal["MUST_HAVE", "STRONG_PREFERENCE", "NICE_TO_HAVE"]
    weight: float = Field(default=10.0, gt=0)
    concepts: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    source_text: str = ""


def determine_importance(line: str, default: str = "STRONG_PREFERENCE") -> str:
    lower = line.lower()
    if any(k in lower for k in MUST_HAVE_KEYWORDS):
        return "MUST_HAVE"
    if any(k in lower for k in NICE_TO_HAVE_KEYWORDS):
        return "NICE_TO_HAVE"
    return default


DEFAULT_CATEGORY_WEIGHTS = {
    "EXPERIENCE": 40,
    "HARD_SKILLS": 30,
    "EDUCATION_CERT": 15,
    "ACHIEVEMENT": 15,
}

CONCEPT_RULES = [
    (
        r"backend\s+engineer|backend\s+developer",
        ["role_family:backend"],
        "EXPERIENCE",
        "EXPERIENCE_DURATION",
        "MUST_HAVE",
        25,
    ),
    (
        r"rest\s+api|microservices",
        ["skill:rest_api", "skill:microservices"],
        "EXPERIENCE",
        "RESPONSIBILITY",
        "STRONG_PREFERENCE",
        15,
    ),
    (r"python|fastapi|django|flask", ["skill:python"], "HARD_SKILLS", "SKILL", "MUST_HAVE", 10),
    (r"postgresql|postgres", ["skill:postgresql"], "HARD_SKILLS", "SKILL", "MUST_HAVE", 8),
    (r"docker", ["skill:docker"], "HARD_SKILLS", "SKILL", "STRONG_PREFERENCE", 6),
    (
        r"kubernetes|k8s|cloud\s*\(aws|gcp|azure",
        ["skill:kubernetes", "skill:cloud"],
        "HARD_SKILLS",
        "SKILL",
        "NICE_TO_HAVE",
        6,
    ),
    (r"memimpin|membimbing|mentoring", ["skill:mentoring"], "EXPERIENCE", "RESPONSIBILITY", "NICE_TO_HAVE", 5),
    (r"sertifikasi\s+cloud|certified", ["cert:cloud"], "EDUCATION_CERT", "CERTIFICATION", "NICE_TO_HAVE", 5),
    (
        r"pencapaian\s+terukur|skala|efisiensi",
        ["achievement:quantified_backend"],
        "ACHIEVEMENT",
        "ACHIEVEMENT",
        "NICE_TO_HAVE",
        10,
    ),
    (
        r"s1\s+teknik\s+informatika|ilmu\s+komputer|sistem\s+informasi",
        ["field:computing"],
        "EDUCATION_CERT",
        "EDUCATION",
        "STRONG_PREFERENCE",
        10,
    ),
]


def compile_jd_rule_based(jd_text: str) -> list[dict[str, Any]]:
    """Deterministic fallback parser mapping bullet points and requirements to concept taxonomy."""
    requirements = []
    raw_lines = [line.strip() for line in jd_text.splitlines() if line.strip()]

    matched_concepts: set[str] = set()
    req_idx = 1

    for orig_line in raw_lines:
        line = orig_line.lstrip("-*• 0123456789.)").strip()
        if len(line) < 8 or line.startswith("#"):
            continue

        matched = False
        for pat, concepts, category, kind, default_importance, default_weight in CONCEPT_RULES:
            if re.search(pat, line, re.IGNORECASE):
                # Avoid duplicate rules for same concept
                c_key = concepts[0]
                if c_key in matched_concepts:
                    matched = True
                    break
                matched_concepts.add(c_key)

                # Importance from line wording
                importance = determine_importance(line, default_importance)

                lint_res = lint_text(line)

                requirements.append(
                    {
                        "requirement_id": f"R{req_idx}",
                        "description": line,
                        "category": category,
                        "kind": kind,
                        "importance": importance,
                        "weight": default_weight,
                        "concepts": concepts,
                        "params": {},
                        "source_text": line,
                        "lint_flags": lint_res["prohibited_flags"] + lint_res["risky_flags"],
                    }
                )
                req_idx += 1
                matched = True
                break

        if not matched and (orig_line.startswith(("-", "*", "•")) or re.match(r"^\d+[\.\)]", orig_line)):
            lower = line.lower()
            is_exp = "tahun" in lower or "pengalaman" in lower or "experience" in lower
            is_edu = any(
                k in lower for k in ["s1", "s2", "d3", "gelar", "pendidikan", "degree", "sertifikasi", "certified"]
            )
            cat = "EXPERIENCE" if is_exp else ("EDUCATION_CERT" if is_edu else "HARD_SKILLS")
            knd = "EXPERIENCE_DURATION" if is_exp else ("EDUCATION" if is_edu else "SKILL")
            imp = determine_importance(line, "STRONG_PREFERENCE")
            lint_res = lint_text(line)
            requirements.append(
                {
                    "requirement_id": f"R{req_idx}",
                    "description": line,
                    "category": cat,
                    "kind": knd,
                    "importance": imp,
                    "weight": 10,
                    "concepts": [],
                    "params": {},
                    "source_text": line,
                    "lint_flags": lint_res["prohibited_flags"] + lint_res["risky_flags"],
                }
            )
            req_idx += 1

    return requirements


EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"(?:\+62|62|08)[0-9\s-]{8,15}")


async def compile_job_requirements(jd_text: str, tenant_id: uuid.UUID | None = None) -> dict[str, Any]:
    """Compiles Job Description into structured requirement set using 9Router with deterministic fallback."""
    # Check overall JD text for prohibited criteria
    overall_lint = lint_text(jd_text)

    # Sanitize any recruiter contact details from JD text before sending to LLM
    clean_jd_text = EMAIL_REGEX.sub("[KONTAK_HR]", jd_text)
    clean_jd_text = PHONE_REGEX.sub("[KONTAK_HR]", clean_jd_text)

    # Attempt LLM compilation via 9Router
    prompt = (
        "Kamu adalah compiler Job Description menjadi kriteria screening terstruktur.\n"
        "Analisis teks lowongan ini dan hasilkan JSON array 'requirements' dengan field:\n"
        "- requirement_id (R1, R2, ...)\n"
        "- description (teks deskripsi)\n"
        "- category (EXPERIENCE, HARD_SKILLS, EDUCATION_CERT, ACHIEVEMENT)\n"
        "- kind (EXPERIENCE_DURATION, RESPONSIBILITY, SKILL, EDUCATION, CERTIFICATION, ACHIEVEMENT)\n"
        "- importance (MUST_HAVE, STRONG_PREFERENCE, NICE_TO_HAVE)\n"
        "- weight (angka 1-30)\n"
        "- concepts (array concept_id seperti role_family:backend, skill:python, skill:postgresql, skill:docker)\n"
        "- source_text (kalimat asli dari JD)\n\n"
        f"Teks Job Description:\n{clean_jd_text}"
    )

    try:
        llm_res = await gateway.call_chat(
            messages=[{"role": "user", "content": prompt}],
            task="jd_compilation",
            tenant_id=tenant_id,
            json_mode=True,
        )
    except Exception as e:
        logger.warning(f"LLM compilation failed, falling back to rule-based: {e}")
        llm_res = None

    requirements = []
    req_list = []
    if isinstance(llm_res, list):
        req_list = llm_res
    elif isinstance(llm_res, dict) and isinstance(llm_res.get("requirements"), list):
        req_list = llm_res["requirements"]

    validated_reqs = []
    if req_list:
        try:
            for idx, item in enumerate(req_list, 1):
                raw_imp = str(item.get("importance", "")).upper()
                if raw_imp not in VALID_IMPORTANCE:
                    raw_imp = determine_importance(item.get("description", "") or item.get("source_text", ""))

                raw_wt = float(item.get("weight") or 10.0)
                if raw_wt <= 0:
                    raw_wt = 10.0

                desc = item.get("description", "")
                r_lint = lint_text(desc)
                concepts = list(item.get("concepts", []))
                for pat, c_list, _cat, _knd, _imp, _wt in CONCEPT_RULES:
                    if re.search(pat, desc, re.IGNORECASE) or re.search(
                        pat, item.get("source_text", ""), re.IGNORECASE
                    ):
                        for c in c_list:
                            if c not in concepts:
                                concepts.append(c)

                model = CompiledRequirement(
                    requirement_id=item.get("requirement_id") or f"R{idx}",
                    description=desc,
                    category=item.get("category") if item.get("category") in VALID_CATEGORIES else "HARD_SKILLS",
                    kind=item.get("kind") or "SKILL",
                    importance=raw_imp,  # type: ignore[arg-type]
                    weight=raw_wt,
                    concepts=concepts,
                    params=item.get("params") or {},
                    source_text=item.get("source_text") or desc,
                )
                req_dict = model.model_dump()
                req_dict["lint_flags"] = r_lint["prohibited_flags"] + r_lint["risky_flags"]
                validated_reqs.append(req_dict)
        except Exception as e:
            logger.warning(f"Validation failed for LLM requirements output: {e}, falling back to rule-based.")
            validated_reqs = []

    if validated_reqs:
        requirements = validated_reqs
    else:
        # Deterministic rule-based fallback
        requirements = compile_jd_rule_based(jd_text)

    # Attach any overall JD prohibited flags to requirements or set level
    all_prohibited = list(overall_lint["prohibited_flags"])
    for r in requirements:
        all_prohibited.extend([f for f in r.get("lint_flags", []) if f.startswith("PROHIBITED_")])
    all_prohibited = sorted(list(set(all_prohibited)))

    return {
        "status": "DRAFT",
        "category_weights": DEFAULT_CATEGORY_WEIGHTS,
        "requirements": requirements,
        "is_valid": len(all_prohibited) == 0,
        "prohibited_flags": all_prohibited,
        "risky_flags": overall_lint["risky_flags"],
    }
