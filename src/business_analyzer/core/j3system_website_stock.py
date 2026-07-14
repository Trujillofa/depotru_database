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
