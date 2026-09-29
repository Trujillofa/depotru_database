"""Programming bugs must not become silent wrong manager numbers."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from business_analyzer.analysis.manager_report import ManagerSalesReport
from business_analyzer.core.database import QueryError


def _sales_row():
    return {
        "Fecha": "2024-05-01",
        "TotalMasIva": 121000.0,
        "TotalSinIva": 100000.0,
        "ValorCosto": 70000.0,
        "Cantidad": 10,
        "TercerosNombres": "Cliente A",
        "ArticulosNombre": "Producto A",
        "ArticulosCodigo": "SKU001",
        "categoria": "Herramientas",
        "subcategoria": "Manuales",
        "DocumentosCodigo": "FE",
        "proveedor": "PROV1",
    }


def _wire_runner(mock_runner_class, *, sql_error, ytd_error=None, budget_error=None):
    runner = mock_runner_class.return_value
    runner.fetch_sales_data.return_value = [_sales_row()]
    runner.fetch_sql_aggregations.side_effect = sql_error
    runner.fetch_ytd_sql_aggregations.side_effect = ytd_error or QueryError("ytd off")
    runner.fetch_year_to_date_data.return_value = [_sales_row()]
    runner.fetch_sb_product_map.return_value = {}
    runner.fetch_j3system_inventory.return_value = {}
    runner.fetch_j3system_product_details.return_value = ({}, {})
    runner.fetch_j3system_warehouse_sales.return_value = {
        "breakdown": [],
        "sales": [],
    }
    if budget_error is not None:
        runner.fetch_budget_vs_actual.side_effect = budget_error
    else:
        runner.fetch_budget_vs_actual.return_value = {
            "available": False,
            "note": "off",
            "periodo": None,
            "sellers": [],
            "summary": {},
        }
    return runner


@pytest.mark.unit
@patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
def test_sql_aggregation_type_error_is_not_swallowed(MockRunner):
    _wire_runner(MockRunner, sql_error=TypeError("broken mapper"))
    report = ManagerSalesReport(2024, 5, use_j3system=False)
    with pytest.raises(TypeError, match="broken mapper"):
        report.generate()


@pytest.mark.unit
@patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
def test_sql_query_error_falls_back_to_row_math(MockRunner):
    _wire_runner(MockRunner, sql_error=QueryError("timeout"))
    report = ManagerSalesReport(2024, 5, use_j3system=False)
    result = report.generate()
    assert result["summary"]["total_revenue_with_iva"] == 121000.0
    assert result["summary"]["gross_profit"] == 30000.0


@pytest.mark.unit
@patch("business_analyzer.analysis.manager_report.report.ContabilidadRunner")
@patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
def test_contabilidad_type_error_is_not_swallowed(MockRunner, MockContabilidad):
    _wire_runner(MockRunner, sql_error=QueryError("sql off"))
    MockContabilidad.return_value.build_report.side_effect = TypeError(
        "contabilidad bug"
    )
    report = ManagerSalesReport(2024, 5, use_j3system=True)
    with pytest.raises(TypeError, match="contabilidad bug"):
        report.generate()


@pytest.mark.unit
@patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
def test_budget_type_error_is_not_swallowed(MockRunner):
    _wire_runner(
        MockRunner,
        sql_error=QueryError("sql off"),
        budget_error=TypeError("budget bug"),
    )
    report = ManagerSalesReport(2024, 5, use_j3system=False)
    with pytest.raises(TypeError, match="budget bug"):
        report.generate()
