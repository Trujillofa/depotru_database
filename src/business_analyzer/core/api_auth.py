"""Optional API key authentication for FastAPI endpoints."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Header, HTTPException, status


def api_key_configured() -> bool:
    return bool(os.getenv("API_KEY", "").strip())


def require_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> None:
    """Reject requests when API_KEY is set but header is missing or wrong."""
    expected = os.getenv("API_KEY", "").strip()
    if not expected:
        return
    if not x_api_key or x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
