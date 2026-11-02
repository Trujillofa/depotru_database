"""Product search against the public storefront (Magento GraphQL).

The ERP names an article for its own warehouse («PISO ARANDA GRIS 50X50
C*2.25M») and files it under categories that are not the ones customers see.
The storefront names the same article for the customer («Piso Cerámico Aranda
Gris 50 X 50 C*2.25M Eurocerámica»), describes it, and files it under the words
people actually say: «Revestimiento» → «Cerámica» → «Piso para interior».

Its search index covers name, description and category, so it answers words
that appear in no ERP article name at all. «Revestimiento» is the case that
matters: it is a category, not a product, and the ERP never says it.

Two steps, because one is not enough:

1. the customer's word is matched against the **category names** (that is where
   «revestimiento» lives);
2. the products of those categories are searched with the remaining words
   («piso»), so «revestimiento para piso» returns floors, not mortar that
   happens to mention revestimiento in its description.

Read-only, no credentials: it uses the same public GraphQL endpoint as
``brand_categories``. Price and quantity are NOT read here: those belong to J3.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from depotru_integrations.magento.categories import post_graphql

MAX_QUERY_LEN = 80
DEFAULT_LIMIT = 5
MAX_LIMIT = 10
MAX_CATEGORIES = 4
DESCRIPTION_CHARS = 240

_CATEGORY_QUERY = """
query StorefrontCategories($term: String!, $size: Int!) {
  categories(filters: {name: {match: $term}}, pageSize: $size) {
    items { uid name url_path }
  }
}
"""

_PRODUCTS_IN_CATEGORIES = """
query StorefrontProducts($term: String!, $size: Int!, $uids: [String!]) {
  products(filter: {category_uid: {in: $uids}}, search: $term, pageSize: $size) {
    total_count
    items { sku name url_key description { html } categories { name url_path } }
  }
}
"""

_PRODUCTS_BY_SEARCH = """
query StorefrontSearch($term: String!, $size: Int!) {
  products(search: $term, pageSize: $size) {
    total_count
    items { sku name url_key description { html } categories { name url_path } }
  }
}
"""

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


class StorefrontQueryError(ValueError):
    """The word the customer used cannot be sent to the storefront."""


def normalize_query(query: str) -> str:
    """A product word, not a query language: letters, digits and separators."""
    value = " ".join((query or "").split())
    if not value:
        raise StorefrontQueryError("query_required")
    if len(value) > MAX_QUERY_LEN:
        value = value[:MAX_QUERY_LEN].strip()
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789 &.-/'x")
    if not set(value.lower()) <= allowed:
        raise StorefrontQueryError("query_invalid_characters")
    return value


def _plain_text(html: str) -> str:
    return _SPACE_RE.sub(" ", _TAG_RE.sub(" ", html or "")).strip()


def _categories(item: Dict[str, Any]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for raw in item.get("categories") or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if name:
            out.append({"name": name, "url_path": str(raw.get("url_path") or "")})
    return out


def _product(item: Dict[str, Any]) -> Dict[str, Any]:
    from depotru_tools.builtins import storefront_product_url

    url_key = str(item.get("url_key") or "").strip()
    description = item.get("description") or {}
    html = description.get("html") if isinstance(description, dict) else ""
    return {
        "sku": str(item.get("sku") or ""),
        "name": str(item.get("name") or "").strip(),
        "url_key": url_key,
        "product_url": storefront_product_url(url_key) if url_key else "",
        "description": _plain_text(str(html or ""))[:DESCRIPTION_CHARS],
        "categories": _categories(item),
    }


def _products(block: Any) -> tuple[List[Dict[str, Any]], int]:
    if not isinstance(block, dict):
        return [], 0
    items = block.get("items") or []
    products = [_product(item) for item in items if isinstance(item, dict)]
    products = [product for product in products if product["sku"] and product["name"]]
    return products, int(block.get("total_count") or 0)


def _match_categories(term: str) -> List[Dict[str, str]]:
    data = post_graphql(_CATEGORY_QUERY, {"term": term, "size": MAX_CATEGORIES})
    items = (data.get("categories") or {}).get("items") or []
    out: List[Dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        uid = str(item.get("uid") or "").strip()
        name = str(item.get("name") or "").strip()
        if uid and name:
            out.append(
                {"uid": uid, "name": name, "url_path": str(item.get("url_path") or "")}
            )
    return out


def _resolve_category(term: str) -> tuple[List[Dict[str, str]], str]:
    """Categoría que nombra el cliente y palabras que quedan para buscar.

    «revestimiento para piso» no es el nombre de ninguna categoría, pero
    «revestimiento» sí: se busca la palabra más larga y el resto («piso») se
    usa como búsqueda dentro de esa categoría. Sin esto, la frase entera caía
    en la búsqueda libre y devolvía mortero.
    """
    matched = _match_categories(term)
    if matched:
        return matched, term
    words = [word for word in term.split() if len(word) >= 4]
    for word in sorted(words, key=len, reverse=True):
        matched = _match_categories(word)
        if matched:
            rest = " ".join(other for other in term.split() if other != word)
            return matched, rest
    return [], term


def search_storefront(query: str, limit: int = DEFAULT_LIMIT) -> Dict[str, Any]:
    """Products of the storefront that match the customer's words.

    ``status`` is ``ok`` (with products), ``empty`` (the storefront answered and
    has nothing for those words) or ``error`` (with ``reason``). The caller must
    be able to tell "there is nothing" from "I could not ask".
    """
    try:
        term = normalize_query(query)
    except StorefrontQueryError as exc:
        return {
            "query": (query or "").strip(),
            "products": [],
            "count": 0,
            "total_count": 0,
            "source": "ecommerce",
            "status": "error",
            "reason": str(exc),
            "matched_categories": [],
        }

    size = max(1, min(int(limit), MAX_LIMIT))
    matched: List[Dict[str, str]] = []
    products: List[Dict[str, Any]] = []
    total = 0

    try:
        matched, search_term = _resolve_category(term)
        if matched:
            block = post_graphql(
                _PRODUCTS_IN_CATEGORIES,
                {
                    "term": search_term or term,
                    "size": size,
                    "uids": [c["uid"] for c in matched],
                },
            )
            products, total = _products(block.get("products"))
        if not products:
            block = post_graphql(_PRODUCTS_BY_SEARCH, {"term": term, "size": size})
            products, total = _products(block.get("products"))
    except Exception as exc:  # noqa: BLE001 — the tool must explain, not crash
        return {
            "query": term,
            "products": [],
            "count": 0,
            "total_count": 0,
            "source": "ecommerce",
            "status": "error",
            "reason": f"storefront_unavailable: {str(exc)[:160]}",
            "matched_categories": [],
        }

    return {
        "query": term,
        "products": products[:size],
        "count": len(products[:size]),
        "total_count": total,
        "source": "ecommerce",
        "status": "ok" if products else "empty",
        # La categoría es el puente de vocabulario: sin ella, «revestimiento»
        # no se puede explicar y el asesor vuelve a contestar «no lo tengo».
        "matched_categories": matched,
    }
