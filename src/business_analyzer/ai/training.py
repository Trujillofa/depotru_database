"""
Training module for AI package - Phase 1 (Core Business Patterns)

Contains schema training logic for Vanna AI.
This version includes 25 real-world examples based on actual database analysis.
"""

from typing import List, Optional, Tuple


def train_on_schema(vn, schema_name: str = "SmartBusiness"):
    """
    Train Vanna on database schema and business rules.

    Args:
        vn: Vanna instance to train
        schema_name: Name of the database schema
    """
    print(f"\nTraining on {schema_name} schema & rules...")

    # 1. DDL (Table Structure) - Complete schema with all fields
    vn.train(
        ddl="""
        CREATE TABLE banco_datos (
            Fecha DATE,
            TotalMasIva DECIMAL(18,2),
            TotalSinIva DECIMAL(18,2),
            ValorCosto DECIMAL(18,2),
            Cantidad INT,
            -- CUSTOMER fields
            TercerosNombres NVARCHAR(200),
            TercerosIdentificacion NVARCHAR(50),
            -- PRODUCT fields
            ArticulosNombre NVARCHAR(200),
            ArticulosCodigo NVARCHAR(50),
            ArticulosReferencia NVARCHAR(100),
            -- VENDOR/SELLER fields (use these for 'vendedor' queries)
            VendedorFactura NVARCHAR(200),
            vendedor_codigo NVARCHAR(50),
            VendedorAsignado NVARCHAR(200),
            -- DOCUMENT fields
            DocumentosCodigo NVARCHAR(10),
            NumeroDocumento INT,
            -- CLASSIFICATION fields (use for brand/category filtering)
            categoria NVARCHAR(100),
            subcategoria NVARCHAR(100),
            proveedor NVARCHAR(100),
            marca NVARCHAR(100),
            -- LOCATION fields
            departamento NVARCHAR(100),
            ciudad NVARCHAR(100)
        );
        """
    )

    # 2. Business Rules/Docs - Critical field mappings with REAL data
    vn.train(
        documentation="""
        SmartBusiness – Ferretería Sales Database (2022-2026, 1.4M+ records)

        =================================================================
        CRITICAL RULES (ALWAYS APPLY)
        =================================================================

        1. ALWAYS exclude test/cancelled docs:
           WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')

        2. Colombian number format: $1.234.567,89 (dots for thousands, comma for decimals)

        3. Date range: 2022-01-11 to 2026-04-15 (5 years of data)

        4. Negative values = Returns/cancellations (include unless filtering explicitly)

        =================================================================
        FIELD MAPPING - ESSENTIAL REFERENCE
        =================================================================

        CUSTOMER (Clientes):
        - TercerosNombres = Customer name (e.g., 'FERRETERIA MAGRETH S A S')
        - TercerosIdentificacion = Customer ID/NIT

        VENDOR/SELLER (Vendedores - NOT customers!):
        - VendedorFactura = Vendor name on receipt (e.g., 'CARLOS EFREY PASCUAS')
        - vendedor_codigo = Vendor code (e.g., '093', '106')
        - VendedorAsignado = Vendor for credit sales (e.g., '106-DIANA PATRICIA CULMA')

        PRODUCT (Productos):
        - ArticulosNombre = Product name (e.g., 'AMARRES PARA TEJA')
        - ArticulosCodigo = Product SKU/code
        - ArticulosReferencia = Reference code

        FINANCIAL (Financiero):
        - TotalMasIva = Revenue WITH tax (IVA) - "Facturación"
        - TotalSinIva = Revenue WITHOUT tax - "Ventas Netas"
        - ValorCosto = Cost/COGS - "Costo"
        - Cantidad = Quantity sold

        METRICS:
        - Profit (Ganancia) = TotalSinIva - ValorCosto
        - Margin % (Margen) = ((TotalSinIva - ValorCosto) / NULLIF(TotalSinIva, 0)) * 100
        - Tax/IVA = TotalMasIva - TotalSinIva

        CLASSIFICATION (Clasificación):
        - categoria = Product category (e.g., 'CEMENTO GRIS', 'HIERRO')
        - subcategoria = Product subcategory
        - proveedor = Products provider/brand (e.g., 'CEMEX', 'SIKA', 'ACESCO')
        - marca = Brand name

        LOCATION (Ubicación):
        - departamento = Colombian department (state)
        - ciudad = City

        TIME (Tiempo):
        - Fecha = Transaction date (YYYY-MM-DD format)
        - YEAR(Fecha) = Year
        - MONTH(Fecha) = Month (1-12)
        - DATEPART(QUARTER, Fecha) = Quarter (1-4)

        =================================================================
        REAL BUSINESS DATA REFERENCE (From 1.4M Records)
        =================================================================

        TOP 5 CATEGORIES (by revenue):
        1. CEMENTO GRIS - $45B (39,136 transactions)
        2. HIERRO - $45B (43,538 transactions)
        3. ZINC - $38B (32,656 transactions)
        4. PRODUCTOS SIKA - $27B (107,472 transactions)
        5. PERFIERIA - $23B (39,509 transactions)

        TOP 5 PROVIDERS/BRANDS (by revenue):
        1. (blank) - $81B
        2. CEMEX - $47B (cement)
        3. ACESCO - $43B (steel/iron)
        4. SIKA - $27B (construction chemicals)
        5. PAVCO - $17B (PVC pipes)

        TOP 5 VENDORS (by transaction count):
        1. CARLOS EFREY PASCUAS - 102,339 transactions, $17B revenue
        2. YULI ALEJANDRA HIGUERA - 91,165 transactions, $18B revenue
        3. ANDRES FELIPE VARGAS JOVEL - 80,086 transactions, $15B revenue
        4. AMELIA SOTELO NARVAEZ - 70,587 transactions, $13B revenue
        5. OSCAR IVAN POLANIA GARCIA - 67,366 transactions, $35B revenue

        TOP 5 CUSTOMERS (by revenue):
        1. FERRETERIA MAGRETH S A S - $12B (14,763 transactions)
        2. ONG FUNDACION GESTION SOCIAL D - $8B (3,266 transactions)
        3. FREDI TRUJILLO CULMA - $4.5B (12,932 transactions)
        4. FERRETERIA LA GRAN REBAJA DE C - $4.2B (4,624 transactions)
        5. GIL ANTONIO VARGAS MERCHAN - $4.2B (1,709 transactions)

        TOP 5 PRODUCTS (by quantity sold):
        1. AMARRES PARA TEJA - 1,583,732 units
        2. CEMENTO GRIS USO GENERAL CEMEX 50KG - 1,476,366 units
        3. ALAMBRE NEGRO RECOCIDO X KILO CONTINUO - 844,586 units
        4. ROLLO CORRUGADO X KG 1/4" SR NTC 2289 - 809,471 units
        5. CODO PRESION 90 1/2 T/PESADO - 779,063 units

        =================================================================
        COLOMBIAN BUSINESS TERMS (Español)
        =================================================================

        English → Spanish:
        - Revenue/Facturación = TotalMasIva (with IVA)
        - Net Sales/Ventas Netas = TotalSinIva (without IVA)
        - Cost/Costo = ValorCosto
        - Profit/Ganancia = TotalSinIva - ValorCosto
        - Margin/Margen = ((TotalSinIva - ValorCosto) / TotalSinIva) * 100
        - Customer/Cliente = TercerosNombres
        - Product/Producto = ArticulosNombre
        - Category/Categoría = categoria
        - Subcategory/Subcategoría = subcategoria
        - Provider/Proveedor = proveedor
        - Brand/Marca = marca
        - Vendor/Vendedor = VendedorFactura
        - Quantity/Cantidad = Cantidad
        - Date/Fecha = Fecha
        - Transaction/Transacción = DocumentosCodigo + NumeroDocumento

        =================================================================
        QUERY PATTERNS BY USE CASE
        =================================================================

        TOP N PATTERNS:
        - SELECT TOP N ... ORDER BY metric DESC
        - Always include metric (revenue, quantity, profit) for ranking

        TIME PERIOD FILTERS:
        - Current year: YEAR(Fecha) = YEAR(GETDATE())
        - Last 30 days: Fecha >= DATEADD(DAY, -30, GETDATE())
        - Last month: Fecha >= DATEADD(MONTH, -1, GETDATE())
        - Specific year: YEAR(Fecha) = 2025
        - Date range: Fecha BETWEEN '2025-01-01' AND '2025-12-31'

        AGGREGATION PATTERNS:
        - Revenue: SUM(TotalMasIva)
        - Net Revenue: SUM(TotalSinIva)
        - Cost: SUM(ValorCosto)
        - Profit: SUM(TotalSinIva - ValorCosto)
        - Quantity: SUM(Cantidad)
        - Transaction count: COUNT(*)
        - Average: AVG(TotalMasIva)

        GROUPING PATTERNS:
        - By category: GROUP BY categoria
        - By month: GROUP BY YEAR(Fecha), MONTH(Fecha)
        - By customer: GROUP BY TercerosNombres
        - By product: GROUP BY ArticulosNombre
        - By vendor: GROUP BY VendedorFactura
        """
    )

    print("✓ Schema training complete!")


def train_with_examples(vn, examples: Optional[List[Tuple[str, str]]] = None):
    """
    Train Vanna with example question-SQL pairs.

    Args:
        vn: Vanna instance to train
        examples: List of (question, sql) tuples. Uses default examples if None.
    """
    if examples is None:
        examples = get_phase1_training_examples()

    print(f"\nTraining with {len(examples)} examples...")

    for question, sql in examples:
        try:
            vn.train(question=question, sql=sql)
        except Exception as e:
            print(f"⚠️ Skipped example '{question[:30]}...': {e}")

    print("✓ Example training complete!")


def get_phase1_training_examples() -> List[Tuple[str, str]]:
    """
    Phase 1: Core Business Patterns (25 examples)
    Based on real data from 1.4M records in SmartBusiness database.
    """
    return [
        # ============================================================
        # CATEGORY 1: TOP PERFORMERS (8 examples)
        # ============================================================
        # Top Products by Revenue
        (
            "Top 10 productos más vendidos por facturación este año",
            """
            SELECT TOP 10
                ArticulosNombre AS Producto,
                SUM(Cantidad) AS Unidades_Vendidas,
                SUM(TotalMasIva) AS Facturacion_Total,
                SUM(TotalSinIva - ValorCosto) AS Ganancia_Neta
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = YEAR(GETDATE())
            GROUP BY ArticulosNombre
            ORDER BY Facturacion_Total DESC
            """,
        ),
        # Top Products by Quantity (Real data: AMARRES PARA TEJA leads)
        (
            "Productos más vendidos por cantidad",
            """
            SELECT TOP 10
                ArticulosNombre AS Producto,
                SUM(Cantidad) AS Cantidad_Total,
                COUNT(*) AS Numero_Transacciones
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            GROUP BY ArticulosNombre
            ORDER BY Cantidad_Total DESC
            """,
        ),
        # Top Customers by Revenue (Real: FERRETERIA MAGRETH #1)
        (
            "Top 10 clientes con mayor facturación",
            """
            SELECT TOP 10
                TercerosNombres AS Cliente,
                SUM(TotalMasIva) AS Facturacion_Total,
                COUNT(*) AS Numero_Compras,
                AVG(TotalMasIva) AS Ticket_Promedio
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            GROUP BY TercerosNombres
            ORDER BY Facturacion_Total DESC
            """,
        ),
        # Top Vendors by Transactions (Real: CARLOS EFREY PASCUAS #1 with 102K txns)
        (
            "Top vendedores por número de transacciones",
            """
            SELECT TOP 10
                COALESCE(VendedorFactura, vendedor_codigo, VendedorAsignado) AS Vendedor,
                COUNT(*) AS Total_Transacciones,
                SUM(TotalMasIva) AS Ventas_Totales,
                AVG(TotalMasIva) AS Ticket_Promedio
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND (VendedorFactura IS NOT NULL OR vendedor_codigo IS NOT NULL)
            GROUP BY VendedorFactura, vendedor_codigo, VendedorAsignado
            ORDER BY Total_Transacciones DESC
            """,
        ),
        # Top Categories by Revenue (Real: CEMENTO GRIS $45B)
        (
            "Categorías con mayor facturación",
            """
            SELECT TOP 10
                categoria AS Categoria,
                SUM(TotalMasIva) AS Facturacion_Total,
                SUM(TotalSinIva - ValorCosto) AS Ganancia_Neta,
                COUNT(*) AS Numero_Transacciones,
                AVG((TotalSinIva - ValorCosto) * 100.0 / NULLIF(TotalSinIva, 0)) AS Margen_Promedio
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND categoria IS NOT NULL
            GROUP BY categoria
            ORDER BY Facturacion_Total DESC
            """,
        ),
        # Top Providers/Brands (Real: CEMEX $47B, ACESCO $43B)
        (
            "Top proveedores por ventas",
            """
            SELECT TOP 10
                proveedor AS Proveedor,
                SUM(TotalMasIva) AS Ventas_Totales,
                SUM(TotalSinIva - ValorCosto) AS Ganancia_Total,
                COUNT(DISTINCT ArticulosNombre) AS Numero_Productos
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND proveedor IS NOT NULL AND proveedor NOT IN ('^_^', '.', 'D', 'F', '')
            GROUP BY proveedor
            ORDER BY Ventas_Totales DESC
            """,
        ),
        # Top Vendors by Revenue
        (
            "Vendedores con mayores ventas",
            """
            SELECT TOP 10
                COALESCE(VendedorFactura, 'Sin Nombre') AS Vendedor,
                SUM(TotalMasIva) AS Ventas_Totales,
                COUNT(*) AS Numero_Ventas,
                SUM(TotalSinIva - ValorCosto) AS Ganancia_Generada
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND (VendedorFactura IS NOT NULL OR vendedor_codigo IS NOT NULL)
            GROUP BY VendedorFactura
            ORDER BY Ventas_Totales DESC
            """,
        ),
        # Top Cities (Geographic)
        (
            "Ciudades con mayor facturación",
            """
            SELECT TOP 10
                ciudad AS Ciudad,
                SUM(TotalMasIva) AS Facturacion_Total,
                COUNT(DISTINCT TercerosNombres) AS Numero_Clientes
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND ciudad IS NOT NULL
            GROUP BY ciudad
            ORDER BY Facturacion_Total DESC
            """,
        ),
        # ============================================================
        # CATEGORY 2: TIME-SERIES ANALYSIS (6 examples)
        # ============================================================
        # Monthly Sales Current Year
        (
            "Ventas mensuales del año actual",
            """
            SELECT
                MONTH(Fecha) AS Mes,
                DATENAME(MONTH, Fecha) AS Nombre_Mes,
                SUM(TotalMasIva) AS Ventas_Total,
                SUM(TotalSinIva - ValorCosto) AS Ganancia,
                COUNT(*) AS Numero_Transacciones
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = YEAR(GETDATE())
            GROUP BY MONTH(Fecha), DATENAME(MONTH, Fecha)
            ORDER BY Mes
            """,
        ),
        # Year-over-Year Comparison
        (
            "Comparación de ventas año contra año",
            """
            SELECT
                YEAR(Fecha) AS Año,
                SUM(TotalMasIva) AS Ventas_Total,
                SUM(TotalSinIva - ValorCosto) AS Ganancia_Total,
                COUNT(*) AS Numero_Transacciones
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) >= YEAR(GETDATE()) - 2
            GROUP BY YEAR(Fecha)
            ORDER BY Año DESC
            """,
        ),
        # Last 30 Days Trend
        (
            "Ventas de los últimos 30 días",
            """
            SELECT
                Fecha,
                SUM(TotalMasIva) AS Ventas_Diarias,
                COUNT(*) AS Numero_Transacciones
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND Fecha >= DATEADD(DAY, -30, GETDATE())
            GROUP BY Fecha
            ORDER BY Fecha DESC
            """,
        ),
        # Quarterly Analysis
        (
            "Ventas por trimestre",
            """
            SELECT
                YEAR(Fecha) AS Año,
                DATEPART(QUARTER, Fecha) AS Trimestre,
                SUM(TotalMasIva) AS Ventas_Total,
                SUM(TotalSinIva - ValorCosto) AS Ganancia,
                COUNT(*) AS Numero_Transacciones
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) >= YEAR(GETDATE()) - 1
            GROUP BY YEAR(Fecha), DATEPART(QUARTER, Fecha)
            ORDER BY Año DESC, Trimestre DESC
            """,
        ),
        # Daily Average by Month
        (
            "Promedio de ventas diarias por mes",
            """
            SELECT
                YEAR(Fecha) AS Año,
                MONTH(Fecha) AS Mes,
                DATENAME(MONTH, Fecha) AS Nombre_Mes,
                AVG(Ventas_Diarias) AS Promedio_Ventas_Diarias,
                AVG(Num_Transacciones) AS Promedio_Transacciones_Diarias
            FROM (
                SELECT
                    Fecha,
                    SUM(TotalMasIva) AS Ventas_Diarias,
                    COUNT(*) AS Num_Transacciones
                FROM banco_datos
                WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
                GROUP BY Fecha
            ) AS Ventas_Diarias
            GROUP BY YEAR(Fecha), MONTH(Fecha), DATENAME(MONTH, Fecha)
            ORDER BY Año DESC, Mes DESC
            """,
        ),
        # Year-Month Detail
        (
            "Ventas por mes comparando años",
            """
            SELECT
                MONTH(Fecha) AS Mes,
                SUM(CASE WHEN YEAR(Fecha) = YEAR(GETDATE()) THEN TotalMasIva ELSE 0 END) AS Ventas_Año_Actual,
                SUM(CASE WHEN YEAR(Fecha) = YEAR(GETDATE()) - 1 THEN TotalMasIva ELSE 0 END) AS Ventas_Año_Anterior,
                SUM(CASE WHEN YEAR(Fecha) = YEAR(GETDATE()) THEN TotalSinIva - ValorCosto ELSE 0 END) AS Ganancia_Actual
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) >= YEAR(GETDATE()) - 1
            GROUP BY MONTH(Fecha)
            ORDER BY Mes
            """,
        ),
        # ============================================================
        # CATEGORY 3: CATEGORY & BRAND ANALYSIS (6 examples)
        # ============================================================
        # Subcategory Breakdown for Top Category
        (
            "Subcategorías dentro de CEMENTO GRIS",
            """
            SELECT
                subcategoria AS Subcategoria,
                SUM(TotalMasIva) AS Facturacion,
                SUM(Cantidad) AS Volumen_KG,
                COUNT(*) AS Transacciones
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND categoria = 'CEMENTO GRIS'
            AND subcategoria IS NOT NULL
            GROUP BY subcategoria
            ORDER BY Facturacion DESC
            """,
        ),
        # SIKA Products Analysis (Real: $27B provider)
        (
            "Productos de SIKA más vendidos",
            """
            SELECT TOP 10
                ArticulosNombre AS Producto,
                SUM(TotalMasIva) AS Ventas,
                SUM(Cantidad) AS Cantidad_Vendida,
                AVG(TotalMasIva / NULLIF(Cantidad, 0)) AS Precio_Promedio
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND (proveedor = 'SIKA' OR categoria LIKE '%SIKA%' OR subcategoria LIKE '%SIKA%' OR ArticulosNombre LIKE '%SIKA%')
            GROUP BY ArticulosNombre
            ORDER BY Ventas DESC
            """,
        ),
        # CEMEX vs ACESCO Comparison
        (
            "Comparación de ventas entre CEMEX y ACESCO",
            """
            SELECT
                CASE
                    WHEN proveedor = 'CEMEX' THEN 'CEMEX'
                    WHEN proveedor = 'ACESCO' THEN 'ACESCO'
                END AS Proveedor,
                SUM(TotalMasIva) AS Ventas_Totales,
                SUM(TotalSinIva - ValorCosto) AS Ganancia,
                COUNT(*) AS Numero_Ventas,
                AVG(TotalMasIva) AS Ticket_Promedio
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND proveedor IN ('CEMEX', 'ACESCO')
            GROUP BY proveedor
            ORDER BY Ventas_Totales DESC
            """,
        ),
        # Category Market Share
        (
            "Participación de mercado por categoría",
            """
            SELECT
                categoria,
                SUM(TotalMasIva) AS Ventas_Categoria,
                SUM(TotalMasIva) * 100.0 / SUM(SUM(TotalMasIva)) OVER () AS Porcentaje_Mercado,
                SUM(TotalSinIva - ValorCosto) AS Ganancia
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND categoria IS NOT NULL
            AND YEAR(Fecha) = YEAR(GETDATE())
            GROUP BY categoria
            ORDER BY Ventas_Categoria DESC
            """,
        ),
        # Products in Specific Category
        (
            "Productos más vendidos de HIERRO",
            """
            SELECT TOP 10
                ArticulosNombre AS Producto,
                SUM(TotalMasIva) AS Ventas,
                SUM(Cantidad) AS Cantidad_KG,
                SUM(TotalSinIva - ValorCosto) AS Ganancia,
                COUNT(*) AS Transacciones
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND categoria = 'HIERRO'
            GROUP BY ArticulosNombre
            ORDER BY Ventas DESC
            """,
        ),
        # Multi-brand Search
        (
            "Ventas de productos PAVCO o EUROCERAMICA",
            """
            SELECT
                proveedor,
                SUM(TotalMasIva) AS Ventas_Totales,
                COUNT(*) AS Numero_Transacciones,
                SUM(TotalSinIva - ValorCosto) AS Ganancia
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND proveedor IN ('PAVCO', 'EUROCERAMICA')
            GROUP BY proveedor
            ORDER BY Ventas_Totales DESC
            """,
        ),
        # ============================================================
        # CATEGORY 4: PROFIT & MARGIN ANALYSIS (3 examples - Bonus for Phase 1)
        # ============================================================
        # Margin by Category
        (
            "Margen de ganancia por categoría",
            """
            SELECT TOP 10
                categoria,
                SUM(TotalSinIva - ValorCosto) AS Ganancia_Total,
                SUM(TotalSinIva) AS Ventas_Netas,
                AVG((TotalSinIva - ValorCosto) * 100.0 / NULLIF(TotalSinIva, 0)) AS Margen_Promedio_Pct,
                COUNT(*) AS Numero_Transacciones
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND TotalSinIva > 0
            AND categoria IS NOT NULL
            GROUP BY categoria
            ORDER BY Margen_Promedio_Pct DESC
            """,
        ),
        # Low Margin Products
        (
            "Productos con margen menor al 10%",
            """
            SELECT TOP 10
                ArticulosNombre AS Producto,
                AVG((TotalSinIva - ValorCosto) * 100.0 / NULLIF(TotalSinIva, 0)) AS Margen_Promedio,
                SUM(TotalMasIva) AS Ventas_Totales,
                SUM(TotalSinIva - ValorCosto) AS Ganancia_Total
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND TotalSinIva > 0
            GROUP BY ArticulosNombre
            HAVING AVG((TotalSinIva - ValorCosto) * 100.0 / NULLIF(TotalSinIva, 0)) < 10
            ORDER BY Ventas_Totales DESC
            """,
        ),
        # Customer Profitability
        (
            "Clientes más rentables por ganancia",
            """
            SELECT TOP 10
                TercerosNombres AS Cliente,
                SUM(TotalSinIva - ValorCosto) AS Ganancia_Total,
                SUM(TotalMasIva) AS Facturacion,
                AVG((TotalSinIva - ValorCosto) * 100.0 / NULLIF(TotalSinIva, 0)) AS Margen_Promedio,
                COUNT(*) AS Numero_Compras
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND TotalSinIva > 0
            GROUP BY TercerosNombres
            ORDER BY Ganancia_Total DESC
            """,
        ),
        # ============================================================
        # CATEGORY 5: VENDOR PERFORMANCE (2 examples - Bonus for Phase 1)
        # ============================================================
        # Vendor Transaction vs Value Analysis
        (
            "Análisis de volumen vs valor por vendedor",
            """
            SELECT TOP 10
                COALESCE(VendedorFactura, vendedor_codigo) AS Vendedor,
                COUNT(*) AS Numero_Ventas,
                SUM(TotalMasIva) AS Ventas_Totales,
                SUM(TotalMasIva) / COUNT(*) AS Ticket_Promedio,
                SUM(TotalSinIva - ValorCosto) AS Ganancia_Generada
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND (VendedorFactura IS NOT NULL OR vendedor_codigo IS NOT NULL)
            AND YEAR(Fecha) = YEAR(GETDATE())
            GROUP BY VendedorFactura, vendedor_codigo
            ORDER BY Numero_Ventas DESC
            """,
        ),
        # Vendor Commission Pattern
        (
            "Vendedores con mejor desempeño este mes",
            """
            SELECT TOP 10
                COALESCE(VendedorFactura, 'Código: ' + vendedor_codigo) AS Vendedor,
                COUNT(*) AS Ventas_Este_Mes,
                SUM(TotalMasIva) AS Total_Vendido,
                SUM(TotalSinIva - ValorCosto) AS Ganancia_Generada
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND Fecha >= DATEADD(MONTH, -1, GETDATE())
            AND (VendedorFactura IS NOT NULL OR vendedor_codigo IS NOT NULL)
            GROUP BY VendedorFactura, vendedor_codigo
            ORDER BY Total_Vendido DESC
            """,
        ),
        # ============================================================
        # PHASE 1 EXTENDED: ADDITIONAL EXAMPLES FROM REAL DATA (20 examples)
        # Generated from database_explained.json real business data
        # ============================================================
        # Real Brand: CEMEX
        (
            "Ventas de productos CEMEX en 2025",
            """
            SELECT
                ArticulosNombre AS Producto,
                SUM(TotalMasIva) AS Ventas_Total,
                SUM(Cantidad) AS Cantidad_Vendida,
                SUM(TotalSinIva - ValorCosto) AS Ganancia
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = 2025
            AND (proveedor = 'CEMEX' OR categoria = 'CEMEX' OR subcategoria = 'CEMEX' OR marca = 'CEMEX' OR ArticulosNombre LIKE '%CEMEX%')
            GROUP BY ArticulosNombre
            ORDER BY Ventas_Total DESC
            """,
        ),
        # Real Brand: ACESCO
        (
            "Productos ACESCO más vendidos este año",
            """
            SELECT TOP 10
                ArticulosNombre AS Producto,
                SUM(TotalMasIva) AS Ventas,
                SUM(Cantidad) AS Unidades,
                AVG(TotalMasIva / NULLIF(Cantidad, 0)) AS Precio_Promedio
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = YEAR(GETDATE())
            AND (proveedor = 'ACESCO' OR categoria = 'ACESCO' OR subcategoria = 'ACESCO' OR marca = 'ACESCO' OR ArticulosNombre LIKE '%ACESCO%')
            GROUP BY ArticulosNombre
            ORDER BY Ventas DESC
            """,
        ),
        # Real Brand: PAVCO
        (
            "Ventas totales de PAVCO por mes",
            """
            SELECT
                MONTH(Fecha) AS Mes,
                DATENAME(MONTH, Fecha) AS Nombre_Mes,
                SUM(TotalMasIva) AS Ventas,
                SUM(TotalSinIva - ValorCosto) AS Ganancia,
                COUNT(*) AS Numero_Ventas
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = YEAR(GETDATE())
            AND (proveedor = 'PAVCO' OR categoria = 'PAVCO' OR subcategoria = 'PAVCO' OR marca = 'PAVCO' OR ArticulosNombre LIKE '%PAVCO%')
            GROUP BY MONTH(Fecha), DATENAME(MONTH, Fecha)
            ORDER BY Mes
            """,
        ),
        # Real Brand: EUROCERAMICA
        (
            "Productos EUROCERAMICA en inventario vendido",
            """
            SELECT TOP 15
                ArticulosNombre AS Producto,
                SUM(TotalMasIva) AS Ventas_Total,
                SUM(Cantidad) AS Unidades_Vendidas,
                AVG((TotalSinIva - ValorCosto) * 100.0 / NULLIF(TotalSinIva, 0)) AS Margen_Promedio
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND (proveedor = 'EUROCERAMICA' OR categoria = 'EUROCERAMICA' OR subcategoria = 'EUROCERAMICA' OR marca = 'EUROCERAMICA' OR ArticulosNombre LIKE '%EUROCERAMICA%')
            GROUP BY ArticulosNombre
            ORDER BY Ventas_Total DESC
            """,
        ),
        # Real Vendor: CARLOS EFREY PASCUAS
        (
            "Ventas del vendedor CARLOS EFREY PASCUAS",
            """
            SELECT
                ArticulosNombre AS Producto,
                SUM(TotalMasIva) AS Ventas,
                SUM(Cantidad) AS Unidades,
                SUM(TotalSinIva - ValorCosto) AS Ganancia_Generada
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = YEAR(GETDATE())
            AND (VendedorFactura LIKE '%CARLOS EFREY%' OR VendedorFactura LIKE '%PASCUAS%')
            GROUP BY ArticulosNombre
            ORDER BY Ventas DESC
            """,
        ),
        # Real Vendor: YULI ALEJANDRA HIGUERA
        (
            "Productos vendidos por YULI ALEJANDRA HIGUERA",
            """
            SELECT TOP 10
                ArticulosNombre AS Producto,
                SUM(TotalMasIva) AS Ventas,
                COUNT(*) AS Numero_Ventas,
                AVG(TotalMasIva) AS Ticket_Promedio
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = YEAR(GETDATE())
            AND (VendedorFactura LIKE '%YULI%' OR VendedorFactura LIKE '%HIGUERA%')
            GROUP BY ArticulosNombre
            ORDER BY Ventas DESC
            """,
        ),
        # Real Customer: FERRETERIA MAGRETH
        (
            "Compras de FERRETERIA MAGRETH S A S",
            """
            SELECT
                ArticulosNombre AS Producto,
                SUM(TotalMasIva) AS Total_Comprado,
                SUM(Cantidad) AS Cantidad,
                COUNT(*) AS Numero_Compras
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = YEAR(GETDATE())
            AND TercerosNombres LIKE '%FERRETERIA MAGRETH%'
            GROUP BY ArticulosNombre
            ORDER BY Total_Comprado DESC
            """,
        ),
        # Real Customer: FREDI TRUJILLO
        (
            "Historial de compras de FREDI TRUJILLO CULMA",
            """
            SELECT
                MONTH(Fecha) AS Mes,
                SUM(TotalMasIva) AS Facturacion_Mensual,
                COUNT(*) AS Numero_Compras,
                SUM(TotalSinIva - ValorCosto) AS Ganancia_Generada
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = YEAR(GETDATE())
            AND TercerosNombres LIKE '%FREDI TRUJILLO%'
            GROUP BY MONTH(Fecha)
            ORDER BY Mes
            """,
        ),
        # Real Product: AMARRES PARA TEJA
        (
            "Historial de ventas de AMARRES PARA TEJA",
            """
            SELECT
                YEAR(Fecha) AS Año,
                MONTH(Fecha) AS Mes,
                SUM(Cantidad) AS Unidades_Vendidas,
                SUM(TotalMasIva) AS Ventas,
                AVG(TotalMasIva / NULLIF(Cantidad, 0)) AS Precio_Promedio
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND ArticulosNombre = 'AMARRES PARA TEJA'
            AND Fecha >= DATEADD(YEAR, -2, GETDATE())
            GROUP BY YEAR(Fecha), MONTH(Fecha)
            ORDER BY Año DESC, Mes DESC
            """,
        ),
        # Real Product: CEMENTO GRIS CEMEX
        (
            "Ventas mensuales de CEMENTO GRIS USO GENERAL CEMEX 50KG",
            """
            SELECT
                MONTH(Fecha) AS Mes,
                DATENAME(MONTH, Fecha) AS Nombre_Mes,
                SUM(Cantidad) AS Bolsas_Vendidas,
                SUM(TotalMasIva) AS Ventas,
                AVG(TotalMasIva / NULLIF(Cantidad, 0)) AS Precio_Promedio_Por_Bolsa
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND ArticulosNombre LIKE '%CEMENTO GRIS%CEMEX%50KG%'
            AND YEAR(Fecha) = YEAR(GETDATE())
            GROUP BY MONTH(Fecha), DATENAME(MONTH, Fecha)
            ORDER BY Mes
            """,
        ),
        # Real Category: CEMENTO GRIS
        (
            "Análisis de ventas de CEMENTO GRIS por proveedor",
            """
            SELECT
                proveedor AS Proveedor,
                SUM(TotalMasIva) AS Ventas,
                SUM(Cantidad) AS Cantidad_Total,
                COUNT(DISTINCT ArticulosNombre) AS Variedad_Productos
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND categoria = 'CEMENTO GRIS'
            AND YEAR(Fecha) = YEAR(GETDATE())
            GROUP BY proveedor
            ORDER BY Ventas DESC
            """,
        ),
        # Real Category: HIERRO
        (
            "Top productos de HIERRO por rentabilidad",
            """
            SELECT TOP 15
                ArticulosNombre AS Producto,
                SUM(TotalSinIva - ValorCosto) AS Ganancia_Total,
                SUM(TotalMasIva) AS Ventas,
                AVG((TotalSinIva - ValorCosto) * 100.0 / NULLIF(TotalSinIva, 0)) AS Margen_Porcentaje
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND categoria = 'HIERRO'
            AND YEAR(Fecha) = YEAR(GETDATE())
            GROUP BY ArticulosNombre
            ORDER BY Ganancia_Total DESC
            """,
        ),
        # Real Category: ZINC
        (
            "Ventas de productos ZINC por mes",
            """
            SELECT
                YEAR(Fecha) AS Año,
                MONTH(Fecha) AS Mes,
                SUM(TotalMasIva) AS Ventas,
                SUM(Cantidad) AS Kilos_Vendidos,
                COUNT(DISTINCT TercerosNombres) AS Numero_Clientes
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND categoria = 'ZINC'
            AND Fecha >= DATEADD(MONTH, -12, GETDATE())
            GROUP BY YEAR(Fecha), MONTH(Fecha)
            ORDER BY Año DESC, Mes DESC
            """,
        ),
        # Document Type Analysis
        (
            "Comparación de ventas por tipo de documento",
            """
            SELECT
                DocumentosCodigo AS Tipo_Documento,
                CASE
                    WHEN DocumentosCodigo = 'FED' THEN 'Factura Almacen'
                    WHEN DocumentosCodigo = 'FEF' THEN 'Factura Florencia'
                    WHEN DocumentosCodigo = 'FET' THEN 'Factura Calle 5'
                    ELSE DocumentosCodigo
                END AS Descripcion,
                COUNT(*) AS Numero_Documentos,
                SUM(TotalMasIva) AS Ventas_Total,
                AVG(TotalMasIva) AS Promedio_Por_Documento
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = YEAR(GETDATE())
            GROUP BY DocumentosCodigo
            ORDER BY Ventas_Total DESC
            """,
        ),
        # Credit Sales Analysis
        (
            "Ventas a crédito vs contado",
            """
            SELECT
                CASE
                    WHEN DiasCredito = 0 THEN 'Contado'
                    ELSE 'Credito'
                END AS Tipo_Venta,
                COUNT(*) AS Numero_Ventas,
                SUM(TotalMasIva) AS Ventas_Total,
                AVG(DiasCredito) AS Promedio_Dias_Credito,
                SUM(TotalSinIva - ValorCosto) AS Ganancia
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = YEAR(GETDATE())
            GROUP BY CASE WHEN DiasCredito = 0 THEN 'Contado' ELSE 'Credito' END
            ORDER BY Ventas_Total DESC
            """,
        ),
        # Geographic Analysis
        (
            "Ventas por departamento en el Huila",
            """
            SELECT
                ciudad AS Ciudad,
                SUM(TotalMasIva) AS Ventas,
                COUNT(DISTINCT TercerosNombres) AS Numero_Clientes,
                COUNT(*) AS Numero_Transacciones
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND departamento = 'HUILA'
            AND YEAR(Fecha) = YEAR(GETDATE())
            GROUP BY ciudad
            ORDER BY Ventas DESC
            """,
        ),
        # Tax Analysis
        (
            "Análisis de IVA por tasa",
            """
            SELECT
                Iva AS Tasa_IVA,
                COUNT(*) AS Numero_Transacciones,
                SUM(TotalMasIva) AS Ventas_Con_IVA,
                SUM(TotalSinIva) AS Ventas_Sin_IVA,
                SUM(TotalMasIva - TotalSinIva) AS Total_IVA_Cobrado
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = YEAR(GETDATE())
            GROUP BY Iva
            ORDER BY Tasa_IVA
            """,
        ),
        # Discount Analysis
        (
            "Productos con mayor descuento aplicado",
            """
            SELECT TOP 10
                ArticulosNombre AS Producto,
                AVG(PorDescuento) AS Descuento_Promedio,
                SUM(ValorDescuento) AS Total_Descuento,
                SUM(TotalMasIva) AS Ventas_Total,
                COUNT(*) AS Numero_Ventas
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND PorDescuento > 0
            AND YEAR(Fecha) = YEAR(GETDATE())
            GROUP BY ArticulosNombre
            ORDER BY Total_Descuento DESC
            """,
        ),
        # Combined Brand + Vendor Analysis
        (
            "Ventas de SIKA por vendedor CARLOS EFREY PASCUAS",
            """
            SELECT
                ArticulosNombre AS Producto,
                SUM(TotalMasIva) AS Ventas,
                SUM(Cantidad) AS Unidades,
                SUM(TotalSinIva - ValorCosto) AS Ganancia
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = 2025
            AND (proveedor = 'SIKA' OR categoria = 'SIKA' OR subcategoria = 'SIKA' OR marca = 'SIKA' OR ArticulosNombre LIKE '%SIKA%')
            AND (VendedorFactura LIKE '%CARLOS EFREY%' OR VendedorFactura LIKE '%PASCUAS%')
            GROUP BY ArticulosNombre
            ORDER BY Ventas DESC
            """,
        ),
        # Customer Segmentation
        (
            "Segmentación de clientes por volumen de compra",
            """
            SELECT
                CASE
                    WHEN Compra_Total >= 1000000000 THEN 'VIP (> $1B)'
                    WHEN Compra_Total >= 100000000 THEN 'Mayorista (> $100M)'
                    WHEN Compra_Total >= 10000000 THEN 'Regular (> $10M)'
                    ELSE 'Minorista (< $10M)'
                END AS Segmento,
                COUNT(*) AS Numero_Clientes,
                AVG(Compra_Total) AS Promedio_Compra,
                SUM(Compra_Total) AS Ventas_Segmento
            FROM (
                SELECT
                    TercerosNombres,
                    SUM(TotalMasIva) AS Compra_Total
                FROM banco_datos
                WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
                AND YEAR(Fecha) = YEAR(GETDATE())
                GROUP BY TercerosNombres
            ) AS Clientes
            GROUP BY CASE
                WHEN Compra_Total >= 1000000000 THEN 'VIP (> $1B)'
                WHEN Compra_Total >= 100000000 THEN 'Mayorista (> $100M)'
                WHEN Compra_Total >= 10000000 THEN 'Regular (> $10M)'
                ELSE 'Minorista (< $10M)'
            END
            ORDER BY SUM(Compra_Total) DESC
            """,
        ),
    ]


def generate_training_data(
    table_name: str = "banco_datos",
    columns: Optional[List[str]] = None,
    include_common_queries: bool = True,
) -> List[Tuple[str, str]]:
    """
    Generate training data for a database table.

    Args:
        table_name: Name of the table
        columns: List of column names to include
        include_common_queries: Whether to include common query templates

    Returns:
        List of (question, sql) tuples
    """
    if columns is None:
        columns = [
            "Fecha",
            "TotalMasIva",
            "TotalSinIva",
            "ValorCosto",
            "Cantidad",
            "TercerosNombres",
            "ArticulosNombre",
            "ArticulosCodigo",
            "DocumentosCodigo",
            "categoria",
            "subcategoria",
            "VendedorFactura",
            "vendedor_codigo",
            "VendedorAsignado",
            "proveedor",
            "marca",
        ]

    examples = []

    if include_common_queries:
        rev_query = (
            f"SELECT SUM(TotalMasIva) AS Total_Revenue FROM {table_name} "
            f"WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')"
        )
        examples.append((f"Total revenue from {table_name}", rev_query))

    return examples


def get_default_training_examples() -> List[Tuple[str, str]]:
    """
    Backward compatibility alias for get_phase1_training_examples().
    Returns Phase 1 training examples.
    """
    return get_phase1_training_examples()


def full_training(vn, schema_name: str = "SmartBusiness"):
    """
    Perform full training: schema + examples.

    Args:
        vn: Vanna instance to train
        schema_name: Name of the database schema
    """
    train_on_schema(vn, schema_name)
    train_with_examples(vn)
    print(
        f"✓ Full training complete – Vanna's ready to query {schema_name} like a pro!"
    )
