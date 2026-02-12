"""
Basic Repository Tests
======================
Simple tests to verify the repository structure and basic functionality.
These tests don't require external dependencies.
"""

from pathlib import Path

import pytest


class TestRepositoryStructure:
    """Test repository structure and files."""

    def test_readme_exists(self):
        """Test that README.md exists."""
        repo_root = Path(__file__).parent.parent
        readme = repo_root / "README.md"
        assert readme.exists(), "README.md should exist"
        assert readme.is_file(), "README.md should be a file"

    def test_requirements_exists(self):
        """Test that requirements.txt exists."""
        repo_root = Path(__file__).parent.parent
        requirements = repo_root / "requirements.txt"
        assert requirements.exists(), "requirements.txt should exist"
        assert requirements.is_file(), "requirements.txt should be a file"

    def test_src_directory_exists(self):
        """Test that src directory exists."""
        repo_root = Path(__file__).parent.parent
        src = repo_root / "src"
        assert src.exists(), "src directory should exist"
        assert src.is_dir(), "src should be a directory"

    def test_tests_directory_exists(self):
        """Test that tests directory exists."""
        repo_root = Path(__file__).parent.parent
        tests = repo_root / "tests"
        assert tests.exists(), "tests directory should exist"
        assert tests.is_dir(), "tests should be a directory"

    def test_docs_directory_exists(self):
        """Test that docs directory exists."""
        repo_root = Path(__file__).parent.parent
        docs = repo_root / "docs"
        assert docs.exists(), "docs directory should exist"
        assert docs.is_dir(), "docs should be a directory"

    def test_env_example_exists(self):
        """Test that .env.example exists."""
        repo_root = Path(__file__).parent.parent
        env_example = repo_root / ".env.example"
        assert env_example.exists(), ".env.example should exist"
        assert env_example.is_file(), ".env.example should be a file"


class TestBasicPythonFunctionality:
    """Test basic Python functionality without external dependencies."""

    def test_basic_math(self):
        """Test basic mathematical operations."""
        assert 1 + 1 == 2
        assert 10 / 2 == 5
        assert 5 * 5 == 25

    def test_string_operations(self):
        """Test basic string operations."""
        assert "hello".upper() == "HELLO"
        assert "WORLD".lower() == "world"
        assert "hello world".split() == ["hello", "world"]

    def test_list_operations(self):
        """Test basic list operations."""
        my_list = [1, 2, 3]
        assert len(my_list) == 3
        assert sum(my_list) == 6
        assert max(my_list) == 3
        assert min(my_list) == 1


class TestUtilityFunctions:
    """Test utility functions that don't require dependencies."""

    def test_safe_divide(self):
        """Test safe division function."""

        def safe_divide(a, b, default=0):
            """Safely divide two numbers."""
            try:
                return a / b if b != 0 else default
            except (TypeError, ZeroDivisionError):
                return default

        assert safe_divide(10, 2) == 5
        assert safe_divide(10, 0) == 0
        assert safe_divide(10, 0, default=-1) == -1
        assert safe_divide("invalid", 2) == 0

    def test_calculate_percentage(self):
        """Test percentage calculation."""

        def calculate_percentage(part, total, default=0):
            """Calculate percentage safely."""
            if total == 0:
                return default
            return (part / total) * 100

        assert calculate_percentage(50, 100) == 50.0
        assert calculate_percentage(25, 100) == 25.0
        assert calculate_percentage(100, 100) == 100.0
        assert calculate_percentage(50, 0) == 0

    def test_format_currency(self):
        """Test currency formatting."""

        def format_currency(amount):
            """Format amount as currency."""
            return f"${amount:,.2f}"

        assert format_currency(1000) == "$1,000.00"
        assert format_currency(1000000) == "$1,000,000.00"
        assert format_currency(123.45) == "$123.45"


# =============================================================================
# Test Suite Information
# =============================================================================


def test_pytest_is_working():
    """Verify that pytest is working correctly."""
    assert True, "Pytest is working!"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
