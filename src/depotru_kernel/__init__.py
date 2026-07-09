"""Shared domain kernel for the Depotru multi-module platform.

Stable contracts used by BI, Assistant, CRM, WMS, and Catalog modules.
Prefer importing from here for identity, money, attribution, and safety rules.
"""

from depotru_kernel.attribution import attribute_sale, resolve_seller
from depotru_kernel.auth import Audience, ToolScope, scopes_for_audience
from depotru_kernel.documents import (
    CANONICAL_EXCLUDED_DOCUMENT_CODES,
    excluded_document_sql_in_list,
)
from depotru_kernel.models import Money, PartyRef, SkuRef
from depotru_kernel.money import format_cop, format_pct

__all__ = [
    "Audience",
    "CANONICAL_EXCLUDED_DOCUMENT_CODES",
    "Money",
    "PartyRef",
    "SkuRef",
    "ToolScope",
    "attribute_sale",
    "excluded_document_sql_in_list",
    "format_cop",
    "format_pct",
    "resolve_seller",
    "scopes_for_audience",
]

__version__ = "0.1.0"
