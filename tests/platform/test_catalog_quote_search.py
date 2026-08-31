"""catalog.quote_search: J3 price/stock SQL + tool merge (no live DB)."""

from __future__ import annotations

import pytest

from business_analyzer.core.j3system_website_stock import build_quote_search_sql
from depotru_kernel.auth import Audience
from depotru_tools.builtins import _tool_quote_search
from depotru_tools.registry import (
    ToolContext,
    get_default_registry,
    reset_default_registry,
)


@pytest.fixture(autouse=True)
def _fresh_registry():
    reset_default_registry()
    yield
    reset_default_registry()


@pytest.mark.unit
def test_quote_search_sql_is_allowlisted_and_has_no_cost():
    sql = build_quote_search_sql(limit=6)
    assert "TOP 6" in sql
    assert "ArticulosVenta" in sql
    assert "ArticulosNombre LIKE %s" in sql
    assert "ArticulosCodigo LIKE %s" in sql
    assert "SaldoActual" in sql
    assert "ALM" in sql
    assert "CEN" not in sql  # denylist warehouse must not be in the IN-list
    assert "ArticulosCosto" not in sql
    assert "ArticulosUltmoCosto" not in sql
    assert "UltimoCostoCompra" not in sql


@pytest.mark.unit
def test_quote_search_tool_is_public():
    names = {
        t["name"] for t in get_default_registry().list_tools(audience=Audience.PUBLIC)
    }
    assert "catalog.quote_search" in names


@pytest.mark.unit
def test_quote_search_merges_j3_rows(monkeypatch: pytest.MonkeyPatch):
    class FakeDB:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute_query(self, sql, params):
            assert "ArticulosCosto" not in sql
            assert params == ("%cemento%", "%cemento%")
            return [
                {
                    "sku": "0020080005",
                    "name": "CEMENTO BLANCO ARGOS 20KG",
                    "price": 36428,
                    "website_qty": 12,
                }
            ]

    monkeypatch.setattr("business_analyzer.core.database.Database", lambda: FakeDB())
    monkeypatch.setattr(
        "depotru_tools.builtins._tool_search_products",
        lambda ctx, params: {"products": [], "source": "none"},
    )
    out = _tool_quote_search(ToolContext(audience=Audience.SALES), {"query": "cemento"})
    assert out["status"] == "ok"
    assert out["products"][0]["sku"] == "0020080005"
    assert out["products"][0]["price"] == 36428
    assert out["products"][0]["website_qty"] == 12
    assert out["products"][0]["in_stock"] is True
    assert "catalogsearch/result" in out["search_url"]
    assert "cost" not in out["products"][0]
