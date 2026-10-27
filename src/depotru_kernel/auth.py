"""Audience and tool-scope model for multi-channel access control."""

from __future__ import annotations

from enum import Enum
from typing import FrozenSet, Mapping


class Audience(str, Enum):
    """Who is calling the platform."""

    PUBLIC = "public"  # Magento storefront visitor
    CUSTOMER = "customer"  # Logged-in Magento customer
    SALES = "sales"  # Internal commercial
    WAREHOUSE = "warehouse"  # WMS / logistics
    ADMIN = "admin"  # Full internal
    SERVICE = "service"  # Machine / Magento ops / cron
    AGENT = "agent"  # MCP / IDE agents
    B2B = "b2b"  # Dedicated Magento-service B2B credential (R22)


class ToolScope(str, Enum):
    """Capability class for a registered tool."""

    PUBLIC_CATALOG = "public_catalog"
    PUBLIC_STOCK = "public_stock"
    PUBLIC_INFO = "public_info"
    CUSTOMER_ORDERS = "customer_orders"
    SALES_MARGIN = "sales_margin"
    SALES_PORTFOLIO = "sales_portfolio"
    WMS_OPS = "wms_ops"
    BI_INTERNAL = "bi_internal"
    ATTRIBUTION = "attribution"
    ADMIN = "admin"
    B2B_QUOTE = "b2b_quote"  # Company-scoped negotiated quotes (never public)
    B2B_CREDIT = "b2b_credit"  # Fail-closed credit status (R14: blocked)
    B2B_ORDER = "b2b_order"  # Idempotent order adapter (R15: submit disabled)


# Default allow-lists per audience (expand carefully).
_AUDIENCE_SCOPES: Mapping[Audience, FrozenSet[ToolScope]] = {
    Audience.PUBLIC: frozenset(
        {
            ToolScope.PUBLIC_CATALOG,
            ToolScope.PUBLIC_STOCK,
            ToolScope.PUBLIC_INFO,
        }
    ),
    Audience.CUSTOMER: frozenset(
        {
            ToolScope.PUBLIC_CATALOG,
            ToolScope.PUBLIC_STOCK,
            ToolScope.PUBLIC_INFO,
            ToolScope.CUSTOMER_ORDERS,
        }
    ),
    Audience.SALES: frozenset(
        {
            ToolScope.PUBLIC_CATALOG,
            ToolScope.PUBLIC_STOCK,
            ToolScope.PUBLIC_INFO,
            ToolScope.CUSTOMER_ORDERS,
            ToolScope.SALES_MARGIN,
            ToolScope.SALES_PORTFOLIO,
            ToolScope.ATTRIBUTION,
            ToolScope.BI_INTERNAL,
        }
    ),
    Audience.WAREHOUSE: frozenset(
        {
            ToolScope.PUBLIC_STOCK,
            ToolScope.WMS_OPS,
            ToolScope.PUBLIC_INFO,
        }
    ),
    Audience.ADMIN: frozenset(set(ToolScope)),
    Audience.SERVICE: frozenset(
        {
            ToolScope.PUBLIC_CATALOG,
            ToolScope.PUBLIC_STOCK,
            ToolScope.PUBLIC_INFO,
            ToolScope.BI_INTERNAL,
            ToolScope.ATTRIBUTION,
        }
    ),
    Audience.AGENT: frozenset(
        {
            ToolScope.PUBLIC_CATALOG,
            ToolScope.PUBLIC_STOCK,
            ToolScope.PUBLIC_INFO,
            ToolScope.BI_INTERNAL,
            ToolScope.ATTRIBUTION,
            ToolScope.WMS_OPS,
        }
    ),
    # R22: the B2B credential invokes ONLY B2B routes — no catalog, sales,
    # stock, BI, or agent capabilities leak through this key.
    Audience.B2B: frozenset(
        {
            ToolScope.B2B_QUOTE,
            ToolScope.B2B_CREDIT,
            ToolScope.B2B_ORDER,
        }
    ),
}


def scopes_for_audience(audience: Audience) -> FrozenSet[ToolScope]:
    return _AUDIENCE_SCOPES.get(audience, frozenset())


def audience_may_use(audience: Audience, scope: ToolScope) -> bool:
    return scope in scopes_for_audience(audience)
