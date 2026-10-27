"""Task 9 — fail-closed credit contract (R14: blocked).

``banco_cartera``/``cliente_cupo`` are AR snapshots and
``CarCarteraCliente`` is ERP AR truth — neither is an atomic reserve API.
Until the owner provides a live source, a freshness formula, and atomic
reserve semantics, the credit endpoint answers ``unavailable`` and never
exposes an available-credit amount for checkout.
"""

from __future__ import annotations

from typing import Any

CREDIT_STATUS_UNAVAILABLE = "unavailable"
CREDIT_REASON = "credit_terms_blocked_r14"


def credit_status(terceros_id: Any, erp: Any = None) -> dict[str, Any]:
    """Always fail closed while R14 is blocked.

    ``erp`` is accepted (and deliberately ignored) so a future live module
    can slot in behind an owner-approved contract without changing callers.
    No snapshot table, no ERP payload, and no numeric amount may leak.
    """
    return {
        "terceros_id": str(terceros_id or "").strip(),
        "credit_status": CREDIT_STATUS_UNAVAILABLE,
        "available_credit": None,
        "currency": None,
        "reason": CREDIT_REASON,
        "source": None,
    }
