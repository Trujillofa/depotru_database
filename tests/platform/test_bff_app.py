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
