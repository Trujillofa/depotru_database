"""
Tests for product analysis module.
"""

import pytest
from src.business_analyzer.analysis.product import (
    ProductAnalyzer,
    safe_divide,
    extract_value,
)


class TestProductAnalyzer:
    """Test ProductAnalyzer class."""

    @pytest.fixture
    def sample_data(self):
        """Provide sample transaction data."""
        return [
            {
                "ArticulosNombre": "Product A",
                "ArticulosCodigo": "SKU001",
                "TotalSinIva": 100000.0,
                "ValorCosto": 70000.0,
                "Cantidad": 10,
            },
            {
                "ArticulosNombre": "Product A",
                "ArticulosCodigo": "SKU001",
                "TotalSinIva": 50000.0,
                "ValorCosto": 35000.0,
                "Cantidad": 5,
            },
            {
                "ArticulosNombre": "Product B",
                "ArticulosCodigo": "SKU002",
                "TotalSinIva": 200000.0,
                "ValorCosto": 100000.0,
                "Cantidad": 20,
            },
            {
                "ArticulosNombre": "Product C",
                "ArticulosCodigo": "SKU003",
                "TotalSinIva": 50000.0,
                "ValorCosto": 46000.0,  # 8% margin (4000/50000), underperforming
                "Cantidad": 5,
            },
        ]

    def test_analyze_returns_dict(self, sample_data):
        """Test analyze returns dictionary."""
        analyzer = ProductAnalyzer(sample_data)
        result = analyzer.analyze()
        assert isinstance(result, dict)

    def test_total_products(self, sample_data):
        """Test total products count."""
        analyzer = ProductAnalyzer(sample_data)
        result = analyzer.analyze()
        assert result["total_products"] == 3

    def test_top_products_sorted(self, sample_data):
        """Test top products are sorted by revenue."""
        analyzer = ProductAnalyzer(sample_data)
        result = analyzer.analyze()
        top_products = result["top_products"]

        assert len(top_products) == 3
        assert top_products[0]["product_name"] == "Product B"  # Highest revenue
        assert top_products[0]["total_revenue"] == 200000.0

    def test_product_sku(self, sample_data):
        """Test SKU extraction."""
        analyzer = ProductAnalyzer(sample_data)
        result = analyzer.analyze()

        product_a = next(
            (p for p in result["top_products"] if p["product_name"] == "Product A"),
            None,
        )
        assert product_a is not None
        assert product_a["sku"] == "SKU001"

    def test_profit_calculation(self, sample_data):
        """Test profit calculation."""
        analyzer = ProductAnalyzer(sample_data)
        result = analyzer.analyze()

        product_a = next(
            (p for p in result["top_products"] if p["product_name"] == "Product A"),
            None,
        )
        assert product_a is not None
        # Revenue: 150000, Cost: 105000, Profit: 45000
        assert product_a["profit"] == 45000.0

    def test_profit_margin_calculation(self, sample_data):
        """Test profit margin calculation."""
        analyzer = ProductAnalyzer(sample_data)
        result = analyzer.analyze()

        product_a = next(
            (p for p in result["top_products"] if p["product_name"] == "Product A"),
            None,
        )
        assert product_a is not None
        # Margin: 45000 / 150000 * 100 = 30%
        assert product_a["profit_margin"] == 30.0

    def test_star_products(self, sample_data):
        """Test star products identification (>30% margin)."""
        analyzer = ProductAnalyzer(sample_data)
        result = analyzer.analyze()

        star_products = result["star_products"]
        # Product B has 50% margin, should be a star product
        product_b = next(
            (p for p in star_products if p["product_name"] == "Product B"), None
        )
        assert product_b is not None

    def test_underperforming_products(self, sample_data):
        """Test underperforming products identification (<10% margin)."""
        analyzer = ProductAnalyzer(sample_data)
        result = analyzer.analyze()

        underperforming = result["underperforming_products"]
        # Product C has 8% margin (4000/50000), should be underperforming (<10%)
        product_c = next(
            (p for p in underperforming if p["product_name"] == "Product C"), None
        )
        assert product_c is not None

    def test_total_quantity(self, sample_data):
        """Test total quantity calculation."""
        analyzer = ProductAnalyzer(sample_data)
        result = analyzer.analyze()

        product_a = next(
            (p for p in result["top_products"] if p["product_name"] == "Product A"),
            None,
        )
        assert product_a is not None
        assert product_a["total_quantity"] == 15  # 10 + 5

    def test_transactions_count(self, sample_data):
        """Test transactions count."""
        analyzer = ProductAnalyzer(sample_data)
        result = analyzer.analyze()

        product_a = next(
            (p for p in result["top_products"] if p["product_name"] == "Product A"),
            None,
        )
        assert product_a is not None
        assert product_a["transactions"] == 2

    def test_empty_data(self):
        """Test handling of empty data."""
        analyzer = ProductAnalyzer([])
        result = analyzer.analyze()
        assert result["total_products"] == 0
        assert result["top_products"] == []
        assert result["star_products"] == []
        assert result["underperforming_products"] == []

    def test_get_profitability_thresholds(self, sample_data):
        """Test getting profitability thresholds."""
        analyzer = ProductAnalyzer(sample_data)
        thresholds = analyzer.get_profitability_thresholds()

        assert "low_margin" in thresholds
        assert "star_product" in thresholds
        assert "critical" in thresholds

    def test_analyze_product_by_name(self, sample_data):
        """Test analyzing specific product by name."""
        analyzer = ProductAnalyzer(sample_data)
        product = analyzer.analyze_product_by_name("Product A")

        assert product is not None
        assert product["product_name"] == "Product A"
        assert product["sku"] == "SKU001"

    def test_analyze_product_by_name_not_found(self, sample_data):
        """Test analyzing non-existent product."""
        analyzer = ProductAnalyzer(sample_data)
        product = analyzer.analyze_product_by_name("NonExistent")

        assert product is None

    def test_unknown_product_default(self):
        """Test unknown product name default."""
        data = [
            {"TotalSinIva": 10000.0, "ValorCosto": 7000.0},
        ]
        analyzer = ProductAnalyzer(data)
        result = analyzer.analyze()

        assert result["total_products"] == 1
        assert result["top_products"][0]["product_name"] == "Unknown"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
