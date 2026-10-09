"""LLM gateway client interfacing with local 9Router proxy with privacy safeguards."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import uuid
from typing import Any

import httpx

from src.infrastructure.config import settings
from src.infrastructure.database import get_connection
from src.infrastructure.logging import logger

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"(?:\+62|62|08)[0-9\s-]{8,15}")


class PrivacyViolationError(ValueError):
    pass


def resolve_router_key() -> str:
    if settings.LLM_GATEWAY_KEY:
        return settings.LLM_GATEWAY_KEY
    db_path = "/srv/apps/9router/data/db/data.sqlite"
    if os.path.exists(db_path):
        try:
            import sqlite3

            with sqlite3.connect(db_path, timeout=2.0) as conn:
                cur = conn.cursor()
                cur.execute("SELECT key FROM apiKeys WHERE isActive = 1 LIMIT 1")
                row = cur.fetchone()
                if row and row[0]:
                    return str(row[0])
        except Exception:
            pass
    return "dev-key"


class ModelGateway:
    def __init__(self):
        self.base_url = settings.LLM_GATEWAY_URL
        self.api_key = resolve_router_key()
        self.model = settings.LLM_MODEL_JD_COMPILER
        self.data_policy = settings.LLM_DATA_POLICY

    def verify_redacted_text(self, text: str) -> None:
        """Pre-flight safety inspection: blocks requests if raw emails or phones are present."""
        if EMAIL_REGEX.search(text):
            raise PrivacyViolationError("Blocked LLM request: raw unredacted email detected in payload.")
        if PHONE_REGEX.search(text):
            raise PrivacyViolationError("Blocked LLM request: raw unredacted phone number detected in payload.")

    async def call_chat(
        self,
        messages: list[dict[str, str]],
        task: str = "jd_compilation",
        tenant_id: uuid.UUID | None = None,
        json_mode: bool = True,
    ) -> dict[str, Any] | None:
        if self.data_policy == "paid_or_local_only":
            logger.warning("LLM call skipped: policy 'paid_or_local_only' restricts dev router usage.")
            return None

        # Concatenate payload for privacy check and hashing
        combined_prompt = "\n".join(m.get("content", "") for m in messages)
        self.verify_redacted_text(combined_prompt)

        input_hash = hashlib.sha256(combined_prompt.encode()).hexdigest()
        t0 = time.time()

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": settings.LLM_TEMPERATURE,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        call_id = uuid.uuid4()
        status_str = "FAILED"
        tokens_in = tokens_out = 0
        output_hash = ""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                latency_ms = int((time.time() - t0) * 1000)

                if res.status_code == 200:
                    resp_data = res.json()
                    status_str = "SUCCESS"
                    usage = resp_data.get("usage", {})
                    tokens_in = usage.get("prompt_tokens", 0)
                    tokens_out = usage.get("completion_tokens", 0)
                    content_str = resp_data["choices"][0]["message"]["content"]
                    output_hash = hashlib.sha256(content_str.encode()).hexdigest()

                    # Record model call without storing CV text
                    await self._record_call(
                        call_id=call_id,
                        tenant_id=tenant_id,
                        task=task,
                        input_hash=input_hash,
                        output_hash=output_hash,
                        tokens_in=tokens_in,
                        tokens_out=tokens_out,
                        latency_ms=latency_ms,
                        status=status_str,
                    )

                    try:
                        return json.loads(content_str)
                    except json.JSONDecodeError:
                        return {"raw_content": content_str}
                else:
                    logger.warning(f"9Router returned HTTP {res.status_code}: {res.text[:200]}")
                    return None
        except Exception as e:
            logger.warning(f"9Router connection failed ({e}). Falling back to deterministic rules.")
            return None

    async def _record_call(
        self,
        call_id: uuid.UUID,
        tenant_id: uuid.UUID | None,
        task: str,
        input_hash: str,
        output_hash: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
        status: str,
    ) -> None:
        try:
            async with get_connection() as conn, conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO model_calls (
                        id, tenant_id, task, provider, model, prompt_version, input_hash, output_hash,
                        tokens_in, tokens_out, latency_ms, status
                    )
                    VALUES (%s, %s, %s, '9router', %s, 'v1.0', %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        call_id,
                        tenant_id,
                        task,
                        self.model,
                        input_hash,
                        output_hash,
                        tokens_in,
                        tokens_out,
                        latency_ms,
                        status,
                    ),
                )
                await conn.commit()
        except Exception as e:
            logger.error(f"Failed to record model call: {e}")


gateway = ModelGateway()


def call_dev_llm(prompt: str, system_prompt: str = "") -> dict[str, Any] | None:
    """Synchronous / script-friendly caller for dev LLM via 9Router."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                res = pool.submit(asyncio.run, gateway.call_chat(messages, task="verification")).result()
        else:
            res = asyncio.run(gateway.call_chat(messages, task="verification"))

        if res:
            return {"status": "SUCCESS", "response": json.dumps(res) if isinstance(res, dict) else str(res)}
        return {"status": "FAILED"}
    except Exception as e:
        logger.warning(f"call_dev_llm failed: {e}")
        return {"status": "FAILED"}
