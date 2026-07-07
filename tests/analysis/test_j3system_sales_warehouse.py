"""Tests for J3System sales-to-warehouse SQL builders."""

import pytest

from business_analyzer.core.j3system_sales_warehouse import (
    WAREHOUSE_CODES,
    build_one_warehouse_per_sale_for_period_sql,
    build_one_warehouse_per_sale_sql,
    build_sales_by_warehouse_sql,
    build_sales_warehouse_detail_sql,
    build_sales_warehouse_sql_for_question,
    build_warehouse_breakdown_for_period_sql,
    extract_warehouse_code,
    is_aggregated_warehouse_question,
    is_j3system_warehouse_question,
    is_one_warehouse_per_sale_question,
    qualified_j3_table,
)


@pytest.mark.unit
def test_qualified_j3_table_defaults_to_j3system():
    assert qualified_j3_table("InvVentas") == "J3System.dbo.InvVentas"


@pytest.mark.unit
def test_detail_sql_joins_invventas_detalle_and_admalmacen():
    sql = build_sales_warehouse_detail_sql()
    lower = sql.lower()
    assert "from j3system.dbo.invventas v" in lower
    assert "join j3system.dbo.invventasdetalle d" in lower
    assert "d.ventaid = v.ventaid" in lower
    assert "left join j3system.dbo.admalmacen a" in lower
    assert "a.almacencodigo as almancen" in lower


@pytest.mark.unit
def test_detail_sql_filters_empty_almancen_and_supports_top_n():
    sql = build_sales_warehouse_detail_sql(top_n=15)
    assert "TOP 15" in sql
    assert "a.AlmacenCodigo <> ''" in sql


@pytest.mark.unit
def test_detail_sql_filters_by_warehouse_code():
    sql = build_sales_warehouse_detail_sql(warehouse_code="FLO")
    assert "a.AlmacenCodigo = 'FLO'" in sql


@pytest.mark.unit
def test_detail_sql_rejects_unknown_warehouse_code():
    with pytest.raises(ValueError, match="Unknown warehouse code"):
        build_sales_warehouse_detail_sql(warehouse_code="ZZZ")


@pytest.mark.unit
def test_by_warehouse_sql_aggregates_distinct_ventas():
    sql = build_sales_by_warehouse_sql()
    assert "COUNT(DISTINCT v.VentaID) AS Numero_Ventas" in sql
    assert "GROUP BY a.AlmacenCodigo, a.AlmacenNombre" in sql


@pytest.mark.unit
def test_one_warehouse_per_sale_uses_cross_apply():
    sql = build_one_warehouse_per_sale_sql()
    lower = sql.lower()
    assert "cross apply" in lower
    assert "top 1 d.almacenid" in lower
    assert "invventasdetalle d" in lower


@pytest.mark.unit
@pytest.mark.parametrize(
    "question,expected",
    [
        ("ventas por bodega en j3system", True),
        ("Listar Almancen por factura", True),
        ("Ventas del almacén FLO", True),
        ("Ventas del Sika Center este año", False),
        ("Ventas de Calle 5 este año", False),
        ("ventas de sika por almacen", False),
        ("ventas de sika en flo", False),
        ("Ventas de CEMEX por sede", False),
    ],
)
def test_is_j3system_warehouse_question(question, expected):
    assert is_j3system_warehouse_question(question) is expected


@pytest.mark.unit
def test_extract_warehouse_code_finds_dot_rot():
    assert extract_warehouse_code("ventas del almacén B.ROT") == "B.ROT"


@pytest.mark.unit
def test_extract_warehouse_code_ignores_spanish_con_preposition():
    assert extract_warehouse_code("Top 10 clientes con mayor facturación") is None
    assert extract_warehouse_code("Listar ventas con su almacén en J3System") is None


@pytest.mark.unit
def test_extract_warehouse_code_finds_con_when_explicit():
    assert extract_warehouse_code("Ventas del almacén CON en J3System") == "CON"


@pytest.mark.unit
def test_is_j3system_warehouse_question_false_for_top_clientes():
    assert (
        is_j3system_warehouse_question("Top 10 clientes con mayor facturación") is False
    )


@pytest.mark.unit
def test_sql_for_question_picks_aggregate_template():
    sql = build_sales_warehouse_sql_for_question("Ventas agrupadas por bodega")
    assert "GROUP BY a.AlmacenCodigo" in sql


@pytest.mark.unit
def test_sql_for_question_picks_one_per_sale_template():
    sql = build_sales_warehouse_sql_for_question("Un almacén por venta sin duplicar")
    assert "CROSS APPLY" in sql


@pytest.mark.unit
def test_warehouse_codes_count_is_14():
    assert len(WAREHOUSE_CODES) == 14


@pytest.mark.unit
def test_period_breakdown_sql_filters_by_fecha_and_aggregates_revenue():
    sql = build_warehouse_breakdown_for_period_sql("2024-05-01", "2024-05-31")
    lower = sql.lower()
    assert "v.fecha between '2024-05-01' and '2024-05-31'" in lower
    assert "sum(d.ventasiniva) as revenue_without_iva" in lower
    assert "count(distinct v.ventaid) as sale_count" in lower


@pytest.mark.unit
def test_period_one_per_sale_sql_uses_cross_apply_and_top():
    sql = build_one_warehouse_per_sale_for_period_sql(
        "2024-05-01", "2024-05-31", top_n=25
    )
    assert "TOP 25" in sql
    assert "CROSS APPLY" in sql
    assert "v.Fecha BETWEEN '2024-05-01' AND '2024-05-31'" in sql


@pytest.mark.unit
def test_detection_helpers_for_template_variants():
    assert is_aggregated_warehouse_question("totales por almacén")
    assert is_one_warehouse_per_sale_question("primera bodega por venta")
