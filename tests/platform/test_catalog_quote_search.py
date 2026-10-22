"""catalog.quote_search: J3 price/IVA SQL + tool merge (fake-only, no live DB)."""

from __future__ import annotations

import json
import logging
import sqlite3
from decimal import Decimal, InvalidOperation

import pytest

from business_analyzer.core.database import ConnectionError as DBConnectionError
from business_analyzer.core.database import ConnectionType, Database, QueryError
from business_analyzer.core.j3system_website_stock import build_quote_search_sql
from business_analyzer.core.quote_search_iva import (
    build_product,
    magento_price_string,
    to_decimal,
)
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


def _decimal_ge(value, threshold) -> int:
    """Exact Decimal ``>=`` for SQLite (returns 1/0, never binary float)."""
    try:
        return 1 if Decimal(str(value)) >= Decimal(str(threshold)) else 0
    except (InvalidOperation, ValueError):
        return 0


def _decimal_gt(value, threshold) -> int:
    """Exact Decimal ``>`` for SQLite (returns 1/0, never binary float)."""
    try:
        return 1 if Decimal(str(value)) > Decimal(str(threshold)) else 0
    except (InvalidOperation, ValueError):
        return 0


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
    conn.create_function("decimal_ge", 2, _decimal_ge)
    conn.create_function("decimal_gt", 2, _decimal_gt)
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


_DECIMAL_COLUMNS = ("price", "iva_rate", "website_qty")


def _row_to_decimal(row: dict) -> dict:
    """Convert SQLite TEXT decimal columns to ``Decimal`` before ``build_product``.

    Production ``to_decimal`` rejects strings by design; the synthetic SQLite
    fixture stores money/rate/qty as TEXT, so the test adapter performs the
    exact base-10 conversion here (never in production parsing).
    """
    out = dict(row)
    for col in _DECIMAL_COLUMNS:
        raw = out.get(col)
        if raw is None or isinstance(raw, Decimal):
            continue
        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                out[col] = None
                continue
            try:
                out[col] = Decimal(text)
            except InvalidOperation:
                out[col] = None
        else:
            out[col] = None
    return out


def _quote_products(conn: sqlite3.Connection, query: str, limit: int = 6) -> list[dict]:
    """Run the shared builder against SQLite and build closed product dicts."""
    sql = build_quote_search_sql(limit=limit, dialect="sqlite")
    pattern = f"%{query}%"
    rows = [dict(r) for r in conn.execute(sql, (pattern, pattern)).fetchall()]
    return [build_product(j3_row=_row_to_decimal(r)) for r in rows]


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
    assert "DECIMAL(18, 4)" not in sql  # no precision-truncating cast on money/stock
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

    monkeypatch.setattr(
        "business_analyzer.core.database.Database",
        lambda suppress_error_details=False: FakeDB(),
    )
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
        "price": Decimal("999.99"),
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
        "price": Decimal("500.0"),
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

    monkeypatch.setattr(
        "business_analyzer.core.database.Database",
        lambda suppress_error_details=False: FailDB(),
    )
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


@pytest.mark.unit
def test_quote_search_strict_type_rejection():
    # J3 ``to_decimal``: float/string/bool/non-finite rejected; only finite
    # Decimal and non-bool int accepted.
    assert to_decimal(1.5) is None
    assert to_decimal("100.0000") is None
    assert to_decimal(True) is None
    assert to_decimal(False) is None
    assert to_decimal(Decimal("NaN")) is None
    assert to_decimal(Decimal("Infinity")) is None
    assert to_decimal(None) is None
    assert to_decimal(Decimal("100.0000")) == Decimal("100.0000")
    assert to_decimal(100) == Decimal("100")

    # Magento display price: float/string/bool/non-finite rejected.
    assert magento_price_string(999.99) is None
    assert magento_price_string("999.99") is None
    assert magento_price_string(True) is None
    assert magento_price_string(Decimal("NaN")) is None
    assert magento_price_string(Decimal("999.99")) == "999.99"
    assert magento_price_string(999) == "999"


@pytest.mark.unit
def test_quote_search_j3_and_magento_float_string_fail_closed():
    # J3 float/string figures fail closed to null (never float, never str).
    p = build_product(
        j3_row={
            "sku": "X",
            "name": "N",
            "price": 100.0,
            "iva_rate": "19.000",
            "line_id": 1,
            "website_qty": "3.0000",
        }
    )
    assert p["price"] is None
    assert p["j3_price"] is None
    assert p["iva_rate"] is None
    assert p["price_with_iva"] is None
    assert p["price_with_iva_reason"] == "j3_price_missing"
    assert p["website_qty"] is None
    assert p["in_stock"] is None

    j3 = {
        "sku": "X",
        "name": "N",
        "price": Decimal("100.0000"),
        "iva_rate": Decimal("19.000"),
        "line_id": 1,
        "website_qty": Decimal("3.0000"),
    }
    assert (
        build_product(j3_row=j3, magento={"sku": "X", "price": 123.45})["magento_price"]
        is None
    )
    assert (
        build_product(j3_row=j3, magento={"sku": "X", "price": "123.45"})[
            "magento_price"
        ]
        is None
    )


@pytest.mark.unit
def test_quote_search_exact_fractional_stock_beyond_4_digits():
    conn = _make_db()
    conn.execute(
        "INSERT INTO AdmLineas (LineasID, LineasPorcentaje) VALUES (1, '19.000')"
    )
    conn.execute(
        "INSERT INTO AdmArticulos (ArticulosID, ArticulosCodigo, ArticulosNombre, "
        "ArticulosVenta, LineasID, ArticulosEstado) VALUES "
        "(1, 'F1', 'PRODUCTO F', '100.0000', 1, 1)"
    )
    _seed_stock(conn, [(1, "0.123456")])
    products = _quote_products(conn, "producto")
    p = products[0]
    assert p["website_qty"] == "0.123456"  # exact, beyond 4 digits, never rounded
    assert p["in_stock"] is True


@pytest.mark.unit
def test_quote_search_ignores_q_alias():
    out = _tool_quote_search(ToolContext(audience=Audience.SALES), {"q": "cemento"})
    assert out["status"] == "error"
    assert out["reason"] == "query_required"


@pytest.mark.unit
def test_quote_search_input_query_schema():
    for bad in (123, ["cemento"], {"a": 1}, None):
        out = _tool_quote_search(ToolContext(audience=Audience.SALES), {"query": bad})
        assert out["status"] == "error"
        assert out["reason"] == "query_required"
    assert (
        _tool_quote_search(ToolContext(audience=Audience.SALES), {"query": "a"})[
            "reason"
        ]
        == "query_required"
    )
    assert (
        _tool_quote_search(ToolContext(audience=Audience.SALES), {"query": "  "})[
            "reason"
        ]
        == "query_required"
    )
    assert (
        _tool_quote_search(ToolContext(audience=Audience.SALES), {})["reason"]
        == "query_required"
    )


@pytest.mark.unit
def test_quote_search_limit_parsing(monkeypatch: pytest.MonkeyPatch):
    captured = []

    class FakeDB:
        def __init__(self, suppress_error_details=False):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute_query(self, sql, params):
            captured.append(sql)
            return []

    monkeypatch.setattr("business_analyzer.core.database.Database", FakeDB)

    def top_for(limit_value):
        captured.clear()
        _tool_quote_search(
            ToolContext(audience=Audience.SALES),
            {"query": "cemento", "limit": limit_value},
        )
        return captured[-1] if captured else ""

    assert "TOP 6" in top_for(None)  # missing/None → default 6
    assert "TOP 6" in top_for("x")  # string → default 6
    assert "TOP 6" in top_for(3.7)  # float → default 6
    assert "TOP 6" in top_for(True)  # bool → default 6
    assert "TOP 1" in top_for(0)  # supplied 0 clamps to 1, not default
    assert "TOP 1" in top_for(-5)  # negative clamps to 1
    assert "TOP 10" in top_for(99)  # above max clamps to 10
    assert "TOP 5" in top_for(5)  # valid int passes through


@pytest.mark.unit
def test_quote_search_malformed_result_set(monkeypatch: pytest.MonkeyPatch):
    class NonListDB:
        def __init__(self, suppress_error_details=False):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute_query(self, sql, params):
            return "not-a-list"

    monkeypatch.setattr("business_analyzer.core.database.Database", NonListDB)
    out = _tool_quote_search(ToolContext(audience=Audience.SALES), {"query": "cemento"})
    assert out["status"] == "error"
    assert out["reason"] == "catalog_unavailable"
    assert out["products"] == []


@pytest.mark.unit
def test_quote_search_non_mapping_row(monkeypatch: pytest.MonkeyPatch):
    class BadRowDB:
        def __init__(self, suppress_error_details=False):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute_query(self, sql, params):
            return [
                {
                    "sku": "OK",
                    "name": "N",
                    "price": Decimal("1.0000"),
                    "iva_rate": Decimal("19.000"),
                    "line_id": 1,
                    "website_qty": Decimal("1.0000"),
                },
                "not-a-mapping",
            ]

    monkeypatch.setattr("business_analyzer.core.database.Database", BadRowDB)
    out = _tool_quote_search(ToolContext(audience=Audience.SALES), {"query": "cemento"})
    assert out["status"] == "error"
    assert out["reason"] == "catalog_unavailable"
    assert out["products"] == []
    assert "not-a-mapping" not in json.dumps(out)


_REQUIRED_ALIASES = ("sku", "name", "price", "iva_rate", "line_id", "website_qty")


def _full_j3_row() -> dict:
    return {
        "sku": "SKU-OK",
        "name": "PRODUCTO OK",
        "price": Decimal("1.0000"),
        "iva_rate": Decimal("19.000"),
        "line_id": 1,
        "website_qty": Decimal("1.0000"),
    }


def _tool_with_rows(monkeypatch: pytest.MonkeyPatch, rows) -> dict:
    class FakeDB:
        def __init__(self, suppress_error_details=False):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute_query(self, sql, params):
            return rows

    monkeypatch.setattr("business_analyzer.core.database.Database", FakeDB)
    return _tool_quote_search(
        ToolContext(audience=Audience.SALES), {"query": "cemento"}
    )


@pytest.mark.unit
def test_quote_search_missing_required_alias(monkeypatch: pytest.MonkeyPatch):
    for missing in _REQUIRED_ALIASES:
        row = {k: v for k, v in _full_j3_row().items() if k != missing}
        out = _tool_with_rows(monkeypatch, [row])
        assert out["status"] == "error"
        assert out["reason"] == "catalog_unavailable"
        assert out["products"] == []
        text = json.dumps(out)
        assert "SKU-OK" not in text
        assert "PRODUCTO" not in text


@pytest.mark.unit
def test_quote_search_blank_sku_not_silently_dropped(monkeypatch: pytest.MonkeyPatch):
    for sku_value in ("", "   ", None):
        row = _full_j3_row()
        row["sku"] = sku_value
        out = _tool_with_rows(monkeypatch, [row])
        assert out["status"] == "error"
        assert out["reason"] == "catalog_unavailable"
        assert out["products"] == []
        text = json.dumps(out)
        assert "PRODUCTO" not in text


@pytest.mark.unit
def test_quote_search_malformed_row_no_partial_products(
    monkeypatch: pytest.MonkeyPatch,
):
    # A valid row followed by a malformed row must emit nothing (atomic reject).
    rows = [_full_j3_row(), {k: v for k, v in _full_j3_row().items() if k != "price"}]
    out = _tool_with_rows(monkeypatch, rows)
    assert out["status"] == "error"
    assert out["reason"] == "catalog_unavailable"
    assert out["products"] == []
    assert "SKU-OK" not in json.dumps(out)


def _bare_db(suppress: bool, connection) -> Database:
    db = object.__new__(Database)
    db._suppress_error_details = suppress
    db._connection = connection
    db._pool_enabled = False
    return db


@pytest.mark.unit
def test_database_suppress_error_details(monkeypatch: pytest.MonkeyPatch, caplog):
    class FakeCursor:
        def execute(self, query, params=None):
            raise Exception("sentinel-SECRET-DSN")

        def close(self):
            pass

    class FakeConn:
        def cursor(self, *args, **kwargs):
            return FakeCursor()

    db = _bare_db(True, FakeConn())
    monkeypatch.setattr(db, "ping", lambda: True)

    with caplog.at_level(logging.WARNING):
        with pytest.raises(QueryError) as exc:
            db.execute_query("SELECT 1 WHERE x = %s", ("secret-param",))

    assert str(exc.value) == "Query failed"
    assert exc.value.__cause__ is None
    assert "sentinel" not in caplog.text
    assert "SECRET" not in caplog.text
    assert "secret-param" not in caplog.text


def _configured_magento(monkeypatch: pytest.MonkeyPatch, search_products):
    """Configure Magento with a fake client; record whether sales-history search
    helpers are ever invoked (they must not be for quote_search)."""
    calls = {"generic_search": 0, "db_search": 0}

    def _spy_generic(ctx, params):
        calls["generic_search"] += 1
        return {"products": [], "source": "none"}

    def _spy_db(query, limit=5):
        calls["db_search"] += 1
        return []

    monkeypatch.setattr("depotru_tools.builtins._tool_search_products", _spy_generic)
    monkeypatch.setattr("depotru_tools.builtins._search_products_db", _spy_db)

    from depotru_integrations.magento.client import MagentoConfig, MagentoRestClient

    monkeypatch.setattr(
        MagentoConfig,
        "from_env",
        classmethod(
            lambda cls: MagentoConfig(base_url="https://m.example", access_token="t")
        ),
    )
    monkeypatch.setattr(MagentoRestClient, "search_products", search_products)
    return calls


@pytest.mark.unit
def test_quote_search_never_uses_sales_history_search(
    monkeypatch: pytest.MonkeyPatch,
):
    def _fake_magento_search(self, query, *, page_size=5):
        return [
            {
                "sku": "SKU1",
                "name": "MAGENTO NAME",
                "price": Decimal("999.99"),
                "product_url": "https://m.example/p.html",
            }
        ]

    calls = _configured_magento(monkeypatch, _fake_magento_search)

    class FakeDB:
        def __init__(self, suppress_error_details=False):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute_query(self, sql, params):
            return [
                {
                    "sku": "SKU1",
                    "name": "J3 NAME",
                    "price": Decimal("100.0000"),
                    "iva_rate": Decimal("19.000"),
                    "line_id": 1,
                    "website_qty": Decimal("3.0000"),
                }
            ]

    monkeypatch.setattr("business_analyzer.core.database.Database", FakeDB)

    out = _tool_quote_search(ToolContext(audience=Audience.SALES), {"query": "cemento"})

    assert calls["generic_search"] == 0
    assert calls["db_search"] == 0
    assert out["status"] == "ok"
    assert out["source"] == "j3"
    p = out["products"][0]
    assert p["source"] == "j3+magento"
    assert p["name"] == "MAGENTO NAME"
    assert p["price"] == "100.0000"  # Magento never replaces J3 price
    assert p["magento_price"] == "999.99"
    assert all(prod.get("source") != "banco_datos" for prod in out["products"])


@pytest.mark.unit
@pytest.mark.parametrize("behavior", ["empty", "raise", "malformed"])
def test_quote_search_magento_fail_closed_no_sales_history(
    monkeypatch: pytest.MonkeyPatch, behavior
):
    def _fake_magento_search(self, query, *, page_size=5):
        if behavior == "empty":
            return []
        if behavior == "raise":
            raise RuntimeError("magento-boom")
        return "not-a-list"  # malformed

    calls = _configured_magento(monkeypatch, _fake_magento_search)

    class FakeDB:
        def __init__(self, suppress_error_details=False):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute_query(self, sql, params):
            return [
                {
                    "sku": "SKU1",
                    "name": "J3 NAME",
                    "price": Decimal("100.0000"),
                    "iva_rate": Decimal("19.000"),
                    "line_id": 1,
                    "website_qty": Decimal("3.0000"),
                }
            ]

    monkeypatch.setattr("business_analyzer.core.database.Database", FakeDB)

    out = _tool_quote_search(ToolContext(audience=Audience.SALES), {"query": "cemento"})

    assert calls["generic_search"] == 0
    assert calls["db_search"] == 0
    assert out["status"] == "ok"
    assert out["source"] == "j3"
    assert out["products"][0]["source"] == "j3"
    assert all(prod.get("source") != "banco_datos" for prod in out["products"])


@pytest.mark.unit
def test_quote_search_magento_only_without_sales_history(
    monkeypatch: pytest.MonkeyPatch,
):
    def _fake_magento_search(self, query, *, page_size=5):
        return [
            {
                "sku": "M1",
                "name": "MAG ONLY",
                "price": Decimal("500.0"),
                "product_url": "https://m.example/m.html",
            }
        ]

    calls = _configured_magento(monkeypatch, _fake_magento_search)

    class EmptyDB:
        def __init__(self, suppress_error_details=False):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute_query(self, sql, params):
            return []

    monkeypatch.setattr("business_analyzer.core.database.Database", EmptyDB)

    out = _tool_quote_search(ToolContext(audience=Audience.SALES), {"query": "mago"})

    assert calls["generic_search"] == 0
    assert calls["db_search"] == 0
    assert out["status"] == "ok"
    assert out["source"] == "magento"
    p = out["products"][0]
    assert p["source"] == "magento"
    assert p["sku"] == "M1"
    assert all(prod.get("source") != "banco_datos" for prod in out["products"])


@pytest.mark.unit
def test_quote_search_build_product_exception_fixed_error(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeDB:
        def __init__(self, suppress_error_details=False):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute_query(self, sql, params):
            return [
                {
                    "sku": "SKU1",
                    "name": "N",
                    "price": Decimal("1.0000"),
                    "iva_rate": Decimal("19.000"),
                    "line_id": 1,
                    "website_qty": Decimal("1.0000"),
                }
            ]

    monkeypatch.setattr("business_analyzer.core.database.Database", FakeDB)

    def _boom(*args, **kwargs):
        raise ValueError("unexpected-decimal-validation-detail")

    monkeypatch.setattr("business_analyzer.core.quote_search_iva.build_product", _boom)

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
    text = json.dumps(out)
    assert "unexpected" not in text
    assert "decimal" not in text
    assert "SKU1" not in text


@pytest.mark.unit
def test_database_default_behavior_unchanged(monkeypatch: pytest.MonkeyPatch):
    class FakeCursor:
        def execute(self, query, params=None):
            raise Exception("sentinel-SECRET-DSN")

        def close(self):
            pass

    class FakeConn:
        def cursor(self, *args, **kwargs):
            return FakeCursor()

    db = _bare_db(False, FakeConn())
    monkeypatch.setattr(db, "ping", lambda: True)

    with pytest.raises(QueryError) as exc:
        db.execute_query("SELECT 1 WHERE x = %s", ("secret-param",))

    assert "sentinel" in str(exc.value)
    assert "SECRET" in str(exc.value)
    assert exc.value.__cause__ is not None


@pytest.mark.unit
def test_database_transient_branch_suppress(monkeypatch: pytest.MonkeyPatch, caplog):
    invalidations = []

    class FakeCursor:
        def execute(self, query, params=None):
            raise Exception("synthetic-TRANSIENT-marker-SECRET")

        def close(self):
            pass

    class FakeConn:
        def cursor(self, *args, **kwargs):
            return FakeCursor()

    db = _bare_db(True, FakeConn())
    monkeypatch.setattr(db, "ping", lambda: True)
    monkeypatch.setattr(db, "_invalidate_connection", lambda: invalidations.append(1))
    monkeypatch.setattr(
        "business_analyzer.core.database.is_transient_db_error", lambda e: True
    )
    monkeypatch.setattr(
        "business_analyzer.core.database.time.sleep", lambda *a, **k: None
    )
    monkeypatch.setenv("DB_QUERY_RETRIES", "2")

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(QueryError) as exc:
            db.execute_query("SELECT 1 WHERE x = %s", ("secret-param",))

    assert str(exc.value) == "Query failed"
    assert exc.value.__cause__ is None
    assert len(invalidations) == 2
    assert "synthetic" not in caplog.text
    assert "TRANSIENT" not in caplog.text
    assert "SECRET" not in caplog.text
    assert "secret-param" not in caplog.text


@pytest.mark.unit
def test_database_connect_and_close_suppress(monkeypatch: pytest.MonkeyPatch, caplog):
    db = object.__new__(Database)
    db._connection = None
    db._suppress_error_details = True
    db.connection_type = ConnectionType.DIRECT

    def _raise_synthetic():
        raise Exception("synthetic-CONNECT-SECRET-DSN")

    monkeypatch.setattr(db, "_get_connection_details", _raise_synthetic)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(DBConnectionError) as exc:
            db.connect()
    assert str(exc.value) == "Failed to connect"
    assert exc.value.__cause__ is None
    assert "synthetic" not in caplog.text
    assert "CONNECT" not in caplog.text
    assert "SECRET" not in caplog.text

    class FakeCloseConn:
        def close(self):
            raise Exception("sentinel-close-error")

    db2 = _bare_db(True, FakeCloseConn())
    with caplog.at_level(logging.WARNING):
        db2.close()
    assert "sentinel" not in caplog.text
    assert db2._connection is None
