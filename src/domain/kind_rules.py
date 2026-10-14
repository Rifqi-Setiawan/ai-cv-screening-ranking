"""Pure functional evaluation rules per requirement kind (02_SCORING Section 4.2)."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from src.domain.text_match import match_skill

ROLE_FAMILY_PATTERNS = {
    "backend": [
        r"backend",
        r"back-end",
        r"api developer",
        r"software engineer.*backend",
        r"\brest\s+api\b",
        r"\bfastapi\b",
        r"\bflask\b",
        r"\bdjango\b",
    ],
    "fullstack": [r"fullstack", r"full-stack", r"full stack"],
    "frontend": [r"frontend", r"front-end", r"ui engineer"],
    "mobile": [r"mobile", r"android", r"ios", r"flutter"],
    "data": [r"data analyst", r"data engineer", r"data scientist", r"bi analyst"],
    "qa": [r"qa", r"quality assurance", r"tester", r"automation engineer"],
    "devops": [r"devops", r"sre", r"platform engineer", r"infrastructure"],
    "hr": [r"\bhr\b", r"human capital", r"recruiter", r"talent acquisition", r"sdm"],
    "business_analyst": [
        r"business analyst",
        r"analis bisnis",
        r"system analyst",
        r"analis sistem",
        r"business development",
        r"bizdev",
        r"business operation",
        r"channel developer",
        r"strategic planning",
        r"perencana strategi",
        r"konsultan bisnis",
        r"business consultant",
        r"operation.*analyst",
        r"process analyst",
    ],
    "financial_analyst": [
        r"financial analyst",
        r"finance analyst",
        r"analis keuangan",
        r"investment analyst",
        r"analis investasi",
        r"corporate finance",
        r"treasury",
        r"finance\b",
        r"keuangan",
        r"accounting",
        r"akuntansi",
        r"auditor",
    ],
    "consultant": [
        r"consultant",
        r"konsultan",
        r"management consultant",
        r"konsultan manajemen",
        r"advisory",
        r"surveyor",
        r"peneliti",
        r"researcher",
    ],
    "civil_engineering": [
        r"sipil",
        r"civil",
        r"konstruksi",
        r"construction",
        r"struktur",
        r"pelaksana",
        r"site manager",
        r"site engineer",
        r"project engineer",
        r"pengawas lapangan",
        r"pengawas proyek",
        r"estimator",
        r"drafter",
        r"survei",
        r"surveyor",
        r"tunnel",
        r"drainase",
        r"kontraktor",
        r"konsultan",
        r"quality control",
        r"qc.*piping",
        r"qc.*structure",
    ],
    "engineering": [
        r"engineer",
        r"teknik",
        r"rekayasa",
        r"drafter",
        r"pelaksana",
        r"pengawas",
        r"mandor",
    ],
}

CONCEPT_ALIASES = {
    "skill:python": ["python", "fastapi", "django", "flask"],
    "skill:postgresql": ["postgresql", "postgres", "psql", "postgre sql", "postgre"],
    "skill:mysql": ["mysql", "mariadb"],
    "skill:docker": ["docker", "dockerized", "containerized", "container", "docker compose"],
    "skill:kubernetes": ["kubernetes", "k8s", "gke", "eks", "aks"],
    "skill:redis": ["redis"],
    "skill:go": ["golang", "go ", "go/"],
    "skill:rest_api": ["rest api", "restful", "api"],
    "skill:microservices": ["microservices", "microservice", "layanan mikro"],
    "skill:aws": ["aws", "amazon web services", "ec2", "ecs", "s3", "sqs", "lambda"],
    "skill:gcp": ["google cloud", "gcp", "gke", "cloud run", "bigquery"],
    "skill:azure": ["azure", "microsoft azure"],
    "skill:recruitment": ["rekrutmen", "recruitment", "sourcing", "screening", "talent acquisition"],
    "skill:payroll": ["payroll", "penggajian", "upah"],
    "skill:bpjs": ["bpjs", "bpjs kesehatan", "bpjs ketenagakerjaan"],
    "skill:labor_law_id": ["uu ketenagakerjaan", "pkwt", "pkwtt", "hubungan industrial"],
    "role_family:civil_engineering": [
        "sipil",
        "civil",
        "konstruksi",
        "pelaksana",
        "site manager",
        "site engineer",
        "pengawas lapangan",
    ],
    "experience:civil_construction": [
        "sipil",
        "konstruksi",
        "pelaksana",
        "site engineer",
        "proyek",
        "pengawas",
        "kontraktor",
        "smelter",
        "bangunan",
    ],
    "skill:autocad": [
        "autocad",
        "cad",
        "computer aided design",
        "drafting",
        "shop drawing",
        "gambar teknik",
        "gambar kerja",
    ],
    "skill:technical_drawing": ["gambar teknik", "shop drawing", "gambar kerja", "autocad", "cad", "drafting"],
    "skill:shop_drawing": ["shop drawing", "gambar kerja", "gambar teknik", "autocad"],
    "skill:sketchup": ["sketchup", "3d modelling", "sketch up"],
    "skill:sap2000": ["sap2000", "sap 2000", "etabs", "analisis struktur"],
    "skill:etabs": ["etabs", "sap2000"],
    "skill:rab_calculation": [
        "rab",
        "rencana anggaran biaya",
        "budgeting",
        "estimasi biaya",
        "estimator",
        "bill of quantity",
        "boq",
    ],
    "skill:project_scheduling": [
        "ms project",
        "microsoft project",
        "penjadwalan",
        "scheduling",
        "kurva s",
        "manajemen proyek",
    ],
    "skill:microsoft_project": ["microsoft project", "ms project", "project"],
    "skill:earthwork": ["pekerjaan tanah", "tanah dasar", "galian", "timbunan", "cut and fill", "earthwork"],
    "skill:foundation": ["pondasi", "foundation", "tiang pancang", "bored pile", "base a"],
    "skill:concrete_work": [
        "beton",
        "concrete",
        "pembesian",
        "bekisting",
        "lean concrete",
        "rigid pavement",
        "readymix",
    ],
    "skill:drainage": ["drainase", "drainage", "saluran air", "gorong", "plumbing"],
    "skill:drainase": ["drainase", "drainage", "saluran air", "gorong", "plumbing"],
    "skill:finishing_work": ["finishing", "pekerjaan finishing", "arsitektur"],
    "skill:k3_konstruksi": [
        "k3",
        "hse",
        "keselamatan kerja",
        "keselamatan dan kesehatan kerja",
        "k3 konstruksi",
        "ahli k3",
        "bimtek k3",
    ],
    "skill:construction_safety": ["k3", "hse", "keselamatan kerja", "safety"],
    "skill:site_supervision": ["pengawas", "pengawasan", "site supervision", "pelaksana", "mandor", "site manager"],
    "skill:subcontractor_management": ["subkontraktor", "mandor", "tenaga kerja", "pekerja", "vendor"],
    "skill:progress_reporting": [
        "laporan progres",
        "laporan harian",
        "laporan mingguan",
        "laporan bulanan",
        "opname",
        "progress report",
    ],
    "skill:quality_control": ["quality control", "pengawasan mutu", "inspeksi", "qc", "qa/qc"],
    "skill:sports_facility_construction": ["lapangan", "olahraga", "sports", "stadion"],
    "skill:swimming_pool_construction": ["kolam renang", "pool", "waterwork"],
    "cert:ska": ["ska", "sertifikat keahlian", "ahli muda", "ahli madya", "ahli utama", "lpjk"],
    "cert:skt": ["skt", "sertifikat keterampilan"],
    "cert:k3_konstruksi": ["k3", "ahli k3", "k3 konstruksi", "bimtek k3", "ahli keselamatan", "hse"],
    "education:civil_engineering": [
        "teknik sipil",
        "civil engineering",
        "teknik bangunan",
        "sarjana terapan teknik sipil",
        "sipil",
    ],
    "role_family:business_analyst": [
        "business analyst",
        "analis bisnis",
        "business development",
        "consultant",
        "analyst",
        "analis",
    ],
    "role_family:management_consultant": ["consultant", "konsultan", "advisory", "strategic", "business consultant"],
    "role_family:financial_analyst": [
        "financial analyst",
        "finance analyst",
        "analis keuangan",
        "investment analyst",
        "analis investasi",
        "finance",
        "keuangan",
    ],
    "skill:microsoft_excel": [
        "excel",
        "ms excel",
        "microsoft excel",
        "spreadsheet",
        "ms. office",
        "microsoft office",
        "google sheets",
        "pivot table",
        "power query",
        "vlookup",
    ],
    "skill:financial_modeling": [
        "financial model",
        "financial modeling",
        "pemodelan keuangan",
        "model keuangan",
        "pemodelan data dan keuangan",
        "financial forecast",
        "proyeksi keuangan",
        "master budget",
        "budgeting",
        "financial projection",
    ],
    "skill:data_modeling": ["data modeling", "pemodelan data", "model data", "pemodelan data dan keuangan"],
    "skill:data_analysis": [
        "data analysis",
        "analisis data",
        "analisa data",
        "data analyst",
        "analythical thinking",
        "analytical thinking",
        "spss",
        "r studio",
        "rstudio",
        "stata",
        "warppls",
        "olah data",
        "regresi",
        "kuantitatif",
    ],
    "skill:report_writing": [
        "penulisan laporan",
        "report writing",
        "laporan bisnis",
        "rekomendasi bisnis",
        "laporan keuangan",
        "menyusun laporan",
        "membuat laporan",
        "laporan",
        "reporting",
    ],
    "skill:presentation": [
        "presentasi",
        "presentation",
        "public speaking",
        "pitch deck",
        "slide",
        "powerpoint",
        "komunikasi",
        "presentations skill",
    ],
    "skill:business_analysis": [
        "business analysis",
        "analisis bisnis",
        "analisa bisnis",
        "business analyst",
        "analis bisnis",
        "business process",
        "proses bisnis",
        "gap analysis",
        "analisis operasional",
    ],
    "skill:cash_flow_projection": ["cash flow", "arus kas", "proyeksi arus kas", "laporan arus kas", "cash management"],
    "skill:npv": ["npv", "net present value"],
    "skill:irr": ["irr", "internal rate of return"],
    "skill:sensitivity_analysis": ["analisis sensitivitas", "sensitivity analysis"],
    "skill:investment_analysis": [
        "analisis investasi",
        "investment analysis",
        "analisis kelayakan investasi",
        "investasi",
        "investment",
        "kelayakan investasi",
    ],
    "skill:market_research": ["market research", "riset pasar", "penelitian pasar", "analisis pasar", "survei pasar"],
    "skill:industry_analysis": [
        "analisis industri",
        "industry analysis",
        "competitive analysis",
        "analisis kompetitor",
        "analisis persaingan",
    ],
    "skill:feasibility_study": [
        "feasibility study",
        "studi kelayakan",
        "kelayakan bisnis",
        "kelayakan proyek",
        "analisis kelayakan",
    ],
    "skill:strategic_planning": [
        "strategic planning",
        "perencanaan strategis",
        "perencanaan strategi",
        "business plan",
        "rencana bisnis",
        "swot",
        "pestel",
        "business model canvas",
        "strategi bisnis",
    ],
    "skill:business_valuation": ["valuasi", "valuation", "business valuation", "valuasi bisnis", "penilaian bisnis"],
    "skill:risk_management": ["manajemen risiko", "risk management", "analisis risiko", "mitigasi risiko"],
    "skill:power_bi": ["power bi", "powerbi", "power-bi"],
    "skill:tableau": ["tableau"],
    "skill:data_visualization": [
        "data visualization",
        "visualisasi data",
        "dashboard",
        "tableau",
        "power bi",
        "powerbi",
        "looker",
        "looker studio",
        "google data studio",
        "vosviewer",
    ],
    "skill:sql": ["sql", "mysql", "postgresql", "ansi sql", "relational database"],
    "skill:sqlite": ["sqlite", "sqlite3"],
    "skill:java": ["java", "j2ee", "spring", "spring boot"],
    "skill:javascript": ["javascript", "js", "ecmascript", "node", "nodejs"],
}


def classify_role_family(title: str, text: str = "") -> str:
    title_lower = title.lower()
    for rf, patterns in ROLE_FAMILY_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, title_lower):
                return rf
    comb = f"{title} {text}".lower()
    for rf, patterns in ROLE_FAMILY_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, comb):
                return rf
    return "other"


def parse_ym(val: str, as_of: str = "2026-10-01") -> tuple[int, int] | None:
    if not val:
        return None
    val_clean = val.strip().lower()
    if val_clean in ("present", "sekarang", "saat ini", "kini", "now", "current"):
        as_of_date = date.fromisoformat(as_of)
        return as_of_date.year, as_of_date.month

    m = re.match(r"^(\d{4})-(\d{2})$", val_clean)
    if m:
        return int(m.group(1)), int(m.group(2))

    m_y = re.match(r"^(\d{4})$", val_clean)
    if m_y:
        return int(m_y.group(1)), 7

    return None


def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    sorted_ivs = sorted(intervals, key=lambda x: (x[0], x[1]))
    merged = [sorted_ivs[0]]
    for cur_start, cur_end in sorted_ivs[1:]:
        prev_start, prev_end = merged[-1]
        if cur_start <= prev_end + 1:
            merged[-1] = (prev_start, max(prev_end, cur_end))
        else:
            merged.append((cur_start, cur_end))
    return merged


def eval_experience_duration(
    profile: dict[str, Any],
    req: dict[str, Any],
    as_of: str = "2026-10-01",
) -> tuple[str, float, dict[str, Any], list[dict[str, Any]], list[str]]:
    """Evaluates EXPERIENCE_DURATION requirements (e.g. R1: min 3 years)."""
    params = req.get("params", {})
    accepted_rfs = [rf.lower() for rf in params.get("accepted_role_families", [])]
    desc_text = (req.get("description", "") + " " + req.get("source_text", "")).lower()

    if not accepted_rfs:
        concepts = [c.lower() for c in req.get("concepts", [])]
        if any("civil" in c for c in concepts) or any(
            term in desc_text for term in ["sipil", "civil", "konstruksi", "lapangan", "proyek sipil", "bangunan"]
        ):
            accepted_rfs = ["civil_engineering", "engineering"]
        elif any("hr" in c for c in concepts) or any(
            term in desc_text for term in ["hr", "human capital", "recruiter", "talent", "payroll"]
        ):
            accepted_rfs = ["hr"]
        elif any("business" in c or "consult" in c or "finance" in c or "financial" in c for c in concepts) or any(
            term in desc_text
            for term in [
                "business analyst",
                "analis bisnis",
                "konsultan",
                "consultant",
                "analis keuangan",
                "financial analyst",
                "keuangan",
                "investasi",
            ]
        ):
            accepted_rfs = ["business_analyst", "financial_analyst", "consultant", "data"]
        elif any("data" in c for c in concepts) or any(term in desc_text for term in ["data", "analyst", "analytics"]):
            accepted_rfs = ["data", "business_analyst"]
        elif any("qa" in c for c in concepts) or any(
            term in desc_text for term in ["qa", "tester", "quality assurance"]
        ):
            accepted_rfs = ["qa"]
        else:
            accepted_rfs = ["backend", "fullstack"]

    min_months = params.get("min_months")
    if min_months is None:
        m_dur = re.search(r"(\d+)\s*(?:-\s*(\d+))?\s*(?:tahun|year)", desc_text)
        if m_dur:
            min_months = int(m_dur.group(1)) * 12
        else:
            min_months = 36

    as_of_y, as_of_m = parse_ym("present", as_of)  # type: ignore[misc]
    as_of_total_m = as_of_y * 12 + as_of_m

    full_intervals: list[tuple[int, int]] = []
    intern_intervals: list[tuple[int, int]] = []
    flags = []
    evidence = []

    for exp in profile.get("experiences", []):
        title = exp.get("title", "")
        bullet_text = " ".join(b.get("text", "") for b in exp.get("bullets", []))
        rf = classify_role_family(title, bullet_text)
        if rf not in accepted_rfs:
            continue

        s_val = exp.get("start", {}).get("value")
        e_val = exp.get("end", {}).get("value")

        s_ym = parse_ym(s_val, as_of)
        e_ym = parse_ym(e_val, as_of)

        if not s_ym or not e_ym:
            continue

        s_tot = s_ym[0] * 12 + s_ym[1]
        e_tot = e_ym[0] * 12 + e_ym[1]

        if s_tot > as_of_total_m or e_tot > as_of_total_m or e_tot < s_tot:
            flags.append("DATE_ANOMALY")
            continue

        is_intern = exp.get("context") == "internship" or exp.get("employment_type") == "internship"
        if is_intern:
            intern_intervals.append((s_tot, e_tot))
        else:
            full_intervals.append((s_tot, e_tot))

        evidence.append(
            {
                "quote": f"{title} ({s_val}..{e_val})",
                "context": exp.get("context", "experience"),
                "verified": True,
            }
        )

    merged_full = merge_intervals(full_intervals)
    merged_intern = merge_intervals(intern_intervals)

    full_m = sum(end - start + 1 for start, end in merged_full)
    intern_m = sum(end - start + 1 for start, end in merged_intern)

    total_months = round(full_m + (intern_m * 0.5), 1)

    if total_months >= min_months:
        state = "STRONG"
    elif total_months > 0:
        state = "PARTIAL"
    else:
        state = "NOT_DEMONSTRATED"

    metrics = {"backend_months": total_months}
    confidence = 0.95
    return state, confidence, metrics, evidence, flags


def eval_skill(
    profile: dict[str, Any],
    req: dict[str, Any],
) -> tuple[str, float, dict[str, Any], list[dict[str, Any]], list[str]]:
    """Evaluates SKILL requirements respecting hierarchy of evidence context."""
    concepts = [c.lower() for c in req.get("concepts", [])]
    acceptable_alt = [a.lower() for a in req.get("params", {}).get("acceptable_alternatives", [])]
    all_target_concepts = set(concepts + acceptable_alt)

    target_keywords: list[str] = []
    for c in all_target_concepts:
        base = c.split(":")[-1]
        target_keywords.extend(CONCEPT_ALIASES.get(c, [base, base.replace("_", " "), base.replace("_", "-")]))

    if not target_keywords:
        desc = req.get("description", "") + " " + req.get("source_text", "")
        potential = re.findall(r"[A-Za-z0-9+#]+", desc)
        for term in potential:
            t_lower = term.lower()
            if len(t_lower) >= 3 and t_lower not in {
                "dan",
                "yang",
                "atau",
                "dengan",
                "untuk",
                "dalam",
                "serta",
                "ke",
                "di",
                "dari",
                "memahami",
                "mampu",
                "menguasai",
                "melakukan",
                "minimal",
                "sebagai",
                "merupakan",
                "nilai",
                "tambah",
                "proyek",
                "pekerjaan",
            }:
                target_keywords.extend(CONCEPT_ALIASES.get(f"skill:{t_lower}", [t_lower]))

    evidence = []

    # Context 1: Dated jobs (STRONG)
    for exp in profile.get("experiences", []):
        combined_text = f"{exp.get('title', '')} " + " ".join(b.get("text", "") for b in exp.get("bullets", []))
        for kw in target_keywords:
            if match_skill(combined_text, kw):
                evidence.append({"quote": combined_text[:120], "context": "experience", "verified": True})
                return "STRONG", 0.95, {}, evidence, []

    # Context 2: Projects, Organizations, or only in skills list (PARTIAL)
    for prj in profile.get("projects", []):
        prj_text = prj.get("text", "") or prj.get("title", "")
        for kw in target_keywords:
            if match_skill(prj_text, kw):
                evidence.append({"quote": prj_text[:120], "context": "project", "verified": True})
                return "PARTIAL", 0.85, {}, evidence, []

    for sk in profile.get("skills", []):
        for kw in target_keywords:
            if match_skill(sk, kw):
                evidence.append({"quote": f"Skills: {sk}", "context": "skills_list", "verified": True})
                return "PARTIAL", 0.85, {}, evidence, []

    # Fallback context: In summary or headline
    summary_text = f"{profile.get('summary', '')} {profile.get('headline', '')}"
    for kw in target_keywords:
        if match_skill(summary_text, kw):
            evidence.append({"quote": f"Summary: {summary_text[:120]}", "context": "summary", "verified": True})
            return "PARTIAL", 0.80, {}, evidence, []

    return "NOT_DEMONSTRATED", 0.95, {}, [], []


def eval_responsibility(
    profile: dict[str, Any],
    req: dict[str, Any],
) -> tuple[str, float, dict[str, Any], list[dict[str, Any]], list[str]]:
    """Evaluates RESPONSIBILITY (e.g. building REST API, microservices, or payroll admin)."""
    concepts = [c.lower() for c in req.get("concepts", [])]
    target_kws: list[str] = []
    for c in concepts:
        base = c.split(":")[-1]
        target_kws.extend(CONCEPT_ALIASES.get(c, [base, base.replace("_", " "), base.replace("_", "-")]))

    if not target_kws:
        desc = req.get("description", "") + " " + req.get("source_text", "")
        potential = re.findall(r"[A-Za-z0-9+#]+", desc)
        for term in potential:
            t_lower = term.lower()
            if len(t_lower) >= 3 and t_lower not in {
                "dan",
                "yang",
                "atau",
                "dengan",
                "untuk",
                "dalam",
                "serta",
                "ke",
                "di",
                "dari",
                "memahami",
                "mampu",
                "menguasai",
                "melakukan",
                "minimal",
                "sebagai",
                "merupakan",
                "nilai",
                "tambah",
                "proyek",
                "pekerjaan",
            }:
                target_kws.extend(CONCEPT_ALIASES.get(f"skill:{t_lower}", [t_lower]))

    # For API building
    build_verbs = [
        r"membangun",
        r"mendesain",
        r"mengembangkan",
        r"membuat",
        r"built",
        r"designed",
        r"developed",
        r"created",
    ]
    target_terms = [r"rest\s+api", r"microservices", r"layanan\s+mikro", r"api\b"]

    evidence = []
    has_building_job = False
    has_building_proj = False
    has_testing_only = False

    for exp in profile.get("experiences", []):
        is_intern = exp.get("context") == "internship" or exp.get("employment_type") == "internship"
        bullets = [b.get("text", "") for b in exp.get("bullets", [])]
        for b in bullets:
            b_lower = b.lower()

            is_test_automation = (
                "test" in b_lower
                or "pengujian" in b_lower
                or "qa" in b_lower
                or "pytest" in b_lower
                or "automation" in b_lower
            )

            # Concept matching for domain responsibilities (like payroll/bpjs in JD-02)
            if target_kws and not any("api" in kw for kw in target_kws):
                for kw in target_kws:
                    if re.search(rf"\b{re.escape(kw)}", b_lower):
                        evidence.append({"quote": b, "context": "experience", "verified": True})
                        return "STRONG", 0.95, {}, evidence, []

            is_build = any(re.search(v, b_lower) for v in build_verbs)
            is_target = any(re.search(t, b_lower) for t in target_terms)

            if is_build and is_target:
                if is_test_automation:
                    has_testing_only = True
                elif not is_intern and "internal sederhana" not in b_lower:
                    has_building_job = True
                    evidence.append({"quote": b, "context": "experience", "verified": True})
                else:
                    has_building_proj = True
                    evidence.append({"quote": b, "context": "internship", "verified": True})

    # Also check job titles for responsibility concepts
    if target_kws and not any("api" in kw for kw in target_kws):
        for exp in profile.get("experiences", []):
            t_lower = exp.get("title", "").lower()
            for kw in target_kws:
                if re.search(rf"\b{re.escape(kw)}", t_lower):
                    evidence.append({"quote": exp.get("title", ""), "context": "experience", "verified": True})
                    return "STRONG", 0.95, {}, evidence, []

    for prj in profile.get("projects", []):
        p_text = prj.get("text", "")
        if target_kws and not any("api" in kw for kw in target_kws):
            for kw in target_kws:
                if re.search(rf"\b{re.escape(kw)}", p_text.lower()):
                    evidence.append({"quote": p_text[:120], "context": "project", "verified": True})
                    return "PARTIAL", 0.85, {}, evidence, []
        if any(re.search(v, p_text.lower()) for v in build_verbs) and any(
            re.search(t, p_text.lower()) for t in target_terms
        ):
            has_building_proj = True
            evidence.append({"quote": p_text[:100], "context": "project", "verified": True})

    if target_kws and not any("api" in kw for kw in target_kws):
        for sk in profile.get("skills", []):
            for kw in target_kws:
                if re.search(rf"\b{re.escape(kw)}", sk.lower()):
                    evidence.append({"quote": f"Skills: {sk}", "context": "skills_list", "verified": True})
                    return "PARTIAL", 0.85, {}, evidence, []

        summary_comb = f"{profile.get('summary', '')} {profile.get('headline', '')}".lower()
        for kw in target_kws:
            if re.search(rf"\b{re.escape(kw)}", summary_comb):
                evidence.append({"quote": f"Summary: {summary_comb[:120]}", "context": "summary", "verified": True})
                return "PARTIAL", 0.80, {}, evidence, []

    if has_building_job:
        return "STRONG", 0.95, {}, evidence, []
    if has_building_proj or has_testing_only:
        return "PARTIAL", 0.85, {}, evidence, []

    return "NOT_DEMONSTRATED", 0.95, {}, [], []


def eval_education(
    profile: dict[str, Any],
    req: dict[str, Any],
) -> tuple[str, float, dict[str, Any], list[dict[str, Any]], list[str]]:
    """Evaluates EDUCATION requirements."""
    params = req.get("params", {})
    desc_text = (req.get("description", "") + " " + req.get("source_text", "")).lower()
    concepts = [c.lower() for c in req.get("concepts", [])]

    min_level = params.get("min_level")
    if not min_level:
        if "d3" in desc_text and "s1" in desc_text:
            min_level = "D3"
        elif "s1" in desc_text:
            min_level = "S1"
        elif "d3" in desc_text:
            min_level = "D3"
        elif "d4" in desc_text:
            min_level = "D4"
        elif "sma" in desc_text or "smk" in desc_text:
            min_level = "SMA"
        else:
            min_level = "S1"

    strong_fields = [f.lower() for f in params.get("strong_fields", [])]
    if not strong_fields:
        if any("civil" in c for c in concepts) or any(term in desc_text for term in ["sipil", "civil", "bangunan"]):
            strong_fields = [
                "teknik sipil",
                "civil engineering",
                "teknik bangunan",
                "sarjana terapan teknik sipil",
                "sipil",
            ]
        elif any(term in desc_text for term in ["informatika", "komputer", "software", "cs"]):
            strong_fields = [
                "teknik informatika",
                "ilmu komputer",
                "sistem informasi",
                "computer science",
                "informatika",
                "computer",
            ]
        elif any(term in desc_text for term in ["hr", "psikologi", "sdm"]):
            strong_fields = ["psikologi", "manajemen", "hukum"]
        elif any(
            term in desc_text
            for term in ["manajemen", "akuntansi", "ekonomi", "bisnis", "industri", "keuangan", "statistika"]
        ) or any(
            c
            in [
                "field:management",
                "field:accounting",
                "field:economics",
                "field:industrial_engineering",
                "field:business",
            ]
            for c in concepts
        ):
            strong_fields = [
                "manajemen",
                "management",
                "akuntansi",
                "accounting",
                "ekonomi",
                "economics",
                "teknik industri",
                "industrial engineering",
                "bisnis",
                "business",
                "administrasi bisnis",
                "business administration",
                "keuangan",
                "finance",
                "statistika",
                "statistics",
                "agribisnis",
                "agribusiness",
                "matematika",
                "mathematics",
                "hukum ekonomi syariah",
                "sharia accounting",
                "digital business",
                "s.e",
                "s.stat",
                "mba",
            ]
            partial_fields = [
                "hukum",
                "hubungan internasional",
                "international relations",
                "administrasi",
                "sains",
                "teknik",
                "sosial",
            ]
        else:
            strong_fields = [
                "teknik informatika",
                "ilmu komputer",
                "sistem informasi",
                "computer science",
                "informatika",
                "computer",
                "psikologi",
                "manajemen",
                "teknik sipil",
                "civil engineering",
            ]

    partial_fields = [
        f.lower()
        for f in params.get(
            "partial_fields",
            ["teknik komputer", "matematika", "rekayasa", "arsitektur", "teknik pengelasan", "welding"],
        )
    ]

    level_rank = {"SMA": 1, "SMK": 1, "D3": 2, "D4": 3, "S1": 3, "S2": 4, "S3": 5}
    min_r = level_rank.get(min_level, 3)

    evidence = []
    state = "NOT_DEMONSTRATED"

    edu_list = list(profile.get("education", []))
    for prj in profile.get("projects", []):
        p_txt = prj.get("text", "")
        if "s1 informatika" in p_txt.lower() or "universitas" in p_txt.lower():
            edu_list.append({"level": "S1", "degree_raw": p_txt, "institution": ""})

    # Also search in profile summary if education list is empty
    if not edu_list:
        summary_txt = profile.get("summary", "")
        for deg in ["s1", "d3", "d4", "sarjana", "diploma"]:
            if deg in summary_txt.lower():
                edu_list.append({"level": deg.upper(), "degree_raw": summary_txt[:150], "institution": ""})
                break

    for edu in edu_list:
        lvl = edu.get("level", "S1")
        lvl_r = level_rank.get(lvl, 3)
        comb = f"{edu.get('degree_raw', '')} {edu.get('major', '')} {edu.get('degree', '')} {edu.get('institution', '')} {edu.get('text', '')}".lower()

        is_strong_f = any(f in comb for f in strong_fields)
        is_partial_f = any(f in comb for f in partial_fields)

        if is_strong_f and lvl_r >= min_r:
            state = "STRONG"
            evidence.append({"quote": comb[:100], "context": "education", "verified": True})
            return state, 0.95, {}, evidence, []
        elif (is_strong_f and lvl_r < min_r) or is_partial_f:
            state = "PARTIAL"
            evidence.append({"quote": comb[:100], "context": "education", "verified": True})

    if state == "NOT_DEMONSTRATED":
        summary_comb = f"{profile.get('summary', '')} {profile.get('headline', '')}".lower()
        if any(f in summary_comb for f in strong_fields) and any(
            lvl.lower() in summary_comb for lvl in ["s1", "s2", "sarjana", "bachelor", "master", "magister"]
        ):
            evidence.append({"quote": summary_comb[:100], "context": "summary", "verified": True})
            return "STRONG", 0.90, {}, evidence, []
        elif any(f in summary_comb for f in partial_fields):
            evidence.append({"quote": summary_comb[:100], "context": "summary", "verified": True})
            return "PARTIAL", 0.80, {}, evidence, []

    return state, 0.95, {}, evidence, []


def eval_certification(
    profile: dict[str, Any],
    req: dict[str, Any],
) -> tuple[str, float, dict[str, Any], list[dict[str, Any]], list[str]]:
    """Evaluates CERTIFICATION requirements."""
    concepts = [c.lower() for c in req.get("concepts", [])]
    desc_text = (req.get("description", "") + " " + req.get("source_text", "")).lower()
    cert_certs = list(profile.get("certifications", []))
    # Also check candidate skills list which may contain certification names
    for sk in profile.get("skills", []):
        if any(
            term in sk.lower()
            for term in ["k3", "sertifikat", "certificate", "competence", "kompetensi", "ahli", "bnsp", "inspektur"]
        ):
            cert_certs.append(sk)

    evidence = []
    for c in cert_certs:
        c_lower = c.lower()
        if (
            "cert:cloud" in concepts or "cert:aws" in concepts or "cert:gcp" in concepts or "cloud" in desc_text
        ) and any(term in c_lower for term in ["aws certified", "google cloud", "azure", "cloud developer"]):
            evidence.append({"quote": c, "context": "certification", "verified": True})
            return "STRONG", 0.95, {}, evidence, []
        if ("cert:hr" in concepts or "hr" in desc_text or "bnsp" in desc_text) and any(
            term in c_lower for term in ["human capital", "bnsp", "chrp", "hr"]
        ):
            evidence.append({"quote": c, "context": "certification", "verified": True})
            return "STRONG", 0.95, {}, evidence, []
        if (
            "cert:ska" in concepts
            or "cert:skt" in concepts
            or "cert:k3" in concepts
            or any(term in desc_text for term in ["ska", "skt", "k3", "konstruksi", "inspektur", "keselamatan"])
        ) and any(
            term in c_lower
            for term in [
                "ska",
                "skt",
                "k3",
                "keselamatan",
                "hse",
                "inspektur",
                "ahli k3",
                "kompetensi",
                "bnsp",
                "bimtek",
            ]
        ):
            evidence.append({"quote": c, "context": "certification", "verified": True})
            return "STRONG", 0.95, {}, evidence, []

    return "NOT_DEMONSTRATED", 0.95, {}, [], []


def eval_achievement(
    profile: dict[str, Any],
    req: dict[str, Any],
) -> tuple[str, float, dict[str, Any], list[dict[str, Any]], list[str]]:
    """Evaluates ACHIEVEMENT requirements (quantified metrics in relevant domain)."""
    concepts = [c.lower() for c in req.get("concepts", [])]
    num_pat = re.compile(
        r"\b\d+(?:[.,]\d+)?\s*(?:%|ms|detik|menit|jam|hari|juta|k|m|ribu|x\s*lipat|posisi|karyawan|orang|akun|\+)",
        re.IGNORECASE,
    )

    is_hr_achievement = "achievement:quantified_hr" in concepts
    evidence = []
    has_tech_num = False
    has_hr_num = False
    has_unrelated_num = False

    for exp in profile.get("experiences", []):
        bullet_text = " ".join(b.get("text", "") for b in exp.get("bullets", []))
        rf = classify_role_family(exp.get("title", ""), bullet_text)
        for b in exp.get("bullets", []):
            txt = b.get("text", "")
            if num_pat.search(txt):
                if rf == "hr":
                    has_hr_num = True
                    evidence.append({"quote": txt, "context": "experience", "verified": True})
                elif rf in ("backend", "fullstack", "devops"):
                    has_tech_num = True
                    evidence.append({"quote": txt, "context": "experience", "verified": True})
                else:
                    has_unrelated_num = True

    for prj in profile.get("projects", []):
        txt = prj.get("text", "")
        if num_pat.search(txt):
            has_unrelated_num = True
            evidence.append({"quote": txt[:100], "context": "project", "verified": True})

    if is_hr_achievement and has_hr_num:
        return "STRONG", 0.95, {}, evidence, []
    if not is_hr_achievement and has_tech_num:
        return "STRONG", 0.95, {}, evidence, []
    if has_unrelated_num:
        has_tech_rf = any(
            classify_role_family(e.get("title", "")) in ("backend", "fullstack", "data", "qa", "devops")
            for e in profile.get("experiences", [])
        )
        if has_tech_rf and not is_hr_achievement:
            return "PARTIAL", 0.85, {}, [], []
    return "NOT_DEMONSTRATED", 0.95, {}, [], []


def eval_leadership(
    profile: dict[str, Any],
    req: dict[str, Any],
) -> tuple[str, float, dict[str, Any], list[dict[str, Any]], list[str]]:
    """Evaluates LEADERSHIP requirements (memimpin tim teknis != tim sales)."""
    lead_verbs = [
        r"memimpin\s+.*tim",
        r"led\s+.*team",
        r"lead\s+.*team",
        r"mentoring",
        r"membimbing",
        r"\bketua\b",
        r"\bhead\b",
        r"\bkoordinator\b",
    ]
    lead_titles = [r"\blead\b", r"\bhead\b", r"\bmanager\b", r"\bsupervisor\b"]

    evidence = []
    has_tech_lead = False
    has_qa_or_org_lead = False
    has_sales_lead = False

    for exp in profile.get("experiences", []):
        title = exp.get("title", "")
        rf = classify_role_family(title)
        bullets_text = " ".join(b.get("text", "") for b in exp.get("bullets", []))

        is_lead = any(re.search(v, bullets_text, re.IGNORECASE) for v in lead_verbs) or any(
            re.search(t, title, re.IGNORECASE) for t in lead_titles
        )

        if is_lead:
            if rf in ("backend", "fullstack", "devops"):
                has_tech_lead = True
                evidence.append({"quote": f"{title}: {bullets_text[:100]}", "context": "experience", "verified": True})
            elif rf in ("qa", "data"):
                has_qa_or_org_lead = True
                evidence.append({"quote": f"{title}: {bullets_text[:100]}", "context": "experience", "verified": True})
            elif "sales" in title.lower() or "marketing" in title.lower():
                has_sales_lead = True

    for org in profile.get("organizations", []):
        txt = org.get("text", "") or org.get("title", "")
        if any(re.search(v, txt, re.IGNORECASE) for v in lead_verbs):
            has_qa_or_org_lead = True
            evidence.append({"quote": txt[:100], "context": "organization", "verified": True})

    for prj in profile.get("projects", []):
        txt = prj.get("text", "")
        if any(re.search(v, txt, re.IGNORECASE) for v in lead_verbs):
            has_qa_or_org_lead = True
            evidence.append({"quote": txt[:100], "context": "project", "verified": True})

    if has_tech_lead:
        return "STRONG", 0.95, {}, evidence, []
    if has_qa_or_org_lead:
        return "PARTIAL", 0.85, {}, evidence, []
    if has_sales_lead:
        return "NOT_DEMONSTRATED", 0.95, {}, [], []

    return "NOT_DEMONSTRATED", 0.95, {}, [], []
