"""Tasks 9-10 — fail-closed credit contract and idempotent order adapter.

Task 9 (R14 blocked): credit answers ``unavailable`` and never exposes an
available-credit amount, regardless of any ERP/snapshot payload.
Task 10 (R15 blocked): order submission ships as contract + fake only —
idempotent semantics with conflict rejection and unknown/reconcile timeout
handling; the real adapter stays disabled.
"""

from __future__ import annotations

import pytest

from depotru_kernel.auth import Audience, ToolScope
from depotru_tools.registry import (
    ToolContext,
    ToolPermissionError,
    get_default_registry,
    reset_default_registry,
)
from modules.b2b.credit import credit_status
from modules.b2b.orders import (
    STATE_SUBMITTED,
    STATE_UNKNOWN,
    FakeOrderAdapter,
    IdempotencyConflictError,
    J3OrderAdapter,
    OrderSubmitDisabled,
    get_order_adapter,
)

# ---------------------------------------------------------------------------
# Task 9 — credit fails closed (R14)
# ---------------------------------------------------------------------------


class _R14BaitErp:
    """Pretends to be a live credit source; the contract must ignore it."""

    def available_credit(self, terceros_id: str) -> dict:
        return {"cliente_cupo": "5000000", "saldo": "1200000"}


@pytest.mark.unit
def test_credit_status_always_unavailable():
    resp = credit_status("90123456", erp=_R14BaitErp())
    assert resp["credit_status"] == "unavailable"
    assert resp["available_credit"] is None
    assert resp["reason"] == "credit_terms_blocked_r14"


@pytest.mark.unit
def test_credit_status_never_leaks_an_amount():
    resp = credit_status("90123456", erp=_R14BaitErp())

    def _no_numbers(node: object) -> None:
        if isinstance(node, bool) or isinstance(node, (int, float)):
            pytest.fail("numeric amount leaked from credit endpoint")
        if isinstance(node, dict):
            for value in node.values():
                _no_numbers(value)
        elif isinstance(node, list):
            for value in node:
                _no_numbers(value)

    _no_numbers(resp)
    assert resp["source"] is None


@pytest.mark.unit
def test_credit_tool_is_b2b_scope_and_public_gets_403():
    try:
        reg = get_default_registry()
        spec = reg.get("b2b.credit_status")
        assert spec.scope is ToolScope.B2B_CREDIT
        assert spec.public_safe is False
        with pytest.raises(ToolPermissionError):
            reg.call(
                "b2b.credit_status",
                {"terceros_id": "1"},
                context=ToolContext(audience=Audience.PUBLIC),
            )
    finally:
        reset_default_registry()


# ---------------------------------------------------------------------------
# Task 10 — idempotent order adapter contract (R15: submit disabled)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fake_adapter_same_key_same_payload_same_erp_id():
    adapter = FakeOrderAdapter()
    payload = {"site": "neiva", "lines": [{"sku": "A", "qty": "1"}]}
    first = adapter.submit("ORD-1", payload)
    replay = adapter.submit("ORD-1", dict(payload))
    assert first.state == STATE_SUBMITTED
    assert first.erp_order_id
    assert replay == first


@pytest.mark.unit
def test_fake_adapter_same_key_different_payload_rejected():
    adapter = FakeOrderAdapter()
    adapter.submit("ORD-1", {"lines": [{"sku": "A", "qty": "1"}]})
    with pytest.raises(IdempotencyConflictError):
        adapter.submit("ORD-1", {"lines": [{"sku": "A", "qty": "5"}]})


@pytest.mark.unit
def test_fake_adapter_timeout_yields_unknown_then_reconciles():
    adapter = FakeOrderAdapter(timeout_keys={"ORD-T"})
    result = adapter.submit("ORD-T", {"lines": []})
    assert result.state == STATE_UNKNOWN
    assert result.erp_order_id is None
    # retry with the same key/payload queries by key first: still unknown
    retry = adapter.submit("ORD-T", {"lines": []})
    assert retry.state == STATE_UNKNOWN
    assert adapter.lookup("ORD-T").state == STATE_UNKNOWN  # type: ignore[union-attr]
    # vendor/ops lookup proof flips unknown → submitted
    reconciled = adapter.reconcile("ORD-T", "ERP-900001")
    assert reconciled.state == STATE_SUBMITTED
    assert reconciled.erp_order_id == "ERP-900001"
    assert adapter.lookup("ORD-T") == reconciled


@pytest.mark.unit
def test_fake_adapter_payload_comparison_is_key_order_insensitive():
    adapter = FakeOrderAdapter()
    first = adapter.submit("ORD-2", {"a": "1", "b": "2"})
    replay = adapter.submit("ORD-2", {"b": "2", "a": "1"})
    assert replay == first


@pytest.mark.unit
def test_real_adapter_disabled_r15():
    adapter = J3OrderAdapter()
    with pytest.raises(OrderSubmitDisabled):
        adapter.submit("ORD-1", {})
    with pytest.raises(OrderSubmitDisabled):
        adapter.lookup("ORD-1")


@pytest.mark.unit
def test_default_adapter_is_disabled(monkeypatch):
    monkeypatch.delenv("B2B_ORDER_ADAPTER", raising=False)
    assert isinstance(get_order_adapter(), J3OrderAdapter)
    monkeypatch.setenv("B2B_ORDER_ADAPTER", "fake")
    assert isinstance(get_order_adapter(), FakeOrderAdapter)


@pytest.mark.unit
def test_order_submit_tool_disabled_fail_closed():
    try:
        reg = get_default_registry()
        spec = reg.get("b2b.order_submit")
        assert spec.scope is ToolScope.B2B_ORDER
        resp = reg.call(
            "b2b.order_submit",
            {"order_key": "ORD-1", "payload": {"lines": []}},
            context=ToolContext(audience=Audience.B2B),
        )
        assert resp["status"] == "disabled"
        assert resp["reason"] == "r15_blocked"
    finally:
        reset_default_registry()
