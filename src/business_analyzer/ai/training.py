"""
Training module for AI package.

Contains schema training logic for Vanna AI.
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

    # 2. Business Rules/Docs - Critical field mappings
    vn.train(
        documentation="""
        SmartBusiness – Ferretería Sales Database

        CRITICAL RULE: ALWAYS add WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC') to exclude test/cancelled docs.

        FIELD MAPPING - VERY IMPORTANT:
        --------------------------------
        CUSTOMER info:
        - TercerosNombres = CUSTOMER name (NOT vendor!)

        VENDOR/SELLER info (use these for 'vendedor' queries):
        - VendedorFactura = Vendor name on receipt (e.g. 'DIANA PATRICIA CULMA')
        - vendedor_codigo = Vendor code (e.g. '093', '106')
        - VendedorAsignado = Vendor for credit sales (e.g. '106-DIANA PATRICIA CULMA')

        BRAND/CATEGORY filtering (check ALL these fields for brand queries):
        - proveedor = Products provider (e.g. 'SIKA', 'BELLOTA', 'PAVCO')
        - categoria = Product category
        - subcategoria = Product subcategory
        - marca = Brand name
        - ArticulosNombre = Product name (may contain brand name)

        BRAND FILTERING RULE: For queries like 'productos SIKA', ALWAYS check ALL of:
        (proveedor = 'SIKA' OR categoria = 'SIKA' OR subcategoria = 'SIKA' OR ArticulosNombre LIKE '%SIKA%')

        VENDOR FILTERING EXAMPLES:
        - 'vendedor 093' -> VendedorFactura LIKE '%093%' OR vendedor_codigo LIKE '%093%' OR VendedorAsignado LIKE '%093%'
        - 'vendedor DIANA' -> VendedorFactura LIKE '%DIANA%'
        - 'vendedor con codigo 106' -> vendedor_codigo = '106'

        Key Metrics:
        - Revenue: SUM(TotalMasIva)
        - Net Revenue: SUM(TotalSinIva)
        - Profit: SUM(TotalSinIva - ValorCosto)
        - Margin %: (TotalSinIva - ValorCosto) / TotalSinIva * 100
        - Tax (IVA): TotalMasIva - TotalSinIva

        Queries in Spanish work best (e.g., 'productos vendidos').
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
        examples = get_default_training_examples()

    print(f"\nTraining with {len(examples)} examples...")

    for question, sql in examples:
        try:
            vn.train(question=question, sql=sql)
        except Exception as e:
            print(f"⚠️ Skipped example '{question[:30]}...': {e}")

    print("✓ Example training complete!")


def get_default_training_examples() -> List[Tuple[str, str]]:
    """
    Get expanded hardware-specific training examples for SmartBusiness.
    Covers sales, inventory, customers, and temporal trends.
    """
    return [
        (
            "Top 10 productos más vendidos este año",
            """
            SELECT TOP 10 ArticulosNombre AS Producto, SUM(Cantidad) AS Unidades_Vendidas,
            SUM(TotalMasIva) AS Revenue FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = YEAR(GETDATE())
            GROUP BY ArticulosNombre ORDER BY Revenue DESC
            """,
        ),
        (
            "Ganancias por categoría en el último mes",
            """
            SELECT categoria, SUM(TotalSinIva - ValorCosto) AS Ganancia_Neta FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND Fecha >= DATEADD(MONTH, -1, GETDATE())
            GROUP BY categoria ORDER BY Ganancia_Neta DESC
            """,
        ),
        # VENDOR EXAMPLES
        (
            "Ventas del vendedor con código 093",
            """
            SELECT ArticulosNombre AS Producto, SUM(TotalMasIva) AS Ventas,
            SUM(Cantidad) AS Unidades FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = YEAR(GETDATE())
            AND (VendedorFactura LIKE '%093%' OR vendedor_codigo LIKE '%093%' OR VendedorAsignado LIKE '%093%')
            GROUP BY ArticulosNombre ORDER BY Ventas DESC
            """,
        ),
        (
            "Ventas del vendedor DIANA",
            """
            SELECT ArticulosNombre AS Producto, SUM(TotalMasIva) AS Ventas,
            SUM(Cantidad) AS Unidades FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND VendedorFactura LIKE '%DIANA%'
            GROUP BY ArticulosNombre ORDER BY Ventas DESC
            """,
        ),
        # BRAND EXAMPLES - Check ALL brand fields
        (
            "Ventas de productos SIKA este año",
            """
            SELECT ArticulosNombre AS Producto, SUM(TotalMasIva) AS Ventas,
            SUM(Cantidad) AS Unidades FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = YEAR(GETDATE())
            AND (proveedor = 'SIKA' OR categoria = 'SIKA' OR subcategoria = 'SIKA' OR ArticulosNombre LIKE '%SIKA%')
            GROUP BY ArticulosNombre ORDER BY Ventas DESC
            """,
        ),
        (
            "Ventas de productos BELLOTA este año",
            """
            SELECT ArticulosNombre AS Producto, SUM(TotalMasIva) AS Ventas,
            SUM(Cantidad) AS Unidades FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = YEAR(GETDATE())
            AND (proveedor = 'BELLOTA' OR categoria = 'BELLOTA' OR subcategoria = 'BELLOTA' OR ArticulosNombre LIKE '%BELLOTA%')
            GROUP BY ArticulosNombre ORDER BY Ventas DESC
            """,
        ),
        # COMBINED VENDOR + BRAND EXAMPLE
        (
            "Ventas de SIKA por vendedor 095 en 2026",
            """
            SELECT ArticulosNombre AS Producto, SUM(TotalMasIva) AS Ventas,
            SUM(Cantidad) AS Unidades FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) = 2026
            AND (proveedor = 'SIKA' OR categoria = 'SIKA' OR subcategoria = 'SIKA' OR ArticulosNombre LIKE '%SIKA%')
            AND (VendedorFactura LIKE '%095%' OR vendedor_codigo LIKE '%095%' OR VendedorAsignado LIKE '%095%')
            GROUP BY ArticulosNombre ORDER BY Ventas DESC
            """,
        ),
        (
            "Top 10 clientes por facturación total",
            """
            SELECT TOP 10 TercerosNombres AS Cliente, SUM(TotalMasIva) AS Facturacion_Total
            FROM banco_datos WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            GROUP BY TercerosNombres ORDER BY Facturacion_Total DESC
            """,
        ),
        (
            "Margen de ganancia promedio por subcategoría",
            """
            SELECT subcategoria, AVG((TotalSinIva - ValorCosto) * 100.0 / NULLIF(TotalSinIva, 0))
            AS Margen_Promedio_Pct FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND TotalSinIva > 0 GROUP BY subcategoria ORDER BY Margen_Promedio_Pct DESC
            """,
        ),
        (
            "Ventas mensuales comparando este año vs año pasado",
            """
            SELECT YEAR(Fecha) AS Ano, MONTH(Fecha) AS Mes, SUM(TotalMasIva) AS Ventas
            FROM banco_datos WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND YEAR(Fecha) >= YEAR(GETDATE()) - 1 GROUP BY YEAR(Fecha), MONTH(Fecha) ORDER BY Mes, Ano
            """,
        ),
        (
            "Categorías que representan el 80% de la facturación",
            """
            SELECT categoria, SUM(TotalMasIva) AS Facturacion FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            GROUP BY categoria ORDER BY Facturacion DESC
            """,
        ),
        (
            "Ranking de proveedores por rentabilidad",
            """
            SELECT proveedor AS Proveedor, SUM(TotalSinIva - ValorCosto) AS Ganancia_Total
            FROM banco_datos WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            GROUP BY proveedor ORDER BY Ganancia_Total DESC
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
