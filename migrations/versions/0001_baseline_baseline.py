"""baseline

Revision ID: 0001_baseline
Revises: 
Create Date: 2026-10-14 11:31:06.405332

"""
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_baseline'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    schema_path = Path(__file__).resolve().parent.parent.parent / "docs" / "spec" / "schemas" / "db_schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    
    # Strip CREATE EXTENSION statements since extensions are provisioned by superuser
    filtered_lines = [
        line for line in sql.splitlines()
        if not line.strip().upper().startswith("CREATE EXTENSION")
    ]
    filtered_sql = "\n".join(filtered_lines)

    conn = op.get_bind()
    conn.exec_driver_sql(filtered_sql)


def downgrade() -> None:
    tables = [
        "model_calls", "audit_logs", "reviews", "evidence", "requirement_scores",
        "candidate_scores", "skill_mentions", "profile_chunks", "candidate_profiles",
        "candidate_identities", "jobs_queue", "documents", "candidates",
        "requirements", "requirement_sets", "jobs", "users"
    ]
    conn = op.get_bind()
    for table in tables:
        conn.exec_driver_sql(f"DROP TABLE IF EXISTS {table} CASCADE;")
