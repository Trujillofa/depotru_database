"""
Tests for financial analysis module.
"""

import pytest

from src.business_analyzer.analysis.financial import (
    FinancialAnalyzer,
    extract_value,
    safe_divide,
)


class TestFinancialAnalyzer:
    """Test FinancialAnalyzer class."""

    @pytest.fixture
    def sample_data(self):
        """Provide sample transaction data."""
        return [
            {
                "TotalMasIva": 120000.0,
                "TotalSinIva": 100000.0,
                "ValorCosto": 70000.0,
            },
            {
                "TotalMasIva": 60000.0,
                "TotalSinIva": 50000.0,
                "ValorCosto": 35000.0,
            },
            {
                "TotalMasIva": 240000.0,
                "TotalSinIva": 200000.0,
                "ValorCosto": 100000.0,
            },
        ]

    def test_analyze_returns_dict(self, sample_data):
        """Test analyze returns dictionary."""
        analyzer = FinancialAnalyzer(sample_data)
        result = analyzer.analyze()
        assert isinstance(result, dict)
        assert "revenue" in result
        assert "costs" in result
        assert "profit" in result

    def test_revenue_with_iva(self, sample_data):
        """Test revenue with IVA calculation."""
        analyzer = FinancialAnalyzer(sample_data)
        result = analyzer.analyze()
        # 120000 + 60000 + 240000 = 420000
        assert result["revenue"]["total_with_iva"] == 420000.0

    def test_revenue_without_iva(self, sample_data):
        """Test revenue without IVA calculation."""
        analyzer = FinancialAnalyzer(sample_data)
        result = analyzer.analyze()
        # 100000 + 50000 + 200000 = 350000
        assert result["revenue"]["total_without_iva"] == 350000.0

    def test_average_order_value(self, sample_data):
        """Test average order value calculation."""
        analyzer = FinancialAnalyzer(sample_data)
        result = analyzer.analyze()
        # (120000 + 60000 + 240000) / 3 = 140000
        assert result["revenue"]["average_order_value"] == 140000.0

    def test_median_order_value(self, sample_data):
        """Test median order value calculation."""
        analyzer = FinancialAnalyzer(sample_data)
        result = analyzer.analyze()
        # Median of [120000, 60000, 240000] = 120000
        assert result["revenue"]["median_order_value"] == 120000.0

    def test_total_cost(self, sample_data):
        """Test total cost calculation."""
        analyzer = FinancialAnalyzer(sample_data)
        result = analyzer.analyze()
        # 70000 + 35000 + 100000 = 205000
        assert result["costs"]["total_cost"] == 205000.0

    def test_average_cost_per_unit(self, sample_data):
        """Test average cost per unit calculation."""
        analyzer = FinancialAnalyzer(sample_data)
        result = analyzer.analyze()
        # (70000 + 35000 + 100000) / 3 = 68333.33
        assert result["costs"]["average_cost_per_unit"] == 68333.33

    def test_gross_profit(self, sample_data):
        """Test gross profit calculation."""
        analyzer = FinancialAnalyzer(sample_data)
        result = analyzer.analyze()
        # 350000 - 205000 = 145000
        assert result["profit"]["gross_profit"] == 145000.0

    def test_gross_profit_margin(self, sample_data):
        """Test gross profit margin calculation."""
        analyzer = FinancialAnalyzer(sample_data)
        result = analyzer.analyze()
        # (145000 / 350000) * 100 = 41.43%
        assert result["profit"]["gross_profit_margin"] == 41.43

    def test_calculate_iva_collected(self, sample_data):
        """Test IVA collected calculation."""
        analyzer = FinancialAnalyzer(sample_data)
        iva = analyzer.calculate_iva_collected()
        # 420000 - 350000 = 70000
        assert iva == 70000.0

    def test_get_revenue_breakdown(self, sample_data):
        """Test revenue breakdown."""
        analyzer = FinancialAnalyzer(sample_data)
        breakdown = analyzer.get_revenue_breakdown()

        assert "sales_revenue" in breakdown
        assert "iva_tax" in breakdown
        assert "total_with_iva" in breakdown
        assert breakdown["sales_revenue"] == 350000.0
        assert breakdown["iva_tax"] == 70000.0
        assert breakdown["total_with_iva"] == 420000.0

    def test_empty_data(self):
        """Test handling of empty data."""
        analyzer = FinancialAnalyzer([])
        result = analyzer.analyze()

        assert result["revenue"]["total_with_iva"] == 0.0
        assert result["revenue"]["total_without_iva"] == 0.0
        assert result["revenue"]["average_order_value"] == 0.0
        assert result["costs"]["total_cost"] == 0.0
        assert result["profit"] == {}

    def test_missing_cost_data(self):
        """Test handling of missing cost data."""
        data = [
            {"TotalMasIva": 120000.0, "TotalSinIva": 100000.0},
        ]
        analyzer = FinancialAnalyzer(data)
        result = analyzer.analyze()

        assert result["revenue"]["total_with_iva"] == 120000.0
        assert result["costs"]["total_cost"] == 0.0
        assert result["profit"] == {}

    def test_decimal_values(self):
        """Test handling of Decimal values."""
        from decimal import Decimal

        data = [
            {
                "TotalMasIva": Decimal("120000.50"),
                "TotalSinIva": Decimal("100000.42"),
                "ValorCosto": Decimal("70000.25"),
            },
        ]
        analyzer = FinancialAnalyzer(data)
        result = analyzer.analyze()

        assert result["revenue"]["total_with_iva"] == 120000.5
        assert result["revenue"]["total_without_iva"] == 100000.42
        assert result["costs"]["total_cost"] == 70000.25


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
