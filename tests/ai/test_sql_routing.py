"""Golden-question SQL routing matrix (session-verified queries)."""

from unittest.mock import MagicMock

import pytest

from business_analyzer.ai.base import AIVanna


def _generate_sql_no_cache(question: str) -> str:
    vn = object.__new__(AIVanna)
    vn._query_cache = MagicMock()
    vn._query_cache.get.return_value = None
    vn.provider = "grok"
    return AIVanna.generate_sql(vn, question)


GOLDEN_QUESTIONS = [
    pytest.param(
        "Top 10 clientes con mayor facturación",
        ["ganancia_neta", "top 10"],
        [],
        id="top_clientes",
    ),
    pytest.param(
        "Vendedores con mejor desempeño este mes",
        ["month(fecha) = month(getdate())", "total_vendido"],
        ["group by vendedorfactura, vendedor_codigo"],
        id="vendedor_desempeno",
    ),
    pytest.param(
        "Promedio de ventas diarias por mes",
        ["sum(totalmasiva)", "promedio_ventas_diarias"],
        ["ventatotal"],
        id="promedio_diario_mes",
    ),
    pytest.param(
        "Comparación de ventas por tipo de documento",
        ["documentoscodigo in ('fed', 'fef', 'fet')", "totalmasiva"],
        ["ventatotal"],
        id="tipo_documento",
    ),
    pytest.param(
        "Ventas de los últimos 30 días",
        ["group by fecha", "ventas_diarias", "sum(totalmasiva)"],
        ["tabla"],
        id="ultimos_30_dias",
    ),
    pytest.param(
        "Ventas de la sede Sika Center por mes",
        ["documentoscodigo = 'fef'"],
        ["marca_proveedor"],
        id="sika_center_mes",
    ),
    pytest.param(
        "Ventas a crédito vs contado",
        ["diascredito"],
        [],
        id="credito_vs_contado",
    ),
    pytest.param(
        "Productos de SIKA más vendidos",
        ["top 10", "group by articulosnombre", "articulosnombre as producto"],
        ["marca_proveedor"],
        id="sika_productos",
    ),
    pytest.param(
        "Ventas de productos SIKA",
        ["marca_proveedor"],
        ["group by articulosnombre"],
        id="sika_brand_total",
    ),
    pytest.param(
        "Productos más vendidos de HIERRO",
        ["group by articulosnombre", "categoria"],
        ["marca_proveedor"],
        id="hierro_productos",
    ),
    pytest.param(
        "Top 10 productos más vendidos por facturación este año",
        ["top 10", "group by articulosnombre", "facturacion_total"],
        ["marca_proveedor"],
        id="top_productos_facturacion",
    ),
]


@pytest.mark.parametrize(
    "question,must_contain,must_not_contain",
    GOLDEN_QUESTIONS,
)
def test_golden_question_sql_routing(question, must_contain, must_not_contain):
    sql = _generate_sql_no_cache(question)
    assert sql, f"No SQL generated for: {question}"
    lower = sql.lower()
    for fragment in must_contain:
        assert fragment in lower, (
            f"Expected '{fragment}' in SQL for '{question}':\n{sql}"
        )
    for fragment in must_not_contain:
        assert fragment not in lower, (
            f"Unexpected '{fragment}' in SQL for '{question}':\n{sql}"
        )