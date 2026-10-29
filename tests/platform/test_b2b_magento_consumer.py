"""Conformance: a real ``b2b.quote`` response must satisfy Magento's consumer.

Magento validates the tool result in
``custom-modules/DepositoTrujillo/B2b/Model/B2bQuoteService.php`` before it
writes a quote snapshot, and it matches response lines to request lines **by
index** with strict string comparison on ``qty``. Until now each repo tested
only its own side: Magento against a fake BFF, the BFF against its own
expectations. A renamed field or a reformatted quantity would therefore only
surface on staging, at the moment a buyer tries to price a cart — fail closed,
but a dead end for the pilot.

This module replays Magento's rules (as of origin/main 81d678dd) against a real
``request_quote()`` response, including the JSON round trip Magento actually
sees, and pins the two quantity normalizers together.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Optional

import pytest

from modules.b2b.contracts import UNIT
from modules.b2b.service import request_quote

_NOW = datetime(2026, 10, 29, 15, 0, 0, tzinfo=timezone.utc)
_DECIMAL_RE = re.compile(r"^\d+(?:\.\d+)?$")


class FakeErp:
    """Minimal customer-tariff ERP: one row per known SKU, no warehouse qty."""

    def __init__(self, prices: Mapping[str, str]) -> None:
        self._prices = dict(prices)
        self.called_with: Optional[dict] = None

    def customer_quote(
        self, site: str, terceros_id: str, skus: list[str]
    ) -> list[dict]:
        self.called_with = {
            "site": site,
            "terceros_id": terceros_id,
            "skus": list(skus),
        }
        return [
            {
                "sku": sku,
                "net_price": Decimal(self._prices[sku]),
                "tariff_id": "1",
                "tariff_code": "001",
                "tariff_name": "PUBLICO GENERAL",
            }
            for sku in skus
            if sku in self._prices
        ]


_PRICES = {
    "0040120004": "2554.0000",
    "CEMENTO-50": "38500.00",
    "CLAVOS-2I": "12345.67",
}


def magento_qty(raw: float) -> str:
    """Magento's CartLineExtractor::qty() — the string it puts on the wire."""
    formatted = f"{raw:.4f}".rstrip("0").rstrip(".")
    return formatted


def magento_payload(items: list[dict]) -> dict:
    """The params Magento's B2bQuoteService::quote() sends."""
    return {
        "company_ref": "2",
        "terceros_id": "7710",
        "site": "neiva",
        "items": items,
    }


class MagentoB2bQuoteValidator:
    """Replica of the checks in B2bQuoteService::quote() (Magento side)."""

    REQUIRED_LINE_KEYS = ("sku", "qty", "unit_net_price", "line_total", "unit")

    def validate(
        self, data: Mapping[str, Any], sent_items: list[dict], site: str
    ) -> list[str]:
        errors: list[str] = []
        if data.get("status") != "ok":
            errors.append("status is not ok")
        if data.get("site") != site:
            errors.append("site echoed differently")
        if data.get("currency") != "COP":
            errors.append("currency is not COP")
        if not data.get("quote_reference"):
            errors.append("quote_reference missing")
        if "timestamp" not in data or "expires_at" not in data:
            errors.append("timestamp/expires_at missing")
            return errors
        try:
            created = datetime.fromisoformat(str(data["timestamp"]))
            expires = datetime.fromisoformat(str(data["expires_at"]))
        except ValueError:
            errors.append("timestamp/expires_at unparseable")
            return errors
        if expires <= created:
            errors.append("expires_at is not after timestamp")
        if expires <= _NOW:
            errors.append("quote is already expired")

        lines = data.get("lines")
        if not isinstance(lines, list):
            errors.append("lines is not a list")
            return errors
        if len(lines) != len(sent_items):
            errors.append("line count differs from the request")
            return errors

        for index, line in enumerate(lines):
            expected = sent_items[index]
            if not isinstance(line, Mapping):
                errors.append(f"line {index} is not an object")
                continue
            if line.get("status") != "ok":
                errors.append(f"line {index} status is {line.get('status')!r}")
            for key in self.REQUIRED_LINE_KEYS:
                if key not in line:
                    errors.append(f"line {index} is missing {key}")
            if line.get("sku") != expected["sku"]:
                errors.append(f"line {index} sku mismatch")
            if str(line.get("qty")) != str(expected["qty"]):
                errors.append(
                    f"line {index} qty {line.get('qty')!r} != sent {expected['qty']!r}"
                )
            for amount_key in ("unit_net_price", "line_total"):
                value = line.get(amount_key)
                if not isinstance(value, str):
                    errors.append(f"line {index} {amount_key} is not a string")
                elif not _DECIMAL_RE.match(value):
                    errors.append(f"line {index} {amount_key} is not decimal-safe")
            if not isinstance(line.get("qty"), str):
                errors.append(f"line {index} qty is not a string")
            if not isinstance(line.get("unit"), str) or line.get("unit") != UNIT:
                errors.append(f"line {index} unit is not {UNIT}")
        return errors


@pytest.mark.unit
def test_magento_consumer_accepts_a_real_quote_response():
    """The whole point: a genuine b2b.quote reply passes Magento's validator."""
    items = [
        {"sku": "0040120004", "qty": magento_qty(1)},
        {"sku": "CEMENTO-50", "qty": magento_qty(10)},
        {"sku": "CLAVOS-2I", "qty": magento_qty(1.5)},
    ]
    erp = FakeErp(_PRICES)

    result = request_quote(
        magento_payload(items), erp, correlation_id="abc123", now=_NOW
    )

    errors = MagentoB2bQuoteValidator().validate(result, items, "neiva")
    assert errors == [], f"Magento would reject this response: {errors}"
    assert result["price_includes_iva"] is False, "R11: net prices, Magento owns tax"
    assert result["correlation_id"] == "abc123"


@pytest.mark.unit
def test_the_response_survives_the_json_round_trip_magento_parses():
    """Magento unserializes JSON; anything numeric there becomes a float."""
    items = [{"sku": "0040120004", "qty": magento_qty(2)}]

    result = request_quote(magento_payload(items), FakeErp(_PRICES), now=_NOW)
    wire = json.loads(json.dumps(result))

    errors = MagentoB2bQuoteValidator().validate(wire, items, "neiva")
    assert errors == [], f"response breaks after JSON: {errors}"
    assert isinstance(wire["lines"][0]["unit_net_price"], str)
    assert isinstance(wire["lines"][0]["line_total"], str)


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw_qty,expected",
    [(1, "1"), (2, "2"), (10, "10"), (1.5, "1.5"), (0.25, "0.25")],
)
def test_bff_echoes_magento_quantities_verbatim(raw_qty, expected):
    """Magento compares qty strings strictly; a reformat silently kills a quote."""
    items = [{"sku": "CEMENTO-50", "qty": magento_qty(raw_qty)}]
    assert items[0]["qty"] == expected

    result = request_quote(magento_payload(items), FakeErp(_PRICES), now=_NOW)

    assert result["lines"][0]["qty"] == expected
    assert MagentoB2bQuoteValidator().validate(result, items, "neiva") == []


@pytest.mark.unit
def test_a_reformatted_quantity_is_rejected_by_the_consumer():
    """Negative control: the validator has teeth when the echo drifts."""
    items = [{"sku": "CEMENTO-50", "qty": "1"}]
    result = request_quote(magento_payload(items), FakeErp(_PRICES), now=_NOW)
    drifted = json.loads(json.dumps(result))
    drifted["lines"][0]["qty"] = "1.0"

    errors = MagentoB2bQuoteValidator().validate(drifted, items, "neiva")

    assert any("qty" in error for error in errors), errors


@pytest.mark.unit
def test_a_numeric_amount_is_rejected_by_the_consumer():
    """Negative control: float amounts would break Magento's decimal guarantee."""
    items = [{"sku": "CEMENTO-50", "qty": "1"}]
    result = request_quote(magento_payload(items), FakeErp(_PRICES), now=_NOW)
    numeric = json.loads(json.dumps(result))
    numeric["lines"][0]["unit_net_price"] = 38500.0

    errors = MagentoB2bQuoteValidator().validate(numeric, items, "neiva")

    assert any("unit_net_price" in error for error in errors), errors


@pytest.mark.unit
def test_a_quote_without_expiry_is_rejected_by_the_consumer():
    """Magento refuses a snapshot it cannot expire."""
    items = [{"sku": "CEMENTO-50", "qty": "1"}]
    result = request_quote(magento_payload(items), FakeErp(_PRICES), now=_NOW)
    del result["expires_at"]

    errors = MagentoB2bQuoteValidator().validate(result, items, "neiva")

    assert any("expires_at" in error for error in errors), errors


@pytest.mark.unit
def test_a_line_error_stops_the_whole_quote_at_the_consumer():
    """Item-level errors are visible, but Magento refuses a partial snapshot."""
    items = [
        {"sku": "CEMENTO-50", "qty": "1"},
        {"sku": "NO-EXISTE", "qty": "2"},
    ]

    result = request_quote(magento_payload(items), FakeErp(_PRICES), now=_NOW)

    assert result["lines"][1]["status"] == "error"
    errors = MagentoB2bQuoteValidator().validate(result, items, "neiva")
    assert any("line 1 status" in error for error in errors), errors
