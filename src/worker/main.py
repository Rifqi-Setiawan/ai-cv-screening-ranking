"""Background task worker for asynchronous CV ingestion, embedding, and scoring."""
from __future__ import annotations

import asyncio
import signal

from src.infrastructure.database import close_db_pool, get_connection
from src.infrastructure.logging import logger

_running = True


def handle_stop(sig, frame):
    global _running
    logger.info(f"Received stop signal {sig}, terminating worker loop gracefully...")
    _running = False


async def worker_loop():
    logger.info("CV Screening worker initialized and polling jobs_queue...")
    while _running:
        try:
            async with get_connection() as conn, conn.cursor() as cur:
                # Poll for queued tasks using SKIP LOCKED
                await cur.execute(
                    """
                        SELECT id, tenant_id, queue_name, payload, attempts
                        FROM jobs_queue
                        WHERE status = 'QUEUED' AND run_after <= now()
                        ORDER BY priority ASC, created_at ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                        """
                )
                task = await cur.fetchone()
                if task:
                    logger.info(f"Picked up job {task['id']} from queue {task['queue_name']}")
                    # Mark RUNNING
                    await cur.execute(
                        "UPDATE jobs_queue SET status = 'RUNNING', started_at = now() WHERE id = %s",
                        (task["id"],),
                    )
                    await conn.commit()
                    # Simulated processing placeholder for M1
                    await asyncio.sleep(0.1)
                    # Mark DONE
                    await cur.execute(
                        "UPDATE jobs_queue SET status = 'DONE', finished_at = now() WHERE id = %s",
                        (task["id"],),
                    )
                    await conn.commit()
                    logger.info(f"Finished job {task['id']}")
                else:
                    await asyncio.sleep(1.0)
        except Exception as e:
            logger.error(f"Worker iteration encountered error: {e}")
            await asyncio.sleep(2.0)

    logger.info("Worker loop exiting, cleaning up resources...")
    await close_db_pool()


def main():
    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
