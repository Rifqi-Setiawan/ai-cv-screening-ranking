#!/usr/bin/env bash
set -euo pipefail

export LD_LIBRARY_PATH="/srv/apps/hermes/opt/postgresql/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}"

echo "=== 1. Drop & Recreate Database cv_screening ==="
psql -h /tmp -p 5432 -U hermes -d postgres -c "DROP DATABASE IF EXISTS cv_screening;"
psql -h /tmp -p 5432 -U hermes -d postgres -c "CREATE DATABASE cv_screening OWNER cv_screening_user;"

echo "=== 2. Provision Extensions (Superuser) ==="
psql -h /tmp -p 5432 -U hermes -d cv_screening -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pgcrypto;"

echo "=== 3. Apply Schema (cv_screening_user) ==="
PGPASSWORD='59Vf0GijbEHFxZyfUHsjoJs9' psql -h 127.0.0.1 -p 5432 -U cv_screening_user -d cv_screening -f docs/spec/schemas/db_schema.sql

echo "=== 4. Seed Initial Users ==="
PYTHONPATH=. .venv/bin/python scripts/seed_users.py

echo "=== Migration & Seeding Successful ==="
