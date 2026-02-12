"""
Tests for AI package initialization and exports.
"""

import sys
import os
import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))


class TestAIPackageImports:
    """Test AI package imports."""

    def test_import_base_classes(self):
        """Test importing base classes."""
        from business_analyzer.ai import (
            AIVanna,
            Config,
            SUPPORTED_PROVIDERS,
            DEFAULT_PROVIDER,
        )

        assert AIVanna is not None
        assert Config is not None
        assert isinstance(SUPPORTED_PROVIDERS, list)
        assert isinstance(DEFAULT_PROVIDER, str)

    def test_import_formatting(self):
        """Test importing formatting functions."""
        from business_analyzer.ai import (
            format_number,
            format_dataframe,
            format_currency,
            format_percentage,
            format_integer,
        )

        assert format_number is not None
        assert format_dataframe is not None
        assert format_currency is not None
        assert format_percentage is not None
        assert format_integer is not None

    def test_import_training(self):
        """Test importing training functions."""
        from business_analyzer.ai import (
            train_on_schema,
            train_with_examples,
            get_default_training_examples,
            generate_training_data,
            full_training,
        )

        assert train_on_schema is not None
        assert train_with_examples is not None
        assert get_default_training_examples is not None
        assert generate_training_data is not None
        assert full_training is not None

    def test_import_insights(self):
        """Test importing insights function."""
        from business_analyzer.ai import generate_insights

        assert generate_insights is not None

    def test_import_providers(self):
        """Test importing providers."""
        from business_analyzer.ai import (
            GrokProvider,
            OpenAIProvider,
            AnthropicProvider,
            OllamaProvider,
        )

        assert GrokProvider is not None
        assert OpenAIProvider is not None
        assert AnthropicProvider is not None
        assert OllamaProvider is not None

    def test_import_factory(self):
        """Test importing factory function."""
        from business_analyzer.ai import create_vanna_instance

        assert create_vanna_instance is not None

    def test_version(self):
        """Test package version."""
        from business_analyzer.ai import __version__

        assert isinstance(__version__, str)
        assert len(__version__) > 0


class TestFactoryFunction:
    """Test factory function."""

    def test_factory_function_exists(self):
        """Test that factory function exists."""
        from business_analyzer.ai import create_vanna_instance

        assert callable(create_vanna_instance)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
