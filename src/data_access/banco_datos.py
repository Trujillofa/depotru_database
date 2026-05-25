import logging
from typing import Any, Dict, List, Optional, Tuple

import pymssql

from ..config import Config

logger = logging.getLogger(__name__)


def build_banco_datos_query(
    limit: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[str, Tuple[Any, ...]]:
    excluded_codes = ", ".join([f"'{code}'" for code in Config.EXCLUDED_DOCUMENT_CODES])
    query = (
        f"SELECT TOP %s * FROM [{Config.DB_NAME}].[dbo].[{Config.DB_TABLE}] "
        f"WHERE DocumentosCodigo NOT IN ({excluded_codes})"
    )
    params: List[Any] = [limit]

    if start_date and end_date:
        query += " AND Fecha BETWEEN %s AND %s"
        params.extend([start_date, end_date])
    elif start_date:
        query += " AND Fecha >= %s"
        params.append(start_date)
    elif end_date:
        query += " AND Fecha <= %s"
        params.append(end_date)

    return query, tuple(params)


def fetch_banco_datos(
    conn_details: Dict[str, Any],
    limit: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    if limit is None:
        limit = Config.DEFAULT_LIMIT

    conn: Any = None
    try:
        host = conn_details["Host"]
        port = conn_details["Port"]
        user = conn_details["UserName"]
        password = conn_details["Password"]
        logger.info("Connecting to database at %s:%s", host, port)

        conn = pymssql.connect(
            server=host,
            port=port,
            user=user,
            password=password,
            database=Config.DB_NAME,
            login_timeout=Config.DB_LOGIN_TIMEOUT,
            timeout=Config.DB_TIMEOUT,
            tds_version=Config.DB_TDS_VERSION,
        )

        logger.info("✓ Connected to database successfully")
        cursor = conn.cursor(as_dict=True)

        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()
        logger.info(f"DB connection test: {result}")

        cursor.execute(
            f"SELECT TOP 0 * FROM [{Config.DB_NAME}].[dbo].[{Config.DB_TABLE}]"
        )
        columns = [desc[0] for desc in cursor.description]
        logger.info(f"Columns in {Config.DB_TABLE}: {columns}")

        query, params = build_banco_datos_query(limit, start_date, end_date)
        cursor.execute(query, params)
        data = list(cursor)

        if not data:
            logger.warning(f"No data retrieved from {Config.DB_TABLE}.")
        else:
            logger.info(f"✓ Fetched {len(data)} rows successfully")

        return data

    except pymssql.OperationalError as exc:
        if "timeout" in str(exc).lower():
            logger.error("❌ Database connection timeout. Check network connectivity.")
        else:
            logger.error(f"❌ Database operational error: {exc}")
        raise
    except pymssql.Error as exc:
        logger.error(f"❌ Database error: {exc}")
        raise
    except Exception as exc:
        logger.error(f"❌ Unexpected error: {exc}")
        raise
    finally:
        if conn:
            try:
                conn.close()
                logger.info("✓ Database connection closed safely")
            except Exception as exc:
                logger.warning(f"Error closing connection: {exc}")
