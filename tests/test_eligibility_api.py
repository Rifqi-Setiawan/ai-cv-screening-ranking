import uuid

import httpx
import pytest
import pytest_asyncio

from src.domain.auth import create_access_token
from src.domain.models import UserRole
from src.infrastructure.database import get_connection

TEST_TENANT = uuid.uuid4()
ADMIN_USER = uuid.uuid4()
RECRUITER_USER = uuid.uuid4()


@pytest_asyncio.fixture
async def setup_users():
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO users (id, tenant_id, email, password_hash, role)
            VALUES (%s, %s, %s, 'hash', 'admin'),
                   (%s, %s, %s, 'hash', 'recruiter')
            ON CONFLICT (email) DO NOTHING
            """,
            (
                ADMIN_USER,
                TEST_TENANT,
                f"admin_{ADMIN_USER}@elig.com",
                RECRUITER_USER,
                TEST_TENANT,
                f"rec_{RECRUITER_USER}@elig.com",
            ),
        )
        await conn.commit()


@pytest.mark.asyncio
async def test_eligibility_rule_lifecycle_and_audit(client: httpx.AsyncClient, setup_users):
    admin_token = create_access_token(
        {
            "sub": str(ADMIN_USER),
            "tenant_id": str(TEST_TENANT),
            "email": f"admin_{ADMIN_USER}@elig.com",
            "role": UserRole.ADMIN.value,
        }
    )
    recruiter_token = create_access_token(
        {
            "sub": str(RECRUITER_USER),
            "tenant_id": str(TEST_TENANT),
            "email": f"rec_{RECRUITER_USER}@elig.com",
            "role": UserRole.RECRUITER.value,
        }
    )

    admin_h = {"Authorization": f"Bearer {admin_token}"}
    recruiter_h = {"Authorization": f"Bearer {recruiter_token}"}

    job_id = uuid.uuid4()
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jobs (id, tenant_id, title, jd_text) VALUES (%s, %s, 'MT Job', 'JD')",
            (job_id, TEST_TENANT),
        )
        await conn.commit()

    # 1. Recruiter creates eligibility rule (justification < 30 chars -> 422)
    bad_payload = {
        "category": "AGE",
        "rule_type": "MAX_AGE",
        "parameters": {"max_age": 27},
        "justification": "Too short",
    }
    r_bad = await client.post(f"/api/v1/jobs/{job_id}/eligibility-rules", json=bad_payload, headers=recruiter_h)
    assert r_bad.status_code == 422

    # 2. Recruiter creates rule with valid justification (>= 30 chars)
    good_payload = {
        "category": "AGE",
        "rule_type": "MAX_AGE",
        "parameters": {"max_age": 27},
        "justification": "Program Management Trainee operasional lapangan 5 tahun ikatan dinas",
    }
    r_create = await client.post(f"/api/v1/jobs/{job_id}/eligibility-rules", json=good_payload, headers=recruiter_h)
    assert r_create.status_code == 201
    rule_data = r_create.json()
    rule_id = rule_data["id"]
    assert rule_data["is_active"] is False

    # 3. Recruiter tries to approve rule -> 403 Forbidden (Only ADMIN can approve!)
    r_rec_app = await client.post(f"/api/v1/jobs/{job_id}/eligibility-rules/{rule_id}/approve", headers=recruiter_h)
    assert r_rec_app.status_code == 403

    # 4. Admin approves rule -> 200 OK
    r_adm_app = await client.post(f"/api/v1/jobs/{job_id}/eligibility-rules/{rule_id}/approve", headers=admin_h)
    assert r_adm_app.status_code == 200
    assert r_adm_app.json()["is_active"] is True

    # 5. Verify audit_logs table has immutable entry for this approval
    async with get_connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT action, target_type, target_id, actor_id
            FROM audit_logs
            WHERE target_id = %s AND action = 'APPROVE_ELIGIBILITY_RULE'
            """,
            (str(rule_id),),
        )
        audit_row = await cur.fetchone()
        assert audit_row is not None
        assert audit_row["actor_id"] == ADMIN_USER
