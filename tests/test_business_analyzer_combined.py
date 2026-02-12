"""
Comprehensive tests for business_analyzer_combined.py
"""

import sys
from datetime import datetime
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Mock pymssql before importing business_analyzer_combined
sys.modules["pymssql"] = Mock()
sys.modules["pyodbc"] = Mock()

# Mock config module with all necessary attributes
mock_config = Mock()
mock_config.Config = Mock()
mock_config.Config.DB_HOST = "test-host"
mock_config.Config.DB_PORT = 1433
mock_config.Config.DB_USER = "test-user"
mock_config.Config.DB_PASSWORD = "test-password"
mock_config.Config.DB_NAME = "TestDB"
mock_config.Config.DB_TABLE = "test_table"
mock_config.Config.NCX_FILE_PATH = "/test/connections.ncx"
mock_config.Config.DB_LOGIN_TIMEOUT = 10
mock_config.Config.DB_TIMEOUT = 10
mock_config.Config.DB_TDS_VERSION = "7.4"
mock_config.Config.DEFAULT_LIMIT = 1000
mock_config.Config.EXCLUDED_DOCUMENT_CODES = ["XY", "AS"]
mock_config.Config.LOG_LEVEL = "INFO"
mock_config.Config.has_direct_db_config = Mock(return_value=True)
mock_config.Config.ensure_output_dir = Mock(return_value=Path("/tmp"))


# Create real config classes with actual values (not mocks)
class CustomerSegmentation:
    VIP_REVENUE_THRESHOLD = 500000
    VIP_ORDERS_THRESHOLD = 5
    HIGH_VALUE_THRESHOLD = 200000
    FREQUENT_ORDERS_THRESHOLD = 10
    REGULAR_REVENUE_THRESHOLD = 50000


class InventoryConfig:
    FAST_MOVER_THRESHOLD = 5
    SLOW_MOVER_THRESHOLD = 2


class ProfitabilityConfig:
    LOW_MARGIN_THRESHOLD = 10
    STAR_PRODUCT_MARGIN = 30
    CRITICAL_MARGIN = 0


mock_config.CustomerSegmentation = CustomerSegmentation
mock_config.InventoryConfig = InventoryConfig
mock_config.ProfitabilityConfig = ProfitabilityConfig

sys.modules["config"] = mock_config

from src.business_analyzer_combined import (
    BusinessMetricsCalculator,
    DecimalEncoder,
    generate_recommendations,
    print_detailed_statistics,
    safe_divide,
    validate_date_format,
    validate_date_range,
    validate_limit,
    validate_sql_identifier,
)


class TestSafeDivide:
    """Test safe_divide function"""

    def test_safe_divide_normal(self):
        """Test normal division"""
        assert safe_divide(10, 2) == 5.0
        assert safe_divide(7, 3) == pytest.approx(2.333, rel=0.01)

    def test_safe_divide_zero_denominator(self):
        """Test division by zero returns default"""
        assert safe_divide(10, 0) == 0.0
        assert safe_divide(10, 0, default=999) == 999

    def test_safe_divide_zero_numerator(self):
        """Test zero numerator"""
        assert safe_divide(0, 5) == 0.0

    def test_safe_divide_with_floats(self):
        """Test safe_divide with float inputs"""
        assert safe_divide(10.5, 2.5) == 4.2


class TestValidateDateFormat:
    """Test validate_date_format function"""

    def test_valid_date_formats(self):
        """Test various valid date formats return datetime objects"""
        result = validate_date_format("2025-01-15", "test")
        assert isinstance(result, datetime)
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_invalid_date_format(self):
        """Test invalid date formats raise ValueError"""
        with pytest.raises(ValueError, match="Invalid.*format"):
            validate_date_format("01-15-2025", "test")
        with pytest.raises(ValueError, match="Invalid.*format"):
            validate_date_format("2025/01/15", "test")
        with pytest.raises(ValueError, match="Invalid.*format"):
            validate_date_format("invalid", "test")

    def test_future_date_warning(self):
        """Test future date raises warning"""
        future_year = datetime.now().year + 2
        with pytest.raises(ValueError, match="year.*seems unreasonable"):
            validate_date_format(f"{future_year}-01-01", "test")


class TestValidateDateRange:
    """Test validate_date_range function"""

    def test_valid_date_range(self):
        """Test valid date range - function returns None on success"""
        result = validate_date_range("2025-01-01", "2025-12-31")
        assert result is None  # Function validates but returns None

    def test_start_after_end(self):
        """Test start date after end date raises ValueError"""
        with pytest.raises(ValueError, match="must be before"):
            validate_date_range("2025-12-31", "2025-01-01")

    def test_same_start_end_date(self):
        """Test same start and end date is valid"""
        result = validate_date_range("2025-06-15", "2025-06-15")
        assert result is None


class TestValidateLimit:
    """Test validate_limit function"""

    def test_valid_limits(self):
        """Test valid limit values - function returns None on success"""
        assert validate_limit(100) is None
        assert validate_limit(1000) is None
        assert validate_limit(5000) is None

    def test_limit_too_small(self):
        """Test limit below minimum raises ValueError"""
        with pytest.raises(ValueError, match="must be at least"):
            validate_limit(0)
        with pytest.raises(ValueError, match="must be at least"):
            validate_limit(-10)

    def test_limit_too_large(self):
        """Test limit above maximum raises ValueError"""
        with pytest.raises(ValueError, match="exceeds maximum"):
            validate_limit(1000001)


class TestValidateSQLIdentifier:
    """Test validate_sql_identifier function"""

    def test_valid_identifiers(self):
        """Test valid SQL identifiers"""
        assert validate_sql_identifier("table_name", "table") == "table_name"
        assert validate_sql_identifier("MyTable", "table") == "MyTable"
        assert validate_sql_identifier("table-123", "table") == "table-123"
        assert validate_sql_identifier("_private", "column") == "_private"

    def test_invalid_characters(self):
        """Test identifiers with invalid characters"""
        with pytest.raises(ValueError, match="Invalid.*SQL identifiers"):
            validate_sql_identifier("table; DROP", "table")
        with pytest.raises(ValueError, match="Invalid.*SQL identifiers"):
            validate_sql_identifier("table'name", "table")
        with pytest.raises(ValueError, match="Invalid.*SQL identifiers"):
            validate_sql_identifier('table"name', "table")
        with pytest.raises(ValueError, match="Invalid.*SQL identifiers"):
            validate_sql_identifier("table name", "table")

    def test_empty_identifier(self):
        """Test empty identifier"""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_sql_identifier("", "table")

    def test_too_long_identifier(self):
        """Test identifier exceeding max length"""
        long_name = "a" * 129
        with pytest.raises(ValueError, match="too long"):
            validate_sql_identifier(long_name, "table")

    def test_max_length_identifier(self):
        """Test identifier at max length"""
        max_name = "a" * 128
        assert validate_sql_identifier(max_name, "table") == max_name


class TestDecimalEncoder:
    """Test DecimalEncoder class"""

    def test_decimal_encoding(self):
        """Test encoding of Decimal values"""
        encoder = DecimalEncoder()
        result = encoder.default(Decimal("10.5"))
        assert result == 10.5

        result = encoder.default(Decimal("100"))
        assert result == 100

    def test_non_decimal_fallback(self):
        """Test fallback for non-Decimal types"""
        encoder = DecimalEncoder()

        # Should use default JSON encoder for other types
        with pytest.raises(TypeError):
            encoder.default("string")


class TestBusinessMetricsCalculator:
    """Test BusinessMetricsCalculator class"""

    @pytest.fixture
    def sample_data(self):
        """Sample transaction data"""
        return [
            {
                "TotalMasIva": 116.0,
                "TotalSinIva": 100.0,
                "ValorCosto": 60.0,
                "Cantidad": 2,
                "TercerosNombres": "Customer A",
                "ArticulosNombre": "Product 1",
                "categoria": "Category 1",
                "Fecha": datetime(2025, 1, 15),
            },
            {
                "TotalMasIva": 232.0,
                "TotalSinIva": 200.0,
                "ValorCosto": 120.0,
                "Cantidad": 4,
                "TercerosNombres": "Customer A",
                "ArticulosNombre": "Product 2",
                "categoria": "Category 1",
                "Fecha": datetime(2025, 1, 16),
            },
            {
                "TotalMasIva": 174.0,
                "TotalSinIva": 150.0,
                "ValorCosto": 90.0,
                "Cantidad": 3,
                "TercerosNombres": "Customer B",
                "ArticulosNombre": "Product 1",
                "categoria": "Category 2",
                "Fecha": datetime(2025, 1, 17),
            },
        ]

    @pytest.fixture
    def empty_data(self):
        """Empty dataset"""
        return []

    def test_init(self, sample_data):
        """Test calculator initialization"""
        calc = BusinessMetricsCalculator(sample_data)
        assert calc.data == sample_data

    def test_calculate_financial_metrics(self, sample_data):
        """Test financial metrics calculation"""
        calc = BusinessMetricsCalculator(sample_data)
        financial = calc.calculate_financial_metrics()

        # Check structure
        assert "revenue" in financial
        assert "costs" in financial
        assert "profit" in financial

        # Verify calculations
        assert financial["revenue"]["total_with_iva"] == 522.0  # 116 + 232 + 174
        assert financial["revenue"]["total_without_iva"] == 450.0  # 100 + 200 + 150
        assert financial["costs"]["total_cost"] == 270.0  # 60 + 120 + 90

    def test_analyze_customers(self, sample_data):
        """Test customer analysis"""
        calc = BusinessMetricsCalculator(sample_data)
        customers = calc.analyze_customers()

        assert "total_customers" in customers
        assert "top_customers" in customers
        assert "customer_concentration" in customers  # Actual key name
        assert "segmentation" in customers

        assert customers["total_customers"] == 2  # Customer A and B

    def test_analyze_products(self, sample_data):
        """Test product analysis"""
        calc = BusinessMetricsCalculator(sample_data)
        products = calc.analyze_products()

        assert "total_products" in products
        assert "top_products" in products
        # Note: profitability info is in top_products, not a separate key
        assert "underperforming_products" in products
        assert "star_products" in products

        assert products["total_products"] == 2  # Product 1 and 2

    def test_analyze_categories(self, sample_data):
        """Test category analysis"""
        calc = BusinessMetricsCalculator(sample_data)
        categories = calc.analyze_categories()

        assert "total_categories" in categories
        assert "category_performance" in categories

        assert categories["total_categories"] == 2  # Category 1 and 2

    def test_analyze_inventory(self, sample_data):
        """Test inventory analysis"""
        calc = BusinessMetricsCalculator(sample_data)
        inventory = calc.analyze_inventory()

        # Actual key names from implementation
        assert "fast_moving_items" in inventory
        assert "slow_moving_items" in inventory

    def test_analyze_trends(self, sample_data):
        """Test trend analysis"""
        calc = BusinessMetricsCalculator(sample_data)
        trends = calc.analyze_trends()

        assert "monthly_trends" in trends
        assert "category_distribution" in trends

    def test_analyze_profitability(self, sample_data):
        """Test profitability analysis"""
        calc = BusinessMetricsCalculator(sample_data)
        profitability = calc.analyze_profitability()

        assert "by_category" in profitability

    def test_segment_customer(self, sample_data):
        """Test customer segmentation logic"""
        calc = BusinessMetricsCalculator(sample_data)

        # VIP customer (high revenue AND high orders)
        assert calc._segment_customer(600000, 10) == "VIP"

        # High Value customer (high revenue only)
        assert calc._segment_customer(300000, 3) == "High Value"

        # Frequent customer (high orders only)
        assert calc._segment_customer(100000, 15) == "Frequent"

        # Regular customer (moderate revenue)
        assert calc._segment_customer(75000, 5) == "Regular"

        # Occasional customer (low revenue)
        assert calc._segment_customer(30000, 2) == "Occasional"

    def test_extract_value(self, sample_data):
        """Test _extract_value helper method"""
        calc = BusinessMetricsCalculator(sample_data)

        row = sample_data[0]
        assert calc._extract_value(row, ["TotalMasIva"]) == 116.0
        assert calc._extract_value(row, ["NonExistent"], default=0) == 0
        assert calc._extract_value(row, ["NonExistent"], default=999) == 999


class TestGenerateRecommendations:
    """Test generate_recommendations function"""

    @pytest.fixture
    def sample_metrics(self):
        """Sample metrics for recommendation testing"""
        return {
            "financial_metrics": {
                "profit": {"gross_profit_margin": 25.0},
            },
            "category_analytics": {
                "category_performance": [
                    {"risk_level": "LOW", "category_name": "Cat1"},
                ]
            },
            "product_analytics": {
                "underperforming_products": [],
                "star_products": ["Product A"],
            },
        }

    def test_generate_recommendations_returns_list(self, sample_metrics):
        """Test recommendations returns a list of strings"""
        recommendations = generate_recommendations(sample_metrics)

        assert isinstance(recommendations, list)
        # Should have at least one recommendation for star products
        assert len(recommendations) >= 1

        # Each recommendation should be a string
        for rec in recommendations:
            assert isinstance(rec, str)

    def test_low_margin_recommendation(self):
        """Test recommendation for low profit margin"""
        metrics = {
            "financial_metrics": {"profit": {"gross_profit_margin": 5.0}},
            "category_analytics": {"category_performance": []},
            "product_analytics": {"underperforming_products": [], "star_products": []},
        }

        recommendations = generate_recommendations(metrics)

        # Should have a warning about low margins
        assert any(
            "margin" in r.lower() or "profit" in r.lower() for r in recommendations
        )

    def test_critical_categories_recommendation(self):
        """Test recommendation for critical categories"""
        metrics = {
            "financial_metrics": {"profit": {"gross_profit_margin": 20.0}},
            "category_analytics": {
                "category_performance": [
                    {"risk_level": "CRITICAL", "category_name": "BadCat"},
                ]
            },
            "product_analytics": {"underperforming_products": [], "star_products": []},
        }

        recommendations = generate_recommendations(metrics)

        # Should have urgent recommendation about critical categories
        assert any("CRITICAL" in r or "critical" in r.lower() for r in recommendations)


class TestPrintDetailedStatistics:
    """Test print_detailed_statistics function"""

    @pytest.fixture
    def sample_analysis(self):
        """Sample analysis data with correct structure"""
        return {
            "calculated_metrics": {
                "financial_metrics": {
                    "revenue": {
                        "total_with_iva": 1000.0,
                        "total_without_iva": 850.0,
                        "average_order_value": 150.0,
                    },
                    "costs": {"total_cost": 600.0},
                    "profit": {"gross_profit": 250.0},
                },
                "customer_analytics": {
                    "total_customers": 10,
                    "top_customers": [
                        {"customer_name": "Customer A", "total_revenue": 500.0},
                        {"customer_name": "Customer B", "total_revenue": 300.0},
                    ],
                },
                "product_analytics": {
                    "total_products": 5,
                    "top_products": [
                        {"product_name": "Product A", "total_revenue": 400.0},
                    ],
                    "underperforming_products": [],
                    "star_products": [],
                },
                "category_analytics": {
                    "category_performance": [
                        {
                            "category_name": "Category 1",
                            "total_revenue": 600.0,
                            "total_cost": 400.0,
                            "profit_margin": 33.3,
                        }
                    ]
                },
                "trend_analytics": {"monthly_trends": {}},
            },
            "strategic_recommendations": [
                "Test recommendation",
            ],
        }

    def test_print_statistics_output(self, sample_analysis, capsys):
        """Test that statistics are printed"""
        print_detailed_statistics(sample_analysis)

        captured = capsys.readouterr()
        output = captured.out

        # Should contain key sections
        assert "DETAILED BUSINESS STATISTICS" in output
        assert "Product A" in output
        assert "Customer A" in output
        assert "Category 1" in output


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_safe_divide_with_various_types(self):
        """Test safe_divide with various numeric types"""
        assert safe_divide(10, 2) == 5.0
        assert safe_divide(10.0, 2.0) == 5.0
        assert safe_divide(0, 5) == 0.0
        assert safe_divide(10, 0, default=-1) == -1

    def test_validate_sql_identifier_unicode(self):
        """Test SQL identifier with unicode characters"""
        # Unicode should be rejected
        with pytest.raises(ValueError):
            validate_sql_identifier("táble", "table")

    def test_business_metrics_with_minimal_data(self):
        """Test calculator with minimal data"""
        minimal_data = [
            {
                "TotalMasIva": 100.0,
                "TotalSinIva": 86.0,
                "ValorCosto": 50.0,
                "Cantidad": 1,
                "TercerosNombres": "Customer",
                "ArticulosNombre": "Product",
                "categoria": "Category",
                "Fecha": datetime(2025, 1, 1),
            },
        ]

        calc = BusinessMetricsCalculator(minimal_data)
        metrics = calc.calculate_financial_metrics()

        # Should handle minimal data gracefully
        assert "revenue" in metrics
        assert metrics["revenue"]["total_with_iva"] == 100.0
