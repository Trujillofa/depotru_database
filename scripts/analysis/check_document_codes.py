#!/usr/bin/env python3
"""Check document codes and revenue breakdown"""
import pymssql

conn = pymssql.connect(
    server="190.60.235.209",
    port=1433,
    user="Consulta",
    password="Control*01",
    database="SmartBusiness",
    login_timeout=30,
    timeout=120,
)

cursor = conn.cursor()

print("="*80)
print("DOCUMENT CODES ANALYSIS - 2024")
print("="*80)

# Check all document codes and their revenue
sql = """
SELECT
    DocumentosCodigo,
    COUNT(*) as num_records,
    SUM(TotalMasIva) as total_revenue,
    SUM(TotalSinIva) as total_revenue_sin_iva,
    SUM(Cantidad) as total_quantity
FROM [dbo].[banco_datos]
WHERE ano = 2024
GROUP BY DocumentosCodigo
ORDER BY SUM(TotalMasIva) DESC
"""

cursor.execute(sql)
print("\nDocument Codes Breakdown:")
print("-"*80)
print(f"{'Code':<10} {'Records':>12} {'Revenue (IVA)':>20} {'Revenue (No IVA)':>20} {'Quantity':>15}")
print("-"*80)

total_all = 0
total_filtered = 0
excluded_codes = ['XY', 'AS', 'TS']
important_codes = ['DDD','DDT','DVD','DVE','FDD','FDT','FED','FET']

for row in cursor.fetchall():
    code = row[0]
    records = row[1]
    revenue_iva = float(row[2]) if row[2] else 0
    revenue_sin_iva = float(row[3]) if row[3] else 0
    qty = float(row[4]) if row[4] else 0

    total_all += revenue_iva
    if code not in excluded_codes:
        total_filtered += revenue_iva

    marker = ""
    if code in excluded_codes:
        marker = " [EXCLUDED]"
    elif code in important_codes:
        marker = " [IMPORTANT]"

    print(f"{code:<10} {records:>12,} ${revenue_iva:>18,.0f} ${revenue_sin_iva:>18,.0f} {qty:>15,.0f}{marker}")

print("-"*80)
print(f"{'TOTAL ALL':<10} ${total_all:>31,.0f}")
print(f"{'FILTERED':<10} ${total_filtered:>31,.0f} (excluding XY, AS, TS)")
print("="*80)

# Check if important codes exist
print("\n\nIMPORTANT CODES CHECK:")
print("-"*80)
for code in important_codes:
    cursor.execute(f"""
        SELECT COUNT(*), SUM(TotalMasIva)
        FROM [dbo].[banco_datos]
        WHERE ano = 2024 AND DocumentosCodigo = '{code}'
    """)
    row = cursor.fetchone()
    count = row[0] if row[0] else 0
    revenue = float(row[1]) if row[1] else 0
    status = "✓ FOUND" if count > 0 else "✗ NOT FOUND"
    print(f"{code}: {status} - {count:,} records, ${revenue:,.0f} revenue")

# Check total revenue with different filters
print("\n\nREVENUE COMPARISON:")
print("-"*80)

# No filter
cursor.execute("""
    SELECT SUM(TotalMasIva), SUM(TotalSinIva)
    FROM [dbo].[banco_datos]
    WHERE ano = 2024
""")
row = cursor.fetchone()
print(f"NO FILTER (all codes):            ${float(row[0]):>18,.0f} (con IVA)  ${float(row[1]):>18,.0f} (sin IVA)")

# Current filter (NOT IN XY, AS, TS)
cursor.execute("""
    SELECT SUM(TotalMasIva), SUM(TotalSinIva)
    FROM [dbo].[banco_datos]
    WHERE ano = 2024 AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
""")
row = cursor.fetchone()
print(f"CURRENT FILTER (NOT XY,AS,TS):    ${float(row[0]):>18,.0f} (con IVA)  ${float(row[1]):>18,.0f} (sin IVA)")

# With periodo filter
cursor.execute("""
    SELECT SUM(TotalMasIva), SUM(TotalSinIva)
    FROM [dbo].[banco_datos]
    WHERE periodo BETWEEN 202401 AND 202412 AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
""")
row = cursor.fetchone()
if row[0]:
    print(f"WITH PERIODO 202401-202412:       ${float(row[0]):>18,.0f} (con IVA)  ${float(row[1]):>18,.0f} (sin IVA)")

# Check periodo values
print("\n\nPERIODO ANALYSIS:")
print("-"*80)
cursor.execute("""
    SELECT MIN(periodo), MAX(periodo), COUNT(DISTINCT periodo)
    FROM [dbo].[banco_datos]
    WHERE ano = 2024
""")
row = cursor.fetchone()
print(f"2024 Periodo range: {row[0]} to {row[1]} ({row[2]} distinct values)")

cursor.execute("""
    SELECT periodo, COUNT(*), SUM(TotalMasIva)
    FROM [dbo].[banco_datos]
    WHERE ano = 2024
    GROUP BY periodo
    ORDER BY periodo
""")
print("\nMonthly breakdown 2024:")
for row in cursor.fetchall():
    print(f"  Periodo {row[0]}: {row[1]:,} records, ${float(row[2]):,.0f}")

cursor.close()
conn.close()
