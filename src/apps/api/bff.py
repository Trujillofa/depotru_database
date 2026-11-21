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


def parse_platform_keys(raw: str | None = None) -> dict[str, str]:
    """Parse ``PLATFORM_API_KEYS`` (``key:audience,key2:audience2``) into a map.

    Raises when one key is mapped to two audiences. ``v1.require_scoped_api_key``
    keeps the last mapping for a duplicated key, so a key appended with a second
    audience would be silently reassigned -- a public key could inherit b2b
    scopes, or the storefront key could fall back to a lesser audience and every
    ``b2b.stock`` call would 403. Refusing to start is the only silent-safe answer.
    """
    value = (raw if raw is not None else os.getenv("PLATFORM_API_KEYS", "")).strip()
    mapping: dict[str, str] = {}
    for part in value.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        key, audience = part.split(":", 1)
        key, audience = key.strip(), audience.strip().lower()
        if not key or not audience:
            continue
        if key in mapping and mapping[key] != audience:
            raise RuntimeError(
                f"PLATFORM_API_KEYS maps one key to two audiences ({mapping[key]!r} and "
                f"{audience!r}): refusing to guess which one the credential is."
            )
        mapping[key] = audience
    return mapping


def configured_audiences(raw: str | None = None) -> set[str]:
    """Audiences present in ``PLATFORM_API_KEYS``."""
    return set(parse_platform_keys(raw).values())


def create_app() -> FastAPI:
    """Build the BFF app, or fail closed when the credential model is missing."""
    raw = os.getenv("PLATFORM_API_KEYS", "")
    if not raw.strip():
        raise RuntimeError(
            "PLATFORM_API_KEYS is not set: the BFF never starts without key->audience mapping."
        )
    if B2B_AUDIENCE not in parse_platform_keys(raw).values():
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
