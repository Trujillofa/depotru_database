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
        "dame una lista de los productos menos vendidos en el sika center",
        ["documentoscodigo = 'fef'", "group by articulosnombre", "order by ventas asc"],
        ["marca_proveedor", "productos_adicional"],
        id="sika_center_least_sold",
    ),
    pytest.param(
        "Ventas a crédito vs contado",
        ["diascredito"],
        [],
        id="credito_vs_contado",
    ),
    pytest.param(
        "Productos de SIKA más vendidos",
        ["top 15", "group by bd.articulosnombre", "articulosnombre as producto"],
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
    pytest.param(
        "ventas de SKA",
        ["marca_proveedor", "totalmasiva", "sika"],
        ["totalactiva", "totalventas"],
        id="ska_typo_brand",
    ),
    pytest.param(
        "Cuáles son las ventas de SIKA al mes?",
        ["group by year(fecha)", "totalmasiva", "sika"],
        ["marca_proveedor", "totalactiva"],
        id="sika_monthly",
    ),
    pytest.param(
        "Ventas por mes comparando años",
        ["ventas_anio_actual", "ventas_anio_anterior", "totalmasiva"],
        ["totalactiva", "totalventas", "documentocodigo"],
        id="year_month_compare",
    ),
    pytest.param(
        "Listar ventas con su almacén en J3System",
        [
            "invventas",
            "invventasdetalle",
            "almacenid",
            "almancen",
            "admalmacen",
        ],
        ["banco_datos", "documentoscodigo"],
        id="j3system_warehouse_detail",
    ),
    pytest.param(
        "Ventas agrupadas por bodega en J3System",
        ["group by a.almacencodigo", "count(distinct v.ventaid)"],
        ["banco_datos"],
        id="j3system_warehouse_aggregate",
    ),
    pytest.param(
        "Un almacén por venta en J3System sin duplicar líneas",
        ["cross apply", "top 1 d.almacenid"],
        ["banco_datos"],
        id="j3system_one_warehouse_per_sale",
    ),
    pytest.param(
        "ventas de sika por documento",
        [
            "documentoscodigo in ('fed', 'fef', 'fet')",
            "group by bd.documentoscodigo",
            "sika",
            "sika center",
        ],
        ["invimpresionfactura", "bd.almacencodigo"],
        id="sika_brand_by_document",
    ),
    pytest.param(
        "ventas de sika por almacen",
        [
            "bd.almacencodigo",
            "group by bd.almacencodigo",
            "admalmacen",
            "sika",
            "flo",
        ],
        ["invimpresionfactura", "documentoscodigo in ('fed', 'fef', 'fet')"],
        id="sika_brand_by_warehouse",
    ),
    pytest.param(
        "ventas de sika en flo",
        [
            "banco_datos",
            "bd.almacencodigo = 'flo'",
            "sika",
            "numero_transacciones",
        ],
        ["invventas", "invventasdetalle"],
        id="sika_brand_at_warehouse_flo",
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
        assert (
            fragment in lower
        ), f"Expected '{fragment}' in SQL for '{question}':\n{sql}"
    for fragment in must_not_contain:
        assert (
            fragment not in lower
        ), f"Unexpected '{fragment}' in SQL for '{question}':\n{sql}"
