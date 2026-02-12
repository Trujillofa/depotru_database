"""
Training module for AI package.

Contains schema training logic for Vanna AI.
"""

from typing import List, Tuple


def train_on_schema(vn, schema_name: str = "SmartBusiness"):
    """
    Train Vanna on database schema and business rules.

    Args:
        vn: Vanna instance to train
        schema_name: Name of the database schema
    """
    print(f"\nTraining on {schema_name} schema & rules...")

    # 1. DDL (Table Structure)
    vn.train(
        ddl="""
        CREATE TABLE banco_datos (
            Fecha DATE,
            TotalMasIva DECIMAL(18,2),
            TotalSinIva DECIMAL(18,2),
            ValorCosto DECIMAL(18,2),
            Cantidad INT,
            TercerosNombres NVARCHAR(200),
            ArticulosNombre NVARCHAR(200),
            ArticulosCodigo NVARCHAR(50),
            DocumentosCodigo NVARCHAR(10),
            categoria NVARCHAR(100),
            subcategoria NVARCHAR(100)
        );
    """
    )

    # 2. Business Rules/Docs
    vn.train(
        documentation="""
        SmartBusiness – Ferretería Sales Database
        CRITICAL RULE: ALWAYS add WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS') to exclude test/cancelled docs.
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


def train_with_examples(vn, examples: List[Tuple[str, str]] = None):
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
            "Productos con margen de ganancia inferior al 10%",
            """
            SELECT ArticulosNombre, categoria, AVG((TotalSinIva - ValorCosto) * 100.0 / NULLIF(TotalSinIva, 0))
            AS Margen FROM banco_datos WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            AND TotalSinIva > 0 GROUP BY ArticulosNombre, categoria
            HAVING AVG((TotalSinIva - ValorCosto) * 100.0 / NULLIF(TotalSinIva, 0)) < 10 ORDER BY Margen ASC
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
            "Clientes que no han comprado en los últimos 90 días",
            """
            SELECT TercerosNombres, MAX(Fecha) AS Ultima_Compra FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            GROUP BY TercerosNombres HAVING MAX(Fecha) < DATEADD(DAY, -90, GETDATE())
            ORDER BY Ultima_Compra DESC
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
            "Ticket promedio por mes",
            """
            SELECT YEAR(Fecha) AS Ano, MONTH(Fecha) AS Mes,
            SUM(TotalMasIva) / COUNT(DISTINCT NumeroDocumento) AS Ticket_Promedio
            FROM banco_datos WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            GROUP BY YEAR(Fecha), MONTH(Fecha) ORDER BY Ano DESC, Mes DESC
            """,
        ),
        (
            "Días de la semana con mayor volumen de ventas",
            """
            SELECT DATENAME(WEEKDAY, Fecha) AS Dia, SUM(TotalMasIva) AS Ventas
            FROM banco_datos WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            GROUP BY DATENAME(WEEKDAY, Fecha), DATEPART(WEEKDAY, Fecha) ORDER BY DATEPART(WEEKDAY, Fecha)
            """,
        ),
        (
            "Ranking de proveedores por rentabilidad",
            """
            SELECT subcategoria AS Proveedor, SUM(TotalSinIva - ValorCosto) AS Ganancia_Total
            FROM banco_datos WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            GROUP BY subcategoria ORDER BY Ganancia_Total DESC
            """,
        ),
    ]


def generate_training_data(
    table_name: str = "banco_datos",
    columns: List[str] = None,
    include_common_queries: bool = True,
) -> List[Tuple[str, str]]:
    """
    Generate training data for a database table.

    Args:
        table_name: Name of the table
        columns: List of column names
        include_common_queries: Whether to include common query patterns

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
        ]

    examples = []

    if include_common_queries:
        # Revenue queries
        # nosec B608: table_name is validated by caller with validate_sql_identifier()
        rev_query = (
            f"SELECT SUM(TotalMasIva) AS Total_Revenue FROM {table_name} "
            f"WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')"
        )
        examples.append((f"Total revenue from {table_name}", rev_query))

        # Top products
        # nosec B608: table_name is validated by caller with validate_sql_identifier()
        prod_query = (
            f"SELECT TOP 10 ArticulosNombre, SUM(Cantidad) AS Total_Quantity "
            f"FROM {table_name} WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS') "
            f"GROUP BY ArticulosNombre ORDER BY Total_Quantity DESC"
        )
        examples.append((f"Top selling products from {table_name}", prod_query))

        # Monthly trends
        # nosec B608: table_name is validated by caller with validate_sql_identifier()
        trend_query = (
            f"SELECT YEAR(Fecha) AS Year, MONTH(Fecha) AS Month, "
            f"SUM(TotalMasIva) AS Revenue FROM {table_name} "
            f"WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS') "
            f"GROUP BY YEAR(Fecha), MONTH(Fecha) ORDER BY Year, Month"
        )
        examples.append((f"Monthly revenue trends from {table_name}", trend_query))

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
