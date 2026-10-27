"""Task 6 — B2B authorization red tests (audience isolation, 401/403 matrix).

Locked by requirements.md R22: a dedicated B2B audience/key must exist; the
``public``, ``agent``, and storefront-Assistant (public) keys must get 403 on
B2B routes; the B2B credential can invoke only B2B routes. ``SERVICE`` does
not include ``SALES_PORTFOLIO`` and must not gain B2B scopes either.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from apps.api.v1 import require_scoped_api_key
from depotru_kernel.auth import (
    Audience,
    ToolScope,
    audience_may_use,
    scopes_for_audience,
)
from depotru_tools.registry import (
    ToolContext,
    ToolPermissionError,
    ToolRegistry,
    ToolSpec,
)

B2B_SCOPES = {
    ToolScope.B2B_QUOTE,
    ToolScope.B2B_CREDIT,
    ToolScope.B2B_ORDER,
}

_NON_ADMIN_AUDIENCES = (
    Audience.PUBLIC,
    Audience.CUSTOMER,
    Audience.SALES,
    Audience.WAREHOUSE,
    Audience.SERVICE,
    Audience.AGENT,
)


# ---------------------------------------------------------------------------
# Audience / scope model
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_b2b_audience_exists():
    assert Audience.B2B.value == "b2b"


@pytest.mark.unit
def test_b2b_scopes_exist():
    assert ToolScope.B2B_QUOTE.value == "b2b_quote"
    assert ToolScope.B2B_CREDIT.value == "b2b_credit"
    assert ToolScope.B2B_ORDER.value == "b2b_order"


@pytest.mark.unit
def test_b2b_audience_gets_only_b2b_scopes():
    """The dedicated B2B credential can invoke only B2B routes."""
    assert set(scopes_for_audience(Audience.B2B)) == B2B_SCOPES


@pytest.mark.unit
def test_no_other_non_admin_audience_has_b2b_scopes():
    for aud in _NON_ADMIN_AUDIENCES:
        scopes = scopes_for_audience(aud)
        assert scopes.isdisjoint(B2B_SCOPES), f"{aud.value} gained a B2B scope"


@pytest.mark.unit
def test_admin_keeps_all_scopes():
    assert set(scopes_for_audience(Audience.ADMIN)) == set(ToolScope)


@pytest.mark.unit
def test_b2b_cannot_invoke_non_b2b_routes():
    for scope in set(ToolScope) - B2B_SCOPES:
        assert not audience_may_use(Audience.B2B, scope), scope.value


# ---------------------------------------------------------------------------
# Registry enforcement (403 matrix)
# ---------------------------------------------------------------------------


def _registry_with_b2b_tool() -> ToolRegistry:
    reg = ToolRegistry()

    def _ok(ctx, params):  # noqa: ANN001, ARG001
        return {"ok": True}

    reg.register(
        ToolSpec(
            name="b2b.quote",
            description="B2B negotiated quote (test stub)",
            scope=ToolScope.B2B_QUOTE,
            handler=_ok,
            public_safe=False,
        )
    )
    reg.register(
        ToolSpec(
            name="catalog.quote_search",
            description="Public list-price search",
            scope=ToolScope.PUBLIC_CATALOG,
            handler=_ok,
            public_safe=True,
        )
    )
    return reg


@pytest.mark.unit
def test_public_agent_service_keys_get_403_on_b2b_tool():
    """R22: public, agent and storefront-Assistant style keys must 403."""
    reg = _registry_with_b2b_tool()
    for aud in (Audience.PUBLIC, Audience.AGENT, Audience.SERVICE, Audience.CUSTOMER):
        with pytest.raises(ToolPermissionError):
            reg.call("b2b.quote", {}, context=ToolContext(audience=aud))


@pytest.mark.unit
def test_b2b_key_invokes_b2b_tools_only():
    reg = _registry_with_b2b_tool()
    ctx = ToolContext(audience=Audience.B2B)
    assert reg.call("b2b.quote", {}, context=ctx) == {"ok": True}
    with pytest.raises(ToolPermissionError):
        reg.call("catalog.quote_search", {}, context=ctx)


# ---------------------------------------------------------------------------
# API key mapping (401 + dedicated B2B credential)
# ---------------------------------------------------------------------------


def test_missing_or_wrong_key_is_401(monkeypatch):
    monkeypatch.setenv("PLATFORM_API_KEYS", "b2b-key:b2b,store-key:public")
    with pytest.raises(HTTPException) as exc:
        require_scoped_api_key(x_api_key=None, x_audience=None)
    assert exc.value.status_code == 401
    with pytest.raises(HTTPException) as exc:
        require_scoped_api_key(x_api_key="not-a-key", x_audience=None)
    assert exc.value.status_code == 401


def test_dedicated_b2b_key_maps_to_b2b_audience(monkeypatch):
    monkeypatch.setenv("PLATFORM_API_KEYS", "b2b-key:b2b,store-key:public")
    assert require_scoped_api_key(x_api_key="b2b-key", x_audience=None) is Audience.B2B
    # Storefront Assistant uses a public key: never elevated, never B2B.
    assert (
        require_scoped_api_key(x_api_key="store-key", x_audience=None)
        is Audience.PUBLIC
    )
