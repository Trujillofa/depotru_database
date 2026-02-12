"""
Database Module for Business Analyzer
======================================
Handles database connections, queries, and credential management.

Supports multiple connection types:
- Direct MSSQL connection
- SSH tunnel connection
- Navicat NCX file connections

Security:
- No hardcoded credentials
- Environment variable configuration
- SQL injection prevention via parameterized queries
"""

from typing import List, Dict, Any, Optional, Union
from enum import Enum
from contextlib import contextmanager
import logging
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, date
from decimal import Decimal

# Database drivers
try:
    import pymssql

    PYMSSQL_AVAILABLE = True
except ImportError:
    PYMSSQL_AVAILABLE = False

try:
    import pyodbc

    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False

# Optional: Navicat cipher decryption
try:
    from NavicatCipher import Navicat12Crypto

    NAVICAT_CIPHER_AVAILABLE = True
except ImportError:
    NAVICAT_CIPHER_AVAILABLE = False

# Optional: AES decryption fallback
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

# Import configuration
try:
    from config import Config
except ImportError:
    # Fallback for when running as part of business_analyzer package
    import sys
    from pathlib import Path

    src_path = Path(__file__).parent.parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from config import Config

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Base exception for database operations"""

    pass


class ConnectionError(DatabaseError):
    """Exception raised when connection fails"""

    pass


class QueryError(DatabaseError):
    """Exception raised when query execution fails"""

    pass


class ConnectionType(Enum):
    """Supported connection types"""

    DIRECT = "direct"
    SSH_TUNNEL = "ssh_tunnel"
    NAVICAT = "navicat"


class Database:
    """
    Database connection manager with support for multiple connection types.

    Usage:
        # Direct connection
        db = Database()
        with db.connect() as conn:
            data = db.execute_query("SELECT * FROM table")

        # Or using context manager for full lifecycle
        with Database() as db:
            data = db.fetch_data(limit=1000)
    """

    def __init__(
        self,
        connection_type: ConnectionType = ConnectionType.DIRECT,
        conn_details: Optional[Dict[str, Any]] = None,
        ncx_file_path: Optional[str] = None,
    ):
        """
        Initialize database connection manager.

        Args:
            connection_type: Type of connection to use
            conn_details: Direct connection details (host, port, user, password, database)
            ncx_file_path: Path to Navicat NCX file for Navicat connections
        """
        self.connection_type = connection_type
        self.conn_details = conn_details or {}
        self.ncx_file_path = ncx_file_path or Config.NCX_FILE_PATH
        self._connection = None
        self._cursor = None

        # Validate drivers are available
        if not PYMSSQL_AVAILABLE and not PYODBC_AVAILABLE:
            raise ImportError(
                "No database driver available. Install pymssql or pyodbc."
            )

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures connection is closed"""
        self.close()
        return False

    def _get_connection_details(self) -> Dict[str, Any]:
        """
        Get connection details based on connection type.

        Returns:
            Dictionary with connection parameters
        """
        if self.connection_type == ConnectionType.NAVICAT:
            return self._load_navicat_connection()
        elif self.connection_type == ConnectionType.DIRECT:
            return self._get_direct_connection_details()
        elif self.connection_type == ConnectionType.SSH_TUNNEL:
            return self._get_ssh_connection_details()
        else:
            raise ConnectionError(
                f"Unsupported connection type: {self.connection_type}"
            )

    def _get_direct_connection_details(self) -> Dict[str, Any]:
        """Get direct connection details from environment or provided config"""
        if self.conn_details:
            return self.conn_details

        # Use Config for environment-based credentials
        if not Config.has_direct_db_config():
            raise ConnectionError(
                "No direct database configuration found. "
                "Set DB_HOST, DB_USER, DB_PASSWORD environment variables."
            )

        return {
            "Host": Config.DB_HOST,
            "Port": Config.DB_PORT,
            "UserName": Config.DB_USER,
            "Password": Config.DB_PASSWORD,
            "Database": Config.DB_NAME,
        }

    def _get_ssh_connection_details(self) -> Dict[str, Any]:
        """
        Get SSH tunnel connection details.

        Note: SSH tunnel implementation would require paramiko or similar.
        This is a placeholder for future implementation.
        """
        raise ConnectionError(
            "SSH tunnel connection not yet implemented. "
            "Use direct connection or configure SSH tunnel externally."
        )

    def _load_navicat_connection(self) -> Dict[str, Any]:
        """
        Load connection details from Navicat NCX file.

        Returns:
            Dictionary with connection parameters
        """
        if not os.path.exists(self.ncx_file_path):
            raise ConnectionError(f"Navicat NCX file not found: {self.ncx_file_path}")

        connections = self._parse_ncx_file(self.ncx_file_path)
        if not connections:
            raise ConnectionError(
                f"No valid connections found in NCX file: {self.ncx_file_path}"
            )

        # Return first connection (could be extended to select by name)
        return connections[0]

    @staticmethod
    def _parse_ncx_file(file_path: str) -> List[Dict[str, Any]]:
        """
        Parse Navicat NCX file and extract connection details.

        Args:
            file_path: Path to NCX file

        Returns:
            List of connection dictionaries
        """
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            connections = []

            for conn in root.findall("Connection"):
                host = conn.get("Host")
                user = conn.get("UserName")
                encrypted_password = conn.get("Password")

                if not all([host, user, encrypted_password]):
                    continue

                try:
                    password = Database._decrypt_navicat_password(encrypted_password)
                except Exception as e:
                    logger.error(f"Failed to decrypt password: {e}")
                    continue

                port = conn.get("Port", "1433")
                database = conn.get("Database", "master")

                connections.append(
                    {
                        "Host": host,
                        "Port": int(port),
                        "UserName": user,
                        "Password": password,
                        "Database": database,
                    }
                )

            return connections
        except Exception as e:
            logger.error(f"Error loading NCX file: {e}")
            return []

    @staticmethod
    def _decrypt_navicat_password(encrypted_password: str) -> str:
        """
        Decrypt password encrypted by Navicat.

        Args:
            encrypted_password: Encrypted password string

        Returns:
            Decrypted password

        Raises:
            ImportError: If no decryption method is available
        """
        if NAVICAT_CIPHER_AVAILABLE:
            try:
                crypto = Navicat12Crypto()
                decrypted = crypto.DecryptStringForNCX(encrypted_password)
                return decrypted
            except Exception as e:
                logger.warning(f"NavicatCipher decryption failed: {e}")

        if CRYPTO_AVAILABLE:
            try:
                key = b"libcckeylibcckey"
                iv = b"libcciv libcciv "
                encrypted_bytes = bytes.fromhex(encrypted_password)
                cipher = AES.new(key, AES.MODE_CBC, iv)
                decrypted = unpad(cipher.decrypt(encrypted_bytes), AES.block_size)
                return decrypted.decode("utf-8")
            except Exception as e:
                logger.warning(f"AES decryption failed: {e}")

        raise ImportError(
            "No decryption method available. Install NavicatCipher or pycryptodome."
        )

    def connect(self) -> "Database":
        """
        Establish database connection.

        Returns:
            Self for method chaining

        Raises:
            ConnectionError: If connection fails
        """
        if self._connection is not None:
            logger.warning("Connection already established")
            return self

        conn_details = self._get_connection_details()

        # Log only non-sensitive info
        host = conn_details.get("Host")
        port = conn_details.get("Port")
        database = conn_details.get("Database", Config.DB_NAME)
        logger.info(f"Connecting to database at {host}:{port}/{database}")

        try:
            if PYMSSQL_AVAILABLE:
                self._connection = pymssql.connect(
                    server=conn_details["Host"],
                    port=conn_details["Port"],
                    user=conn_details["UserName"],
                    password=conn_details["Password"],
                    database=database,
                    login_timeout=Config.DB_LOGIN_TIMEOUT,
                    timeout=Config.DB_TIMEOUT,
                    tds_version=Config.DB_TDS_VERSION,
                )
            elif PYODBC_AVAILABLE:
                # ODBC connection string
                conn_str = (
                    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                    f"SERVER={conn_details['Host']},{conn_details['Port']};"
                    f"DATABASE={database};"
                    f"UID={conn_details['UserName']};"
                    f"PWD={conn_details['Password']};"
                    f"LoginTimeout={Config.DB_LOGIN_TIMEOUT};"
                )
                self._connection = pyodbc.connect(conn_str)
            else:
                raise ConnectionError("No database driver available")

            logger.info("✓ Connected to database successfully")

            # Test connection
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            logger.info(f"DB connection test: {result}")
            cursor.close()

        except Exception as e:
            self._connection = None
            if "timeout" in str(e).lower():
                raise ConnectionError(f"Database connection timeout: {e}")
            raise ConnectionError(f"Failed to connect to database: {e}")

        return self

    def close(self):
        """Close database connection safely"""
        if self._connection:
            try:
                self._connection.close()
                logger.info("✓ Database connection closed safely")
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
            finally:
                self._connection = None
                self._cursor = None

    def is_connected(self) -> bool:
        """Check if database connection is active"""
        return self._connection is not None

    @staticmethod
    def validate_sql_identifier(identifier: str, param_name: str) -> str:
        """
        Validate and sanitize SQL identifier (table name, database name, column name).

        This prevents SQL injection by ensuring identifiers only contain safe characters.
        SQL identifiers should only contain alphanumeric characters, underscores, and hyphens.

        Args:
            identifier: The SQL identifier to validate
            param_name: Parameter name for error messages

        Returns:
            The validated identifier

        Raises:
            ValueError: If identifier contains unsafe characters
        """
        if not identifier:
            raise ValueError(f"{param_name} cannot be empty")

        # SQL identifiers should only contain: letters, numbers, underscores, hyphens
        if not re.match(r"^[a-zA-Z0-9_-]+$", identifier):
            raise ValueError(
                f"Invalid {param_name}: '{identifier}'. "
                f"SQL identifiers can only contain letters, numbers, underscores, and hyphens."
            )

        # Additional length check
        if len(identifier) > 128:
            raise ValueError(
                f"{param_name} is too long ({len(identifier)} characters). "
                f"Maximum is 128 characters."
            )

        return identifier

    def execute_query(
        self, query: str, params: Optional[tuple] = None, fetch: bool = True
    ) -> Union[List[Dict[str, Any]], int]:
        """
        Execute a SQL query with optional parameters.

        Args:
            query: SQL query string (use %s for parameters)
            params: Query parameters (tuple)
            fetch: Whether to fetch results (for SELECT queries)

        Returns:
            List of dictionaries for SELECT queries, row count for others

        Raises:
            QueryError: If query execution fails
            ConnectionError: If not connected
        """
        if not self._connection:
            raise ConnectionError("Not connected to database. Call connect() first.")

        try:
            cursor = (
                self._connection.cursor(as_dict=True)
                if PYMSSQL_AVAILABLE
                else self._connection.cursor()
            )

            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)

            if fetch:
                if PYMSSQL_AVAILABLE:
                    results = list(cursor)
                else:
                    # pyodbc returns tuples, convert to dicts
                    columns = (
                        [desc[0] for desc in cursor.description]
                        if cursor.description
                        else []
                    )
                    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                cursor.close()
                return results
            else:
                rowcount = cursor.rowcount
                self._connection.commit()
                cursor.close()
                return rowcount

        except Exception as e:
            raise QueryError(f"Query execution failed: {e}")

    def fetch_data(
        self,
        table: Optional[str] = None,
        limit: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        excluded_codes: Optional[List[str]] = None,
        columns: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch data from database with filtering options.

        Args:
            table: Table name (defaults to Config.DB_TABLE)
            limit: Maximum number of records
            start_date: Start date filter (YYYY-MM-DD)
            end_date: End date filter (YYYY-MM-DD)
            excluded_codes: List of document codes to exclude
            columns: Specific columns to fetch (None for all)

        Returns:
            List of dictionaries containing query results
        """
        if limit is None:
            limit = Config.DEFAULT_LIMIT

        # Validate identifiers
        db_name = self.validate_sql_identifier(Config.DB_NAME, "database name")
        table_name = self.validate_sql_identifier(
            table or Config.DB_TABLE, "table name"
        )

        # Validate excluded codes
        excluded_codes = excluded_codes or Config.EXCLUDED_DOCUMENT_CODES
        for code in excluded_codes:
            self.validate_sql_identifier(code, "excluded document code")

        # Build query
        if columns:
            col_str = ", ".join(
                [self.validate_sql_identifier(c, "column") for c in columns]
            )
        else:
            col_str = "*"

        # Handle exclusions with parameterized query
        if excluded_codes:
            placeholders = ", ".join(["%s"] * len(excluded_codes))
            query = f"SELECT TOP %s {col_str} FROM [{db_name}].[dbo].[{table_name}] WHERE DocumentosCodigo NOT IN ({placeholders})"
            params = [limit] + list(excluded_codes)
        else:
            query = f"SELECT TOP %s {col_str} FROM [{db_name}].[dbo].[{table_name}]"
            params = [limit]

        # Add date filters
        if start_date and end_date:
            query += " AND Fecha BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        elif start_date:
            query += " AND Fecha >= %s"
            params.append(start_date)
        elif end_date:
            query += " AND Fecha <= %s"
            params.append(end_date)

        logger.info(f"Fetching data from {table_name} (limit: {limit})")
        results = self.execute_query(query, tuple(params))
        logger.info(f"✓ Fetched {len(results)} rows successfully")

        return results

    def get_columns(self, table: Optional[str] = None) -> List[str]:
        """
        Get column names for a table.

        Args:
            table: Table name (defaults to Config.DB_TABLE)

        Returns:
            List of column names
        """
        table_name = self.validate_sql_identifier(
            table or Config.DB_TABLE, "table name"
        )
        db_name = self.validate_sql_identifier(Config.DB_NAME, "database name")

        query = f"SELECT TOP 0 * FROM [{db_name}].[dbo].[{table_name}]"
        cursor = self._connection.cursor()
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        cursor.close()

        return columns


# Convenience functions for backward compatibility


def get_db_connection(
    connection_type: str = "direct", conn_details: Optional[Dict[str, Any]] = None
) -> Database:
    """
    Get database connection (backward compatible).

    Args:
        connection_type: 'direct', 'ssh_tunnel', or 'navicat'
        conn_details: Optional connection details

    Returns:
        Database instance (connected)
    """
    conn_type = ConnectionType(connection_type)
    db = Database(connection_type=conn_type, conn_details=conn_details)
    return db.connect()


def load_connections(file_path: str) -> List[Dict[str, Any]]:
    """
    Load connections from Navicat NCX file (backward compatible).

    Args:
        file_path: Path to NCX file

    Returns:
        List of connection dictionaries
    """
    return Database._parse_ncx_file(file_path)


def decrypt_navicat_password(encrypted_password: str) -> str:
    """
    Decrypt Navicat password (backward compatible).

    Args:
        encrypted_password: Encrypted password

    Returns:
        Decrypted password
    """
    return Database._decrypt_navicat_password(encrypted_password)


def validate_sql_identifier(identifier: str, param_name: str) -> str:
    """
    Validate SQL identifier (backward compatible).

    Args:
        identifier: SQL identifier to validate
        param_name: Parameter name for error messages

    Returns:
        Validated identifier
    """
    return Database.validate_sql_identifier(identifier, param_name)
