"""Main FastAPI application with middleware and logging setup."""

from __future__ import annotations

import json
import logging
import os
import sys
import time

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.errors import setup_error_handlers
from app.core.middleware import (
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
    RequestLoggingMiddleware,
    setup_cors,
    setup_gzip,
    setup_rate_limiting,
    setup_slow_connection_rejection,
)
from app.auth.routes import router as auth_router
from app.auth.oauth_routes import router as oauth_router
from app.users.routes import router as users_router

# API prefix constant
API_PREFIX = "/api/v1"


def setup_logging() -> None:
    """Configure structured JSON logging for CloudWatch compatibility."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # JSON format for CloudWatch Logs
    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_data = {
                "timestamp": time.time(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }

            # Add extra fields from record
            if hasattr(record, "request_id"):
                log_data["request_id"] = record.request_id

            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)

            return json.dumps(log_data, default=str)

    if settings.log_format == "json":
        formatter: logging.Formatter = JSONFormatter()
    else:
        # Human-readable format for dev
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - "
            "[%(request_id)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    # Clear existing handlers to avoid duplicates
    root_logger.handlers = []
    root_logger.addHandler(handler)

    # Set levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# Setup logging before creating app
setup_logging()

app = FastAPI(
    title=f"{settings.tenant_name} Reporting Platform API",
    version="0.1.0",
)

# Setup error handlers (must be done before routes are added)
setup_error_handlers(app, debug=(settings.app_env != "production"))

# Add middleware (order matters - add in reverse order of execution)
# Last added = first executed

# 1. Request ID (first to execute, last to add)
app.add_middleware(RequestIDMiddleware)

# 2. Security Headers
app.add_middleware(SecurityHeadersMiddleware)

# 3. Request Logging (after request ID is set)
if settings.enable_request_logging:
    app.add_middleware(RequestLoggingMiddleware)

# 4. Rate Limiting (before CORS, after auth context)
setup_rate_limiting(app)

# 5. Slow Connection Rejection
setup_slow_connection_rejection(app)

# 6. CORS
setup_cors(app)

# 7. GZip Compression (last to execute, first to add)
if settings.enable_gzip:
    setup_gzip(app)

# Include routers
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(oauth_router, prefix=API_PREFIX)
app.include_router(users_router, prefix=API_PREFIX)


@app.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(
        {
            "status": "ok",
            "env": os.getenv("APP_ENV", "dev"),
            "version": app.version,
        }
    )


@app.get(f"{API_PREFIX}/ping")
async def ping() -> dict:
    """Simple ping endpoint for connectivity checks."""
    return {"message": "pong"}
