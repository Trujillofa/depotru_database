"""Task 8 — typed B2B quote orchestration (fail-closed).

Server-to-server only: identity (``company_ref``/``terceros_id``) is
resolved server-side by the Magento module and verified staff-side; request
parameters can never switch company (R3). Any ERP failure, missing tariff,
refused tariff (006), or over-limit request fails closed — the route never
falls back to a retail/list price (R11, R22).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Mapping, Optional

from modules.b2b.contracts import (
    CONTRACT_VERSION,
    CURRENCY,
    MAX_SKUS,
    PRICE_INCLUDES_IVA,
    SKU_MAX_LEN,
    UNIT,
    ErpTimeoutError,
    ErpUnavailableError,
    format_amount,
    normalize_sku,
    parse_quantity,
    site_is_valid,
    tariff_is_missing,
    tariff_is_refused,
)

# R4 default TTL alignment: quotes expire after 24h until another value is
# signed. Expiry is enforced again at cart/gate time against the snapshot.
_QUOTE_TTL = timedelta(hours=24)


def _line_error(sku: str, qty: str, error: str) -> dict[str, Any]:
    return {"sku": sku, "qty": qty, "status": "error", "error": error}


def _request_error(reason: str, correlation_id: str) -> dict[str, Any]:
    return {
        "status": "error",
        "reason": reason,
        "correlation_id": correlation_id,
        "contract_version": CONTRACT_VERSION,
    }


def request_quote(
    payload: Any,
    erp: Any,
    *,
    correlation_id: Optional[str] = None,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Validate, dispatch to the ERP tariff boundary, and shape the reply.

    ``erp`` must satisfy the ``B2BErpClient`` protocol (Task 7 tests use a
    fake). ``now``/``correlation_id`` are injectable for tests.
    """
    now = now or datetime.now(timezone.utc)
    corr = correlation_id or uuid.uuid4().hex
    base: dict[str, Any] = {
        "correlation_id": corr,
        "contract_version": CONTRACT_VERSION,
    }

    # --- request-level validation (fail closed before touching the ERP) ----
    if not isinstance(payload, Mapping):
        return {**base, "status": "error", "reason": "items_invalid"}

    company_ref = str(payload.get("company_ref") or "").strip()
    terceros_id = str(payload.get("terceros_id") or "").strip()
    if not company_ref or not terceros_id:
        return {**base, "status": "error", "reason": "identity_required"}

    site_raw = payload.get("site")
    if not site_is_valid(site_raw):
        return {**base, "status": "error", "reason": "site_invalid"}
    site = str(site_raw).strip().lower()

    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return {**base, "status": "error", "reason": "items_invalid"}
    if len(items) > MAX_SKUS:
        return {**base, "status": "error", "reason": "too_many_skus"}

    # --- line validation ----------------------------------------------------
    lines: list[dict[str, Any]] = []
    erp_skus: list[str] = []
    parsed: dict[str, Any] = {}
    for item in items:
        if not isinstance(item, Mapping):
            lines.append(_line_error("", "", "invalid_item"))
            continue
        sku = normalize_sku(item.get("sku")) or ""
        raw_qty = item.get("qty")
        qty_str = "" if raw_qty is None else str(raw_qty).strip()
        if len(sku) > SKU_MAX_LEN:
            lines.append(_line_error(sku, qty_str, "sku_too_long"))
            continue
        qty = parse_quantity(raw_qty)
        if qty is None:
            lines.append(_line_error(sku, qty_str, "invalid_qty"))
            continue
        if not sku:
            lines.append(_line_error(sku, qty_str, "sku_required"))
            continue
        lines.append({"sku": sku, "qty": format_amount(qty), "_qty": qty})
        erp_skus.append(sku)
        parsed[sku] = qty

    # --- ERP dispatch (the only price source; fail closed) -----------------
    rows: dict[str, dict[str, Any]] = {}
    if erp_skus:
        try:
            for row in erp.customer_quote(site, terceros_id, erp_skus):
                if isinstance(row, Mapping) and row.get("sku") is not None:
                    rows[str(row["sku"])] = dict(row)
        except ErpTimeoutError:
            return {
                **base,
                "status": "unavailable",
                "reason": "erp_timeout",
                "lines": [],
            }
        except ErpUnavailableError:
            return {
                **base,
                "status": "unavailable",
                "reason": "erp_unavailable",
                "lines": [],
            }
        except Exception:  # noqa: BLE001 — unknown ERP failure fails closed
            return {
                **base,
                "status": "unavailable",
                "reason": "erp_unavailable",
                "lines": [],
            }

    # --- price resolution (never a retail fallback) -------------------------
    for line in lines:
        if line.get("status") == "error":
            continue
        sku = str(line["sku"])
        line_qty: Any = line.pop("_qty", None)
        row = rows.get(sku)
        if row is None:
            line["status"] = "error"
            line["error"] = "unknown_sku"
            continue
        tariff_id = row.get("tariff_id")
        tariff_code = row.get("tariff_code")
        tariff_name = row.get("tariff_name")
        if tariff_is_missing(tariff_id, tariff_code):
            line["status"] = "error"
            line["error"] = "missing_tariff"
            continue
        if tariff_is_refused(tariff_id, tariff_code, tariff_name):
            line["status"] = "error"
            line["error"] = "refused_tariff"
            continue
        net_price = row.get("net_price")
        if not isinstance(net_price, (int, Decimal)) or isinstance(net_price, bool):
            line["status"] = "error"
            line["error"] = "missing_price"
            continue
        net = net_price if isinstance(net_price, Decimal) else Decimal(net_price)
        line["status"] = "ok"
        line["unit_net_price"] = format_amount(net)
        line["line_total"] = format_amount(net * line_qty)
        line["unit"] = UNIT

    expires_at = now + _QUOTE_TTL
    return {
        **base,
        "status": "ok",
        "quote_reference": (f"B2B-{now.strftime('%Y%m%d%H%M%S')}-{corr[:8].upper()}"),
        "company_ref": company_ref,
        "terceros_id": terceros_id,
        "site": site,
        "currency": CURRENCY,
        "price_includes_iva": PRICE_INCLUDES_IVA,
        "lines": lines,
        "timestamp": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    }
