"""catalog.brand_categories: storefront taxonomy of one brand (no live network)."""

from __future__ import annotations

import pytest

from depotru_integrations.magento import categories as brand_categories
from depotru_kernel.auth import Audience
from depotru_tools.builtins import _tool_brand_categories, _tool_brand_suggest
from depotru_tools.registry import (
    ToolContext,
    get_default_registry,
    reset_default_registry,
)

BROCHA = {
    "id": 18298,
    "name": "Brochas",
    "url_path": "herramientas-manuales/brochas",
    "level": 3,
}
MANUALES = {
    "id": 49,
    "name": "Herramientas manuales",
    "url_path": "herramientas-manuales",
    "level": 2,
}
MASILLA = {"id": 104, "name": " Masillas", "url_path": "pinturas/masillas", "level": 3}
PINTURAS = {"id": 100, "name": "Pinturas", "url_path": "pinturas", "level": 2}

OPTIONS = {
    "items": [
        {
            "attribute_options": [
                {"label": "PINTUCO", "value": "175"},
                {"label": "SIKA", "value": "193"},
                {"label": "PINTUCO ANDINA", "value": "240"},
            ]
        }
    ]
}


def _product(sku: str, name: str, categories: list[dict]):
    return {"sku": sku, "name": name, "categories": categories}


class FakeStorefront:
    """Answers the two GraphQL queries the module sends."""

    def __init__(
        self, products: list[dict], total: int | None = None, page_size: int = 100
    ):
        self.products = products
        self.total = len(products) if total is None else total
        self.page_size = page_size
        self.calls: list[str] = []

    def __call__(self, query: str, variables: dict) -> dict:
        if "customAttributeMetadata" in query:
            self.calls.append("brands")
            return {"customAttributeMetadata": OPTIONS}
        self.calls.append(f"page{variables['page']}")
        start = (variables["page"] - 1) * self.page_size
        return {
            "products": {
                "total_count": self.total,
                "items": self.products[start : start + self.page_size],
            }
        }


@pytest.fixture(autouse=True)
def _fresh_state():
    reset_default_registry()
    brand_categories.reset_cache()
    yield
    reset_default_registry()
    brand_categories.reset_cache()


@pytest.mark.unit
def test_brand_is_resolved_by_label_then_by_unique_prefix(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(brand_categories, "_post_query", FakeStorefront([], total=0))
    assert brand_categories.resolve_brand_id("pintuco") == "175"
    assert brand_categories.resolve_brand_id("Pintuco") == "175"
    assert brand_categories.resolve_brand_id("sik") == "193"
    # Two options start with "pintuco": a prefix cannot pick one of them.
    assert brand_categories.resolve_brand_id("pintuc") is None


@pytest.mark.unit
def test_groups_products_by_parent_and_subcategory(monkeypatch: pytest.MonkeyPatch):
    fake = FakeStorefront(
        [
            _product(
                "0010310013", 'BROCHA PINTUCO CERDA BLANCA 1"', [MANUALES, BROCHA]
            ),
            _product(
                "0010310014", 'BROCHA PINTUCO CERDA BLANCA 2"', [MANUALES, BROCHA]
            ),
            _product("0090060252", "PINTUCOFILL 7 ANTIHONGOS", [PINTURAS, MASILLA]),
        ]
    )
    monkeypatch.setattr(brand_categories, "_post_query", fake)
    result = brand_categories.brand_category_overview("pintuco")

    assert result["status"] == "ok"
    assert result["source"] == "ecommerce"
    assert result["brand_id"] == "175"
    assert result["matched_products"] == 3
    tree = {node["name"]: node for node in result["categories"]}
    assert tree["Herramientas manuales"]["products"] == 2
    assert tree["Herramientas manuales"]["subcategories"] == [
        {"name": "Brochas", "url_path": "herramientas-manuales/brochas", "products": 2}
    ]
    # The storefront has category names with leading spaces: they are trimmed.
    assert tree["Pinturas"]["subcategories"][0]["name"] == "Masillas"


@pytest.mark.unit
def test_reads_every_page_of_a_big_brand(monkeypatch: pytest.MonkeyPatch):
    products = [
        _product(f"00103100{i:02d}", f"BROCHA PINTUCO {i}", [MANUALES, BROCHA])
        for i in range(150)
    ]
    fake = FakeStorefront(products, total=150)
    monkeypatch.setattr(brand_categories, "_post_query", fake)
    result = brand_categories.brand_category_overview("pintuco")

    assert result["matched_products"] == 150
    assert result["categories"][0]["products"] == 150
    assert [call for call in fake.calls if call.startswith("page")] == [
        "page1",
        "page2",
    ]


@pytest.mark.unit
def test_unknown_brand_is_empty_not_an_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(brand_categories, "_post_query", FakeStorefront([], total=0))
    result = brand_categories.brand_category_overview("marca-inexistente")

    assert result["status"] == "empty"
    assert result["reason"] == "brand_not_in_storefront"
    assert result["categories"] == []


@pytest.mark.unit
def test_upstream_failure_returns_no_categories(monkeypatch: pytest.MonkeyPatch):
    def boom(query, variables):
        raise RuntimeError("Magento HTTP 503")

    monkeypatch.setattr(brand_categories, "_post_query", boom)
    result = brand_categories.brand_category_overview("sika")

    assert result["status"] == "error"
    assert result["reason"] == "upstream_error"
    assert result["categories"] == []


@pytest.mark.unit
@pytest.mark.parametrize("brand", ["", "   ", "pintuco'; DROP TABLE", "x" * 41])
def test_brand_must_be_a_name(brand: str, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        brand_categories, "_post_query", FakeStorefront([], total=0), raising=False
    )
    result = brand_categories.brand_category_overview(brand)
    assert result["status"] == "error"
    assert result["categories"] == []


@pytest.mark.unit
def test_cache_avoids_asking_twice(monkeypatch: pytest.MonkeyPatch):
    fake = FakeStorefront(
        [_product("0010310013", "BROCHA PINTUCO 1", [MANUALES, BROCHA])]
    )
    monkeypatch.setattr(brand_categories, "_post_query", fake)
    brand_categories.brand_category_overview("pintuco")
    brand_categories.brand_category_overview("Pintuco")

    assert fake.calls == ["brands", "page1"]


@pytest.mark.unit
def test_tool_is_registered_as_public_and_returns_the_tree(
    monkeypatch: pytest.MonkeyPatch,
):
    names = {
        tool["name"]
        for tool in get_default_registry().list_tools(audience=Audience.PUBLIC)
    }
    assert "catalog.brand_categories" in names

    monkeypatch.setattr(
        brand_categories,
        "_post_query",
        FakeStorefront(
            [_product("0010310013", "BROCHA PINTUCO 1", [MANUALES, BROCHA])]
        ),
    )
    result = get_default_registry().call(
        "catalog.brand_categories",
        {"brand": "pintuco"},
        context=ToolContext(audience=Audience.PUBLIC),
    )
    assert result["categories"][0]["name"] == "Herramientas manuales"


@pytest.mark.unit
def test_tool_never_raises_when_the_adapter_fails(monkeypatch: pytest.MonkeyPatch):
    def boom(brand):
        raise RuntimeError("import exploded")

    monkeypatch.setattr(
        "depotru_integrations.magento.categories.brand_category_overview", boom
    )
    result = _tool_brand_categories(
        ToolContext(audience=Audience.PUBLIC), {"brand": "sika"}
    )
    assert result["status"] == "error"
    assert result["categories"] == []


def test_suggest_brands_recognises_a_typo(monkeypatch):
    """«accesco» es un error de dedo por ACESCO: se recomienda, no se niega."""
    monkeypatch.setattr(
        brand_categories,
        "brand_options",
        lambda: {
            "acesco": "12",
            "pintuco": "175",
            "sika": "193",
        },
    )
    result = brand_categories.suggest_brands("accesco")
    assert result["status"] == "ok"
    nombres = [item["brand"] for item in result["suggestions"]]
    assert "ACESCO" in nombres
    assert result["suggestions"][0]["brand"] == "ACESCO"


def test_suggest_brands_prefers_a_prefix(monkeypatch):
    monkeypatch.setattr(
        brand_categories,
        "brand_options",
        lambda: {
            "pintuco": "175",
            "pinturas del sur": "300",
        },
    )
    result = brand_categories.suggest_brands("pintu")
    assert result["suggestions"][0]["brand"] == "PINTUCO"


def test_suggest_brands_returns_nothing_for_an_unrelated_word(monkeypatch):
    monkeypatch.setattr(
        brand_categories,
        "brand_options",
        lambda: {
            "pintuco": "175",
            "sika": "193",
        },
    )
    result = brand_categories.suggest_brands("zzzzqqq")
    assert result["status"] == "empty"
    assert result["suggestions"] == []


def test_brand_suggest_tool_never_raises(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("storefront caído")

    monkeypatch.setattr(brand_categories, "brand_options", boom)
    out = _tool_brand_suggest(None, {"query": "accesco"})  # type: ignore[arg-type]
    assert out["status"] == "error"
    assert out["suggestions"] == []
