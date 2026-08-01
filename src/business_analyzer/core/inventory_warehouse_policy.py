"""Commercial warehouse policy for inventory turnover (Rotación de Existencias).

Stricter than website stock policy: only main sellable / ops bodegas feed
turnover rankings so noise warehouses (CON, B.ROT, BDT, CEN, …) do not
dominate quiebre tables.
"""

from __future__ import annotations

from typing import FrozenSet, Iterable, Tuple

from business_analyzer.core.website_warehouse_policy import (
    ALL_J3_WAREHOUSE_CODES,
    sql_in_list,
)

# Phase-1 commercial allowlist (plan: ALM, SUR, BD6, DIS, FLO).
# BOD deferred pending ops confirmation (specialty "MANGUERAS").
TURNOVER_WAREHOUSE_ALLOWLIST: Tuple[str, ...] = (
    "ALM",
    "SUR",
    "BD6",
    "DIS",
    "FLO",
)

TURNOVER_WAREHOUSE_DENYLIST: FrozenSet[str] = frozenset(
    c for c in ALL_J3_WAREHOUSE_CODES if c not in TURNOVER_WAREHOUSE_ALLOWLIST
)

TURNOVER_WAREHOUSE_LABELS = {
    "ALM": "001 / almacén principal",
    "SUR": "SUR",
    "BD6": "BD6",
    "DIS": "DISTRIBUCIONES",
    "FLO": "ALMACEN FLORENCIA",
}


def turnover_warehouse_allowlist(
    codes: Iterable[str] | None = None,
) -> Tuple[str, ...]:
    """Return the commercial allowlist (override via ``codes`` for tests)."""
    if codes is None:
        return TURNOVER_WAREHOUSE_ALLOWLIST
    return tuple(str(c).strip() for c in codes if str(c).strip())


def is_turnover_warehouse(code: str) -> bool:
    """True if ``code`` is in the commercial turnover allowlist."""
    raw = (code or "").strip().upper()
    if not raw:
        return False
    allowed = {c.upper() for c in TURNOVER_WAREHOUSE_ALLOWLIST}
    return raw in allowed


def turnover_warehouse_sql_in_list(codes: Iterable[str] | None = None) -> str:
    """Safe SQL IN-list for commercial warehouses."""
    return str(sql_in_list(turnover_warehouse_allowlist(codes)))


# Non-inventory / service SKUs that pollute stock and overstock rankings.
# Exact codes and prefixes (e.g. 008050 = transporte / flete family).
TURNOVER_SKU_DENYLIST_EXACT: FrozenSet[str] = frozenset(
    {
        "0080500001",  # TRANSPORTE DE MERCANCIA
        "0110010001",  # SERV DE TRANSPORTE DE MERCANCIA EXCLUIDO
    }
)

TURNOVER_SKU_DENYLIST_PREFIXES: Tuple[str, ...] = (
    "008050",  # service / freight family
)

# Name tokens (uppercase) that mark non-merchandise lines.
TURNOVER_SKU_DENYLIST_NAME_TOKENS: Tuple[str, ...] = (
    "SERVICIO",
    "SERV DE ",
    "TRANSPORTE DE MERCANCIA",
)


def is_turnover_sku_denied(sku: str, nombre: str | None = None) -> bool:
    """True if SKU/name is a service/non-stock line excluded from actions."""
    code = (sku or "").strip()
    if code and code in TURNOVER_SKU_DENYLIST_EXACT:
        return True
    if code and any(code.startswith(p) for p in TURNOVER_SKU_DENYLIST_PREFIXES):
        return True
    name = (nombre or "").upper()
    if name and any(tok in name for tok in TURNOVER_SKU_DENYLIST_NAME_TOKENS):
        return True
    return False


def turnover_sku_denylist_sql_not_like() -> str:
    """SQL fragment for excluding service SKUs/names (use inside NOT (...))."""
    parts = [f"a.ArticulosCodigo = '{c}'" for c in sorted(TURNOVER_SKU_DENYLIST_EXACT)]
    for p in TURNOVER_SKU_DENYLIST_PREFIXES:
        safe = p.replace("'", "''")
        parts.append(f"a.ArticulosCodigo LIKE '{safe}%'")
    for tok in TURNOVER_SKU_DENYLIST_NAME_TOKENS:
        safe = tok.replace("'", "''")
        parts.append(f"a.ArticulosNombre LIKE '%{safe}%'")
    if not parts:
        return "1=0"
    return " OR ".join(parts)


def turnover_policy_summary() -> dict:
    """JSON-serializable snapshot for report headers."""
    allow = list(turnover_warehouse_allowlist())
    return {
        "allowlist": allow,
        "allowlist_labels": {k: TURNOVER_WAREHOUSE_LABELS.get(k, k) for k in allow},
        "denylist": sorted(TURNOVER_WAREHOUSE_DENYLIST),
        "sku_denylist_exact": sorted(TURNOVER_SKU_DENYLIST_EXACT),
        "sku_denylist_prefixes": list(TURNOVER_SKU_DENYLIST_PREFIXES),
        "note": (
            "Commercial warehouses only; excludes CON/B.ROT/BDT/CEN/EXH/"
            "EXD/TRA/MDL/BOD by default. Service SKUs (e.g. 008050*) excluded."
        ),
    }
