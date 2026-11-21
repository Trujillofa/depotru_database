"""Offline public catalogue snapshot, published atomically by the nightly job.

No database client is imported by this reader. Counts are individual invoices,
never pair affinity; public prices share quote_search's Decimal/IVA contract.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from business_analyzer.core.quote_search_iva import build_product

SNAPSHOT_ENV = "CATALOG_CATEGORY_SNAPSHOT"
WINDOW_MONTHS = 12
MAX_AGE_DAYS = 5
STOCK_FIELDS = {"website_qty", "in_stock"}


def _valid_product(sku: str, product: Any) -> bool:
    """Accept only the closed, exact public-price shape emitted by the job."""
    if not isinstance(product, dict) or not isinstance(sku, str) or not sku:
        return False
    count = product.get("invoice_count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        return False
    if not isinstance(product.get("name"), str):
        return False
    try:
        price = product.get("j3_price")
        rate = product.get("iva_rate")
        if price is not None and not isinstance(price, str):
            return False
        if rate is not None and not isinstance(rate, str):
            return False
        expected = build_product(
            j3_row={
                "sku": sku,
                "name": product["name"],
                "price": Decimal(price) if price is not None else None,
                "iva_rate": Decimal(rate) if rate is not None else None,
                "line_id": None
                if product.get("price_with_iva_reason") == "line_not_found"
                else 1,
            }
        )
        for key in STOCK_FIELDS:
            expected.pop(key)
        expected["invoice_count"] = count
        return product == expected and all(
            type(product[key]) is type(value) for key, value in expected.items()
        )
    except (InvalidOperation, ValueError, TypeError):
        return False


def snapshot_path() -> Path:
    """Shared default for the job and BFF on the same host/user."""
    return Path(
        os.getenv(SNAPSHOT_ENV) or "~/.cache/depotru/catalog-category-products.json"
    ).expanduser()


def read_snapshot() -> tuple[dict[str, dict[str, Any]], str]:
    """Missing, stale or invalid snapshots never trigger live J3 reads."""
    try:
        payload = json.loads(snapshot_path().read_text(encoding="utf-8"))
        stamp = datetime.fromisoformat(payload["stored_at"])
        now = datetime.now(timezone.utc)
        if not now - timedelta(days=MAX_AGE_DAYS) <= stamp <= now:
            return {}, "presentation_fallback:stale_snapshot"
        if payload["version"] != 1 or payload["window_months"] != WINDOW_MONTHS:
            raise ValueError("snapshot contract")
        products = payload["products"]
        if not isinstance(products, dict):
            raise ValueError("snapshot products")
        for sku, product in products.items():
            if not _valid_product(sku, product):
                raise ValueError("snapshot product")
        return products, "j3_invoice_snapshot"
    except FileNotFoundError:
        return {}, "presentation_fallback:missing_snapshot"
    except (OSError, ValueError, KeyError, TypeError):
        return {}, "presentation_fallback:invalid_snapshot"


def write_snapshot(products: dict[str, dict], path: Path) -> None:
    """Atomic replacement; never expose a partially refreshed catalogue."""
    payload = {
        "version": 1,
        "window_months": WINDOW_MONTHS,
        "stored_at": datetime.now(timezone.utc).isoformat(),
        "products": products,
    }
    encoded = json.dumps(payload, ensure_ascii=False)
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".category-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
