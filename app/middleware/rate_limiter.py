"""
Rate Limiter Middleware
Simple in-memory rate limiting to protect the connector from abuse.
Uses a sliding window per IP address.
"""

import time
from collections import defaultdict, deque
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Max requests per window per IP
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_WINDOW = 60  # seconds

# Per-IP request timestamps
_request_log: dict[str, deque] = defaultdict(deque)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Sliding window rate limiter middleware.
    Allows up to RATE_LIMIT_REQUESTS per IP per RATE_LIMIT_WINDOW seconds.
    """

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW

        # Clean up old requests outside window
        timestamps = _request_log[client_ip]
        while timestamps and timestamps[0] < window_start:
            timestamps.popleft()

        if len(timestamps) >= RATE_LIMIT_REQUESTS:
            retry_after = int(RATE_LIMIT_WINDOW - (now - timestamps[0]))
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate Limit Exceeded",
                    "message": f"Too many requests. Max {RATE_LIMIT_REQUESTS} per {RATE_LIMIT_WINDOW}s.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)
        response = await call_next(request)

        # Inject rate limit headers
        remaining = RATE_LIMIT_REQUESTS - len(timestamps)
        response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_REQUESTS)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Window"] = f"{RATE_LIMIT_WINDOW}s"

        return response
