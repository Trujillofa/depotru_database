"""
Tests for AI package training module.
"""

import sys
import os
import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from business_analyzer.ai.training import (
    get_default_training_examples,
    generate_training_data,
)


class TestTrainingExamples:
    """Test training examples."""

    def test_default_examples_not_empty(self):
        """Test that default examples are not empty."""
        examples = get_default_training_examples()
        assert len(examples) > 0

    def test_default_examples_structure(self):
        """Test that default examples have correct structure."""
        examples = get_default_training_examples()
        for question, sql in examples:
            assert isinstance(question, str)
            assert isinstance(sql, str)
            assert len(question) > 0
            assert len(sql) > 0

    def test_default_examples_contain_sql(self):
        """Test that default examples contain SQL."""
        examples = get_default_training_examples()
        for question, sql in examples:
            assert "SELECT" in sql.upper()


class TestGenerateTrainingData:
    """Test training data generation."""

    def test_generate_training_data_basic(self):
        """Test basic training data generation."""
        data = generate_training_data()
        assert len(data) > 0

    def test_generate_training_data_custom_table(self):
        """Test training data generation with custom table."""
        data = generate_training_data(table_name="custom_table")
        assert len(data) > 0
        # Check that custom table name is used
        for question, sql in data:
            assert "custom_table" in sql

    def test_generate_training_data_without_common_queries(self):
        """Test training data generation without common queries."""
        data = generate_training_data(include_common_queries=False)
        assert len(data) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
