"""
End-to-end MCP integration test for the database server.

This launches the MCP server as a child process (using uv to ensure deps)
and drives it with the official mcp client SDK over stdio.

Requires:
- mcp package installed (pip install mcp or the project's [mcp] extra)
- The project editable or source available
- For full query tests: DB credentials in env (or .env loaded)

Run with: python -m pytest tests/mcp/test_mcp_integration.py -q --tb=short -m "not requires_db or requires_db"

Mark: uses pytest.mark.asyncio
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Dict, List

import pytest

try:
    from mcp.client.stdio import stdio_client

    from mcp import ClientSession, StdioServerParameters

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    ClientSession = None  # type: ignore
    StdioServerParameters = None  # type: ignore
    stdio_client = None  # type: ignore

# Skip all if no mcp SDK
pytestmark = pytest.mark.skipif(
    not MCP_AVAILABLE,
    reason="mcp package not installed (pip install mcp or -e '.[mcp]')",
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _mcp_server_command() -> List[str]:
    """Prefer uv when available; fall back to the active interpreter on CI."""
    if shutil.which("uv"):
        return [
            "uv",
            "run",
            "--with-editable",
            str(PROJECT_ROOT),
            "--with",
            "mcp",
            "python",
            "-m",
            "business_analyzer.mcp.database_server",
        ]
    return [sys.executable, "-m", "business_analyzer.mcp.database_server"]


@asynccontextmanager
async def mcp_server_session(
    env: Dict[str, str] | None = None,
) -> AsyncIterator[ClientSession]:
    """Launch the depotru-database MCP server and yield an initialized ClientSession."""
    cmd = _mcp_server_command()
    server_params = StdioServerParameters(
        command=cmd[0],
        args=cmd[1:],
        env=env or os.environ.copy(),
        cwd=str(PROJECT_ROOT),
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


@pytest.mark.asyncio
async def test_mcp_tools_list():
    """Verify tool discovery returns the expected 5 tools."""
    async with mcp_server_session() as session:
        tools_result = await session.list_tools()
        names = sorted([t.name for t in tools_result.tools])
        assert names == [
            "describe_table",
            "health",
            "list_tables",
            "query",
            "query_smartbusiness",
        ]


@pytest.mark.asyncio
async def test_mcp_health():
    """Health tool should return status without requiring DB connect."""
    async with mcp_server_session() as session:
        result = await session.call_tool("health", {})
        # result.content is list of TextContent
        text = result.content[0].text if result.content else "{}"
        data = json.loads(text)
        assert data.get("status") == "ok"
        assert "primary_database" in data
        assert "write_mode" in data
        assert isinstance(data.get("query_timeout_sec"), int)


@pytest.mark.asyncio
@pytest.mark.requires_db
async def test_mcp_query_smartbusiness_complex():
    """query_smartbusiness with GROUP BY should succeed and return the 'complex query' note."""
    sql = (
        "SELECT TOP 5 marca, COUNT(*) as cnt "
        "FROM banco_datos "
        "GROUP BY marca "
        "ORDER BY cnt DESC"
    )
    async with mcp_server_session() as session:
        result = await session.call_tool("query_smartbusiness", {"sql": sql})
        text = result.content[0].text if result.content else "{}"
        data = json.loads(text)
        assert "rows" in data
        assert "note" in data
        assert "Complex query with GROUP BY" in (data.get("note") or "")


@pytest.mark.asyncio
@pytest.mark.requires_db  # for real data queries; can be skipped in CI without DB
async def test_mcp_describe_table():
    """Describe a known table; requires DB but exercises schema path."""
    async with mcp_server_session() as session:
        result = await session.call_tool("describe_table", {"table": "banco_datos"})
        text = result.content[0].text if result.content else "{}"
        data = json.loads(text)
        assert data.get("table", "").endswith("banco_datos")
        cols = data.get("columns", [])
        assert any(c.get("name") in ("VentaID", "marca", "TotalMasIva") for c in cols)


# Optional: more tests can be added for query, list_tables, J3 if env has creds
