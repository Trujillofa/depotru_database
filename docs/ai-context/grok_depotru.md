# Deposito Trujillo - Database Analysis Documentation

**Created:** 2025-11-27
**Purpose:** Complete reference for SmartBusiness database analysis, queries, and reporting
**Database:** SQL Server - SmartBusiness

---

## 📊 Table of Contents

1. [Database Connection](#database-connection)
2. [Database Schema](#database-schema)
3. [Critical Field Mappings](#critical-field-mappings)
4. [Data Quality Issues & Fixes](#data-quality-issues--fixes)
5. [Exclusions & Filters](#exclusions--filters)
6. [File Structure](#file-structure)
7. [SQL Query Patterns](#sql-query-patterns)
8. [Key Findings](#key-findings)
9. [Future Development](#future-development)

---

## 🔌 Database Connection

### Connection Details

```python
db_host = "190.60.235.209"
db_port = 1433
db_username = "Consulta"
db_password = "Control*01"
database = "SmartBusiness"
```

### Python Connection Code

```python
import pymssql

conn = pymssql.connect(
    server="190.60.235.209",
    port=1433,
    user="Consulta",
    password="Control*01",
    database="SmartBusiness",
    login_timeout=30,
    timeout=180,
)
```

### Test Connection

```bash
# Quick test
python3 -c "import pymssql; conn = pymssql.connect(server='190.60.235.209', port=1433, user='Consulta', password='Control*01', database='SmartBusiness'); print('✅ Connected'); conn.close()"
```

---

## 🗄️ Database Schema

### Primary Table: `[dbo].[banco_datos]`

This table contains all transactional sales data.

#### Key Fields

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| **VentaID** | varchar | Unique transaction ID | Primary identifier |
| **Fecha** | date | Transaction date | Format: YYYY-MM-DD |
| **ano** | int | Year | 2024, 2025 |
| **mes** | int | Month | 1-12 |
| **periodo** | varchar | Period code | ⚠️ INCONSISTENT FORMAT (see below) |
| **DocumentosCodigo** | varchar(3) | Document type code | DDD, DDT, DVD, etc. |
| **TercerosNombres** | varchar | Customer name | Use for customer analysis |
| **ArticulosCodigo** | varchar | Product SKU | Unique product identifier |
| **ArticulosNombre** | varchar | Product name | Product description |
| **categoria** | varchar | Category (WRONG) | ❌ DO NOT USE - use 'marca' |
| **marca** | varchar | **ACTUAL CATEGORY** | ✅ USE THIS for category |
| **subcategoria** | varchar | Subcategory | Product subcategory |
| **proveedor** | varchar | Supplier/Vendor | Provider name |
| **Cantidad** | decimal | Quantity sold | Negative = returns |
| **TotalSinIva** | decimal | **Revenue (before tax)** | ✅ USE THIS |
| **TotalMasIva** | decimal | Revenue (with tax) | ❌ DO NOT USE |
| **ValorCosto** | decimal | Cost value | For profit calculation |

#### Critical Period Field Format Issue

⚠️ **WARNING:** The `periodo` field has INCONSISTENT formatting:

```
January 2024:   20241  (5 digits)
February 2024:  20242  (5 digits)
...
September 2024: 20249  (5 digits)
October 2024:   202410 (6 digits)
November 2024:  202411 (6 digits)
December 2024:  202412 (6 digits)
```

**Solution:** Always use `ano IN (2024, 2025)` instead of `periodo BETWEEN ...`

---

## 🔑 Critical Field Mappings

### ⚠️ CATEGORY FIELD CONFUSION

**IMPORTANT:** The field named `categoria` is **NOT** the actual category!

| Field Name | Actual Use | Use In Queries |
|------------|------------|----------------|
| `categoria` | Product line/type | Only for filtering (e.g., "PRODUCTOS SIKA") |
| **`marca`** | **REAL CATEGORY** | **✅ Use for category analysis** |
| `subcategoria` | Subcategory | Use for subcategory breakdown |

### Revenue Fields

| Field | Description | When to Use |
|-------|-------------|-------------|
| **`TotalSinIva`** | Revenue BEFORE tax | ✅ **ALWAYS USE THIS** |
| `TotalMasIva` | Revenue WITH tax | ❌ DO NOT USE (inflates by ~16%) |

### Profit Calculation

```sql
-- Correct profit calculation
SUM(TotalSinIva - ValorCosto) AS profit

-- Correct margin calculation
(SUM(TotalSinIva - ValorCosto) / NULLIF(SUM(TotalSinIva), 0) * 100) AS margin_pct
```

### Quantity & Returns

```sql
-- Net quantity (sales - returns)
SUM(Cantidad) AS net_quantity

-- Gross sales (positive only)
SUM(CASE WHEN Cantidad > 0 THEN Cantidad ELSE 0 END) AS gross_sales

-- Returns (negative values)
SUM(CASE WHEN Cantidad < 0 THEN ABS(Cantidad) ELSE 0 END) AS returns
```

---

## 🔧 Data Quality Issues & Fixes

### 1. Period Format Inconsistency

**Problem:** `periodo` field has 5-6 digit inconsistency
**Impact:** Missing 75% of data when using `BETWEEN 202401 AND 202512`
**Solution:** Use `ano IN (2024, 2025)` filter

### 2. Category Field Mislabeling

**Problem:** Field named `categoria` is not the business category
**Impact:** Wrong category analysis, 73 categories instead of 13
**Solution:** Use `marca` field for category analysis

### 3. Tax-Inclusive Values

**Problem:** Initial analysis used `TotalMasIva` (with tax)
**Impact:** Revenue inflated by ~16%, margins calculated wrong
**Solution:** Always use `TotalSinIva` for revenue

### 4. Provider Name Whitespace

**Problem:** "SIKA" and " SIKA" (with leading space) treated as different
**Impact:** Vendor counts inflated
**Solution:** Consider `TRIM(proveedor)` in queries

---

## 🚫 Exclusions & Filters

### Standard Exclusions (All Queries)

```sql
WHERE
  -- Exclude administrative document types
  DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')

  -- Exclude internal transactions
  AND TercerosNombres != 'DEPOSITO TRUJILLO SAS'

  -- Year filter
  AND ano IN (2024, 2025)
```

### Document Code Reference

#### ✅ INCLUDE (Valid Sales/Returns)
- **DDD** - Sales document
- **DDT** - Sales document
- **DVD** - Sales document
- **DVE** - Sales document
- **FDD** - Sales document
- **FDT** - Sales document
- **FED** - Sales document
- **FET** - Sales document

#### ❌ EXCLUDE (Administrative/Internal)
- **XY** - Administrative
- **AS** - Administrative
- **TS** - Administrative
- **YX** - Inventory transfers
- **ISC** - Internal stock corrections

### Special Exclusion: DEPOSITO TRUJILLO SAS

**Why Exclude:**
- This is NOT a customer - it's internal inventory operations
- Document codes: YX, ISC (inventory adjustments)
- Transactions: 483 total (174 in 2024, 309 in 2025)
- Impact: $312M in internal transfers excluded from customer analysis

See: `DEPOSITO_TRUJILLO_INVESTIGATION.md` for full details

---

## 📁 File Structure

### Analysis Scripts

| File | Purpose | Last Updated |
|------|---------|--------------|
| **sika_analysis.py** | Main PRODUCTOS SIKA analysis script | 2025-11-26 |
| sika_analysis_backup.py | Backup before vendor removal | 2025-11-26 |
| run_analysis.py | General category analysis (all products) | 2025-11-26 |
| investigate_deposito.py | DEPOSITO TRUJILLO investigation | 2025-11-26 |
| check_document_codes.py | Document code validation | 2025-11-26 |

### Report Generators

| File | Purpose | Output |
|------|---------|--------|
| **generate_sika_report.py** | English SIKA report generator | SIKA_ANALYSIS_REPORT.md |
| **generate_sika_report_es.py** | Spanish SIKA report generator | REPORTE_SIKA_ESPANOL.md |
| generate_report.py | General category report generator | ANALYSIS_REPORT.md |

### Output Reports

| File | Description | Language |
|------|-------------|----------|
| **REPORTE_SIKA_ESPANOL.md** | PRODUCTOS SIKA comprehensive analysis | Spanish |
| **SIKA_ANALYSIS_REPORT.md** | PRODUCTOS SIKA comprehensive analysis | English |
| ANALYSIS_REPORT.md | All categories analysis | English |
| DEPOSITO_TRUJILLO_INVESTIGATION.md | Internal operations investigation | English |
| SIKA_PROVIDER_VERIFICATION.md | Provider analysis | English |

### Data Files

| File | Description | Format |
|------|-------------|--------|
| sika_analysis_report.json | SIKA analysis raw data | JSON |
| analysis_report.json | General analysis raw data | JSON |

### Documentation

| File | Purpose |
|------|---------|
| **claude_depotru.md** | Original comprehensive reference |
| **grok_depotru.md** | THIS FILE - Grok's analysis reference |
| claude.md | Original SQL queries and documentation |

---

## 📝 SQL Query Patterns

### Template: Customer Analysis

```sql
SELECT
    TercerosNombres AS customer_name,
    ano AS year,
    COUNT(DISTINCT VentaID) AS num_orders,
    SUM(Cantidad) AS net_units,
    SUM(TotalSinIva) AS total_revenue,
    SUM(TotalSinIva - ValorCosto) AS total_profit,
    AVG(TotalSinIva) AS avg_order_value,
    (SUM(TotalSinIva - ValorCosto) / NULLIF(SUM(TotalSinIva), 0) * 100) AS margin_pct
FROM [dbo].[banco_datos]
WHERE categoria = 'PRODUCTOS SIKA'
  AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
  AND TercerosNombres != 'DEPOSITO TRUJILLO SAS'
  AND ano IN (2024, 2025)
GROUP BY TercerosNombres, ano
ORDER BY SUM(TotalSinIva) DESC
```

### Template: Product Performance

```sql
SELECT
    marca AS category,
    subcategoria,
    ArticulosCodigo AS sku,
    ArticulosNombre AS product_name,
    ano AS year,
    SUM(Cantidad) AS net_units,
    SUM(CASE WHEN Cantidad > 0 THEN Cantidad ELSE 0 END) AS gross_sales,
    SUM(CASE WHEN Cantidad < 0 THEN ABS(Cantidad) ELSE 0 END) AS returns,
    SUM(TotalSinIva) AS revenue,
    SUM(TotalSinIva - ValorCosto) AS profit,
    (SUM(TotalSinIva - ValorCosto) / NULLIF(SUM(TotalSinIva), 0) * 100) AS margin_pct,
    COUNT(DISTINCT TercerosNombres) AS unique_customers
FROM [dbo].[banco_datos]
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
  AND TercerosNombres != 'DEPOSITO TRUJILLO SAS'
  AND ano IN (2024, 2025)
GROUP BY marca, subcategoria, ArticulosCodigo, ArticulosNombre, ano
ORDER BY SUM(TotalSinIva) DESC
```

### Template: Monthly Trends

```sql
SELECT
    ano AS year,
    mes AS month,
    COUNT(DISTINCT TercerosNombres) AS unique_customers,
    COUNT(DISTINCT VentaID) AS transactions,
    SUM(Cantidad) AS net_units,
    SUM(TotalSinIva) AS revenue,
    SUM(TotalSinIva - ValorCosto) AS profit,
    AVG(TotalSinIva) AS avg_transaction
FROM [dbo].[banco_datos]
WHERE categoria = 'PRODUCTOS SIKA'
  AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
  AND TercerosNombres != 'DEPOSITO TRUJILLO SAS'
  AND ano IN (2024, 2025)
GROUP BY ano, mes
ORDER BY ano, mes
```

### Template: Customer Segmentation

```sql
WITH CustomerRevenue AS (
    SELECT
        TercerosNombres AS customer_name,
        ano AS year,
        SUM(TotalSinIva) AS total_revenue
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
        AVG(total_revenue) AS avg_revenue_per_customer
    FROM CustomerRevenue
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
```

---

## 🔍 Key Findings

### Overall Business (All Categories)

**Period:** 2024-2025

| Metric | 2024 | 2025 | Growth |
|--------|------|------|--------|
| Revenue (pre-tax) | $72.5B | $78.1B | +7.7% |
| Top Category | MATERIALES PARA CONSTRUCCION | 69.7% | - |
| Total Categories | 13 | - | - |

### PRODUCTOS SIKA Analysis

**Period:** 2024-2025
**Exclusions Applied:** DEPOSITO TRUJILLO SAS, Document codes YX/ISC

| Metric | 2024 | 2025 | Growth |
|--------|------|------|--------|
| **Revenue (pre-tax)** | $4,626M | $5,549M | **+20.0%** |
| **Profit** | $730M | $921M | **+26.2%** |
| **Margin** | 15.8% | 16.6% | **+0.8pp** |
| **Customers** | 4,335 | 5,017 | **+15.7%** |
| **Transactions** | 17,272 | 18,858 | **+9.2%** |
| **Avg Transaction** | $194,597 | $203,813 | **+4.7%** |
| **Products Sold** | 129,414 | 147,987 | **+14.4%** |
| **Returns** | 2,356 | 6,081 | **+158.1%** ⚠️ |

#### Customer Segmentation (2025)

| Segment | Customers | Revenue | % of Total |
|---------|-----------|---------|------------|
| VIP (>$50M) | 16 | $2,142M | 38.6% |
| High Value ($10M-50M) | 65 | $1,349M | 24.3% |
| Medium ($5M-10M) | 78 | $545M | 9.8% |
| Regular ($1M-5M) | 377 | $867M | 15.6% |
| Occasional (<$1M) | 4,481 | $647M | 11.7% |

#### Top 5 Customers (2025)

1. **OLGA ORTIZ ORTIZ** - $403.8M (9.8% margin)
2. **CONSTRUCTORA SANTA LUCIA SAS** - $306.0M (13.7% margin)
3. **CONSTRUIMOS DEL HUILA S.A** - $188.4M (11.1% margin)
4. **FERRETERIA MAGRETH S A S** - $178.5M (7.6% margin)
5. **DEPOSITO TRUJILLO SAS** - $167.3M (excluded - internal)

#### Monthly Performance (2025)

**Best Month:** March ($649.8M, +94.0% YoY)
**Worst Month:** November ($427.3M, -21.8% YoY)

#### Critical Issues Identified

⚠️ **URGENT - Returns Spike:**
- Returns increased +158% (2,356 → 6,081 units)
- Requires immediate root cause analysis
- Potential quality control issue with SIKA supplier

### Provider Analysis

**SIKA is the sole provider** for PRODUCTOS SIKA category:
- Market share: 99.93% (combined "SIKA" + " SIKA")
- 294 active SKUs
- 51,438 transactions
- $10.48B total revenue (2024+2025)

**Risk:** Single supplier dependency - mission-critical relationship

---

## 🚀 Future Development

### Recommended Enhancements

1. **Automated Reporting**
   - Schedule daily/weekly/monthly report generation
   - Email distribution of key metrics
   - Dashboard with real-time metrics

2. **Return Analysis Deep Dive**
   - Identify products with high return rates
   - Analyze return reasons by customer
   - Seasonal return pattern analysis

3. **Customer Lifetime Value**
   - Calculate LTV for customer segments
   - Predict churn risk
   - Identify growth opportunities

4. **Inventory Optimization**
   - Forecast demand by product/month
   - Identify slow-moving inventory
   - Optimize stock levels

5. **Margin Analysis**
   - Product-level margin trends
   - Customer-level margin analysis
   - Identify margin improvement opportunities

6. **Competitive Analysis**
   - Cross-category performance
   - Market share by subcategory
   - Price positioning analysis

### Database Improvements Needed

1. **Data Quality**
   - Standardize `periodo` field format (all 6 digits)
   - Clean provider names (remove whitespace)
   - Rename `categoria` field to avoid confusion
   - Add proper `category` field mapped from `marca`

2. **Performance Optimization**
   - Add indexes on frequently queried fields (ano, marca, TercerosNombres)
   - Consider materialized views for common aggregations
   - Partition large tables by year

3. **Documentation**
   - Create data dictionary for all fields
   - Document business rules
   - Define standard KPIs

### Query Optimization Tips

1. **Use Appropriate Indexes**
   ```sql
   -- Recommended indexes:
   CREATE INDEX idx_ano_marca ON [dbo].[banco_datos](ano, marca)
   CREATE INDEX idx_categoria ON [dbo].[banco_datos](categoria)
   CREATE INDEX idx_customer ON [dbo].[banco_datos](TercerosNombres)
   ```

2. **Limit Result Sets**
   ```sql
   -- Always use TOP when testing
   SELECT TOP 1000 * FROM [dbo].[banco_datos]
   ```

3. **Avoid SELECT ***
   ```sql
   -- Specify only needed columns
   SELECT ano, marca, TotalSinIva FROM [dbo].[banco_datos]
   ```

### Debugging Tips

1. **Check Connection**
   ```python
   # Test connection before queries
   try:
       conn = get_connection()
       print("✅ Connected")
   except Exception as e:
       print(f"❌ Connection failed: {e}")
   ```

2. **Validate Filters**
   ```sql
   -- Count records before and after filters
   SELECT COUNT(*) as total FROM [dbo].[banco_datos]
   SELECT COUNT(*) as filtered
   FROM [dbo].[banco_datos]
   WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
   ```

3. **Check Data Types**
   ```python
   # Convert Decimal to float for JSON serialization
   def to_float(val):
       if isinstance(val, Decimal):
           return float(val)
       return val
   ```

### Common Issues & Solutions

| Issue | Symptom | Solution |
|-------|---------|----------|
| Missing data | Revenue too low | Check `ano` filter, not `periodo` |
| Wrong categories | 73 categories instead of 13 | Use `marca` field, not `categoria` |
| Inflated revenue | Values ~16% higher | Use `TotalSinIva`, not `TotalMasIva` |
| Wrong margins | Margins 29-30% instead of 16-17% | Use pre-tax values in calculation |
| Timeout errors | Query takes >180s | Add indexes, limit date range |
| Internal transactions | Customer named DEPOSITO TRUJILLO | Exclude in WHERE clause |

---

## 📞 Support & Contacts

### Database Access
- **Server:** 190.60.235.209:1433
- **Database:** SmartBusiness
- **Read-Only User:** Consulta
- **Connection:** Direct (no VPN required)

### Files Location
- **Working Directory:** `/home/yderf/depotru_database/`
- **Python Scripts:** `*.py`
- **Reports:** `*.md`, `*.json`
- **Documentation:** `grok_depotru.md` (this file)

### Quick Commands

```bash
# Navigate to project
cd /home/yderf/depotru_database

# Run SIKA analysis
python3 sika_analysis.py

# Generate English report
python3 generate_sika_report.py

# Generate Spanish report
python3 generate_sika_report_es.py

# Run general analysis
python3 run_analysis.py

# Investigate specific issue
python3 investigate_deposito.py
```

---

## 📝 Change Log

| Date | Change | By |
|------|--------|-----|
| 2025-11-26 | Initial database analysis | Claude |
| 2025-11-26 | Fixed periodo format issue | Claude |
| 2025-11-26 | Corrected category field (marca) | Claude |
| 2025-11-26 | Fixed tax inclusion issue | Claude |
| 2025-11-26 | Excluded DEPOSITO TRUJILLO SAS | Claude |
| 2025-11-26 | Removed provider analysis | Claude |
| 2025-11-26 | Created comprehensive documentation | Claude |
| 2025-11-27 | Created Grok's version of documentation | Grok |

---

**Last Updated:** 2025-11-27
**Version:** 1.0
**Status:** Production Ready ✅

---

*For questions or issues, refer to the SQL patterns section and run test queries to validate before production use.*