"""The BFF entrypoint exposes the platform /v1 surface and refuses to start open."""

from __future__ import annotations

import pytest

from apps.api.bff import configured_audiences, create_app


def test_refuses_without_key_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PLATFORM_API_KEYS", raising=False)
    with pytest.raises(RuntimeError, match="PLATFORM_API_KEYS"):
        create_app()


def test_refuses_without_b2b_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_API_KEYS", "pub:public,ops:service")
    with pytest.raises(RuntimeError, match="b2b audience"):
        create_app()


def test_exposes_only_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_API_KEYS", "b2bkey:b2b,pub:public")
    paths = set(create_app().openapi()["paths"])
    assert "/v1/tools/call" in paths
    assert "/healthz" in paths
    # The BI surface must never be reachable through the BFF.
    assert not any(
        path.startswith(("/analysis", "/metrics", "/vanna")) for path in paths
    )


def test_configured_audiences_parses_map() -> None:
    # Entries without a separator, or with an empty key/audience, are dropped.
    assert configured_audiences("a:b2b, b:public ,garbage, :service,noaud:") == {
        "b2b",
        "public",
    }
    assert configured_audiences("a:b2b, x:service") == {"b2b", "service"}


def test_duplicate_key_with_two_audiences_is_refused() -> None:
    # v1 keeps the last mapping, so a duplicated key would be silently
    # reassigned; the app must refuse to start instead of guessing.
    with pytest.raises(RuntimeError, match="two audiences"):
        configured_audiences("storefront:b2b,storefront:public")


def test_b2b_key_reaches_b2b_stock_over_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """The route must be proven through the published app, not the registry.

    The 403 that broke the pickup gate was an audience/scope mismatch that no
    registry-level test can see: only a request through create_app() sees it.
    """
    from fastapi.testclient import TestClient

    import modules.b2b.register as reg_mod

    monkeypatch.setenv("PLATFORM_API_KEYS", "store:b2b,bi:public")
    monkeypatch.setattr(
        reg_mod,
        "catalog_stock",
        lambda ctx, params: {
            "ok": True,
            "sede": "florencia",
            "results": [{"sku": "X", "status": "ok"}],
        },
    )
    client = TestClient(create_app())

    ok = client.post(
        "/v1/tools/call",
        json={"name": "b2b.stock", "params": {"skus": ["X"], "sede": "florencia"}},
        headers={"X-API-Key": "store"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["audience"] == "b2b"
    assert ok.json()["result"]["results"][0]["sku"] == "X"

    denied = client.post(
        "/v1/tools/call",
        json={"name": "b2b.stock", "params": {"skus": ["X"], "sede": "florencia"}},
        headers={"X-API-Key": "bi"},
    )
    assert denied.status_code == 403
