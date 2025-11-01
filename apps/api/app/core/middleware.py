"""FastAPI middleware for request processing, logging, and security."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Callable

import redis.asyncio as aioredis
from fastapi import Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis connection pool for rate limiting (lazy initialization)
_redis_pool: aioredis.Redis | None = None


async def get_redis_pool() -> aioredis.Redis | None:
    """Get Redis connection pool for rate limiting."""
    global _redis_pool
    if _redis_pool is None and settings.enable_rate_limiting:
        try:
            from app.core.redis_instrumentation import InstrumentedRedis
            
            redis_client = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Wrap with instrumentation
            _redis_pool = InstrumentedRedis(redis_client)  # type: ignore[assignment]
        except Exception as e:
            logger.warning(f"Failed to connect to Redis for rate limiting: {e}")
            return None
    return _redis_pool

# Sensitive fields to redact from logs
SENSITIVE_FIELDS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "authorization",
}


def _redact_sensitive_data(data: dict | None) -> dict | None:
    """Redact sensitive fields from logging data."""
    if not data:
        return data

    redacted = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(field in key_lower for field in SENSITIVE_FIELDS):
            redacted[key] = "***REDACTED***"
        elif isinstance(value, dict):
            redacted[key] = _redact_sensitive_data(value)
        elif isinstance(value, list):
            redacted[key] = [
                _redact_sensitive_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            redacted[key] = value
    return redacted


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID to all requests and responses."""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # Use existing X-Request-ID if present, otherwise generate one
        request_id = request.headers.get(
            "X-Request-ID", str(uuid.uuid4())
        )

        # Add request ID to request state
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Only add HSTS in production (HTTPS)
        if settings.app_env == "production":
            response.headers[
                "Strict-Transport-Security"
            ] = "max-age=31536000; includeSubDomains"

        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log request/response with structured JSON logging and EMF metrics."""

    def __init__(self, app, exclude_paths: list[str] | None = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/health",
            "/api/v1/ping",
            "/docs",
            "/openapi.json",
            "/redoc",
        ]
        # Track active requests for gauge metric
        self._active_requests = 0

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # Skip logging for excluded paths
        if any(
            request.url.path.startswith(path)
            for path in self.exclude_paths
        ):
            return await call_next(request)

        # Extract request information
        request_id = getattr(request.state, "request_id", "unknown")
        start_time = time.time()

        # Increment active requests
        self._active_requests += 1

        # Get user info if available (from request state or auth)
        user_id = getattr(request.state, "user_id", None)
        tenant_id = getattr(request.state, "tenant_id", None)

        # Prepare request log data
        request_log = {
            "timestamp": time.time(),
            "level": "INFO",
            "type": "http_request",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_host": request.client.host if request.client else None,
            "user_id": str(user_id) if user_id else None,
            "tenant_id": str(tenant_id) if tenant_id else None,
        }

        # Log request body for POST/PUT/PATCH (excluding sensitive data)
        # Note: We can't read the body here without consuming it, so we'll
        # log it after processing. For now, just log the presence.
        if request.method in ("POST", "PUT", "PATCH"):
            # Check content-length if available
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    request_log["request_body_size"] = int(content_length)
                except ValueError:
                    pass

        # Log request
        logger.info(
            json.dumps(request_log, default=str),
            extra={"request_id": request_id},
        )

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
            error = None
        except Exception as e:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            error = str(e)
            
            # Log exception with full context
            logger.error(
                f"Request processing error: {type(e).__name__}: {str(e)}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "user_id": str(user_id) if user_id else None,
                    "tenant_id": str(tenant_id) if tenant_id else None,
                },
                exc_info=True,
            )
            raise
        finally:
            # Decrement active requests
            self._active_requests -= 1

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Emit EMF metrics
            try:
                from app.core.metrics import emit_http_request, emit_active_requests

                emit_http_request(
                    method=request.method,
                    path=request.url.path,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    request_id=request_id,
                    user_id=str(user_id) if user_id else None,
                    tenant_id=str(tenant_id) if tenant_id else None,
                )

                emit_active_requests(
                    count=self._active_requests,
                )
            except ImportError:
                # Metrics module not available, skip
                pass

            # Prepare response log data
            response_log = {
                "timestamp": time.time(),
                "level": "INFO" if status_code < 400 else "ERROR",
                "type": "http_response",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 2),
                "user_id": str(user_id) if user_id else None,
                "tenant_id": str(tenant_id) if tenant_id else None,
            }

            if error:
                response_log["error"] = error

            # Log response
            log_level = logging.ERROR if status_code >= 500 else (
                logging.WARNING if status_code >= 400 else logging.INFO
            )
            logger.log(
                log_level,
                json.dumps(response_log, default=str),
                extra={"request_id": request_id},
            )

        # Add timing header
        response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"

        return response


def setup_cors(app) -> None:
    """Configure CORS middleware."""
    # Determine allowed origins based on environment
    if settings.app_env == "production":
        # In production, configure via env var
        import os

        cors_origins_str = os.getenv("CORS_ORIGINS", "")
        if cors_origins_str:
            cors_origins = [origin.strip() for origin in cors_origins_str.split(",")]
        else:
            cors_origins = []  # No CORS in production if not configured
    else:
        # In dev, allow common localhost origins
        cors_origins = [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
        ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )


def setup_gzip(app) -> None:
    """Configure GZip compression middleware."""
    app.add_middleware(
        GZipMiddleware,
        minimum_size=500,  # Only compress responses > 500 bytes
        compresslevel=6,  # Balance between speed and compression
    )


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """Middleware to rate limit requests using Redis sliding window algorithm.

    Uses Redis to track request counts per IP or user identifier.
    Implements a sliding window rate limiting algorithm.
    """

    def __init__(self, app, exclude_paths: list[str] | None = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/health",
            "/api/v1/ping",
            "/docs",
            "/openapi.json",
            "/redoc",
        ]

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # Skip rate limiting for excluded paths
        if any(
            request.url.path.startswith(path)
            for path in self.exclude_paths
        ):
            return await call_next(request)

        # Get client identifier (IP address or user ID)
        client_ip = request.client.host if request.client else "unknown"
        user_id = getattr(request.state, "user_id", None)

        # Use user_id if available, otherwise use IP
        identifier = str(user_id) if user_id else client_ip
        identifier_type = "user" if user_id else "ip"

        # Get Redis connection
        redis_client = await get_redis_pool()

        if redis_client is None:
            # Redis not available, skip rate limiting
            logger.warning(
                "Rate limiting enabled but Redis unavailable, "
                "skipping rate limit check"
            )
            return await call_next(request)

        # Get rate limit configuration
        window_seconds = settings.rate_limit_window_seconds
        max_requests = (
            settings.rate_limit_max_requests_per_user
            if user_id
            else settings.rate_limit_max_requests_per_ip
        )

        # Generate Redis key
        redis_key = f"ratelimit:{identifier_type}:{identifier}"

        try:
            # Sliding window rate limiting using Redis
            now = time.time()
            window_start = now - window_seconds

            # Use Redis pipeline for atomic operations
            pipe = redis_client.pipeline()
            
            # Remove old entries outside the window
            pipe.zremrangebyscore(redis_key, 0, window_start)

            # Count current requests in window (before adding current request)
            pipe.zcard(redis_key)

            # Add current request timestamp
            pipe.zadd(redis_key, {str(now): now})

            # Set expiration on the key
            pipe.expire(redis_key, window_seconds)

            # Execute pipeline atomically
            results = await pipe.execute()
            
            # results[0] = zremrangebyscore result (number removed)
            # results[1] = zcard result (count before adding current request)
            # results[2] = zadd result (number added)
            # results[3] = expire result (success)
            current_count = results[1] + 1  # +1 for current request we just added

            if current_count > max_requests:
                # Rate limit exceeded
                logger.warning(
                    f"Rate limit exceeded for {identifier_type}:{identifier} "
                    f"({current_count}/{max_requests} requests)"
                )

                # Calculate retry-after
                oldest_request = await redis_client.zrange(
                    redis_key, 0, 0, withscores=True
                )
                if oldest_request:
                    oldest_time = oldest_request[0][1]
                    retry_after = int(window_seconds - (now - oldest_time)) + 1
                else:
                    retry_after = window_seconds

                return Response(
                    content=json.dumps(
                        {
                            "error": "rate_limit_exceeded",
                            "message": (
                                "Too many requests. "
                                f"Please try again in {retry_after} seconds."
                            ),
                            "retry_after": retry_after,
                        }
                    ),
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    headers={
                        "Content-Type": "application/json",
                        "X-RateLimit-Limit": str(max_requests),
                        "X-RateLimit-Remaining": str(
                            max(0, max_requests - current_count)
                        ),
                        "X-RateLimit-Reset": str(int(now + retry_after)),
                        "Retry-After": str(retry_after),
                    },
                )

            # Add rate limit headers to response
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(max_requests)
            response.headers["X-RateLimit-Remaining"] = str(
                max(0, max_requests - current_count)
            )
            response.headers["X-RateLimit-Reset"] = str(
                int(now + window_seconds)
            )

            return response

        except Exception as e:
            logger.error(f"Rate limiting error: {e}", exc_info=True)
            # On error, allow request through
            return await call_next(request)


class SlowConnectionMiddleware(BaseHTTPMiddleware):
    """Middleware to reject slow connections.

    Monitors connection establishment time and initial data transfer.
    Rejects connections that take too long to send initial request data.
    """

    def __init__(
        self,
        app,
        connection_timeout_seconds: float = 5.0,
        exclude_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.connection_timeout = connection_timeout_seconds
        self.exclude_paths = exclude_paths or [
            "/health",
            "/api/v1/ping",
            "/docs",
            "/openapi.json",
            "/redoc",
        ]

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # Skip for excluded paths
        if any(
            request.url.path.startswith(path)
            for path in self.exclude_paths
        ):
            return await call_next(request)

        # Use asyncio timeout to reject slow connections
        # This will cancel the request if it takes longer than the timeout
        try:
            response = await asyncio.wait_for(
                call_next(request),
                timeout=self.connection_timeout,
            )
            return response

        except asyncio.TimeoutError:
            # Request took too long - reject it
            logger.warning(
                f"Slow connection timeout: {self.connection_timeout}s "
                f"for {request.url.path} from {request.client.host}"
            )

            return Response(
                content=json.dumps(
                    {
                        "error": "connection_timeout",
                        "message": (
                            "Connection timeout. The request took too long "
                            "to complete. Please ensure your connection is "
                            "stable and try again."
                        ),
                    }
                ),
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                headers={"Content-Type": "application/json"},
            )

        except Exception as e:
            # Re-raise other exceptions (they'll be handled by error handlers)
            raise


def setup_rate_limiting(app) -> None:
    """Configure rate limiting middleware."""
    if settings.enable_rate_limiting:
        app.add_middleware(RateLimitingMiddleware)
        logger.info("Rate limiting middleware enabled")


def setup_slow_connection_rejection(app) -> None:
    """Configure slow connection rejection middleware."""
    if settings.enable_slow_connection_rejection:
        app.add_middleware(
            SlowConnectionMiddleware,
            connection_timeout_seconds=(
                settings.slow_connection_timeout_seconds
            ),
        )
        logger.info(
            f"Slow connection rejection middleware enabled "
            f"(timeout: {settings.slow_connection_timeout_seconds}s)"
        )

