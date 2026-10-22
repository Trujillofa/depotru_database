"""Isolated B2 unit tests: run with --noconftest --disable-plugin-autoload.

The database module is replaced before core imports; no settings are loaded.
All data below are synthetic sentinels, unrelated to any customer or catalog.
"""

from __future__ import annotations

import importlib
import re
import socket
import sqlite3
import sys
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest

from depotru_kernel.auth import Audience, ToolScope, audience_may_use
from depotru_tools.builtins import _tool_quote_for_customer, register_builtin_tools
from depotru_tools.registry import ToolContext, ToolPermissionError, ToolRegistry

pytestmark = pytest.mark.unit
TOOL = "catalog.quote_for_customer"
SERVER_ID = 73  # Synthetic internal identity, never returned.
IDENTITY_KEY = "verified_customer_terceros_id"
SKU = "SYNTHETIC-A"
PRIVATE_SENTINEL = "SYNTHETIC-PRIVATE-DO-NOT-RETURN"
BAJA_ROTACION = "B.ROT"
CONTRACT_DIR = Path(__file__).resolve().parents[2] / "docs" / "contracts"
CONTRACT = CONTRACT_DIR / "catalog-quote-for-customer.md"

# Canonical fixed-point strings produced by the Decimal JSON serialiser.
DEFAULT_PRICE = "12.50"
DEFAULT_QTY = "4.25"


def tariff_row(**changes):
    return {
        "tarifas_id": 3,
        "tarifa_codigo": "SYNTHETIC-TARIFF",
        "tarifa_nombre": "TARIFA SINTETICA",
        "TercerosID": SERVER_ID,
        "TercerosNombres": PRIVATE_SENTINEL,
        **changes,
    }


def article_row(**changes):
    return {
        "sku": SKU,
        "name": "ARTICULO SINTETICO",
        "price_rows": 1,
        "price_min": Decimal("12.50"),
        "price_max": Decimal("12.50"),
        "qty": Decimal("4.25"),
        "baja_rotacion": Decimal("0"),
        "TercerosID": SERVER_ID,
        "TercerosNombres": PRIVATE_SENTINEL,
        **changes,
    }


def assert_sanitized(payload):
    """Structural leak checks; no substring scanning of identity values."""
    forbidden = {
        IDENTITY_KEY,
        "customer_id",
        "terceros_id",
        "TercerosID",
        "TercerosNombres",
        "TercerosCelular",
        "TercerosIdentificacion",
        "phone",
        "telefono",
        "cost",
        "margin",
        "price_includes_iva",
        "unit",
    }

    def check(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for nested in value.values():
                check(nested)
        elif isinstance(value, list):
            for nested in value:
                check(nested)
        else:
            assert value != SERVER_ID
            assert value != PRIVATE_SENTINEL

    check(payload)
    assert payload["iva_status"] == "unknown"
    if payload.get("site"):
        coverage = payload["stock_coverage"]
        assert coverage["status"] == "physical_warehouses_only"
        assert coverage["virtual_warehouses_reported_separately"] is True
        assert coverage["overlap_possible"] is True
        assert "reason" not in coverage
        assert "unmapped_warehouses" not in coverage
        virtual = coverage["virtual_warehouses"]
        assert [w["code"] for w in virtual] == [BAJA_ROTACION]
        assert virtual[0]["site"] is None
        assert virtual[0]["kind"] == "virtual"
        assert BAJA_ROTACION not in coverage["mapped_warehouses"]


@pytest.fixture
def harness(monkeypatch):
    def forbidden_network(*args, **kwargs):
        raise AssertionError("Network forbidden in isolated B2 tests")

    monkeypatch.setattr(socket.socket, "connect", forbidden_network)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden_network)
    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden_network)

    class FakeDB:
        constructed = 0
        calls = []
        results = [[tariff_row()], [article_row()]]
        opening_error = None
        entering_error = None

        def __init__(self):
            type(self).constructed += 1
            if self.opening_error:
                raise self.opening_error

        def __enter__(self):
            if self.entering_error:
                raise self.entering_error
            return self

        def __exit__(self, *args):
            return False

        def execute_query(self, sql, params):
            self.calls.append((sql, params))
            result = self.results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        @staticmethod
        def validate_sql_identifier(value, label):
            assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value)
            return value

    # The real database/config modules must never be imported by this slice.
    database = ModuleType("business_analyzer.core.database")
    database.Database = FakeDB
    database.DatabaseError = RuntimeError
    database.ConnectionType = object
    database.env_database_name = lambda key, default: default
    monkeypatch.setitem(sys.modules, database.__name__, database)

    # Snapshot the modules imported under the fake database so a later test in
    # the same session never reuses a module bound to a stale fake.
    tracked = (
        "business_analyzer.core.j3system_customer_quote",
        "business_analyzer.core.j3system_sales_warehouse",
        "business_analyzer.core.website_warehouse_policy",
    )
    saved = {name: sys.modules.get(name) for name in tracked}
    for name in tracked:
        sys.modules.pop(name, None)

    quote = importlib.import_module("business_analyzer.core.j3system_customer_quote")
    registry = ToolRegistry()
    register_builtin_tools(registry)

    class Harness:
        db = FakeDB
        module = quote
        tools = registry

        def invoke(self, params=None, extras=None, audience=Audience.SALES):
            result = registry.call(
                TOOL,
                {"site": "neiva", "skus": [SKU]} if params is None else params,
                context=ToolContext(
                    audience=audience,
                    extras={IDENTITY_KEY: SERVER_ID} if extras is None else extras,
                ),
            )
            assert_sanitized(result)
            return result

    try:
        yield Harness()
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def test_registration_and_closed_schema(harness):
    spec = harness.tools.get(TOOL)
    assert spec.scope == ToolScope.SALES_PORTFOLIO
    assert spec.public_safe is False
    assert set(spec.parameters_schema) == {"site", "skus"}
    assert TOOL in {s["name"] for s in harness.tools.list_tools(Audience.SALES)}
    assert TOOL in {s["name"] for s in harness.tools.list_tools(Audience.ADMIN)}
    assert audience_may_use(Audience.ADMIN, ToolScope.SALES_PORTFOLIO)


@pytest.mark.parametrize(
    "audience",
    [
        Audience.PUBLIC,
        Audience.CUSTOMER,
        Audience.WAREHOUSE,
        Audience.SERVICE,
        Audience.AGENT,
    ],
)
def test_other_audiences_cannot_discover_or_invoke(harness, audience):
    assert TOOL not in {s["name"] for s in harness.tools.list_tools(audience)}
    with pytest.raises(ToolPermissionError):
        harness.invoke(audience=audience)
    result = _tool_quote_for_customer(ToolContext(audience=audience), {})
    assert result["reason"] == "audience_not_allowed"
    assert_sanitized(result)
    assert harness.db.constructed == 0


@pytest.mark.parametrize(
    "extras", [{}, {"customer_id": SERVER_ID}, {"terceros_id": SERVER_ID}]
)
def test_missing_verified_identity_fails_before_db(harness, extras):
    assert harness.invoke(extras=extras)["reason"] == "verified_customer_required"
    assert harness.db.constructed == 0


@pytest.mark.parametrize(
    "identity",
    [None, 0, -1, True, False, 1.5, "SYNTHETIC-INVALID", "", {}, [], "²", 2**40],
)
def test_invalid_verified_identity_fails_before_db(harness, identity):
    result = harness.invoke(extras={IDENTITY_KEY: identity})
    assert result["reason"] == "verified_customer_required"
    assert harness.db.constructed == 0


@pytest.mark.parametrize(
    "key",
    [
        "customer_id",
        "terceros_id",
        "phone",
        "telefono",
        "tercero",
        IDENTITY_KEY,
        "extra",
    ],
)
def test_unknown_model_keys_fail_before_db_even_with_valid_identity(harness, key):
    result = harness.invoke({"site": "neiva", "skus": [SKU], key: "SYNTHETIC-REJECTED"})
    assert result["reason"] == "unexpected_parameters"
    assert harness.db.constructed == 0


def test_unknown_keys_precede_identity_validation(harness):
    assert (
        harness.invoke({"extra": True}, extras={})["reason"] == "unexpected_parameters"
    )
    assert harness.db.constructed == 0


@pytest.mark.parametrize("site", [None, "", "SYNTHETIC-UNKNOWN", [], {}, True])
def test_invalid_site_fails_before_db(harness, site):
    assert harness.invoke({"site": site, "skus": [SKU]})["reason"] == "site_invalid"
    assert harness.db.constructed == 0


@pytest.mark.parametrize(
    "skus,reason",
    [
        (None, "skus_required"),
        ([], "skus_required"),
        (42, "skus_required"),
        ([SKU] * 21, "too_many_skus"),
        (["SYNTHETIC-" + "X" * 40], "invalid_sku"),
        (["SYNTHETIC'"], "invalid_sku"),
        (["SYNTHETIC A"], "invalid_sku"),
        (["SYNTHETIC;DROP"], "invalid_sku"),
        (["SYNTHETIC\nA"], "invalid_sku"),
        (["SYNTHETIC-Á"], "invalid_sku"),
        ([None], "invalid_sku"),
        ([{}], "invalid_sku"),
        ([True], "invalid_sku"),
        ([""], "invalid_sku"),
    ],
)
def test_invalid_skus_and_caps_fail_before_db(harness, skus, reason):
    assert harness.invoke({"site": "neiva", "skus": skus})["reason"] == reason
    assert harness.db.constructed == 0


def test_request_normalization_and_deduplication(harness):
    result = harness.invoke(
        {"site": " NEIVA ", "skus": [SKU, f" {SKU.lower()} "]},
        extras={IDENTITY_KEY: f" {SERVER_ID} "},
    )
    assert result["status"] == "ok"
    assert len(result["lines"]) == 1
    assert result["lines"][0]["sku"] == SKU
    assert harness.db.calls[0][1] == (SERVER_ID,)


def test_sku_casing_preserves_first_occurrence(harness):
    first = "synthetic-a"
    later = "SYNTHETIC-A"
    harness.db.results[1] = [article_row(sku=later)]
    result = harness.invoke({"site": "neiva", "skus": [first, later]})
    assert len(result["lines"]) == 1
    assert result["lines"][0]["sku"] == first
    assert result["lines"][0]["status"] == "ok"


def test_maximum_sku_count_and_length_are_accepted(harness):
    skus = ["SYNTHETIC-" + chr(ord("A") + i) for i in range(19)] + ["X" * 40]
    harness.db.results[1] = [article_row(sku=sku) for sku in skus]
    result = harness.invoke({"site": "neiva", "skus": skus})
    assert result["status"] == "ok"
    assert len(result["lines"]) == 20


@pytest.mark.parametrize(
    "site,warehouses",
    [
        ("neiva", {"ALM", "BD6", "SUR", "DIS", "BOD"}),
        ("florencia", {"FLO"}),
    ],
)
def test_bound_parameters_bounded_aggregates_and_net_quote(harness, site, warehouses):
    result = harness.invoke({"site": site, "skus": [SKU]})
    assert result["status"] == "ok"
    line = result["lines"][0]
    assert (line["price"], line["qty"], line["stock_status"]) == (
        DEFAULT_PRICE,
        DEFAULT_QTY,
        "available",
    )
    assert set(result["stock_coverage"]["mapped_warehouses"]) == warehouses
    customer_sql, customer_params = harness.db.calls[0]
    quote_sql, quote_params = harness.db.calls[1]
    assert customer_params == (SERVER_ID,)
    assert quote_params == (3,)
    assert customer_sql.count("%s") == quote_sql.count("%s") == 1
    assert "TOP 2 " in customer_sql and "t.TercerosID = %s" in customer_sql
    assert "TOP 21 " in quote_sql
    assert quote_sql.endswith("ORDER BY a.ArticulosCodigo, a.ArticulosID")
    assert "ORDER BY ArticulosCodigo, ArticulosID" in quote_sql
    assert f"ArticulosCodigo IN ('{SKU}')" in quote_sql
    assert "p.ArticulosID IN (SELECT ArticulosID FROM targets)" in quote_sql
    assert "e.ArticulosID IN (SELECT ArticulosID FROM targets)" in quote_sql
    assert "p.TarifasID = %s AND p.Cantidad = 0" in quote_sql
    assert "COUNT(*) = COUNT(SaldoActual)" in quote_sql
    assert "COUNT(CASE WHEN p.PreciosValor > 0 THEN 1 END) AS price_rows" in quote_sql
    assert "CAST(" not in quote_sql
    wh_filter = re.search(r"al\.AlmacenCodigo IN \(([^)]+)\)", quote_sql).group(1)
    assert set(re.findall(r"'([^']+)'", wh_filter)) == warehouses
    assert "TercerosID" not in quote_sql and str(SERVER_ID) not in customer_sql
    for forbidden in (
        "TercerosNombres",
        "TercerosCelular",
        "TercerosIdentificacion",
        "ArticulosCosto",
        "ValorCosto",
        "ArticulosMargen",
        "ArticulosVenta",
        "PreciosIncremento",
        "Magento",
        "INSERT",
        "UPDATE",
        "DELETE",
    ):
        assert forbidden not in customer_sql + quote_sql


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"tarifas_id": None}, "tariff_missing"),
        ({"tarifas_id": 0}, "tariff_missing"),
        ({"tarifas_id": -1}, "tariff_missing"),
        ({"tarifas_id": True}, "tariff_missing"),
        ({"tarifas_id": 3.5}, "tariff_missing"),
        ({"tarifas_id": "SYNTHETIC-INVALID"}, "tariff_missing"),
        ({"tarifa_codigo": "", "tarifa_nombre": ""}, "tariff_missing"),
        ({"tarifas_id": 6}, "tariff_refused"),
        ({"tarifa_codigo": "006"}, "tariff_refused"),
        ({"tarifa_nombre": " al costo "}, "tariff_refused"),
        ({"tarifa_nombre": "AL  COSTO"}, "tariff_refused"),
    ],
)
def test_missing_and_cost_tariffs_never_query_item_prices(harness, changes, reason):
    harness.db.results[0] = [tariff_row(**changes)]
    result = harness.invoke()
    assert result["reason"] == reason
    assert len(harness.db.calls) == 1
    assert "AdmPrecios" not in harness.db.calls[0][0]
    # A refusal/missing tariff never echoes tariff metadata.
    assert "tariff" not in result


@pytest.mark.parametrize(
    "rows,reason",
    [
        ([], "customer_not_found"),
        ([tariff_row(), tariff_row()], "customer_ambiguous"),
        ([tariff_row()] * 3, "erp_unavailable"),
        ([None], "erp_unavailable"),
        (None, "erp_unavailable"),
    ],
)
def test_customer_lookup_cardinality_and_shape(harness, rows, reason):
    harness.db.results[0] = rows
    assert harness.invoke()["reason"] == reason
    assert len(harness.db.calls) == 1


@pytest.mark.parametrize(
    "qty",
    [
        None,
        "",
        "SYNTHETIC-INVALID",
        True,
        False,
        -1,
        float("nan"),
        float("inf"),
        -float("inf"),
        {},
    ],
)
def test_invalid_quantity_stays_unknown(harness, qty):
    harness.db.results[1] = [article_row(qty=qty)]
    line = harness.invoke()["lines"][0]
    assert line["price"] == DEFAULT_PRICE
    assert line["qty"] is None and line["stock_status"] == "unknown"


def test_float_quantity_is_rejected_as_unknown(harness):
    # A float cannot prove it kept precision, so it is rejected even if finite.
    harness.db.results[1] = [article_row(qty=4.25)]
    line = harness.invoke()["lines"][0]
    assert line["qty"] is None and line["stock_status"] == "unknown"


def test_missing_quantity_stays_unknown(harness):
    row = article_row()
    row.pop("qty")
    harness.db.results[1] = [row]
    line = harness.invoke()["lines"][0]
    assert line["qty"] is None and line["stock_status"] == "unknown"


def test_explicit_zero_is_only_zero_in_site_warehouses(harness):
    harness.db.results[1] = [article_row(qty=Decimal("0"))]
    result = harness.invoke()
    assert result["lines"][0]["qty"] == "0"
    assert result["lines"][0]["stock_status"] == "zero_in_mapped_warehouses"
    assert result["stock_coverage"]["status"] == "physical_warehouses_only"


def test_missing_article_has_neither_price_nor_stock(harness):
    harness.db.results[1] = []
    result = harness.invoke()
    assert result["status"] == "error" and result["reason"] == "article_not_found"
    line = result["lines"][0]
    assert line["price"] is None and line["qty"] is None
    assert line["stock_status"] == "unknown"


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"price_rows": 0}, "price_missing"),
        ({"price_min": None}, "price_missing"),
        ({"price_min": Decimal("0")}, "price_missing"),
        ({"price_min": 0}, "price_missing"),
        ({"price_min": Decimal("-0.01")}, "price_missing"),
        ({"price_min": -1}, "price_missing"),
        ({"price_min": float("nan")}, "price_missing"),
        ({"price_rows": "SYNTHETIC-INVALID"}, "price_missing"),
        ({"price_rows": Decimal("1.5")}, "price_missing"),
        ({"price_rows": 2, "price_max": Decimal("12.51")}, "price_ambiguous"),
        ({"price_rows": 2, "price_max": None}, "price_ambiguous"),
    ],
)
def test_missing_and_ambiguous_prices(harness, changes, reason):
    harness.db.results[1] = [article_row(**changes)]
    result = harness.invoke()
    assert result["status"] == "error" and result["reason"] == reason
    assert result["lines"][0]["price"] is None


@pytest.mark.parametrize(
    "price_rows",
    [
        -1,
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
        "²",
        "١٢٣",
        "\u0661\u0662",
    ],
)
def test_malformed_count_yields_price_missing(harness, price_rows):
    harness.db.results[1] = [article_row(price_rows=price_rows)]
    result = harness.invoke()
    assert result["status"] == "error" and result["reason"] == "price_missing"
    assert result["lines"][0]["price"] is None


@pytest.mark.parametrize("price_rows", [Decimal("2.0"), " 2 "])
def test_valid_count_forms_are_quotable(harness, price_rows):
    harness.db.results[1] = [article_row(price_rows=price_rows)]
    assert harness.invoke()["lines"][0]["price"] == DEFAULT_PRICE


def test_equal_duplicate_prices_are_quotable(harness):
    harness.db.results[1] = [article_row(price_rows=2)]
    assert harness.invoke()["lines"][0]["price"] == DEFAULT_PRICE


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, 0),
        (1, 1),
        (5, 5),
        (Decimal("2.0"), 2),
        (Decimal("0"), 0),
        ("2", 2),
        (" 5 ", 5),
        (-1, None),
        (True, None),
        (False, None),
        (Decimal("NaN"), None),
        (Decimal("sNaN"), None),
        (Decimal("Infinity"), None),
        (Decimal("-Infinity"), None),
        (Decimal("-1"), None),
        (Decimal("1.5"), None),
        ("²", None),
        ("١٢٣", None),
        ("", None),
        ("  ", None),
        ("-1", None),
        (1.0, None),
        (None, None),
    ],
)
def test_as_count_edge_cases(harness, value, expected):
    assert harness.module._as_count(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (Decimal("12.50"), Decimal("12.50")),
        (Decimal("0"), Decimal("0")),
        (1, Decimal("1")),
        (0, Decimal("0")),
        ("12.50", None),
        ("", None),
        ("  12.50  ", None),
        (12.5, None),
        (0.0, None),
        (float("nan"), None),
        (float("inf"), None),
        (-1, None),
        (True, None),
        (Decimal("NaN"), None),
        (Decimal("sNaN"), None),
        (Decimal("Infinity"), None),
        (Decimal("-1"), None),
        (None, None),
        ({}, None),
        ([], None),
    ],
)
def test_as_decimal_accepts_only_decimal_and_finite_int(harness, value, expected):
    assert harness.module._as_decimal(value) == expected


def test_large_price_is_exact_fixed_point_string(harness):
    value = Decimal("1234567890123456.78")
    harness.db.results[1] = [article_row(price_min=value, price_max=value)]
    line = harness.invoke()["lines"][0]
    assert line["status"] == "ok"
    assert line["price"] == "1234567890123456.78"


def test_adjacent_large_prices_are_not_collapsed(harness):
    low = Decimal("1234567890123456.78")
    high = Decimal("1234567890123456.79")
    harness.db.results[1] = [article_row(price_rows=2, price_min=low, price_max=high)]
    result = harness.invoke()
    assert result["reason"] == "price_ambiguous"
    assert result["lines"][0]["price"] is None


def test_zero_price_is_absent_and_never_erases_a_valid_price(harness):
    """Execute the shared price aggregate in sqlite: the ambiguity count and
    the min/max operate on the same strictly-positive rows, so a zero,
    negative, or NULL price never inflates the count nor erases a valid
    positive price."""
    fragment = harness.module._price_aggregate_sql("AdmPrecios").replace("%s", "?")
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE TABLE targets (ArticulosID INTEGER PRIMARY KEY)")
        conn.execute(
            "CREATE TABLE AdmPrecios ("
            "ArticulosID INTEGER, TarifasID INTEGER, Cantidad INTEGER, "
            "PreciosValor INTEGER)"
        )
        conn.executemany(
            "INSERT INTO targets VALUES (?)",
            [(aid,) for aid in range(1, 7)],
        )
        conn.executemany(
            "INSERT INTO AdmPrecios VALUES (?, ?, ?, ?)",
            [
                # A zero beside one valid positive price: the count stays 1.
                (1, 42, 0, 0),
                (1, 42, 0, 12),
                # Negative and NULL rows beside one valid positive price.
                (2, 42, 0, -1),
                (2, 42, 0, None),
                (2, 42, 0, 12),
                # Only absent rows: no valid positive price at all.
                (3, 42, 0, 0),
                (3, 42, 0, -5),
                (3, 42, 0, None),
                # Two distinct positive prices: ambiguous.
                (4, 42, 0, 10),
                (4, 42, 0, 20),
                # Two equal positive prices: quotable duplicate, not ambiguous.
                (5, 42, 0, 12),
                (5, 42, 0, 12),
                # Non-unit row and wrong tariff are both excluded.
                (6, 42, 0, 12),
                (6, 42, 1, 99),
                (6, 99, 0, 88),
                # Article 7 is not a target: excluded by the target filter.
                (7, 42, 0, 12),
            ],
        )
        result = {
            aid: (rows, mn, mx)
            for aid, rows, mn, mx in conn.execute(fragment, (42,)).fetchall()
        }
    finally:
        conn.close()
    expected = {
        1: (1, 12, 12),
        2: (1, 12, 12),
        3: (0, None, None),
        4: (2, 10, 20),
        5: (2, 12, 12),
        6: (1, 12, 12),
    }
    assert set(result) == set(expected)
    for aid, triple in expected.items():
        assert result[aid] == triple


def test_fractional_stock_preserves_exact_scale(harness):
    harness.db.results[1] = [article_row(qty=Decimal("0.0001"))]
    line = harness.invoke()["lines"][0]
    assert line["qty"] == "0.0001"
    assert line["stock_status"] == "available"


def test_mixed_quote_has_partial_status_and_explicit_missing_article(harness):
    result = harness.invoke({"site": "neiva", "skus": [SKU, "SYNTHETIC-MISSING"]})
    assert result["status"] == "partial"
    assert result["reason"] == "article_not_found"
    assert [line["status"] for line in result["lines"]] == ["ok", "article_not_found"]


@pytest.mark.parametrize(
    "rows",
    [
        [article_row(), article_row()],
        [article_row(sku="SYNTHETIC-UNREQUESTED")],
        [article_row()] * 22,
        [None],
        None,
        {"unexpected": []},
    ],
)
def test_bad_article_results_fail_closed(harness, rows):
    harness.db.results[1] = rows
    result = harness.invoke()
    assert result["reason"] == "erp_unavailable" and result["lines"] == []


def test_duplicate_article_guard_within_row_cap(harness):
    harness.db.results[1] = [article_row(), article_row()]
    result = harness.invoke({"site": "neiva", "skus": [SKU, "SYNTHETIC-MISSING"]})
    assert result["reason"] == "erp_unavailable" and result["lines"] == []


@pytest.mark.parametrize("failure", ["construct", "enter", "customer", "quote"])
def test_db_failure_hides_driver_text_and_does_not_log(
    harness, failure, caplog, capsys
):
    error = RuntimeError(PRIVATE_SENTINEL)
    if failure == "construct":
        harness.db.opening_error = error
    elif failure == "enter":
        harness.db.entering_error = error
    else:
        harness.db.results[0 if failure == "customer" else 1] = error
    result = harness.invoke()
    assert result["reason"] == "erp_unavailable" and result["lines"] == []
    assert not caplog.records
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""


def test_admin_uses_only_explicit_kernel_inheritance(harness):
    assert harness.invoke(audience=Audience.ADMIN)["status"] == "ok"


# --- B.ROT: separate virtual warehouse without a physical site -----------


def test_baja_rotacion_is_reported_as_virtual_warehouse_without_site(harness):
    result = harness.invoke()
    coverage = result["stock_coverage"]
    assert coverage["status"] == "physical_warehouses_only"
    assert coverage["virtual_warehouses_reported_separately"] is True
    assert coverage["overlap_possible"] is True
    (virtual,) = coverage["virtual_warehouses"]
    assert virtual["code"] == BAJA_ROTACION
    assert virtual["name"] == "PRODUCTOS DE BAJA ROTACION"
    assert virtual["site"] is None
    assert virtual["kind"] == "virtual"
    assert BAJA_ROTACION not in coverage["mapped_warehouses"]
    assert "unmapped_warehouses" not in coverage
    assert "unmapped_warehouse_stock" not in str(result)


def test_brot_note_is_neutral_and_names_no_internal_person(harness):
    note = harness.invoke()["stock_coverage"]["note"]
    assert "Fredy" not in note
    assert "confirmación" in note
    assert "B.ROT" in note


def test_exact_physical_qty_is_unchanged_and_excludes_baja_rotacion(harness):
    row = article_row(qty=Decimal("4.25"), baja_rotacion=Decimal("9.5"))
    harness.db.results[1] = [row]
    line = harness.invoke()["lines"][0]
    assert line["qty"] == "4.25"
    assert line["stock_status"] == "available"
    assert line["baja_rotacion"] == "9.5"


def test_exact_baja_rotacion_quantity_is_surfaced_separately(harness):
    row = article_row(qty=Decimal("4.25"), baja_rotacion=Decimal("9.5"))
    harness.db.results[1] = [row]
    line = harness.invoke()["lines"][0]
    assert line["baja_rotacion"] == "9.5"
    assert line["baja_rotacion_status"] == "present"


def test_baja_rotacion_is_never_added_to_the_physical_total(harness):
    row = article_row(qty=Decimal("4.25"), baja_rotacion=Decimal("100.5"))
    harness.db.results[1] = [row]
    line = harness.invoke()["lines"][0]
    # Structural: two independent fields, no combined figure; the physical
    # quantity is unchanged by the B.ROT quantity.
    assert line["qty"] == "4.25"
    assert line["baja_rotacion"] == "100.5"
    assert "combined_qty" not in line
    assert "total_qty" not in line


def test_independent_latest_years_are_not_collapsed(harness):
    # Physical stock and B.ROT each come from their own latest-year row,
    # possibly different years; they are surfaced independently, never summed.
    row = article_row(qty=Decimal("10.0000"), baja_rotacion=Decimal("20.0000"))
    harness.db.results[1] = [row]
    line = harness.invoke()["lines"][0]
    assert line["qty"] == "10.0000"
    assert line["baja_rotacion"] == "20.0000"
    assert line["stock_status"] == "available"
    assert line["baja_rotacion_status"] == "present"
    assert line["requires_physical_origin_confirmation"] is True


def test_baja_rotacion_only_stock_requires_human_origin_confirmation(harness):
    row = article_row(qty=Decimal("0"), baja_rotacion=Decimal("3"))
    harness.db.results[1] = [row]
    line = harness.invoke()["lines"][0]
    assert line["qty"] == "0"
    assert line["stock_status"] == "zero_in_mapped_warehouses"
    assert line["baja_rotacion"] == "3"
    assert line["baja_rotacion_status"] == "present"
    assert line["requires_physical_origin_confirmation"] is True


def test_baja_rotacion_only_stock_does_not_assert_site_availability(harness):
    row = article_row(qty=Decimal("0"), baja_rotacion=Decimal("3"))
    harness.db.results[1] = [row]
    line = harness.invoke()["lines"][0]
    assert line["stock_status"] != "available"
    assert line["qty"] == "0"


def test_baja_rotacion_flags_confirmation_even_when_site_has_stock(harness):
    row = article_row(qty=Decimal("2"), baja_rotacion=Decimal("3"))
    harness.db.results[1] = [row]
    line = harness.invoke()["lines"][0]
    assert line["requires_physical_origin_confirmation"] is True


def test_zero_baja_rotacion_is_reported_as_zero_not_available(harness):
    row = article_row(qty=Decimal("4.25"), baja_rotacion=Decimal("0"))
    harness.db.results[1] = [row]
    line = harness.invoke()["lines"][0]
    assert line["baja_rotacion"] == "0"
    assert line["baja_rotacion_status"] == "zero"
    assert line["requires_physical_origin_confirmation"] is False


@pytest.mark.parametrize(
    "baja_rotacion",
    [
        None,
        "",
        "SYNTHETIC-INVALID",
        True,
        False,
        -1,
        float("nan"),
        float("inf"),
        -float("inf"),
        {},
    ],
)
def test_invalid_baja_rotacion_stays_unknown(harness, baja_rotacion):
    harness.db.results[1] = [article_row(baja_rotacion=baja_rotacion)]
    line = harness.invoke()["lines"][0]
    assert line["baja_rotacion"] is None
    assert line["baja_rotacion_status"] == "unknown"
    # Unknown status => the confirmation flag is null, never false.
    assert line["requires_physical_origin_confirmation"] is None


def test_missing_baja_rotacion_stays_unknown(harness):
    row = article_row()
    row.pop("baja_rotacion")
    harness.db.results[1] = [row]
    line = harness.invoke()["lines"][0]
    assert line["baja_rotacion"] is None
    assert line["baja_rotacion_status"] == "unknown"
    assert line["requires_physical_origin_confirmation"] is None


def test_latest_year_window_selects_per_pair_and_guards_ties(harness):
    """Execute the shared window fragment and stock aggregate helper in
    sqlite: latest year per (article, warehouse) — never a global year, never
    summed history — and a same-year tie failing closed to NULL."""
    window = harness.module._latest_year_window
    aggregate = harness.module._stock_aggregate_sql
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(
            "CREATE TABLE stock_rows ("
            "ArticulosID INTEGER, AlmacenID INTEGER, Ano INTEGER, SaldoActual INTEGER)"
        )
        rows = [
            # Article 1: two warehouses; only each pair's latest year counts.
            (1, 10, 2023, 10),
            (1, 10, 2024, 20),
            (1, 11, 2023, 4),
            (1, 11, 2024, 5),
            # Article 2: duplicated latest-year row (tie) must fail closed.
            (2, 10, 2024, 7),
            (2, 10, 2024, 8),
            # Article 3: only an older year; per-pair selection keeps it.
            (3, 10, 2023, 100),
            # Article 4: positive older-year balance, zero latest-year balance;
            # the aggregate must return zero, never the older positive figure.
            (4, 10, 2023, 50),
            (4, 10, 2024, 0),
        ]
        conn.executemany("INSERT INTO stock_rows VALUES (?, ?, ?, ?)", rows)

        ranked = conn.execute(window("stock_rows")).fetchall()
        # rn = 1 keeps exactly one row per (article, warehouse) pair.
        assert {(r[0], r[1]) for r in ranked} == {
            (1, 10),
            (1, 11),
            (2, 10),
            (3, 10),
            (4, 10),
        }
        # Latest year per pair only: article 1's 2023 rows must not survive.
        assert {(r[1], r[2], r[3]) for r in ranked if r[0] == 1} == {
            (10, 2024, 20),
            (11, 2024, 5),
        }
        # Article 2's duplicated latest-year row still flags ties == 2.
        art2 = [r for r in ranked if r[0] == 2]
        assert len(art2) == 1 and art2[0][2] == 2024 and art2[0][4] == 2

        # Article 4's latest-year zero supersedes its older positive balance.
        art4 = [r for r in ranked if r[0] == 4]
        assert art4 == [(4, 10, 2024, 0, 1)]

        # The exact shared stock aggregate helper over a local CTE named
        # stock_latest (one of the two accepted internal source names).
        totals_sql = f"""
            WITH stock_latest AS (
                {window("stock_rows")}
            )
            {aggregate("stock_latest")}
            ORDER BY ArticulosID
        """
        totals = dict(conn.execute(totals_sql).fetchall())
        # Article 1 = 20 + 5 (latest year only, no 2023 history); article 2
        # ties -> NULL; article 3 keeps its only (older) year; article 4's
        # latest-year zero supersedes its older positive balance.
        assert totals == {1: 25, 2: None, 3: 100, 4: 0}
    finally:
        conn.close()


def test_erp_failure_returns_no_price_and_no_stock(harness):
    harness.db.results[1] = RuntimeError(PRIVATE_SENTINEL)
    result = harness.invoke()
    assert result["reason"] == "erp_unavailable"
    assert result["lines"] == []
    assert "price" not in result
    assert "qty" not in result
    assert "baja_rotacion" not in result


def test_baja_rotacion_appears_only_in_its_own_aggregate(harness):
    harness.invoke()
    quote_sql = harness.db.calls[1][0]
    filters = re.findall(r"al\.AlmacenCodigo IN \(([^)]+)\)", quote_sql)
    assert len(filters) == 2
    site_codes = set(re.findall(r"'([^']+)'", filters[0]))
    brot_codes = set(re.findall(r"'([^']+)'", filters[1]))
    assert BAJA_ROTACION not in site_codes
    assert brot_codes == {BAJA_ROTACION}
    assert "baja_rotacion_rows" in quote_sql
    assert "stock_latest" in quote_sql
    assert "baja_rotacion_latest" in quote_sql


def test_site_aggregate_reads_only_stock_latest(harness):
    harness.invoke()
    quote_sql = harness.db.calls[1][0]
    st_aggregate = quote_sql.split(") st ON st.ArticulosID = a.ArticulosID")[0].rsplit(
        "LEFT JOIN (", 1
    )[1]
    assert "FROM stock_latest" in st_aggregate
    assert "baja_rotacion_latest" not in st_aggregate
    assert "baja_rotacion_rows" not in st_aggregate


def test_baja_rotacion_aggregate_selects_its_own_latest_year(harness):
    harness.invoke()
    quote_sql = harness.db.calls[1][0]
    br_aggregate = quote_sql.split(") br ON br.ArticulosID = a.ArticulosID")[0].rsplit(
        "LEFT JOIN (", 1
    )[1]
    assert "FROM baja_rotacion_latest" in br_aggregate
    assert "FROM stock_latest" not in br_aggregate


def test_latest_year_selection_is_per_pair_not_global(harness):
    harness.invoke()
    quote_sql = harness.db.calls[1][0]
    assert quote_sql.count("ROW_NUMBER() OVER (") == 2
    assert "PARTITION BY ArticulosID, AlmacenID ORDER BY Ano DESC" in quote_sql
    assert "MAX(Ano)" not in quote_sql
    assert "MAX(ties) = 1" in quote_sql
    assert "COUNT(*) OVER (PARTITION BY ArticulosID, AlmacenID, Ano)" in quote_sql


def test_con_is_excluded_from_every_warehouse_set(harness):
    harness.invoke()
    quote_sql = harness.db.calls[1][0]
    warehouse_codes = set(re.findall(r"'([A-Z0-9.]+)'", quote_sql))
    assert "CON" not in warehouse_codes
    assert BAJA_ROTACION in warehouse_codes


def test_con_cannot_be_added_to_a_site_warehouse_set(harness):
    build = harness.module.build_customer_quote_lines_sql
    original = dict(harness.module.SITES)
    try:
        harness.module.SITES["neiva"] = original["neiva"] + ("CON",)
        with pytest.raises(ValueError):
            build(site="neiva", skus=[SKU])
    finally:
        harness.module.SITES.clear()
        harness.module.SITES.update(original)


def test_baja_rotacion_cannot_be_added_to_a_site_warehouse_set(harness):
    build = harness.module.build_customer_quote_lines_sql
    original = dict(harness.module.SITES)
    try:
        harness.module.SITES["neiva"] = original["neiva"] + (BAJA_ROTACION,)
        with pytest.raises(ValueError):
            build(site="neiva", skus=[SKU])
    finally:
        harness.module.SITES.clear()
        harness.module.SITES.update(original)


def test_contract_documents_baja_rotacion_as_virtual_warehouse():
    text = CONTRACT.read_text(encoding="utf-8")
    collapsed = " ".join(text.split())
    for phrase in (
        "physical_warehouses_only",
        "virtual_warehouses",
        "requires_physical_origin_confirmation",
        "baja_rotacion",
        "POR CONFIRMAR",
        "tri-state",
        "iva_status",
        "ROW_NUMBER()",
        "PARTITION BY ArticulosID, AlmacenID",
        "server-side message validator",
    ):
        assert phrase in collapsed
    assert "no `price_includes_iva`" in text
    assert "no `unit` field" in text
    assert "MAX(ties)" in collapsed
    assert "complete_for_site" not in text
    assert "Fredy" in collapsed
    assert "2026-10-22" in collapsed
    assert "486" in collapsed
