#!/usr/bin/env python3
"""
Anomaly Detection Background Worker.

Compares yesterday's sales vs 30-day moving average.
If drop > threshold_pct, logs alert (no Telegram/WhatsApp bot).
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass

import pymssql


def to_float(value: object) -> float:
    """Convert DB scalar values to float safely."""
    if isinstance(value, (int, float, Decimal, str, bytes)):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


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


def check_anomaly(days: int = 1, threshold_pct: float = 20.0) -> bool:
    """
    Check for sales anomalies.
    Returns True if anomaly detected (drop > threshold_pct).
    """
    yesterday = date.today() - timedelta(days=days)
    month_ago = yesterday - timedelta(days=30)

    sql = f"""
    SELECT
        SUM(TotalMasIva) as total_sales
    FROM banco_datos
    WHERE Fecha = '{yesterday.isoformat()}'
      AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
    """

    sql_avg = f"""
    SELECT
        AVG(TotalMasIva) as avg_sales
    FROM (
        SELECT SUM(TotalMasIva) as TotalMasIva
        FROM banco_datos
        WHERE Fecha BETWEEN '{month_ago.isoformat()}' AND '{yesterday.isoformat()}'
          AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
        GROUP BY Fecha
    ) t
    """

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        row = cursor.fetchone()
        yesterday_sales = to_float(row[0]) if row else 0.0

        cursor.execute(sql_avg)
        row = cursor.fetchone()
        avg_sales = to_float(row[0]) if row else 0.0

        cursor.close()
    finally:
        conn.close()

    if avg_sales == 0:
        print(
            f"[ANOMALY] Yesterday sales: ${yesterday_sales:,.2f}, 30-day avg: N/A (no data)"
        )
        return False

    drop_pct = ((avg_sales - yesterday_sales) / avg_sales) * 100

    if drop_pct > threshold_pct:
        print(
            f"[ANOMALY] Yesterday sales: ${yesterday_sales:,.2f}, 30-day avg: ${avg_sales:,.2f}, drop: {drop_pct:.1f}% > {threshold_pct:.1f}%"
        )
        return True
    else:
        print(
            f"[OK] Yesterday sales: ${yesterday_sales:,.2f}, 30-day avg: ${avg_sales:,.2f}, drop: {drop_pct:.1f}%"
        )
        return False


if __name__ == "__main__":
    anomaly = check_anomaly(days=1, threshold_pct=20.0)
    sys.exit(0 if not anomaly else 1)
