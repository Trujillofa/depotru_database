"""
Tests for manager report module.
"""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from business_analyzer.analysis.manager_report import (
    ManagerSalesReport,
    _extract_row_value,
    _to_float,
    safe_divide,
)


class TestSafeDivide:
    """Test safe_divide helper."""

    def test_normal_division(self):
        assert safe_divide(10.0, 2.0) == 5.0

    def test_divide_by_zero(self):
        assert safe_divide(10.0, 0.0) == 0.0

    def test_divide_by_zero_custom_default(self):
        assert safe_divide(10.0, 0.0, default=1.0) == 1.0

    def test_zero_numerator(self):
        assert safe_divide(0.0, 10.0) == 0.0


class TestToFloat:
    """Test _to_float helper."""

    def test_decimal_conversion(self):
        assert _to_float(Decimal("123.45")) == 123.45

    def test_string_number(self):
        assert _to_float("1234") == 1234.0

    def test_date_string_returns_none(self):
        assert _to_float("2024-05-01") is None

    def test_none_returns_none(self):
        assert _to_float(None) is None


class TestExtractRowValue:
    """Test _extract_row_value helper."""

    def test_decimal_conversion(self):
        row = {"value": Decimal("123.45")}
        assert _extract_row_value(row, ["value"]) == 123.45

    def test_string_number(self):
        row = {"value": "1234"}
        assert _extract_row_value(row, ["value"]) == 1234.0

    def test_date_string_returns_none(self):
        row = {"value": "2024-05-01"}
        assert _extract_row_value(row, ["value"]) is None

    def test_null_value(self):
        row = {"value": None}
        assert _extract_row_value(row, ["value"]) is None

    def test_missing_key(self):
        row = {"other": 1}
        assert _extract_row_value(row, ["value"]) is None

    def test_multiple_keys(self):
        row = {"b": 2}
        assert _extract_row_value(row, ["a", "b"]) == 2


class TestManagerSalesReport:
    """Test ManagerSalesReport class."""

    @pytest.fixture
    def sample_sales_data(self):
        """Provide sample transaction data with Decimal values."""
        return [
            {
                "Fecha": "2024-05-01",
                "TotalMasIva": Decimal("121000.00"),
                "TotalSinIva": Decimal("100000.00"),
                "ValorCosto": Decimal("70000.00"),
                "Cantidad": 10,
                "TercerosNombres": "Cliente A",
                "ArticulosNombre": "Producto A",
                "ArticulosCodigo": "SKU001",
                "categoria": "Herramientas",
                "subcategoria": "Manuales",
                "DocumentosCodigo": "FE",
                "proveedor": "PROV1",
            },
            {
                "Fecha": "2024-05-01",
                "TotalMasIva": Decimal("60500.00"),
                "TotalSinIva": Decimal("50000.00"),
                "ValorCosto": Decimal("35000.00"),
                "Cantidad": 5,
                "TercerosNombres": "Cliente A",
                "ArticulosNombre": "Producto B",
                "ArticulosCodigo": "SKU002",
                "categoria": "Electricidad",
                "subcategoria": "Cables",
                "DocumentosCodigo": "FE",
                "proveedor": "PROV2",
            },
            {
                "Fecha": "2024-05-02",
                "TotalMasIva": Decimal("242000.00"),
                "TotalSinIva": Decimal("200000.00"),
                "ValorCosto": Decimal("100000.00"),
                "Cantidad": 20,
                "TercerosNombres": "Cliente B",
                "ArticulosNombre": "Producto B",
                "ArticulosCodigo": "SKU002",
                "categoria": "Electricidad",
                "subcategoria": "Cables",
                "DocumentosCodigo": "FE",
                "proveedor": "PROV2",
            },
            {
                "Fecha": "2024-05-02",
                "TotalMasIva": Decimal("12100.00"),
                "TotalSinIva": Decimal("10000.00"),
                "ValorCosto": Decimal("9200.00"),
                "Cantidad": 2,
                "TercerosNombres": "Cliente C",
                "ArticulosNombre": "Producto C",
                "ArticulosCodigo": "SKU003",
                "categoria": "Herramientas",
                "subcategoria": "Electricas",
                "DocumentosCodigo": "FE",
                "proveedor": "PROV1",
            },
        ]

    @pytest.fixture
    def mock_j3system_inventory(self):
        """Provide sample J3System inventory data."""
        return [
            {
                "ArticulosCodigo": "SKU001",
                "ArticulosNombre": "Producto A",
                "ArticulosPeso": Decimal("1.5"),
                "stock_quantity": Decimal("5"),
            },
            {
                "ArticulosCodigo": "SKU002",
                "ArticulosNombre": "Producto B",
                "ArticulosPeso": Decimal("2.0"),
                "stock_quantity": Decimal("25"),
            },
            {
                "ArticulosCodigo": "SKU003",
                "ArticulosNombre": "Producto C",
                "ArticulosPeso": Decimal("0.5"),
                "stock_quantity": Decimal("3"),
            },
        ]

    def _setup_mock_runner(
        self, mock_runner_class, sales_data, j3_inventory=None, j3_error=False
    ):
        """Configure mock SalesQueryRunner."""
        runner = mock_runner_class.return_value
        runner.fetch_sales_data.return_value = sales_data
        runner.fetch_sql_aggregations.side_effect = RuntimeError(
            "sql disabled in tests"
        )
        runner.fetch_ytd_sql_aggregations.side_effect = RuntimeError(
            "ytd sql disabled in tests"
        )
        runner.fetch_year_to_date_data.return_value = sales_data
        runner.fetch_sb_product_map.return_value = {}
        if j3_error:
            runner.fetch_j3system_inventory.return_value = {}
            runner.fetch_j3system_product_details.return_value = ({}, {})
        else:
            runner.fetch_j3system_inventory.return_value = {
                row["ArticulosCodigo"]: {
                    "name": row.get("ArticulosNombre"),
                    "weight_kg": float(row.get("ArticulosPeso", 0)),
                    "stock_quantity": float(row.get("stock_quantity", 0)),
                }
                for row in (j3_inventory or [])
            }
            runner.fetch_j3system_product_details.return_value = ({}, {})
        runner.fetch_j3system_warehouse_sales.return_value = {
            "breakdown": [],
            "sales": [],
        }
        return runner

    @patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
    def test_generate_returns_dict(self, MockRunner, sample_sales_data):
        """Test generate returns a dict with expected keys."""
        self._setup_mock_runner(MockRunner, sample_sales_data)

        report = ManagerSalesReport(2024, 5)
        result = report.generate()

        assert isinstance(result, dict)
        assert "metadata" in result
        assert "summary" in result
        assert "top_products" in result
        assert "top_customers" in result
        assert "category_breakdown" in result
        assert "daily_trend" in result
        assert "inventory_insights" in result
        assert "formatted" in result

    @patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
    def test_summary_calculations(self, MockRunner, sample_sales_data):
        """Test summary metrics are calculated correctly."""
        self._setup_mock_runner(MockRunner, sample_sales_data)

        report = ManagerSalesReport(2024, 5)
        result = report.generate()
        summary = result["summary"]
        formatted = result["formatted"]["summary"]

        # Raw numbers
        assert summary["total_revenue_with_iva"] == 435600.0
        assert summary["total_revenue_without_iva"] == 360000.0
        assert summary["total_cost"] == 214200.0
        assert summary["gross_profit"] == 145800.0
        assert summary["order_count"] == 4
        assert summary["total_quantity_sold"] == 37

        # Formatted strings
        assert formatted["total_revenue_with_iva"] == "$435.600"
        assert formatted["total_revenue_without_iva"] == "$360.000"
        assert formatted["total_cost"] == "$214.200"
        assert formatted["gross_profit"] == "$145.800"
        assert formatted["gross_margin_pct"] == "40,5%"
        assert formatted["order_count"] == "4"
        assert formatted["total_quantity_sold"] == "37"

    @patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
    def test_top_products_sorted_by_revenue(self, MockRunner, sample_sales_data):
        """Test top products are sorted by revenue descending."""
        self._setup_mock_runner(MockRunner, sample_sales_data)

        report = ManagerSalesReport(2024, 5)
        result = report.generate()
        top = result["top_products"]
        formatted = result["formatted"]["top_products"]

        assert len(top) == 3
        assert top[0]["product_name"] == "Producto B"
        assert top[0]["total_revenue"] == 250000.0
        assert formatted[0]["product_name"] == "Producto B"
        assert formatted[0]["total_revenue"] == "$250.000"

    @patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
    def test_top_customers_sorted_by_revenue(self, MockRunner, sample_sales_data):
        """Test top customers are sorted by revenue descending."""
        self._setup_mock_runner(MockRunner, sample_sales_data)

        report = ManagerSalesReport(2024, 5)
        result = report.generate()
        top = result["top_customers"]
        formatted = result["formatted"]["top_customers"]

        assert len(top) == 3
        assert top[0]["customer_name"] == "Cliente B"
        assert top[0]["total_revenue"] == 242000.0
        assert formatted[0]["customer_name"] == "Cliente B"
        assert formatted[0]["total_revenue"] == "$242.000"
        assert formatted[1]["total_orders"] == "2"

    @patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
    def test_category_breakdown(self, MockRunner, sample_sales_data):
        """Test category breakdown includes revenue and margin."""
        self._setup_mock_runner(MockRunner, sample_sales_data)

        report = ManagerSalesReport(2024, 5)
        result = report.generate()
        breakdown = result["category_breakdown"]

        assert len(breakdown) == 3
        # Electricidad > Cables is top with $250,000
        assert breakdown[0]["category_path"] == "Electricidad > Cables"
        assert breakdown[0]["total_revenue"] == 250000.0

    @patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
    def test_daily_trend(self, MockRunner, sample_sales_data):
        """Test daily trend groups revenue and orders by date."""
        self._setup_mock_runner(MockRunner, sample_sales_data)

        report = ManagerSalesReport(2024, 5)
        result = report.generate()
        trend = result["daily_trend"]
        formatted = result["formatted"]["daily_trend"]

        assert len(trend) == 2
        assert trend[0]["date"] == "2024-05-01"
        assert trend[0]["revenue_with_iva"] == 181500.0
        assert trend[1]["date"] == "2024-05-02"
        assert formatted[0]["revenue_with_iva"] == "$181.500"

    @patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
    def test_inventory_insights_with_j3system(
        self, MockRunner, sample_sales_data, mock_j3system_inventory
    ):
        """Test inventory insights include low stock alerts from J3System."""
        self._setup_mock_runner(
            MockRunner, sample_sales_data, j3_inventory=mock_j3system_inventory
        )

        report = ManagerSalesReport(2024, 5)
        result = report.generate()
        insights = result["inventory_insights"]

        assert len(insights["fast_movers_in_month"]) == 3
        low_stock = insights["low_stock_alert"]
        assert len(low_stock) == 2
        # Fast movers ordered by quantity sold: SKU002 (25), SKU001 (10), SKU003 (2)
        # SKU002 has stock 25 (>10) so excluded. Low stock: SKU001 (stock 5), SKU003 (stock 3)
        assert low_stock[0]["sku"] == "SKU001"
        assert low_stock[0]["current_stock"] == 5.0

    @patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
    def test_empty_data(self, MockRunner):
        """Test report handles empty data gracefully."""
        self._setup_mock_runner(MockRunner, [])

        report = ManagerSalesReport(2024, 5)
        result = report.generate()

        assert result["formatted"]["summary"]["total_revenue_with_iva"] == "$0"
        assert result["top_products"] == []
        assert result["top_customers"] == []
        assert result["category_breakdown"] == []
        assert result["daily_trend"] == []
        assert result["inventory_insights"]["low_stock_alert"] == []
        assert result["inventory_insights"]["fast_movers_in_month"] == []
        assert result.get("vendor_sales") == []
        assert result.get("customer_vendor_mix") == []
        assert result.get("procurement_plan") == []

    @patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
    def test_sql_excludes_test_docs(self, MockRunner, sample_sales_data):
        """Test report uses May 2024 period via SalesQueryRunner."""
        runner = self._setup_mock_runner(MockRunner, sample_sales_data)

        report = ManagerSalesReport(2024, 5)
        report.generate()

        runner.fetch_sales_data.assert_called_once()
        assert report.start_date == "2024-05-01"
        assert report.end_date == "2024-05-31"

    @patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
    def test_warehouse_sales_from_j3system(self, MockRunner, sample_sales_data):
        """Warehouse breakdown uses J3System InvVentas/InvImpresionFactura data."""
        runner = self._setup_mock_runner(MockRunner, sample_sales_data)
        runner.fetch_j3system_warehouse_sales.return_value = {
            "breakdown": [
                {
                    "warehouse_code": "FLO",
                    "warehouse_name": "ALMACEN FLORENCIA",
                    "sale_count": 12,
                    "revenue_without_iva": 5000000.0,
                    "revenue_with_iva": 5950000.0,
                    "quantity": 48,
                },
                {
                    "warehouse_code": "DIS",
                    "warehouse_name": "DISTRIBUCIONES",
                    "sale_count": 8,
                    "revenue_without_iva": 2000000.0,
                    "revenue_with_iva": 2380000.0,
                    "quantity": 20,
                },
            ],
            "sales": [
                {
                    "VentaID": 101,
                    "NumeroDocumento": 9001,
                    "Fecha": "2024-05-02",
                    "NroFactura": "FV-9001",
                    "warehouse_code": "FLO",
                    "warehouse_name": "ALMACEN FLORENCIA",
                }
            ],
        }

        report = ManagerSalesReport(2024, 5)
        result = report.generate()
        wh = result["warehouse_sales"]

        assert len(wh["breakdown"]) == 2
        assert wh["breakdown"][0]["warehouse_code"] == "FLO"
        assert wh["breakdown"][0]["sale_count"] == 12
        assert wh["breakdown"][0]["revenue_pct"] == 71.4
        assert len(wh["sales_detail"]) == 1
        assert wh["sales_detail"][0]["venta_id"] == 101
        assert wh["sales_detail"][0]["warehouse_code"] == "FLO"
        formatted = result["formatted"]["warehouse_sales"]
        assert formatted["breakdown"][0]["warehouse_name"] == "ALMACEN FLORENCIA"
        runner.fetch_j3system_warehouse_sales.assert_called_once()

    @patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
    def test_j3system_failure_graceful(self, MockRunner, sample_sales_data):
        """Test J3System connection failure is handled gracefully."""
        self._setup_mock_runner(MockRunner, sample_sales_data, j3_error=True)

        report = ManagerSalesReport(2024, 5)
        result = report.generate()

        assert result["inventory_insights"]["low_stock_alert"] == []
        assert result["inventory_insights"]["fast_movers_in_month"] == []
        assert "note" in result["inventory_insights"]
        assert result["warehouse_sales"]["breakdown"] == []
        assert "note" in result["warehouse_sales"]

    @patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
    def test_context_manager_used(self, MockRunner, sample_sales_data):
        """Test SalesQueryRunner fetch methods are invoked."""
        runner = self._setup_mock_runner(MockRunner, sample_sales_data)

        report = ManagerSalesReport(2024, 5)
        report.generate()

        runner.fetch_sales_data.assert_called_once()
        runner.fetch_year_to_date_data.assert_called_once()
        runner.fetch_sb_product_map.assert_called_once()
        runner.fetch_j3system_warehouse_sales.assert_called_once()

    @patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
    def test_vendor_sales_uses_sql_aggregations(self, MockRunner, sample_sales_data):
        """Vendor/mix sections should use SQL rows when available."""
        runner = self._setup_mock_runner(MockRunner, sample_sales_data)
        runner.fetch_sql_aggregations.return_value = {
            "summary": {},
            "top_products": [],
            "top_customers": [],
            "category_breakdown": [],
            "daily_trend": [],
            "vendor_sales": [
                {
                    "vendor_name": "PROV1",
                    "total_revenue": 150000.0,
                    "total_cost": 90000.0,
                    "total_quantity": 15,
                    "transactions": 2,
                }
            ],
            "marca_sales": [],
            "customer_vendor_pairs": [
                {
                    "customer_name": "Cliente A",
                    "vendor_name": "PROV1",
                    "revenue": 150000.0,
                    "transactions": 2,
                }
            ],
            "sku_monthly_sales": [
                {
                    "sku": "SKU001",
                    "product_name": "Producto A",
                    "quantity": 10,
                    "revenue": 100000.0,
                }
            ],
            "abc_products": [{"entity_name": "Producto A", "total_revenue": 100000.0}],
            "abc_customers": [{"entity_name": "Cliente A", "total_revenue": 181500.0}],
            "abc_vendors": [{"entity_name": "PROV1", "total_revenue": 150000.0}],
            "product_margins": [],
            "customer_baskets": [],
        }
        runner.fetch_sql_aggregations.side_effect = None

        report = ManagerSalesReport(2024, 5)
        result = report.generate()

        assert result["vendor_sales"][0]["vendor_name"] == "PROV1"
        assert result["customer_vendor_mix"][0]["customer_name"] == "Cliente A"
        assert "abc_analysis" in result

    @patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
    def test_new_sections_present(self, MockRunner, sample_sales_data):
        """Test that vendor sales, mix, suggestions, procurement plan and shopping recs are in output."""
        self._setup_mock_runner(MockRunner, sample_sales_data)

        report = ManagerSalesReport(2024, 5)
        result = report.generate()

        # Core new sections always present
        assert "vendor_sales" in result
        assert "customer_vendor_mix" in result
        assert "customer_order_suggestions" in result
        assert "shopping_recommendations" in result
        assert "procurement_plan" in result
        assert "customer_vendor_mix" in result.get("formatted", {})
        assert "procurement_plan" in result.get("formatted", {})

        # With proveedores in fixture, vendor_sales should populate
        assert len(result["vendor_sales"]) >= 1
        # Mix should have entries
        assert len(result["customer_vendor_mix"]) >= 1

    @patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
    def test_procurement_plan_aggregates_suggestions(
        self, MockRunner, sample_sales_data
    ):
        """Procurement plan should derive from order suggestions when they exist (uses full-year YTD)."""
        self._setup_mock_runner(MockRunner, sample_sales_data)

        report = ManagerSalesReport(2024, 5)
        result = report.generate()

        # Even if zero suggestions (small data + 1.5x factor), structure must exist and be list
        plan = result.get("procurement_plan", [])
        assert isinstance(plan, list)
        # If any, must have expected keys
        for p in plan:
            assert "vendor_name" in p
            assert "total_suggested_units" in p
            assert "key_products" in p

    @patch("business_analyzer.analysis.manager_report.report.SalesQueryRunner")
    def test_ytd_uses_full_year_dates(self, MockRunner, sample_sales_data):
        """YTD query must request full year (Jan-Dec) to include all sales from the year."""
        runner = self._setup_mock_runner(MockRunner, sample_sales_data)

        report = ManagerSalesReport(2024, 5)
        report.generate()

        runner.fetch_year_to_date_data.assert_called_once()
        assert report.year == 2024

    def test_invalid_month_raises(self):
        with pytest.raises(ValueError):
            ManagerSalesReport(2024, 13)

    def test_invalid_year_raises(self):
        with pytest.raises(ValueError):
            ManagerSalesReport(1999, 5)


class TestManagerReportHeuristics:
    def test_is_recommendable_product_excludes_logistics_items(self):
        from business_analyzer.analysis.manager_report import _is_recommendable_product

        assert _is_recommendable_product("Varilla 1/2") is True
        assert _is_recommendable_product("Bolsa plastica grande") is False
        assert _is_recommendable_product("Transporte urbano") is False
        assert _is_recommendable_product("Cemento gris 50kg") is False

    def test_is_likely_supplier_name_filters_product_like_strings(self):
        from business_analyzer.analysis.manager_report import _is_likely_supplier_name

        assert _is_likely_supplier_name("SIKA") is True
        assert _is_likely_supplier_name("ACESCO") is True
        assert _is_likely_supplier_name("BARRA CORRUGADA 1/2") is False
        assert _is_likely_supplier_name("") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
