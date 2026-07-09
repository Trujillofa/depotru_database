"""Tool registry: same capabilities for REST, MCP, and Magento assistant."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional

from depotru_kernel.auth import Audience, ToolScope, audience_may_use

ToolHandler = Callable[["ToolContext", Mapping[str, Any]], Any]


class ToolNotFoundError(KeyError):
    """Raised when a tool name is not registered."""


class ToolPermissionError(PermissionError):
    """Raised when the audience may not invoke a tool."""


@dataclass(frozen=True)
class ToolSpec:
    """Metadata for one platform capability."""

    name: str
    description: str
    scope: ToolScope
    handler: ToolHandler
    parameters_schema: Mapping[str, Any] = field(default_factory=dict)
    # If True, responses must not include cost/margin for public audiences
    public_safe: bool = False


@dataclass
class ToolContext:
    """Runtime context for a tool invocation."""

    audience: Audience = Audience.SERVICE
    request_id: Optional[str] = None
    extras: Dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """In-process tool catalog."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if not spec.name:
            raise ValueError("Tool name is required")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(name) from exc

    def list_tools(
        self,
        audience: Optional[Audience] = None,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for spec in sorted(self._tools.values(), key=lambda s: s.name):
            if audience is not None and not audience_may_use(audience, spec.scope):
                continue
            items.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "scope": spec.scope.value,
                    "public_safe": spec.public_safe,
                    "parameters": dict(spec.parameters_schema),
                }
            )
        return items

    def call(
        self,
        name: str,
        params: Optional[Mapping[str, Any]] = None,
        *,
        context: Optional[ToolContext] = None,
    ) -> Any:
        ctx = context or ToolContext()
        spec = self.get(name)
        if not audience_may_use(ctx.audience, spec.scope):
            raise ToolPermissionError(
                f"Audience {ctx.audience.value} cannot use tool {name} "
                f"(scope={spec.scope.value})"
            )
        return spec.handler(ctx, params or {})


_DEFAULT: Optional[ToolRegistry] = None


def get_default_registry() -> ToolRegistry:
    """Lazy singleton with built-in tools registered once."""
    global _DEFAULT
    if _DEFAULT is None:
        from depotru_tools.builtins import register_builtin_tools

        reg = ToolRegistry()
        register_builtin_tools(reg)
        _DEFAULT = reg
    return _DEFAULT


def reset_default_registry() -> None:
    """Test helper: clear the singleton."""
    global _DEFAULT
    _DEFAULT = None
