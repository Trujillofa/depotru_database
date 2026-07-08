"""J3System critical inventory and stock-break analysis.

Combines warehouse-level balances from ``InvDetalleExistencias`` with 90-day
sales velocity from ``banco_datos`` (cross-database on the same MSSQL host).

Coverage (días) = ``SaldoActual / venta_diaria_promedio`` where
``venta_diaria_promedio = SUM(Cantidad últimos N días) / N``.

``StockMinimo`` is often zero in J3System; use ``low_stock_threshold`` (default 10)
as the operational alert level (aligned with the manager report).
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, cast

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_sales_warehouse import (
    _validate_period_date,
    qualified_j3_table,
)

DEFAULT_VELOCITY_DAYS = 90
DEFAULT_LOW_STOCK_THRESHOLD = 10
DEFAULT_MIN_VELOCITY_QTY = 50
DEFAULT_MAX_COVER_DAYS_ALERT = 14
DEFAULT_TOP_N = 50

EXCLUDED_DOC_CODES: tuple[str, ...] = ("XY", "AS", "TS", "YX", "ISC")


def qualified_sb_table(table: str, sb_database: Optional[str] = None) -> str:
    """Return a validated ``SmartBusiness.dbo.<table>`` reference."""
    db_name = sb_database or os.getenv("DB_NAME", "SmartBusiness")
    validated_db = Database.validate_sql_identifier(db_name, "smartbusiness database")
    validated_table = Database.validate_sql_identifier(table, "table")
    return f"{validated_db}.dbo.{validated_table}"


def _excluded_docs_sql() -> str:
    return ", ".join(f"'{code}'" for code in EXCLUDED_DOC_CODES)


def _positive_int(value: int, name: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def build_velocity_cte(
    *,
    as_of_date: str,
    velocity_days: int = DEFAULT_VELOCITY_DAYS,
    sb_database: Optional[str] = None,
) -> str:
    """CTE: SKU-level sales quantity and daily average over ``velocity_days``."""
    banco = qualified_sb_table("banco_datos", sb_database)
    days = _positive_int(velocity_days, "velocity_days")
    as_of = _validate_period_date(as_of_date, "as_of_date")
    excluded = _excluded_docs_sql()
    return f"""
velocidad AS (
    SELECT
        ArticulosCodigo,
        SUM(Cantidad) AS Cantidad_90d,
        SUM(Cantidad) / {days}.0 AS Venta_Diaria_Promedio
    FROM {banco}
    WHERE Fecha >= DATEADD(DAY, -{days}, CAST('{as_of}' AS DATE))
      AND Fecha <= CAST('{as_of}' AS DATE)
      AND DocumentosCodigo NOT IN ({excluded})
      AND Cantidad > 0
    GROUP BY ArticulosCodigo
)""".strip()


def build_existencias_cte(
    *,
    inventory_year: Optional[int] = None,
    j3_database: Optional[str] = None,
) -> str:
    """CTE: current balances per SKU and warehouse (latest ``Ano`` by default)."""
    detalle = qualified_j3_table("InvDetalleExistencias", j3_database)
    existencias = qualified_j3_table("InvExistencias", j3_database)
    articulos = qualified_j3_table("AdmArticulos", j3_database)
    almacen = qualified_j3_table("AdmAlmacen", j3_database)
    year_filter = (
        f"WHERE d.Ano = {int(inventory_year)}"
        if inventory_year is not None
        else f"WHERE d.Ano = (SELECT MAX(Ano) FROM {detalle})"
    )
    return f"""
existencias AS (
    SELECT
        a.ArticulosCodigo,
        a.ArticulosNombre,
        al.AlmacenCodigo,
        al.AlmacenNombre,
        CAST(d.SaldoActual AS DECIMAL(18, 4)) AS Saldo_Actual,
        CAST(d.StockMinimo AS DECIMAL(18, 4)) AS Stock_Minimo,
        d.Ano AS Ano_Inventario
    FROM {detalle} d
    JOIN {existencias} e ON e.ExistenciasID = d.ExistenciasID
    JOIN {articulos} a ON a.ArticulosID = e.ArticulosID
    JOIN {almacen} al ON al.AlmacenID = d.AlmacenID
    {year_filter}
      AND CAST(d.SaldoActual AS DECIMAL(18, 4)) >= 0
      AND al.AlmacenCodigo IS NOT NULL
      AND al.AlmacenCodigo <> ''
)""".strip()


def build_critical_inventory_sql(
    as_of_date: str,
    *,
    velocity_days: int = DEFAULT_VELOCITY_DAYS,
    low_stock_threshold: int = DEFAULT_LOW_STOCK_THRESHOLD,
    min_velocity_qty: int = DEFAULT_MIN_VELOCITY_QTY,
    max_cover_days_alert: int = DEFAULT_MAX_COVER_DAYS_ALERT,
    top_n: int = DEFAULT_TOP_N,
    inventory_year: Optional[int] = None,
    j3_database: Optional[str] = None,
    sb_database: Optional[str] = None,
) -> str:
    """SKUs with low stock and high rotation, ranked by days of cover."""
    velocity = build_velocity_cte(
        as_of_date=as_of_date,
        velocity_days=velocity_days,
        sb_database=sb_database,
    )
    existencias = build_existencias_cte(
        inventory_year=inventory_year, j3_database=j3_database
    )
    threshold = _positive_int(low_stock_threshold, "low_stock_threshold")
    min_qty = _positive_int(min_velocity_qty, "min_velocity_qty")
    max_cover = _positive_int(max_cover_days_alert, "max_cover_days_alert")
    limit = _positive_int(top_n, "top_n")
    as_of = _validate_period_date(as_of_date, "as_of_date")
    return f"""
WITH {velocity},
{existencias}
SELECT TOP ({limit})
    ex.ArticulosCodigo AS SKU,
    ex.ArticulosNombre AS Producto,
    ex.AlmacenCodigo,
    ex.AlmacenNombre,
    ex.Saldo_Actual,
    ex.Stock_Minimo,
    ex.Ano_Inventario,
    v.Cantidad_90d,
    v.Venta_Diaria_Promedio,
    CASE
        WHEN v.Venta_Diaria_Promedio > 0
        THEN ex.Saldo_Actual / v.Venta_Diaria_Promedio
        ELSE NULL
    END AS Dias_Cobertura,
    CASE
        WHEN ex.Stock_Minimo > 0 AND ex.Saldo_Actual < ex.Stock_Minimo
        THEN 'DEBAJO_MINIMO'
        WHEN v.Venta_Diaria_Promedio > 0
             AND ex.Saldo_Actual / v.Venta_Diaria_Promedio < 3
        THEN 'QUIEBRE_INMINENTE'
        WHEN ex.Saldo_Actual <= {threshold}
        THEN 'STOCK_CRITICO'
        WHEN v.Venta_Diaria_Promedio > 0
             AND ex.Saldo_Actual / v.Venta_Diaria_Promedio < {max_cover}
        THEN 'COBERTURA_BAJA'
        ELSE 'ALERTA_ROTACION'
    END AS Prioridad
FROM existencias ex
INNER JOIN velocidad v ON v.ArticulosCodigo = ex.ArticulosCodigo
WHERE v.Cantidad_90d >= {min_qty}
  AND (
    (ex.Stock_Minimo > 0 AND ex.Saldo_Actual < ex.Stock_Minimo)
    OR ex.Saldo_Actual <= {threshold}
    OR (
        v.Venta_Diaria_Promedio > 0
        AND ex.Saldo_Actual / v.Venta_Diaria_Promedio < {max_cover}
    )
  )
ORDER BY
    CASE WHEN v.Venta_Diaria_Promedio > 0 THEN ex.Saldo_Actual / v.Venta_Diaria_Promedio ELSE 999999 END,
    v.Cantidad_90d DESC;
""".strip()


def build_critical_inventory_by_warehouse_sql(
    as_of_date: str,
    *,
    velocity_days: int = DEFAULT_VELOCITY_DAYS,
    low_stock_threshold: int = DEFAULT_LOW_STOCK_THRESHOLD,
    min_velocity_qty: int = DEFAULT_MIN_VELOCITY_QTY,
    max_cover_days_alert: int = DEFAULT_MAX_COVER_DAYS_ALERT,
    inventory_year: Optional[int] = None,
    j3_database: Optional[str] = None,
    sb_database: Optional[str] = None,
) -> str:
    """Aggregate critical SKU counts and average cover days per warehouse."""
    velocity = build_velocity_cte(
        as_of_date=as_of_date,
        velocity_days=velocity_days,
        sb_database=sb_database,
    )
    existencias = build_existencias_cte(
        inventory_year=inventory_year, j3_database=j3_database
    )
    threshold = _positive_int(low_stock_threshold, "low_stock_threshold")
    min_qty = _positive_int(min_velocity_qty, "min_velocity_qty")
    max_cover = _positive_int(max_cover_days_alert, "max_cover_days_alert")
    _validate_period_date(as_of_date, "as_of_date")
    return f"""
WITH {velocity},
{existencias},
criticos AS (
    SELECT
        ex.AlmacenCodigo,
        ex.AlmacenNombre,
        ex.Saldo_Actual,
        v.Cantidad_90d,
        v.Venta_Diaria_Promedio,
        CASE
            WHEN v.Venta_Diaria_Promedio > 0
            THEN ex.Saldo_Actual / v.Venta_Diaria_Promedio
            ELSE NULL
        END AS Dias_Cobertura
    FROM existencias ex
    INNER JOIN velocidad v ON v.ArticulosCodigo = ex.ArticulosCodigo
    WHERE v.Cantidad_90d >= {min_qty}
      AND (
        (ex.Stock_Minimo > 0 AND ex.Saldo_Actual < ex.Stock_Minimo)
        OR ex.Saldo_Actual <= {threshold}
        OR (
            v.Venta_Diaria_Promedio > 0
            AND ex.Saldo_Actual / v.Venta_Diaria_Promedio < {max_cover}
        )
      )
)
SELECT
    AlmacenCodigo,
    AlmacenNombre,
    COUNT(*) AS SKUs_Criticos,
    SUM(CASE WHEN Dias_Cobertura IS NOT NULL AND Dias_Cobertura < 7 THEN 1 ELSE 0 END)
        AS SKUs_Quiebre_7d,
    AVG(Dias_Cobertura) AS Promedio_Dias_Cobertura,
    SUM(Saldo_Actual) AS Stock_Total_Critico
FROM criticos
GROUP BY AlmacenCodigo, AlmacenNombre
ORDER BY SKUs_Criticos DESC;
""".strip()


def validate_inventory_as_of_date(as_of_date: str) -> None:
    """Raise if ``as_of_date`` is not YYYY-MM-DD."""
    _validate_period_date(as_of_date, "as_of_date")


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def critical_inventory_summary_from_rows(
    rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Aggregate detail rows into period-level inventory risk KPIs."""
    if not rows:
        return {
            "SKUs_Criticos": 0,
            "SKUs_Quiebre_7d": 0,
            "Promedio_Dias_Cobertura": 0.0,
            "SKUs_Stock_Bajo": 0,
        }

    cover_values = [
        _as_float(r.get("Dias_Cobertura"))
        for r in rows
        if r.get("Dias_Cobertura") is not None
    ]
    quiebre = sum(
        1
        for r in rows
        if r.get("Dias_Cobertura") is not None
        and _as_float(r.get("Dias_Cobertura")) < 7
    )
    stock_bajo = sum(1 for r in rows if _as_float(r.get("Saldo_Actual")) <= 10)

    return {
        "SKUs_Criticos": len(rows),
        "SKUs_Quiebre_7d": quiebre,
        "Promedio_Dias_Cobertura": (
            sum(cover_values) / len(cover_values) if cover_values else 0.0
        ),
        "SKUs_Stock_Bajo": stock_bajo,
    }


def top_critical_by_warehouse(
    rows: Sequence[Mapping[str, Any]],
    *,
    n: int = 5,
) -> List[Dict[str, Any]]:
    """Warehouses with the most critical SKUs in the result set."""
    counts: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        code = str(row.get("AlmacenCodigo") or "")
        if not code:
            continue
        bucket = counts.setdefault(
            code,
            {
                "AlmacenCodigo": code,
                "AlmacenNombre": row.get("AlmacenNombre"),
                "SKUs_Criticos": 0,
            },
        )
        bucket["SKUs_Criticos"] += 1
    ranked = sorted(counts.values(), key=lambda r: r["SKUs_Criticos"], reverse=True)
    return ranked[:n]


class CriticalInventoryRunner:
    """Execute cross-database critical inventory SQL via SmartBusiness connection."""

    def __init__(
        self,
        db: Optional[Database] = None,
        *,
        j3_database: Optional[str] = None,
        sb_database: Optional[str] = None,
        velocity_days: int = DEFAULT_VELOCITY_DAYS,
        low_stock_threshold: int = DEFAULT_LOW_STOCK_THRESHOLD,
        min_velocity_qty: int = DEFAULT_MIN_VELOCITY_QTY,
        max_cover_days_alert: int = DEFAULT_MAX_COVER_DAYS_ALERT,
        top_n: int = DEFAULT_TOP_N,
    ) -> None:
        self.db = db or Database()
        self.j3_database = j3_database
        self.sb_database = sb_database
        self.velocity_days = velocity_days
        self.low_stock_threshold = low_stock_threshold
        self.min_velocity_qty = min_velocity_qty
        self.max_cover_days_alert = max_cover_days_alert
        self.top_n = top_n

    def _execute_query(self, sql: str) -> List[Dict[str, Any]]:
        self.db.connect()
        rows = cast(List[Dict[str, Any]], self.db.execute_query(sql))
        return [dict(row) for row in rows]

    def fetch_critical_skus(self, as_of_date: str) -> List[Dict[str, Any]]:
        validate_inventory_as_of_date(as_of_date)
        sql = build_critical_inventory_sql(
            as_of_date,
            velocity_days=self.velocity_days,
            low_stock_threshold=self.low_stock_threshold,
            min_velocity_qty=self.min_velocity_qty,
            max_cover_days_alert=self.max_cover_days_alert,
            top_n=self.top_n,
            j3_database=self.j3_database,
            sb_database=self.sb_database,
        )
        return self._execute_query(sql)

    def fetch_by_warehouse(self, as_of_date: str) -> List[Dict[str, Any]]:
        validate_inventory_as_of_date(as_of_date)
        sql = build_critical_inventory_by_warehouse_sql(
            as_of_date,
            velocity_days=self.velocity_days,
            low_stock_threshold=self.low_stock_threshold,
            min_velocity_qty=self.min_velocity_qty,
            max_cover_days_alert=self.max_cover_days_alert,
            j3_database=self.j3_database,
            sb_database=self.sb_database,
        )
        return self._execute_query(sql)

    def build_report(self, as_of_date: str) -> Dict[str, Any]:
        detail = self.fetch_critical_skus(as_of_date)
        by_wh = self.fetch_by_warehouse(as_of_date)
        return {
            "as_of_date": as_of_date,
            "velocity_days": self.velocity_days,
            "summary": critical_inventory_summary_from_rows(detail),
            "critical_skus": detail,
            "by_warehouse": by_wh,
            "top_warehouses": top_critical_by_warehouse(detail),
        }
