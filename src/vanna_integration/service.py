from typing import Any

DDL_TRAINING_BLOCK = """
        -- Main business data table
        -- Contains all sales transactions for hardware store
        CREATE TABLE banco_datos (
            Fecha DATE,                    -- Transaction date
            TotalMasIva DECIMAL(18,2),     -- Total amount WITH tax (IVA)
            TotalSinIva DECIMAL(18,2),     -- Total amount WITHOUT tax
            ValorCosto DECIMAL(18,2),      -- Product cost
            Cantidad INT,                  -- Quantity sold
            TercerosNombres NVARCHAR(200), -- Customer name
            ArticulosNombre NVARCHAR(200), -- Product name
            ArticulosCodigo NVARCHAR(50),  -- Product SKU/code
            DocumentosCodigo NVARCHAR(10), -- Document type (exclude XY, AS, TS)
            categoria NVARCHAR(100),       -- Product category
            subcategoria NVARCHAR(100)     -- Product subcategory
        );

        -- Note: Always filter out DocumentosCodigo IN ('XY', 'AS', 'TS') in queries
    """

DOCUMENTATION_TRAINING_BLOCK = """
        # SmartBusiness Database - Hardware Store Sales Data

        ## Key Tables
        - **banco_datos**: Main sales transactions table with all business data

        ## Important Fields
        - **TotalMasIva**: Revenue WITH tax (IVA) - use for total revenue calculations
        - **TotalSinIva**: Revenue WITHOUT tax - use for profit margin calculations
        - **ValorCosto**: Product cost - use to calculate profit
        - **TercerosNombres**: Customer name
        - **ArticulosNombre**: Product name
        - **categoria/subcategoria**: Product categorization

        ## Business Rules
        1. ALWAYS exclude documents with DocumentosCodigo IN ('XY', 'AS', 'TS')
        2. Profit = TotalSinIva - ValorCosto
        3. Profit Margin = (TotalSinIva - ValorCosto) / TotalSinIva * 100
        4. IVA (tax) = TotalMasIva - TotalSinIva

        ## Common Queries
        - Top customers by revenue: GROUP BY TercerosNombres, SUM(TotalMasIva)
        - Top products: GROUP BY ArticulosNombre, SUM(TotalMasIva)
        - Category performance: GROUP BY categoria, calculate profit margins
        - Monthly trends: GROUP BY YEAR(Fecha), MONTH(Fecha)
    """

EXAMPLE_SQL_BLOCKS = [
    """
        -- Question: Who are my top 10 customers by revenue?
        SELECT TOP 10
            TercerosNombres as customer_name,
            SUM(TotalMasIva) as total_revenue,
            COUNT(*) as order_count,
            AVG(TotalMasIva) as avg_order_value
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
        GROUP BY TercerosNombres
        ORDER BY total_revenue DESC
    """,
    """
        -- Question: What are my best selling products?
        SELECT TOP 10
            ArticulosNombre as product_name,
            SUM(TotalMasIva) as total_revenue,
            SUM(Cantidad) as units_sold,
            SUM(TotalSinIva) - SUM(ValorCosto) as profit,
            CASE
                WHEN SUM(TotalSinIva) > 0
                THEN (SUM(TotalSinIva) - SUM(ValorCosto)) / SUM(TotalSinIva) * 100
                ELSE 0
            END as profit_margin_pct
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
        GROUP BY ArticulosNombre
        ORDER BY total_revenue DESC
    """,
    """
        -- Question: How are my product categories performing?
        SELECT
            categoria as category,
            SUM(TotalMasIva) as total_revenue,
            SUM(TotalSinIva) - SUM(ValorCosto) as profit,
            CASE
                WHEN SUM(TotalSinIva) > 0
                THEN (SUM(TotalSinIva) - SUM(ValorCosto)) / SUM(TotalSinIva) * 100
                ELSE 0
            END as profit_margin_pct,
            COUNT(*) as transaction_count
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
        GROUP BY categoria
        ORDER BY total_revenue DESC
    """,
    """
        -- Question: Show me monthly revenue trends
        SELECT
            YEAR(Fecha) as year,
            MONTH(Fecha) as month,
            SUM(TotalMasIva) as total_revenue,
            SUM(TotalSinIva) - SUM(ValorCosto) as profit,
            COUNT(*) as transaction_count
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
        GROUP BY YEAR(Fecha), MONTH(Fecha)
        ORDER BY year DESC, month DESC
    """,
    """
        -- Question: What's my revenue this month?
        SELECT
            SUM(TotalMasIva) as total_revenue,
            SUM(TotalSinIva) as revenue_without_tax,
            SUM(TotalMasIva) - SUM(TotalSinIva) as tax_collected,
            SUM(TotalSinIva) - SUM(ValorCosto) as gross_profit,
            COUNT(*) as total_orders
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
            AND Fecha >= DATEADD(MONTH, DATEDIFF(MONTH, 0, GETDATE()), 0)
            AND Fecha < DATEADD(MONTH, DATEDIFF(MONTH, 0, GETDATE()) + 1, 0)
    """,
    """
        -- Question: Which products have low profit margins?
        SELECT TOP 20
            ArticulosNombre as product_name,
            SUM(TotalSinIva) as revenue,
            SUM(ValorCosto) as cost,
            SUM(TotalSinIva) - SUM(ValorCosto) as profit,
            CASE
                WHEN SUM(TotalSinIva) > 0
                THEN (SUM(TotalSinIva) - SUM(ValorCosto)) / SUM(TotalSinIva) * 100
                ELSE 0
            END as profit_margin_pct
        FROM banco_datos
        WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
        GROUP BY ArticulosNombre
        HAVING SUM(TotalSinIva) > 0
        ORDER BY profit_margin_pct ASC
    """,
]


class VannaService:
    def __init__(self, vn: Any):
        self._vn = vn

    def connect_to_mssql(
        self,
        db_server: str,
        db_name: str,
        db_user: str,
        db_password: str,
    ) -> Any:
        odbc_conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={db_server};"
            f"DATABASE={db_name};"
            f"UID={db_user};"
            f"PWD={db_password}"
        )

        print(f"Connecting to SQL Server: {db_server}/{db_name}")
        self._vn.connect_to_mssql(odbc_conn_str=odbc_conn_str)
        print("✓ Connected to database!")
        return self._vn

    def train_on_schema(self) -> Any:
        print("\nTraining Vanna on your database schema...")
        print("  - Loading table information...")
        self._vn.run_sql(
            """
        SELECT
            TABLE_SCHEMA,
            TABLE_NAME,
            COLUMN_NAME,
            DATA_TYPE,
            IS_NULLABLE,
            COLUMN_DEFAULT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME IN ('banco_datos')
        ORDER BY TABLE_NAME, ORDINAL_POSITION
    """
        )

        self._vn.train(ddl=DDL_TRAINING_BLOCK)
        print("  - Adding business context...")
        self._vn.train(documentation=DOCUMENTATION_TRAINING_BLOCK)
        print("  - Adding example queries...")
        for sql in EXAMPLE_SQL_BLOCKS:
            self._vn.train(sql=sql)

        print("✓ Training complete!")
        return self._vn
