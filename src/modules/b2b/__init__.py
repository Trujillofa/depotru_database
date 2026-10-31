"""B2B BFF module (Phase 1): typed quote, credit, and order contracts.

Fail-closed by design: R11 (no retail fallback), R12 (no warehouse qty),
R14 (credit blocked), R15 (ERP submit disabled), R22 (dedicated audience).
"""

from modules.b2b.contracts import (
    CURRENCY,
    SKU_MAX_LEN,
    UNIT,
    ErpTimeoutError,
    ErpUnavailableError,
)

__all__ = [
    "CURRENCY",
    "SKU_MAX_LEN",
    "UNIT",
    "ErpTimeoutError",
    "ErpUnavailableError",
]
