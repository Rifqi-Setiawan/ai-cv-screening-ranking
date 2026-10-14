from unittest.mock import AsyncMock, patch

import pytest

from src.domain.jd_compiler import compile_jd_rule_based, compile_job_requirements


def test_rule_based_importance_keywords():
    jd_nice = "- Menguasai Docker merupakan nilai tambah"
    reqs_nice = compile_jd_rule_based(jd_nice)
    assert len(reqs_nice) >= 1
    assert reqs_nice[0]["importance"] == "NICE_TO_HAVE"

    jd_must = "- Wajib memiliki pengalaman 3 tahun backend"
    reqs_must = compile_jd_rule_based(jd_must)
    assert len(reqs_must) >= 1
    assert reqs_must[0]["importance"] == "MUST_HAVE"


@pytest.mark.asyncio
async def test_llm_invalid_importance_coerced_or_fallback():
    # LLM returns invalid importance 'SUPER_IMPORTANT'
    mock_llm_res = {
        "requirements": [
            {
                "requirement_id": "R1",
                "description": "Menguasai Kubernetes merupakan nilai tambah",
                "importance": "SUPER_IMPORTANT",
                "weight": -5,
            }
        ]
    }

    with patch("src.domain.jd_compiler.gateway.call_chat", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = mock_llm_res
        res = await compile_job_requirements("Sample JD text")
        reqs = res["requirements"]
        assert len(reqs) >= 1
        # The invalid importance must NOT leak through as SUPER_IMPORTANT
        assert reqs[0]["importance"] in ("MUST_HAVE", "STRONG_PREFERENCE", "NICE_TO_HAVE")
        assert reqs[0]["importance"] == "NICE_TO_HAVE"
        # Negative weight must be coerced to positive default
        assert reqs[0]["weight"] > 0
