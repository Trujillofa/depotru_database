#!/usr/bin/env python3
"""
Investigation: DEPOSITO TRUJILLO SAS transactions
Check what sales are attributed to this customer
"""

import pymssql
import json
from datetime import datetime
from decimal import Decimal

# Database connection
db_host = "190.60.235.209"
db_port = 1433
db_username = "Consulta"
db_password = "Control*01"
database = "SmartBusiness"

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

def to_float(val):
    if val is None:
        return 0.0
    if isinstance(val, Decimal):
        return float(val)
    return float(val)

def main():
    conn = None
    try:
        conn = get_connection()

        # 1. Check DEPOSITO TRUJILLO SAS transactions
        print("\n" + "="*80)
        print("DEPOSITO TRUJILLO SAS - Transaction Analysis")
        print("="*80)

        sql_deposito = """
        SELECT
            ano AS year,
            mes AS month,
            DocumentosCodigo AS doc_code,
            VentaID AS sale_id,
            Fecha AS date,
            ArticulosCodigo AS sku,
            ArticulosNombre AS product,
            Cantidad AS quantity,
            TotalSinIva AS revenue,
            ValorCosto AS cost,
            TotalSinIva - ValorCosto AS profit,
            proveedor AS vendor,
            subcategoria
        FROM [dbo].[banco_datos]
        WHERE categoria = 'PRODUCTOS SIKA'
          AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
          AND ano IN (2024, 2025)
          AND TercerosNombres = 'DEPOSITO TRUJILLO SAS'
        ORDER BY Fecha DESC
        """

        cursor = conn.cursor()
        cursor.execute(sql_deposito)
        columns = [desc[0] for desc in cursor.description]
        results = cursor.fetchall()
        cursor.close()

        print(f"\n📊 Total transactions found: {len(results)}")

        if results:
            # Summary by year
            summary_2024 = {
                'transactions': 0,
                'revenue': 0,
                'profit': 0,
                'units': 0
            }
            summary_2025 = {
                'transactions': 0,
                'revenue': 0,
                'profit': 0,
                'units': 0
            }

            doc_codes = set()

            print("\n📋 Sample Transactions (First 20):")
            print("-" * 150)
            print(f"{'Date':<12} {'Year':<6} {'Month':<6} {'Doc':<6} {'SKU':<15} {'Product':<40} {'Qty':<8} {'Revenue':<15} {'Vendor':<20}")
            print("-" * 150)

            for i, row in enumerate(results[:20]):
                data = dict(zip(columns, row))
                print(f"{str(data['date']):<12} {data['year']:<6} {data['month']:<6} {data['doc_code']:<6} {data['sku']:<15} {str(data['product'])[:40]:<40} {to_float(data['quantity']):<8.0f} ${to_float(data['revenue']):<14,.0f} {str(data['vendor']):<20}")

            print("-" * 150)

            # Calculate summaries
            for row in results:
                data = dict(zip(columns, row))
                year = data['year']
                revenue = to_float(data['revenue'])
                profit = to_float(data['profit'])
                qty = to_float(data['quantity'])
                doc_codes.add(data['doc_code'])

                if year == 2024:
                    summary_2024['transactions'] += 1
                    summary_2024['revenue'] += revenue
                    summary_2024['profit'] += profit
                    summary_2024['units'] += qty
                elif year == 2025:
                    summary_2025['transactions'] += 1
                    summary_2025['revenue'] += revenue
                    summary_2025['profit'] += profit
                    summary_2025['units'] += qty

            print("\n📈 SUMMARY BY YEAR:")
            print("\n2024:")
            print(f"  Transactions: {summary_2024['transactions']:,}")
            print(f"  Revenue: ${summary_2024['revenue']:,.0f}")
            print(f"  Profit: ${summary_2024['profit']:,.0f}")
            print(f"  Units: {summary_2024['units']:,.0f}")

            print("\n2025:")
            print(f"  Transactions: {summary_2025['transactions']:,}")
            print(f"  Revenue: ${summary_2025['revenue']:,.0f}")
            print(f"  Profit: ${summary_2025['profit']:,.0f}")
            print(f"  Units: {summary_2025['units']:,.0f}")

            print(f"\n📝 Document Codes Found: {', '.join(sorted(doc_codes))}")

        # 2. Check ALL providers for PRODUCTOS SIKA category
        print("\n" + "="*80)
        print("PRODUCTOS SIKA - Provider Verification")
        print("="*80)

        sql_providers = """
        SELECT DISTINCT
            proveedor,
            COUNT(DISTINCT ArticulosCodigo) AS num_products,
            COUNT(*) AS num_transactions,
            SUM(TotalSinIva) AS total_revenue
        FROM [dbo].[banco_datos]
        WHERE categoria = 'PRODUCTOS SIKA'
          AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
          AND ano IN (2024, 2025)
        GROUP BY proveedor
        ORDER BY SUM(TotalSinIva) DESC
        """

        cursor = conn.cursor()
        cursor.execute(sql_providers)
        results = cursor.fetchall()
        cursor.close()

        print(f"\n📊 Total unique providers found: {len(results)}")
        print("\nProvider Details:")
        print("-" * 100)
        print(f"{'Provider':<30} {'Products':<12} {'Transactions':<15} {'Revenue':<20}")
        print("-" * 100)

        total_revenue = 0
        for row in results:
            provider = row[0] if row[0] else "NULL/Unknown"
            products = int(row[1])
            transactions = int(row[2])
            revenue = to_float(row[3])
            total_revenue += revenue
            print(f"{str(provider):<30} {products:<12} {transactions:<15,} ${revenue:<19,.0f}")

        print("-" * 100)
        print(f"{'TOTAL':<30} {'':<12} {'':<15} ${total_revenue:<19,.0f}")
        print("-" * 100)

        # Calculate percentage for each provider
        print("\nProvider Market Share:")
        for row in results:
            provider = row[0] if row[0] else "NULL/Unknown"
            revenue = to_float(row[3])
            percentage = (revenue / total_revenue * 100) if total_revenue > 0 else 0
            print(f"  {provider}: {percentage:.2f}%")

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
