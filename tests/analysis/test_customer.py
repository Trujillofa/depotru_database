"""
Tests for customer analysis module.
"""

import pytest
from src.business_analyzer.analysis.customer import (
    CustomerAnalyzer,
    safe_divide,
    extract_value,
)


class TestSafeDivide:
    """Test safe_divide helper function."""

    def test_normal_division(self):
        """Test normal division case."""
        result = safe_divide(100, 50)
        assert result == 2.0

    def test_division_by_zero(self):
        """Test division by zero returns default."""
        result = safe_divide(100, 0)
        assert result == 0.0

    def test_division_by_zero_custom_default(self):
        """Test division by zero with custom default."""
        result = safe_divide(100, 0, default=-1)
        assert result == -1.0

    def test_zero_numerator(self):
        """Test zero numerator."""
        result = safe_divide(0, 100)
        assert result == 0.0


class TestExtractValue:
    """Test extract_value helper function."""

    def test_extract_first_key(self):
        """Test extracting first available key."""
        row = {"name": "John", "age": 30}
        result = extract_value(row, ["name", "nombre"])
        assert result == "John"

    def test_extract_second_key(self):
        """Test extracting second key when first missing."""
        row = {"nombre": "Juan", "age": 30}
        result = extract_value(row, ["name", "nombre"])
        assert result == "Juan"

    def test_extract_default(self):
        """Test default value when keys missing."""
        row = {"age": 30}
        result = extract_value(row, ["name", "nombre"], default="Unknown")
        assert result == "Unknown"

    def test_extract_decimal(self):
        """Test extracting Decimal value."""
        from decimal import Decimal

        row = {"price": Decimal("99.99")}
        result = extract_value(row, ["price"])
        assert result == 99.99
        assert isinstance(result, float)

    def test_extract_string_number(self):
        """Test extracting string number."""
        row = {"price": "1,234.56"}
        result = extract_value(row, ["price"])
        assert result == 1234.56


class TestCustomerAnalyzer:
    """Test CustomerAnalyzer class."""

    @pytest.fixture
    def sample_data(self):
        """Provide sample transaction data."""
        return [
            {
                "TercerosNombres": "Customer A",
                "TotalMasIva": 100000.0,
                "ArticulosNombre": "Product 1",
                "Fecha": "2025-01-01",
            },
            {
                "TercerosNombres": "Customer A",
                "TotalMasIva": 50000.0,
                "ArticulosNombre": "Product 2",
                "Fecha": "2025-01-02",
            },
            {
                "TercerosNombres": "Customer B",
                "TotalMasIva": 600000.0,
                "ArticulosNombre": "Product 1",
                "Fecha": "2025-01-03",
            },
            {
                "TercerosNombres": "Customer C",
                "TotalMasIva": 250000.0,
                "ArticulosNombre": "Product 3",
                "Fecha": "2025-01-04",
            },
        ]

    def test_analyze_returns_dict(self, sample_data):
        """Test analyze returns dictionary."""
        analyzer = CustomerAnalyzer(sample_data)
        result = analyzer.analyze()
        assert isinstance(result, dict)

    def test_total_customers(self, sample_data):
        """Test total customers count."""
        analyzer = CustomerAnalyzer(sample_data)
        result = analyzer.analyze()
        assert result["total_customers"] == 3

    def test_top_customers_sorted(self, sample_data):
        """Test top customers are sorted by revenue."""
        analyzer = CustomerAnalyzer(sample_data)
        result = analyzer.analyze()
        top_customers = result["top_customers"]
        assert len(top_customers) == 3
        assert top_customers[0]["customer_name"] == "Customer B"  # Highest revenue
        assert top_customers[0]["total_revenue"] == 600000.0

    def test_customer_segmentation(self, sample_data):
        """Test customer segmentation logic."""
        analyzer = CustomerAnalyzer(sample_data)
        result = analyzer.analyze()

        # Customer B: 600k revenue, 1 order -> High Value (not VIP due to low orders)
        # Customer C: 250k revenue, 1 order -> High Value
        # Customer A: 150k total, 2 orders -> High Value
        segments = result["segmentation"]
        assert "High Value" in segments

    def test_vip_segment(self):
        """Test VIP customer segmentation."""
        data = [
            {
                "TercerosNombres": "VIP Customer",
                "TotalMasIva": 600000.0,
                "ArticulosNombre": "Product 1",
            },
            {
                "TercerosNombres": "VIP Customer",
                "TotalMasIva": 100000.0,
                "ArticulosNombre": "Product 2",
            },
            {
                "TercerosNombres": "VIP Customer",
                "TotalMasIva": 50000.0,
                "ArticulosNombre": "Product 3",
            },
            {
                "TercerosNombres": "VIP Customer",
                "TotalMasIva": 75000.0,
                "ArticulosNombre": "Product 4",
            },
            {
                "TercerosNombres": "VIP Customer",
                "TotalMasIva": 80000.0,
                "ArticulosNombre": "Product 5",
            },
            {
                "TercerosNombres": "VIP Customer",
                "TotalMasIva": 90000.0,
                "ArticulosNombre": "Product 6",
            },
        ]
        analyzer = CustomerAnalyzer(data)
        result = analyzer.analyze()

        vip_customer = next(
            (
                c
                for c in result["top_customers"]
                if c["customer_name"] == "VIP Customer"
            ),
            None,
        )
        assert vip_customer is not None
        assert vip_customer["customer_segment"] == "VIP"

    def test_average_order_value(self, sample_data):
        """Test average order value calculation."""
        analyzer = CustomerAnalyzer(sample_data)
        result = analyzer.analyze()

        customer_a = next(
            (c for c in result["top_customers"] if c["customer_name"] == "Customer A"),
            None,
        )
        assert customer_a is not None
        assert customer_a["average_order_value"] == 75000.0  # (100000 + 50000) / 2

    def test_product_diversity(self, sample_data):
        """Test product diversity calculation."""
        analyzer = CustomerAnalyzer(sample_data)
        result = analyzer.analyze()

        customer_a = next(
            (c for c in result["top_customers"] if c["customer_name"] == "Customer A"),
            None,
        )
        assert customer_a is not None
        assert customer_a["product_diversity"] == 2  # Product 1 and Product 2

    def test_customer_concentration(self, sample_data):
        """Test customer concentration calculation."""
        analyzer = CustomerAnalyzer(sample_data)
        result = analyzer.analyze()

        concentration = result["customer_concentration"]
        assert "top_10_percentage" in concentration
        assert isinstance(concentration["top_10_percentage"], float)

    def test_empty_data(self):
        """Test handling of empty data."""
        analyzer = CustomerAnalyzer([])
        result = analyzer.analyze()
        assert result["total_customers"] == 0
        assert result["top_customers"] == []

    def test_get_segment_thresholds(self, sample_data):
        """Test getting segmentation thresholds."""
        analyzer = CustomerAnalyzer(sample_data)
        thresholds = analyzer.get_segment_thresholds()

        assert "vip_revenue" in thresholds
        assert "vip_orders" in thresholds
        assert "high_value" in thresholds
        assert "frequent_orders" in thresholds
        assert "regular_revenue" in thresholds

    def test_unknown_customer_default(self):
        """Test unknown customer name default."""
        data = [
            {"TotalMasIva": 10000.0, "ArticulosNombre": "Product 1"},
        ]
        analyzer = CustomerAnalyzer(data)
        result = analyzer.analyze()

        assert result["total_customers"] == 1
        assert result["top_customers"][0]["customer_name"] == "Unknown"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
