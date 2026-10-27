"""Category tree of one brand, read from the Ecommerce storefront.

The J3 category columns are not customer-facing (most of Pintuco sits in
``OTRAS``); the storefront is the source of truth for how the catalogue is
organised for customers. This module resolves the brand in the storefront's
``brand`` attribute, reads every product of it and folds their categories into
a two-level tree.

Read-only, no credentials: it only uses the public storefront GraphQL endpoint.
"""

from __future__ import annotations

import json
import os
import time
import unicodedata
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_STOREFRONT = "https://www.depositotrujillo.co"
GRAPHQL_PATH = "/graphql"
TIMEOUT_SEC = 20.0
MAX_BRAND_LEN = 40
PAGE_SIZE = 100
MAX_PAGES = 6
CACHE_TTL_SEC = 600.0

_BRAND_OPTIONS_QUERY = """
query BrandOptions {
  customAttributeMetadata(
    attributes: [{attribute_code: "brand", entity_type: "4"}]
  ) {
    items { attribute_options { label value } }
  }
}
"""

_BRAND_PRODUCTS_QUERY = """
query BrandProducts($id: String!, $size: Int!, $page: Int!) {
  products(filter: {brand: {eq: $id}}, pageSize: $size, currentPage: $page) {
    total_count
    items {
      sku
      name
      categories { id name url_path level }
    }
  }
}
"""

_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
_brand_options_cache: Optional[tuple[float, Dict[str, str]]] = None


class BrandQueryError(ValueError):
    """The brand cannot be used as a catalogue query."""


def graphql_url() -> str:
    base = (
        os.getenv("MAGENTO_GRAPHQL_URL")
        or os.getenv("MAGENTO_STOREFRONT_URL")
        or os.getenv("MAGENTO_BASE_URL")
        or DEFAULT_STOREFRONT
    ).rstrip("/")
    if base.endswith(GRAPHQL_PATH):
        return base
    return f"{base}{GRAPHQL_PATH}"


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", (text or "").lower())
    return " ".join(
        "".join(ch for ch in decomposed if not unicodedata.combining(ch)).split()
    )


def normalize_brand(brand: str) -> str:
    """A brand is a name, not a query language: letters, digits and separators."""
    value = " ".join((brand or "").split())
    if not value:
        raise BrandQueryError("brand_required")
    if len(value) > MAX_BRAND_LEN:
        raise BrandQueryError("brand_too_long")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789 &.-'")
    if not set(value.lower()) <= allowed:
        raise BrandQueryError("brand_invalid_characters")
    return value


def _post_query(query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = Request(
        graphql_url(),
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=TIMEOUT_SEC) as response:  # nosec B310
        raw = response.read().decode("utf-8")
    payload = json.loads(raw) if raw else {}
    if not isinstance(payload, dict):
        return {}
    errors = payload.get("errors")
    if errors:
        raise RuntimeError(f"GraphQL errors: {str(errors)[:200]}")
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def brand_options() -> Dict[str, str]:
    """Folded brand label -> storefront option id, cached for ten minutes."""
    global _brand_options_cache
    if (
        _brand_options_cache is not None
        and time.monotonic() - _brand_options_cache[0] < CACHE_TTL_SEC
    ):
        return _brand_options_cache[1]
    data = _post_query(_BRAND_OPTIONS_QUERY, {})
    items = (data.get("customAttributeMetadata") or {}).get("items") or []
    options: Dict[str, str] = {}
    for block in items:
        if not isinstance(block, dict):
            continue
        for option in block.get("attribute_options") or []:
            if not isinstance(option, dict):
                continue
            label = _fold(str(option.get("label") or ""))
            value = str(option.get("value") or "").strip()
            if label and value:
                options.setdefault(label, value)
    _brand_options_cache = (time.monotonic(), options)
    return options


def resolve_brand_id(brand: str) -> Optional[str]:
    """Exact label first, then a unique prefix ("pintuc" -> PINTUCO)."""
    options = brand_options()
    wanted = _fold(brand)
    if wanted in options:
        return options[wanted]
    prefixed = {value for label, value in options.items() if label.startswith(wanted)}
    if len(prefixed) == 1:
        return prefixed.pop()
    return None


def _category_of_product(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    categories = item.get("categories")
    if not isinstance(categories, list):
        return None
    usable = [
        category
        for category in categories
        if isinstance(category, dict) and category.get("url_path")
    ]
    if not usable:
        return None
    return max(usable, key=lambda category: int(category.get("level") or 0))


def _parent_of(
    category: Dict[str, Any], categories: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    path = str(category.get("url_path") or "")
    if "/" not in path:
        return None
    parent_path = path.rsplit("/", 1)[0]
    for candidate in categories:
        if isinstance(candidate, dict) and candidate.get("url_path") == parent_path:
            return candidate
    return {
        "name": parent_path.rsplit("/", 1)[-1].replace("-", " "),
        "url_path": parent_path,
        "level": int(category.get("level") or 2) - 1,
    }


def _label(category: Dict[str, Any]) -> str:
    return " ".join(str(category.get("name") or "").split())


def _tree(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tree: Dict[str, Dict[str, Any]] = {}
    for item in products:
        deepest = _category_of_product(item)
        if deepest is None:
            continue
        parent = _parent_of(deepest, item.get("categories") or [])
        sub_name = _label(deepest)
        sub_path = str(deepest.get("url_path"))
        if parent is None:
            node = tree.setdefault(
                sub_path,
                {
                    "name": sub_name,
                    "url_path": sub_path,
                    "products": 0,
                    "subcategories": [],
                },
            )
            node["products"] += 1
            continue
        parent_path = str(parent.get("url_path"))
        node = tree.setdefault(
            parent_path,
            {
                "name": _label(parent),
                "url_path": parent_path,
                "products": 0,
                "subcategories": [],
            },
        )
        node["products"] += 1
        found = next(
            (sub for sub in node["subcategories"] if sub["url_path"] == sub_path), None
        )
        if found is None:
            node["subcategories"].append(
                {"name": sub_name, "url_path": sub_path, "products": 1}
            )
        else:
            found["products"] += 1
    categories = sorted(
        tree.values(), key=lambda node: (-node["products"], node["name"])
    )
    for node in categories:
        node["subcategories"].sort(key=lambda sub: (-sub["products"], sub["name"]))
    return categories


def brand_category_overview(brand: str) -> Dict[str, Any]:
    """Categories and subcategories of one brand, as the storefront has them."""
    try:
        value = normalize_brand(brand)
    except BrandQueryError as exc:
        return {
            "brand": brand,
            "status": "error",
            "reason": str(exc),
            "categories": [],
        }

    cache_key = _fold(value)
    cached = _cache.get(cache_key)
    if cached is not None and time.monotonic() - cached[0] < CACHE_TTL_SEC:
        return cached[1]

    try:
        brand_id = resolve_brand_id(value)
    except (HTTPError, URLError, RuntimeError, json.JSONDecodeError, OSError):
        return {
            "brand": value,
            "status": "error",
            "reason": "upstream_error",
            "categories": [],
        }
    if brand_id is None:
        missing: Dict[str, Any] = {
            "brand": value,
            "status": "empty",
            "reason": "brand_not_in_storefront",
            "categories": [],
        }
        _cache[cache_key] = (time.monotonic(), missing)
        return missing

    products: List[Dict[str, Any]] = []
    total_count = 0
    for page in range(1, MAX_PAGES + 1):
        try:
            data = _post_query(
                _BRAND_PRODUCTS_QUERY,
                {"id": brand_id, "size": PAGE_SIZE, "page": page},
            )
        except (HTTPError, URLError, RuntimeError, json.JSONDecodeError, OSError):
            return {
                "brand": value,
                "status": "error",
                "reason": "upstream_error",
                "categories": [],
            }
        block = data.get("products") if isinstance(data, dict) else None
        if not isinstance(block, dict):
            break
        total_count = int(block.get("total_count") or 0)
        items = block.get("items")
        if not isinstance(items, list) or not items:
            break
        products.extend(item for item in items if isinstance(item, dict))
        if len(products) >= total_count:
            break

    categories = _tree(products)
    result: Dict[str, Any] = {
        "brand": value,
        "brand_id": brand_id,
        "status": "ok" if categories else "empty",
        "matched_products": len(products),
        "total_count": total_count,
        "categories": categories,
        "source": "ecommerce",
    }
    _cache[cache_key] = (time.monotonic(), result)
    return result


def reset_cache() -> None:
    global _brand_options_cache
    _cache.clear()
    _brand_options_cache = None
