"""Unified seller attribution — single entry point for all modules.

Priority (locked commercial rule):
  1. VendedorAsignado leading code
  2. VendedorFactura official owner / name map
  3. vendedor_codigo
  4. POOL

Implementation delegates to ``presupuesto_2026`` / ``vendor_ownership`` so
budget generation and platform tools cannot drift.
"""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

from business_analyzer.core.presupuesto_2026 import DEFAULT_CODE_MERGES
from business_analyzer.core.presupuesto_2026 import attribute_sale as _attribute_sale
from business_analyzer.core.presupuesto_2026 import (
    normalize_code,
    normalize_name,
    official_owner_for_factura,
    parse_asignado_code,
)
from business_analyzer.core.vendor_ownership import (
    ACTIVE_META_CODES_2026,
    OFFICIAL_CODE_NAMES,
    OFFICIAL_FACTURA_OWNERS,
)


def attribute_sale(
    *,
    code: Optional[str] = None,
    name: Optional[str] = None,
    asignado: Optional[str] = None,
    name_to_code: Optional[Mapping[str, str]] = None,
    active_codes: Optional[Sequence[str]] = None,
    merges: Optional[Mapping[str, str]] = None,
    pool_key: str = "POOL",
) -> str:
    """Return active canonical vendor code or POOL."""
    result = _attribute_sale(
        code=code,
        name=name,
        asignado=asignado,
        name_to_code=name_to_code or {},
        active_codes=active_codes or ACTIVE_META_CODES_2026,
        merges=merges or DEFAULT_CODE_MERGES,
        pool_key=pool_key,
    )
    return str(result)


def resolve_seller(
    *,
    code: Optional[str] = None,
    name: Optional[str] = None,
    asignado: Optional[str] = None,
    name_to_code: Optional[Mapping[str, str]] = None,
) -> dict:
    """Tool-friendly attribution result with display name."""
    resolved = attribute_sale(
        code=code,
        name=name,
        asignado=asignado,
        name_to_code=name_to_code,
    )
    display = OFFICIAL_CODE_NAMES.get(resolved)
    if not display and resolved != "POOL":
        display = (name or "").strip() or None
    return {
        "code": resolved,
        "display_name": display,
        "is_pool": resolved == "POOL",
        "rule": "asignado > factura_owner > vendedor_codigo > POOL",
        "inputs": {
            "code": normalize_code(code),
            "name": normalize_name(name) if name else None,
            "asignado_code": parse_asignado_code(asignado),
            "factura_owner": official_owner_for_factura(name),
        },
    }


__all__ = [
    "ACTIVE_META_CODES_2026",
    "OFFICIAL_CODE_NAMES",
    "OFFICIAL_FACTURA_OWNERS",
    "attribute_sale",
    "normalize_code",
    "normalize_name",
    "resolve_seller",
]
