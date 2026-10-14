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
                    UPDATE jobs_queue
                    SET status = 'RUNNING', locked_at = now(), attempts = attempts + 1
                    WHERE id = (
                        SELECT id FROM jobs_queue
                        WHERE (status = 'PENDING' AND run_after <= now())
                           OR (status = 'RUNNING' AND locked_at < now() - interval '10 minutes' AND attempts < max_attempts)
                        ORDER BY id ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    RETURNING id, type, payload, attempts, max_attempts
                    """
                )
                task = await cur.fetchone()
                if task:
                    await conn.commit()
                    task_id = task["id"]
                    q_type = task["type"]
                    payload = task["payload"]
                    attempts = task["attempts"]
                    max_attempts = task["max_attempts"]
                    logger.info(f"Claimed job {task_id} of type {q_type} (attempt {attempts}/{max_attempts})")

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
                        logger.error(f"Job {task_id} failed with error: {err}", exc_info=True)
                        if attempts < max_attempts:
                            await cur.execute(
                                """
                                UPDATE jobs_queue
                                SET status = 'PENDING',
                                    error = %s,
                                    run_after = now() + (%s * interval '1 minute')
                                WHERE id = %s
                                """,
                                (str(err)[:500], attempts, task_id),
                            )
                        else:
                            await cur.execute(
                                """
                                UPDATE jobs_queue
                                SET status = 'FAILED',
                                    error = %s
                                WHERE id = %s
                                """,
                                (str(err)[:500], task_id),
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
