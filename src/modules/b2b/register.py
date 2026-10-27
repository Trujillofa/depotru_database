"""Tool registration for the B2B module (depotru_tools registry).

All B2B tools sit on B2B-only scopes (R22): the ``public``, ``agent``, and
storefront-Assistant keys get 403; the B2B credential gets nothing else.
``b2b.order_submit`` is fail-closed disabled while R15 is blocked.
"""

from __future__ import annotations

from typing import Any, Mapping

from depotru_kernel.auth import ToolScope
from depotru_tools.registry import ToolContext, ToolRegistry, ToolSpec
from modules.b2b.credit import credit_status
from modules.b2b.erp import get_b2b_erp_client
from modules.b2b.service import request_quote


def _tool_b2b_quote(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """Company-scoped negotiated quote (never the public list price)."""
    result: dict = request_quote(params, get_b2b_erp_client())
    return result


def _tool_b2b_credit_status(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """Fail-closed credit status (R14: blocked)."""
    result: dict = credit_status(params.get("terceros_id"))
    return result


def _tool_b2b_order_submit(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """Disabled by design (R15): no Magento→ERP order write in v1."""
    return {
        "status": "disabled",
        "reason": "r15_blocked",
        "policy": (
            "ERP order submission requires a Task 5 approved vendor API; "
            "pilot path is manual sales handoff (R13)"
        ),
    }


def register_b2b_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolSpec(
            name="b2b.quote",
            description=(
                "Company-scoped negotiated quote from the ERP customer tariff "
                "(server-to-server; fails closed; never list price)"
            ),
            scope=ToolScope.B2B_QUOTE,
            handler=_tool_b2b_quote,
            public_safe=False,
            parameters_schema={
                "company_ref": "staff-linked company reference",
                "terceros_id": "server-resolved ERP customer id",
                "site": "'neiva' | 'florencia'",
                "items": "[{sku, qty}] (max 20 SKUs)",
            },
        )
    )
    registry.register(
        ToolSpec(
            name="b2b.credit_status",
            description=(
                "Company credit status — unavailable while credit terms are "
                "blocked (R14); never returns an amount"
            ),
            scope=ToolScope.B2B_CREDIT,
            handler=_tool_b2b_credit_status,
            public_safe=False,
            parameters_schema={"terceros_id": "ERP customer id"},
        )
    )
    registry.register(
        ToolSpec(
            name="b2b.order_submit",
            description=(
                "ERP order submission — DISABLED (R15 blocked); contract-only "
                "surface, pilot uses manual sales handoff (R13)"
            ),
            scope=ToolScope.B2B_ORDER,
            handler=_tool_b2b_order_submit,
            public_safe=False,
            parameters_schema={
                "order_key": "idempotency key (Magento order ref)",
                "payload": "order payload (unused while disabled)",
            },
        )
    )
