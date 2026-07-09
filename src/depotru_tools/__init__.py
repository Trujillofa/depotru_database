"""Capability / tool registry shared by REST, MCP, and Assistant channels."""

from depotru_tools.registry import (
    ToolContext,
    ToolNotFoundError,
    ToolPermissionError,
    ToolRegistry,
    ToolSpec,
    get_default_registry,
)

__all__ = [
    "ToolContext",
    "ToolNotFoundError",
    "ToolPermissionError",
    "ToolRegistry",
    "ToolSpec",
    "get_default_registry",
]
