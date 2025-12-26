# Business Data Analyzer - Project Documentation

## Overview

Business intelligence tool for hardware store operations analyzing sales data from **SmartBusiness** SQL Server database.

## Database Connection

```bash
# Environment variables (.env)
DB_HOST=your_server
DB_PORT=1433
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=SmartBusiness
```

## Database Schema

**Table:** `[dbo].[banco_datos]`

| Column | Type | Description |
|--------|------|-------------|
| VentaID | Integer | Transaction ID (PK) |
| Fecha | Date | Transaction date |
| periodo | Integer | Period (YYYYMM format) |
| ano | Integer | Year |
| mes | Integer | Month |
| ArticulosCodigo | String | Product SKU |
| ArticulosNombre | String | Product name |
| marca | String | Product category |
| subcategoria | String | Product subcategory |
| Cantidad | Float | Quantity (positive=sale, negative=return) |
| TotalSinIva | Decimal | Revenue pre-tax |
| TotalMasIva | Decimal | Revenue post-tax |
| ValorCosto | Decimal | Cost value |
| TercerosNombres | String | Customer name |
| DocumentosCodigo | String | Document type |

## Important Notes

- **Negative Cantidad** = Returns (should be included in calculations for accurate net values)
- **Excluded Document Types:** `'XY', 'AS', 'TS'`

---

## Analysis Queries (Periodo 202401-202512)

### 1. BESTSELLER by Category & Subcategory (Highest Net Quantity Sold)

```sql
-- Bestseller per Category/Subcategory with yearly breakdown
-- Includes returns (negative qty) for accurate NET sales
WITH SalesSummary AS (
    SELECT
        marca,
        subcategoria,
        ArticulosCodigo,
        ArticulosNombre,
        ano,
        SUM(Cantidad) AS net_cantidad,  -- Net: sales minus returns
        SUM(CASE WHEN Cantidad > 0 THEN Cantidad ELSE 0 END) AS gross_sales,
        SUM(CASE WHEN Cantidad < 0 THEN ABS(Cantidad) ELSE 0 END) AS returns,
        SUM(TotalMasIva) AS net_revenue,
        SUM(TotalMasIva - ValorCosto) AS net_profit,
        COUNT(DISTINCT VentaID) AS num_transactions
    FROM [dbo].[banco_datos]
    WHERE ano IN (2024, 2025)
      AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
    GROUP BY marca, subcategoria, ArticulosCodigo, ArticulosNombre, ano
    HAVING SUM(Cantidad) > 0  -- Only products with positive net sales
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
ORDER BY marca, subcategoria, ano;
```

### 2. MOST PROFITABLE by Category & Subcategory (Highest Net Profit)

```sql
-- Most Profitable Product per Category/Subcategory with yearly breakdown
-- Includes returns for accurate NET profit calculation
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
    HAVING SUM(TotalMasIva) > 0  -- Products with positive net revenue
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
ORDER BY marca, subcategoria, ano;
```

### 3. AVERAGE TICKET by Category & Subcategory

```sql
-- Average Ticket per Category/Subcategory with yearly breakdown
-- Net values including returns
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
ORDER BY marca, subcategoria, ano;
```

---

## YEARLY TOTALS (2024 vs 2025)

### Total Summary by Year

```sql
-- Yearly totals across all categories (including returns)
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
ORDER BY ano;
```

### Category Totals by Year

```sql
-- Category totals per year (including returns)
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
ORDER BY marca, ano;
```

---

## Combined Analysis Report Query

```sql
-- COMPLETE ANALYSIS: All metrics in one view (with returns)
WITH BaseData AS (
    SELECT
        marca,
        subcategoria,
        ArticulosCodigo,
        ArticulosNombre,
        ano,
        SUM(Cantidad) AS net_qty,
        SUM(CASE WHEN Cantidad > 0 THEN Cantidad ELSE 0 END) AS gross_qty,
        SUM(CASE WHEN Cantidad < 0 THEN ABS(Cantidad) ELSE 0 END) AS return_qty,
        SUM(TotalMasIva) AS net_rev,
        SUM(TotalMasIva - ValorCosto) AS net_profit,
        COUNT(DISTINCT VentaID) AS num_trans
    FROM [dbo].[banco_datos]
    WHERE ano IN (2024, 2025)
      AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
    GROUP BY marca, subcategoria, ArticulosCodigo, ArticulosNombre, ano
),
Rankings AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY marca, subcategoria, ano
            ORDER BY net_qty DESC
        ) AS rank_qty,
        ROW_NUMBER() OVER (
            PARTITION BY marca, subcategoria, ano
            ORDER BY net_profit DESC
        ) AS rank_profit
    FROM BaseData
    WHERE net_qty > 0  -- Positive net sales for bestseller
),
CategorySummary AS (
    SELECT
        marca,
        subcategoria,
        ano,
        SUM(net_rev) / NULLIF(SUM(num_trans), 0) AS avg_ticket,
        SUM(net_rev) AS cat_revenue,
        SUM(net_profit) AS cat_profit,
        SUM(net_qty) AS cat_net_units,
        SUM(gross_qty) AS cat_gross_units,
        SUM(return_qty) AS cat_returns
    FROM BaseData
    GROUP BY marca, subcategoria, ano
)
SELECT
    c.marca,
    c.subcategoria,
    c.ano AS year,
    -- Bestseller
    b.ArticulosCodigo AS bestseller_sku,
    b.ArticulosNombre AS bestseller_name,
    b.net_qty AS bestseller_net_units,
    b.gross_qty AS bestseller_gross_units,
    b.return_qty AS bestseller_returns,
    -- Most Profitable
    p.ArticulosCodigo AS profitable_sku,
    p.ArticulosNombre AS profitable_name,
    p.net_profit AS profitable_profit,
    -- Average Ticket & Category Totals
    c.avg_ticket,
    c.cat_revenue AS category_net_revenue,
    c.cat_profit AS category_net_profit,
    c.cat_net_units AS category_net_units,
    c.cat_gross_units AS category_gross_units,
    c.cat_returns AS category_returns
FROM CategorySummary c
LEFT JOIN Rankings b ON c.marca = b.marca
    AND c.subcategoria = b.subcategoria
    AND c.ano = b.ano
    AND b.rank_qty = 1
LEFT JOIN Rankings p ON c.marca = p.marca
    AND c.subcategoria = p.subcategoria
    AND c.ano = p.ano
    AND p.rank_profit = 1
ORDER BY c.marca, c.subcategoria, c.ano;
```

---

## Returns Analysis Query

```sql
-- Detailed returns analysis by category/subcategory
SELECT
    marca,
    subcategoria,
    ano AS year,
    SUM(CASE WHEN Cantidad < 0 THEN ABS(Cantidad) ELSE 0 END) AS total_returns,
    SUM(CASE WHEN Cantidad > 0 THEN Cantidad ELSE 0 END) AS total_sales,
    CAST(
        SUM(CASE WHEN Cantidad < 0 THEN ABS(Cantidad) ELSE 0 END) * 100.0 /
        NULLIF(SUM(CASE WHEN Cantidad > 0 THEN Cantidad ELSE 0 END), 0)
    AS DECIMAL(5,2)) AS return_rate_pct,
    SUM(CASE WHEN Cantidad < 0 THEN TotalMasIva ELSE 0 END) AS return_value,
    COUNT(DISTINCT CASE WHEN Cantidad < 0 THEN VentaID END) AS return_transactions
FROM [dbo].[banco_datos]
WHERE ano IN (2024, 2025)
  AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
GROUP BY marca, subcategoria, ano
HAVING SUM(CASE WHEN Cantidad < 0 THEN 1 ELSE 0 END) > 0
ORDER BY return_rate_pct DESC;
```

---

## Python Integration Example

```python
import pymssql
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

# Connect to database
conn = pymssql.connect(
    server=os.getenv('DB_HOST'),
    port=int(os.getenv('DB_PORT', 1433)),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME', 'SmartBusiness')
)

# Execute analysis with returns included
query = """
    SELECT marca, subcategoria, ano,
           SUM(Cantidad) as net_units,
           SUM(CASE WHEN Cantidad > 0 THEN Cantidad ELSE 0 END) as gross_units,
           SUM(CASE WHEN Cantidad < 0 THEN ABS(Cantidad) ELSE 0 END) as returns,
           SUM(TotalMasIva) as net_revenue,
           SUM(TotalMasIva - ValorCosto) as net_profit
    FROM [dbo].[banco_datos]
    WHERE ano IN (2024, 2025)
      AND DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
    GROUP BY marca, subcategoria, ano
    ORDER BY marca, subcategoria, ano
"""

df = pd.read_sql(query, conn)
print(df)
conn.close()
```

---

## Business Thresholds (from config.py)

| Metric | Threshold | Description |
|--------|-----------|-------------|
| VIP Customer | $500,000+ | Revenue or 5+ orders |
| High Value | $200,000+ | Revenue threshold |
| Regular | $50,000+ | Revenue threshold |
| Fast Mover | 5+ trans | Inventory velocity |
| Slow Mover | ≤2 trans | Inventory velocity |
| Low Margin | 10% | Profitability alert |
| Star Product | 30%+ | High margin products |

---

## Usage

```bash
# Clone repository
git clone https://github.com/Trujillofa/coding_omarchy.git
cd coding_omarchy

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run analysis
python business_analyzer_combined.py --start-date 2024-01-01 --end-date 2025-12-31
```

## Output

Reports generated in `~/business_reports/`:
- `analysis_YYYYMMDD_HHMMSS.json` - JSON data
- `business_report_YYYYMMDD_HHMMSS.png` - Visualization
