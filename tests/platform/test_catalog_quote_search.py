"""catalog.quote_search: J3 price/IVA SQL + tool merge (fake-only, no live DB)."""

from __future__ import annotations

import json
import sqlite3
from decimal import Decimal, InvalidOperation

import pytest

from business_analyzer.core.j3system_website_stock import build_quote_search_sql
from business_analyzer.core.quote_search_iva import build_product
from depotru_kernel.auth import Audience
from depotru_tools.builtins import _tool_quote_search
from depotru_tools.registry import (
    ToolContext,
    get_default_registry,
    reset_default_registry,
)


class _DecimalSum:
    """Exact Decimal SUM aggregate for SQLite (never binary float)."""

    def __init__(self) -> None:
        self.total = Decimal("0")

    def step(self, value) -> None:
        if value is None:
            return
        try:
            self.total += Decimal(str(value))
        except (InvalidOperation, ValueError):
            pass

    def finalize(self) -> str:
        return format(self.total, "f")


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE AdmArticulos (ArticulosID INTEGER PRIMARY KEY, "
        "ArticulosCodigo TEXT, ArticulosNombre TEXT, ArticulosVenta TEXT, "
        "LineasID INTEGER, ArticulosEstado INTEGER)"
    )
    conn.execute(
        "CREATE TABLE AdmLineas (LineasID INTEGER PRIMARY KEY, LineasPorcentaje TEXT)"
    )
    conn.execute(
        "CREATE TABLE AdmGrupos (GruposID INTEGER PRIMARY KEY, Porcentaje TEXT)"
    )
    conn.execute(
        "CREATE TABLE InvDetalleExistencias (ExistenciasID INTEGER, "
        "AlmacenID INTEGER, SaldoActual TEXT, Ano INTEGER)"
    )
    conn.execute(
        "CREATE TABLE InvExistencias (ExistenciasID INTEGER, ArticulosID INTEGER)"
    )
    conn.execute(
        "CREATE TABLE AdmAlmacen (AlmacenID INTEGER PRIMARY KEY, AlmacenCodigo TEXT)"
    )
    conn.create_aggregate("decimal_sum", 1, _DecimalSum)
    conn.row_factory = sqlite3.Row
    return conn


def _seed_stock(conn: sqlite3.Connection, items) -> None:
    for i, (articulos_id, saldo) in enumerate(items):
        almacen_id = 100 + i
        existen_id = 200 + i
        conn.execute(
            "INSERT INTO AdmAlmacen (AlmacenID, AlmacenCodigo) VALUES (?, 'ALM')",
            (almacen_id,),
        )
        conn.execute(
            "INSERT INTO InvExistencias (ExistenciasID, ArticulosID) VALUES (?, ?)",
            (existen_id, articulos_id),
        )
        conn.execute(
            "INSERT INTO InvDetalleExistencias "
            "(ExistenciasID, AlmacenID, SaldoActual, Ano) VALUES (?, ?, ?, 2026)",
            (existen_id, almacen_id, saldo),
        )


def _quote_products(conn: sqlite3.Connection, query: str, limit: int = 6) -> list[dict]:
    """Run the shared builder against SQLite and build closed product dicts."""
    sql = build_quote_search_sql(limit=limit, dialect="sqlite")
    pattern = f"%{query}%"
    rows = [dict(r) for r in conn.execute(sql, (pattern, pattern)).fetchall()]
    return [build_product(j3_row=r) for r in rows]


@pytest.fixture(autouse=True)
def _fresh_registry():
    reset_default_registry()
    yield
    reset_default_registry()


@pytest.fixture(autouse=True)
def _no_magento(monkeypatch: pytest.MonkeyPatch):
    """Never touch env credentials or Magento in fake-only tests."""
    from depotru_integrations.magento.client import MagentoConfig

    monkeypatch.setattr(MagentoConfig, "from_env", classmethod(lambda cls: None))
    monkeypatch.setattr(
        "depotru_tools.builtins._tool_search_products",
        lambda ctx, params: {"products": [], "source": "none"},
    )


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
    # IVA rate via LEFT JOIN; no other rate source, no ArticulosEstado filter.
    assert "AdmLineas" in sql
    assert "LineasPorcentaje" in sql
    assert "ArticulosEstado" not in sql
    assert "AdmGrupos" not in sql
    assert "AdmPrecios" not in sql
    assert "LineasIndicadorIva" not in sql


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
                    "price": Decimal("36428.0000"),
                    "iva_rate": Decimal("19.000"),
                    "line_id": 5,
                    "website_qty": Decimal("12.0000"),
                }
            ]

    monkeypatch.setattr("business_analyzer.core.database.Database", lambda: FakeDB())
    out = _tool_quote_search(ToolContext(audience=Audience.SALES), {"query": "cemento"})
    assert out["status"] == "ok"
    p = out["products"][0]
    assert p["sku"] == "0020080005"
    assert p["price"] == "36428.0000"
    assert p["j3_price"] == "36428.0000"
    assert p["price_basis"] == "J3"
    assert p["price_includes_iva"] is False
    assert p["iva_rate"] == "19.000"
    assert p["price_with_iva"] == 43349  # 36428 * 1.19 = 43349.32 -> 43349
    assert p["website_qty"] == "12.0000"
    assert p["in_stock"] is True
    assert "catalogsearch/result" in out["search_url"]
    assert "cost" not in p


@pytest.mark.unit
def test_quote_search_rates_19_5_0():
    conn = _make_db()
    conn.execute(
        "INSERT INTO AdmLineas (LineasID, LineasPorcentaje) "
        "VALUES (1, '19.000'), (2, '5.000'), (3, '0.000')"
    )
    conn.execute(
        "INSERT INTO AdmArticulos (ArticulosID, ArticulosCodigo, ArticulosNombre, "
        "ArticulosVenta, LineasID, ArticulosEstado) VALUES "
        "(1, 'A1', 'PRODUCTO A', '100.0000', 1, 1), "
        "(2, 'A2', 'PRODUCTO B', '100.0000', 2, 0), "
        "(3, 'A3', 'PRODUCTO C', '100.0000', 3, 5)"
    )
    products = {p["sku"]: p for p in _quote_products(conn, "producto")}
    assert products["A1"]["iva_rate"] == "19.000"
    assert products["A1"]["price_with_iva"] == 119
    assert products["A2"]["iva_rate"] == "5.000"
    assert products["A2"]["price_with_iva"] == 105
    assert products["A3"]["iva_rate"] == "0.000"
    assert products["A3"]["price_with_iva"] == 100


@pytest.mark.unit
def test_quote_search_zero_rate_and_half_up():
    conn = _make_db()
    conn.execute(
        "INSERT INTO AdmLineas (LineasID, LineasPorcentaje) "
        "VALUES (1, '0.000'), (2, '19.000')"
    )
    conn.execute(
        "INSERT INTO AdmArticulos (ArticulosID, ArticulosCodigo, ArticulosNombre, "
        "ArticulosVenta, LineasID, ArticulosEstado) VALUES "
        "(1, 'Z', 'PRODUCTO Z', '100.5000', 1, 1), "
        "(2, 'H', 'PRODUCTO H', '100.5000', 2, 1)"
    )
    products = {p["sku"]: p for p in _quote_products(conn, "producto")}
    assert products["Z"]["price_with_iva"] == 101  # ROUND_HALF_UP(100.5000) = 101
    assert products["H"]["price_with_iva"] == 120  # 100.5 * 1.19 = 119.595 -> 120


@pytest.mark.unit
def test_quote_search_missing_line_and_null_rate():
    conn = _make_db()
    conn.execute("INSERT INTO AdmLineas (LineasID, LineasPorcentaje) VALUES (1, NULL)")
    conn.execute(
        "INSERT INTO AdmArticulos (ArticulosID, ArticulosCodigo, ArticulosNombre, "
        "ArticulosVenta, LineasID, ArticulosEstado) VALUES "
        "(1, 'NL', 'PRODUCTO NL', '200.0000', 999, 1), "
        "(2, 'NR', 'PRODUCTO NR', '200.0000', 1, 1)"
    )
    products = {p["sku"]: p for p in _quote_products(conn, "producto")}
    assert products["NL"]["price"] == "200.0000"
    assert products["NL"]["j3_price"] == "200.0000"
    assert products["NL"]["iva_rate"] is None
    assert products["NL"]["price_with_iva"] is None
    assert products["NL"]["price_with_iva_reason"] == "line_not_found"
    assert products["NR"]["price"] == "200.0000"
    assert products["NR"]["iva_rate"] is None
    assert products["NR"]["price_with_iva"] is None
    assert products["NR"]["price_with_iva_reason"] == "iva_rate_null"


@pytest.mark.unit
def test_quote_search_group_rate_ignored_and_estado_not_filtered():
    conn = _make_db()
    conn.execute(
        "INSERT INTO AdmLineas (LineasID, LineasPorcentaje) VALUES (1, '19.000')"
    )
    conn.execute("INSERT INTO AdmGrupos (GruposID, Porcentaje) VALUES (1, '99.000')")
    conn.execute(
        "INSERT INTO AdmArticulos (ArticulosID, ArticulosCodigo, ArticulosNombre, "
        "ArticulosVenta, LineasID, ArticulosEstado) VALUES "
        "(1, 'G1', 'PRODUCTO G', '100.0000', 1, 0)"
    )
    products = _quote_products(conn, "producto")
    assert len(products) == 1
    p = products[0]
    assert p["iva_rate"] == "19.000"  # group 99% ignored
    assert p["price_with_iva"] == 119
    assert p["sku"] == "G1"  # ArticulosEstado=0 is still returned


@pytest.mark.unit
def test_quote_search_j3_vs_magento():
    j3_row = {
        "sku": "SKU1",
        "name": "J3 NAME",
        "price": Decimal("100.0000"),
        "iva_rate": Decimal("19.000"),
        "line_id": 1,
        "website_qty": Decimal("3.0000"),
    }
    magento = {
        "sku": "SKU1",
        "name": "MAGENTO NAME",
        "price": 999.99,
        "product_url": "https://example.com/p.html",
    }
    p = build_product(j3_row=j3_row, magento=magento)
    assert p["price"] == "100.0000"  # Magento never replaces J3 price
    assert p["price_basis"] == "J3"
    assert p["price_includes_iva"] is False
    assert p["j3_price"] == "100.0000"
    assert p["iva_rate"] == "19.000"
    assert p["price_with_iva"] == 119
    assert p["name"] == "MAGENTO NAME"
    assert p["product_url"] == "https://example.com/p.html"
    assert p["magento_price"] == "999.99"
    assert p["source"] == "j3+magento"


@pytest.mark.unit
def test_quote_search_magento_only():
    magento = {
        "sku": "M1",
        "name": "MAG ONLY",
        "price": 500.0,
        "product_url": "https://example.com/m.html",
    }
    p = build_product(magento=magento)
    assert p["price"] is None
    assert p["price_basis"] == "none"
    assert p["price_includes_iva"] is None
    assert p["j3_price"] is None
    assert p["iva_rate"] is None
    assert p["price_with_iva"] is None
    assert p["price_with_iva_reason"] == "j3_price_missing"
    assert p["magento_price"] == "500.0"
    assert p["website_qty"] is None
    assert p["in_stock"] is None
    assert p["source"] == "magento"


@pytest.mark.unit
def test_quote_search_exact_decimal_serialization():
    conn = _make_db()
    conn.execute(
        "INSERT INTO AdmLineas (LineasID, LineasPorcentaje) VALUES (1, '19.000')"
    )
    conn.execute(
        "INSERT INTO AdmArticulos (ArticulosID, ArticulosCodigo, ArticulosNombre, "
        "ArticulosVenta, LineasID, ArticulosEstado) VALUES "
        "(1, 'S1', 'PRODUCTO S', '36428.0000', 1, 1)"
    )
    _seed_stock(conn, [(1, "12.5000")])
    products = _quote_products(conn, "producto")
    p = products[0]
    assert p["price"] == "36428.0000"
    assert p["j3_price"] == "36428.0000"
    assert p["iva_rate"] == "19.000"
    assert p["website_qty"] == "12.5000"  # fractional digits preserved exactly
    assert p["in_stock"] is True
    assert isinstance(p["price"], str)
    assert isinstance(p["j3_price"], str)
    assert isinstance(p["iva_rate"], str)
    assert isinstance(p["website_qty"], str)
    assert isinstance(p["price_with_iva"], int)


@pytest.mark.unit
def test_quote_search_closed_output_shape():
    p = build_product(
        j3_row={
            "sku": "X",
            "name": "N",
            "price": Decimal("10.0000"),
            "iva_rate": Decimal("19.000"),
            "line_id": 1,
            "website_qty": Decimal("0.0000"),
        }
    )
    assert set(p.keys()) == {
        "sku",
        "name",
        "price",
        "price_basis",
        "price_includes_iva",
        "j3_price",
        "iva_rate",
        "price_with_iva",
        "price_with_iva_reason",
        "magento_price",
        "website_qty",
        "in_stock",
        "product_url",
        "source",
    }


@pytest.mark.unit
def test_quote_search_catalog_unavailable(monkeypatch: pytest.MonkeyPatch):
    class FailDB:
        def __enter__(self):
            raise ConnectionError("boom: SQLSTATE 08S01 host=secret-dsn")

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("business_analyzer.core.database.Database", lambda: FailDB())
    out = _tool_quote_search(ToolContext(audience=Audience.SALES), {"query": "cemento"})
    assert out["status"] == "error"
    assert out["reason"] == "catalog_unavailable"
    assert out["products"] == []
    assert out["count"] == 0
    assert out["source"] == "none"
    assert set(out.keys()) == {
        "query",
        "products",
        "count",
        "source",
        "search_url",
        "status",
        "reason",
    }
    # No raw driver/SQL/connection detail leaks into the result.
    text = json.dumps(out)
    assert "08S01" not in text
    assert "secret" not in text
    assert "boom" not in text
