#!/usr/bin/env python3
"""Database seeder to initialize default demo users for the 3 roles."""
from __future__ import annotations

import asyncio
import uuid
from src.domain.auth import hash_password
from src.domain.models import UserRole
from src.infrastructure.database import close_db_pool, get_connection
from src.infrastructure.logging import logger

DEMO_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

INITIAL_USERS = [
    {
        "email": "admin@rifqisetiawan.my.id",
        "password": "AdminSecurePassword2026!",
        "role": UserRole.ADMIN,
    },
    {
        "email": "recruiter@rifqisetiawan.my.id",
        "password": "RecruiterPassword2026!",
        "role": UserRole.RECRUITER,
    },
    {
        "email": "manager@rifqisetiawan.my.id",
        "password": "ManagerPassword2026!",
        "role": UserRole.HIRING_MANAGER,
    },
]


async def seed():
    logger.info("Seeding initial users into cv_screening database...")
    async with get_connection() as conn:
        async with conn.cursor() as cur:
            for u in INITIAL_USERS:
                pwd_hash = hash_password(u["password"])
                await cur.execute(
                    """
                    INSERT INTO users (tenant_id, email, password_hash, role, is_active)
                    VALUES (%s, %s, %s, %s, true)
                    ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash, role = EXCLUDED.role
                    RETURNING id, email, role
                    """,
                    (DEMO_TENANT_ID, u["email"], pwd_hash, u["role"].value),
                )
                row = await cur.fetchone()
                logger.info(f"Seeded user: {row['email']} with role {row['role']} (ID: {row['id']})")
            await conn.commit()
    await close_db_pool()
    logger.info("Database seeding completed.")


if __name__ == "__main__":
    asyncio.run(seed())
