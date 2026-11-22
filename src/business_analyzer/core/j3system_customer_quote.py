"""Customer quote: list price, UND, and stock at the site warehouses.

A quote exists when the ERP returns a price and the stock of each warehouse
for that site. ``PreciosValor`` is the net price (before IVA).
``PreciosIncremento`` and the mostrador price are not applied. Cost and
margin columns are never selected.

A tercero without any ``TarifasID`` (consumidor final) is quoted at the
public store price: ``AdmArticulos.ArticulosVenta``, the same net public
reference price the storefront catalog uses. The response marks that
fallback explicitly with ``tarifa_origen="publica"`` and a ``tarifa`` payload
without an ERP tariff id (``id`` is null; no tariff row is invented). A
refused tariff (006 AL COSTO) and a dangling ``TarifasID`` still fail closed.

Neiva stock is reported per warehouse (ALM, BD6, SUR, DIS, BOD). Florencia
is FLO only. The sell unit is the article itself: UND.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from business_analyzer.core.j3system_sales_warehouse import qualified_j3_table
from business_analyzer.core.website_warehouse_policy import sql_in_list

UNIT = "UND"
MAX_SKUS = 20
SKU_MAX_LEN = 40

NEIVA_WAREHOUSES: tuple[str, ...] = ("ALM", "BD6", "SUR", "DIS", "BOD")
FLORENCIA_WAREHOUSES: tuple[str, ...] = ("FLO",)
SITES: dict[str, tuple[str, ...]] = {
    "neiva": NEIVA_WAREHOUSES,
    "florencia": FLORENCIA_WAREHOUSES,
}

# TarifasID 6 is 006 AL COSTO. It is not a sell price.
REFUSED_TARIFF_IDS = frozenset({6})
REFUSED_TARIFF_CODES = frozenset({"006"})
REFUSED_TARIFF_NAMES = frozenset({"AL COSTO"})

# Public-tariff fallback (consumidor final without TarifasID).
CUSTOMER_TARIFF_ORIGEN = "tercero"
PUBLIC_TARIFF_ORIGEN = "publica"
PUBLIC_TARIFF_CODE = "PUBLICA"
PUBLIC_TARIFF_NAME = "PRECIO PUBLICO (RESPALDO)"

FORBIDDEN_SQL_FRAGMENTS: tuple[str, ...] = (
    "ArticulosCosto",
    "ArticulosUltmoCosto",
    "ArticulosMargen",
    "UltimoCostoCompra",
    "CostoInicial",
    "CostoDepre",
    "ValorCosto",
    "ListadoPreciosCosto",
    "CostoSinIva",
    "CostoMasIva",
    "CostoAnterior",
    "PreciosIncremento",
    "ArticulosVenta",
    "TercerosNombres",
    "TercerosCelular",
    "TercerosIdentificacion",
)


@dataclass(frozen=True)
class QuoteRequest:
    """Validated tool inputs. ``skus`` are exact article codes."""

    terceros_id: int
    site: str
    skus: tuple[str, ...]


def warehouses_for_site(site: str) -> tuple[str, ...]:
    """Return the sellable warehouse codes for ``neiva`` or ``florencia``."""
    try:
        return SITES[site]
    except KeyError as exc:
        raise ValueError(f"Unknown site: {site}") from exc


def _qty_alias(code: str) -> str:
    return "qty_" + code.lower().replace(".", "_")


def _fail(
    reason: str,
    *,
    terceros_id: Optional[int] = None,
    site: Optional[str] = None,
    tarifa: Optional[dict[str, Any]] = None,
    lines: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": "error",
        "reason": reason,
        "price_includes_iva": False,
        "lines": list(lines or []),
    }
    if terceros_id is not None:
        body["terceros_id"] = terceros_id
    if site is not None:
        body["site"] = site
    if tarifa is not None:
        body["tarifa"] = tarifa
    return body


def _parse_terceros_id(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def _parse_skus(value: Any) -> tuple[str, ...] | str:
    """Return a sku tuple, or an error reason string."""
    if isinstance(value, str):
        raw_items: list[Any] = [value]
    elif isinstance(value, (list, tuple)):
        raw_items = list(value)
    else:
        return "skus_required"
    skus: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        sku = str(item or "").strip()
        if not sku:
            continue
        key = sku.upper()
        if key in seen:
            continue
        seen.add(key)
        skus.append(sku)
    if not skus:
        return "skus_required"
    if len(skus) > MAX_SKUS:
        return "too_many_skus"
    try:
        sql_in_list(skus, max_len=SKU_MAX_LEN)
    except ValueError:
        return "invalid_sku"
    return tuple(skus)


def parse_quote_request(
    params: Mapping[str, Any],
) -> tuple[Optional[QuoteRequest], Optional[dict[str, Any]]]:
    """Validate inputs. No ERP call."""
    terceros_id = _parse_terceros_id(params.get("terceros_id"))
    if terceros_id is None:
        return None, _fail("terceros_id_required")
    site = str(params.get("site") or "").strip().lower()
    if site not in SITES:
        return None, _fail("site_invalid", terceros_id=terceros_id)
    skus = _parse_skus(params.get("skus"))
    if isinstance(skus, str):
        return None, _fail(skus, terceros_id=terceros_id, site=site)
    return QuoteRequest(terceros_id=terceros_id, site=site, skus=skus), None


def build_customer_tariff_sql() -> str:
    """One tercero's tariff. No name, phone, or identification."""
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


def _stock_join_parts(site: str) -> tuple[str, str]:
    """``(outer qty columns, LEFT JOIN clause)`` for the site warehouses.

    Shared by the tariff quote and the public fallback quote so both report
    identical per-warehouse stock.
    """
    warehouses = warehouses_for_site(site)
    warehouse_sql = sql_in_list(warehouses)
    detalle = qualified_j3_table("InvDetalleExistencias")
    existencias = qualified_j3_table("InvExistencias")
    almacen = qualified_j3_table("AdmAlmacen")

    qty_sums: list[str] = []
    qty_outer: list[str] = []
    for code in warehouses:
        quoted = sql_in_list([code])
        alias = _qty_alias(code)
        qty_sums.append(
            "SUM(CASE WHEN al.AlmacenCodigo = "
            f"{quoted} THEN CAST(d.SaldoActual AS DECIMAL(18, 4)) "
            f"ELSE 0 END) AS {alias}"
        )
        qty_outer.append(f"CAST(ISNULL(st.{alias}, 0) AS DECIMAL(18, 4)) AS {alias}")
    qty_sum_sql = ",\n        ".join(qty_sums)
    qty_outer_sql = ",\n    ".join(qty_outer)
    join_sql = (
        f"LEFT JOIN (\n"
        f"    SELECT\n"
        f"        e.ArticulosID,\n"
        f"        {qty_sum_sql}\n"
        f"    FROM {detalle} d\n"
        f"    JOIN {existencias} e ON e.ExistenciasID = d.ExistenciasID\n"
        f"    JOIN {almacen} al ON al.AlmacenID = d.AlmacenID\n"
        f"    WHERE d.Ano = (SELECT MAX(Ano) FROM {detalle})\n"
        f"      AND CAST(d.SaldoActual AS DECIMAL(18, 4)) >= 0\n"
        f"      AND al.AlmacenCodigo IN ({warehouse_sql})\n"
        f"    GROUP BY e.ArticulosID\n"
        f") st ON st.ArticulosID = a.ArticulosID"
    )
    return qty_outer_sql, join_sql


def build_customer_quote_lines_sql(*, site: str, skus: Sequence[str]) -> str:
    """Net list price and per-warehouse qty for exact SKUs.

    ``TarifasID`` is the only bound parameter. SKUs and warehouse codes are
    validated literals.
    """
    sku_sql = sql_in_list(skus, max_len=SKU_MAX_LEN)
    articulos = qualified_j3_table("AdmArticulos")
    precios = qualified_j3_table("AdmPrecios")
    qty_outer_sql, stock_join_sql = _stock_join_parts(site)

    return f"""
SELECT
    a.ArticulosCodigo AS sku,
    a.ArticulosNombre AS name,
    ISNULL(pr.price_rows, 0) AS price_rows,
    pr.price_min,
    pr.price_max,
    {qty_outer_sql}
FROM {articulos} a
LEFT JOIN (
    SELECT
        p.ArticulosID,
        COUNT(*) AS price_rows,
        MIN(CAST(p.PreciosValor AS DECIMAL(18, 2))) AS price_min,
        MAX(CAST(p.PreciosValor AS DECIMAL(18, 2))) AS price_max
    FROM {precios} p
    WHERE p.TarifasID = %s
      AND p.Cantidad = 0
    GROUP BY p.ArticulosID
) pr ON pr.ArticulosID = a.ArticulosID
{stock_join_sql}
WHERE a.ArticulosCodigo IN ({sku_sql})
""".strip()


def build_public_quote_lines_sql(*, site: str, skus: Sequence[str]) -> str:
    """Public store price and per-warehouse qty for exact SKUs.

    Fallback quote for a tercero without ``TarifasID``: the price is
    ``AdmArticulos.ArticulosVenta``, the same net public reference price the
    storefront catalog quotes (``quote_search`` basis), before IVA. No
    ``AdmPrecios`` read and no customer tariff is invented. A null
    ``ArticulosVenta`` surfaces as ``price_missing`` per line, fail-closed.
    """
    sku_sql = sql_in_list(skus, max_len=SKU_MAX_LEN)
    articulos = qualified_j3_table("AdmArticulos")
    qty_outer_sql, stock_join_sql = _stock_join_parts(site)

    return f"""
SELECT
    a.ArticulosCodigo AS sku,
    a.ArticulosNombre AS name,
    1 AS price_rows,
    CAST(a.ArticulosVenta AS DECIMAL(18, 2)) AS price_min,
    CAST(a.ArticulosVenta AS DECIMAL(18, 2)) AS price_max,
    {qty_outer_sql}
FROM {articulos} a
{stock_join_sql}
WHERE a.ArticulosCodigo IN ({sku_sql})
""".strip()


def tariff_is_absent(row: Mapping[str, Any]) -> bool:
    """True when the tercero carries no ``TarifasID`` at all.

    NULL, empty, unparseable, or 0. A set-but-dangling id (no ``AdmTarifas``
    row) is not absent: it still fails closed as ``tariff_missing``.
    """
    raw_id = row.get("tarifas_id")
    if raw_id is None or raw_id == "":
        return True
    try:
        return int(raw_id) == 0
    except (TypeError, ValueError):
        return True


def tariff_decision(row: Mapping[str, Any]) -> Optional[str]:
    """Return a failure reason, or None when the list may be quoted."""
    raw_id = row.get("tarifas_id")
    if raw_id is None or raw_id == "":
        return "tariff_missing"
    try:
        tariff_id = int(raw_id)
    except (TypeError, ValueError):
        return "tariff_missing"
    codigo = str(row.get("tarifa_codigo") or "").strip()
    nombre = str(row.get("tarifa_nombre") or "").strip().upper()
    if tariff_id == 0:
        return "tariff_missing"
    if (
        tariff_id in REFUSED_TARIFF_IDS
        or codigo in REFUSED_TARIFF_CODES
        or nombre in REFUSED_TARIFF_NAMES
    ):
        return "tariff_refused"
    if not codigo and not nombre:
        return "tariff_missing"
    return None


def tarifa_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    raw_id = row.get("tarifas_id")
    tariff_id: Optional[int]
    try:
        tariff_id = int(raw_id) if raw_id is not None and raw_id != "" else None
    except (TypeError, ValueError):
        tariff_id = None
    return {
        "id": tariff_id,
        "codigo": str(row.get("tarifa_codigo") or "").strip(),
        "nombre": str(row.get("tarifa_nombre") or "").strip(),
    }


def _as_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _same_money(left: Any, right: Any) -> bool:
    a = _as_float(left)
    b = _as_float(right)
    if a is None or b is None:
        return False
    return abs(a - b) <= 0.01


def _warehouses_from_row(row: Mapping[str, Any], site: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for code in warehouses_for_site(site):
        qty = _as_float(row.get(_qty_alias(code)))
        out.append({"code": code, "qty": 0.0 if qty is None else qty})
    return out


def _assemble_lines(
    request: QuoteRequest,
    rows: Sequence[Mapping[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    by_sku: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        key = str(row.get("sku") or "").strip().upper()
        if not key:
            continue
        if key in by_sku:
            return "erp_unavailable", []
        by_sku[key] = row

    lines: list[dict[str, Any]] = []
    first_reason: Optional[str] = None
    for sku in request.skus:
        row = by_sku.get(sku.upper())
        if row is None:
            reason = "article_not_found"
            lines.append({"sku": sku, "status": reason, "unit": UNIT})
        else:
            reason, line = _line_from_row(sku, row, request.site)
            lines.append(line)
        if reason is not None and first_reason is None:
            first_reason = reason
    return first_reason or "ok", lines


def _line_from_row(
    requested_sku: str,
    row: Mapping[str, Any],
    site: str,
) -> tuple[Optional[str], dict[str, Any]]:
    sku = str(row.get("sku") or requested_sku).strip()
    name = str(row.get("name") or "").strip()
    warehouses = _warehouses_from_row(row, site)
    try:
        price_rows = int(row.get("price_rows") or 0)
    except (TypeError, ValueError):
        price_rows = 0
    price_min = row.get("price_min")
    price_max = row.get("price_max")
    base = {
        "sku": sku,
        "name": name,
        "unit": UNIT,
        "warehouses": warehouses,
    }
    if price_rows <= 0 or _as_float(price_min) is None:
        return "price_missing", {**base, "status": "price_missing", "price": None}
    if price_rows > 1 and not _same_money(price_min, price_max):
        return "price_ambiguous", {
            **base,
            "status": "price_ambiguous",
            "price": None,
        }
    return None, {**base, "status": "ok", "price": _as_float(price_min)}


def public_tarifa_payload() -> dict[str, Any]:
    """The explicit public-fallback tariff marker. No ERP tariff is invented."""
    return {"id": None, "codigo": PUBLIC_TARIFF_CODE, "nombre": PUBLIC_TARIFF_NAME}


def _fetch_public_fallback_quote(db: Any, request: QuoteRequest) -> dict[str, Any]:
    """Quote at the public store price because the tercero has no tariff.

    Same fail-closed shape as the tariff quote: a price-read failure is
    ``erp_unavailable`` with the public tariff already resolved, and per-line
    problems (``article_not_found``, ``price_missing``) fail the quote.
    """
    tarifa = public_tarifa_payload()

    def _fail_public(reason: str) -> dict[str, Any]:
        return _fail(
            reason,
            terceros_id=request.terceros_id,
            site=request.site,
            tarifa=tarifa,
        )

    try:
        line_rows = db.execute_query(
            build_public_quote_lines_sql(site=request.site, skus=request.skus),
            (),
        )
    except Exception:  # noqa: BLE001 — fail closed; do not leak the driver message
        return _fail_public("erp_unavailable")
    if not isinstance(line_rows, list):
        return _fail_public("erp_unavailable")
    mappings = [row for row in line_rows if isinstance(row, Mapping)]
    if len(mappings) != len(line_rows):
        return _fail_public("erp_unavailable")
    line_reason, lines = _assemble_lines(request, mappings)
    if line_reason == "erp_unavailable":
        return _fail_public("erp_unavailable")
    body: dict[str, Any] = {
        "status": "ok" if line_reason == "ok" else "error",
        "terceros_id": request.terceros_id,
        "site": request.site,
        "tarifa": tarifa,
        "tarifa_origen": PUBLIC_TARIFF_ORIGEN,
        "price_includes_iva": False,
        "lines": lines,
    }
    if line_reason != "ok":
        body["reason"] = line_reason
    return body


def fetch_customer_quote(db: Any, request: QuoteRequest) -> dict[str, Any]:
    """Read one quote. ``db.execute_query`` must already be connected.

    A tercero without any ``TarifasID`` is quoted at the public store price
    (``ArticulosVenta``) with ``tarifa_origen="publica"``. A refused tariff
    returns an error and does not read prices. A failure of the price and
    stock read returns ``erp_unavailable`` and keeps the tariff already
    resolved. A failure of the customer read is raised for the tool handler
    to turn into ``erp_unavailable``.
    """
    customer_rows = db.execute_query(
        build_customer_tariff_sql(),
        (request.terceros_id,),
    )
    if not isinstance(customer_rows, list):
        return _fail(
            "erp_unavailable",
            terceros_id=request.terceros_id,
            site=request.site,
        )
    if len(customer_rows) == 0:
        return _fail(
            "customer_not_found",
            terceros_id=request.terceros_id,
            site=request.site,
        )
    if len(customer_rows) > 1:
        return _fail(
            "customer_ambiguous",
            terceros_id=request.terceros_id,
            site=request.site,
        )
    customer = customer_rows[0]
    if not isinstance(customer, Mapping):
        return _fail(
            "erp_unavailable",
            terceros_id=request.terceros_id,
            site=request.site,
        )
    tarifa = tarifa_payload(customer)
    reason = tariff_decision(customer)
    if reason:
        if reason == "tariff_missing" and tariff_is_absent(customer):
            return _fetch_public_fallback_quote(db, request)
        return _fail(
            reason,
            terceros_id=request.terceros_id,
            site=request.site,
            tarifa=tarifa,
        )

    try:
        line_rows = db.execute_query(
            build_customer_quote_lines_sql(site=request.site, skus=request.skus),
            (int(customer["tarifas_id"]),),
        )
    except Exception:  # noqa: BLE001 — fail closed; do not leak the driver message
        return _fail(
            "erp_unavailable",
            terceros_id=request.terceros_id,
            site=request.site,
            tarifa=tarifa,
        )
    if not isinstance(line_rows, list):
        return _fail(
            "erp_unavailable",
            terceros_id=request.terceros_id,
            site=request.site,
            tarifa=tarifa,
        )
    mappings = [row for row in line_rows if isinstance(row, Mapping)]
    if len(mappings) != len(line_rows):
        return _fail(
            "erp_unavailable",
            terceros_id=request.terceros_id,
            site=request.site,
            tarifa=tarifa,
        )
    line_reason, lines = _assemble_lines(request, mappings)
    if line_reason == "erp_unavailable":
        return _fail(
            "erp_unavailable",
            terceros_id=request.terceros_id,
            site=request.site,
            tarifa=tarifa,
        )
    body: dict[str, Any] = {
        "status": "ok" if line_reason == "ok" else "error",
        "terceros_id": request.terceros_id,
        "site": request.site,
        "tarifa": tarifa,
        "tarifa_origen": CUSTOMER_TARIFF_ORIGEN,
        "price_includes_iva": False,
        "lines": lines,
    }
    if line_reason != "ok":
        body["reason"] = line_reason
    return body
