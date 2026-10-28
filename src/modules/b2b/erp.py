"""ERP client boundary for B2B customer quotes.

When ``B2B_ERP_MODE=j3`` the client reads ``AdmPrecios`` at ``Cantidad = 0``
for the staff-linked ``TercerosID`` tariff (see ``j3_customer_quote``). Any
other mode fails closed. Never fall back to the public list price
(``AdmArticulos.ArticulosVenta`` / ``catalog.quote_search``).
"""

from __future__ import annotations

import os
from typing import Any, Callable, Optional, Protocol, Sequence, cast

from modules.b2b.contracts import ErpTimeoutError, ErpUnavailableError
from modules.b2b.j3_customer_quote import fetch_customer_quote

_TIMEOUT_MARKERS = ("timeout", "timed out", "10060")


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
    """J3 ``AdmPrecios`` customer quote. Requires ``B2B_ERP_MODE=j3``."""

    def __init__(self, db_factory: Optional[Callable[[], Any]] = None) -> None:
        self._db_factory = db_factory

    def customer_quote(
        self, site: str, terceros_id: str, skus: Sequence[str]
    ) -> list[dict[str, Any]]:
        mode = (os.getenv("B2B_ERP_MODE") or "").strip().lower()
        if mode != "j3":
            raise ErpUnavailableError("b2b_erp_disabled")
        try:
            if self._db_factory is not None:
                return cast(
                    list[dict[str, Any]],
                    fetch_customer_quote(self._db_factory(), site, terceros_id, skus),
                )
            from business_analyzer.core.database import Database

            with Database(suppress_error_details=True) as db:
                return cast(
                    list[dict[str, Any]],
                    fetch_customer_quote(db, site, terceros_id, skus),
                )
        except (ErpUnavailableError, ErpTimeoutError):
            raise
        except Exception as exc:  # noqa: BLE001 — unknown J3 failure fails closed
            text = str(exc).lower()
            if any(marker in text for marker in _TIMEOUT_MARKERS):
                raise ErpTimeoutError("j3_timeout") from exc
            raise ErpUnavailableError("j3_unavailable") from exc


def get_b2b_erp_client() -> B2BErpClient:
    """Single supported entry point for tool handlers."""
    return J3CustomerQuoteClient()
