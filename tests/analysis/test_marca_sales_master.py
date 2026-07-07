"""Tests that marca sales prefer productos_adicional over banco_datos.marca."""

from decimal import Decimal
from unittest.mock import Mock, patch

from business_analyzer.analysis.manager_report import ManagerSalesReport


class TestMarcaSalesMaster:
    def _setup_runner(self, mock_runner_class, sales_data, product_map):
        runner = mock_runner_class.return_value
        runner.fetch_sales_data.return_value = sales_data
        runner.fetch_sql_aggregations.side_effect = RuntimeError("sql off")
        runner.fetch_ytd_sql_aggregations.side_effect = RuntimeError("ytd off")
        runner.fetch_year_to_date_data.return_value = sales_data
        runner.fetch_sb_product_map.return_value = product_map
        runner.fetch_j3system_inventory.return_value = {}
        runner.fetch_j3system_product_details.return_value = ({}, {})
        runner.fetch_j3system_warehouse_sales.return_value = {
            "breakdown": [],
            "sales": [],
        }
        runner.fetch_budget_vs_actual.return_value = {
            "available": False,
            "note": "off",
            "periodo": None,
            "sellers": [],
            "summary": {},
        }
        return runner

    @patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
    def test_marca_sales_use_producto_marca_from_master(self, MockRunner):
        sales = [
            {
                "Fecha": "2024-05-01",
                "TotalSinIva": Decimal("100000"),
                "ValorCosto": Decimal("70000"),
                "Cantidad": 5,
                "ArticulosCodigo": "SKU1",
                "marca": "HERRAMIENTAS SIKA",
                "proveedor": "PROV",
                "DocumentosCodigo": "FED",
            }
        ]
        product_map = {
            "SKU1": {"marca": "SIKA", "proveedor": "SIKA COLOMBIA"},
        }
        self._setup_runner(MockRunner, sales, product_map)

        report = ManagerSalesReport(2024, 5, use_j3system=False)
        result = report.generate()
        marcas = result["marca_sales"]

        assert len(marcas) == 1
        assert marcas[0]["marca_name"] == "SIKA"
        assert marcas[0]["total_revenue"] == 100000.0
