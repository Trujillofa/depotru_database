#!/usr/bin/env python3
"""
Predictive analytics for demand forecasting.

Uses simple linear regression to forecast demand (sales velocity)
for the next N days based on historical Cantidad and Fecha.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import cast

try:
    from dotenv import load_dotenv

    _ = load_dotenv()
except ImportError:
    pass

import pymssql


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def get_connection():
    return pymssql.connect(
        server=require_env("DB_SERVER"),
        user=require_env("DB_USER"),
        password=require_env("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "SmartBusiness"),
        port=os.getenv("DB_PORT", "1433"),
        login_timeout=30,
        timeout=180,
    )


def forecast_demand(product_id: str, days: int = 30) -> int:
    """
    Forecast demand for a product using linear regression on historical sales.

    Args:
        product_id: Product identifier (ArticulosCodigo or similar)
        days: Number of days to forecast ahead

    Returns:
        Projected sales volume (integer) for the next `days` period
    """
    end_date = date.today()
    start_date = end_date - timedelta(days=90)  # Use 90 days of history

    sql = f"""
    SELECT
        Fecha,
        SUM(Cantidad) as total_qty
    FROM banco_datos
    WHERE ArticulosCodigo = '{product_id}'
      AND Fecha BETWEEN '{start_date.isoformat()}' AND '{end_date.isoformat()}'
      AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
    GROUP BY Fecha
    ORDER BY Fecha
    """

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        cursor.close()
    finally:
        conn.close()

    if not rows or len(rows) < 2:
        return 0

    # Simple linear regression: y = mx + b
    n = len(rows)
    x = list(range(n))
    y = [float(cast(float, row[1])) for row in rows]

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

    # Forecast for next `days` period
    last_x = n - 1
    forecast_per_day = m * (last_x + days / 2) + b
    forecast_total = (
        int(forecast_per_day * days / 30) if days != 30 else int(forecast_per_day)
    )

    return max(0, forecast_total)


def get_top_products(limit: int = 10) -> list[dict[str, object]]:
    """Get top-selling products by quantity in last 30 days."""
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    sql = f"""
    SELECT TOP {limit}
        ArticulosCodigo as product_id,
        ArticulosNombre as product_name,
        SUM(Cantidad) as total_qty
    FROM banco_datos
    WHERE Fecha BETWEEN '{start_date.isoformat()}' AND '{end_date.isoformat()}'
      AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
    GROUP BY ArticulosCodigo, ArticulosNombre
    ORDER BY total_qty DESC
    """

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        if cursor.description is None:
            return []
        columns = [str(col[0]) for col in cursor.description]
        rows = cursor.fetchall()
        cursor.close()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    product = sys.argv[1] if len(sys.argv) > 1 else "TEST-ITEM-1"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    result = forecast_demand(product, days)
    print(f"Forecast for {product} ({days} days): {result} units")
