"""Helpers for extracting request information for audit logging."""

from __future__ import annotations

from typing import Optional, Tuple

from fastapi import Request


def get_request_ip(request: Request) -> Optional[str]:
    """Extract IP address from request."""
    # Check X-Forwarded-For header first (for proxied requests)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def get_request_user_agent(request: Request) -> Optional[str]:
    """Extract user agent from request."""
    return request.headers.get("User-Agent")


async def get_request_info(request: Request) -> Tuple[Optional[str], Optional[str]]:
    """Extract IP and user agent from request."""
    return (get_request_ip(request), get_request_user_agent(request))



