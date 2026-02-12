"""
Training module for AI package.

Contains schema training logic for Vanna AI.
"""

from typing import List, Tuple, Optional


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
    Get default training examples for SmartBusiness database.

    Returns:
        List of (question, sql) tuples
    """
    return [
        (
            "Top 10 productos más vendidos este año",
            """
            SELECT TOP 10
                ArticulosNombre AS Producto,
                SUM(Cantidad) AS Unidades_Vendidas,
                SUM(TotalMasIva) AS Revenue
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
              AND YEAR(Fecha) = YEAR(GETDATE())
            GROUP BY ArticulosNombre
            ORDER BY Revenue DESC
        """,
        ),
        (
            "Ganancias por categoría en el último mes",
            """
            SELECT
                categoria,
                SUM(TotalSinIva - ValorCosto) AS Ganancia_Neta
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
              AND Fecha >= DATEADD(MONTH, -1, GETDATE())
            GROUP BY categoria
            ORDER BY Ganancia_Neta DESC
        """,
        ),
        (
            "Top 10 clientes por facturación total",
            """
            SELECT TOP 10
                TercerosNombres AS Cliente,
                SUM(TotalMasIva) AS Facturacion_Total
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
            GROUP BY TercerosNombres
            ORDER BY Facturacion_Total DESC
        """,
        ),
        (
            "Margen de ganancia promedio por subcategoría",
            """
            SELECT
                subcategoria,
                AVG((TotalSinIva - ValorCosto) * 100.0 / NULLIF(TotalSinIva, 0)) AS Margen_Promedio_Pct
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS') AND TotalSinIva > 0
            GROUP BY subcategoria
            ORDER BY Margen_Promedio_Pct DESC
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
        examples.append(
            (
                f"Total revenue from {table_name}",
                f"SELECT SUM(TotalMasIva) AS Total_Revenue FROM {table_name} WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')",
            )
        )

        # Top products
        examples.append(
            (
                f"Top selling products from {table_name}",
                f"SELECT TOP 10 ArticulosNombre, SUM(Cantidad) AS Total_Quantity FROM {table_name} WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS') GROUP BY ArticulosNombre ORDER BY Total_Quantity DESC",
            )
        )

        # Monthly trends
        examples.append(
            (
                f"Monthly revenue trends from {table_name}",
                f"SELECT YEAR(Fecha) AS Year, MONTH(Fecha) AS Month, SUM(TotalMasIva) AS Revenue FROM {table_name} WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS') GROUP BY YEAR(Fecha), MONTH(Fecha) ORDER BY Year, Month",
            )
        )

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
