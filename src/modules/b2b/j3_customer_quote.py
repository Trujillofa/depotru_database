"""J3 customer-tariff quote (released contract for ``b2b.quote``).

Reads ``AdmPrecios.PreciosValor`` at ``Cantidad = 0`` for the staff-linked
``TercerosID`` tariff. Does not return warehouse qty (R12). Does not read
``ArticulosVenta`` / ``PreciosIncremento`` (R11). SKUs are allowlisted
literals; ``TercerosID`` and ``TarifasID`` are bound parameters.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Optional, Sequence

from business_analyzer.core.j3system_sales_warehouse import qualified_j3_table
from business_analyzer.core.website_warehouse_policy import sql_in_list
from modules.b2b.contracts import (
    SKU_MAX_LEN,
    ErpUnavailableError,
    tariff_is_missing,
    tariff_is_refused,
)

FORBIDDEN_SQL_FRAGMENTS: tuple[str, ...] = (
    "ArticulosVenta",
    "PreciosIncremento",
    "SaldoActual",
    "InvDetalleExistencias",
    "warehouse_qty",
    "qty_alm",
    "TercerosNombres",
    "TercerosCelular",
    "TercerosIdentificacion",
    "ArticulosCosto",
)


def parse_terceros_id(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def build_customer_tariff_sql() -> str:
    """One tercero's tariff. No name, phone, identification, or list price."""
    terceros = qualified_j3_table("AdmTerceros")
    tarifas = qualified_j3_table("AdmTarifas")
    return f"""
SELECT
    t.TercerosID AS terceros_id,
    t.TarifasID AS tarifas_id,
    tf.TarifasCodigo AS tarifa_codigo,
    tf.TarifasNombre AS tarifa_nombre
FROM {terceros} t
LEFT JOIN {tarifas} tf ON tf.TarifasID = t.TarifasID
WHERE t.TercerosID = %s
""".strip()


def build_customer_quote_lines_sql(*, skus: Sequence[str]) -> str:
    """Net tariff price at Cantidad=0. No stock join."""
    sku_sql = sql_in_list(skus, max_len=SKU_MAX_LEN)
    articulos = qualified_j3_table("AdmArticulos")
    precios = qualified_j3_table("AdmPrecios")
    return f"""
SELECT
    a.ArticulosCodigo AS sku,
    COUNT(*) AS price_rows,
    MIN(CAST(p.PreciosValor AS DECIMAL(18, 2))) AS price_min,
    MAX(CAST(p.PreciosValor AS DECIMAL(18, 2))) AS price_max
FROM {articulos} a
JOIN {precios} p ON p.ArticulosID = a.ArticulosID
WHERE p.TarifasID = %s
  AND p.Cantidad = 0
  AND a.ArticulosCodigo IN ({sku_sql})
GROUP BY a.ArticulosCodigo
""".strip()


def _as_decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    if isinstance(value, float):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _safe_skus(skus: Sequence[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in skus:
        sku = str(raw or "").strip()
        if not sku or sku.upper() in seen:
            continue
        try:
            sql_in_list([sku], max_len=SKU_MAX_LEN)
        except ValueError:
            continue
        seen.add(sku.upper())
        out.append(sku)
    return out


def _tariff_fields(row: dict[str, Any]) -> dict[str, str]:
    raw_id = row.get("tarifas_id")
    try:
        tariff_id = str(int(raw_id)) if raw_id is not None and raw_id != "" else ""
    except (TypeError, ValueError):
        tariff_id = str(raw_id or "").strip()
    return {
        "tariff_id": tariff_id,
        "tariff_code": str(row.get("tarifa_codigo") or "").strip(),
        "tariff_name": str(row.get("tarifa_nombre") or "").strip(),
    }


def fetch_customer_quote(
    db: Any,
    site: str,
    terceros_id: str | int,
    skus: Sequence[str],
) -> list[dict[str, Any]]:
    """Read tariff then prices. ``site`` is accepted for the protocol and unused
    for stock (R12). ``db.execute_query(sql, params)`` must already be connected.
    """
    del site  # pricing is per customer tariff, not per warehouse
    parsed_id = parse_terceros_id(terceros_id)
    if parsed_id is None:
        raise ErpUnavailableError("terceros_id_invalid")

    tariff_rows = db.execute_query(build_customer_tariff_sql(), (parsed_id,))
    if not isinstance(tariff_rows, list) or not tariff_rows:
        raise ErpUnavailableError("customer_not_found")
    tariff = dict(tariff_rows[0])
    fields = _tariff_fields(tariff)

    wanted = _safe_skus(skus)
    if not wanted:
        return []

    refused = tariff_is_refused(
        fields["tariff_id"], fields["tariff_code"], fields["tariff_name"]
    )
    if tariff_is_missing(fields["tariff_id"], fields["tariff_code"]) or refused:
        return [{"sku": sku, **fields} for sku in wanted]

    sql = build_customer_quote_lines_sql(skus=wanted)
    price_rows = db.execute_query(sql, (int(fields["tariff_id"]),))
    by_sku: dict[str, dict[str, Any]] = {}
    if isinstance(price_rows, list):
        for row in price_rows:
            if not isinstance(row, dict):
                continue
            key = str(row.get("sku") or "").strip().upper()
            if key:
                by_sku[key] = row

    out: list[dict[str, Any]] = []
    for sku in wanted:
        row = by_sku.get(sku.upper())
        payload: dict[str, Any] = {"sku": sku, **fields}
        if row is None:
            out.append(payload)
            continue
        try:
            price_count = int(row.get("price_rows") or 0)
        except (TypeError, ValueError):
            price_count = 0
        lo = _as_decimal(row.get("price_min"))
        hi = _as_decimal(row.get("price_max"))
        if price_count == 1 and lo is not None:
            payload["net_price"] = lo
        elif price_count > 1 and lo is not None and hi is not None and lo == hi:
            payload["net_price"] = lo
        out.append(payload)
    return out
