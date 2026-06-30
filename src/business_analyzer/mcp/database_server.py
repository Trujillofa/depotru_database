#!/usr/bin/env python3
"""
MCP Server for Database Access (Reusable MSSQL / SmartBusiness-style)

This provides a Model Context Protocol (MCP) stdio server exposing safe,
reusable tools for querying Microsoft SQL Server databases.

It reuses the battle-tested connection logic, NCX support, validation,
and dual-DB (SmartBusiness + J3System) helpers from the Business Analyzer.

Intended use:
- For this project: optional sidecar for agents that prefer tool-calling over
  raw NL2SQL or direct Python imports.
- For *other instances*: drop-in generic MSSQL MCP server. Configure via the
  same DB_* / NCX_FILE_PATH environment variables. It works with any MSSQL
  schema (the SmartBusiness-specific helpers are optional conveniences).

Run (recommended, no global install required):
    uv run --with-editable . --with mcp python -m business_analyzer.mcp.database_server

Or after `pip install -e ".[mcp]"`:
    python -m business_analyzer.mcp.database_server

Register example (in ~/.grok/config.toml or <repo>/.grok/config.toml):
    [mcp_servers.depotru-database]
    command = "uv"
    args = ["run", "--with-editable", ".", "--with", "mcp", "python", "-m", "business_analyzer.mcp.database_server"]
    env = { DB_HOST = "...", DB_USER = "...", ... }   # or rely on .env / NCX_FILE_PATH
    enabled = true

Tools exposed (namespaced as depotru-database__<tool> when configured as "depotru-database"):
- query
- list_tables
- describe_table
- query_smartbusiness (auto-injects common DocumentosCodigo exclusion, now with full safety checks)
- health (ping with config info)

Security notes:
- In default read-only mode: ONLY SELECT and WITH (CTEs) are allowed.
  EXEC/EXECUTE is **completely blocked** even in read-only mode because
  it can invoke xp_cmdshell and other OS command execution stored procedures.
- When ALLOW_WRITE=1: EXEC/EXECUTE is allowed (still subject to dangerous
  statement blocks).
- All identifiers are validated (same rules as the core Database class).
- Queries are parameterized where possible.
- No DDL/DML by default (read-only bias). Can be relaxed with ALLOW_WRITE=1.

This server is intentionally generic so it can be reused across different
MSSQL-based BI/ERP projects.
"""

import asyncio
import atexit
import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make the package importable when run directly or via uv run --with-editable
if str(Path(__file__).resolve().parents[3]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
if str(Path(__file__).resolve().parents[2] / "src") not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

# Lazy import of MCP SDK so that "import business_analyzer.mcp" or the package
# can succeed even if the user only installed the core (non-mcp) extras.
_mcp_available = False
try:
    import mcp.types as types
    from mcp.server import Server
    from mcp.server.stdio import stdio_server

    _mcp_available = True
except ImportError:
    Server = None  # type: ignore
    stdio_server = None  # type: ignore
    types = None  # type: ignore

# Reuse the project's robust Database layer (NCX, validation, pooling, J3 helper, etc.)
try:
    from business_analyzer.core.database import Config as CoreConfig
    from business_analyzer.core.database import ConnectionType, Database

    LegacyConfig = None
    try:
        from business_analyzer.core.config import Config as LegacyConfig
    except Exception:
        pass  # Legacy config optional; core.database already provides Config
except (ImportError, ModuleNotFoundError) as import_err:
    print(
        f"WARNING: Could not import business_analyzer.core.database ({import_err}).",
        file=sys.stderr,
    )
    print(
        "Falling back to minimal standalone DB helper (limited NCX/J3 support).",
        file=sys.stderr,
    )
    Database = None  # type: ignore
    ConnectionType = None  # type: ignore
    CoreConfig = None
    LegacyConfig = None

# ---------------------------------------------------------------------------
# Configuration (same spirit as the main project)
# ---------------------------------------------------------------------------


def _get_db_config() -> Dict[str, Any]:
    """Collect connection info from environment (mirrors the main app)."""
    return {
        "host": os.getenv("DB_HOST") or os.getenv("DB_SERVER"),
        "port": int(os.getenv("DB_PORT", os.getenv("DB_PORT", 1433))),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_NAME", "SmartBusiness"),
        "j3_database": os.getenv("DB_NAME_J3SYSTEM", "J3System"),
        "ncx_file": os.getenv("NCX_FILE_PATH"),
        "encrypt": os.getenv("DB_ENCRYPT", "no").lower() in ("1", "true", "yes"),
        "timeout": int(os.getenv("DB_TIMEOUT", "180")),
    }


def _is_write_allowed() -> bool:
    return os.getenv("ALLOW_WRITE", "0").lower() in ("1", "true", "yes")


def _is_safe_sql(sql: str) -> bool:
    """Very conservative safety check.

    In read-only mode (default): only allows SELECT and WITH (CTEs).
    EXEC/EXECUTE is blocked entirely in read-only mode because it can invoke
    xp_cmdshell and other dangerous stored procedures (OS command injection risk).

    Stacked queries using ; (e.g. SELECT 1; EXEC xp_cmdshell ...) are rejected
    in read-only mode to prevent bypass.

    When ALLOW_WRITE=1, EXEC/EXECUTE and ; are permitted (still subject to
    dangerous statement blocks).
    """
    if not sql or not sql.strip():
        return False
    s = sql.strip().lower()
    # Block obvious dangerous statements (DDL/DML) unless write explicitly allowed
    dangerous = (
        "drop ",
        "delete ",
        "update ",
        "insert ",
        "alter ",
        "create ",
        "truncate ",
        "grant ",
        "revoke ",
    )
    if any(d in s for d in dangerous):
        if not _is_write_allowed():
            return False

    write_allowed = _is_write_allowed()

    # P0: Block stacked queries (semicolon bypass) in read-only mode.
    # Legitimate single-statement SELECTs for this use case do not require
    # top-level ; (internal ; in procs/strings are rare at top level for our queries).
    # MSSQL procs handle their own.
    if not write_allowed:
        stripped = sql.strip().rstrip(";").strip()
        if ";" in stripped:
            return False

    # Allowed starts
    if s.startswith("select") or s.startswith("with"):
        return True
    # EXEC/EXECUTE only in write mode (security: prevents xp_cmdshell etc.)
    if write_allowed and (s.startswith("exec ") or s.startswith("execute ")):
        return True
    return False


# ---------------------------------------------------------------------------
# Database helper (prefers the rich project implementation)
# ---------------------------------------------------------------------------


def _get_database(target_db: Optional[str] = None) -> Any:
    """Return a connected Database instance or a minimal fallback.

    Reuses per-thread Database instances when the rich project layer is available.
    Includes basic retry for transient connection errors (M-1).
    """
    import time

    from business_analyzer.core.db_factory import get_database as factory_get_database

    cfg = _get_db_config()
    max_retries = 2
    backoff = 0.5

    last_err = None
    for attempt in range(max_retries + 1):
        try:
            if Database is not None:
                conn_type = ConnectionType.DIRECT if ConnectionType else "direct"
                if cfg["ncx_file"] and os.path.exists(cfg["ncx_file"]):
                    return factory_get_database(
                        target_db=target_db,
                        reuse=True,
                        connection_type=conn_type,
                        ncx_file_path=cfg["ncx_file"],
                    )
                details = {
                    "Host": cfg["host"],
                    "Port": cfg["port"],
                    "UserName": cfg["user"],
                    "Password": cfg["password"],
                    "Database": target_db or cfg["database"],
                }
                return factory_get_database(
                    target_db=target_db,
                    reuse=True,
                    connection_type=conn_type,
                    conn_details=details,
                )

            # Fallback
            import pymssql  # type: ignore

            db_name = target_db or cfg["database"]
            conn = pymssql.connect(
                server=cfg["host"],
                user=cfg["user"],
                password=cfg["password"],
                database=db_name,
                port=str(cfg["port"]),
                tds_version="7.4",
            )
            return conn

        except Exception as e:
            last_err = e
            if attempt < max_retries:
                jitter = random.uniform(0, 0.5)
                time.sleep(backoff * (2**attempt) + jitter)
            else:
                raise RuntimeError(
                    f"Failed to connect after {max_retries+1} attempts: {e}"
                ) from last_err
    raise last_err  # type: ignore


def _execute_on_db(
    db: Any, sql: str, params: Optional[tuple] = None
) -> List[Dict[str, Any]]:
    """Execute and return list of dict rows. Works with both rich Database and raw pymssql."""
    if Database is not None and isinstance(db, Database):
        # The project's execute_query already returns list[dict] for pymssql
        return db.execute_query(sql, params)  # type: ignore

    # Raw pymssql fallback
    cursor = db.cursor(as_dict=True)
    cursor.execute(sql, params or ())
    rows = list(cursor)
    cursor.close()
    return rows


def _close_db(db: Any):
    """No-op for pooled/reused Database instances; closes raw pymssql fallback."""
    if Database is not None and isinstance(db, Database):
        return
    try:
        db.close()
    except Exception:
        pass


# Query timeout (seconds). Prevents long-running queries from hanging the MCP server.
_raw_to = os.getenv("DB_QUERY_TIMEOUT") or os.getenv("DB_QUERY_TIMEOUT_SEC") or "60"
QUERY_TIMEOUT_SEC = int(_raw_to) if int(_raw_to) > 0 else 60

# Module-level executor to avoid creating new ThreadPool per query (H-1 resource leak under concurrent calls)
# Limited workers for MCP tool concurrency
_executor = ThreadPoolExecutor(max_workers=4)

# Simple in-memory rate limiter for MCP tools (M-NEW-3) to prevent runaway agent hammering DB
# Thread-safe with Lock (M2)
_rate_limit: dict = {}
_rate_limit_lock = threading.Lock()
_RATE_LIMIT_WINDOW = 1.0  # seconds
_MAX_CALLS_PER_WINDOW = 20


def _shutdown_executor():
    from business_analyzer.core.db_factory import release_thread_connections

    release_thread_connections()
    _executor.shutdown(wait=True)


atexit.register(_shutdown_executor)


def _execute_on_db_with_timeout(
    db: Any, sql: str, params: Optional[tuple] = None
) -> List[Dict[str, Any]]:
    """Execute query with timeout protection."""
    timeout = QUERY_TIMEOUT_SEC
    future = _executor.submit(_execute_on_db, db, sql, params)
    try:
        return future.result(timeout=timeout)
    except FuturesTimeout:
        # Best effort cancel (may not kill the DB query, but releases the thread)
        future.cancel()
        raise TimeoutError(
            f"Query timed out after {timeout} seconds (set DB_QUERY_TIMEOUT to increase)"
        )


# ---------------------------------------------------------------------------
# MCP Server Definition (lazily constructed inside main() so the module can
# be imported without the optional "mcp" extra).
# ---------------------------------------------------------------------------


def _build_server():
    """Construct the MCP server and register all tools. Only called when we actually start the MCP process."""
    if not _mcp_available or Server is None:
        raise RuntimeError(
            "MCP SDK not available. Install with: pip install mcp (or use 'uv --with mcp ...')"
        )

    srv = Server("depotru-database-mcp")

    @srv.list_tools()
    async def list_tools() -> List[types.Tool]:
        tools = [
            types.Tool(
                name="query",
                description=(
                    "Execute a read-oriented SQL query against the configured MSSQL instance. "
                    "Supports both SmartBusiness and J3System via the 'database' parameter. "
                    "Queries are validated for basic safety."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "The SQL to execute (SELECT/WITH preferred)",
                        },
                        "database": {
                            "type": "string",
                            "description": "Target database name (e.g. 'SmartBusiness' or 'J3System'). Defaults to DB_NAME env.",
                            "default": None,
                        },
                        "params": {
                            "type": "array",
                            "items": {"type": ["string", "number", "boolean", "null"]},
                            "description": "Optional parameters for parameterized query (recommended).",
                            "default": None,
                        },
                    },
                    "required": ["sql"],
                },
            ),
            types.Tool(
                name="list_tables",
                description="List tables in the target database (useful for schema exploration).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "database": {
                            "type": "string",
                            "description": "Target database",
                            "default": None,
                        },
                        "schema": {
                            "type": "string",
                            "description": "Schema filter (default: dbo)",
                            "default": "dbo",
                        },
                    },
                },
            ),
            types.Tool(
                name="describe_table",
                description="Return column metadata for a table (name, type, nullable, etc.).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "table": {
                            "type": "string",
                            "description": "Table name (without schema)",
                        },
                        "database": {
                            "type": "string",
                            "description": "Target database",
                            "default": None,
                        },
                        "schema": {"type": "string", "default": "dbo"},
                    },
                    "required": ["table"],
                },
            ),
            types.Tool(
                name="query_smartbusiness",
                description=(
                    "Convenience wrapper for SmartBusiness. Automatically injects the common "
                    "DocumentosCodigo exclusion (XY, AS, TS, etc.) used throughout the project. "
                    "Great for ad-hoc sales queries without forgetting the filter."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "sql": {
                            "type": "string",
                            "description": "Base SELECT ... FROM banco_datos ... (the exclusion will be added if missing)",
                        },
                        "params": {
                            "type": "array",
                            "items": {"type": ["string", "number"]},
                            "default": None,
                        },
                    },
                    "required": ["sql"],
                },
            ),
            types.Tool(
                name="health",
                description="Lightweight health check / ping for MCP clients and monitoring. Does not require DB connectivity.",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]
        return tools

    return srv


def _normalize_database(db_name: Optional[str]) -> str:
    if not db_name:
        cfg = _get_db_config()
        return cfg["database"]
    if db_name.lower() in ("j3", "j3system", "j3_system"):
        cfg = _get_db_config()
        return cfg["j3_database"]
    return db_name


def _register_tools(srv):
    """Register all call_tool handlers on the given server instance."""

    @srv.call_tool()
    async def call_tool(
        name: str, arguments: Dict[str, Any]
    ) -> List[types.TextContent]:
        # M-NEW-3: basic rate limiting - thread safe (M2)
        now = time.time()
        with _rate_limit_lock:
            calls = _rate_limit.get(name, [])
            calls = [t for t in calls if now - t < _RATE_LIMIT_WINDOW]
            if len(calls) >= _MAX_CALLS_PER_WINDOW:
                raise ValueError(
                    f"Rate limit exceeded for tool '{name}'. Please slow down requests."
                )
            calls.append(now)
            _rate_limit[name] = calls

        try:
            if name == "query":
                sql: str = arguments["sql"]
                db_name = _normalize_database(arguments.get("database"))
                params = tuple(arguments.get("params") or ())

                if not _is_safe_sql(sql):
                    raise ValueError(
                        "Query rejected for safety. Only SELECT/WITH/EXEC allowed unless ALLOW_WRITE=1."
                    )

                db = _get_database(db_name)
                try:
                    rows = _execute_on_db_with_timeout(db, sql, params)
                    original_count = len(rows)
                    limit = 500
                    truncated = original_count > limit
                    if truncated:
                        rows = rows[:limit]
                    return [
                        types.TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "rows": rows,
                                    "row_count": len(rows),
                                    "original_row_count": original_count,
                                    "truncated": truncated,
                                    "limit": limit,
                                    "note": (
                                        "Result truncated to first 500 rows"
                                        if truncated
                                        else None
                                    ),
                                },
                                default=str,
                                indent=2,
                            ),
                        )
                    ]
                finally:
                    _close_db(db)

            elif name == "list_tables":
                db_name = _normalize_database(arguments.get("database"))
                schema = arguments.get("schema", "dbo")
                db = _get_database(db_name)
                try:
                    sql = """
                        SELECT TABLE_NAME
                        FROM INFORMATION_SCHEMA.TABLES
                        WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_SCHEMA = %s
                        ORDER BY TABLE_NAME
                    """
                    rows = _execute_on_db_with_timeout(db, sql, (schema,))
                    tables = [r.get("TABLE_NAME") or r.get("table_name") for r in rows]
                    return [
                        types.TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "database": db_name,
                                    "schema": schema,
                                    "tables": tables,
                                }
                            ),
                        )
                    ]
                finally:
                    _close_db(db)

            elif name == "describe_table":
                table = arguments["table"]
                db_name = _normalize_database(arguments.get("database"))
                schema = arguments.get("schema", "dbo")
                # M-NEW-4: validate table (and schema) identifier to prevent injection
                if Database is not None:
                    table = Database.validate_sql_identifier(table, "table")
                    if schema:
                        schema = Database.validate_sql_identifier(schema, "schema")
                db = _get_database(db_name)
                try:
                    sql = """
                        SELECT
                            COLUMN_NAME as name,
                            DATA_TYPE as type,
                            IS_NULLABLE as nullable,
                            CHARACTER_MAXIMUM_LENGTH as max_length,
                            COLUMN_DEFAULT as default_value
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                        ORDER BY ORDINAL_POSITION
                    """
                    rows = _execute_on_db_with_timeout(db, sql, (schema, table))
                    # Normalize for consistency (M-5)
                    normalized = []
                    for r in rows:
                        normalized.append(
                            {
                                "name": r.get("name") or r.get("COLUMN_NAME"),
                                "type": r.get("type") or r.get("DATA_TYPE"),
                                "nullable": (
                                    r.get("nullable") or r.get("IS_NULLABLE") or "YES"
                                ).upper()
                                == "YES",
                                "max_length": r.get("max_length")
                                or r.get("CHARACTER_MAXIMUM_LENGTH"),
                                "default": r.get("default_value")
                                or r.get("COLUMN_DEFAULT"),
                            }
                        )
                    return [
                        types.TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "database": db_name,
                                    "table": f"{schema}.{table}",
                                    "columns": normalized,
                                },
                                default=str,
                                indent=2,
                            ),
                        )
                    ]
                finally:
                    _close_db(db)

            elif name == "query_smartbusiness":
                base_sql: str = arguments["sql"]
                params = tuple(arguments.get("params") or ())
                excluded = getattr(
                    CoreConfig, "EXCLUDED_DOCUMENT_CODES", None
                ) or getattr(
                    LegacyConfig,
                    "EXCLUDED_DOCUMENT_CODES",
                    ["XY", "AS", "TS", "YX", "ISC"],
                )

                # CRITICAL: must call safety check to prevent bypass (C-NEW-1)
                if not _is_safe_sql(base_sql):
                    raise ValueError(
                        "Query rejected for safety. Only SELECT/WITH/EXEC allowed unless ALLOW_WRITE=1."
                    )

                sql_lower = base_sql.lower()
                applied = False
                note = "SmartBusiness common document filter was applied where appropriate."

                if "documentoscodigo" not in sql_lower and "banco_datos" in sql_lower:
                    # H-2: strip comments and strings before clause detection to avoid false negatives
                    def _sanitize_for_clause_check(s: str) -> str:
                        # remove -- line comments
                        s = re.sub(r"--.*?(?:\n|$)", " ", s, flags=re.MULTILINE)
                        # remove /* */ block comments
                        s = re.sub(r"/\*.*?\*/", " ", s, flags=re.DOTALL)
                        # M1: improved string stripping for MSSQL:
                        # - optional N prefix for unicode strings N'...'
                        # - handle ''' (triple quote edge, e.g. 'foo''\'bar' or literal ''')
                        # - roughly handle doubled quotes
                        s = re.sub(r"(?i:N)?'(?:''|[^'])*(?:'(?!'))?", "'__STR__'", s)
                        # replace double-quoted identifiers (optional N too, though rare)
                        s = re.sub(r'(?i:N)?"(?:""|[^"])*(?:"(?!"))?', '"__ID__"', s)
                        return " " + s.lower() + " "

                    sanitized = _sanitize_for_clause_check(base_sql)
                    # Check for clauses that would make blind WHERE append produce invalid SQL
                    complex_clauses = [
                        " group by ",
                        " order by ",
                        " having ",
                        " limit ",
                    ]
                    has_complex = any(c in sanitized for c in complex_clauses)

                    if has_complex:
                        note = (
                            "Complex query with GROUP BY/ORDER BY/HAVING/LIMIT detected. "
                            "Auto-injection skipped to avoid invalid SQL. "
                            "Include 'AND DocumentosCodigo NOT IN (...)' yourself in the WHERE clause."
                        )
                    else:
                        base_sql = base_sql.rstrip().rstrip(";")
                        if "where" in sql_lower:
                            inject = f" AND DocumentosCodigo NOT IN ({', '.join(['%s'] * len(excluded))})"
                            base_sql = base_sql + inject
                        else:
                            inject = f" WHERE DocumentosCodigo NOT IN ({', '.join(['%s'] * len(excluded))})"
                            base_sql = base_sql + inject
                        params = params + tuple(excluded)
                        applied = True

                db = _get_database("SmartBusiness")
                try:
                    rows = _execute_on_db_with_timeout(db, base_sql, params)
                    original_count = len(rows)
                    limit = 500
                    truncated = original_count > limit
                    if truncated:
                        rows = rows[:limit]
                    return [
                        types.TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "rows": rows,
                                    "row_count": len(rows),
                                    "original_row_count": original_count,
                                    "truncated": truncated,
                                    "limit": limit,
                                    "applied_excludes": excluded if applied else [],
                                    "note": note,
                                },
                                default=str,
                                indent=2,
                            ),
                        )
                    ]
                finally:
                    _close_db(db)

            elif name == "health":
                cfg = _get_db_config()
                return [
                    types.TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "status": "ok",
                                "server": "depotru-database-mcp",
                                "primary_database": cfg["database"],
                                "j3_database": cfg["j3_database"],
                                "write_mode": _is_write_allowed(),
                                "query_timeout_sec": QUERY_TIMEOUT_SEC,
                            }
                        ),
                    )
                ]

            else:
                raise ValueError(f"Unknown tool: {name}")

        except Exception as e:
            return [
                types.TextContent(
                    type="text", text=json.dumps({"error": str(e), "tool": name})
                )
            ]


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the MCP stdio server."""
    if not _mcp_available:
        print("ERROR: 'mcp' package is not installed.", file=sys.stderr)
        print(
            "Run with: uv --with mcp python -m business_analyzer.mcp.database_server",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Starting depotru-database MCP server (stdio)...", file=sys.stderr)
    cfg = _get_db_config()
    print(f"  Primary DB target: {cfg['database']}", file=sys.stderr)
    print(f"  J3System target  : {cfg['j3_database']}", file=sys.stderr)
    if cfg["ncx_file"]:
        print(f"  Using NCX        : {cfg['ncx_file']}", file=sys.stderr)
    else:
        print(f"  Host             : {cfg['host']}", file=sys.stderr)

    srv = _build_server()
    _register_tools(srv)

    async def _run():
        async with stdio_server() as (read_stream, write_stream):
            await srv.run(
                read_stream,
                write_stream,
                srv.create_initialization_options(),
            )

    asyncio.run(_run())


if __name__ == "__main__":
    main()
