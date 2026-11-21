"""Browse a brand's stable category path, ranked by offline invoice totals."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from business_analyzer.core.quote_search_iva import build_product
from depotru_integrations.affinity.category_snapshot import STOCK_FIELDS, read_snapshot
from depotru_integrations.magento import categories

WINDOW = 40

_QUERY = """
query CategoryBrandProducts($id: String!, $size: Int!, $page: Int!) {
  products(filter: {brand: {eq: $id}}, pageSize: $size, currentPage: $page,
           sort: {name: ASC}) {
    total_count
    items { sku name url_key categories { name url_path } }
  }
}
"""
# Normalize mass/volume only within their own dimension; no kg-vs-l ranking.
_PRESENTATION = re.compile(
    r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s*(kg|gr|g|ml|litros?|lt|l)\b", re.I
)
_UNITS = {
    "kg": ("mass", Decimal(1000)),
    "gr": ("mass", Decimal(1)),
    "g": ("mass", Decimal(1)),
    "ml": ("volume", Decimal(1)),
    "l": ("volume", Decimal(1000)),
    "lt": ("volume", Decimal(1000)),
    "litro": ("volume", Decimal(1000)),
    "litros": ("volume", Decimal(1000)),
}


def _presentation(name: str) -> tuple[str, Decimal]:
    match = _PRESENTATION.search(name)
    if not match:
        return "unknown", Decimal(0)
    dimension, multiplier = _UNITS[match[2].lower()]
    return dimension, Decimal(match[1].replace(",", ".")) * multiplier


def _rank(products: list[dict], counts: dict[str, int]) -> list[dict]:
    # Equal-sales groups keep deterministic dimension slots; sorting only the
    # members of each dimension avoids pretending 1 litre < 2 kilograms.
    ordered = sorted(products, key=lambda p: (-counts.get(p["sku"], 0), p["sku"]))
    groups: dict[tuple[int, str], list[int]] = {}
    for index, product in enumerate(ordered):
        dimension, _ = _presentation(product["name"])
        groups.setdefault((counts.get(product["sku"], 0), dimension), []).append(index)
    for (_, dimension), indices in groups.items():
        if dimension == "unknown":
            continue
        members = sorted(
            (ordered[index] for index in indices),
            key=lambda p: (_presentation(p["name"])[1], p["sku"]),
        )
        for index, member in zip(indices, members):
            ordered[index] = member
    return ordered


def category_products(brand: Any, url_path: Any) -> dict:
    """Forty internal options; the inbox owns its six-visible-item window.

    Only Magento public taxonomy is live. Both sales and J3 public prices come
    from the nightly snapshot. Missing snapshots leave prices null, never guessed.
    """
    result: dict[str, Any] = {
        "brand": brand if isinstance(brand, str) else "",
        "url_path": url_path if isinstance(url_path, str) else "",
        "products": [],
        "count": 0,
        "source": "none",
    }
    try:
        clean_brand = categories.normalize_brand(result["brand"])
        path = result["url_path"]
        if (
            not path
            or len(path) > 500
            or not re.fullmatch(r"[a-z0-9_-]+(?:/[a-z0-9_-]+)*", path)
        ):
            raise ValueError("url_path_invalid")
    except ValueError as exc:
        return {**result, "status": "error", "reason": str(exc)}

    try:
        brand_id = categories.resolve_brand_id(clean_brand)
        if brand_id is None:
            return {**result, "status": "empty", "reason": "brand_not_in_storefront"}
        items: dict[str, dict] = {}
        scanned = 0
        total = 0
        for page in range(1, categories.MAX_PAGES + 1):
            data = categories.post_graphql(
                _QUERY, {"id": brand_id, "size": categories.PAGE_SIZE, "page": page}
            )
            block = data["products"]
            total = int(block["total_count"])
            rows = block["items"]
            if not isinstance(rows, list):
                raise ValueError("unreadable products")
            scanned += len(rows)
            for item in rows:
                paths = [c.get("url_path") or "" for c in item["categories"]]
                if not any(p == path or p.startswith(path + "/") for p in paths):
                    continue
                sku = str(item["sku"]).strip()
                if sku and item.get("name"):
                    items.setdefault(sku, item)
            if scanned >= total:
                break
            if not rows:
                raise ValueError("incomplete products")
        if scanned < total:
            # Do not claim a sales-ranked window over an arbitrary partial set.
            return {**result, "status": "error", "reason": "brand_catalog_truncated"}
    except Exception:  # noqa: BLE001 - no URLs/credentials/driver details to public
        return {**result, "status": "error", "reason": "catalog_unavailable"}

    snapshot, source = read_snapshot()
    if source == "j3_invoice_snapshot" and any(sku not in snapshot for sku in items):
        # Newly listed Magento SKUs are not zero-sale observations in J3.
        # Use a homogeneous presentation-only ranking until the next refresh.
        source = "presentation_fallback:incomplete_snapshot"
    products = []
    counts = {}
    from depotru_tools.builtins import storefront_product_url

    for sku, item in items.items():
        saved = snapshot.get(sku)
        product = dict(saved) if saved else build_product(magento=item)
        count = product.pop("invoice_count", 0)
        counts[sku] = count if source == "j3_invoice_snapshot" else 0
        product["name"] = item["name"]
        product["product_url"] = storefront_product_url(item.get("url_key") or "")
        for key in STOCK_FIELDS:
            product.pop(key, None)
        products.append(product)
    ranked = _rank(products, counts)[:WINDOW]
    return {
        **result,
        "status": "ok" if ranked else "empty",
        "source": source,
        "window_months": 12,
        "products": ranked,
        "count": len(ranked),
        "total_count": len(products),
        "has_more": len(products) > WINDOW,
    }
