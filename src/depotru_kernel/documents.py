"""Canonical document-type filters for sales analytics.

CRITICAL: always exclude test / non-commercial document codes when querying
``banco_datos`` or derived sales facts.
"""

from __future__ import annotations

from typing import Sequence, Tuple

# Canonical five-code exclusion list (source of truth for the platform).
# Matches ``config.Config.EXCLUDED_DOCUMENT_CODES`` and AGENTS.md guidance.
CANONICAL_EXCLUDED_DOCUMENT_CODES: Tuple[str, ...] = (
    "XY",
    "AS",
    "TS",
    "YX",
    "ISC",
)


def excluded_document_codes(
    extra: Sequence[str] | None = None,
) -> Tuple[str, ...]:
    """Return excluded codes, optionally extended (deduped, order-preserving)."""
    codes = list(CANONICAL_EXCLUDED_DOCUMENT_CODES)
    if extra:
        for code in extra:
            c = (code or "").strip().upper()
            if c and c not in codes:
                codes.append(c)
    return tuple(codes)


def excluded_document_sql_in_list(
    extra: Sequence[str] | None = None,
) -> str:
    """SQL fragment for ``NOT IN (...)`` with quoted codes (static constants only)."""
    codes = excluded_document_codes(extra)
    return ", ".join(f"'{c}'" for c in codes)
