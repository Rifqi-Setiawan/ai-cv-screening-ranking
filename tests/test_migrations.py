import os
import subprocess
import psycopg
import pytest
from src.infrastructure.config import settings


def test_reset_dev_db_script_refuses_without_confirm():
    res = subprocess.run(
        ["bash", "scripts/reset_dev_db.sh"],
        capture_output=True,
        text=True,
        env={**os.environ, "CONFIRM_RESET": "no"},
    )
    assert res.returncode == 1
    assert "Ditolak: script ini MENGHAPUS database" in res.stdout or "Ditolak" in res.stderr


def test_alembic_upgrade_on_isolated_db():
    # 1. Create a temporary isolated database
    test_db_name = "cv_screening_alembic_test"
    admin_conn = psycopg.connect("postgresql://hermes@/postgres?host=/tmp&port=5432", autocommit=True)
    with admin_conn.cursor() as cur:
        cur.execute(f"DROP DATABASE IF EXISTS {test_db_name}")
        cur.execute(f"CREATE DATABASE {test_db_name} OWNER cv_screening_user")
    admin_conn.close()

    # Superuser provisions required extensions on the new database
    admin_test_conn = psycopg.connect(f"postgresql://hermes@/{test_db_name}?host=/tmp&port=5432", autocommit=True)
    with admin_test_conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    admin_test_conn.close()

    test_db_url = f"postgresql://cv_screening_user:4ql2MmOgXcZ9p9LPeNsP8JkMe7stZFnf6sAbmQxG1_c@127.0.0.1:5432/{test_db_name}"

    try:
        # 2. Run alembic upgrade head on this clean DB
        env = {**os.environ, "DATABASE_URL": test_db_url, "APP_ENV": "test"}
        res = subprocess.run(
            [".venv/bin/alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert res.returncode == 0, f"Alembic upgrade failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"

        # 3. Verify tables exist
        test_conn = psycopg.connect(test_db_url)
        with test_conn.cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            tables = {r[0] for r in cur.fetchall()}
            assert "jobs" in tables
            assert "candidates" in tables
            assert "requirement_sets" in tables
            assert "requirements" in tables
            assert "alembic_version" in tables
        test_conn.close()
    finally:
        # Cleanup isolated test DB
        admin_conn = psycopg.connect("postgresql://hermes@/postgres?host=/tmp&port=5432", autocommit=True)
        with admin_conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {test_db_name}")
        admin_conn.close()
