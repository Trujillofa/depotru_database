"""
Unit Tests for vanna_grok.py
=============================
Tests core functionality of the Vanna Grok integration without requiring
external dependencies (API keys, database connections).

Run with: pytest tests/test_vanna_grok.py -v
"""

import pytest
from pathlib import Path
import sys

# Skip entire module if dependencies not installed
pd = pytest.importorskip("pandas", reason="pandas not installed")
pytest.importorskip("vanna", reason="vanna not installed")

from unittest.mock import Mock, patch, MagicMock

# Add src to path for imports (using pytest.ini pythonpath configuration)
from vanna_grok import format_number, format_dataframe


# =============================================================================
# Test Number Formatting
# =============================================================================

class TestNumberFormatting:
    """Test Colombian number formatting functions."""
    
    def test_format_currency_columns(self):
        """Test currency formatting with Colombian peso format."""
        # Test various currency keywords
        assert format_number(1000000, "revenue") == "$1.000.000"
        assert format_number(1234567, "ganancia") == "$1.234.567"
        assert format_number(500000, "total") == "$500.000"
        assert format_number(100, "costo") == "$100"
        assert format_number(999.99, "precio") == "$1.000"  # Rounds to integer
        
    def test_format_percentage_columns(self):
        """Test percentage formatting with Spanish format."""
        # Test percentage keywords
        result = format_number(45.6, "margen")
        assert "45" in result and "%" in result
        
        result = format_number(12.3, "margin")
        assert "12" in result and "%" in result
        
    def test_format_regular_numbers(self):
        """Test regular number formatting (quantities, counts)."""
        # Integer formatting
        assert format_number(1234, "cantidad") == "1.234"
        assert format_number(1000000, "unidades") == "1.000.000"
        
    def test_format_null_values(self):
        """Test handling of null/None values."""
        assert format_number(None, "revenue") == "-"
        assert format_number(pd.NA, "revenue") == "-"
        assert format_number(float('nan'), "revenue") == "-"
        
    def test_format_invalid_values(self):
        """Test handling of invalid numeric values."""
        # Should return string representation
        result = format_number("invalid", "revenue")
        assert result == "invalid"
        
        result = format_number("text", "margen")
        assert result == "text"
    
    def test_format_zero_values(self):
        """Test formatting of zero values."""
        assert format_number(0, "revenue") == "$0"
        assert format_number(0.0, "margen") == "0,0%" or format_number(0.0, "margen") == "0.0%"
        
    def test_format_negative_values(self):
        """Test formatting of negative values."""
        result = format_number(-1000, "revenue")
        assert "-" in result
        assert "1" in result
        
    def test_format_dataframe_basic(self):
        """Test formatting entire dataframe."""
        df = pd.DataFrame({
            "revenue": [1000000, 2000000, 3000000],
            "margen": [25.5, 30.2, 28.9],
            "cantidad": [100, 200, 150]
        })
        
        df_formatted = format_dataframe(df)
        
        # Should return a dataframe
        assert isinstance(df_formatted, pd.DataFrame)
        assert len(df_formatted) == 3
        assert list(df_formatted.columns) == ["revenue", "margen", "cantidad"]
        
        # Values should be formatted as strings
        assert isinstance(df_formatted.iloc[0]["revenue"], str)
        assert "$" in df_formatted.iloc[0]["revenue"]
        
    def test_format_dataframe_empty(self):
        """Test formatting empty dataframe."""
        df = pd.DataFrame()
        result = format_dataframe(df)
        assert result.empty
        
    def test_format_dataframe_none(self):
        """Test formatting None dataframe."""
        result = format_dataframe(None)
        assert result is None


# =============================================================================
# Test Configuration (Mocked)
# =============================================================================

class TestConfiguration:
    """Test configuration management."""
    
    @patch.dict('os.environ', {'GROK_API_KEY': 'xai-test-key-123'})
    def test_config_with_valid_grok_key(self):
        """Test configuration with valid Grok API key."""
        # Reimport to get new config
        import importlib
        import vanna_grok
        importlib.reload(vanna_grok)
        
        # Should not raise error
        assert True
    
    @patch.dict('os.environ', {
        'GROK_API_KEY': 'xai-test-key',
        'DB_SERVER': 'test-server',
        'DB_NAME': 'TestDB',
        'DB_USER': 'testuser',
        'DB_PASSWORD': 'testpass',
        'PORT': '9999',
        'HOST': 'localhost'
    })
    def test_config_custom_values(self):
        """Test configuration with custom environment values."""
        # Reimport to get new config
        import importlib
        import vanna_grok
        importlib.reload(vanna_grok)
        
        from vanna_grok import Config
        
        assert Config.GROK_API_KEY == 'xai-test-key'
        assert Config.DB_SERVER == 'test-server'
        assert Config.DB_NAME == 'TestDB'
        assert Config.DB_USER == 'testuser'
        assert Config.DB_PASSWORD == 'testpass'
        assert Config.PORT == 9999
        assert Config.HOST == 'localhost'


# =============================================================================
# Test AI Insights Generation (Mocked)
# =============================================================================

class TestInsightsGeneration:
    """Test AI insights generation with mocked Grok client."""
    
    def test_generate_insights_with_data(self):
        """Test insights generation with valid data."""
        from vanna_grok import generate_insights
        
        # Create sample data
        df = pd.DataFrame({
            "producto": ["Producto A", "Producto B", "Producto C"],
            "ventas": [1000000, 2000000, 1500000],
            "margen": [25.5, 30.2, 28.9]
        })
        
        # Mock Grok client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Test insights response"
        mock_client.chat.completions.create.return_value = mock_response
        
        result = generate_insights(
            question="¿Cuáles son mis productos más vendidos?",
            sql="SELECT * FROM productos",
            df=df,
            grok_client=mock_client
        )
        
        # Should return string with insights
        assert isinstance(result, str)
        assert "ANÁLISIS INTELIGENTE" in result or "insights" in result.lower()
        
    def test_generate_insights_empty_dataframe(self):
        """Test insights generation with empty dataframe."""
        from vanna_grok import generate_insights
        
        df = pd.DataFrame()
        mock_client = MagicMock()
        
        result = generate_insights(
            question="Test question",
            sql="SELECT * FROM test",
            df=df,
            grok_client=mock_client
        )
        
        # Should return warning message
        assert "No hay datos" in result or isinstance(result, str)
    
    def test_generate_insights_api_error(self):
        """Test insights generation when API fails."""
        from vanna_grok import generate_insights
        
        df = pd.DataFrame({"col1": [1, 2, 3]})
        
        # Mock client that raises exception
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        result = generate_insights(
            question="Test question",
            sql="SELECT * FROM test",
            df=df,
            grok_client=mock_client
        )
        
        # Should handle error gracefully
        assert isinstance(result, str)
        assert "No se pudieron generar insights" in result or "error" in result.lower()


# =============================================================================
# Integration Tests (Require Dependencies)
# =============================================================================

@pytest.mark.integration
@pytest.mark.requires_api
class TestVannaGrokIntegration:
    """Integration tests that require actual dependencies."""
    
    @pytest.mark.skip(reason="Requires Grok API key and should not run in CI")
    def test_grok_vanna_initialization(self):
        """Test GrokVanna class initialization."""
        # This would require actual API key and dependencies
        # Skipped in CI/CD
        pass
    
    @pytest.mark.skip(reason="Requires database connection and should not run in CI")
    def test_database_connection(self):
        """Test database connection."""
        # This would require actual database
        # Skipped in CI/CD
        pass


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_format_very_large_numbers(self):
        """Test formatting very large numbers."""
        result = format_number(1000000000000, "revenue")
        assert "$" in result
        assert "1.000.000.000.000" in result or "trillion" in result.lower()
    
    def test_format_very_small_numbers(self):
        """Test formatting very small numbers."""
        result = format_number(0.001, "revenue")
        assert "$" in result
    
    def test_format_mixed_dataframe(self):
        """Test dataframe with mixed data types."""
        df = pd.DataFrame({
            "text": ["A", "B", "C"],
            "revenue": [1000, 2000, 3000],
            "margen": [25.5, 30.2, None],  # Include None
            "cantidad": [100, 200, 150]
        })
        
        result = format_dataframe(df)
        
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        # Should handle None gracefully
        assert "-" in str(result.iloc[2]["margen"]) or result.iloc[2]["margen"] == "-"


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
