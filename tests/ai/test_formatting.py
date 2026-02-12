"""
Tests for AI package formatting module.
"""

import os
import sys

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

import pandas as pd

from business_analyzer.ai.formatting import (
    CURRENCY_COLUMNS,
    PERCENTAGE_COLUMNS,
    format_currency,
    format_dataframe,
    format_integer,
    format_number,
    format_percentage,
)


class TestFormatNumber:
    """Test number formatting functions."""

    def test_format_currency_column(self):
        """Test formatting of known currency columns."""
        result = format_number(1234567, "TotalMasIva")
        assert result == "$1.234.567"

    def test_format_percentage_column(self):
        """Test formatting of known percentage columns."""
        result = format_number(45.6, "Margen_Promedio_Pct")
        assert result == "45,6%"

    def test_format_integer(self):
        """Test formatting of integer values."""
        result = format_number(1234, "Cantidad")
        assert result == "1.234"

    def test_format_decimal(self):
        """Test formatting of decimal values."""
        result = format_number(1234.56, "SomeDecimalValue")
        # Should format as regular decimal with 2 places
        assert "1.234" in result or "1,234" in result

    def test_format_none(self):
        """Test formatting of None values."""
        result = format_number(None, "AnyColumn")
        assert result == "-"

    def test_format_nan(self):
        """Test formatting of NaN values."""
        result = format_number(float("nan"), "AnyColumn")
        assert result == "-"


class TestFormatCurrency:
    """Test currency formatting."""

    def test_format_currency_basic(self):
        """Test basic currency formatting."""
        result = format_currency(1234567)
        assert result == "$1.234.567"

    def test_format_currency_with_decimals(self):
        """Test currency formatting with decimals."""
        result = format_currency(1234.56, decimals=2)
        assert "$" in result
        assert "1.234" in result or "1,234" in result

    def test_format_currency_none(self):
        """Test currency formatting with None."""
        result = format_currency(None)
        assert result == "-"


class TestFormatPercentage:
    """Test percentage formatting."""

    def test_format_percentage_basic(self):
        """Test basic percentage formatting."""
        result = format_percentage(45.6)
        assert result == "45,6%"

    def test_format_percentage_zero_decimals(self):
        """Test percentage formatting with zero decimals."""
        result = format_percentage(45.6, decimals=0)
        assert result == "46%"

    def test_format_percentage_none(self):
        """Test percentage formatting with None."""
        result = format_percentage(None)
        assert result == "-"


class TestFormatInteger:
    """Test integer formatting."""

    def test_format_integer_basic(self):
        """Test basic integer formatting."""
        result = format_integer(1234)
        assert result == "1.234"

    def test_format_integer_large(self):
        """Test large integer formatting."""
        result = format_integer(1234567890)
        assert "1.234.567.890" in result

    def test_format_integer_none(self):
        """Test integer formatting with None."""
        result = format_integer(None)
        assert result == "-"


class TestFormatDataFrame:
    """Test DataFrame formatting."""

    def test_format_dataframe_basic(self):
        """Test basic DataFrame formatting."""
        df = pd.DataFrame(
            {
                "TotalMasIva": [1000, 2000, 3000],
                "Cantidad": [10, 20, 30],
            }
        )
        result = format_dataframe(df)
        assert isinstance(result, pd.DataFrame)
        assert result.shape == df.shape

    def test_format_dataframe_empty(self):
        """Test empty DataFrame formatting."""
        df = pd.DataFrame()
        result = format_dataframe(df)
        assert result is df  # Should return same empty DataFrame

    def test_format_dataframe_none(self):
        """Test None DataFrame formatting."""
        result = format_dataframe(None)
        assert result is None


class TestConstants:
    """Test formatting constants."""

    def test_currency_columns(self):
        """Test that currency columns are defined."""
        assert "TotalMasIva" in CURRENCY_COLUMNS
        assert "TotalSinIva" in CURRENCY_COLUMNS
        assert "Revenue" in CURRENCY_COLUMNS

    def test_percentage_columns(self):
        """Test that percentage columns are defined."""
        assert "Margen_Promedio_Pct" in PERCENTAGE_COLUMNS
        assert "profit_margin_pct" in PERCENTAGE_COLUMNS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
