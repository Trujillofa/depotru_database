# MCP Database Server — Full Usage Guide

A [Model Context Protocol](https://modelcontextprotocol.io/) server that gives AI agents (Grok, Claude, Cursor, etc.) safe, structured access to your MSSQL databases — SmartBusiness, J3System, or any other instance on the same server.

## Table of Contents

- [What It Does](#what-it-does)
- [Quick Start](#quick-start)
- [Registering with Your Agent](#registering-with-your-agent)
  - [Grok / Pi](#grok--pi)
  - [Claude Desktop](#claude-desktop)
  - [Cursor](#cursor)
- [Environment Variables](#environment-variables)
- [Tools Reference](#tools-reference)
  - [query](#query)
  - [list_tables](#list_tables)
  - [describe_table](#describe_table)
  - [query_smartbusiness](#query_smartbusiness)
  - [health](#health)
- [Response Format](#response-format)
- [Security Model](#security-model)
- [Query Timeout](#query-timeout)
- [Using It for Other MSSQL Instances](#using-it-for-other-mssql-instances)
- [Troubleshooting](#troubleshooting)
- [Testing](#testing)

---

## What It Does

The server speaks MCP over **stdio** — your agent launches it as a subprocess, discovers its tools, and calls them. No HTTP server, no port management.

It reuses the project's existing `Database` class, so you get:

- **NCX / Navicat support** — if you have an `.ncx` file, it just works
- **pymssql + pyodbc fallback** — tries pymssql first, falls back to pyodbc
- **Connection pooling** — managed by the core `Database` class
- **Identifier validation** — table and schema names are sanitized against injection
- **Dual-database awareness** — SmartBusiness for sales, J3System for ERP master data
- **Auto-exclusion filter** — `query_smartbusiness` injects the `DocumentosCodigo NOT IN ('XY','AS','TS',...)` filter so you never forget it

All of this is exposed as five clean tools your agent can discover and call.

---

## Quick Start

From the repo root, no install required:

```bash
uv run --with-editable . --with mcp python -m business_analyzer.mcp.database_server
```

Or after installing the `mcp` extra:

```bash
pip install -e ".[mcp]"
depotru-db-mcp
```

The server starts, prints connection info to stderr, and waits for MCP messages on stdin.

---

## Registering with Your Agent

### Grok / Pi

Add to `.grok/config.toml` (project-scoped) or `~/.grok/config.toml` (global):

```toml
[mcp_servers.depotru-database]
command = "uv"
args = ["run", "--with-editable", ".", "--with", "mcp", "python", "-m", "business_analyzer.mcp.database_server"]
enabled = true
startup_timeout_sec = 15
tool_timeout_sec = 120
```

Then restart Grok or press `Ctrl+L` (or `/mcps`) in the TUI to refresh.

Tools appear as:
- `depotru-database__query`
- `depotru-database__list_tables`
- `depotru-database__describe_table`
- `depotru-database__query_smartbusiness`
- `depotru-database__health`

### Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "depotru-database": {
      "command": "uv",
      "args": ["run", "--with-editable", ".", "--with", "mcp", "python", "-m", "business_analyzer.mcp.database_server"],
      "env": {
        "DB_HOST": "your-server",
        "DB_USER": "readonly_user",
        "DB_PASSWORD": "your-password",
        "DB_NAME": "SmartBusiness",
        "DB_NAME_J3SYSTEM": "J3System"
      }
    }
  }
}
```

### Cursor

Add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "depotru-database": {
      "command": "uv",
      "args": ["run", "--with-editable", ".", "--with", "mcp", "python", "-m", "business_analyzer.mcp.database_server"],
      "env": {
        "DB_HOST": "your-server",
        "DB_USER": "readonly_user",
        "DB_PASSWORD": "your-password"
      }
    }
  }
}
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DB_HOST` | Yes* | — | MSSQL server hostname or IP |
| `DB_USER` | Yes* | — | Database username |
| `DB_PASSWORD` | Yes* | — | Database password |
| `DB_NAME` | No | `SmartBusiness` | Primary database |
| `DB_PORT` | No | `1433` | Server port |
| `DB_NAME_J3SYSTEM` | No | `J3System` | J3 ERP database name |
| `NCX_FILE_PATH` | No* | — | Navicat export file (alternative to DB_HOST/USER/PASSWORD) |
| `DB_ENCRYPT` | No | `no` | Connection encryption (`1`/`true`/`yes` to enable) |
| `DB_TIMEOUT` | No | `30` | Connection timeout in seconds |
| `DB_QUERY_TIMEOUT` | No | `60` | Query execution timeout in seconds |
| `ALLOW_WRITE` | No | `0` | Set to `1` to allow non-SELECT statements |

\* Either `DB_HOST` + `DB_USER` + `DB_PASSWORD` **or** `NCX_FILE_PATH` must be set.

You can pass these via:
1. A `.env` file in the project root (loaded automatically by the main app)
2. The `env` key in your MCP client config (recommended for agent-specific credentials)
3. Shell environment variables

---

## Tools Reference

### `query`

Execute a SQL query against any configured database.

**Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `sql` | string | ✅ | The SQL statement to execute |
| `database` | string | No | Target database (`SmartBusiness`, `J3System`, or any name) |
| `params` | array | No | Parameterized values (recommended for user input) |

**Examples:**

```
# Simple sales query
use_tool("depotru-database__query", {
  "sql": "SELECT TOP 10 ArticulosNombre, SUM(TotalMasIva) as total FROM banco_datos WHERE DocumentosCodigo NOT IN ('XY','AS','TS') GROUP BY ArticulosNombre ORDER BY total DESC"
})

# Parameterized query against J3System
use_tool("depotru-database__query", {
  "sql": "SELECT ArticulosNombre, ArticulosPeso FROM AdmArticulos WHERE ArticulosPeso > %s",
  "database": "J3System",
  "params": [50]
})

# CTE (Common Table Expression)
use_tool("depotru-database__query", {
  "sql": "WITH top_clients AS (SELECT TOP 5 TercerosNombres, SUM(TotalMasIva) as total FROM banco_datos WHERE DocumentosCodigo NOT IN ('XY','AS','TS') GROUP BY TercerosNombres ORDER BY total DESC) SELECT * FROM top_clients"
})
```

**What's allowed (read-only mode):**
- `SELECT` statements
- `WITH` (CTEs) followed by `SELECT`

**What's blocked (read-only mode):**
- `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `CREATE`, `TRUNCATE`, `GRANT`, `REVOKE`
- `EXEC` / `EXECUTE` (prevents `xp_cmdshell` and similar OS command injection)
- Stacked queries with `;` (e.g., `SELECT 1; DROP TABLE x`)

Set `ALLOW_WRITE=1` to relax these restrictions (except dangerous DDL/DML keywords remain blocked).

---

### `list_tables`

List all base tables in a database schema. Useful for exploration before querying.

**Parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `database` | string | No | `DB_NAME` | Target database |
| `schema` | string | No | `dbo` | Schema filter |

**Example:**

```
use_tool("depotru-database__list_tables", {
  "database": "J3System"
})
```

**Response:**

```json
{
  "database": "J3System",
  "schema": "dbo",
  "tables": ["AdmArticulos", "AdmTerceros", "AdmPrecios", "InvExistencias", ...]
}
```

---

### `describe_table`

Get column metadata for a specific table.

**Parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `table` | string | ✅ | — | Table name (without schema prefix) |
| `database` | string | No | `DB_NAME` | Target database |
| `schema` | string | No | `dbo` | Schema name |

**Example:**

```
use_tool("depotru-database__describe_table", {
  "table": "banco_datos",
  "database": "SmartBusiness"
})
```

**Response:**

```json
{
  "database": "SmartBusiness",
  "table": "dbo.banco_datos",
  "columns": [
    { "name": "Fecha", "type": "date", "nullable": true, "max_length": null, "default": null },
    { "name": "TotalMasIva", "type": "decimal", "nullable": true, "max_length": null, "default": null },
    { "name": "ArticulosNombre", "type": "nvarchar", "nullable": true, "max_length": 200, "default": null },
    ...
  ]
}
```

Table and schema names are validated against SQL injection before the query runs.

---

### `query_smartbusiness`

Convenience wrapper for SmartBusiness sales queries. Automatically injects the standard `DocumentosCodigo NOT IN ('XY','AS','TS','YX','ISC')` exclusion filter that every legitimate banco_datos query needs.

**Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `sql` | string | ✅ | Base SQL querying `banco_datos` |
| `params` | array | No | Additional parameterized values |

**How it works:**

1. Validates the SQL for safety (same rules as `query`)
2. Checks if `DocumentosCodigo` is already in the query — if yes, does nothing
3. Checks if the query has `banco_datos` — if not, does nothing
4. Strips comments and string literals, then checks for `GROUP BY` / `ORDER BY` / `HAVING` / `LIMIT` — if found, skips injection (to avoid producing invalid SQL) and tells you
5. Otherwise, appends `WHERE DocumentosCodigo NOT IN (...)` or `AND DocumentosCodigo NOT IN (...)` depending on whether a `WHERE` already exists

**Examples:**

```
# Simple query — filter auto-injected
use_tool("depotru-database__query_smartbusiness", {
  "sql": "SELECT TOP 20 ArticulosNombre, SUM(TotalMasIva) as total FROM banco_datos GROUP BY ArticulosNombre ORDER BY total DESC"
})

# With existing WHERE — filter appended as AND
use_tool("depotru-database__query_smartbusiness", {
  "sql": "SELECT * FROM banco_datos WHERE Fecha >= '2025-01-01' AND TotalMasIva > 1000000"
})

# Complex query with GROUP BY — auto-injection skipped, you handle the filter
use_tool("depotru-database__query_smartbusiness", {
  "sql": "SELECT categoria, SUM(TotalMasIva) as total FROM banco_datos WHERE DocumentosCodigo NOT IN ('XY','AS','TS') GROUP BY categoria ORDER BY total DESC"
})
```

**Response includes:**

```json
{
  "rows": [...],
  "row_count": 20,
  "original_row_count": 20,
  "truncated": false,
  "limit": 500,
  "applied_excludes": ["XY", "AS", "TS", "YX", "ISC"],
  "note": "SmartBusiness common document filter was applied where appropriate."
}
```

If auto-injection was skipped:

```json
{
  "rows": [...],
  "applied_excludes": [],
  "note": "Complex query with GROUP BY/ORDER BY/HAVING/LIMIT detected. Auto-injection skipped to avoid invalid SQL. Include 'AND DocumentosCodigo NOT IN (...)' yourself in the WHERE clause."
}
```

---

### `health`

Lightweight ping that returns server status without touching the database. Useful for monitoring and startup verification.

**Parameters:** None.

**Response:**

```json
{
  "status": "ok",
  "server": "depotru-database-mcp",
  "primary_database": "SmartBusiness",
  "j3_database": "J3System",
  "write_mode": false,
  "query_timeout_sec": 60
}
```

---

## Response Format

All tools return JSON wrapped in MCP `TextContent`. The general shape:

```json
{
  "rows": [ ... ],
  "row_count": 42,
  "original_row_count": 1200,
  "truncated": true,
  "limit": 500
}
```

| Field | Description |
|-------|-------------|
| `rows` | Array of row objects (column names as keys) |
| `row_count` | Number of rows actually returned (after truncation) |
| `original_row_count` | Number of rows the query produced before truncation |
| `truncated` | `true` if results were cut at the limit |
| `limit` | The truncation threshold (default: 500 rows) |

On error:

```json
{
  "error": "Query rejected for safety. Only SELECT/WITH/EXEC allowed unless ALLOW_WRITE=1.",
  "tool": "query"
}
```

---

## Security Model

### Read-Only by Default

Without `ALLOW_WRITE=1`, the server only allows:

- `SELECT` statements
- `WITH` (CTEs) that lead to `SELECT`

Everything else is rejected:

| Blocked | Why |
|---------|-----|
| `DROP`, `DELETE`, `UPDATE`, `INSERT` | Data modification |
| `ALTER`, `CREATE`, `TRUNCATE` | Schema changes |
| `GRANT`, `REVOKE` | Permission changes |
| `EXEC`, `EXECUTE` | Can invoke `xp_cmdshell` → OS commands |
| `;` (stacked queries) | Bypass via `SELECT 1; EXEC ...` |

### Identifier Validation

Table names and schema names passed to `describe_table` are validated using the same `validate_sql_identifier` method from the core `Database` class. This prevents SQL injection through metadata queries.

### Query Timeout

All queries have a configurable timeout (default: 60 seconds). If a query exceeds this, the thread is cancelled and an error is returned. Prevents runaway queries from blocking the server.

### Rate Limiting

Built-in rate limiter caps at 20 calls per second per tool. Prevents a misbehaving agent from hammering the database.

### Resource Management

- A module-level `ThreadPoolExecutor` (4 workers) handles query execution with timeout
- Properly shut down via `atexit` when the process exits
- Database connections are opened and closed per-query (no connection leak)

---

## Query Timeout

Controlled by environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_QUERY_TIMEOUT` | `60` | Max seconds a query can run |
| `DB_QUERY_TIMEOUT_SEC` | `60` | Alias (same effect) |

Set it higher for heavy reports:

```toml
# In your MCP client config
env = { DB_HOST = "...", DB_QUERY_TIMEOUT = "300" }
```

The timeout is reported in the `health` tool response.

---

## Using It for Other MSSQL Instances

This server is intentionally generic. To use it with a different MSSQL database:

1. **Same server, different database** — just pass the `database` parameter to `query` or `list_tables`
2. **Completely different project** — copy `src/business_analyzer/mcp/` into your project

For option 2, you have two paths:

### With the full `business_analyzer` package (recommended)

You get NCX support, identifier validation, connection pooling, and the J3System helper:

```toml
[mcp_servers.my-database]
command = "uv"
args = ["run", "--with-editable", ".", "--with", "mcp", "python", "-m", "business_analyzer.mcp.database_server"]
env = { DB_HOST = "my-server", DB_USER = "readonly", DB_PASSWORD = "secret", DB_NAME = "MyDatabase" }
enabled = true
```

### Standalone (no business_analyzer dependency)

The server degrades gracefully if `business_analyzer.core.database` is not importable. It falls back to a minimal `pymssql`-only connection. You lose NCX support and identifier validation, but basic querying works:

```toml
[mcp_servers.my-database]
command = "python"
args = ["-m", "business_analyzer.mcp.database_server"]
env = { DB_HOST = "my-server", DB_USER = "readonly", DB_PASSWORD = "secret", DB_NAME = "MyDatabase" }
enabled = true
```

The `query_smartbusiness` tool is harmless if you don't have a `banco_datos` table — it simply won't match and won't inject anything.

---

## Troubleshooting

### Server won't start

```
ERROR: 'mcp' package is not installed.
```

**Fix:** Add `--with mcp` to your command, or `pip install mcp`.

### "Could not import business_analyzer.core.database"

This is a **warning**, not a fatal error. The server falls back to a minimal pymssql connection. If you need the full features (NCX, validation, J3 helpers), make sure the project is installed or on the Python path.

### Connection refused

Check your environment variables:

```bash
# Verify the server can see them
uv run --with-editable . --with mcp python -c "
import sys; sys.path.insert(0, 'src')
from business_analyzer.mcp.database_server import _get_db_config
import json; print(json.dumps(_get_db_config(), indent=2, default=str))
"
```

### Queries timing out

Increase `DB_QUERY_TIMEOUT`:

```toml
env = { DB_QUERY_TIMEOUT = "300" }
```

### Rate limit errors

If you see `"Rate limit exceeded for tool 'query'"`, your agent is calling tools too fast. The limit is 20 calls/second per tool. This is a safety feature — if it's too aggressive for your use case, adjust `_MAX_CALLS_PER_WINDOW` in the source.

### Tools not appearing in Grok

1. Check the config file path (`.grok/config.toml` in project root or `~/.grok/config.toml`)
2. Press `Ctrl+L` or run `/mcps` to refresh
3. Check the MCP server logs on stderr for startup errors

---

## Testing

```bash
# MCP-specific tests (fast, no DB required)
python -m pytest tests/mcp/ -v

# Full test suite
python -m pytest --tb=no -q

# Compile check (catches syntax errors)
python -m py_compile src/business_analyzer/mcp/database_server.py
```

The MCP tests mock the database layer and MCP SDK, so they run without a real database or the `mcp` package installed.

---

## Architecture

```
Agent (Grok/Claude/Cursor)
  │
  │ MCP protocol (stdio JSON-RPC)
  ▼
database_server.py
  │
  ├── _is_safe_sql()          ← security gate
  ├── _execute_on_db_with_timeout()  ← thread pool + timeout
  ├── _get_database()         ← retry + backoff
  │     │
  │     ▼
  │   business_analyzer.core.database.Database  (rich path)
  │   or pymssql.connect()                       (fallback)
  │
  └── Tools:
      ├── query
      ├── list_tables
      ├── describe_table
      ├── query_smartbusiness  (auto-filter injection)
      └── health
```

Each tool call:
1. Checks the rate limiter
2. Validates the SQL (safety gate)
3. Opens a database connection
4. Executes the query with a timeout
5. Truncates results if needed (500 row limit)
6. Closes the connection
7. Returns JSON to the agent

---

## Testing the MCP Server

Unit tests (no MCP SDK or DB required):
```bash
python -m pytest tests/mcp/ -q
```

End-to-end integration test (requires `mcp` + `pytest-asyncio` packages; exercises real stdio JSON-RPC protocol + optional real DB):
```bash
# Using uv (recommended, no permanent install):
uv run --with mcp --with pytest-asyncio python -m pytest tests/mcp/test_mcp_integration.py -q
# Or after installing extras:
pip install -e ".[mcp]"
pip install pytest-asyncio
python -m pytest tests/mcp/test_mcp_integration.py -q
```

The integration test launches the server via the documented `uv run --with-editable ...` command and drives it with `mcp.client.stdio` + `ClientSession`, verifying:
- initialize
- tools/list (the 5 tools)
- health, query_smartbusiness (complex query + note), describe_table, etc.

See `tests/mcp/test_mcp_integration.py` for the harness (skips cleanly if no `mcp`).

---

## License

Same as the parent project. See root `LICENSE` and `CONTRIBUTING.md`.
