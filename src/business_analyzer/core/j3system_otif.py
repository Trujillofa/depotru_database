"""J3System delivery compliance (OTIF) SQL builders.

``InvHistoricoEntregas`` stores ``FechaEntrega`` as Colombian text
(``DD/MM/YYYY H:M``). Parse the date portion with ``CONVERT(..., 103)``.

**On time:** ``FechaEntrega_Parsed <= FechaProximaEntrega`` (promised date).
**Lead time:** ``DATEDIFF(DAY, FechaFactura, FechaEntrega_Parsed)``.
**In full (line):** ``Entrega >= CantidadFacturada`` for the delivery event.

Join to ``InvVentas`` when needed::
    ``AdmDocumentos.DocumentosCodigo = Docto`` AND ``NumeroDocumento = Numero``
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Sequence

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_sales_warehouse import (
    _validate_period_date,
    qualified_j3_table,
)

DEFAULT_MIN_CUSTOMER_DELIVERIES = 20
DEFAULT_TOP_N_CUSTOMERS = 10

EXCLUDED_DOC_CODES: tuple[str, ...] = ("XY", "AS", "TS", "YX", "ISC")
ENTREGA_TIPO = "Entrega"


def _excluded_docs_sql() -> str:
    return ", ".join(f"'{code}'" for code in EXCLUDED_DOC_CODES)


def fecha_entrega_parsed_sql(column: str = "e.FechaEntrega") -> str:
    """SQL expression: parse ``DD/MM/YYYY`` prefix of ``FechaEntrega`` to DATE."""
    return f"""CASE
        WHEN LEN({column}) >= 10
         AND SUBSTRING({column}, 3, 1) = '/'
         AND SUBSTRING({column}, 6, 1) = '/'
        THEN CONVERT(DATE, LEFT({column}, 10), 103)
        ELSE NULL
    END"""


def _entregas_filtradas_cte(
    *,
    start_date: str,
    end_date: str,
    j3_database: Optional[str] = None,
) -> str:
    historico = qualified_j3_table("InvHistoricoEntregas", j3_database)
    start = _validate_period_date(start_date, "start_date")
    end = _validate_period_date(end_date, "end_date")
    excluded = _excluded_docs_sql()
    parsed = fecha_entrega_parsed_sql("e.FechaEntrega")
    return f"""
entregas_filtradas AS (
    SELECT
        e.Docto,
        e.Numero,
        e.FechaFactura,
        e.FechaProximaEntrega,
        {parsed} AS FechaEntrega_Parsed,
        e.Cliente,
        e.Almacen,
        e.CantidadFacturada,
        e.Entrega,
        e.Saldo
    FROM {historico} e
    WHERE e.Tipo = '{ENTREGA_TIPO}'
      AND e.FechaFactura BETWEEN '{start}' AND '{end}'
      AND e.Docto NOT IN ({excluded})
)""".strip()


def build_otif_summary_sql(
    start_date: str,
    end_date: str,
    *,
    j3_database: Optional[str] = None,
) -> str:
    """Period-level OTIF, fill rate, and average lead time."""
    entregas = _entregas_filtradas_cte(
        start_date=start_date, end_date=end_date, j3_database=j3_database
    )
    start = _validate_period_date(start_date, "start_date")
    end = _validate_period_date(end_date, "end_date")
    return f"""
WITH {entregas}
SELECT
    '{start}' AS Fecha_Inicio,
    '{end}' AS Fecha_Fin,
    COUNT(*) AS Total_Entregas,
    SUM(CASE WHEN FechaEntrega_Parsed IS NOT NULL THEN 1 ELSE 0 END) AS Entregas_Parseadas,
    SUM(
        CASE
            WHEN FechaEntrega_Parsed IS NOT NULL
             AND FechaEntrega_Parsed <= FechaProximaEntrega
            THEN 1 ELSE 0
        END
    ) AS Entregas_A_Tiempo,
    SUM(
        CASE
            WHEN FechaEntrega_Parsed IS NOT NULL
             AND FechaEntrega_Parsed > FechaProximaEntrega
            THEN 1 ELSE 0
        END
    ) AS Entregas_Tarde,
    CASE
        WHEN SUM(CASE WHEN FechaEntrega_Parsed IS NOT NULL THEN 1 ELSE 0 END) = 0
        THEN 0
        ELSE SUM(
            CASE
                WHEN FechaEntrega_Parsed IS NOT NULL
                 AND FechaEntrega_Parsed <= FechaProximaEntrega
                THEN 1 ELSE 0
            END
        ) * 100.0
        / SUM(CASE WHEN FechaEntrega_Parsed IS NOT NULL THEN 1 ELSE 0 END)
    END AS OTIF_Pct,
    CASE
        WHEN SUM(CASE WHEN FechaEntrega_Parsed IS NOT NULL THEN 1 ELSE 0 END) = 0
        THEN 0
        ELSE AVG(
            CAST(DATEDIFF(DAY, FechaFactura, FechaEntrega_Parsed) AS FLOAT)
        )
    END AS Lead_Time_Promedio_Dias,
    CASE
        WHEN COUNT(*) = 0 THEN 0
        ELSE SUM(CASE WHEN Entrega >= CantidadFacturada THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
    END AS Fill_Rate_Pct
FROM entregas_filtradas;
""".strip()


def build_otif_by_warehouse_sql(
    start_date: str,
    end_date: str,
    *,
    j3_database: Optional[str] = None,
) -> str:
    """OTIF and lead time aggregated per warehouse (``Almacen`` code)."""
    entregas = _entregas_filtradas_cte(
        start_date=start_date, end_date=end_date, j3_database=j3_database
    )
    _validate_period_date(start_date, "start_date")
    _validate_period_date(end_date, "end_date")
    return f"""
WITH {entregas}
SELECT
    Almacen AS Almacen_Codigo,
    COUNT(*) AS Total_Entregas,
    SUM(
        CASE
            WHEN FechaEntrega_Parsed IS NOT NULL
             AND FechaEntrega_Parsed <= FechaProximaEntrega
            THEN 1 ELSE 0
        END
    ) AS Entregas_A_Tiempo,
    SUM(
        CASE
            WHEN FechaEntrega_Parsed IS NOT NULL
             AND FechaEntrega_Parsed > FechaProximaEntrega
            THEN 1 ELSE 0
        END
    ) AS Entregas_Tarde,
    CASE
        WHEN SUM(CASE WHEN FechaEntrega_Parsed IS NOT NULL THEN 1 ELSE 0 END) = 0
        THEN 0
        ELSE SUM(
            CASE
                WHEN FechaEntrega_Parsed IS NOT NULL
                 AND FechaEntrega_Parsed <= FechaProximaEntrega
                THEN 1 ELSE 0
            END
        ) * 100.0
        / SUM(CASE WHEN FechaEntrega_Parsed IS NOT NULL THEN 1 ELSE 0 END)
    END AS OTIF_Pct,
    CASE
        WHEN SUM(CASE WHEN FechaEntrega_Parsed IS NOT NULL THEN 1 ELSE 0 END) = 0
        THEN 0
        ELSE AVG(
            CAST(DATEDIFF(DAY, FechaFactura, FechaEntrega_Parsed) AS FLOAT)
        )
    END AS Lead_Time_Promedio_Dias,
    CASE
        WHEN COUNT(*) = 0 THEN 0
        ELSE SUM(CASE WHEN Entrega >= CantidadFacturada THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
    END AS Fill_Rate_Pct
FROM entregas_filtradas
WHERE FechaEntrega_Parsed IS NOT NULL
GROUP BY Almacen
ORDER BY OTIF_Pct ASC, Total_Entregas DESC;
""".strip()


def build_otif_by_customer_sql(
    start_date: str,
    end_date: str,
    *,
    min_deliveries: int = DEFAULT_MIN_CUSTOMER_DELIVERIES,
    top_n: int = DEFAULT_TOP_N_CUSTOMERS,
    j3_database: Optional[str] = None,
) -> str:
    """Customers with worst on-time performance (minimum delivery volume)."""
    entregas = _entregas_filtradas_cte(
        start_date=start_date, end_date=end_date, j3_database=j3_database
    )
    _validate_period_date(start_date, "start_date")
    _validate_period_date(end_date, "end_date")
    min_del = int(min_deliveries)
    limit = int(top_n)
    return f"""
WITH {entregas}
SELECT TOP ({limit})
    Cliente,
    COUNT(*) AS Total_Entregas,
    SUM(
        CASE
            WHEN FechaEntrega_Parsed <= FechaProximaEntrega THEN 1 ELSE 0
        END
    ) AS Entregas_A_Tiempo,
    SUM(
        CASE
            WHEN FechaEntrega_Parsed > FechaProximaEntrega THEN 1 ELSE 0
        END
    ) AS Entregas_Tarde,
    CASE
        WHEN COUNT(*) = 0 THEN 0
        ELSE SUM(
            CASE WHEN FechaEntrega_Parsed <= FechaProximaEntrega THEN 1 ELSE 0 END
        ) * 100.0 / COUNT(*)
    END AS OTIF_Pct,
    AVG(CAST(DATEDIFF(DAY, FechaFactura, FechaEntrega_Parsed) AS FLOAT))
        AS Lead_Time_Promedio_Dias
FROM entregas_filtradas
WHERE FechaEntrega_Parsed IS NOT NULL
GROUP BY Cliente
HAVING COUNT(*) >= {min_del}
ORDER BY OTIF_Pct ASC, Total_Entregas DESC;
""".strip()


def validate_otif_sql_period(start_date: str, end_date: str) -> None:
    """Raise if period strings are invalid or reversed."""
    _validate_period_date(start_date, "start_date")
    _validate_period_date(end_date, "end_date")
    if start_date > end_date:
        raise ValueError(f"start_date {start_date!r} is after end_date {end_date!r}")


def parse_fecha_entrega(value: object) -> Optional[str]:
    """Parse ``DD/MM/YYYY H:M`` to ISO date ``YYYY-MM-DD`` (Python-side helper)."""
    if value is None:
        return None
    text = str(value).strip()
    if len(text) < 10:
        return None
    date_part = text[:10]
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", date_part):
        return None
    day, month, year = date_part.split("/")
    return f"{year}-{month}-{day}"


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


def otif_summary_from_warehouse_rows(
    rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Weighted OTIF aggregate from warehouse-level rows."""
    total = sum(_as_int(r.get("Total_Entregas")) for r in rows)
    on_time = sum(_as_int(r.get("Entregas_A_Tiempo")) for r in rows)
    late = sum(_as_int(r.get("Entregas_Tarde")) for r in rows)

    weighted_lead = 0.0
    for row in rows:
        n = _as_int(row.get("Total_Entregas"))
        if n:
            weighted_lead += _as_float(row.get("Lead_Time_Promedio_Dias")) * n

    weighted_fill = 0.0
    for row in rows:
        n = _as_int(row.get("Total_Entregas"))
        if n:
            weighted_fill += _as_float(row.get("Fill_Rate_Pct")) * n

    return {
        "Total_Entregas": total,
        "Entregas_A_Tiempo": on_time,
        "Entregas_Tarde": late,
        "OTIF_Pct": (on_time * 100.0 / total) if total else 0.0,
        "Lead_Time_Promedio_Dias": (weighted_lead / total) if total else 0.0,
        "Fill_Rate_Pct": (weighted_fill / total) if total else 0.0,
    }


def worst_otif_warehouses(
    rows: Sequence[Mapping[str, Any]],
    *,
    n: int = 5,
) -> List[Dict[str, Any]]:
    """Warehouses with lowest OTIF % (enough volume)."""
    ranked = sorted(rows, key=lambda r: _as_float(r.get("OTIF_Pct")))
    return [dict(row) for row in ranked[:n]]


def worst_otif_customers(
    rows: Sequence[Mapping[str, Any]],
    *,
    n: int = 5,
) -> List[Dict[str, Any]]:
    """Customers already ranked worst-first from SQL."""
    return [dict(row) for row in rows[:n]]


class OtifRunner:
    """Execute J3System OTIF SQL and return structured results."""

    def __init__(
        self,
        db: Optional[Database] = None,
        *,
        j3_database: Optional[str] = None,
        min_customer_deliveries: int = DEFAULT_MIN_CUSTOMER_DELIVERIES,
        top_n_customers: int = DEFAULT_TOP_N_CUSTOMERS,
    ) -> None:
        self.db = db or Database()
        self.j3_database = j3_database
        self.min_customer_deliveries = min_customer_deliveries
        self.top_n_customers = top_n_customers

    def _execute_j3_query(self, sql: str) -> List[Dict[str, Any]]:
        conn = self.db.get_j3system_connection()
        try:
            cursor = conn.cursor(as_dict=True)
            cursor.execute(sql)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def fetch_summary(self, start_date: str, end_date: str) -> Dict[str, Any]:
        validate_otif_sql_period(start_date, end_date)
        sql = build_otif_summary_sql(start_date, end_date, j3_database=self.j3_database)
        rows = self._execute_j3_query(sql)
        return dict(rows[0]) if rows else {}

    def fetch_by_warehouse(
        self, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        validate_otif_sql_period(start_date, end_date)
        sql = build_otif_by_warehouse_sql(
            start_date, end_date, j3_database=self.j3_database
        )
        return self._execute_j3_query(sql)

    def fetch_worst_customers(
        self, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        validate_otif_sql_period(start_date, end_date)
        sql = build_otif_by_customer_sql(
            start_date,
            end_date,
            min_deliveries=self.min_customer_deliveries,
            top_n=self.top_n_customers,
            j3_database=self.j3_database,
        )
        return self._execute_j3_query(sql)

    def build_report(self, start_date: str, end_date: str) -> Dict[str, Any]:
        summary = self.fetch_summary(start_date, end_date)
        by_warehouse = self.fetch_by_warehouse(start_date, end_date)
        worst_customers = self.fetch_worst_customers(start_date, end_date)
        if not summary and by_warehouse:
            summary = otif_summary_from_warehouse_rows(by_warehouse)
        return {
            "period": {"start": start_date, "end": end_date},
            "summary": summary,
            "by_warehouse": by_warehouse,
            "worst_customers": worst_customers,
            "worst_warehouses": worst_otif_warehouses(by_warehouse),
        }
