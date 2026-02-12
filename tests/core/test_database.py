"""
Comprehensive Unit Tests for Database Module
============================================

Tests cover:
- Database class initialization
- Connection type detection (direct, ssh, navicat)
- SQL injection prevention (validate_sql_identifier)
- Query building with parameters
- Error handling
- Context manager functionality

All tests use mocking - no real database connection required.
"""

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, Mock, mock_open, patch

import pytest

# Setup path and mocks BEFORE importing business_analyzer
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Mock external dependencies BEFORE importing business_analyzer
sys.modules["pymssql"] = Mock()
sys.modules["pyodbc"] = Mock()
sys.modules["NavicatCipher"] = Mock()
sys.modules["Crypto"] = Mock()
sys.modules["Crypto.Cipher"] = Mock()
sys.modules["Crypto.Util"] = Mock()
sys.modules["Crypto.Util.Padding"] = Mock()

# Create and inject mock config module BEFORE importing business_analyzer
mock_config_module = Mock()
mock_config_module.Config = Mock()
mock_config_module.Config.DB_HOST = "test-host"
mock_config_module.Config.DB_PORT = 1433
mock_config_module.Config.DB_USER = "test-user"
mock_config_module.Config.DB_PASSWORD = "test-password"
mock_config_module.Config.DB_NAME = "TestDB"
mock_config_module.Config.DB_TABLE = "test_table"
mock_config_module.Config.NCX_FILE_PATH = "/test/connections.ncx"
mock_config_module.Config.DB_LOGIN_TIMEOUT = 10
mock_config_module.Config.DB_TIMEOUT = 10
mock_config_module.Config.DB_TDS_VERSION = "7.4"
mock_config_module.Config.DEFAULT_LIMIT = 1000
mock_config_module.Config.EXCLUDED_DOCUMENT_CODES = ["XY", "AS"]
mock_config_module.Config.has_direct_db_config = Mock(return_value=True)
mock_config_module.Config.ensure_output_dir = Mock(return_value=Path("/tmp"))
sys.modules["config"] = mock_config_module

# Now import the database module - this MUST be after all the mocks are in place
from business_analyzer.core.database import (
    ConnectionError,
    ConnectionType,
    Database,
    DatabaseError,
    QueryError,
    decrypt_navicat_password,
    get_db_connection,
    load_connections,
    validate_sql_identifier,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_config():
    """Mock Config class with test values"""
    with patch("business_analyzer.core.database.Config") as mock_cfg:
        mock_cfg.DB_HOST = "test-host"
        mock_cfg.DB_PORT = 1433
        mock_cfg.DB_USER = "test-user"
        mock_cfg.DB_PASSWORD = "test-password"
        mock_cfg.DB_NAME = "TestDB"
        mock_cfg.DB_TABLE = "test_table"
        mock_cfg.NCX_FILE_PATH = "/test/connections.ncx"
        mock_cfg.DB_LOGIN_TIMEOUT = 10
        mock_cfg.DB_TIMEOUT = 10
        mock_cfg.DB_TDS_VERSION = "7.4"
        mock_cfg.DEFAULT_LIMIT = 1000
        mock_cfg.EXCLUDED_DOCUMENT_CODES = ["XY", "AS"]
        mock_cfg.has_direct_db_config.return_value = True
        yield mock_cfg


@pytest.fixture
def mock_pymssql():
    """Mock pymssql module"""
    with patch("business_analyzer.core.database.pymssql") as mock:
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock.connect.return_value = mock_conn
        yield mock


@pytest.fixture
def mock_pyodbc():
    """Mock pyodbc module"""
    with patch("business_analyzer.core.database.pyodbc") as mock:
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value = mock_cursor
        mock.connect.return_value = mock_conn
        yield mock


@pytest.fixture
def sample_conn_details():
    """Sample connection details for testing"""
    return {
        "Host": "test-server",
        "Port": 1433,
        "UserName": "testuser",
        "Password": "testpass",
        "Database": "TestDB",
    }


# =============================================================================
# Database Class Initialization Tests
# =============================================================================


class TestDatabaseInitialization:
    """Test Database class initialization with various configurations"""

    def test_init_default_connection_type(self, mock_config):
        """Test initialization with default connection type (DIRECT)"""
        db = Database()
        assert db.connection_type == ConnectionType.DIRECT
        assert db.conn_details == {}
        assert db.ncx_file_path == "/test/connections.ncx"
        assert db._connection is None
        assert db._cursor is None

    def test_init_with_explicit_connection_type(self, mock_config):
        """Test initialization with explicit connection type"""
        db = Database(connection_type=ConnectionType.NAVICAT)
        assert db.connection_type == ConnectionType.NAVICAT

    def test_init_with_connection_details(self, mock_config, sample_conn_details):
        """Test initialization with provided connection details"""
        db = Database(conn_details=sample_conn_details)
        assert db.conn_details == sample_conn_details

    def test_init_with_ncx_file_path(self, mock_config):
        """Test initialization with custom NCX file path"""
        custom_path = "/custom/path.ncx"
        db = Database(ncx_file_path=custom_path)
        assert db.ncx_file_path == custom_path

    def test_init_no_drivers_available(self, mock_config):
        """Test initialization fails when no drivers available"""
        with patch("business_analyzer.core.database.PYMSSQL_AVAILABLE", False):
            with patch("business_analyzer.core.database.PYODBC_AVAILABLE", False):
                with pytest.raises(ImportError, match="No database driver available"):
                    Database()

    def test_init_with_ssh_tunnel_type(self, mock_config):
        """Test initialization with SSH tunnel type"""
        db = Database(connection_type=ConnectionType.SSH_TUNNEL)
        assert db.connection_type == ConnectionType.SSH_TUNNEL


# =============================================================================
# Connection Type Detection Tests
# =============================================================================


class TestConnectionTypeDetection:
    """Test connection type detection and handling"""

    def test_get_connection_details_direct(self, mock_config, sample_conn_details):
        """Test getting connection details for direct connection"""
        db = Database(
            connection_type=ConnectionType.DIRECT, conn_details=sample_conn_details
        )
        details = db._get_connection_details()
        assert details == sample_conn_details

    def test_get_connection_details_direct_from_config(self, mock_config):
        """Test getting direct connection details from Config"""
        db = Database(connection_type=ConnectionType.DIRECT)
        details = db._get_connection_details()
        assert details["Host"] == "test-host"
        assert details["Port"] == 1433
        assert details["UserName"] == "test-user"
        assert details["Password"] == "test-password"
        assert details["Database"] == "TestDB"

    def test_get_connection_details_direct_no_config(self, mock_config):
        """Test direct connection fails when no config available"""
        mock_config.has_direct_db_config.return_value = False
        db = Database(connection_type=ConnectionType.DIRECT)
        with pytest.raises(
            ConnectionError, match="No direct database configuration found"
        ):
            db._get_connection_details()

    def test_get_connection_details_ssh_not_implemented(self, mock_config):
        """Test SSH tunnel raises not implemented error"""
        db = Database(connection_type=ConnectionType.SSH_TUNNEL)
        with pytest.raises(
            ConnectionError, match="SSH tunnel connection not yet implemented"
        ):
            db._get_connection_details()

    def test_get_connection_details_navicat(self, mock_config):
        """Test getting connection details from Navicat NCX file"""
        db = Database(connection_type=ConnectionType.NAVICAT)

        with patch.object(db, "_load_navicat_connection") as mock_load:
            mock_load.return_value = {
                "Host": "navicat-host",
                "Port": 1433,
                "UserName": "navicat-user",
                "Password": "navicat-pass",
                "Database": "NavicatDB",
            }
            details = db._get_connection_details()
            assert details["Host"] == "navicat-host"

    def test_get_connection_details_unsupported_type(self, mock_config):
        """Test unsupported connection type raises error"""
        db = Database()
        # Manually set invalid type
        db.connection_type = "invalid"
        with pytest.raises(ConnectionError, match="Unsupported connection type"):
            db._get_connection_details()


# =============================================================================
# Navicat NCX File Tests
# =============================================================================


class TestNavicatNCX:
    """Test Navicat NCX file parsing and password decryption"""

    def test_load_navicat_connection_file_not_found(self, mock_config):
        """Test loading NCX file that doesn't exist"""
        db = Database(
            connection_type=ConnectionType.NAVICAT, ncx_file_path="/nonexistent.ncx"
        )
        with pytest.raises(ConnectionError, match="Navicat NCX file not found"):
            db._load_navicat_connection()

    def test_load_navicat_connection_no_valid_connections(self, mock_config):
        """Test loading NCX file with no valid connections"""
        db = Database(connection_type=ConnectionType.NAVICAT)

        with patch("os.path.exists", return_value=True):
            with patch.object(Database, "_parse_ncx_file", return_value=[]):
                with pytest.raises(ConnectionError, match="No valid connections found"):
                    db._load_navicat_connection()

    def test_parse_ncx_file_success(self, mock_config):
        """Test parsing valid NCX file"""
        with patch("xml.etree.ElementTree.parse") as mock_parse:
            mock_tree = Mock()
            mock_root = Mock()

            # Create mock connection elements
            conn1 = Mock()
            conn1.get.side_effect = lambda key: {
                "Host": "server1",
                "UserName": "user1",
                "Password": "encrypted1",
                "Port": "1433",
                "Database": "db1",
            }.get(key)

            conn2 = Mock()
            conn2.get.side_effect = lambda key: {
                "Host": "server2",
                "UserName": "user2",
                "Password": "encrypted2",
                "Port": "1433",
                "Database": "db2",
            }.get(key)

            mock_root.findall.return_value = [conn1, conn2]
            mock_tree.getroot.return_value = mock_root
            mock_parse.return_value = mock_tree

            with patch.object(
                Database, "_decrypt_navicat_password", return_value="decrypted"
            ):
                connections = Database._parse_ncx_file("/test.ncx")
                assert len(connections) == 2
                assert connections[0]["Host"] == "server1"
                assert connections[1]["Host"] == "server2"

    def test_parse_ncx_file_missing_fields(self, mock_config):
        """Test parsing NCX file with incomplete connection data"""
        with patch("xml.etree.ElementTree.parse") as mock_parse:
            mock_tree = Mock()
            mock_root = Mock()

            # Connection missing required fields
            conn = Mock()
            conn.get.side_effect = lambda key: {
                "Host": "server1",
                "UserName": None,  # Missing
                "Password": "encrypted1",
            }.get(key)

            mock_root.findall.return_value = [conn]
            mock_tree.getroot.return_value = mock_root
            mock_parse.return_value = mock_tree

            connections = Database._parse_ncx_file("/test.ncx")
            assert len(connections) == 0  # Should skip incomplete connections

    def test_parse_ncx_file_decrypt_error(self, mock_config):
        """Test parsing NCX file with decryption error"""
        with patch("xml.etree.ElementTree.parse") as mock_parse:
            mock_tree = Mock()
            mock_root = Mock()

            conn = Mock()
            conn.get.side_effect = lambda key: {
                "Host": "server1",
                "UserName": "user1",
                "Password": "encrypted1",
                "Port": "1433",
                "Database": "db1",
            }.get(key)

            mock_root.findall.return_value = [conn]
            mock_tree.getroot.return_value = mock_root
            mock_parse.return_value = mock_tree

            with patch.object(
                Database,
                "_decrypt_navicat_password",
                side_effect=Exception("Decrypt failed"),
            ):
                connections = Database._parse_ncx_file("/test.ncx")
                assert (
                    len(connections) == 0
                )  # Should skip connections with decrypt errors

    def test_parse_ncx_file_parse_error(self, mock_config):
        """Test parsing invalid NCX file"""
        with patch("xml.etree.ElementTree.parse", side_effect=Exception("Parse error")):
            connections = Database._parse_ncx_file("/test.ncx")
            assert connections == []

    def test_decrypt_navicat_password_with_navicat_cipher(self, mock_config):
        """Test password decryption using NavicatCipher"""
        with patch("business_analyzer.core.database.NAVICAT_CIPHER_AVAILABLE", True):
            with patch(
                "business_analyzer.core.database.Navicat12Crypto"
            ) as mock_crypto:
                mock_instance = Mock()
                mock_instance.DecryptStringForNCX.return_value = "decrypted_password"
                mock_crypto.return_value = mock_instance

                result = Database._decrypt_navicat_password("encrypted")
                assert result == "decrypted_password"

    def test_decrypt_navicat_password_with_crypto_fallback(self, mock_config):
        """Test password decryption using pycryptodome fallback"""
        with patch("business_analyzer.core.database.NAVICAT_CIPHER_AVAILABLE", False):
            with patch("business_analyzer.core.database.CRYPTO_AVAILABLE", True):
                with patch("business_analyzer.core.database.AES") as mock_aes:
                    with patch("business_analyzer.core.database.unpad") as mock_unpad:
                        mock_cipher = Mock()
                        mock_cipher.decrypt.return_value = b"padded_password"
                        mock_aes.new.return_value = mock_cipher
                        mock_unpad.return_value = b"decrypted_password"

                        result = Database._decrypt_navicat_password(
                            "656e63727970746564"
                        )  # hex for 'encrypted'
                        assert result == "decrypted_password"

    def test_decrypt_navicat_password_no_method_available(self, mock_config):
        """Test password decryption fails when no method available"""
        with patch("business_analyzer.core.database.NAVICAT_CIPHER_AVAILABLE", False):
            with patch("business_analyzer.core.database.CRYPTO_AVAILABLE", False):
                with pytest.raises(ImportError, match="No decryption method available"):
                    Database._decrypt_navicat_password("encrypted")


# =============================================================================
# SQL Injection Prevention Tests
# =============================================================================


class TestSQLInjectionPrevention:
    """Test SQL injection prevention via validate_sql_identifier"""

    def test_validate_sql_identifier_valid(self):
        """Test valid SQL identifiers pass validation"""
        valid_identifiers = [
            "table_name",
            "TableName",
            "table123",
            "table_123",
            "table-name",
            "TABLE_NAME",
            "a",
            "A1_b2-c3",
        ]
        for identifier in valid_identifiers:
            result = Database.validate_sql_identifier(identifier, "test_param")
            assert result == identifier

    def test_validate_sql_identifier_empty(self):
        """Test empty identifier raises error"""
        with pytest.raises(ValueError, match="cannot be empty"):
            Database.validate_sql_identifier("", "table_name")

    def test_validate_sql_identifier_none(self):
        """Test None identifier raises error"""
        with pytest.raises(ValueError, match="cannot be empty"):
            Database.validate_sql_identifier(None, "table_name")

    def test_validate_sql_identifier_invalid_characters(self):
        """Test identifiers with invalid characters raise error"""
        invalid_identifiers = [
            "table;name",  # Semicolon
            "table name",  # Space
            "table\nname",  # Newline
            "table\tname",  # Tab
            "table.name",  # Dot
            "table/name",  # Slash
            "table\\name",  # Backslash
            "table'name",  # Quote
            'table"name',  # Double quote
            "table`name",  # Backtick
            "table$name",  # Dollar sign
            "table@name",  # At sign
            "table#name",  # Hash
            "table!name",  # Exclamation
            "table%name",  # Percent
            "table*name",  # Asterisk
            "table(name)",  # Parentheses
            "table[name]",  # Brackets
            "table{name}",  # Braces
            "table<name>",  # Angle brackets
            "table+name",  # Plus
            "table=name",  # Equals
            "table?name",  # Question mark
            "table&name",  # Ampersand
            "table|name",  # Pipe
            "table^name",  # Caret
            "table~name",  # Tilde
        ]
        for identifier in invalid_identifiers:
            with pytest.raises(ValueError, match="Invalid test_param"):
                Database.validate_sql_identifier(identifier, "test_param")

    def test_validate_sql_identifier_too_long(self):
        """Test identifier exceeding 128 characters raises error"""
        long_identifier = "a" * 129
        with pytest.raises(ValueError, match="too long"):
            Database.validate_sql_identifier(long_identifier, "table_name")

    def test_validate_sql_identifier_exactly_128_chars(self):
        """Test identifier with exactly 128 characters passes"""
        identifier = "a" * 128
        result = Database.validate_sql_identifier(identifier, "table_name")
        assert result == identifier

    def test_validate_sql_identifier_sql_injection_attempts(self):
        """Test common SQL injection patterns are blocked"""
        injection_attempts = [
            "users; DROP TABLE users;--",
            "users' OR '1'='1",
            "users' UNION SELECT * FROM passwords--",
            "users; INSERT INTO users VALUES ('hacker', 'pass')--",
            "users; DELETE FROM users WHERE '1'='1",
            "users; UPDATE users SET password='hacked'--",
        ]
        for attempt in injection_attempts:
            with pytest.raises(ValueError, match="Invalid"):
                Database.validate_sql_identifier(attempt, "table_name")


# =============================================================================
# Connection and Query Tests
# =============================================================================


class TestDatabaseConnection:
    """Test database connection establishment and management"""

    def test_connect_success_pymssql(self, mock_config, mock_pymssql):
        """Test successful connection using pymssql"""
        db = Database(connection_type=ConnectionType.DIRECT)
        result = db.connect()

        assert result is db  # Returns self for chaining
        assert db.is_connected()
        assert db._connection is not None
        mock_pymssql.connect.assert_called_once()

    def test_connect_success_pyodbc(self, mock_config, mock_pyodbc):
        """Test successful connection using pyodbc when pymssql unavailable"""
        with patch("business_analyzer.core.database.PYMSSQL_AVAILABLE", False):
            with patch("business_analyzer.core.database.PYODBC_AVAILABLE", True):
                db = Database(connection_type=ConnectionType.DIRECT)
                result = db.connect()

                assert result is db
                assert db.is_connected()
                mock_pyodbc.connect.assert_called_once()

    def test_connect_already_connected(self, mock_config, mock_pymssql):
        """Test connecting when already connected logs warning"""
        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        # Second connect should return early
        result = db.connect()
        assert result is db
        # Should only call connect once
        assert mock_pymssql.connect.call_count == 1

    def test_connect_failure(self, mock_config, mock_pymssql):
        """Test connection failure raises ConnectionError"""
        mock_pymssql.connect.side_effect = Exception("Connection refused")

        db = Database(connection_type=ConnectionType.DIRECT)
        with pytest.raises(ConnectionError, match="Failed to connect to database"):
            db.connect()

        assert not db.is_connected()
        assert db._connection is None

    def test_connect_timeout(self, mock_config, mock_pymssql):
        """Test connection timeout raises specific error"""
        mock_pymssql.connect.side_effect = Exception("Connection timeout")

        db = Database(connection_type=ConnectionType.DIRECT)
        with pytest.raises(ConnectionError, match="Database connection timeout"):
            db.connect()

    def test_close_connection(self, mock_config, mock_pymssql):
        """Test closing database connection"""
        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        db.close()

        assert not db.is_connected()
        assert db._connection is None
        assert db._cursor is None
        mock_pymssql.connect.return_value.close.assert_called_once()

    def test_close_not_connected(self, mock_config):
        """Test closing when not connected doesn't error"""
        db = Database(connection_type=ConnectionType.DIRECT)
        db.close()  # Should not raise
        assert not db.is_connected()

    def test_close_with_error(self, mock_config, mock_pymssql):
        """Test close handles errors gracefully"""
        mock_pymssql.connect.return_value.close.side_effect = Exception("Close error")

        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()
        db.close()  # Should not raise despite error

        assert not db.is_connected()


# =============================================================================
# Query Execution Tests
# =============================================================================


class TestQueryExecution:
    """Test query execution with parameters"""

    def test_execute_query_not_connected(self, mock_config):
        """Test executing query without connection raises error"""
        db = Database(connection_type=ConnectionType.DIRECT)
        with pytest.raises(ConnectionError, match="Not connected to database"):
            db.execute_query("SELECT * FROM table")

    def test_execute_query_select_pymssql(self, mock_config, mock_pymssql):
        """Test SELECT query execution with pymssql"""
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(
            return_value=iter([{"id": 1, "name": "Test"}, {"id": 2, "name": "Test2"}])
        )
        mock_pymssql.connect.return_value.cursor.return_value = mock_cursor

        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        results = db.execute_query("SELECT * FROM table")

        assert len(results) == 2
        assert results[0]["id"] == 1
        mock_cursor.execute.assert_called_once_with("SELECT * FROM table", None)

    def test_execute_query_with_params(self, mock_config, mock_pymssql):
        """Test query execution with parameters"""
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(return_value=iter([]))
        mock_pymssql.connect.return_value.cursor.return_value = mock_cursor

        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        db.execute_query("SELECT * FROM table WHERE id = %s", (1,))

        mock_cursor.execute.assert_called_once_with(
            "SELECT * FROM table WHERE id = %s", (1,)
        )

    def test_execute_query_insert(self, mock_config, mock_pymssql):
        """Test INSERT query execution (no fetch)"""
        mock_cursor = Mock()
        mock_cursor.rowcount = 5
        mock_pymssql.connect.return_value.cursor.return_value = mock_cursor

        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        result = db.execute_query(
            "INSERT INTO table VALUES (%s)", ("value",), fetch=False
        )

        assert result == 5  # Row count
        mock_cursor.execute.assert_called_once()
        mock_pymssql.connect.return_value.commit.assert_called_once()

    def test_execute_query_error(self, mock_config, mock_pymssql):
        """Test query execution error raises QueryError"""
        mock_cursor = Mock()
        mock_cursor.execute.side_effect = Exception("Query failed")
        mock_pymssql.connect.return_value.cursor.return_value = mock_cursor

        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        with pytest.raises(QueryError, match="Query execution failed"):
            db.execute_query("SELECT * FROM table")

    def test_execute_query_pyodbc(self, mock_config, mock_pyodbc):
        """Test query execution with pyodbc"""
        with patch("business_analyzer.core.database.PYMSSQL_AVAILABLE", False):
            with patch("business_analyzer.core.database.PYODBC_AVAILABLE", True):
                mock_cursor = Mock()
                mock_cursor.description = [("id",), ("name",)]
                mock_cursor.fetchall.return_value = [(1, "Test"), (2, "Test2")]
                mock_pyodbc.connect.return_value.cursor.return_value = mock_cursor

                db = Database(connection_type=ConnectionType.DIRECT)
                db.connect()

                results = db.execute_query("SELECT * FROM table")

                assert len(results) == 2
                assert results[0] == {"id": 1, "name": "Test"}


# =============================================================================
# Context Manager Tests
# =============================================================================


class TestContextManager:
    """Test context manager functionality"""

    def test_context_manager_enter(self, mock_config, mock_pymssql):
        """Test context manager entry connects to database"""
        with Database(connection_type=ConnectionType.DIRECT) as db:
            assert db.is_connected()
            assert isinstance(db, Database)

    def test_context_manager_exit_closes(self, mock_config, mock_pymssql):
        """Test context manager exit closes connection"""
        db = None
        with Database(connection_type=ConnectionType.DIRECT) as db:
            pass

        assert not db.is_connected()

    def test_context_manager_exception(self, mock_config, mock_pymssql):
        """Test context manager handles exceptions properly"""
        db = None
        try:
            with Database(connection_type=ConnectionType.DIRECT) as db:
                assert db.is_connected()
                raise ValueError("Test exception")
        except ValueError:
            pass

        assert not db.is_connected()

    def test_context_manager_returns_false(self, mock_config, mock_pymssql):
        """Test context manager __exit__ returns False (doesn't suppress exceptions)"""
        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        result = db.__exit__(None, None, None)
        assert result is False


# =============================================================================
# Fetch Data Tests
# =============================================================================


class TestFetchData:
    """Test fetch_data method with various parameters"""

    def test_fetch_data_basic(self, mock_config, mock_pymssql):
        """Test basic data fetching"""
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(return_value=iter([{"id": 1}, {"id": 2}]))
        mock_pymssql.connect.return_value.cursor.return_value = mock_cursor

        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        results = db.fetch_data(table="test_table", limit=10)

        assert len(results) == 2
        mock_cursor.execute.assert_called_once()

    def test_fetch_data_with_excluded_codes(self, mock_config, mock_pymssql):
        """Test fetching with excluded document codes"""
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(return_value=iter([]))
        mock_pymssql.connect.return_value.cursor.return_value = mock_cursor

        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        db.fetch_data(table="test_table", limit=10, excluded_codes=["XY", "AB"])

        call_args = mock_cursor.execute.call_args
        assert "NOT IN" in call_args[0][0]
        assert "%s" in call_args[0][0]

    def test_fetch_data_with_date_range(self, mock_config, mock_pymssql):
        """Test fetching with date range filters"""
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(return_value=iter([]))
        mock_pymssql.connect.return_value.cursor.return_value = mock_cursor

        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        db.fetch_data(
            table="test_table",
            limit=10,
            start_date="2024-01-01",
            end_date="2024-12-31",
        )

        call_args = mock_cursor.execute.call_args
        assert "BETWEEN" in call_args[0][0]

    def test_fetch_data_with_start_date_only(self, mock_config, mock_pymssql):
        """Test fetching with only start date"""
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(return_value=iter([]))
        mock_pymssql.connect.return_value.cursor.return_value = mock_cursor

        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        db.fetch_data(table="test_table", limit=10, start_date="2024-01-01")

        call_args = mock_cursor.execute.call_args
        assert ">=" in call_args[0][0]

    def test_fetch_data_with_end_date_only(self, mock_config, mock_pymssql):
        """Test fetching with only end date"""
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(return_value=iter([]))
        mock_pymssql.connect.return_value.cursor.return_value = mock_cursor

        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        db.fetch_data(table="test_table", limit=10, end_date="2024-12-31")

        call_args = mock_cursor.execute.call_args
        assert "<=" in call_args[0][0]

    def test_fetch_data_with_columns(self, mock_config, mock_pymssql):
        """Test fetching specific columns"""
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(return_value=iter([]))
        mock_pymssql.connect.return_value.cursor.return_value = mock_cursor

        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        db.fetch_data(table="test_table", limit=10, columns=["id", "name", "date"])

        call_args = mock_cursor.execute.call_args
        assert "id, name, date" in call_args[0][0]

    def test_fetch_data_invalid_table_name(self, mock_config, mock_pymssql):
        """Test fetching with invalid table name raises error"""
        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        with pytest.raises(ValueError, match="Invalid table name"):
            db.fetch_data(table="table; DROP TABLE users;--")

    def test_fetch_data_invalid_column_name(self, mock_config, mock_pymssql):
        """Test fetching with invalid column name raises error"""
        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        with pytest.raises(ValueError, match="Invalid column"):
            db.fetch_data(
                table="test_table", columns=["id", "name; DROP TABLE users;--"]
            )


# =============================================================================
# Get Columns Tests
# =============================================================================


class TestGetColumns:
    """Test get_columns method"""

    def test_get_columns_success(self, mock_config, mock_pymssql):
        """Test getting column names"""
        mock_cursor = Mock()
        mock_cursor.description = [("id",), ("name",), ("date",)]
        mock_pymssql.connect.return_value.cursor.return_value = mock_cursor

        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        columns = db.get_columns(table="test_table")

        assert columns == ["id", "name", "date"]
        mock_cursor.execute.assert_called_once()

    def test_get_columns_not_connected(self, mock_config):
        """Test get_columns when not connected"""
        db = Database(connection_type=ConnectionType.DIRECT)

        with pytest.raises(ConnectionError, match="Not connected to database"):
            db.get_columns(table="test_table")

    def test_get_columns_invalid_table(self, mock_config, mock_pymssql):
        """Test get_columns with invalid table name"""
        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        with pytest.raises(ValueError, match="Invalid table name"):
            db.get_columns(table="table; DROP TABLE users;--")


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


class TestBackwardCompatibility:
    """Test backward compatible functions"""

    def test_get_db_connection(self, mock_config, mock_pymssql):
        """Test get_db_connection convenience function"""
        db = get_db_connection(connection_type="direct")

        assert isinstance(db, Database)
        assert db.is_connected()

    def test_get_db_connection_ssh(self, mock_config):
        """Test get_db_connection with SSH type"""
        with pytest.raises(
            ConnectionError, match="SSH tunnel connection not yet implemented"
        ):
            get_db_connection(connection_type="ssh_tunnel")

    def test_load_connections(self, mock_config):
        """Test load_connections convenience function"""
        with patch.object(
            Database, "_parse_ncx_file", return_value=[{"Host": "test"}]
        ) as mock_parse:
            connections = load_connections("/test.ncx")

            assert len(connections) == 1
            mock_parse.assert_called_once_with("/test.ncx")

    def test_decrypt_navicat_password_compat(self, mock_config):
        """Test decrypt_navicat_password convenience function"""
        with patch.object(
            Database, "_decrypt_navicat_password", return_value="decrypted"
        ) as mock_decrypt:
            result = decrypt_navicat_password("encrypted")

            assert result == "decrypted"
            mock_decrypt.assert_called_once_with("encrypted")

    def test_validate_sql_identifier_compat(self):
        """Test validate_sql_identifier convenience function"""
        result = validate_sql_identifier("valid_table", "table_name")
        assert result == "valid_table"


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_connection_details_with_string_port(self, mock_config, mock_pymssql):
        """Test connection handles string port from NCX file"""
        with patch("xml.etree.ElementTree.parse") as mock_parse:
            mock_tree = Mock()
            mock_root = Mock()

            conn = Mock()
            conn.get.side_effect = lambda key: {
                "Host": "server1",
                "UserName": "user1",
                "Password": "encrypted1",
                "Port": "1433",  # String port
                "Database": "db1",
            }.get(key)

            mock_root.findall.return_value = [conn]
            mock_tree.getroot.return_value = mock_root
            mock_parse.return_value = mock_tree

            with patch.object(
                Database, "_decrypt_navicat_password", return_value="decrypted"
            ):
                connections = Database._parse_ncx_file("/test.ncx")
                assert connections[0]["Port"] == 1433  # Should be converted to int

    def test_fetch_data_default_limit(self, mock_config, mock_pymssql):
        """Test fetch_data uses default limit from Config"""
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(return_value=iter([]))
        mock_pymssql.connect.return_value.cursor.return_value = mock_cursor

        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        db.fetch_data(table="test_table")  # No limit specified

        call_args = mock_cursor.execute.call_args
        assert "TOP %s" in call_args[0][0]
        assert 1000 in call_args[0][1]  # Default limit from Config

    def test_fetch_data_empty_excluded_codes(self, mock_config, mock_pymssql):
        """Test fetch_data with empty excluded codes list"""
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(return_value=iter([]))
        mock_pymssql.connect.return_value.cursor.return_value = mock_cursor

        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        db.fetch_data(table="test_table", limit=10, excluded_codes=[])

        call_args = mock_cursor.execute.call_args
        assert "NOT IN" not in call_args[0][0]  # Should not have WHERE clause

    def test_execute_query_no_results(self, mock_config, mock_pymssql):
        """Test execute_query with no results"""
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(return_value=iter([]))
        mock_pymssql.connect.return_value.cursor.return_value = mock_cursor

        db = Database(connection_type=ConnectionType.DIRECT)
        db.connect()

        results = db.execute_query("SELECT * FROM empty_table")

        assert results == []

    def test_execute_query_pyodbc_no_description(self, mock_config, mock_pyodbc):
        """Test pyodbc query with no description (no results)"""
        with patch("business_analyzer.core.database.PYMSSQL_AVAILABLE", False):
            with patch("business_analyzer.core.database.PYODBC_AVAILABLE", True):
                mock_cursor = Mock()
                mock_cursor.description = None
                mock_cursor.fetchall.return_value = []
                mock_pyodbc.connect.return_value.cursor.return_value = mock_cursor

                db = Database(connection_type=ConnectionType.DIRECT)
                db.connect()

                results = db.execute_query("SELECT * FROM empty_table")

                assert results == []


# =============================================================================
# Integration-style Tests
# =============================================================================


class TestIntegration:
    """Integration-style tests for complete workflows"""

    def test_full_workflow_context_manager(self, mock_config, mock_pymssql):
        """Test complete workflow using context manager"""
        mock_cursor = Mock()
        mock_cursor.__iter__ = Mock(
            return_value=iter(
                [{"id": 1, "name": "Product A"}, {"id": 2, "name": "Product B"}]
            )
        )
        mock_pymssql.connect.return_value.cursor.return_value = mock_cursor

        with Database(connection_type=ConnectionType.DIRECT) as db:
            # Get columns
            mock_cursor.description = [("id",), ("name",)]
            columns = db.get_columns(table="products")
            assert columns == ["id", "name"]

            # Fetch data
            mock_cursor.__iter__ = Mock(
                return_value=iter(
                    [
                        {"id": 1, "name": "Product A"},
                        {"id": 2, "name": "Product B"},
                    ]
                )
            )
            data = db.fetch_data(table="products", limit=10)
            assert len(data) == 2

            # Execute custom query
            mock_cursor.__iter__ = Mock(return_value=iter([{"count": 100}]))
            result = db.execute_query("SELECT COUNT(*) as count FROM products")
            assert result[0]["count"] == 100

        # Verify connection closed
        assert not db.is_connected()

    def test_navicat_workflow(self, mock_config, mock_pymssql):
        """Test complete Navicat connection workflow"""
        with patch("os.path.exists", return_value=True):
            with patch("xml.etree.ElementTree.parse") as mock_parse:
                mock_tree = Mock()
                mock_root = Mock()

                conn = Mock()
                conn.get.side_effect = lambda key: {
                    "Host": "navicat-server",
                    "UserName": "navicat-user",
                    "Password": "encrypted123",
                    "Port": "1433",
                    "Database": "NavicatDB",
                }.get(key)

                mock_root.findall.return_value = [conn]
                mock_tree.getroot.return_value = mock_root
                mock_parse.return_value = mock_tree

                with patch.object(
                    Database, "_decrypt_navicat_password", return_value="decrypted_pass"
                ):
                    with Database(
                        connection_type=ConnectionType.NAVICAT,
                        ncx_file_path="/test.ncx",
                    ) as db:
                        assert db.is_connected()
                        # Verify connection was made with correct credentials
                        call_kwargs = mock_pymssql.connect.call_args[1]
                        assert call_kwargs["server"] == "navicat-server"
                        assert call_kwargs["user"] == "navicat-user"
                        assert call_kwargs["password"] == "decrypted_pass"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
