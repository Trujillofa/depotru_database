"""
Tests for business_analyzer/analysis/customer_optimized.py
"""

import pytest
from business_analyzer.analysis.customer_optimized import (
    safe_divide,
    extract_value,
    OptimizedCustomerAnalyzer,
)


class TestSafeDivide:
    """Test safe_divide function"""

    def test_normal_division(self):
        """Test normal division"""
        result = safe_divide(100, 50)
        assert result == 2.0

    def test_division_by_zero(self):
        """Test division by zero returns default"""
        result = safe_divide(100, 0)
        assert result == 0.0

    def test_division_by_zero_custom_default(self):
        """Test division by zero with custom default"""
        result = safe_divide(100, 0, default=-1.0)
        assert result == -1.0

    def test_zero_numerator(self):
        """Test zero numerator"""
        result = safe_divide(0, 50)
        assert result == 0.0


class TestExtractValue:
    """Test extract_value function"""

    def test_extract_first_key(self):
        """Test extracting first available key"""
        row = {"TercerosNombres": "Customer A", "NombreCliente": "Customer B"}
        result = extract_value(row, ["TercerosNombres", "NombreCliente"])
        assert result == "Customer A"

    def test_extract_second_key(self):
        """Test extracting second key when first is missing"""
        row = {"NombreCliente": "Customer B"}
        result = extract_value(row, ["TercerosNombres", "NombreCliente"])
        assert result == "Customer B"

    def test_extract_default(self):
        """Test returning default when no keys found"""
        row = {}
        result = extract_value(row, ["TercerosNombres", "NombreCliente"], default="Unknown")
        assert result == "Unknown"

    def test_extract_decimal(self):
        """Test extracting Decimal value"""
        from decimal import Decimal
        row = {"TotalMasIva": Decimal("100.50")}
        result = extract_value(row, ["TotalMasIva"])
        assert result == 100.50
        assert isinstance(result, float)

    def test_extract_string_number(self):
        """Test extracting string number"""
        row = {"TotalMasIva": "100.50"}
        result = extract_value(row, ["TotalMasIva"])
        assert result == 100.50

    def test_extract_date_string(self):
        """Test that date strings are returned as-is"""
        row = {"Fecha": "2025-01-15"}
        result = extract_value(row, ["Fecha"])
        assert result == "2025-01-15"


class TestOptimizedCustomerAnalyzer:
    """Test OptimizedCustomerAnalyzer class"""

    def test_analyze_returns_dict(self):
        """Test that analyze returns a dictionary"""
        data = [
            {"TercerosNombres": "Customer A", "TotalMasIva": 100.0, "Cantidad": 1},
            {"TercerosNombres": "Customer B", "TotalMasIva": 200.0, "Cantidad": 2},
        ]
        analyzer = OptimizedCustomerAnalyzer(data)
        result = analyzer.analyze()
        assert isinstance(result, dict)

    def test_total_customers(self):
        """Test total customers count"""
        data = [
            {"TercerosNombres": "Customer A", "TotalMasIva": 100.0},
            {"TercerosNombres": "Customer B", "TotalMasIva": 200.0},
            {"TercerosNombres": "Customer A", "TotalMasIva": 150.0},  # Same customer
        ]
        analyzer = OptimizedCustomerAnalyzer(data)
        result = analyzer.analyze()
        assert result["total_customers"] == 2

    def test_top_customers_sorted(self):
        """Test top customers are sorted by revenue"""
        data = [
            {"TercerosNombres": "Customer A", "TotalMasIva": 100.0},
            {"TercerosNombres": "Customer B", "TotalMasIva": 500.0},
            {"TercerosNombres": "Customer C", "TotalMasIva": 300.0},
        ]
        analyzer = OptimizedCustomerAnalyzer(data)
        result = analyzer.analyze()
        top_customers = result["top_customers"]
        assert len(top_customers) == 3
        assert top_customers[0]["customer_name"] == "Customer B"  # Highest revenue

    def test_customer_segmentation(self):
        """Test customer segmentation"""
        data = [
            {"TercerosNombres": "VIP", "TotalMasIva": 10000.0, "Cantidad": 50},
            {"TercerosNombres": "High", "TotalMasIva": 5000.0, "Cantidad": 30},
            {"TercerosNombres": "Regular", "TotalMasIva": 1000.0, "Cantidad": 10},
        ]
        analyzer = OptimizedCustomerAnalyzer(data)
        result = analyzer.analyze()
        segments = result["segmentation"]
        # All should be "Occasional" with the mock thresholds
        assert "Occasional" in segments

    def test_customer_concentration(self):
        """Test customer concentration calculation"""
        data = [
            {"TercerosNombres": "Customer A", "TotalMasIva": 800.0},
            {"TercerosNombres": "Customer B", "TotalMasIva": 200.0},
        ]
        analyzer = OptimizedCustomerAnalyzer(data)
        result = analyzer.analyze()
        assert "customer_concentration" in result
        assert "top_10_percentage" in result["customer_concentration"]

    def test_empty_data(self):
        """Test handling of empty data"""
        analyzer = OptimizedCustomerAnalyzer([])
        result = analyzer.analyze()
        assert result["total_customers"] == 0
        assert result["top_customers"] == []

    def test_get_segment_thresholds(self):
        """Test getting segment thresholds"""
        analyzer = OptimizedCustomerAnalyzer([])
        thresholds = analyzer.get_segment_thresholds()
        assert isinstance(thresholds, dict)
        assert "vip_revenue" in thresholds
        assert "high_value" in thresholds

    def test_caching(self):
        """Test that customer aggregation is cached"""
        data = [
            {"TercerosNombres": "Customer A", "TotalMasIva": 100.0},
        ]
        analyzer = OptimizedCustomerAnalyzer(data)
        
        # First call should compute
        result1 = analyzer.analyze()
        
        # Second call should use cache
        result2 = analyzer.analyze()
        
        assert result1 == result2

    def test_clear_cache(self):
        """Test clearing cache"""
        data = [
            {"TercerosNombres": "Customer A", "TotalMasIva": 100.0},
        ]
        analyzer = OptimizedCustomerAnalyzer(data)
        analyzer.analyze()
        
        # Clear cache
        analyzer.clear_cache()
        
        assert analyzer._cache == {}
        assert analyzer._customers_list is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
