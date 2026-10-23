"""J3System website stock totals using the warehouse allowlist (#182).

Sums ``InvDetalleExistencias.SaldoActual`` per SKU only for almacenes in
``website_warehouse_allowlist()``. Optionally returns per-warehouse breakdown
and the qty that would be excluded by the denylist.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_sales_warehouse import qualified_j3_table
from business_analyzer.core.website_warehouse_policy import (
    WEBSITE_WAREHOUSE_DENYLIST,
    sql_in_list,
    website_warehouse_allowlist,
)


def build_website_stock_by_sku_sql(
    *,
    inventory_year: Optional[int] = None,
    j3_database: Optional[str] = None,
    sku_filter: Optional[Sequence[str]] = None,
    top_n: Optional[int] = None,
) -> str:
    """Aggregate allowlisted warehouse balances per article code."""
    allow = website_warehouse_allowlist()
    allow_sql = sql_in_list(allow)
    deny_sql = sql_in_list(sorted(WEBSITE_WAREHOUSE_DENYLIST))

    detalle = qualified_j3_table("InvDetalleExistencias", j3_database)
    existencias = qualified_j3_table("InvExistencias", j3_database)
    articulos = qualified_j3_table("AdmArticulos", j3_database)
    almacen = qualified_j3_table("AdmAlmacen", j3_database)

    year_filter = (
        f"d.Ano = {int(inventory_year)}"
        if inventory_year is not None
        else f"d.Ano = (SELECT MAX(Ano) FROM {detalle})"
    )

    sku_clause = ""
    if sku_filter:
        sku_sql = sql_in_list(sku_filter, max_len=40)
        sku_clause = f"AND a.ArticulosCodigo IN ({sku_sql})"

    top = f"TOP {int(top_n)} " if top_n is not None and int(top_n) > 0 else ""

    return f"""
SELECT {top}
    a.ArticulosCodigo AS sku,
    MAX(a.ArticulosNombre) AS name,
    CAST(SUM(CASE WHEN al.AlmacenCodigo IN ({allow_sql})
        THEN CAST(d.SaldoActual AS DECIMAL(18, 4)) ELSE 0 END) AS DECIMAL(18, 4))
        AS website_qty,
    CAST(SUM(CASE WHEN al.AlmacenCodigo IN ({deny_sql})
        THEN CAST(d.SaldoActual AS DECIMAL(18, 4)) ELSE 0 END) AS DECIMAL(18, 4))
        AS excluded_qty,
    CAST(SUM(CAST(d.SaldoActual AS DECIMAL(18, 4))) AS DECIMAL(18, 4)) AS all_warehouses_qty,
    COUNT(DISTINCT CASE WHEN al.AlmacenCodigo IN ({allow_sql})
        AND CAST(d.SaldoActual AS DECIMAL(18, 4)) > 0
        THEN al.AlmacenCodigo END) AS allowlist_warehouses_with_qty
FROM {detalle} d
JOIN {existencias} e ON e.ExistenciasID = d.ExistenciasID
JOIN {articulos} a ON a.ArticulosID = e.ArticulosID
JOIN {almacen} al ON al.AlmacenID = d.AlmacenID
WHERE {year_filter}
  AND CAST(d.SaldoActual AS DECIMAL(18, 4)) >= 0
  AND al.AlmacenCodigo IS NOT NULL
  AND LTRIM(RTRIM(al.AlmacenCodigo)) <> ''
  {sku_clause}
GROUP BY a.ArticulosCodigo
HAVING SUM(CASE WHEN al.AlmacenCodigo IN ({allow_sql})
    THEN CAST(d.SaldoActual AS DECIMAL(18, 4)) ELSE 0 END) > 0
    OR SUM(CASE WHEN al.AlmacenCodigo IN ({deny_sql})
    THEN CAST(d.SaldoActual AS DECIMAL(18, 4)) ELSE 0 END) > 0
ORDER BY excluded_qty DESC, website_qty DESC
""".strip()


def build_website_stock_impact_summary_sql(
    *,
    inventory_year: Optional[int] = None,
    j3_database: Optional[str] = None,
) -> str:
    """One-row summary: how much stock sits only on denylisted warehouses."""
    allow = website_warehouse_allowlist()
    allow_sql = sql_in_list(allow)
    deny_sql = sql_in_list(sorted(WEBSITE_WAREHOUSE_DENYLIST))

    detalle = qualified_j3_table("InvDetalleExistencias", j3_database)
    existencias = qualified_j3_table("InvExistencias", j3_database)
    articulos = qualified_j3_table("AdmArticulos", j3_database)
    almacen = qualified_j3_table("AdmAlmacen", j3_database)

    year_filter = (
        f"d.Ano = {int(inventory_year)}"
        if inventory_year is not None
        else f"d.Ano = (SELECT MAX(Ano) FROM {detalle})"
    )

    return f"""
SELECT
    CAST(SUM(CASE WHEN al.AlmacenCodigo IN ({allow_sql})
        THEN CAST(d.SaldoActual AS DECIMAL(18, 4)) ELSE 0 END) AS DECIMAL(18, 4))
        AS website_qty_sum,
    CAST(SUM(CASE WHEN al.AlmacenCodigo IN ({deny_sql})
        THEN CAST(d.SaldoActual AS DECIMAL(18, 4)) ELSE 0 END) AS DECIMAL(18, 4))
        AS excluded_qty_sum,
    CAST(SUM(CAST(d.SaldoActual AS DECIMAL(18, 4))) AS DECIMAL(18, 4)) AS all_warehouses_qty_sum,
    COUNT(DISTINCT a.ArticulosCodigo) AS sku_rows_touched
FROM {detalle} d
JOIN {existencias} e ON e.ExistenciasID = d.ExistenciasID
JOIN {articulos} a ON a.ArticulosID = e.ArticulosID
JOIN {almacen} al ON al.AlmacenID = d.AlmacenID
WHERE {year_filter}
  AND CAST(d.SaldoActual AS DECIMAL(18, 4)) > 0
  AND al.AlmacenCodigo IS NOT NULL
  AND LTRIM(RTRIM(al.AlmacenCodigo)) <> ''
""".strip()


def build_quote_search_sql(*, limit: int = 6, dialect: str = "tsql") -> str:
    """Name/SKU search with allowlisted website qty, list price, and IVA rate.

    Price is ``AdmArticulos.ArticulosVenta`` (money, before IVA). Never select
    cost and never filter on ``ArticulosEstado``. The IVA rate is
    ``AdmLineas.LineasPorcentaje`` (percentage, not a fraction) reached via a
    LEFT JOIN so a missing line/NULL rate never removes the product. Stock is
    J3 ``InvDetalleExistencias.SaldoActual`` on the website allowlist.

    ``dialect`` selects the parameter/limit/coalesce syntax: ``"tsql"`` (the
    production SQL Server dialect) or ``"sqlite"`` (used by fake-only tests via
    an exact ``Decimal`` ``decimal_sum`` aggregate). Both emit the same query
    structure and logic.
    """
    if dialect not in {"tsql", "sqlite"}:
        raise ValueError(f"unsupported dialect: {dialect!r}")
    limit_n = max(1, min(int(limit), 10))
    allow_sql = sql_in_list(website_warehouse_allowlist())

    sqlite = dialect == "sqlite"
    if sqlite:
        table = lambda name: name  # noqa: E731 — bare names for the SQLite fixture
        placeholder = "?"
        top = ""
        tail = f"LIMIT {limit_n}"
        price_expr = "a.ArticulosVenta"
        website_qty_expr = "COALESCE(s.website_qty, '0.0000')"
        stock_sum_expr = (
            f"decimal_sum(CASE WHEN al.AlmacenCodigo IN ({allow_sql}) "
            f"THEN d.SaldoActual END)"
        )
        stock_filter = "decimal_ge(d.SaldoActual, '0') = 1"
        sort_cond = "decimal_gt(COALESCE(s.website_qty, '0.0000'), '0') = 1"
    else:
        table = qualified_j3_table
        placeholder = "%s"
        top = f"TOP {limit_n} "
        tail = ""
        price_expr = "a.ArticulosVenta"
        website_qty_expr = "ISNULL(s.website_qty, 0)"
        stock_sum_expr = (
            f"SUM(CASE WHEN al.AlmacenCodigo IN ({allow_sql}) "
            f"THEN d.SaldoActual ELSE 0 END)"
        )
        stock_filter = "d.SaldoActual >= 0"
        sort_cond = "ISNULL(s.website_qty, 0) > 0"

    articulos = table("AdmArticulos")
    lineas = table("AdmLineas")
    detalle = table("InvDetalleExistencias")
    existencias = table("InvExistencias")
    almacen = table("AdmAlmacen")
    return f"""
SELECT {top}
    a.ArticulosCodigo AS sku,
    a.ArticulosNombre AS name,
    {price_expr} AS price,
    l.LineasPorcentaje AS iva_rate,
    l.LineasID AS line_id,
    {website_qty_expr} AS website_qty
FROM {articulos} a
LEFT JOIN {lineas} l ON l.LineasID = a.LineasID
LEFT JOIN (
    SELECT
        e.ArticulosID,
        {stock_sum_expr} AS website_qty
    FROM {detalle} d
    JOIN {existencias} e ON e.ExistenciasID = d.ExistenciasID
    JOIN {almacen} al ON al.AlmacenID = d.AlmacenID
    WHERE d.Ano = (SELECT MAX(Ano) FROM {detalle})
      AND {stock_filter}
    GROUP BY e.ArticulosID
) s ON s.ArticulosID = a.ArticulosID
WHERE (a.ArticulosNombre LIKE {placeholder} OR a.ArticulosCodigo LIKE {placeholder})
ORDER BY CASE WHEN {sort_cond} THEN 0 ELSE 1 END,
         a.ArticulosNombre
{tail}
""".strip()


class WebsiteStockRunner:
    """Execute website stock queries against J3System."""

    def __init__(self, db: Optional[Database] = None) -> None:
        self.db = db or Database()

    def _execute(self, sql: str) -> List[Dict[str, Any]]:
        self.db.connect()
        rows = self.db.execute_query(sql)
        if not isinstance(rows, list):
            return []
        return [dict(r) for r in rows]

    def impact_summary(self, *, inventory_year: Optional[int] = None) -> Dict[str, Any]:
        sql = build_website_stock_impact_summary_sql(inventory_year=inventory_year)
        rows = self._execute(sql)
        if not rows:
            return {}
        return dict(rows[0])

    def stock_by_sku(
        self,
        *,
        inventory_year: Optional[int] = None,
        skus: Optional[Sequence[str]] = None,
        top_n: int = 100,
    ) -> List[Dict[str, Any]]:
        sql = build_website_stock_by_sku_sql(
            inventory_year=inventory_year,
            sku_filter=skus,
            top_n=None if skus else top_n,
        )
        return self._execute(sql)

    def skus_with_excluded_stock(
        self,
        *,
        inventory_year: Optional[int] = None,
        top_n: int = 50,
        min_excluded: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """SKUs where denylist warehouses hold qty (website would drop if filtered)."""
        rows = self.stock_by_sku(
            inventory_year=inventory_year, top_n=max(top_n * 5, 200)
        )
        filtered = [
            r for r in rows if float(r.get("excluded_qty") or 0) >= min_excluded
        ]
        filtered.sort(key=lambda r: float(r.get("excluded_qty") or 0), reverse=True)
        return filtered[:top_n]
