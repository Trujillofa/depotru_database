"""
Comprehensive tests for business_analyzer_combined.py
"""

import json
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Mock pymssql before importing business_analyzer_combined
sys.modules["pymssql"] = Mock()
sys.modules["pyodbc"] = Mock()

# Mock config before importing
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

    def test_safe_divide_none_denominator(self):
        """Test division with None denominator"""
        assert safe_divide(10, None) == 0.0

    def test_safe_divide_zero_numerator(self):
        """Test zero numerator"""
        assert safe_divide(0, 5) == 0.0


class TestValidateDateFormat:
    """Test validate_date_format function"""

    def test_valid_date_formats(self):
        """Test various valid date formats"""
        assert validate_date_format("2025-01-15", "test") == "2025-01-15"
        assert validate_date_format("2024-12-31", "test") == "2024-12-31"
        assert validate_date_format("2023-06-01", "test") == "2023-06-01"

    def test_invalid_date_format(self):
        """Test invalid date formats raise ValueError"""
        with pytest.raises(ValueError, match="Invalid date format"):
            validate_date_format("01-15-2025", "test")
        with pytest.raises(ValueError, match="Invalid date format"):
            validate_date_format("2025/01/15", "test")
        with pytest.raises(ValueError, match="Invalid date format"):
            validate_date_format("invalid", "test")

    def test_empty_date(self):
        """Test empty date returns None"""
        assert validate_date_format("", "test") is None
        assert validate_date_format(None, "test") is None

    def test_future_date_warning(self):
        """Test future date raises warning"""
        future_year = datetime.now().year + 2
        with pytest.raises(ValueError, match="Future date"):
            validate_date_format(f"{future_year}-01-01", "test")


class TestValidateDateRange:
    """Test validate_date_range function"""

    def test_valid_date_range(self):
        """Test valid date range"""
        start, end = validate_date_range("2025-01-01", "2025-12-31")
        assert start == "2025-01-01"
        assert end == "2025-12-31"

    def test_start_after_end(self):
        """Test start date after end date raises ValueError"""
        with pytest.raises(ValueError, match="Start date must be before"):
            validate_date_range("2025-12-31", "2025-01-01")

    def test_same_start_end_date(self):
        """Test same start and end date is valid"""
        start, end = validate_date_range("2025-06-15", "2025-06-15")
        assert start == "2025-06-15"
        assert end == "2025-06-15"

    def test_none_dates(self):
        """Test None dates are handled"""
        start, end = validate_date_range(None, None)
        assert start is None
        assert end is None


class TestValidateLimit:
    """Test validate_limit function"""

    def test_valid_limits(self):
        """Test valid limit values"""
        assert validate_limit(100) == 100
        assert validate_limit(1000) == 1000
        assert validate_limit(5000) == 5000

    def test_limit_too_small(self):
        """Test limit below minimum raises ValueError"""
        with pytest.raises(ValueError, match="Limit must be between"):
            validate_limit(0)
        with pytest.raises(ValueError, match="Limit must be between"):
            validate_limit(-10)

    def test_limit_too_large(self):
        """Test limit above maximum raises ValueError"""
        with pytest.raises(ValueError, match="Limit must be between"):
            validate_limit(100001)

    def test_limit_not_integer(self):
        """Test non-integer limit raises ValueError"""
        with pytest.raises(ValueError, match="Limit must be an integer"):
            validate_limit("100")
        with pytest.raises(ValueError, match="Limit must be an integer"):
            validate_limit(100.5)


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
        from decimal import Decimal
        
        encoder = DecimalEncoder()
        result = encoder.default(Decimal("10.5"))
        assert result == 10.5
        
        result = encoder.default(Decimal("100"))
        assert result == 100

    def test_non_decimal_fallback(self):
        """Test fallback for non-Decimal types"""
        from decimal import Decimal
        
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

    def test_calculate_all_metrics(self, sample_data):
        """Test calculate_all_metrics method"""
        calc = BusinessMetricsCalculator(sample_data)
        metrics = calc.calculate_all_metrics()
        
        assert "financial" in metrics
        assert "customers" in metrics
        assert "products" in metrics
        assert "categories" in metrics
        assert "inventory" in metrics
        assert "trends" in metrics
        assert "profitability" in metrics

    def test_calculate_financial_metrics(self, sample_data):
        """Test financial metrics calculation"""
        calc = BusinessMetricsCalculator(sample_data)
        financial = calc.calculate_financial_metrics()
        
        assert "total_revenue_with_iva" in financial
        assert "total_revenue_without_iva" in financial
        assert "total_cost" in financial
        assert "gross_profit" in financial
        assert "profit_margin" in financial
        assert "average_order_value" in financial
        
        # Verify calculations
        assert financial["total_revenue_with_iva"] == 522.0  # 116 + 232 + 174
        assert financial["total_revenue_without_iva"] == 450.0  # 100 + 200 + 150
        assert financial["total_cost"] == 270.0  # 60 + 120 + 90

    def test_analyze_customers(self, sample_data):
        """Test customer analysis"""
        calc = BusinessMetricsCalculator(sample_data)
        customers = calc.analyze_customers()
        
        assert "total_customers" in customers
        assert "segments" in customers
        assert "top_customers" in customers
        assert "concentration" in customers
        
        assert customers["total_customers"] == 2  # Customer A and B

    def test_analyze_products(self, sample_data):
        """Test product analysis"""
        calc = BusinessMetricsCalculator(sample_data)
        products = calc.analyze_products()
        
        assert "total_products" in products
        assert "top_products" in products
        assert "profitability" in products
        
        assert products["total_products"] == 2  # Product 1 and 2

    def test_analyze_categories(self, sample_data):
        """Test category analysis"""
        calc = BusinessMetricsCalculator(sample_data)
        categories = calc.analyze_categories()
        
        assert "total_categories" in categories
        assert "category_performance" in categories
        assert "subcategory_analysis" in categories
        
        assert categories["total_categories"] == 2  # Category 1 and 2

    def test_analyze_inventory(self, sample_data):
        """Test inventory analysis"""
        calc = BusinessMetricsCalculator(sample_data)
        inventory = calc.analyze_inventory()
        
        assert "total_transactions" in inventory
        assert "fast_movers" in inventory
        assert "slow_movers" in inventory
        assert "total_items" in inventory

    def test_analyze_trends(self, sample_data):
        """Test trend analysis"""
        calc = BusinessMetricsCalculator(sample_data)
        trends = calc.analyze_trends()
        
        assert "monthly" in trends
        assert "category_distribution" in trends

    def test_analyze_profitability(self, sample_data):
        """Test profitability analysis"""
        calc = BusinessMetricsCalculator(sample_data)
        profitability = calc.analyze_profitability()
        
        assert "by_category" in profitability
        assert "overall_margin" in profitability

    def test_segment_customer(self, sample_data):
        """Test customer segmentation logic"""
        calc = BusinessMetricsCalculator(sample_data)
        
        # VIP customer
        assert calc._segment_customer(600000, 10) == "VIP"
        
        # High Value customer
        assert calc._segment_customer(300000, 5) == "High Value"
        
        # Frequent customer
        assert calc._segment_customer(100000, 15) == "Frequent"
        
        # Regular customer
        assert calc._segment_customer(75000, 5) == "Regular"
        
        # Low Value customer
        assert calc._segment_customer(30000, 2) == "Low Value"

    def test_empty_data_handling(self, empty_data):
        """Test handling of empty data"""
        calc = BusinessMetricsCalculator(empty_data)
        
        financial = calc.calculate_financial_metrics()
        assert financial["total_revenue_with_iva"] == 0
        assert financial["total_revenue_without_iva"] == 0
        
        customers = calc.analyze_customers()
        assert customers["total_customers"] == 0
        
        products = calc.analyze_products()
        assert products["total_products"] == 0

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
            "financial": {
                "profit_margin": 25.0,
                "average_order_value": 150.0,
            },
            "products": {
                "profitability": {
                    "critical_products": [],
                    "underperforming_products": [],
                    "star_products": ["Product A"],
                }
            },
            "categories": {
                "category_performance": {
                    "Category 1": {"margin": 5.0},
                    "Category 2": {"margin": 35.0},
                }
            },
        }

    def test_generate_recommendations_structure(self, sample_metrics):
        """Test recommendations structure"""
        recommendations = generate_recommendations(sample_metrics)
        
        assert isinstance(recommendations, list)
        assert len(recommendations) > 0
        
        for rec in recommendations:
            assert "type" in rec
            assert "priority" in rec
            assert "message" in rec

    def test_low_margin_recommendation(self):
        """Test recommendation for low profit margin"""
        metrics = {
            "financial": {"profit_margin": 5.0, "average_order_value": 100.0},
            "products": {"profitability": {"critical_products": [], "underperforming_products": [], "star_products": []}},
            "categories": {"category_performance": {}},
        }
        
        recommendations = generate_recommendations(metrics)
        
        # Should have a warning about low margins
        warning_recs = [r for r in recommendations if "margin" in r["message"].lower() or "profit" in r["message"].lower()]
        assert len(warning_recs) > 0

    def test_critical_products_recommendation(self):
        """Test recommendation for critical products"""
        metrics = {
            "financial": {"profit_margin": 20.0, "average_order_value": 150.0},
            "products": {"profitability": {"critical_products": ["Bad Product"], "underperforming_products": [], "star_products": []}},
            "categories": {"category_performance": {}},
        }
        
        recommendations = generate_recommendations(metrics)
        
        # Should have urgent recommendation about critical products
        critical_recs = [r for r in recommendations if r["type"] == "danger"]
        assert len(critical_recs) > 0


class TestPrintDetailedStatistics:
    """Test print_detailed_statistics function"""

    @pytest.fixture
    def sample_analysis(self):
        """Sample analysis data for printing"""
        return {
            "metrics": {
                "financial": {
                    "total_revenue_with_iva": 1000.0,
                    "total_revenue_without_iva": 850.0,
                    "average_order_value": 150.0,
                },
                "customers": {
                    "total_customers": 10,
                    "top_customers": [
                        {"name": "Customer A", "revenue": 500.0},
                        {"name": "Customer B", "revenue": 300.0},
                    ],
                },
                "products": {
                    "total_products": 5,
                    "top_products": [
                        {"name": "Product A", "revenue": 400.0},
                    ],
                },
                "categories": {
                    "category_performance": {
                        "Category 1": {"revenue": 600.0, "cost": 400.0, "margin": 33.3},
                    }
                },
            },
            "recommendations": [
                {"type": "success", "priority": 1, "message": "Good performance"},
            ],
        }

    def test_print_statistics_output(self, sample_analysis, capsys):
        """Test that statistics are printed"""
        print_detailed_statistics(sample_analysis)
        
        captured = capsys.readouterr()
        output = captured.out
        
        # Should contain key sections
        assert "FINANCIAL METRICS" in output or "Financial" in output
        assert "Customer" in output or "CUSTOMER" in output
        assert "Product" in output or "PRODUCT" in output


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_safe_divide_with_floats(self):
        """Test safe_divide with float inputs"""
        assert safe_divide(10.5, 2.5) == 4.2

    def test_validate_sql_identifier_unicode(self):
        """Test SQL identifier with unicode characters"""
        # Unicode should be rejected
        with pytest.raises(ValueError):
            validate_sql_identifier("táble", "table")

    def test_business_metrics_with_missing_fields(self):
        """Test calculator with incomplete data"""
        incomplete_data = [
            {"TercerosNombres": "Customer A"},  # Missing most fields
        ]
        
        calc = BusinessMetricsCalculator(incomplete_data)
        metrics = calc.calculate_all_metrics()
        
        # Should handle missing fields gracefully
        assert "financial" in metrics
        assert "customers" in metrics
