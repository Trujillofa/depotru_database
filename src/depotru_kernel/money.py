"""Colombian money and percentage formatting helpers."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Union

Number = Union[int, float, Decimal]


def format_cop(
    value: Optional[Number],
    *,
    decimals: int = 0,
    with_symbol: bool = True,
) -> str:
    """Format as Colombian pesos: ``$1.234.567`` or ``$1.234.567,89``."""
    if value is None:
        return "-"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "-"
    if decimals <= 0:
        rounded = int(round(num))
        body = f"{rounded:,}".replace(",", ".")
    else:
        # US-style then swap separators for es_CO
        raw = f"{num:,.{decimals}f}"
        body = raw.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"${body}" if with_symbol else body


def format_pct(
    value: Optional[Number],
    *,
    decimals: int = 1,
) -> str:
    """Format percentage with comma decimal: ``45,6%``."""
    if value is None:
        return "-"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "-"
    raw = f"{num:.{decimals}f}"
    body = raw.replace(".", ",")
    return f"{body}%"
