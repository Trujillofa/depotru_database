"""ERP client boundary for B2B customer quotes (candidate contract).

The customer-quote ERP contract is NOT released (docs/b2b/erp-contract.md):
the only known candidate lives uncommitted on a dirty checkout, and the
Task 5 transactional decision is a written ``blocked``. The real client is
therefore gated behind ``B2B_ERP_MODE=j3`` and fails closed otherwise.

When the contract is released, the query must be parameterized and
allowlisted — never interpolate an identifier. Sketch of the intended shape
(NOT executed here)::

    SELECT p.PreciosValor, p.TarifasID, p.Cantidad
    FROM AdmPrecios p
    WHERE p.ArticulosID = %s AND p.TarifasID = %s AND p.Cantidad = 0

with ``TarifasID`` resolved server-side from the staff-linked
``TercerosID`` — never from a browser-supplied parameter.
"""

from __future__ import annotations

import os
from typing import Any, Protocol, Sequence

from modules.b2b.contracts import ErpUnavailableError


class B2BErpClient(Protocol):
    """Read-only customer-tariff boundary. No writes, ever."""

    def customer_quote(
        self, site: str, terceros_id: str, skus: Sequence[str]
    ) -> list[dict[str, Any]]:
        """Return price rows for the customer's tariff; rows are dicts with
        ``sku``, ``net_price`` (Decimal), ``tariff_id``, ``tariff_code``,
        ``tariff_name``."""
        ...  # pragma: no cover


class J3CustomerQuoteClient:
    """Real client — disabled until the customer-quote contract is released.

    Fail closed: any caller before release gets ``ErpUnavailableError`` and
    the quote route answers ``status=unavailable``. Never fall back to the
    public list price (``AdmArticulos.ArticulosVenta`` / catalog.quote_search).
    """

    def customer_quote(
        self, site: str, terceros_id: str, skus: Sequence[str]
    ) -> list[dict[str, Any]]:
        mode = (os.getenv("B2B_ERP_MODE") or "").strip().lower()
        if mode != "j3":
            raise ErpUnavailableError("b2b_erp_disabled")
        raise ErpUnavailableError("customer_quote_contract_not_released")


def get_b2b_erp_client() -> B2BErpClient:
    """Single supported entry point for tool handlers."""
    return J3CustomerQuoteClient()
