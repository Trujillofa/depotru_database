#!/usr/bin/env python3
"""
Business Analysis Report - Category/Subcategory Analysis
Periodo: 202401-202512 (Jan 2024 - Dec 2025)
"""

import json
import os
import sys
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
    print(f"🔗 Connecting directly to {db_host}:{db_port}...")
    conn = pymssql.connect(
        server=db_host,
        port=db_port,
        user=db_username,
        password=db_password,
        database=database,
        login_timeout=30,
        timeout=120,
    )
    print(f"✅ Connected to database: {database}")
    return conn


def decimal_to_float(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def run_query(conn, sql, description):
    print(f"\n📊 Running: {description}")
    cursor = conn.cursor()
    cursor.execute(sql)
    columns = [desc[0] for desc in cursor.description]
    results = cursor.fetchall()
    cursor.close()
    return columns, results


def main():
    conn = None
    report = {
        "generated_at": datetime.now().isoformat(),
        "periodo": "202401-202512",
        "summary": {},
        "yearly_totals": [],
        "category_totals": [],
        "bestsellers": [],
        "most_profitable": [],
        "avg_ticket_by_category": [],
    }

    try:
        conn = get_connection()

        # 1. YEARLY TOTALS
        sql_yearly = """
        SELECT
            ano AS year,
            COUNT(DISTINCT marca) AS num_categories,
            COUNT(DISTINCT subcategoria) AS num_subcategories,
            COUNT(DISTINCT ArticulosCodigo) AS unique_products,
            SUM(Cantidad) AS net_units_sold,
            SUM(CASE WHEN Cantidad > 0 THEN Cantidad ELSE 0 END) AS gross_units_sold,
            SUM(CASE WHEN Cantidad < 0 THEN ABS(Cantidad) ELSE 0 END) AS units_returned,
            SUM(TotalMasIva) AS net_revenue,
            SUM(TotalMasIva - ValorCosto) AS net_profit,
            COUNT(DISTINCT VentaID) AS total_transactions,
            SUM(TotalMasIva) / NULLIF(COUNT(DISTINCT VentaID), 0) AS avg_ticket
        FROM [dbo].[banco_datos]
        WHERE ano IN (2024, 2025)
          AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
        GROUP BY ano
        ORDER BY ano
        """
        cols, rows = run_query(conn, sql_yearly, "Yearly Totals")
        for row in rows:
            report["yearly_totals"].append(
                dict(
                    zip(cols, [float(x) if isinstance(x, Decimal) else x for x in row])
                )
            )

        # 2. CATEGORY TOTALS BY YEAR
        sql_cat = """
        SELECT
            marca,
            ano AS year,
            COUNT(DISTINCT subcategoria) AS num_subcategories,
            COUNT(DISTINCT ArticulosCodigo) AS unique_products,
            SUM(Cantidad) AS net_units,
            SUM(CASE WHEN Cantidad > 0 THEN Cantidad ELSE 0 END) AS gross_units,
            SUM(CASE WHEN Cantidad < 0 THEN ABS(Cantidad) ELSE 0 END) AS returned_units,
            SUM(TotalMasIva) AS net_revenue,
            SUM(TotalMasIva - ValorCosto) AS net_profit,
            COUNT(DISTINCT VentaID) AS transactions,
            SUM(TotalMasIva) / NULLIF(COUNT(DISTINCT VentaID), 0) AS avg_ticket
        FROM [dbo].[banco_datos]
        WHERE ano IN (2024, 2025)
          AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
        GROUP BY marca, ano
        ORDER BY marca, ano
        """
        cols, rows = run_query(conn, sql_cat, "Category Totals by Year")
        for row in rows:
            report["category_totals"].append(
                dict(
                    zip(cols, [float(x) if isinstance(x, Decimal) else x for x in row])
                )
            )

        # 3. BESTSELLERS BY CATEGORY/SUBCATEGORY
        sql_best = """
        WITH SalesSummary AS (
            SELECT
                marca,
                subcategoria,
                ArticulosCodigo,
                ArticulosNombre,
                ano,
                SUM(Cantidad) AS net_cantidad,
                SUM(CASE WHEN Cantidad > 0 THEN Cantidad ELSE 0 END) AS gross_sales,
                SUM(CASE WHEN Cantidad < 0 THEN ABS(Cantidad) ELSE 0 END) AS returns,
                SUM(TotalMasIva) AS net_revenue,
                SUM(TotalMasIva - ValorCosto) AS net_profit
            FROM [dbo].[banco_datos]
            WHERE ano IN (2024, 2025)
              AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
            GROUP BY marca, subcategoria, ArticulosCodigo, ArticulosNombre, ano
            HAVING SUM(Cantidad) > 0
        ),
        RankedProducts AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY marca, subcategoria, ano
                    ORDER BY net_cantidad DESC
                ) AS rank_bestseller
            FROM SalesSummary
        )
        SELECT
            marca,
            subcategoria,
            ano AS year,
            ArticulosCodigo AS sku,
            ArticulosNombre AS product_name,
            net_cantidad AS net_units_sold,
            gross_sales,
            returns,
            net_revenue AS revenue,
            net_profit AS profit
        FROM RankedProducts
        WHERE rank_bestseller = 1
        ORDER BY marca, subcategoria, ano
        """
        cols, rows = run_query(conn, sql_best, "Bestsellers by Category/Subcategory")
        for row in rows:
            report["bestsellers"].append(
                dict(
                    zip(cols, [float(x) if isinstance(x, Decimal) else x for x in row])
                )
            )

        # 4. MOST PROFITABLE BY CATEGORY/SUBCATEGORY
        sql_profit = """
        WITH ProfitSummary AS (
            SELECT
                marca,
                subcategoria,
                ArticulosCodigo,
                ArticulosNombre,
                ano,
                SUM(Cantidad) AS net_cantidad,
                SUM(TotalMasIva) AS net_revenue,
                SUM(TotalMasIva - ValorCosto) AS net_profit,
                CASE
                    WHEN SUM(TotalMasIva) <> 0
                    THEN (SUM(TotalMasIva - ValorCosto) / ABS(SUM(TotalMasIva))) * 100
                    ELSE 0
                END AS profit_margin_pct
            FROM [dbo].[banco_datos]
            WHERE ano IN (2024, 2025)
              AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
            GROUP BY marca, subcategoria, ArticulosCodigo, ArticulosNombre, ano
            HAVING SUM(TotalMasIva) > 0
        ),
        RankedProfit AS (
            SELECT *,
                ROW_NUMBER() OVER (
                    PARTITION BY marca, subcategoria, ano
                    ORDER BY net_profit DESC
                ) AS rank_profit
            FROM ProfitSummary
        )
        SELECT
            marca,
            subcategoria,
            ano AS year,
            ArticulosCodigo AS sku,
            ArticulosNombre AS product_name,
            net_profit AS total_profit,
            profit_margin_pct AS margin_percentage,
            net_revenue AS revenue,
            net_cantidad AS net_units
        FROM RankedProfit
        WHERE rank_profit = 1
        ORDER BY marca, subcategoria, ano
        """
        cols, rows = run_query(
            conn, sql_profit, "Most Profitable by Category/Subcategory"
        )
        for row in rows:
            report["most_profitable"].append(
                dict(
                    zip(cols, [float(x) if isinstance(x, Decimal) else x for x in row])
                )
            )

        # 5. AVERAGE TICKET BY CATEGORY/SUBCATEGORY
        sql_ticket = """
        SELECT
            marca,
            subcategoria,
            ano AS year,
            COUNT(DISTINCT VentaID) AS num_transactions,
            SUM(TotalMasIva) AS net_revenue,
            SUM(TotalMasIva) / NULLIF(COUNT(DISTINCT VentaID), 0) AS avg_ticket,
            SUM(Cantidad) AS net_units,
            SUM(CASE WHEN Cantidad > 0 THEN Cantidad ELSE 0 END) AS gross_units,
            SUM(CASE WHEN Cantidad < 0 THEN ABS(Cantidad) ELSE 0 END) AS returned_units,
            SUM(TotalMasIva - ValorCosto) AS net_profit
        FROM [dbo].[banco_datos]
        WHERE ano IN (2024, 2025)
          AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
        GROUP BY marca, subcategoria, ano
        ORDER BY marca, subcategoria, ano
        """
        cols, rows = run_query(
            conn, sql_ticket, "Average Ticket by Category/Subcategory"
        )
        for row in rows:
            report["avg_ticket_by_category"].append(
                dict(
                    zip(cols, [float(x) if isinstance(x, Decimal) else x for x in row])
                )
            )

        # Save report
        output_file = "reports/data/analysis_report.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Report saved to: {output_file}")

        # Print summary
        print("\n" + "=" * 80)
        print("ANALYSIS REPORT SUMMARY - Periodo 202401-202512")
        print("=" * 80)

        print("\n📅 YEARLY TOTALS:")
        print("-" * 60)
        for y in report["yearly_totals"]:
            print(f"  Year {y['year']}:")
            print(f"    Revenue: ${y['net_revenue']:,.2f}")
            print(f"    Profit: ${y['net_profit']:,.2f}")
            print(f"    Units Sold (Net): {y['net_units_sold']:,.0f}")
            print(f"    Returns: {y['units_returned']:,.0f}")
            print(f"    Avg Ticket: ${y['avg_ticket']:,.2f}")
            print(f"    Transactions: {y['total_transactions']:,}")

        print(
            f"\n📦 CATEGORIES ANALYZED: {len(set(c['marca'] for c in report['category_totals']))}"
        )
        print(f"📁 SUBCATEGORIES: {len(report['avg_ticket_by_category'])}")
        print(f"🏆 BESTSELLERS FOUND: {len(report['bestsellers'])}")
        print(f"💰 PROFITABLE PRODUCTS: {len(report['most_profitable'])}")

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
