"""Background task worker for asynchronous CV ingestion, embedding, and scoring."""

from __future__ import annotations

import asyncio
import signal
from uuid import UUID

from src.infrastructure.database import close_db_pool, get_connection
from src.infrastructure.logging import logger
from src.worker.processor import process_document

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
                await cur.execute(
                    """
                    SELECT id, type, payload, attempts
                    FROM jobs_queue
                    WHERE status = 'PENDING' AND run_after <= now()
                    ORDER BY id ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """
                )
                task = await cur.fetchone()
                if task:
                    task_id = task["id"]
                    q_type = task["type"]
                    payload = task["payload"]
                    logger.info(f"Picked up job {task_id} of type {q_type}")

                    await cur.execute(
                        "UPDATE jobs_queue SET status = 'RUNNING', locked_at = now() WHERE id = %s",
                        (task_id,),
                    )
                    await conn.commit()

                    try:
                        if q_type == "ingest_cv":
                            doc_id = UUID(payload["document_id"])
                            await process_document(doc_id)

                        await cur.execute(
                            "UPDATE jobs_queue SET status = 'DONE' WHERE id = %s",
                            (task_id,),
                        )
                        await conn.commit()
                        logger.info(f"Job {task_id} completed successfully.")
                    except Exception as err:
                        logger.error(f"Job {task_id} failed with error: {err}")
                        await cur.execute(
                            """
                            UPDATE jobs_queue
                            SET status = 'FAILED', error = %s, attempts = attempts + 1
                            WHERE id = %s
                            """,
                            (str(err), task_id),
                        )
                        await conn.commit()
                else:
                    await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"Worker polling loop error: {e}")
            await asyncio.sleep(1.0)

    logger.info("Worker loop exiting, cleaning up resources...")
    await close_db_pool()


def main():
    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
