"""Sales anomaly detection — compare yesterday vs 30-day moving average."""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from ..core.database import Database


def check_sales_anomaly(
    days_ago: int = 1,
    threshold_pct: float = 20.0,
    db: Optional["Database"] = None,
) -> Dict[str, Any]:
    """
    Detect if recent daily sales dropped more than ``threshold_pct`` vs 30-day avg.

    Returns dict with keys: anomaly (bool), yesterday_sales, avg_sales, drop_pct.
    """
    from ..core.database import Database

    target = date.today() - timedelta(days=days_ago)
    month_ago = target - timedelta(days=30)

    sql_day = """
        SELECT SUM(TotalMasIva) AS total_sales
        FROM banco_datos
        WHERE Fecha = %s
          AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
    """
    sql_avg = """
        SELECT AVG(TotalMasIva) AS avg_sales
        FROM (
            SELECT SUM(TotalMasIva) AS TotalMasIva
            FROM banco_datos
            WHERE Fecha BETWEEN %s AND %s
              AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
            GROUP BY Fecha
        ) t
    """

    def _run(conn: "Database") -> Dict[str, Any]:
        day_raw = conn.execute_query(sql_day, (target.isoformat(),))
        avg_raw = conn.execute_query(
            sql_avg, (month_ago.isoformat(), target.isoformat())
        )
        day_rows = day_raw if isinstance(day_raw, list) else []
        avg_rows = avg_raw if isinstance(avg_raw, list) else []
        yesterday_sales = float(
            (day_rows[0].get("total_sales") if day_rows else 0) or 0
        )
        avg_sales = float((avg_rows[0].get("avg_sales") if avg_rows else 0) or 0)

        if avg_sales == 0:
            return {
                "anomaly": False,
                "yesterday_sales": yesterday_sales,
                "avg_sales": avg_sales,
                "drop_pct": 0.0,
                "target_date": target.isoformat(),
            }

        drop_pct = ((avg_sales - yesterday_sales) / avg_sales) * 100
        return {
            "anomaly": drop_pct > threshold_pct,
            "yesterday_sales": yesterday_sales,
            "avg_sales": avg_sales,
            "drop_pct": drop_pct,
            "target_date": target.isoformat(),
        }

    if db is not None:
        return _run(db)
    with Database() as conn:
        return _run(conn)
