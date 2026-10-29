"""Minimal BFF surface for the B2B pilot: the platform ``/v1`` API and nothing else.

The BI application (``src/api.py``) mounts the v1 router next to endpoints whose
``require_api_key`` dependency is a no-op when ``API_KEY`` is unset. Publishing
that app to reach ``b2b.quote`` from Magento would therefore publish the BI
surface too. This module mounts only ``/v1`` and refuses to start unless a
dedicated B2B audience key is configured (R22).

Run as a factory so importing the module never depends on the environment:

    PLATFORM_API_KEYS="key:audience,..." \
        uvicorn apps.api.bff:create_app --factory --host 127.0.0.1 --port 8099
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from apps.api.v1 import router as platform_v1_router

B2B_AUDIENCE = "b2b"


def configured_audiences(raw: str | None = None) -> set[str]:
    """Audiences present in ``PLATFORM_API_KEYS`` (``key:audience,key2:audience2``)."""
    value = (raw if raw is not None else os.getenv("PLATFORM_API_KEYS", "")).strip()
    audiences: set[str] = set()
    for part in value.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        key, audience = part.split(":", 1)
        if key.strip() and audience.strip():
            audiences.add(audience.strip().lower())
    return audiences


def create_app() -> FastAPI:
    """Build the BFF app, or fail closed when the credential model is missing."""
    raw = os.getenv("PLATFORM_API_KEYS", "")
    if not raw.strip():
        raise RuntimeError(
            "PLATFORM_API_KEYS is not set: the BFF never starts without key->audience mapping."
        )
    if B2B_AUDIENCE not in configured_audiences(raw):
        raise RuntimeError(
            "No key is mapped to the b2b audience: R22 requires a dedicated B2B credential."
        )

    app = FastAPI(
        title="Depositotrujillo BFF",
        description="Platform v1 surface for Magento (b2b.quote and friends).",
        version="1.0.0",
    )
    app.include_router(platform_v1_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
