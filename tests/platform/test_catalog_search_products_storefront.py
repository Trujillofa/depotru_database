"""catalog.search_products: la tienda primero, el histórico como respaldo.

La herramienta decía «Magento and/or sales history» y nunca llegaba a Magento:
sin credenciales REST, buscaba ``name LIKE`` (que no encuentra categorías) y se
tragaba el error. Ahora pregunta al storefront GraphQL —el mismo endpoint
público que usa ``brand_categories``— y, si no puede, lo dice.
"""

from __future__ import annotations

import pytest

from depotru_integrations.magento import storefront as storefront_module
from depotru_kernel.auth import Audience
from depotru_tools.builtins import _tool_search_products
from depotru_tools.registry import ToolContext

CTX = ToolContext(audience=Audience.PUBLIC)


@pytest.fixture(autouse=True)
def _fresh_category_cache():
    # El catálogo se cachea; entre pruebas cada una tiene su propio mago.
    storefront_module._cached_categories.cache_clear()
    yield
    storefront_module._cached_categories.cache_clear()


REVESTIMIENTO_CATEGORIES = {
    "categories": {
        "items": [
            {"uid": "NTk=", "name": "Revestimiento", "url_path": "revestimiento"},
        ]
    }
}

PISO_ITEMS = [
    {
        "sku": "0060440386",
        "name": "Piso Cerámico Aranda Gris 50 X 50 C*2.25M Eurocerámica",
        "url_key": "piso-ceramico-aranda-gris-50-x-50",
        "description": {"html": "<p>Piso <strong>cerámico</strong> para interior</p>"},
        "categories": [
            {"name": "Revestimiento", "url_path": "revestimiento"},
            {"name": "Ceramica", "url_path": "revestimiento/ceramica"},
        ],
    },
    {
        "sku": "0060450235",
        "name": "Fachaleta Missouri 30.5x45 C*1.78 M",
        "url_key": "fachaleta-missouri-30-5x45",
        "description": {"html": ""},
        "categories": [{"name": "Revestimiento", "url_path": "revestimiento"}],
    },
]


class FakeStorefront:
    """Answers the three GraphQL shapes the module sends, in order."""

    def __init__(self, categories=None, products=None, raw=None):
        self.categories = categories
        self.products = products
        self.raw = raw
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, query: str, variables: dict) -> dict:
        self.calls.append((query, variables))
        if isinstance(self.raw, Exception):
            raise self.raw
        if "categories(" in query:
            if self.categories is not None:
                # La categoría existe con la palabra suelta, no con la frase.
                if variables.get("term") in ("revestimiento", "aranda"):
                    return self.categories
                return {"categories": {"items": []}}
            return {"categories": {"items": []}}
        return {"products": {"total_count": 148, "items": (self.products or [])}}


@pytest.mark.unit
def test_category_name_is_the_bridge_for_a_word_the_erp_never_uses(monkeypatch):
    fake = FakeStorefront(categories=REVESTIMIENTO_CATEGORIES, products=PISO_ITEMS)
    monkeypatch.setattr(storefront_module, "post_graphql", fake)

    result = _tool_search_products(
        CTX, {"query": "revestimiento para piso", "limit": 5}
    )

    assert result["source"] == "ecommerce"
    assert result["status"] == "ok"
    assert result["total_count"] == 148
    assert result["reason"] if "reason" in result else True
    # La categoría se buscó por nombre y los productos se filtraron por su uid:
    # sin ese filtro, «revestimiento» devuelve mortero y ofertas.
    product_call = [c for c in fake.calls if "category_uid" in c[0]][0]
    assert "categories(" in fake.calls[0][0]
    assert product_call[1]["uids"] == ["NTk="]
    assert "reason" not in result


@pytest.mark.unit
def test_a_phrase_finds_the_category_by_its_strongest_word(monkeypatch):
    fake = FakeStorefront(categories=REVESTIMIENTO_CATEGORIES, products=PISO_ITEMS)
    monkeypatch.setattr(storefront_module, "post_graphql", fake)

    _tool_search_products(CTX, {"query": "revestimiento para piso"})

    # Primero la frase entera; al no existir esa categoría, la palabra que sí
    # la nombra; y dentro de ella se busca el resto («para piso»).
    terms = [call[1].get("term") for call in fake.calls]
    assert terms[0] == "revestimiento para piso"
    assert "revestimiento" in terms
    product_call = [c for c in fake.calls if "category_uid" in c[0]][0]
    assert product_call[1]["uids"] == ["NTk="]
    assert "piso" in product_call[1]["term"]


@pytest.mark.unit
def test_customer_name_is_used_verbatim_not_the_erp_name(monkeypatch):
    fake = FakeStorefront(categories=REVESTIMIENTO_CATEGORIES, products=PISO_ITEMS)
    monkeypatch.setattr(storefront_module, "post_graphql", fake)

    result = _tool_search_products(CTX, {"query": "revestimiento", "limit": 5})
    first = result["products"][0]

    assert first["name"].startswith("Piso Cerámico Aranda")
    assert first["categories"][0]["name"] == "Revestimiento"
    assert first["description"] == "Piso cerámico para interior"
    assert first["product_url"].endswith(".html")


@pytest.mark.unit
def test_without_a_matching_category_it_searches_the_storefront_anyway(monkeypatch):
    fake = FakeStorefront(products=PISO_ITEMS)
    monkeypatch.setattr(storefront_module, "post_graphql", fake)

    _tool_search_products(CTX, {"query": "aranda"})

    assert "categories(" in fake.calls[0][0]
    assert "category_uid" not in fake.calls[1][0]
    assert fake.calls[1][1]["term"] == "aranda"


@pytest.mark.unit
def test_storefront_empty_falls_back_to_sales_history(monkeypatch):
    fake = FakeStorefront(products=[])
    fake_empty = {"products": {"total_count": 0, "items": []}}
    fake.products = []
    monkeypatch.setattr(storefront_module, "post_graphql", lambda q, v: fake_empty)
    monkeypatch.setattr(
        "depotru_tools.builtins._search_products_db",
        lambda query, limit=5: [{"sku": "1", "name": "CEMENTO GRIS", "qty_sold": "10"}],
    )
    result = _tool_search_products(CTX, {"query": "cemento gris"})

    assert result["source"] == "banco_datos"
    assert result["count"] == 1


@pytest.mark.unit
def test_storefront_failure_is_visible_not_hidden(monkeypatch):
    fake = FakeStorefront(raw=None)
    fake.raw = RuntimeError("GraphQL errors: boom")
    monkeypatch.setattr(storefront_module, "post_graphql", fake)
    monkeypatch.setattr(
        "depotru_tools.builtins._search_products_db",
        lambda query, limit=5: [{"sku": "1", "name": "CEMENTO GRIS", "qty_sold": "10"}],
    )
    result = _tool_search_products(CTX, {"query": "cemento gris"})

    assert result["source"] == "banco_datos"
    assert result["reason"].startswith("storefront_unavailable")


@pytest.mark.unit
def test_a_query_with_markup_is_refused_not_forwarded(monkeypatch):
    fake = FakeStorefront(products=PISO_ITEMS)
    monkeypatch.setattr(storefront_module, "post_graphql", fake)
    monkeypatch.setattr(
        "depotru_tools.builtins._search_products_db", lambda q, limit=5: []
    )
    result = _tool_search_products(CTX, {"query": "piso{__typename}"})

    assert result["status"] == "empty"
    assert result["reason"] == "query_invalid_characters"
    assert fake.calls == []
