"""Database connection pool and async session manager using psycopg 3."""
from __future__ import annotations

import contextlib
from collections.abc import AsyncGenerator
from typing import Any

import psycopg
from pgvector.psycopg import register_vector_async
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from src.infrastructure.config import settings
from src.infrastructure.logging import logger

_pool: AsyncConnectionPool | None = None


async def get_db_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        logger.info("Initializing async database connection pool...")

        async def configure(conn: psycopg.AsyncConnection) -> None:
            await register_vector_async(conn)

        _pool = AsyncConnectionPool(
            conninfo=settings.DATABASE_URL,
            min_size=settings.DB_POOL_MIN,
            max_size=settings.DB_POOL_MAX,
            configure=configure,
            open=False,
        )
        await _pool.open()
        logger.info("Async database connection pool opened successfully.")
    return _pool


async def close_db_pool() -> None:
    global _pool
    if _pool is not None:
        logger.info("Closing database connection pool...")
        await _pool.close()
        _pool = None
        logger.info("Database connection pool closed.")


@contextlib.asynccontextmanager
async def get_connection() -> AsyncGenerator[Any, None]:
    pool = await get_db_pool()
    async with pool.connection() as conn:
        conn.row_factory = dict_row  # type: ignore[assignment]
        yield conn
