"""catalog.cross_sell: lo que la tienda declara como complemento.

La relación la posee merchandising, no una tabla escrita a mano. Pero la mitad
de lo que Magento tiene como cross-sell en boquilla es el mismo producto en otro
color: eso es una variante, no un complemento, y ofrecerlo sería ruido.
"""

from __future__ import annotations

import pytest

from depotru_integrations.magento import storefront as storefront_module
from depotru_kernel.auth import Audience
from depotru_tools.builtins import _tool_cross_sell
from depotru_tools.registry import ToolContext

CTX = ToolContext(audience=Audience.PUBLIC)


def _row(sku: str, name: str) -> dict:
    return {
        "sku": sku,
        "name": name,
        "url_key": sku.lower(),
        "categories": [
            {"name": "Materiales de construcción", "url_path": "materiales"}
        ],
    }


CEMENTO = {
    "products": {
        "items": [
            {
                "sku": "0020090002",
                "name": "Cemento Gris Uso General Cemex 50Kg",
                "crosssell_products": [
                    _row("0020190005", "Barra Corrugada 9Mm X 6M Ntc 2289 Peso 3"),
                    _row("0020090003", "Cemento Gris Uso General Cemex X 1 Kg"),
                ],
                "related_products": [
                    _row("0020080002", "Cemento Blanco Cemex 25Kg"),
                ],
                "upsell_products": [],
            }
        ]
    }
}


@pytest.mark.unit
def test_variants_of_the_same_product_are_not_complements(monkeypatch):
    monkeypatch.setattr(storefront_module, "post_graphql", lambda q, v: CEMENTO)
    result = _tool_cross_sell(CTX, {"sku": "0020090002"})

    names = [product["name"] for product in result["products"]]
    assert result["status"] == "ok"
    # La barra corrugada y el cemento blanco sí; el mismo cemento por kilo no.
    assert "Barra Corrugada 9Mm X 6M Ntc 2289 Peso 3" in names
    assert "Cemento Blanco Cemex 25Kg" in names
    assert all("X 1 Kg" not in name for name in names)
    assert [p["relation"] for p in result["products"]] == ["crosssell", "related"]


@pytest.mark.unit
def test_the_quoted_sku_is_never_offered_to_itself(monkeypatch):
    payload = {
        "products": {
            "items": [
                {
                    "sku": "0020090002",
                    "name": "Cemento Gris Uso General Cemex 50Kg",
                    "crosssell_products": [
                        _row("0020090002", "Cemento Gris Uso General Cemex 50Kg")
                    ],
                    "related_products": [],
                    "upsell_products": [],
                }
            ]
        }
    }
    monkeypatch.setattr(storefront_module, "post_graphql", lambda q, v: payload)
    result = _tool_cross_sell(CTX, {"sku": "0020090002"})

    assert result["status"] == "empty"
    assert result["products"] == []


@pytest.mark.unit
def test_a_product_without_relations_says_empty_not_error(monkeypatch):
    payload = {
        "products": {
            "items": [
                {
                    "sku": "0060440386",
                    "name": "Piso Cerámico Aranda Gris 50 X 50",
                    "crosssell_products": [],
                    "related_products": [],
                    "upsell_products": [],
                }
            ]
        }
    }
    monkeypatch.setattr(storefront_module, "post_graphql", lambda q, v: payload)
    result = _tool_cross_sell(CTX, {"sku": "0060440386"})

    assert result["status"] == "empty"
    assert "reason" not in result


@pytest.mark.unit
def test_storefront_failure_is_reported(monkeypatch):
    def boom(query: str, variables: dict) -> dict:
        raise RuntimeError("GraphQL errors: boom")

    monkeypatch.setattr(storefront_module, "post_graphql", boom)
    result = _tool_cross_sell(CTX, {"sku": "0020090002"})

    assert result["status"] == "error"
    assert result["reason"].startswith("storefront_unavailable")


@pytest.mark.unit
def test_an_empty_sku_is_refused(monkeypatch):
    monkeypatch.setattr(
        storefront_module, "post_graphql", lambda q, v: pytest.fail("no debió llamar")
    )
    result = _tool_cross_sell(CTX, {"sku": "  "})

    assert result["status"] == "error"
    assert result["reason"] == "sku_invalid"
