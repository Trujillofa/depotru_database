"""
Metabase Connection Diagnostic Tool
====================================
Run this to diagnose why Metabase shows different data than DBeaver.

Usage:
    python test_metabase_connection.py
"""

import pytest

# Skip this module if pymssql is not installed
pytest.importorskip("pymssql")

import pymssql

from config import Config

# YOUR CONNECTION DETAILS - Match what you use in Metabase!
HOST = "your-server"  # Replace with your server
PORT = 1433
USER = "your-username"  # Replace with your username
PASSWORD = "your-password"  # Replace with your password
DATABASE = Config.DB_NAME  # Should be 'SmartBusiness'

print("=" * 70)
print("METABASE CONNECTION DIAGNOSTIC TOOL")
print("=" * 70)
print()
print("Testing connection with settings:")
print(f"  Host: {HOST}")
print(f"  Port: {PORT}")
print(f"  Database: {DATABASE}")
print(f"  User: {USER}")
print()
print("Make sure these EXACT settings are used in Metabase!")
print()

try:
    print("[1/5] Connecting to SQL Server...")
    conn = pymssql.connect(
        server=HOST, port=PORT, user=USER, password=PASSWORD, database=DATABASE
    )
    print("  ✓ Connection successful!")
    print()

    cursor = conn.cursor(as_dict=True)

    # Check 1: Verify current database
    print("[2/5] Checking current database...")
    cursor.execute("SELECT DB_NAME() as current_db")
    result = cursor.fetchone()
    current_db = result["current_db"]
    print(f"  Current database: {current_db}")

    if current_db != DATABASE:
        print(f"  ⚠️  WARNING: Connected to '{current_db}' but expected '{DATABASE}'!")
        print(f"  This is likely your problem!")
    else:
        print(f"  ✓ Correct database!")
    print()

    # Check 2: List all tables
    print("[3/5] Listing all tables in current database...")
    cursor.execute(
        """
        SELECT
            TABLE_SCHEMA,
            TABLE_NAME,
            TABLE_TYPE
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_SCHEMA, TABLE_NAME
    """
    )

    tables = cursor.fetchall()
    print(f"  Found {len(tables)} tables:")

    for table in tables[:15]:  # Show first 15
        print(f"    - {table['TABLE_SCHEMA']}.{table['TABLE_NAME']}")

    if len(tables) > 15:
        print(f"    ... and {len(tables) - 15} more tables")
    print()

    # Check 3: Verify banco_datos exists
    print("[4/5] Checking banco_datos table...")
    banco_datos_exists = any(t["TABLE_NAME"] == "banco_datos" for t in tables)

    if banco_datos_exists:
        print("  ✓ banco_datos table found!")

        # Get row count
        cursor.execute("SELECT COUNT(*) as total FROM banco_datos")
        total_result = cursor.fetchone()
        total_rows = total_result["total"]
        print(f"  Total rows: {total_rows:,}")

        # Get filtered count (excluding XY, AS, TS)
        cursor.execute(
            """
            SELECT COUNT(*) as filtered
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
        """
        )
        filtered_result = cursor.fetchone()
        filtered_rows = filtered_result["filtered"]
        print(f"  Filtered rows (excl. XY/AS/TS): {filtered_rows:,}")

        # Get sample data
        cursor.execute("SELECT TOP 3 * FROM banco_datos")
        samples = cursor.fetchall()
        print(f"  Sample columns: {', '.join(samples[0].keys())}")

    else:
        print("  ❌ banco_datos table NOT FOUND!")
        print("  This is your problem - wrong database!")
    print()

    # Check 4: List all databases
    print("[5/5] Listing all available databases...")
    cursor.execute(
        """
        SELECT name FROM sys.databases
        WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb')
        ORDER BY name
    """
    )
    databases = cursor.fetchall()
    print(f"  Available databases:")
    for db in databases:
        marker = " ← YOU ARE HERE" if db["name"] == current_db else ""
        marker += " ← METABASE SHOULD USE THIS" if db["name"] == "SmartBusiness" else ""
        print(f"    - {db['name']}{marker}")
    print()

    conn.close()

    # Final diagnosis
    print("=" * 70)
    print("DIAGNOSIS")
    print("=" * 70)
    print()

    if current_db == DATABASE and banco_datos_exists:
        print("✅ Everything looks good!")
        print()
        print("If Metabase still shows wrong data:")
        print("  1. Go to Metabase Admin → Databases")
        print("  2. Click 'Sync database schema now'")
        print("  3. Click 'Re-scan field values now'")
        print("  4. Wait 2-3 minutes")
        print("  5. Refresh page")
    elif current_db != DATABASE:
        print(f"❌ PROBLEM FOUND: Wrong database!")
        print()
        print(f"You connected to: {current_db}")
        print(f"Should connect to: {DATABASE}")
        print()
        print("FIX IN METABASE:")
        print("  1. Go to Metabase Admin → Databases")
        print("  2. Click on your SQL Server connection")
        print(f"  3. Change 'Database name' to: {DATABASE}")
        print("  4. Click 'Save'")
        print("  5. Click 'Sync database schema now'")
    elif not banco_datos_exists:
        print(f"❌ PROBLEM FOUND: banco_datos table not in {current_db}")
        print()
        print("Possible causes:")
        print("  1. Wrong database selected")
        print("  2. User doesn't have permissions")
        print("  3. Table is in different schema")
        print()
        print("Try:")
        print("  - Check database name in Metabase")
        print("  - Check user permissions")
        print(f"  - Verify table exists: SELECT * FROM {DATABASE}.dbo.banco_datos")

    print()
    print("=" * 70)

except pymssql.OperationalError as e:
    print(f"❌ Connection failed: {e}")
    print()
    print("Common causes:")
    print("  1. Wrong host/port")
    print("  2. Wrong username/password")
    print("  3. SQL Server not accepting remote connections")
    print("  4. Firewall blocking port 1433")
    print()
    print("Check:")
    print(f"  - Host: {HOST}")
    print(f"  - Port: {PORT}")
    print(f"  - User: {USER}")
    print("  - Can you connect with DBeaver?")

except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback

    traceback.print_exc()

print()
print("Need help? Share this output!")
