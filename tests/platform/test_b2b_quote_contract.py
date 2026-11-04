"""Task 7 — B2B quote request contract tests (fake ERP, no live DB).

Locked by docs/b2b requirements R11/R12/R19/R22 + erp-contract.md:
- Request is server-to-server only: company_ref, terceros_id, site, items.
- Response: quote reference, SKU, net unit price, price_includes_iva, unit,
  currency, decimal-safe amounts, item-level errors, timestamp/expiry,
  correlation ID. Omit phone, legal ID, cost, margin, customer name and
  warehouse qty (R12 blocked).
- Fail closed: invalid site/SKU, missing tariff, refused tariff (006 / id 6 /
  AL COSTO), oversized carts (no cap), ERP failure, timeouts. Never
  fall back to retail / catalog.quote_search list price.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Optional

import pytest

from depotru_kernel.auth import Audience, ToolScope
from depotru_tools.registry import (
    ToolContext,
    ToolPermissionError,
    get_default_registry,
    reset_default_registry,
)
from modules.b2b.contracts import (
    CURRENCY,
    SKU_MAX_LEN,
    UNIT,
    ErpTimeoutError,
    ErpUnavailableError,
)
from modules.b2b.service import _QUOTE_TTL, request_quote

_NOW = datetime(2026, 10, 27, 12, 0, 0, tzinfo=timezone.utc)


class FakeErp:
    """Fake customer-tariff ERP per erp-contract.md candidate semantics."""

    def __init__(
        self,
        prices: Optional[Mapping[str, Mapping[str, str]]] = None,
        warehouse_qty: Optional[Mapping[str, str]] = None,
        raise_error: Optional[Exception] = None,
    ) -> None:
        self._prices = dict(prices or {})
        self._warehouse_qty = dict(warehouse_qty or {})
        self._raise = raise_error
        self.called_with: Optional[Mapping[str, Any]] = None

    def customer_quote(
        self, site: str, terceros_id: str, skus: list[str]
    ) -> list[dict]:
        if self._raise is not None:
            raise self._raise
        self.called_with = {
            "site": site,
            "terceros_id": terceros_id,
            "skus": list(skus),
        }
        rows = []
        for sku in skus:
            info = self._prices.get(sku)
            if info is None:
                continue
            row = {
                "sku": sku,
                "net_price": Decimal(info["net_price"]),
                "tariff_id": info.get("tariff_id", "1"),
                "tariff_code": info.get("tariff_code", "001"),
                "tariff_name": info.get("tariff_name", "PUBLICO GENERAL"),
            }
            if sku in self._warehouse_qty:
                row["warehouse_qty"] = dict(self._warehouse_qty[sku])
            rows.append(row)
        return rows


_GOOD_PRICES = {
    "CEMENTO-50": {"net_price": "38500.00"},
    "CLAVOS-2I": {"net_price": "12345.67"},
    "REFUSED-006": {
        "net_price": "999.99",
        "tariff_id": "6",
        "tariff_code": "006",
        "tariff_name": "AL COSTO",
    },
    "NO-TARIFA": {"net_price": "5000.00", "tariff_id": "", "tariff_code": ""},
}


def _request(items: Optional[list] = None, **overrides: Any) -> dict:
    req: dict[str, Any] = {
        "company_ref": "company-a",
        "terceros_id": "90123456",
        "site": "neiva",
        "items": items if items is not None else [{"sku": "CEMENTO-50", "qty": "10"}],
    }
    req.update(overrides)
    return req


# ---------------------------------------------------------------------------
# Happy path + response shape
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_valid_quote_response_shape():
    resp = request_quote(
        _request(),
        FakeErp(_GOOD_PRICES),
        correlation_id="corr-1",
        now=_NOW,
    )
    assert resp["status"] == "ok"
    assert resp["quote_reference"]
    assert resp["company_ref"] == "company-a"
    assert resp["terceros_id"] == "90123456"
    assert resp["site"] == "neiva"
    assert resp["currency"] == CURRENCY == "COP"
    assert resp["price_includes_iva"] is False  # R11: net before IVA
    assert resp["correlation_id"] == "corr-1"
    line = resp["lines"][0]
    assert line["sku"] == "CEMENTO-50"
    assert line["status"] == "ok"
    assert line["unit_net_price"] == "38500.00"  # decimal-safe string
    assert line["line_total"] == "385000.00"
    assert line["qty"] == "10"
    assert line["unit"] == UNIT == "UND"
    # timestamp/expiry are ISO-8601 and expiry is after timestamp
    ts = datetime.fromisoformat(resp["timestamp"])
    exp = datetime.fromisoformat(resp["expires_at"])
    assert exp > ts
    assert exp - ts == _QUOTE_TTL


@pytest.mark.unit
def test_correlation_id_generated_when_absent():
    resp = request_quote(_request(), FakeErp(_GOOD_PRICES), now=_NOW)
    assert resp["correlation_id"]


@pytest.mark.unit
def test_decimal_safe_no_json_floats():
    resp = request_quote(_request(), FakeErp(_GOOD_PRICES), now=_NOW)
    roundtrip = json.loads(json.dumps(resp))
    assert roundtrip == json.loads(json.dumps(json.loads(json.dumps(resp))))

    def _no_floats(node: Any) -> None:
        if isinstance(node, float):
            pytest.fail("float leaked into B2B quote response")
        if isinstance(node, dict):
            for value in node.values():
                _no_floats(value)
        if isinstance(node, list):
            for value in node:
                _no_floats(value)

    _no_floats(roundtrip)
    line = roundtrip["lines"][0]
    assert isinstance(line["unit_net_price"], str)
    assert isinstance(line["line_total"], str)


@pytest.mark.unit
def test_omits_phone_legal_id_cost_margin_customer_name():
    resp = request_quote(_request(), FakeErp(_GOOD_PRICES), now=_NOW)
    forbidden = {
        "phone",
        "telefono",
        "celular",
        "legal_id",
        "nit",
        "terceros_identificacion",
        "cost",
        "costo",
        "margin",
        "margen",
        "customer_name",
        "nombre",
        "razon_social",
    }

    def _scan(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                assert key.lower() not in forbidden, key
                _scan(value)
        elif isinstance(node, list):
            for value in node:
                _scan(value)

    _scan(resp)


@pytest.mark.unit
def test_omits_warehouse_qty_even_when_erp_returns_it():
    """R12 blocked: the candidate ERP returns per-warehouse qty; v1 omits it."""
    erp = FakeErp(
        _GOOD_PRICES,
        warehouse_qty={"CEMENTO-50": {"ALM": "100", "BD6": "40"}},
    )
    resp = request_quote(_request(), erp, now=_NOW)
    assert erp.called_with is not None  # ERP did return warehouse data

    def _scan(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                assert key.lower() not in ("warehouse_qty", "warehouses"), key
                _scan(value)
        elif isinstance(node, list):
            for value in node:
                _scan(value)

    _scan(resp)


# ---------------------------------------------------------------------------
# Request-level failures (fail closed before ERP)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_invalid_site_rejected():
    resp = request_quote(_request(site="bogota"), FakeErp(_GOOD_PRICES), now=_NOW)
    assert resp["status"] == "error"
    assert resp["reason"] == "site_invalid"


def _identityless(*keys: str) -> dict:
    req = _request()
    for key in keys:
        req.pop(key, None)
    return req


@pytest.mark.unit
def test_missing_identity_fields_rejected():
    for req in (
        _identityless("company_ref"),
        _identityless("terceros_id"),
    ):
        resp = request_quote(req, FakeErp(_GOOD_PRICES), now=_NOW)
        assert resp["status"] == "error"
        assert resp["reason"] == "identity_required"


@pytest.mark.unit
def test_empty_or_non_list_items_rejected():
    for items in ([], "ceemento", None):
        req = _request()
        req["items"] = items
        resp = request_quote(req, FakeErp(_GOOD_PRICES), now=_NOW)
        assert resp["status"] == "error"
        assert resp["reason"] == "items_invalid"


@pytest.mark.unit
def test_no_sku_cap_reaches_line_validation():
    """R19 cap removed (Yderf, 2026-10-31): a 21-SKU cart is no longer refused
    up front; it proceeds to per-line validation and reaches the ERP."""
    items = [{"sku": f"SKU-{i:03d}", "qty": "1"} for i in range(21)]
    erp = FakeErp(_GOOD_PRICES)
    resp = request_quote(_request(items=items), erp, now=_NOW)
    assert resp.get("reason") != "too_many_skus"
    assert erp.called_with is not None  # request was not blocked before the ERP


# ---------------------------------------------------------------------------
# Line-level failures (fail closed, never a retail fallback)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_sku_too_long_rejected():
    assert SKU_MAX_LEN == 40
    items = [{"sku": "X" * (SKU_MAX_LEN + 1), "qty": "1"}]
    resp = request_quote(_request(items=items), FakeErp(_GOOD_PRICES), now=_NOW)
    assert resp["status"] == "ok"  # request-level ok
    line = resp["lines"][0]
    assert line["status"] == "error"
    assert line["error"] == "sku_too_long"
    assert "unit_net_price" not in line


@pytest.mark.unit
def test_invalid_qty_rejected():
    for qty in ("0", "-3", "abc", ""):
        items = [{"sku": "CEMENTO-50", "qty": qty}]
        resp = request_quote(_request(items=items), FakeErp(_GOOD_PRICES), now=_NOW)
        line = resp["lines"][0]
        assert line["status"] == "error", qty
        assert line["error"] == "invalid_qty"


@pytest.mark.unit
def test_unknown_sku_item_error():
    items = [
        {"sku": "CEMENTO-50", "qty": "1"},
        {"sku": "NO-EXISTE", "qty": "2"},
    ]
    resp = request_quote(_request(items=items), FakeErp(_GOOD_PRICES), now=_NOW)
    assert resp["status"] == "ok"
    by_sku = {line["sku"]: line for line in resp["lines"]}
    assert by_sku["CEMENTO-50"]["status"] == "ok"
    assert by_sku["NO-EXISTE"]["status"] == "error"
    assert by_sku["NO-EXISTE"]["error"] == "unknown_sku"
    assert "unit_net_price" not in by_sku["NO-EXISTE"]


@pytest.mark.unit
def test_missing_tariff_fail_closed():
    items = [{"sku": "NO-TARIFA", "qty": "1"}]
    resp = request_quote(_request(items=items), FakeErp(_GOOD_PRICES), now=_NOW)
    line = resp["lines"][0]
    assert line["status"] == "error"
    assert line["error"] == "missing_tariff"
    assert "unit_net_price" not in line


@pytest.mark.unit
def test_refused_tariff_006_fail_closed():
    items = [{"sku": "REFUSED-006", "qty": "1"}]
    resp = request_quote(_request(items=items), FakeErp(_GOOD_PRICES), now=_NOW)
    line = resp["lines"][0]
    assert line["status"] == "error"
    assert line["error"] == "refused_tariff"
    assert "unit_net_price" not in line


@pytest.mark.unit
def test_erp_unavailable_fail_closed():
    resp = request_quote(
        _request(),
        FakeErp(raise_error=ErpUnavailableError("j3 down")),
        correlation_id="corr-1",
        now=_NOW,
    )
    assert resp["status"] == "unavailable"
    assert resp["reason"] == "erp_unavailable"
    assert resp["correlation_id"] == "corr-1"
    assert resp["lines"] == []  # never a partial/retail answer


@pytest.mark.unit
def test_erp_timeout_fail_closed():
    resp = request_quote(
        _request(), FakeErp(raise_error=ErpTimeoutError("timeout")), now=_NOW
    )
    assert resp["status"] == "unavailable"
    assert resp["reason"] == "erp_timeout"


@pytest.mark.unit
def test_erp_failure_never_falls_back_to_retail_list_price():
    """R11/R22: no catalog.quote_search style answer leaks through this route."""
    resp = request_quote(
        _request(), FakeErp(raise_error=ErpUnavailableError("down")), now=_NOW
    )
    assert "products" not in resp
    assert "search_url" not in resp
    assert "source" not in resp


@pytest.mark.unit
def test_erp_receives_server_identity_not_browser_input():
    erp = FakeErp(_GOOD_PRICES)
    request_quote(_request(), erp, now=_NOW)
    assert erp.called_with == {
        "site": "neiva",
        "terceros_id": "90123456",
        "skus": ["CEMENTO-50"],
    }


# ---------------------------------------------------------------------------
# Tool registration (R22: never reuse catalog.quote_search)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_b2b_quote_tool_registered_with_b2b_scope_only():
    try:
        reg = get_default_registry()
        spec = reg.get("b2b.quote")
        assert spec.scope is ToolScope.B2B_QUOTE
        assert spec.public_safe is False
        # distinct capability from the public list-price search
        assert reg.get("catalog.quote_search").scope is ToolScope.PUBLIC_CATALOG
        with pytest.raises(ToolPermissionError):
            reg.call("b2b.quote", {}, context=ToolContext(audience=Audience.PUBLIC))
    finally:
        reset_default_registry()
