"""B2B contract constants, exceptions, and validation helpers.

Locked by docs/b2b/requirements.md (R11, R12, R19, R22) and
docs/b2b/erp-contract.md. Decimal-safe everywhere: amounts cross the wire as
fixed-point strings, never JSON floats.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Optional

# --- Locked contract constants -------------------------------------------

CURRENCY = "COP"
UNIT = "UND"  # candidate assumption; verify against released contract
PRICE_INCLUDES_IVA = False  # R11: net before IVA; Magento owns tax
CONTRACT_VERSION = "1"

SKU_MAX_LEN = 40  # candidate ERP cap
MAX_QUANTITY = Decimal("999999")

# R9: sites v1 — Neiva and Florencia only.
SITE_WAREHOUSES: dict[str, tuple[str, ...]] = {
    "neiva": ("ALM", "BD6", "SUR", "DIS", "BOD"),
    "florencia": ("FLO",),
}

# Refused tariff (candidate): id 6 / code 006 / name AL COSTO. Never price it.
REFUSED_TARIFF_IDS = frozenset({"6"})
REFUSED_TARIFF_CODES = frozenset({"006"})
REFUSED_TARIFF_NAMES = frozenset({"AL COSTO"})


class ErpUnavailableError(RuntimeError):
    """ERP connection/query failure — mapped to a fail-closed response."""


class ErpTimeoutError(RuntimeError):
    """ERP timeout — mapped to a fail-closed response."""


def site_is_valid(site: Any) -> bool:
    return isinstance(site, str) and site.strip().lower() in SITE_WAREHOUSES


def normalize_sku(raw: Any) -> Optional[str]:
    """Stripped SKU, or None when absent/blank/not a string."""
    if not isinstance(raw, str):
        return None
    sku = raw.strip()
    return sku or None


def parse_quantity(raw: Any) -> Optional[Decimal]:
    """Exact Decimal quantity > 0, or None when invalid (never a float)."""
    if isinstance(raw, bool) or raw is None or raw == "":
        return None
    if isinstance(raw, float):
        # Reject binary floats at the boundary: require a decimal-safe string
        # or int. A float input has already lost exactness.
        return None
    try:
        qty = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    if not qty.is_finite() or qty <= 0 or qty > MAX_QUANTITY:
        return None
    return qty


def format_amount(value: Decimal) -> str:
    """Fixed-point string with no exponent and no float round-trip."""
    return format(value, "f")


def tariff_is_missing(tariff_id: Any, tariff_code: Any) -> bool:
    return not (str(tariff_id or "").strip() or str(tariff_code or "").strip())


def tariff_is_refused(tariff_id: Any, tariff_code: Any, tariff_name: Any) -> bool:
    return (
        str(tariff_id or "").strip().upper() in REFUSED_TARIFF_IDS
        or str(tariff_code or "").strip().upper() in REFUSED_TARIFF_CODES
        or str(tariff_name or "").strip().upper() in REFUSED_TARIFF_NAMES
    )
