#!/usr/bin/env python3
"""
PRODUCTOS SIKA Analysis - Comprehensive Report
Focus: Customers, Vendors, Monthly Trends (2024 vs 2025)
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

import pymssql

# SECURITY: Load credentials from environment variables
# Set these before running:
#   export DB_SERVER="your-server"
#   export DB_USER="your-user"
#   export DB_PASSWORD="your-password"
db_host = os.environ.get("DB_SERVER")
db_port = int(os.environ.get("DB_PORT", "1433"))
db_username = os.environ.get("DB_USER")
db_password = os.environ.get("DB_PASSWORD")
database = os.environ.get("DB_NAME", "SmartBusiness")

if not all([db_host, db_username, db_password]):
    print("ERROR: Missing required environment variables")
    print("Please set: DB_SERVER, DB_USER, DB_PASSWORD")
    sys.exit(1)


def get_connection():
    print(f"🔗 Connecting to {db_host}:{db_port}...")
    conn = pymssql.connect(
        server=db_host,
        port=db_port,
        user=db_username,
        password=db_password,
        database=database,
        login_timeout=30,
        timeout=180,
    )
    print(f"✅ Connected to database: {database}")
    return conn


def run_query(conn, sql, description):
    print(f"\n📊 {description}...")
    cursor = conn.cursor()
    cursor.execute(sql)
    columns = [desc[0] for desc in cursor.description]
    results = cursor.fetchall()
    cursor.close()
    return columns, results


def to_float(val):
    if val is None:
        return 0.0
    if isinstance(val, Decimal):
        return float(val)
    return float(val)


def main():
    conn = None
    report = {
        "generated_at": datetime.now().isoformat(),
        "filter": "categoria = 'PRODUCTOS SIKA' (excluding internal transactions)",
        "exclusions": "DEPOSITO TRUJILLO SAS (internal), Document codes: YX, ISC (inventory adjustments)",
        "provider": "SIKA (implicit - category defined by provider)",
        "period": "2024-2025",
        "summary": {},
        "monthly_sales": [],
        "top_customers": [],
        "customer_segments": [],
        "bestsellers": [],
        "most_profitable": [],
        "subcategory_performance": [],
        "insights": [],
    }

    try:
        conn = get_connection()

        # 1. OVERALL SUMMARY
        sql_summary = """
        SELECT
            ano AS year,
            COUNT(DISTINCT TercerosNombres) AS unique_customers,
            COUNT(DISTINCT proveedor) AS unique_vendors,
            COUNT(DISTINCT subcategoria) AS subcategories,
            COUNT(DISTINCT ArticulosCodigo) AS unique_products,
            SUM(Cantidad) AS net_units,
            SUM(CASE WHEN Cantidad > 0 THEN Cantidad ELSE 0 END) AS gross_units,
            SUM(CASE WHEN Cantidad < 0 THEN ABS(Cantidad) ELSE 0 END) AS returns,
            SUM(TotalSinIva) AS net_revenue,
            SUM(TotalSinIva) AS net_revenue_sin_iva,
            SUM(TotalSinIva - ValorCosto) AS net_profit,
            COUNT(DISTINCT VentaID) AS transactions,
            AVG(TotalSinIva) AS avg_transaction_value
        FROM [dbo].[banco_datos]
        WHERE categoria = 'PRODUCTOS SIKA'
          AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
          AND TercerosNombres != 'DEPOSITO TRUJILLO SAS'
          AND ano IN (2024, 2025)
        GROUP BY ano
        ORDER BY ano
        """
        cols, rows = run_query(conn, sql_summary, "Overall Summary")
        for row in rows:
            summary = dict(
                zip(
                    cols,
                    [
                        to_float(x) if isinstance(x, (Decimal, float)) else x
                        for x in row
                    ],
                )
            )
            report["summary"][int(summary["year"])] = summary

        # 2. MONTHLY SALES COMPARISON
        sql_monthly = """
        SELECT
            ano AS year,
            mes AS month,
            COUNT(DISTINCT TercerosNombres) AS customers,
            COUNT(DISTINCT VentaID) AS transactions,
            SUM(Cantidad) AS net_units,
            SUM(TotalSinIva) AS revenue,
            SUM(TotalSinIva - ValorCosto) AS profit,
            AVG(TotalSinIva - ValorCosto) / NULLIF(AVG(TotalSinIva), 0) * 100 AS margin_pct
        FROM [dbo].[banco_datos]
        WHERE categoria = 'PRODUCTOS SIKA'
          AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
          AND TercerosNombres != 'DEPOSITO TRUJILLO SAS'
          AND ano IN (2024, 2025)
        GROUP BY ano, mes
        ORDER BY ano, mes
        """
        cols, rows = run_query(conn, sql_monthly, "Monthly Sales")
        for row in rows:
            report["monthly_sales"].append(
                dict(
                    zip(
                        cols,
                        [
                            to_float(x) if isinstance(x, (Decimal, float)) else x
                            for x in row
                        ],
                    )
                )
            )

        # 3. TOP CUSTOMERS BY REVENUE
        sql_customers = """
        SELECT TOP 50
            TercerosNombres AS customer_name,
            TercerosIdentificacion AS customer_id,
            ano AS year,
            COUNT(DISTINCT VentaID) AS num_orders,
            SUM(Cantidad) AS total_units,
            SUM(TotalSinIva) AS total_revenue,
            SUM(TotalSinIva - ValorCosto) AS total_profit,
            AVG(TotalSinIva) AS avg_order_value,
            MIN(Fecha) AS first_purchase,
            MAX(Fecha) AS last_purchase
        FROM [dbo].[banco_datos]
        WHERE categoria = 'PRODUCTOS SIKA'
          AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
          AND TercerosNombres != 'DEPOSITO TRUJILLO SAS'
          AND ano IN (2024, 2025)
        GROUP BY TercerosNombres, TercerosIdentificacion, ano
        ORDER BY SUM(TotalSinIva) DESC
        """
        cols, rows = run_query(conn, sql_customers, "Top Customers")
        for row in rows:
            report["top_customers"].append(
                dict(
                    zip(
                        cols,
                        [
                            to_float(x)
                            if isinstance(x, (Decimal, float))
                            else str(x)
                            if not isinstance(x, (int, str, type(None)))
                            else x
                            for x in row
                        ],
                    )
                )
            )

        # 4. CUSTOMER SEGMENTATION
        sql_segments = """
        WITH CustomerMetrics AS (
            SELECT
                TercerosNombres,
                ano,
                COUNT(DISTINCT VentaID) AS num_orders,
                SUM(TotalSinIva) AS total_revenue,
                AVG(TotalSinIva) AS avg_order
            FROM [dbo].[banco_datos]
            WHERE categoria = 'PRODUCTOS SIKA'
              AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
          AND TercerosNombres != 'DEPOSITO TRUJILLO SAS'
              AND ano IN (2024, 2025)
            GROUP BY TercerosNombres, ano
        ),
        Segments AS (
            SELECT
                ano,
                CASE
                    WHEN total_revenue >= 50000000 THEN 'VIP (>50M)'
                    WHEN total_revenue >= 10000000 THEN 'High Value (10M-50M)'
                    WHEN total_revenue >= 5000000 THEN 'Medium (5M-10M)'
                    WHEN total_revenue >= 1000000 THEN 'Regular (1M-5M)'
                    ELSE 'Occasional (<1M)'
                END AS segment,
                COUNT(*) AS num_customers,
                SUM(total_revenue) AS segment_revenue,
                AVG(total_revenue) AS avg_revenue_per_customer,
                SUM(num_orders) AS total_orders
            FROM CustomerMetrics
            GROUP BY ano,
                CASE
                    WHEN total_revenue >= 50000000 THEN 'VIP (>50M)'
                    WHEN total_revenue >= 10000000 THEN 'High Value (10M-50M)'
                    WHEN total_revenue >= 5000000 THEN 'Medium (5M-10M)'
                    WHEN total_revenue >= 1000000 THEN 'Regular (1M-5M)'
                    ELSE 'Occasional (<1M)'
                END
        )
        SELECT * FROM Segments
        ORDER BY ano, segment_revenue DESC
        """
        cols, rows = run_query(conn, sql_segments, "Customer Segmentation")
        for row in rows:
            report["customer_segments"].append(
                dict(
                    zip(
                        cols,
                        [
                            to_float(x) if isinstance(x, (Decimal, float)) else x
                            for x in row
                        ],
                    )
                )
            )

        # 5. BESTSELLERS BY SUBCATEGORY
        sql_bestsellers = """
        WITH ProductSales AS (
            SELECT
                subcategoria,
                ArticulosCodigo,
                ArticulosNombre,
                ano,
                SUM(Cantidad) AS net_units,
                SUM(TotalSinIva) AS revenue,
                SUM(TotalSinIva - ValorCosto) AS profit,
                COUNT(DISTINCT TercerosNombres) AS unique_customers
            FROM [dbo].[banco_datos]
            WHERE categoria = 'PRODUCTOS SIKA'
              AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
          AND TercerosNombres != 'DEPOSITO TRUJILLO SAS'
              AND ano IN (2024, 2025)
            GROUP BY subcategoria, ArticulosCodigo, ArticulosNombre, ano
            HAVING SUM(Cantidad) > 0
        ),
        Ranked AS (
            SELECT *,
                ROW_NUMBER() OVER (PARTITION BY subcategoria, ano ORDER BY net_units DESC) AS rank
            FROM ProductSales
        )
        SELECT
            subcategoria,
            ano AS year,
            ArticulosCodigo AS sku,
            ArticulosNombre AS product_name,
            net_units,
            revenue,
            profit,
            unique_customers
        FROM Ranked
        WHERE rank = 1
        ORDER BY ano, revenue DESC
        """
        cols, rows = run_query(conn, sql_bestsellers, "Bestsellers by Subcategory")
        for row in rows:
            report["bestsellers"].append(
                dict(
                    zip(
                        cols,
                        [
                            to_float(x) if isinstance(x, (Decimal, float)) else x
                            for x in row
                        ],
                    )
                )
            )

        # 6. MOST PROFITABLE PRODUCTS
        sql_profitable = """
        SELECT TOP 30
            subcategoria,
            ArticulosCodigo AS sku,
            ArticulosNombre AS product_name,
            ano AS year,
            SUM(Cantidad) AS net_units,
            SUM(TotalSinIva) AS revenue,
            SUM(TotalSinIva - ValorCosto) AS profit,
            (SUM(TotalSinIva - ValorCosto) / NULLIF(SUM(TotalSinIva), 0)) * 100 AS margin_pct,
            COUNT(DISTINCT TercerosNombres) AS unique_customers
        FROM [dbo].[banco_datos]
        WHERE categoria = 'PRODUCTOS SIKA'
          AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
          AND TercerosNombres != 'DEPOSITO TRUJILLO SAS'
          AND ano IN (2024, 2025)
        GROUP BY subcategoria, ArticulosCodigo, ArticulosNombre, ano
        HAVING SUM(TotalSinIva) > 0
        ORDER BY SUM(TotalSinIva - ValorCosto) DESC
        """
        cols, rows = run_query(conn, sql_profitable, "Most Profitable Products")
        for row in rows:
            report["most_profitable"].append(
                dict(
                    zip(
                        cols,
                        [
                            to_float(x) if isinstance(x, (Decimal, float)) else x
                            for x in row
                        ],
                    )
                )
            )

        # 7. SUBCATEGORY PERFORMANCE
        sql_subcat = """
        SELECT
            subcategoria,
            ano AS year,
            COUNT(DISTINCT ArticulosCodigo) AS num_products,
            COUNT(DISTINCT TercerosNombres) AS num_customers,
            SUM(Cantidad) AS net_units,
            SUM(TotalSinIva) AS revenue,
            SUM(TotalSinIva - ValorCosto) AS profit,
            (SUM(TotalSinIva - ValorCosto) / NULLIF(SUM(TotalSinIva), 0)) * 100 AS margin_pct,
            COUNT(DISTINCT VentaID) AS transactions
        FROM [dbo].[banco_datos]
        WHERE categoria = 'PRODUCTOS SIKA'
          AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
          AND TercerosNombres != 'DEPOSITO TRUJILLO SAS'
          AND ano IN (2024, 2025)
        GROUP BY subcategoria, ano
        ORDER BY ano, SUM(TotalSinIva) DESC
        """
        cols, rows = run_query(conn, sql_subcat, "Subcategory Performance")
        for row in rows:
            report["subcategory_performance"].append(
                dict(
                    zip(
                        cols,
                        [
                            to_float(x) if isinstance(x, (Decimal, float)) else x
                            for x in row
                        ],
                    )
                )
            )

        # Save JSON report
        output_json = "reports/data/sika_analysis_report.json"
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\n✅ JSON Report saved to: {output_json}")

        # Generate insights
        print("\n" + "=" * 80)
        print("PRODUCTOS SIKA ANALYSIS - KEY METRICS")
        print("=" * 80)

        for year in [2024, 2025]:
            if year in report["summary"]:
                s = report["summary"][year]
                print(f"\n📅 YEAR {year}:")
                print(f"  Revenue: ${s['net_revenue']:,.0f}")
                print(
                    f"  Profit: ${s['net_profit']:,.0f} (Margin: {(s['net_profit']/s['net_revenue']*100):.1f}%)"
                )
                print(f"  Customers: {int(s['unique_customers']):,}")
                print(f"  Vendors: {int(s['unique_vendors']):,}")
                print(f"  Transactions: {int(s['transactions']):,}")
                print(f"  Avg Transaction: ${s['avg_transaction_value']:,.0f}")

        # YoY comparison
        if 2024 in report["summary"] and 2025 in report["summary"]:
            s24 = report["summary"][2024]
            s25 = report["summary"][2025]
            rev_growth = (
                (s25["net_revenue"] - s24["net_revenue"]) / s24["net_revenue"] * 100
            )
            profit_growth = (
                (s25["net_profit"] - s24["net_profit"]) / s24["net_profit"] * 100
            )
            cust_growth = (
                (s25["unique_customers"] - s24["unique_customers"])
                / s24["unique_customers"]
                * 100
            )

            print(f"\n📈 YoY GROWTH (2024→2025):")
            print(f"  Revenue: {rev_growth:+.1f}%")
            print(f"  Profit: {profit_growth:+.1f}%")
            print(f"  Customers: {cust_growth:+.1f}%")

        print(f"\n📦 Product Portfolio:")
        print(
            f"  Subcategories: {len(set(p['subcategoria'] for p in report['subcategory_performance']))}"
        )
        print(
            f"  Total SKUs: {report['summary'][2024]['unique_products'] if 2024 in report['summary'] else 0}"
        )

        return report

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        if conn:
            conn.close()
            print("\n🔒 Connection closed")


if __name__ == "__main__":
    main()
