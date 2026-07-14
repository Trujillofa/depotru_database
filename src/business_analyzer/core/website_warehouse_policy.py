"""Website-facing J3 warehouse allowlist / denylist (issue #182).

Magento only stores MSI sources ``default`` and ``CENTRO``; J3 warehouse codes
never appear on Magento rows. b2c.smart-business.app aggregates ERP stock
before POST /V1/inventory/source-items.

This module is the **SSOT** for which J3 ``AlmacenCodigo`` values may count
toward website sellable stock. Magento dual-source sum (default+CENTRO) is
intentional for promos — see sibling repo issue Trujillofa/depositotrujillo.co#182.
"""

from __future__ import annotations

from typing import FrozenSet, Iterable, Tuple

# Full known set (keep in sync with j3system_sales_warehouse.WAREHOUSE_CODES).
ALL_J3_WAREHOUSE_CODES: Tuple[str, ...] = (
    "ALM",
    "SUR",
    "BD6",
    "DIS",
    "BOD",
    "BDT",
    "FLO",
    "CEN",
    "MDL",
    "EXH",
    "TRA",
    "CON",
    "B.ROT",
    "EXD",
)

# Exclude from website / B2C aggregation (ops decision 2026-07-14).
WEBSITE_WAREHOUSE_DENYLIST: FrozenSet[str] = frozenset(
    {
        "CEN",  # 005 GARANTIAS
        "EXH",  # BOD EXHIBICION ALMACEN
        "EXD",  # BOD EXHIBICION DISTRIBUCIONES
        "BDT",  # BODEGA AJUSTES TEMPORALES
        "MDL",  # MERCADO LIBRE
        "TRA",  # MCIA COMITECAFE
    }
)

WEBSITE_WAREHOUSE_DENYLIST_LABELS = {
    "CEN": "005 GARANTIAS",
    "EXH": "BOD EXHIBICION ALMACEN",
    "EXD": "BOD EXHIBICION DISTRIBUCIONES",
    "BDT": "BODEGA AJUSTES TEMPORALES",
    "MDL": "MERCADO LIBRE",
    "TRA": "MCIA COMITECAFE",
}

# Magento MSI sources that feed website stock "Total Disponible" (stock_id=3).
# Dual sum is intentional for website promos — do not collapse without a new decision.
MAGENTO_WEBSITE_MSI_SOURCES: Tuple[str, ...] = ("default", "CENTRO")


def website_warehouse_allowlist(
    all_codes: Iterable[str] | None = None,
) -> Tuple[str, ...]:
    """Return sorted allowlist = all known codes minus denylist."""
    codes = tuple(all_codes) if all_codes is not None else ALL_J3_WAREHOUSE_CODES
    allowed = [c for c in codes if c not in WEBSITE_WAREHOUSE_DENYLIST]
    return tuple(sorted(allowed, key=lambda x: (x.replace(".", ""), x)))


def is_website_warehouse(code: str) -> bool:
    """True if ``code`` is allowed for website stock aggregation."""
    raw = (code or "").strip()
    if not raw:
        return False
    # Match denylist case-insensitively; preserve known codes like B.ROT
    denied = {d.upper() for d in WEBSITE_WAREHOUSE_DENYLIST}
    return raw.upper() not in denied


def sql_in_list(codes: Iterable[str], *, max_len: int = 10) -> str:
    """Build a safe SQL IN-list of short codes (warehouse / SKU codes)."""
    parts = []
    for raw in codes:
        code = str(raw).strip()
        if not code or len(code) > max_len:
            raise ValueError(f"Invalid code for SQL IN-list: {raw!r}")
        # Allow letters, digits, dot, underscore, hyphen
        if not all(ch.isalnum() or ch in "._-" for ch in code):
            raise ValueError(f"Invalid code chars: {raw!r}")
        safe = code.replace("'", "''")
        parts.append(f"'{safe}'")
    if not parts:
        raise ValueError("Code list is empty")
    return ", ".join(parts)


def policy_summary() -> dict:
    """JSON-serializable policy snapshot for CLIs and reports."""
    allow = website_warehouse_allowlist()
    return {
        "denylist": sorted(WEBSITE_WAREHOUSE_DENYLIST),
        "denylist_labels": dict(WEBSITE_WAREHOUSE_DENYLIST_LABELS),
        "allowlist": list(allow),
        "magento_msi_sources": list(MAGENTO_WEBSITE_MSI_SOURCES),
        "magento_dual_source_note": (
            "Website sales channel uses stock Total Disponible = "
            "default + CENTRO (intentional for promos)."
        ),
        "issue": "Trujillofa/depositotrujillo.co#182",
    }
