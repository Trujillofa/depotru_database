"""Tool registration for the B2B module (depotru_tools registry).

All B2B tools sit on B2B-only scopes (R22): the ``public``, ``agent``, and
storefront-Assistant keys get 403; the B2B credential gets nothing else.
``b2b.order_submit`` is fail-closed disabled while R15 is blocked.
"""

from __future__ import annotations

from typing import Any, Mapping

from depotru_kernel.auth import ToolScope
from depotru_tools.registry import ToolContext, ToolRegistry, ToolSpec
from modules.b2b.cartera import (
    cartera_detail_response,
    cartera_summary_response,
    get_b2b_cartera_client,
)
from modules.b2b.credit import credit_status
from modules.b2b.erp import get_b2b_erp_client
from modules.b2b.service import request_quote
from modules.catalog.stock import catalog_stock


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


def _tool_b2b_cartera_detail(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """One staff-linked company's open AR (R23: member's own tercero only)."""
    result: dict = cartera_detail_response(
        params.get("terceros_id"), get_b2b_cartera_client()
    )
    return result


def _tool_b2b_cartera_summary(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """All open AR accounts, biggest debt first (R23: platform-admin view)."""
    result: dict = cartera_summary_response(
        params.get("max_rows"), get_b2b_cartera_client()
    )
    return result


def _tool_b2b_stock(ctx: ToolContext, params: Mapping[str, Any]) -> dict:
    """Sede availability for the B2B storefront.

    One implementation, not two: the storefront's Florencia placement gate asks
    the same aggregate as ``catalog.stock``. It is registered on its own B2B
    scope because R22 forbids the B2B credential the sales-portfolio scope that
    ``catalog.stock`` requires -- without this route the gate could never get an
    answer, and every pickup order would be refused as "stock unknown".
    """
    return dict(catalog_stock(ctx, params))


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
                "items": "[{sku, qty}]",
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

    registry.register(
        ToolSpec(
            name="b2b.cartera_detail",
            description=(
                "Open AR documents, aging buckets and cupo for ONE staff-linked "
                "company (R23: display-only; member sees only its own tercero)"
            ),
            scope=ToolScope.B2B_CARTERA,
            handler=_tool_b2b_cartera_detail,
            public_safe=False,
            parameters_schema={
                "terceros_id": "server-resolved ERP customer id (1..9999999)",
            },
        )
    )

    registry.register(
        ToolSpec(
            name="b2b.cartera_summary",
            description=(
                "Client-grain open AR across ALL companies, biggest debt first "
                "(R23: display-only; storefront gate is platform-admin only)"
            ),
            scope=ToolScope.B2B_CARTERA,
            handler=_tool_b2b_cartera_summary,
            public_safe=False,
            parameters_schema={
                "max_rows": "1..500 (default 200)",
            },
        )
    )

    registry.register(
        ToolSpec(
            name="b2b.stock",
            description=(
                "Exact SKU/sede availability for the B2B storefront (Florencia "
                "pickup); same fail-closed aggregate as catalog.stock"
            ),
            scope=ToolScope.B2B_STOCK,
            handler=_tool_b2b_stock,
            public_safe=False,
            parameters_schema={
                "skus": "1-5 exact SKU codes",
                "sede": "'neiva' | 'florencia' (absent -> both)",
            },
        )
    )
