"""Category browsing contract: stable paths, offline ranking, no stock."""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from business_analyzer.core.quote_search_iva import build_product
from depotru_integrations.affinity import category_snapshot as snapshot
from depotru_integrations.magento import categories
from depotru_integrations.magento.category_products import _rank, category_products
from depotru_kernel.auth import Audience
from depotru_tools.builtins import register_builtin_tools
from depotru_tools.registry import ToolContext, ToolRegistry

PATH = "materiales/aditivos"


def test_category_products_is_public_read_only():
    registry = ToolRegistry()
    register_builtin_tools(registry)
    spec = registry.get("catalog.category_products")
    assert spec.public_safe
    assert "url_path" in spec.parameters_schema
    result = registry.call(
        spec.name,
        {"brand": "sika", "url_path": ""},
        context=ToolContext(audience=Audience.PUBLIC),
    )
    assert result["status"] == "error"
    assert result["products"] == []


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setenv(snapshot.SNAPSHOT_ENV, str(tmp_path / "snapshot.json"))
    # Any transitive live J3 access during a message is a hard test failure.
    from business_analyzer.core import database

    def forbidden(*args, **kwargs):
        pytest.fail("category browsing reached live J3")

    monkeypatch.setattr(database.Database, "execute_query", forbidden)
    monkeypatch.setattr(categories, "resolve_brand_id", lambda brand: "42")

    def unconfigured(*args, **kwargs):
        pytest.fail("unexpected network request")

    monkeypatch.setattr(categories, "post_graphql", unconfigured)


def item(sku, name, path=PATH):
    return {
        "sku": sku,
        "name": name,
        "url_key": "product-" + sku,
        "categories": [{"name": "Display name changed", "url_path": path}],
    }


def storefront(monkeypatch, items):
    calls = []

    def query(sql, variables):
        assert variables["id"] == "42"
        assert "search:" not in sql
        assert "stock" not in sql.lower()
        calls.append(variables)
        start = (variables["page"] - 1) * variables["size"]
        return {
            "products": {
                "items": items[start : start + variables["size"]],
                "total_count": len(items),
            }
        }

    monkeypatch.setattr(categories, "post_graphql", query)
    return calls


def saved(sku, count):
    product = build_product(
        j3_row={
            "sku": sku,
            "name": "ERP product",
            "price": Decimal("100.50"),
            "iva_rate": Decimal("19"),
            "line_id": 1,
        }
    )
    for key in snapshot.STOCK_FIELDS:
        product.pop(key)
    return {**product, "invoice_count": count}


def test_sales_first_then_smaller_presentation_and_quote_price(monkeypatch):
    storefront(
        monkeypatch,
        [
            item("drum", "Plastocrete DM 230 kg"),
            item("small", "Aditivo 2 kg"),
            item("medium", "Aditivo 20 kg"),
            item("other", "Otro", "other/category"),
        ],
    )
    snapshot.write_snapshot(
        {
            "drum": saved("drum", 80),
            "small": saved("small", 20),
            "medium": saved("medium", 20),
        },
        snapshot.snapshot_path(),
    )
    result = category_products("sika", PATH)
    assert result["source"] == "j3_invoice_snapshot"
    assert [p["sku"] for p in result["products"]] == ["drum", "small", "medium"]
    product = result["products"][0]
    expected = build_product(
        j3_row={
            "sku": "drum",
            "price": Decimal("100.50"),
            "iva_rate": Decimal(19),
            "line_id": 1,
        }
    )
    assert product["price_with_iva"] == expected["price_with_iva"] == 120
    assert set(product) == set(expected) - snapshot.STOCK_FIELDS
    assert product["price"] == "100.50"
    assert product["product_url"].endswith("product-drum.html")


def test_missing_snapshot_is_presentation_only_with_null_prices(monkeypatch):
    storefront(monkeypatch, [item("a", "Aditivo 230 kg"), item("b", "Aditivo 2 kg")])
    result = category_products("sika", PATH)
    assert result["source"] == "presentation_fallback:missing_snapshot"
    assert [p["sku"] for p in result["products"]] == ["b", "a"]
    assert all(p["price_with_iva"] is None for p in result["products"])
    assert all(not snapshot.STOCK_FIELDS.intersection(p) for p in result["products"])


def test_window_after_global_ranking_not_magento_first_forty(monkeypatch):
    items = [
        item(str(i), f"Aditivo {i + 1} kg", PATH + "/plastificantes")
        for i in range(120)
    ]
    items.append(items[0])  # duplicate SKU cannot consume a window slot
    calls = storefront(monkeypatch, items)
    snapshot.write_snapshot(
        {str(i): saved(str(i), 100 if i == 119 else 0) for i in range(120)},
        snapshot.snapshot_path(),
    )
    result = category_products("sika", PATH)
    assert result["count"] == len(result["products"]) == 40
    assert result["products"][0]["sku"] == "119"
    assert result["total_count"] == 120
    assert result["has_more"] is True
    assert len(calls) == 2


def test_no_prefix_sibling_or_display_name_matching(monkeypatch):
    storefront(monkeypatch, [item("x", "Aditivo", PATH + "-other")])
    assert category_products("sika", PATH)["status"] == "empty"
    assert category_products("sika", "Display name changed")["status"] == "error"


def test_incomplete_catalog_is_explicit_not_false_ranking(monkeypatch):
    monkeypatch.setattr(categories, "MAX_PAGES", 1)
    storefront(monkeypatch, [item(str(i), "Aditivo") for i in range(101)])
    result = category_products("sika", PATH)
    assert result["reason"] == "brand_catalog_truncated"
    assert result["products"] == []


def test_upstream_failure_is_sanitized(monkeypatch):
    def broken(*args):
        raise RuntimeError("private connection details")

    monkeypatch.setattr(categories, "post_graphql", broken)
    result = category_products("sika", PATH)
    assert result["reason"] == "catalog_unavailable"
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize("path", [None, 3, "", "../aditivos", "foo/", "a//b", "x?y"])
def test_invalid_identity_does_not_fetch(path):
    assert category_products("sika", path)["status"] == "error"


def test_brand_missing_is_empty(monkeypatch):
    monkeypatch.setattr(categories, "resolve_brand_id", lambda brand: None)
    assert category_products("unknown", PATH)["reason"] == "brand_not_in_storefront"


def test_rank_only_compares_sizes_in_same_dimension():
    products = [
        item("a", "Aditivo 20 kg"),
        item("b", "Aditivo 1 l"),
        item("c", "Aditivo 500 g"),
        item("d", "Aditivo 200 ml"),
        item("e", "Presentacion desconocida"),
    ]
    assert [p["sku"] for p in _rank(products, {})] == ["c", "d", "a", "b", "e"]


@pytest.mark.parametrize(
    "kind", ["stale", "future", "window", "corrupt", "stock", "missing_field", "cost"]
)
def test_snapshot_rejects_out_of_contract(kind):
    snapshot.write_snapshot({"a": saved("a", 1)}, snapshot.snapshot_path())
    payload = json.loads(snapshot.snapshot_path().read_text())
    if kind in {"stale", "future"}:
        offset = -6 if kind == "stale" else 1
        payload["stored_at"] = (
            datetime.now(timezone.utc) + timedelta(days=offset)
        ).isoformat()
    elif kind == "window":
        payload["window_months"] = 6
    elif kind == "stock":
        payload["products"]["a"]["website_qty"] = "10"
    elif kind == "missing_field":
        payload["products"]["a"].pop("price_with_iva")
    elif kind == "cost":
        payload["products"]["a"]["cost"] = "private"
    snapshot.snapshot_path().write_text(
        "bad json" if kind == "corrupt" else json.dumps(payload)
    )
    products, source = snapshot.read_snapshot()
    assert products == {}
    assert source.startswith("presentation_fallback:")


def test_partial_snapshot_discloses_presentation_fallback(monkeypatch):
    storefront(monkeypatch, [item("a", "Aditivo 230 kg"), item("b", "Aditivo 2 kg")])
    snapshot.write_snapshot({"a": saved("a", 100)}, snapshot.snapshot_path())
    result = category_products("sika", PATH)
    assert result["source"] == "presentation_fallback:incomplete_snapshot"
    assert [p["sku"] for p in result["products"]] == ["b", "a"]
    assert result["products"][0]["price_with_iva"] is None
    assert result["products"][1]["price_with_iva"] == 120


@pytest.mark.parametrize(
    ("field", "replacement"),
    [("price_with_iva", True), ("price_includes_iva", 0)],
)
def test_snapshot_requires_exact_primitive_types(field, replacement):
    product = saved("a", 1)
    product.update(price="1", j3_price="1", iva_rate="0", price_with_iva=1)
    assert snapshot._valid_product("a", product)
    product[field] = replacement
    assert not snapshot._valid_product("a", product)
