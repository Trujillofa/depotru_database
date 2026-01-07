"""
Test SQL injection prevention measures
"""
import pytest
import sys
sys.path.insert(0, 'src')

from business_analyzer_combined import validate_sql_identifier


class TestSQLInjectionPrevention:
    """Test SQL injection prevention"""

    def test_validate_sql_identifier_valid_names(self):
        """Test that valid SQL identifiers are accepted"""
        valid_names = [
            'SmartBusiness',
            'banco_datos',
            'test_table',
            'MyDatabase',
            'table-name',
            'ABC123',
            'XY',
            'AS',
            'TS'
        ]
        
        for name in valid_names:
            result = validate_sql_identifier(name, 'test')
            assert result == name, f"Valid name '{name}' should be accepted"

    def test_validate_sql_identifier_rejects_injection(self):
        """Test that SQL injection attempts are rejected"""
        injection_attempts = [
            "'; DROP TABLE users--",
            "table; DELETE FROM users",
            "../../../etc/passwd",
            "table\"; DROP TABLE users--",
            "' OR '1'='1",
            "table/*comment*/name",
            "table name",  # space
            "table;name",  # semicolon
            "table'name",  # quote
            'table"name',  # double quote
            "table(name)",  # parentheses
            "table[name]",  # brackets
        ]
        
        for attempt in injection_attempts:
            with pytest.raises(ValueError, match="Invalid.*SQL identifiers"):
                validate_sql_identifier(attempt, 'table')

    def test_validate_sql_identifier_rejects_empty(self):
        """Test that empty identifiers are rejected"""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_sql_identifier('', 'table')

    def test_validate_sql_identifier_rejects_too_long(self):
        """Test that overly long identifiers are rejected"""
        long_name = 'a' * 129  # 129 characters
        with pytest.raises(ValueError, match="too long"):
            validate_sql_identifier(long_name, 'table')

    def test_validate_sql_identifier_max_length_accepted(self):
        """Test that 128 character identifiers are accepted"""
        max_length_name = 'a' * 128
        result = validate_sql_identifier(max_length_name, 'table')
        assert result == max_length_name
