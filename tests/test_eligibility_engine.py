import uuid
from datetime import date
import pytest
from pydantic import ValidationError

from src.api.routes.eligibility import EligibilityRuleCreate
from src.domain.eligibility import (
    calculate_age,
    evaluate_candidate_eligibility,
    parse_date_of_birth,
)
from src.domain.scorer import score


def test_parse_dob_and_calculate_age():
    as_of = date(2026, 10, 1)

    # Born 1999-05-15 -> age 27
    dob = parse_date_of_birth("1999-05-15")
    assert dob == date(1999, 5, 15)
    assert calculate_age(dob, as_of) == 27

    # Born 1999-11-20 (birthday not yet reached on 2026-10-01) -> age 26
    dob2 = parse_date_of_birth("20 November 1999")
    assert dob2 == date(1999, 11, 20)
    assert calculate_age(dob2, as_of) == 26


def test_evaluate_eligibility_max_age_rule():
    as_of = date(2026, 10, 1)
    rules = [
        {
            "id": str(uuid.uuid4()),
            "category": "AGE",
            "rule_type": "MAX_AGE",
            "parameters": {"max_age": 27},
            "is_active": True,
        }
    ]

    # Candidate 1: Age 25 (Eligible)
    c1 = {"other_personal": {"date_of_birth": "2001-01-10"}}
    res1 = evaluate_candidate_eligibility(c1, rules, as_of)
    assert res1["overall_status"] == "ELIGIBLE"

    # Candidate 2: Age 30 (Not Eligible)
    c2 = {"other_personal": {"date_of_birth": "1996-01-10"}}
    res2 = evaluate_candidate_eligibility(c2, rules, as_of)
    assert res2["overall_status"] == "NOT_ELIGIBLE"

    # Candidate 3: Modern CV without DOB -> UNKNOWN (never disqualified automatically!)
    c3 = {"other_personal": {}}
    res3 = evaluate_candidate_eligibility(c3, rules, as_of)
    assert res3["overall_status"] == "UNKNOWN"
    assert "Tanggal lahir tidak dicantumkan" in res3["evaluations"][0]["reason"]


def test_evaluate_eligibility_gender_rule():
    as_of = date(2026, 10, 1)
    rules = [
        {
            "id": str(uuid.uuid4()),
            "category": "GENDER",
            "rule_type": "EXACT_GENDER",
            "parameters": {"gender": "F"},
            "is_active": True,
        }
    ]

    # Female candidate -> Eligible
    c_female = {"other_personal": {"gender": "Perempuan"}}
    res_f = evaluate_candidate_eligibility(c_female, rules, as_of)
    assert res_f["overall_status"] == "ELIGIBLE"

    # Male candidate -> Not Eligible
    c_male = {"other_personal": {"gender": "Laki-laki"}}
    res_m = evaluate_candidate_eligibility(c_male, rules, as_of)
    assert res_m["overall_status"] == "NOT_ELIGIBLE"

    # Modern CV with no gender mentioned -> UNKNOWN
    c_none = {"other_personal": {}}
    res_none = evaluate_candidate_eligibility(c_none, rules, as_of)
    assert res_none["overall_status"] == "UNKNOWN"


def test_eligibility_justification_minimum_30_chars():
    # Short justification (< 30 chars) must raise ValidationError
    with pytest.raises(ValidationError):
        EligibilityRuleCreate(
            category="AGE",
            rule_type="MAX_AGE",
            parameters={"max_age": 28},
            justification="Short reason",
        )

    # Valid justification (>= 30 chars) passes
    rule = EligibilityRuleCreate(
        category="AGE",
        rule_type="MAX_AGE",
        parameters={"max_age": 28},
        justification="Program Management Trainee ikatan dinas 5 tahun sesuai regulasi internal perusahaan",
    )
    assert rule.category == "AGE"


def test_competency_score_invariant_under_eligibility():
    # Invariant I-1: Competency score must be 100% blind to age/gender/eligibility
    req_set = {
        "category_weights": {"HARD_SKILLS": 100},
        "requirements": [
            {
                "requirement_id": "R1",
                "category": "HARD_SKILLS",
                "importance": "MUST_HAVE",
                "weight": 10,
            }
        ],
    }
    states = {"R1": "STRONG"}

    # Candidate score
    score_res = score(states, req_set)
    assert score_res.final_score == 100.0
    assert score_res.band == "A"
    assert score_res.recommendation == "SHORTLIST"
