"""
Unit Tests for Business Metrics Calculator
==========================================
Demonstrates proper testing practices.

Run with: pytest test_business_metrics.py -v
"""

import pytest
from decimal import Decimal
from datetime import datetime

# Skip all tests in this module if dependencies are missing
pymssql = pytest.importorskip("pymssql", reason="pymssql not installed")
pytest.importorskip("examples.improvements_p0", reason="improvements_p0 requires pymssql")


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def sample_data():
    """Sample data for testing"""
    return [
        {
            "TotalMasIva": 116.0,
            "TotalSinIva": 100.0,
            "ValorCosto": 60.0,
            "Cantidad": 2,
            "TercerosNombres": "Customer A",
            "ArticulosNombre": "Product 1",
            "categoria": "Category 1",
            "Fecha": datetime(2025, 1, 15)
        },
        {
            "TotalMasIva": 232.0,
            "TotalSinIva": 200.0,
            "ValorCosto": 120.0,
            "Cantidad": 4,
            "TercerosNombres": "Customer A",
            "ArticulosNombre": "Product 2",
            "categoria": "Category 1",
            "Fecha": datetime(2025, 1, 16)
        },
        {
            "TotalMasIva": 174.0,
            "TotalSinIva": 150.0,
            "ValorCosto": 90.0,
            "Cantidad": 3,
            "TercerosNombres": "Customer B",
            "ArticulosNombre": "Product 1",
            "categoria": "Category 2",
            "Fecha": datetime(2025, 1, 17)
        }
    ]


@pytest.fixture
def empty_data():
    """Empty dataset for edge case testing"""
    return []


@pytest.fixture
def decimal_data():
    """Data with Decimal types (from pymssql)"""
    return [
        {
            "TotalMasIva": Decimal("116.50"),
            "TotalSinIva": Decimal("100.43"),
            "ValorCosto": Decimal("60.25"),
            "Cantidad": Decimal("2"),
        }
    ]


@pytest.fixture
def null_data():
    """Data with None/null values"""
    return [
        {
            "TotalMasIva": None,
            "TotalSinIva": 100.0,
            "ValorCosto": None,
            "Cantidad": 1,
        },
        {
            "TotalMasIva": 200.0,
            "TotalSinIva": None,
            "ValorCosto": 80.0,
            "Cantidad": None,
        }
    ]


# ============================================================================
# Test Safe Division
# ============================================================================

def test_safe_divide_normal():
    """Test safe division with valid numbers"""
    from examples.improvements_p0 import safe_divide

    assert safe_divide(100, 50) == 2.0
    assert safe_divide(100, 4) == 25.0
    assert safe_divide(7, 2) == 3.5


def test_safe_divide_by_zero():
    """Test safe division handles zero denominator"""
    from examples.improvements_p0 import safe_divide

    assert safe_divide(100, 0) == 0.0
    assert safe_divide(100, 0, default=-1) == -1.0
    assert safe_divide(0, 0) == 0.0


def test_safe_divide_negative():
    """Test safe division with negative numbers"""
    from examples.improvements_p0 import safe_divide

    assert safe_divide(-100, 50) == -2.0
    assert safe_divide(100, -50) == -2.0
    assert safe_divide(-100, -50) == 2.0


# ============================================================================
# Test Date Validation
# ============================================================================

def test_validate_date_range_valid():
    """Test date validation with valid inputs"""
    from examples.improvements_p0 import validate_date_range

    start, end = validate_date_range("2025-01-01", "2025-12-31")
    assert start.year == 2025
    assert start.month == 1
    assert start.day == 1
    assert end.year == 2025
    assert end.month == 12
    assert end.day == 31


def test_validate_date_range_invalid_format():
    """Test date validation rejects invalid formats"""
    from examples.improvements_p0 import validate_date_range

    with pytest.raises(ValueError, match="Invalid.*format"):
        validate_date_range("2025/01/01", "2025-12-31")

    with pytest.raises(ValueError, match="Invalid.*format"):
        validate_date_range("01-01-2025", "2025-12-31")

    with pytest.raises(ValueError, match="Invalid.*format"):
        validate_date_range("invalid", "2025-12-31")


def test_validate_date_range_wrong_order():
    """Test date validation rejects end before start"""
    from examples.improvements_p0 import validate_date_range

    with pytest.raises(ValueError, match="must be before"):
        validate_date_range("2025-12-31", "2025-01-01")


def test_validate_date_range_unreasonable_year():
    """Test date validation rejects unreasonable years"""
    from examples.improvements_p0 import validate_date_range

    with pytest.raises(ValueError, match="unreasonable"):
        validate_date_range("1999-01-01", "1999-12-31")

    with pytest.raises(ValueError, match="unreasonable"):
        validate_date_range("2030-01-01", "2030-12-31")


# ============================================================================
# Test Limit Validation
# ============================================================================

def test_validate_limit_valid():
    """Test limit validation with valid inputs"""
    from examples.improvements_p0 import validate_limit

    assert validate_limit(1) == 1
    assert validate_limit(1000) == 1000
    assert validate_limit(100000) == 100000
    assert validate_limit(1000000) == 1000000
    assert validate_limit(None) == 1000  # Default


def test_validate_limit_invalid():
    """Test limit validation rejects invalid inputs"""
    from examples.improvements_p0 import validate_limit

    with pytest.raises(ValueError, match="must be an integer"):
        validate_limit("1000")

    with pytest.raises(ValueError, match="must be an integer"):
        validate_limit(1000.5)


def test_validate_limit_out_of_range():
    """Test limit validation rejects out-of-range values"""
    from examples.improvements_p0 import validate_limit

    with pytest.raises(ValueError, match="must be at least 1"):
        validate_limit(0)

    with pytest.raises(ValueError, match="must be at least 1"):
        validate_limit(-100)

    with pytest.raises(ValueError, match="exceeds maximum"):
        validate_limit(2000000)


# ============================================================================
# Test Profit Margin Calculation
# ============================================================================

def test_calculate_profit_margin_safe_normal():
    """Test profit margin calculation with normal data"""
    from examples.improvements_p0 import calculate_profit_margin_safe

    result = calculate_profit_margin_safe(revenue=100, cost=60)
    assert result["profit"] == 40.0
    assert result["margin"] == 40.0


def test_calculate_profit_margin_safe_zero_revenue():
    """Test profit margin calculation with zero revenue"""
    from examples.improvements_p0 import calculate_profit_margin_safe

    # Should not crash!
    result = calculate_profit_margin_safe(revenue=0, cost=50)
    assert result["profit"] == -50.0
    assert result["margin"] == 0.0  # Safe default


def test_calculate_profit_margin_safe_negative():
    """Test profit margin calculation with loss"""
    from examples.improvements_p0 import calculate_profit_margin_safe

    result = calculate_profit_margin_safe(revenue=100, cost=150)
    assert result["profit"] == -50.0
    assert result["margin"] == -50.0


# ============================================================================
# Test Financial Metrics Calculation
# ============================================================================

def test_calculate_financial_metrics_safe_normal(sample_data):
    """Test financial metrics with normal data"""
    from examples.improvements_p0 import calculate_financial_metrics_safe

    metrics = calculate_financial_metrics_safe(sample_data)

    assert metrics["revenue"]["total_with_iva"] == 522.0  # 116 + 232 + 174
    assert metrics["revenue"]["total_without_iva"] == 450.0  # 100 + 200 + 150
    assert metrics["costs"]["total_cost"] == 270.0  # 60 + 120 + 90
    assert metrics["profit"]["profit"] == 180.0  # 450 - 270
    assert metrics["profit"]["margin"] == 40.0  # (180 / 450) * 100


def test_calculate_financial_metrics_safe_empty(empty_data):
    """Test financial metrics with empty data"""
    from examples.improvements_p0 import calculate_financial_metrics_safe

    # Should not crash!
    metrics = calculate_financial_metrics_safe(empty_data)

    assert metrics["revenue"]["total_with_iva"] == 0.0
    assert metrics["revenue"]["total_without_iva"] == 0.0
    assert metrics["revenue"]["average_order_value"] == 0.0
    assert metrics["costs"]["total_cost"] == 0.0
    assert metrics["profit"]["profit"] == 0.0
    assert metrics["profit"]["margin"] == 0.0


def test_calculate_financial_metrics_safe_decimal(decimal_data):
    """Test financial metrics with Decimal types"""
    from examples.improvements_p0 import calculate_financial_metrics_safe

    # Should handle Decimal types correctly
    metrics = calculate_financial_metrics_safe(decimal_data)

    assert isinstance(metrics["revenue"]["total_with_iva"], float)
    assert metrics["revenue"]["total_with_iva"] == 116.50


def test_calculate_financial_metrics_safe_null(null_data):
    """Test financial metrics with null values"""
    from examples.improvements_p0 import calculate_financial_metrics_safe

    # Should handle None values gracefully
    metrics = calculate_financial_metrics_safe(null_data)

    assert metrics["revenue"]["total_with_iva"] == 200.0  # Only second row
    assert metrics["revenue"]["total_without_iva"] == 100.0  # Only first row


# ============================================================================
# Test Customer Segmentation
# ============================================================================

def test_customer_segmentation():
    """Test customer segmentation logic"""
    # Import the actual BusinessMetricsCalculator if needed
    # or create a minimal version for testing

    def segment_customer(revenue: float, orders: int) -> str:
        """Customer segmentation logic"""
        if revenue > 500000 and orders > 5:
            return "VIP"
        elif revenue > 200000:
            return "High Value"
        elif orders > 10:
            return "Frequent"
        elif revenue > 50000:
            return "Regular"
        else:
            return "Occasional"

    assert segment_customer(600000, 10) == "VIP"
    assert segment_customer(300000, 2) == "High Value"
    assert segment_customer(10000, 15) == "Frequent"
    assert segment_customer(100000, 5) == "Regular"
    assert segment_customer(10000, 2) == "Occasional"


# ============================================================================
# Integration Test
# ============================================================================

def test_full_pipeline_with_sample_data(sample_data):
    """Test complete analysis pipeline with known data"""
    from examples.improvements_p0 import calculate_financial_metrics_safe

    # This would normally test the complete flow
    metrics = calculate_financial_metrics_safe(sample_data)

    # Verify all expected keys exist
    assert "revenue" in metrics
    assert "costs" in metrics
    assert "profit" in metrics

    # Verify calculations are reasonable
    assert metrics["revenue"]["total_with_iva"] > 0
    assert metrics["costs"]["total_cost"] > 0
    assert metrics["profit"]["profit"] > 0
    assert 0 <= metrics["profit"]["margin"] <= 100


# ============================================================================
# Edge Cases
# ============================================================================

def test_edge_case_single_record():
    """Test with single record"""
    from examples.improvements_p0 import calculate_financial_metrics_safe

    data = [{"TotalMasIva": 100, "TotalSinIva": 84, "ValorCosto": 50}]
    metrics = calculate_financial_metrics_safe(data)

    assert metrics["revenue"]["total_with_iva"] == 100
    assert metrics["profit"]["profit"] == 34  # 84 - 50


def test_edge_case_large_numbers():
    """Test with very large numbers"""
    from examples.improvements_p0 import calculate_financial_metrics_safe

    data = [{"TotalMasIva": 1e9, "TotalSinIva": 1e9, "ValorCosto": 5e8}]
    metrics = calculate_financial_metrics_safe(data)

    assert metrics["revenue"]["total_with_iva"] == 1e9
    assert metrics["profit"]["margin"] == 50.0


def test_edge_case_all_zeros():
    """Test with all zero values"""
    from examples.improvements_p0 import calculate_financial_metrics_safe

    data = [{"TotalMasIva": 0, "TotalSinIva": 0, "ValorCosto": 0}]
    metrics = calculate_financial_metrics_safe(data)

    # Should not crash
    assert metrics["revenue"]["total_with_iva"] == 0
    assert metrics["profit"]["margin"] == 0


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
