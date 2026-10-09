"""In-memory sliding window rate limiter for API protection (M6)."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

# IP -> list of timestamps
_request_history: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(max_requests: int = 60, window_seconds: int = 60):
    async def dependency(request: Request):
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        key = f"{client_ip}:{request.url.path}"

        # Clean old timestamps
        history = _request_history[key]
        valid_from = now - window_seconds
        _request_history[key] = [t for t in history if t > valid_from]

        if len(_request_history[key]) >= max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: maximum {max_requests} requests per {window_seconds}s.",
            )

        _request_history[key].append(now)

    return dependency
