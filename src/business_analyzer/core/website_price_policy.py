"""J3 ArticulosVenta → Magento list price (IVA-inclusive COP).

Magento storefront stores the customer-facing number. Live 2026-09-10:
SKU 0010170536 J3 venta 216000 → PDP 257040 = 216000 × 1.19.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable, List, Mapping, Optional, Sequence

IVA_RATE = Decimal("1.19")
DRIFT_THRESHOLD = Decimal("1")


def _as_decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return None


def target_price(venta: Any) -> Optional[int]:
    """Return Magento COP list price, or None if the J3 venta must be skipped."""
    amount = _as_decimal(venta)
    if amount is None or amount <= 0:
        return None
    return int((amount * IVA_RATE).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def should_update(magento_price: Any, target: Any) -> bool:
    """True when Magento list price differs from target by >= 1 COP."""
    current = _as_decimal(magento_price)
    wanted = _as_decimal(target)
    if current is None or wanted is None:
        return False
    return abs(current - wanted) >= DRIFT_THRESHOLD


def build_price_payload(
    *,
    j3_rows: Sequence[Mapping[str, Any]],
    magento_rows: Sequence[Mapping[str, Any]],
) -> List[dict]:
    """Join J3 venta to Magento prices; keep only SKUs that must change.

    Skips: missing Magento SKU, missing/non-positive J3 venta, SKUs with
    special_price > 0, rows already within 1 COP of target.
    """
    magento_by_sku = {}
    for row in magento_rows:
        sku = str(row.get("sku") or "").strip()
        if sku:
            magento_by_sku[sku] = row

    payload: List[dict] = []
    for row in j3_rows:
        sku = str(row.get("sku") or "").strip()
        if not sku:
            continue
        magento = magento_by_sku.get(sku)
        if magento is None:
            continue
        special = _as_decimal(magento.get("special_price"))
        if special is not None and special > 0:
            continue
        wanted = target_price(row.get("venta"))
        if wanted is None:
            continue
        current = magento.get("price")
        if not should_update(current, wanted):
            continue
        current_dec = _as_decimal(current) or Decimal("0")
        payload.append(
            {
                "sku": sku,
                "j3_venta": _as_decimal(row.get("venta")),
                "magento_price": current_dec,
                "target": wanted,
                "delta": wanted - int(current_dec),
            }
        )
    payload.sort(key=lambda item: -abs(int(item["delta"])))
    return payload


def build_j3_venta_sql(*, j3_database: Optional[str] = None) -> str:
    """Select SKU + list venta from J3 AdmArticulos."""
    from business_analyzer.core.j3system_sales_warehouse import qualified_j3_table

    articulos = qualified_j3_table("AdmArticulos", j3_database)
    return (
        "SELECT a.ArticulosCodigo AS sku, a.ArticulosVenta AS venta "
        f"FROM {articulos} a "
        "WHERE a.ArticulosCodigo IS NOT NULL "
        "AND LTRIM(RTRIM(a.ArticulosCodigo)) <> ''"
    )


def parse_magento_price_tsv(text: str) -> List[dict]:
    """Parse `sku\\tprice\\tspecial_price` rows from Magento mysql -N."""
    rows: List[dict] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        sku = parts[0].strip()
        price = parts[1].strip()
        special = parts[2].strip() if len(parts) > 2 else ""
        if not sku:
            continue
        rows.append(
            {
                "sku": sku,
                "price": price,
                "special_price": None
                if special in ("", "NULL", "None", "\\N")
                else special,
            }
        )
    return rows


def payload_stats(payload: Iterable[Mapping[str, Any]]) -> dict:
    """Summary counts for a dry-run log line."""
    rows = list(payload)
    deltas = [abs(int(r.get("delta") or 0)) for r in rows]
    return {
        "payload_skus": len(rows),
        "min_abs_delta": min(deltas) if deltas else 0,
        "max_abs_delta": max(deltas) if deltas else 0,
        "median_abs_delta": sorted(deltas)[len(deltas) // 2] if deltas else 0,
    }
