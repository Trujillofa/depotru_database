"""Database Module for Business Analyzer. Handles connections, queries, security."""

import logging
import os
import re

# nosec B405: xml.etree.ElementTree is used for parsing local Navicat NCX files only
# These are trusted configuration files, not external/untrusted XML data
import xml.etree.ElementTree as ET  # nosec B405
from enum import Enum
from typing import Any, Dict, List, Optional, Union

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

try:
    from NavicatCipher import Navicat12Crypto

    NAVICAT_CIPHER_AVAILABLE = True
except ImportError:
    NAVICAT_CIPHER_AVAILABLE = False

try:
    # nosec B413: pyCrypto is deprecated but used as fallback for Navicat password decryption
    # This is acceptable because: 1) It's a fallback only, 2) NavicatCipher is preferred,
    # 3) The encrypted data is from local NCX files, not external/untrusted sources
    from Crypto.Cipher import AES  # nosec B413
    from Crypto.Util.Padding import unpad  # nosec B413

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

try:
    from config import Config
except ImportError:
    import sys
    from pathlib import Path

    src_path = Path(__file__).parent.parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from config import Config

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    pass


class ConnectionError(DatabaseError):
    pass


class QueryError(DatabaseError):
    pass


class ConnectionType(Enum):
    DIRECT = "direct"
    SSH_TUNNEL = "ssh_tunnel"
    NAVICAT = "navicat"


class Database:
    """Database connection manager with multiple connection types."""

    def __init__(
        self,
        connection_type: ConnectionType = ConnectionType.DIRECT,
        conn_details: Optional[Dict[str, Any]] = None,
        ncx_file_path: Optional[str] = None,
    ):
        self.connection_type, self.conn_details, self.ncx_file_path = (
            connection_type,
            conn_details or {},
            ncx_file_path or Config.NCX_FILE_PATH,
        )
        self._connection = None
        if not PYMSSQL_AVAILABLE and not PYODBC_AVAILABLE:
            raise ImportError(
                "No database driver available. Install pymssql or pyodbc."
            )

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()
        return False

    def _get_connection_details(self) -> Dict[str, Any]:
        if self.connection_type == ConnectionType.NAVICAT:
            return self._load_navicat_connection()
        elif self.connection_type == ConnectionType.DIRECT:
            return self._get_direct_connection_details()
        elif self.connection_type == ConnectionType.SSH_TUNNEL:
            raise ConnectionError("SSH tunnel not implemented")
        raise ConnectionError(f"Unsupported connection type: {self.connection_type}")

    def _get_direct_connection_details(self) -> Dict[str, Any]:
        if self.conn_details:
            return self.conn_details
        if not Config.has_direct_db_config():
            raise ConnectionError(
                "No database config. Set DB_HOST, DB_USER, DB_PASSWORD."
            )
        return {
            "Host": Config.DB_HOST,
            "Port": Config.DB_PORT,
            "UserName": Config.DB_USER,
            "Password": Config.DB_PASSWORD,
            "Database": Config.DB_NAME,
        }

    def _load_navicat_connection(self) -> Dict[str, Any]:
        if not os.path.exists(self.ncx_file_path):
            raise ConnectionError(f"NCX file not found: {self.ncx_file_path}")
        connections = self._parse_ncx_file(self.ncx_file_path)
        if not connections:
            raise ConnectionError(
                f"No valid connections in NCX file: {self.ncx_file_path}"
            )
        return connections[0]

    @staticmethod
    def _parse_ncx_file(file_path: str) -> List[Dict[str, Any]]:
        try:
            connections = []
            # nosec B314: Parsing local Navicat NCX config files (trusted source)
            for conn in (
                ET.parse(file_path).getroot().findall("Connection")
            ):  # nosec B314
                host, user, encrypted = (
                    conn.get("Host"),
                    conn.get("UserName"),
                    conn.get("Password"),
                )
                if not all([host, user, encrypted]):
                    continue
                try:
                    password = Database._decrypt_navicat_password(encrypted)
                except Exception as e:
                    logger.error(f"Decrypt failed: {e}")
                    continue
                connections.append(
                    {
                        "Host": host,
                        "Port": int(conn.get("Port", "1433")),
                        "UserName": user,
                        "Password": password,
                        "Database": conn.get("Database", "master"),
                    }
                )
            return connections
        except Exception as e:
            logger.error(f"Error loading NCX: {e}")
            return []

    @staticmethod
    def _decrypt_navicat_password(encrypted: str) -> str:
        if NAVICAT_CIPHER_AVAILABLE:
            try:
                return Navicat12Crypto().DecryptStringForNCX(encrypted)
            except Exception as e:
                logger.warning(f"NavicatCipher failed: {e}")
        if CRYPTO_AVAILABLE:
            try:
                key, iv = b"libcckeylibcckey", b"libcciv libcciv "
                return unpad(
                    AES.new(key, AES.MODE_CBC, iv).decrypt(bytes.fromhex(encrypted)),
                    AES.block_size,
                ).decode("utf-8")
            except Exception as e:
                logger.warning(f"AES failed: {e}")
        raise ImportError("No decryption method available.")

    def connect(self) -> "Database":
        if self._connection:
            logger.warning("Already connected")
            return self
        details = self._get_connection_details()
        host, port, db = (
            details.get("Host"),
            details.get("Port"),
            details.get("Database", Config.DB_NAME),
        )
        logger.info(f"Connecting to {host}:{port}/{db}")
        try:
            if PYMSSQL_AVAILABLE:
                self._connection = pymssql.connect(
                    server=details["Host"],
                    port=details["Port"],
                    user=details["UserName"],
                    password=details["Password"],
                    database=db,
                    login_timeout=Config.DB_LOGIN_TIMEOUT,
                    timeout=Config.DB_TIMEOUT,
                    tds_version=Config.DB_TDS_VERSION,
                )
            elif PYODBC_AVAILABLE:
                self._connection = pyodbc.connect(
                    f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={details['Host']},{details['Port']};DATABASE={db};UID={details['UserName']};PWD={details['Password']};"
                )
            logger.info("✓ Connected successfully")
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1 as test")
            cursor.fetchone()
            cursor.close()
        except Exception as e:
            self._connection = None
            raise ConnectionError(
                f"Connection timeout: {e}"
                if "timeout" in str(e).lower()
                else f"Failed to connect: {e}"
            )
        return self

    def close(self):
        if self._connection:
            try:
                self._connection.close()
                logger.info("✓ Connection closed")
            except Exception as e:
                logger.warning(f"Error closing: {e}")
            finally:
                self._connection = None

    def is_connected(self) -> bool:
        return self._connection is not None

    @staticmethod
    def validate_sql_identifier(identifier: str, param_name: str) -> str:
        if not identifier:
            raise ValueError(f"{param_name} cannot be empty")
        if not re.match(r"^[a-zA-Z0-9_-]+$", identifier):
            raise ValueError(
                f"Invalid {param_name}: '{identifier}'. Only alphanumeric, _, - allowed."
            )
        if len(identifier) > 128:
            raise ValueError(
                f"{param_name} too long ({len(identifier)} chars). Max 128."
            )
        return identifier

    def execute_query(
        self, query: str, params: Optional[tuple] = None, fetch: bool = True
    ) -> Union[List[Dict[str, Any]], int]:
        if not self._connection:
            raise ConnectionError("Not connected. Call connect() first.")
        try:
            cursor = (
                self._connection.cursor(as_dict=True)
                if PYMSSQL_AVAILABLE
                else self._connection.cursor()
            )
            cursor.execute(query, params)
            if fetch:
                results = (
                    list(cursor)
                    if PYMSSQL_AVAILABLE
                    else [
                        dict(zip([d[0] for d in cursor.description], row))
                        for row in cursor.fetchall()
                    ]
                )
                cursor.close()
                return results
            rowcount = cursor.rowcount
            self._connection.commit()
            cursor.close()
            return rowcount
        except Exception as e:
            raise QueryError(f"Query failed: {e}")

    def fetch_data(
        self,
        table: Optional[str] = None,
        limit: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        excluded_codes: Optional[List[str]] = None,
        columns: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        limit = limit or Config.DEFAULT_LIMIT
        db_name = self.validate_sql_identifier(Config.DB_NAME, "database")
        table_name = self.validate_sql_identifier(table or Config.DB_TABLE, "table")
        excluded_codes = excluded_codes or Config.EXCLUDED_DOCUMENT_CODES
        for code in excluded_codes:
            self.validate_sql_identifier(code, "excluded code")
        col_str = (
            ", ".join([self.validate_sql_identifier(c, "column") for c in columns])
            if columns
            else "*"
        )
        if excluded_codes:
            # nosec B608: SQL identifiers validated above with validate_sql_identifier()
            # Parameters use %s placeholders for safe parameterization
            query = f"SELECT TOP %s {col_str} FROM [{db_name}].[dbo].[{table_name}] WHERE DocumentosCodigo NOT IN ({', '.join(['%s'] * len(excluded_codes))})"  # nosec B608
            params = [limit] + list(excluded_codes)
        else:
            # nosec B608: SQL identifiers validated above with validate_sql_identifier()
            query = f"SELECT TOP %s {col_str} FROM [{db_name}].[dbo].[{table_name}]"  # nosec B608
            params = [limit]
        if start_date and end_date:
            query += " AND Fecha BETWEEN %s AND %s"
            params.extend([start_date, end_date])
        elif start_date:
            query += " AND Fecha >= %s"
            params.append(start_date)
        elif end_date:
            query += " AND Fecha <= %s"
            params.append(end_date)
        logger.info(f"Fetching from {table_name} (limit: {limit})")
        results = self.execute_query(query, tuple(params))
        logger.info(f"✓ Fetched {len(results)} rows")
        return results

    def get_columns(self, table: Optional[str] = None) -> List[str]:
        table_name = self.validate_sql_identifier(table or Config.DB_TABLE, "table")
        db_name = self.validate_sql_identifier(Config.DB_NAME, "database")
        cursor = self._connection.cursor()
        # nosec B608: SQL identifiers validated above with validate_sql_identifier()
        cursor.execute(
            f"SELECT TOP 0 * FROM [{db_name}].[dbo].[{table_name}]"
        )  # nosec B608
        columns = [desc[0] for desc in cursor.description]
        cursor.close()
        return columns


# Backward compatibility
def get_db_connection(
    connection_type: str = "direct", conn_details: Optional[Dict[str, Any]] = None
) -> Database:
    return Database(
        connection_type=ConnectionType(connection_type), conn_details=conn_details
    ).connect()


def load_connections(file_path: str) -> List[Dict[str, Any]]:
    return Database._parse_ncx_file(file_path)


def decrypt_navicat_password(encrypted: str) -> str:
    return Database._decrypt_navicat_password(encrypted)


def validate_sql_identifier(identifier: str, param_name: str) -> str:
    return Database.validate_sql_identifier(identifier, param_name)
