"""
Predictive analytics for demand forecasting.

Uses simple linear regression to forecast demand (sales velocity)
for the next N days based on historical Cantidad and Fecha.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from ..core.database import Database


def _excluded_docs_placeholders() -> tuple[str, tuple[str, ...]]:
    """Build parameterized NOT IN clause from Config.EXCLUDED_DOCUMENT_CODES."""
    from config import Config

    codes = tuple(Config.EXCLUDED_DOCUMENT_CODES)
    clause = ", ".join(["%s"] * len(codes))
    return f"DocumentosCodigo NOT IN ({clause})", codes


def _linear_forecast(daily_qty: List[float], days: int) -> int:
    """Pure regression forecast from ordered daily quantities."""
    if not daily_qty or len(daily_qty) < 2:
        return 0

    n = len(daily_qty)
    x = list(range(n))
    y = daily_qty

    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(x[i] * y[i] for i in range(n))
    sum_x2 = sum(xi * xi for xi in x)

    denominator = n * sum_x2 - sum_x * sum_x
    if denominator == 0:
        avg = sum_y / n
        return int(avg * days / 30) if days != 30 else int(avg)

    m = (n * sum_xy - sum_x * sum_y) / denominator
    b = (sum_y - m * sum_x) / n

    last_x = n - 1
    forecast_per_day = m * (last_x + days / 2) + b
    forecast_total = (
        int(forecast_per_day * days / 30) if days != 30 else int(forecast_per_day)
    )
    return max(0, forecast_total)


def forecast_demand(
    product_id: str,
    days: int = 30,
    history_days: int = 90,
    db: Optional["Database"] = None,
) -> int:
    """
    Forecast demand for a product using linear regression on historical sales.

    Args:
        product_id: Product identifier (ArticulosCodigo)
        days: Number of days to forecast ahead
        history_days: Lookback window for regression
        db: Optional Database instance (creates one if omitted)

    Returns:
        Projected sales volume (integer) for the next ``days`` period
    """
    from ..core.database import Database

    end_date = date.today()
    start_date = end_date - timedelta(days=history_days)

    excluded_clause, excluded_codes = _excluded_docs_placeholders()
    sql = f"""
        SELECT
            Fecha,
            SUM(Cantidad) AS total_qty
        FROM banco_datos
        WHERE ArticulosCodigo = %s
          AND Fecha BETWEEN %s AND %s
          AND {excluded_clause}
        GROUP BY Fecha
        ORDER BY Fecha
    """  # nosec B608 — excluded codes come from Config

    def _run(conn: "Database") -> List[Dict[str, Any]]:
        rows = conn.execute_query(
            sql,
            (product_id, start_date.isoformat(), end_date.isoformat(), *excluded_codes),
        )
        return rows if isinstance(rows, list) else []

    if db is not None:
        rows = _run(db)
    else:
        with Database() as conn:
            rows = _run(conn)

    daily_qty = [float(r.get("total_qty") or 0) for r in rows]
    return _linear_forecast(daily_qty, days)


def get_top_products(
    limit: int = 10,
    lookback_days: int = 30,
    db: Optional["Database"] = None,
) -> List[Dict[str, Any]]:
    """Top-selling products by quantity in the last ``lookback_days``."""
    from ..core.database import Database

    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)
    safe_limit = max(1, min(int(limit), 100))

    excluded_clause, excluded_codes = _excluded_docs_placeholders()
    sql = f"""
        SELECT TOP {safe_limit}
            ArticulosCodigo AS product_id,
            ArticulosNombre AS product_name,
            SUM(Cantidad) AS total_qty
        FROM banco_datos
        WHERE Fecha BETWEEN %s AND %s
          AND {excluded_clause}
        GROUP BY ArticulosCodigo, ArticulosNombre
        ORDER BY total_qty DESC
    """  # nosec B608 — limit is bounded int; excluded codes from Config

    def _run(conn: "Database") -> List[Dict[str, Any]]:
        rows = conn.execute_query(
            sql, (start_date.isoformat(), end_date.isoformat(), *excluded_codes)
        )
        return rows if isinstance(rows, list) else []

    if db is not None:
        return _run(db)
    with Database() as conn:
        return _run(conn)


if __name__ == "__main__":
    import sys

    product = sys.argv[1] if len(sys.argv) > 1 else "TEST-ITEM-1"
    forecast_days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    result = forecast_demand(product, forecast_days)
    print(f"Forecast for {product} ({forecast_days} days): {result} units")
