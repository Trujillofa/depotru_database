"""MCP (Model Context Protocol) servers for the Business Data Analyzer.

Currently contains:
- database_server: Reusable MSSQL database access for agents (SmartBusiness + J3System aware).
"""


def run_database_mcp_server():
    """Lazy entrypoint so the mcp subpackage can be imported without the optional mcp extra."""
    from .database_server import main as _main

    _main()
