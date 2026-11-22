"""POST /v1/tools/call must not serialize the event loop.

The endpoint used to be ``async def`` while running the synchronous tool
handler (pymssql J3 queries, seconds each) directly on the event loop of a
single-worker uvicorn: one slow tool call froze every concurrent request and
the inbox advisor's fixed 8 s client timeout turned queue position into the
opciones/clarify/bff_error lottery (kanban t_ffbf9522, 2026-11-21).

This regression pins the offload: two concurrent slow tool calls must overlap
in the server's worker threads, not queue on the event loop.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Mapping

import httpx
import pytest

import modules.b2b.register as reg_mod
from apps.api.bff import create_app

SLEEP_SECONDS = 0.3


def _slow_catalog_stock(ctx: Any, params: Mapping[str, Any]) -> dict:
    time.sleep(SLEEP_SECONDS)
    return {"ok": True, "sede": params.get("sede", "florencia"), "results": []}


@pytest.mark.asyncio
async def test_concurrent_tool_calls_overlap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLATFORM_API_KEYS", "store:b2b,bi:public")
    monkeypatch.setattr(reg_mod, "catalog_stock", _slow_catalog_stock)
    app = create_app()

    request_body = {
        "name": "b2b.stock",
        "params": {"skus": ["X"], "sede": "florencia"},
    }
    headers = {"X-API-Key": "store"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://bff"
    ) as client:
        started = time.monotonic()
        responses = await asyncio.gather(
            client.post("/v1/tools/call", json=request_body, headers=headers),
            client.post("/v1/tools/call", json=request_body, headers=headers),
        )
        elapsed = time.monotonic() - started

    for response in responses:
        assert response.status_code == 200, response.text
        assert response.json()["result"]["ok"] is True

    # Serial execution takes >= 2 * SLEEP_SECONDS (0.6 s); overlapped
    # execution finishes in ~SLEEP_SECONDS. The threshold sits strictly
    # between the two so the test is red while the loop is blocked.
    assert elapsed < 2 * SLEEP_SECONDS - 0.1, (
        f"tool calls serialized on the server: {elapsed:.2f}s for two "
        f"{SLEEP_SECONDS}s calls"
    )
