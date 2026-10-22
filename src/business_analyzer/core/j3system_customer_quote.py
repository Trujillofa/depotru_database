"""Read-only quotes for server-verified customers; see the B2 contract.

``B.ROT`` (PRODUCTOS DE BAJA ROTACION) is a virtual warehouse without a
physical site. Its stock is aggregated separately and never summed into a
site's physical quantity.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, NamedTuple, Optional, Sequence

from business_analyzer.core.j3system_sales_warehouse import qualified_j3_table
from business_analyzer.core.website_warehouse_policy import sql_in_list
from depotru_kernel.auth import Audience

UNIT, MAX_SKUS, SKU_MAX_LEN = "UND", 20, 40
VERIFIED_CUSTOMER_KEY = "verified_customer_terceros_id"
# ADMIN explicitly inherits all scopes in depotru_kernel.auth.
ALLOWED_AUDIENCES = frozenset({Audience.SALES, Audience.ADMIN})
ALLOWED_PARAM_KEYS = frozenset({"site", "skus"})
SITES = {"neiva": ("ALM", "BD6", "SUR", "DIS", "BOD"), "florencia": ("FLO",)}
# Virtual warehouse: it has no physical site, so it never joins a site list.
BAJA_ROTACION_WAREHOUSE = "B.ROT"
BAJA_ROTACION_NAME = "PRODUCTOS DE BAJA ROTACION"
# Never queried by this slice: not a site warehouse, not part of B.ROT.
EXCLUDED_WAREHOUSES = ("CON",)
# Physical warehouses may never include the virtual B.ROT warehouse or CON.
PHYSICAL_EXCLUDED_WAREHOUSES = (BAJA_ROTACION_WAREHOUSE, "CON")
STATUS_OK, STATUS_PARTIAL, STATUS_ERROR = "ok", "partial", "error"
STOCK_AVAILABLE = "available"
STOCK_ZERO = "zero_in_mapped_warehouses"
STOCK_UNKNOWN = "unknown"
BROT_PRESENT = "present"
BROT_ZERO = "zero"
BROT_UNKNOWN = "unknown"
COVERAGE_STATUS = "physical_warehouses_only"

VIRTUAL_WAREHOUSES: list[dict[str, Any]] = [
    {
        "code": BAJA_ROTACION_WAREHOUSE,
        "name": BAJA_ROTACION_NAME,
        "kind": "virtual",
        "site": None,
    },
]

_BROT_NOTE = (
    "B.ROT es una bodega virtual sin sede: su stock se reporta aparte, "
    "nunca se suma al stock de la sede y puede solaparse con el de las "
    "bodegas físicas; una venta sólo desde B.ROT exige confirmar con una "
    "persona el origen físico."
)


class QuoteRequest(NamedTuple):
    """Validated inputs; customer_id is server-only and never returned."""

    site: str
    skus: tuple[str, ...]
    customer_id: int


def stock_coverage(site: Optional[str]) -> Optional[dict[str, Any]]:
    """Site coverage plus the separately reported virtual warehouse."""
    if site is None:
        return None
    if site not in SITES:
        return None
    coverage: dict[str, Any] = {
        "status": COVERAGE_STATUS,
        "mapped_warehouses": list(SITES[site]),
        "virtual_warehouses": [dict(w) for w in VIRTUAL_WAREHOUSES],
        "virtual_warehouses_reported_separately": True,
        "overlap_possible": True,
        "note": _BROT_NOTE,
    }
    return coverage


def error_payload(
    reason: str, *, site: Optional[str] = None, tariff: Any = None
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": STATUS_ERROR,
        "reason": reason,
        "price_includes_iva": False,
        "lines": [],
    }
    if site is not None:
        body.update(site=site, stock_coverage=stock_coverage(site))
    if tariff is not None:
        body["tariff"] = dict(tariff)
    return body


def _positive_id(value: Any) -> Optional[int]:
    """Accept only an exact positive int or an ASCII digit string."""
    if isinstance(value, str):
        raw = value.strip()
        if not (raw.isascii() and raw.isdigit() and len(raw) <= 10):
            return None
        candidate = int(raw)
    elif isinstance(value, bool) or not isinstance(value, int):
        return None
    else:
        candidate = value
    return candidate if 0 < candidate <= 2147483647 else None


def _parse_skus(value: Any) -> tuple[str, ...] | str:
    if not isinstance(value, (str, list)):
        return "skus_required"
    raw = [value] if isinstance(value, str) else value
    if not raw:
        return "skus_required"
    if len(raw) > MAX_SKUS:
        return "too_many_skus"
    if any(not isinstance(s, str) or not s.strip().isascii() for s in raw):
        return "invalid_sku"
    skus = tuple({s.strip().upper(): s.strip() for s in raw}.values())
    try:
        sql_in_list(skus, max_len=SKU_MAX_LEN)
    except ValueError:
        return "invalid_sku"
    return skus


def parse_quote_request(
    params: Any, extras: Any
) -> tuple[Optional[QuoteRequest], Optional[dict[str, Any]]]:
    if not isinstance(params, Mapping) or set(params) - ALLOWED_PARAM_KEYS:
        return None, error_payload("unexpected_parameters")
    raw = extras.get(VERIFIED_CUSTOMER_KEY) if isinstance(extras, Mapping) else None
    customer = _positive_id(raw)
    if customer is None:
        return None, error_payload("verified_customer_required")
    raw_site = params.get("site")
    site = raw_site.strip().lower() if isinstance(raw_site, str) else None
    if site is None:
        return None, error_payload("site_invalid")
    if site not in SITES:
        return None, error_payload("site_invalid")
    skus = _parse_skus(params.get("skus"))
    if isinstance(skus, str):
        return None, error_payload(skus, site=site)
    return QuoteRequest(site, skus, customer), None


def build_customer_tariff_sql() -> str:
    """Bound server identity; TOP 2 distinguishes absent/unique/duplicate."""
    return f"""
SELECT TOP 2 t.TarifasID AS tarifas_id, tf.TarifasCodigo AS tarifa_codigo,
    tf.TarifasNombre AS tarifa_nombre
FROM {qualified_j3_table("AdmTerceros")} t
LEFT JOIN {qualified_j3_table("AdmTarifas")} tf ON tf.TarifasID = t.TarifasID
WHERE t.TercerosID = %s
""".strip()


def _warehouse_set(codes: Sequence[str], *, virtual: bool = False) -> str:
    """Render a warehouse IN-list with physical/virtual allowlists."""
    for code in codes:
        if virtual:
            if code != BAJA_ROTACION_WAREHOUSE:
                raise ValueError(f"Only B.ROT is allowed in the virtual set: {code}")
        elif code in PHYSICAL_EXCLUDED_WAREHOUSES:
            raise ValueError(f"Excluded warehouse in physical set: {code}")
    rendered: str = sql_in_list(codes)
    return rendered


def build_customer_quote_lines_sql(*, site: str, skus: Sequence[str]) -> str:
    """Bound verified tariff; validated literal SKU and warehouse sets."""
    sku_list = list(skus)
    if not 1 <= len(sku_list) <= MAX_SKUS:
        raise ValueError("Invalid SKU count")
    sku_set = sql_in_list(sku_list, max_len=SKU_MAX_LEN)
    warehouse_set = _warehouse_set(SITES[site])
    baja_rotacion_set = _warehouse_set((BAJA_ROTACION_WAREHOUSE,), virtual=True)
    return f"""
WITH targets AS (
    SELECT TOP {MAX_SKUS + 1} ArticulosID, ArticulosCodigo, ArticulosNombre
    FROM {qualified_j3_table("AdmArticulos")}
    WHERE ArticulosCodigo IN ({sku_set})
), stock_rows AS (
    SELECT e.ArticulosID, d.Ano, d.SaldoActual
    FROM {qualified_j3_table("InvDetalleExistencias")} d
    JOIN {qualified_j3_table("InvExistencias")} e ON e.ExistenciasID = d.ExistenciasID
    JOIN {qualified_j3_table("AdmAlmacen")} al ON al.AlmacenID = d.AlmacenID
    WHERE e.ArticulosID IN (SELECT ArticulosID FROM targets)
      AND al.AlmacenCodigo IN ({warehouse_set})
), baja_rotacion_rows AS (
    SELECT e.ArticulosID, d.Ano, d.SaldoActual
    FROM {qualified_j3_table("InvDetalleExistencias")} d
    JOIN {qualified_j3_table("InvExistencias")} e ON e.ExistenciasID = d.ExistenciasID
    JOIN {qualified_j3_table("AdmAlmacen")} al ON al.AlmacenID = d.AlmacenID
    WHERE e.ArticulosID IN (SELECT ArticulosID FROM targets)
      AND al.AlmacenCodigo IN ({baja_rotacion_set})
)
SELECT TOP {MAX_SKUS + 1} a.ArticulosCodigo AS sku, a.ArticulosNombre AS name,
    pr.price_rows, pr.price_min, pr.price_max, st.qty, br.baja_rotacion
FROM targets a
LEFT JOIN (
    SELECT p.ArticulosID, COUNT(*) AS price_rows,
      CASE WHEN COUNT(*) = COUNT(p.PreciosValor)
        THEN MIN(CAST(p.PreciosValor AS DECIMAL(18,2))) END AS price_min,
      MAX(CAST(p.PreciosValor AS DECIMAL(18,2))) AS price_max
    FROM {qualified_j3_table("AdmPrecios")} p
    WHERE p.TarifasID = %s AND p.Cantidad = 0
      AND p.ArticulosID IN (SELECT ArticulosID FROM targets)
    GROUP BY p.ArticulosID
) pr ON pr.ArticulosID = a.ArticulosID
LEFT JOIN (
    SELECT ArticulosID,
      CASE WHEN COUNT(*) = COUNT(SaldoActual) AND MIN(SaldoActual) >= 0
        THEN SUM(CAST(SaldoActual AS DECIMAL(18,4))) END AS qty
    FROM stock_rows WHERE Ano = (SELECT MAX(Ano) FROM stock_rows)
    GROUP BY ArticulosID
) st ON st.ArticulosID = a.ArticulosID
LEFT JOIN (
    SELECT ArticulosID,
      CASE WHEN COUNT(*) = COUNT(SaldoActual) AND MIN(SaldoActual) >= 0
        THEN SUM(CAST(SaldoActual AS DECIMAL(18,4))) END AS baja_rotacion
    FROM baja_rotacion_rows WHERE Ano = (SELECT MAX(Ano) FROM baja_rotacion_rows)
    GROUP BY ArticulosID
) br ON br.ArticulosID = a.ArticulosID
""".strip()


def tariff_decision(row: Mapping[str, Any]) -> Optional[str]:
    tariff_id = _positive_id(row.get("tarifas_id"))
    codigo = str(row.get("tarifa_codigo") or "").strip()
    nombre = str(row.get("tarifa_nombre") or "").strip().upper()
    if tariff_id == 6 or codigo == "006" or nombre == "AL COSTO":
        return "tariff_refused"
    if tariff_id is None or not (codigo or nombre):
        return "tariff_missing"
    return None


def _as_float(value: Any) -> Optional[float]:
    try:
        number = float(value) if not isinstance(value, bool) else -1
        return number if math.isfinite(number) and number >= 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _row_float(row: Optional[Mapping[str, Any]], key: str) -> Optional[float]:
    """Read one optional numeric column from an article row."""
    if row is None:
        return None
    return _as_float(row.get(key))


def _build_lines(
    request: QuoteRequest, rows: Sequence[Mapping[str, Any]]
) -> tuple[Optional[str], list[dict[str, Any]]]:
    by_sku: dict[str, Mapping[str, Any]] = {}
    for source_row in rows:
        key = str(source_row.get("sku") or "").strip().upper()
        if key not in {sku.upper() for sku in request.skus} or key in by_sku:
            return "erp_unavailable", []
        by_sku[key] = source_row
    lines: list[dict[str, Any]] = []
    first_reason: Optional[str] = None
    reason: Optional[str]
    for sku in request.skus:
        mapped: Optional[Mapping[str, Any]] = by_sku.get(sku.upper())
        article_row: Optional[Mapping[str, Any]] = mapped
        qty = _row_float(article_row, "qty")
        baja_rotacion = _row_float(article_row, "baja_rotacion")
        name = str(article_row.get("name") or "") if article_row is not None else ""
        line: dict[str, Any] = {
            "sku": sku,
            "name": name,
            "qty": qty,
            "stock_status": STOCK_UNKNOWN,
            "baja_rotacion": baja_rotacion,
            "baja_rotacion_status": BROT_UNKNOWN,
            "requires_physical_origin_confirmation": False,
            "price": None,
        }
        if qty is not None:
            line["stock_status"] = STOCK_AVAILABLE if qty > 0 else STOCK_ZERO
        if baja_rotacion is not None:
            brot_status = BROT_PRESENT if baja_rotacion > 0 else BROT_ZERO
            line["baja_rotacion_status"] = brot_status
        # B.ROT may overlap the physical warehouses and has no site. Any
        # positive B.ROT stock requires human confirmation of the physical
        # origin; the site's own availability stays independent.
        if baja_rotacion is not None and baja_rotacion > 0:
            line["requires_physical_origin_confirmation"] = True
        reason = "article_not_found"
        if article_row is not None:
            low = _row_float(article_row, "price_min")
            high = _row_float(article_row, "price_max")
            count = _row_float(article_row, "price_rows")
            if count is None or count < 1 or low is None:
                reason = "price_missing"
            elif not count.is_integer() or high is None or low != high:
                reason = "price_ambiguous"
            else:
                reason = None
                line["price"] = low
        line["status"] = reason or STATUS_OK
        lines.append(line)
        first_reason = first_reason or reason
    return first_reason, lines


def _query(db: Any, sql: str, params: tuple, cap: int) -> Any:
    """Fail closed without driver text or unbounded result processing."""
    try:
        rows = db.execute_query(sql, params)
        if isinstance(rows, list) and len(rows) <= cap:
            return rows if all(isinstance(row, Mapping) for row in rows) else None
    except Exception:  # noqa: BLE001 — no driver messages or logging
        pass
    return None


def fetch_customer_quote(db: Any, request: QuoteRequest) -> dict[str, Any]:
    site = request.site
    customers = _query(db, build_customer_tariff_sql(), (request.customer_id,), 2)
    if customers is None:
        return error_payload("erp_unavailable", site=site)
    reason: Optional[str]
    if len(customers) != 1:
        reason = "customer_ambiguous" if customers else "customer_not_found"
        return error_payload(reason, site=site)
    customer = customers[0]
    tariff = {
        "codigo": str(customer.get("tarifa_codigo") or "").strip(),
        "nombre": str(customer.get("tarifa_nombre") or "").strip(),
    }
    reason = tariff_decision(customer)
    if reason:
        return error_payload(reason, site=site, tariff=tariff)
    sql = build_customer_quote_lines_sql(site=site, skus=request.skus)
    rows = _query(db, sql, (_positive_id(customer.get("tarifas_id")),), MAX_SKUS + 1)
    if rows is None or len(rows) > len(request.skus):
        return error_payload("erp_unavailable", site=site, tariff=tariff)
    reason, lines = _build_lines(request, rows)
    if reason is not None and reason == "erp_unavailable":
        return error_payload(reason, site=site, tariff=tariff)
    quoted = sum(line["status"] == STATUS_OK for line in lines)
    status = STATUS_OK if quoted == len(lines) else STATUS_PARTIAL
    if not quoted:
        status = STATUS_ERROR
    body: dict[str, Any] = {
        "status": status,
        "site": site,
        "unit": UNIT,
        "price_includes_iva": False,
        "tariff": tariff,
        "stock_coverage": stock_coverage(site),
        "lines": lines,
    }
    if status != STATUS_OK:
        body["reason"] = reason
    return body
