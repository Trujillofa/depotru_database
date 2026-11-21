"""Exact decimal aggregation and pure helpers for ``catalog.stock``.

Holds the fail-closed, exact fixed-point arithmetic (§9) and the pure
normalization/classification helpers shared by ``catalog.stock``. No I/O, no
SQL, no DB access — everything here is deterministic and side-effect free, so
``catalog.stock`` keeps only the read/query/handler flow. See
docs/contracts/catalog-stock.md.
"""

from __future__ import annotations

import decimal
import re
from decimal import Decimal
from typing import Any

MAX_SKU_LENGTH = 40

_SKU_RE = re.compile(r"^[A-Z0-9._-]+$")
_DECIMAL_RE = re.compile(r"^\d+(\.\d+)?$")

_NEIVA = frozenset({"ALM", "BD6", "SUR", "DIS", "BOD"})
_FLORENCIA = frozenset({"FLO"})
_BAJA_ROTACION = frozenset({"B.ROT"})
_EXCLUDED = frozenset({"CON", "CEN", "EXH", "EXD", "BDT", "MDL", "TRA"})


class _InvalidInputError(Exception):
    """Closed-schema input violation (→ entrada_invalida)."""


class _InvalidValue(Exception):
    """Unsignable / non-exact saldo value (→ validacion_fallida)."""


# ---------------------------------------------------------------------------
# Exact fixed-point addition (§9)
# ---------------------------------------------------------------------------


def exact_add(left: Decimal, right: Decimal) -> Decimal:
    """Add two ``Decimal`` values exactly.

    Runs under ``prec=80`` with the ``Inexact`` trap enabled so any rounding
    raises ``decimal.Inexact`` instead of silently losing precision.
    """
    with decimal.localcontext() as ctx:
        ctx.prec = 80
        ctx.traps[decimal.Inexact] = True
        return left + right


# ---------------------------------------------------------------------------
# Exact decimal (§9)
# ---------------------------------------------------------------------------


def _canonicalize(value: Decimal) -> str:
    text = "0" if value == 0 else format(value, "f")
    if not _DECIMAL_RE.fullmatch(text) or Decimal(text) != value:
        raise _InvalidValue
    return text


def _coerce_number(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise _InvalidValue
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise _InvalidValue
        return value
    raise _InvalidValue


# ---------------------------------------------------------------------------
# Input normalization (§2)
# ---------------------------------------------------------------------------


def _upper_ascii(text: str) -> str | None:
    if any(ord(ch) > 127 for ch in text):
        return None
    return text.upper()


def _normalize_one_sku(raw: Any) -> str:
    if not isinstance(raw, str):
        raise _InvalidInputError
    upper = _upper_ascii(raw.strip())
    if (
        upper is None
        or not upper
        or len(upper) > MAX_SKU_LENGTH
        or not _SKU_RE.fullmatch(upper)
    ):
        raise _InvalidInputError
    return upper


def _normalize_sede(raw: Any) -> str:
    if raw is None:
        return "ambas"
    if not isinstance(raw, str):
        raise _InvalidInputError
    value = raw.strip().lower()
    if value not in ("neiva", "florencia"):
        raise _InvalidInputError
    return value


# ---------------------------------------------------------------------------
# Warehouse classification (§6, §7)
# ---------------------------------------------------------------------------


def _normalize_warehouse_code(code: Any) -> str | None:
    if not isinstance(code, str):
        return None
    trimmed = code.strip()
    if not trimmed:
        return None
    return _upper_ascii(trimmed)


def _classify_warehouse(code: str | None) -> str | None:
    if code in _NEIVA:
        return "neiva"
    if code in _FLORENCIA:
        return "florencia"
    if code in _BAJA_ROTACION:
        return "baja_rotacion"
    if code in _EXCLUDED:
        return "excluded"
    return None


# ---------------------------------------------------------------------------
# Row-shape guards (§11)
# ---------------------------------------------------------------------------


def _valid_multiplicity(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _usable_id(value: Any) -> bool:
    if value is None:
        return False
    try:
        hash(value)
    except TypeError:
        return False
    return True
