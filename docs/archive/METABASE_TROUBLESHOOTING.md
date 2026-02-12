# Metabase + SQL Server Connection Troubleshooting

## Issue: Tables appear empty or different from DBeaver

This is a common issue when Metabase connects to the wrong schema or database.

---

## Quick Diagnosis

### 1. Check Which Database Metabase Connected To

In Metabase:
1. Go to **Admin Settings** (gear icon) → **Databases**
2. Click on your SQL Server connection
3. Check the **Database name** field

**Common Issues:**
- ❌ Connected to `master` instead of `SmartBusiness`
- ❌ Connected to wrong database instance
- ❌ Schema not specified

---

## Solution #1: Fix Database Name (Most Common)

### Step 1: Verify Correct Database
In DBeaver, run:
```sql
-- Check which database you're using
SELECT DB_NAME() as current_database;

-- List all databases
SELECT name FROM sys.databases;

-- Check your actual data
SELECT TOP 5 * FROM SmartBusiness.dbo.banco_datos;
```

### Step 2: Update Metabase Connection

In Metabase Admin → Databases:

```
Host: your-server-address
Port: 1433
Database name: SmartBusiness  ← MAKE SURE THIS IS CORRECT!
Username: your-username
Password: your-password

Additional JDBC options:
instance=your-instance-name (if using named instance)
```

### Step 3: Specify Schema in Instance Filter

Scroll down to **Advanced options** in Metabase:

```
Schema filters (patterns):
Include: dbo
```

This tells Metabase to only show tables from the `dbo` schema.

---

## Solution #2: Check Connection String

### SQL Server Connection String Format

Metabase needs the correct format:

**Standard Instance:**
```
Server: your-server.com
Port: 1433
Database: SmartBusiness
```

**Named Instance:**
```
Server: your-server.com\INSTANCENAME
Port: (leave empty or use dynamic port)
Database: SmartBusiness
```

**With Additional Options:**
```
Additional JDBC options:
encrypt=false;trustServerCertificate=true;
```

---

## Solution #3: Test Connection Manually

### Create Test Connection Script

```python
# test_metabase_connection.py
import pymssql

# Use the EXACT same credentials as Metabase
conn = pymssql.connect(
    server='your-server',
    port=1433,
    user='your-username',
    password='your-password',
    database='SmartBusiness',  # ← Make sure this matches!
)

cursor = conn.cursor()

# List all tables in current database
cursor.execute("""
    SELECT
        TABLE_SCHEMA,
        TABLE_NAME,
        TABLE_TYPE
    FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_TYPE = 'BASE TABLE'
    ORDER BY TABLE_SCHEMA, TABLE_NAME
""")

print("Tables in current database:")
for row in cursor.fetchall():
    print(f"  {row[0]}.{row[1]}")

# Check banco_datos specifically
cursor.execute("""
    SELECT COUNT(*) as row_count
    FROM banco_datos
    WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
""")
result = cursor.fetchone()
print(f"\nbanco_datos rows (filtered): {result[0]:,}")

conn.close()
print("\n✓ Connection successful!")
```

Run it:
```bash
python test_metabase_connection.py
```

Compare the output with what you see in Metabase.

---

## Solution #4: Check User Permissions

The user account Metabase uses might not have permissions to see all tables.

### Check Permissions
```sql
-- Run in DBeaver as admin
USE SmartBusiness;

-- Check what schemas the user can see
SELECT
    dp.name AS principal_name,
    dp.type_desc AS principal_type,
    o.name AS object_name,
    p.permission_name,
    p.state_desc
FROM sys.database_permissions AS p
JOIN sys.database_principals AS dp ON p.grantee_principal_id = dp.principal_id
JOIN sys.objects AS o ON p.major_id = o.object_id
WHERE dp.name = 'your-metabase-username'
ORDER BY o.name;

-- Grant permissions if needed (run as admin)
GRANT SELECT ON SCHEMA::dbo TO [your-metabase-username];
GRANT SELECT ON banco_datos TO [your-metabase-username];
```

---

## Solution #5: Metabase Sync Issues

Sometimes Metabase cache gets out of sync.

### Force Resync

1. Go to **Admin** → **Databases**
2. Click on your SQL Server database
3. Scroll down and click **Sync database schema now**
4. Click **Re-scan field values now**
5. Wait 2-5 minutes
6. Refresh the page

---

## Solution #6: Check for Multiple Schemas

Your database might have multiple schemas, and Metabase is showing the wrong one.

### Identify All Schemas
```sql
-- In DBeaver
SELECT
    s.name AS schema_name,
    COUNT(t.TABLE_NAME) AS table_count
FROM sys.schemas s
LEFT JOIN INFORMATION_SCHEMA.TABLES t ON s.name = t.TABLE_SCHEMA
WHERE t.TABLE_TYPE = 'BASE TABLE' OR t.TABLE_TYPE IS NULL
GROUP BY s.name
ORDER BY table_count DESC;
```

### Configure Metabase to See Correct Schema

In Metabase connection settings, under **Advanced options**:

```
Schema filters (patterns):
Include only: dbo

Or if your tables are in different schema:
Include only: your_schema_name
```

---

## Solution #7: Use Fully Qualified Names

When creating queries in Metabase, use fully qualified table names:

```sql
-- Instead of:
SELECT * FROM banco_datos

-- Use:
SELECT * FROM SmartBusiness.dbo.banco_datos

-- Or at minimum:
SELECT * FROM dbo.banco_datos
```

---

## Verification Checklist

After fixing connection, verify in Metabase:

### 1. Check Database Explorer
- Click **Browse Data** in Metabase
- You should see `SmartBusiness` database
- Click on it
- You should see `banco_datos` table
- Click on it
- Should show data with proper row counts

### 2. Run Test Query
Go to **New** → **SQL Query**

```sql
-- Test query
SELECT
    COUNT(*) as total_rows,
    MIN(Fecha) as earliest_date,
    MAX(Fecha) as latest_date,
    SUM(TotalMasIva) as total_revenue
FROM banco_datos
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
```

Should match what you see in DBeaver!

### 3. Compare Results

| Tool | Database | Schema | Table | Row Count |
|------|----------|--------|-------|-----------|
| DBeaver | SmartBusiness | dbo | banco_datos | XXX,XXX |
| Metabase | ??? | ??? | ??? | ??? |

They should match!

---

## Common Error Messages and Fixes

### Error: "Cannot open database requested in login"
**Cause:** Database name is wrong
**Fix:** Change database name to `SmartBusiness` in Metabase connection

### Error: "The user does not have permission"
**Cause:** Insufficient permissions
**Fix:** Grant SELECT permissions (see Solution #4)

### Error: "Invalid object name 'banco_datos'"
**Cause:** Wrong schema or database
**Fix:** Use fully qualified name: `dbo.banco_datos`

### Tables show 0 rows but DBeaver shows data
**Cause:** Metabase cached old data
**Fix:** Force resync (Solution #5)

---

## Debug Information to Collect

If still having issues, collect this info:

```sql
-- Run in DBeaver
-- 1. Current database
SELECT DB_NAME() as current_db;

-- 2. Available databases
SELECT name FROM sys.databases WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb');

-- 3. Tables in SmartBusiness
USE SmartBusiness;
SELECT TABLE_SCHEMA, TABLE_NAME,
       (SELECT COUNT(*) FROM banco_datos) as approx_rows
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_NAME = 'banco_datos';

-- 4. Connection info
SELECT
    @@SERVERNAME as server_name,
    @@VERSION as sql_version,
    DB_NAME() as current_database,
    USER_NAME() as current_user;
```

Share this output and I can help debug further!

---

## Quick Fix Script

Create this file and run it:

```python
# fix_metabase_connection.py
"""
Quick diagnostic for Metabase connection issues
"""
import pymssql

# YOUR CONNECTION DETAILS (same as Metabase)
HOST = "your-server"
PORT = 1433
USER = "your-username"
PASSWORD = "your-password"
DATABASE = "SmartBusiness"  # ← Is this correct?

print("Testing SQL Server connection...")
print(f"Host: {HOST}:{PORT}")
print(f"Database: {DATABASE}")
print(f"User: {USER}")
print()

try:
    # Test connection
    conn = pymssql.connect(
        server=HOST,
        port=PORT,
        user=USER,
        password=PASSWORD,
        database=DATABASE
    )

    cursor = conn.cursor(as_dict=True)

    # Get current database
    cursor.execute("SELECT DB_NAME() as db")
    result = cursor.fetchone()
    print(f"✓ Connected to database: {result['db']}")

    # List all tables
    cursor.execute("""
        SELECT TABLE_SCHEMA, TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_SCHEMA, TABLE_NAME
    """)

    tables = cursor.fetchall()
    print(f"✓ Found {len(tables)} tables")
    print("\nTables:")
    for table in tables[:10]:  # Show first 10
        print(f"  - {table['TABLE_SCHEMA']}.{table['TABLE_NAME']}")

    if len(tables) > 10:
        print(f"  ... and {len(tables) - 10} more")

    # Check banco_datos specifically
    try:
        cursor.execute("SELECT COUNT(*) as cnt FROM banco_datos")
        result = cursor.fetchone()
        print(f"\n✓ banco_datos exists with {result['cnt']:,} rows")
    except Exception as e:
        print(f"\n✗ Cannot access banco_datos: {e}")

    conn.close()

    print("\n" + "="*50)
    print("SUCCESS! Connection works.")
    print("="*50)
    print("\nIf Metabase shows different results:")
    print("1. Check Metabase database name matches:", DATABASE)
    print("2. Force sync in Metabase Admin")
    print("3. Check schema filters (should include 'dbo')")

except Exception as e:
    print(f"\n✗ Connection failed: {e}")
    print("\nTroubleshooting:")
    print("1. Check HOST, PORT, USER, PASSWORD are correct")
    print("2. Check DATABASE name is correct")
    print("3. Check SQL Server allows remote connections")
    print("4. Check firewall allows port 1433")
```

Run it:
```bash
python fix_metabase_connection.py
```

---

## Most Likely Solution

Based on your description, **Metabase is probably connected to the wrong database**.

**Do this:**
1. Go to Metabase Admin → Databases
2. Click your SQL Server connection
3. Change **Database name** to: `SmartBusiness`
4. Click **Save**
5. Click **Sync database schema now**
6. Wait 2 minutes
7. Check Browse Data again

**That usually fixes it!** ✨

---

Let me know what you see and I'll help debug further!
