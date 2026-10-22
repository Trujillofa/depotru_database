"""``catalog.quote_search`` price/IVA disambiguation (B0 contract).

The canonical price is the J3 ``AdmArticulos.ArticulosVenta`` value *before*
IVA; Magento is display-only and never a price/IVA basis. ``price_with_iva`` is
computed server-side with exact ``Decimal`` arithmetic (``ROUND_HALF_UP``),
never ``float``. Every decimal figure serializes as a canonical fixed-point
base-10 string preserving ``Decimal`` scale; only ``price_with_iva`` is an
integer COP JSON number.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Mapping, Optional

_ONE = Decimal("1")
_HUNDRED = Decimal("100")
_INTEGER = Decimal("1")


def to_decimal(value: Any) -> Optional[Decimal]:
    """Strictly parse ``value`` to a finite ``Decimal``; fail-closed otherwise.

    Accepts ``Decimal``, ``int``, and canonical base-10 strings. ``float`` is
    rejected (a binary float cannot be an exact base-10 source), as are bools,
    empty strings, and non-finite values.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, int):
        d = Decimal(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            d = Decimal(text)
        except InvalidOperation:
            return None
    else:
        return None
    if not d.is_finite():
        return None
    return d


def decimal_string(value: Decimal) -> str:
    """Canonical fixed-point base-10 rendering (``format(d, 'f')``)."""
    return format(value, "f")


def magento_price_string(value: Any) -> Optional[str]:
    """Canonical decimal string for the display-only Magento price.

    Magento's adapter yields ``float``; convert it to an exact base-10 string
    (``Decimal(str(value))``) without ever emitting a JSON number. Display-only:
    never a basis for price, IVA, or ``price_with_iva``.
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        d = value
    elif isinstance(value, int):
        d = Decimal(value)
    else:
        try:
            d = Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    if not d.is_finite():
        return None
    return format(d, "f")


def compute_price_with_iva(
    j3_price: Optional[Decimal], iva_rate: Optional[Decimal]
) -> Optional[int]:
    """Integer-COP IVA-inclusive price from exact ``Decimal`` HALF_UP arithmetic."""
    if j3_price is None or iva_rate is None:
        return None
    total = j3_price * (_ONE + iva_rate / _HUNDRED)
    return int(total.quantize(_INTEGER, rounding=ROUND_HALF_UP))


def price_with_iva_reason(
    j3_price: Optional[Decimal],
    line_id: Any,
    iva_rate: Optional[Decimal],
) -> Optional[str]:
    """Deterministic typed reason for a null ``price_with_iva`` (contract §7.2).

    Precedence (highest first): ``j3_price_missing``, ``line_not_found``,
    ``iva_rate_null``.
    """
    if j3_price is None:
        return "j3_price_missing"
    if line_id is None:
        return "line_not_found"
    if iva_rate is None:
        return "iva_rate_null"
    return None


def build_product(
    j3_row: Optional[Mapping[str, Any]] = None,
    magento: Optional[Mapping[str, Any]] = None,
) -> dict:
    """Build the closed product object from a J3 row and/or Magento match.

    ``j3_row`` is a raw DB row (keys ``sku``, ``name``, ``price``, ``iva_rate``,
    ``line_id``, ``website_qty``). ``magento`` contributes only ``name``,
    ``product_url``, and the separate display-only ``magento_price``; it never
    changes the J3 price, basis, IVA rate, or ``price_with_iva``.
    """
    mag = dict(magento or {})
    if j3_row is None:
        return {
            "sku": str(mag.get("sku") or ""),
            "name": str(mag.get("name") or ""),
            "price": None,
            "price_basis": "none",
            "price_includes_iva": None,
            "j3_price": None,
            "iva_rate": None,
            "price_with_iva": None,
            "price_with_iva_reason": "j3_price_missing",
            "magento_price": magento_price_string(mag.get("price")),
            "website_qty": None,
            "in_stock": None,
            "product_url": str(mag.get("product_url") or ""),
            "source": "magento",
        }

    sku = str(j3_row.get("sku") or "")
    j3_price = to_decimal(j3_row.get("price"))
    iva_rate = to_decimal(j3_row.get("iva_rate"))
    line_id = j3_row.get("line_id")
    website_qty = to_decimal(j3_row.get("website_qty"))

    reason = price_with_iva_reason(j3_price, line_id, iva_rate)
    pwi = None if reason is not None else compute_price_with_iva(j3_price, iva_rate)

    return {
        "sku": sku,
        "name": str(mag.get("name") or j3_row.get("name") or ""),
        "price": decimal_string(j3_price) if j3_price is not None else None,
        "price_basis": "J3",
        "price_includes_iva": False,
        "j3_price": decimal_string(j3_price) if j3_price is not None else None,
        "iva_rate": decimal_string(iva_rate) if iva_rate is not None else None,
        "price_with_iva": pwi,
        "price_with_iva_reason": reason,
        "magento_price": magento_price_string(mag.get("price")),
        "website_qty": decimal_string(website_qty) if website_qty is not None else None,
        "in_stock": (website_qty > 0) if website_qty is not None else None,
        "product_url": str(mag.get("product_url") or ""),
        "source": "j3+magento" if mag else "j3",
    }
