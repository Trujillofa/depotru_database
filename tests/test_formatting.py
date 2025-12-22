#!/usr/bin/env python3
"""
Tests for number formatting functions (Colombian format).
"""

import pytest
import pandas as pd
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestNumberFormatting:
    """Test Colombian number formatting functions"""

    def test_format_currency(self):
        """Test currency formatting with Colombian pesos"""
        # Import dynamically to avoid missing dependencies in CI
        try:
            from src.vanna_grok import format_number
        except ImportError:
            pytest.skip("vanna_grok not available")

        # Test various currency values
        assert format_number(1234567, "TotalMasIva") == "$1.234.567"
        assert format_number(1000, "Revenue") == "$1.000"
        assert format_number(100.5, "Precio") == "$100"

    def test_format_percentage(self):
        """Test percentage formatting (Spanish format: 45,6%)"""
        try:
            from src.vanna_grok import format_number
        except ImportError:
            pytest.skip("vanna_grok not available")

        # Test various percentage values
        assert format_number(45.6, "Margen_Promedio_Pct") == "45,6%"
        assert format_number(100.0, "margin_pct") == "100,0%"
        assert format_number(0.5, "percentage") == "0,5%"

    def test_format_quantity(self):
        """Test quantity formatting (thousands separator)"""
        try:
            from src.vanna_grok import format_number
        except ImportError:
            pytest.skip("vanna_grok not available")

        # Test integer quantities
        assert format_number(1234, "Cantidad") == "1.234"
        assert format_number(1000000, "Units") == "1.000.000"

    def test_format_null_values(self):
        """Test handling of null/None/NaN values"""
        try:
            from src.vanna_grok import format_number
        except ImportError:
            pytest.skip("vanna_grok not available")

        # Test various null representations
        assert format_number(None, "TotalMasIva") == "-"
        assert format_number(pd.NA, "Revenue") == "-"
        assert format_number(float('nan'), "Cantidad") == "-"

    def test_format_dataframe(self):
        """Test formatting entire DataFrame"""
        try:
            from src.vanna_grok import format_dataframe
        except ImportError:
            pytest.skip("vanna_grok not available")

        # Create test DataFrame
        df = pd.DataFrame({
            'TotalMasIva': [1234567.89, 9876543.21],
            'Margen_Promedio_Pct': [45.6, 23.4],
            'Cantidad': [1234, 5678]
        })

        # Format it
        df_formatted = format_dataframe(df)

        # Verify formatting
        assert df_formatted.iloc[0]['TotalMasIva'] == "$1.234.568"
        assert df_formatted.iloc[0]['Margen_Promedio_Pct'] == "45,6%"
        assert df_formatted.iloc[0]['Cantidad'] == "1.234"

    def test_format_dataframe_row_limit(self):
        """Test that format_dataframe respects MAX_DISPLAY_ROWS"""
        try:
            from src.vanna_grok import format_dataframe
        except ImportError:
            pytest.skip("vanna_grok not available")

        # Create large DataFrame (200 rows)
        df = pd.DataFrame({
            'Value': range(200)
        })

        # Format with limit of 50
        df_formatted = format_dataframe(df, max_rows=50)

        # Should only return 50 rows
        assert len(df_formatted) == 50


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
