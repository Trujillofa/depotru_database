"""catalog.quote_for_customer: customer list, UND, site stock. No live DB."""

from __future__ import annotations

import pytest

from business_analyzer.core.j3system_customer_quote import (
    FORBIDDEN_SQL_FRAGMENTS,
    build_customer_quote_lines_sql,
    build_customer_tariff_sql,
    fetch_customer_quote,
    parse_quote_request,
)
from depotru_kernel.auth import Audience
from depotru_tools.builtins import _tool_quote_for_customer
from depotru_tools.registry import (
    ToolContext,
    ToolPermissionError,
    get_default_registry,
    reset_default_registry,
)


@pytest.fixture(autouse=True)
def _fresh_registry():
    reset_default_registry()
    yield
    reset_default_registry()


def _sql(site: str) -> str:
    return build_customer_quote_lines_sql(site=site, skus=("0020080005",))


@pytest.mark.unit
def test_neiva_sql_lists_each_bodega_and_skips_cost():
    sql = _sql("neiva")
    for code in ("ALM", "BD6", "SUR", "DIS", "BOD"):
        assert f"'{code}'" in sql
    assert "'FLO'" not in sql
    assert "'CEN'" not in sql
    assert "PreciosValor" in sql
    assert "TarifasID = %s" in sql
    assert "Cantidad = 0" in sql
    assert "SaldoActual" in sql
    assert "MAX(Ano)" in sql
    assert ">= 0" in sql
    for fragment in FORBIDDEN_SQL_FRAGMENTS:
        assert fragment not in sql


@pytest.mark.unit
def test_florencia_sql_is_flo_only():
    sql = _sql("florencia")
    assert "'FLO'" in sql
    for code in ("ALM", "BD6", "SUR", "DIS", "BOD", "CEN"):
        assert f"'{code}'" not in sql
    for fragment in FORBIDDEN_SQL_FRAGMENTS:
        assert fragment not in sql


@pytest.mark.unit
def test_tariff_sql_does_not_read_customer_identity():
    sql = build_customer_tariff_sql()
    assert "TercerosID = %s" in sql
    assert "TarifasID" in sql
    for fragment in (
        "TercerosNombres",
        "TercerosCelular",
        "TercerosIdentificacion",
        "ArticulosCosto",
    ):
        assert fragment not in sql


@pytest.mark.unit
def test_tool_is_sales_only():
    registry = get_default_registry()
    public = {t["name"] for t in registry.list_tools(audience=Audience.PUBLIC)}
    sales = {t["name"] for t in registry.list_tools(audience=Audience.SALES)}
    assert "catalog.quote_for_customer" not in public
    assert "catalog.quote_for_customer" in sales
    assert "catalog.quote_search" in public
    with pytest.raises(ToolPermissionError):
        registry.call(
            "catalog.quote_for_customer",
            {"terceros_id": 1, "site": "neiva", "skus": ["0020080005"]},
            context=ToolContext(audience=Audience.PUBLIC),
        )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("params", "reason"),
    [
        ({}, "terceros_id_required"),
        ({"terceros_id": 0, "site": "neiva", "skus": ["A"]}, "terceros_id_required"),
        ({"terceros_id": 5, "site": "bogota", "skus": ["A"]}, "site_invalid"),
        ({"terceros_id": 5, "site": "neiva"}, "skus_required"),
        ({"terceros_id": 5, "site": "neiva", "skus": []}, "skus_required"),
        (
            {"terceros_id": 5, "site": "neiva", "skus": ["BAD SKU"]},
            "invalid_sku",
        ),
        (
            {
                "terceros_id": 5,
                "site": "neiva",
                "skus": [f"S{i:02d}" for i in range(21)],
            },
            "too_many_skus",
        ),
    ],
)
def test_params_fail_before_any_quote(params, reason):
    request, error = parse_quote_request(params)
    assert request is None
    assert error is not None
    assert error["status"] == "error"
    assert error["reason"] == reason
    assert error["lines"] == []


class _FakeDB:
    def __init__(self, customer, lines=None, boom_on=None):
        self.customer = customer
        self.lines = lines or []
        self.boom_on = boom_on
        self.calls: list[tuple[str, tuple]] = []

    def execute_query(self, sql, params):
        self.calls.append((sql, params))
        if self.boom_on == "customer" and "AdmTerceros" in sql:
            raise ConnectionError("down")
        if self.boom_on == "lines" and "AdmPrecios" in sql:
            raise ConnectionError("down")
        if "AdmTerceros" in sql:
            return self.customer
        return self.lines


def _request():
    parsed, error = parse_quote_request(
        {"terceros_id": 42, "site": "neiva", "skus": ["0020080005", "0020080005"]}
    )
    assert error is None and parsed is not None
    assert parsed.skus == ("0020080005",)
    return parsed


@pytest.mark.unit
def test_missing_and_refused_tariffs_do_not_read_prices():
    missing = _FakeDB([{"terceros_id": 42, "tarifas_id": None}])
    out = fetch_customer_quote(missing, _request())
    assert out["reason"] == "tariff_missing"
    assert len(missing.calls) == 1

    zero = _FakeDB(
        [{"terceros_id": 42, "tarifas_id": 0, "tarifa_codigo": "", "tarifa_nombre": ""}]
    )
    assert fetch_customer_quote(zero, _request())["reason"] == "tariff_missing"
    assert len(zero.calls) == 1

    cost = _FakeDB(
        [
            {
                "terceros_id": 42,
                "tarifas_id": 6,
                "tarifa_codigo": "006",
                "tarifa_nombre": "AL COSTO",
            }
        ]
    )
    refused = fetch_customer_quote(cost, _request())
    assert refused["reason"] == "tariff_refused"
    assert refused["tarifa"]["codigo"] == "006"
    assert len(cost.calls) == 1


@pytest.mark.unit
def test_neiva_quote_returns_net_price_and_each_warehouse():
    db = _FakeDB(
        customer=[
            {
                "terceros_id": 42,
                "tarifas_id": 5,
                "tarifa_codigo": "005",
                "tarifa_nombre": "FERRETERIA AAA",
            }
        ],
        lines=[
            {
                "sku": "0020080005",
                "name": "CEMENTO GRIS 50KG",
                "price_rows": 1,
                "price_min": 28000,
                "price_max": 28000,
                "qty_alm": 4,
                "qty_bd6": 0,
                "qty_sur": 2,
                "qty_dis": None,
                "qty_bod": 1,
            }
        ],
    )
    out = fetch_customer_quote(db, _request())
    assert out["status"] == "ok"
    assert out["price_includes_iva"] is False
    assert out["tarifa"]["id"] == 5
    assert "reason" not in out
    line = out["lines"][0]
    assert line["status"] == "ok"
    assert line["price"] == 28000
    assert line["unit"] == "UND"
    assert [w["code"] for w in line["warehouses"]] == [
        "ALM",
        "BD6",
        "SUR",
        "DIS",
        "BOD",
    ]
    assert [w["qty"] for w in line["warehouses"]] == [4, 0, 2, 0, 1]
    assert "cost" not in line
    assert db.calls[1][1] == (5,)
    assert "ArticulosVenta" not in db.calls[1][0]


@pytest.mark.unit
def test_florencia_quote_has_only_flo():
    parsed, error = parse_quote_request(
        {"terceros_id": 7, "site": "florencia", "skus": ["ABC123"]}
    )
    assert error is None and parsed is not None
    db = _FakeDB(
        customer=[
            {
                "terceros_id": 7,
                "tarifas_id": 4,
                "tarifa_codigo": "004",
                "tarifa_nombre": "FERRETERIA AA",
            }
        ],
        lines=[
            {
                "sku": "ABC123",
                "name": "VARILLA",
                "price_rows": 1,
                "price_min": 1000,
                "price_max": 1000,
                "qty_flo": 8,
            }
        ],
    )
    out = fetch_customer_quote(db, parsed)
    assert out["status"] == "ok"
    assert out["lines"][0]["warehouses"] == [{"code": "FLO", "qty": 8}]


@pytest.mark.unit
def test_missing_price_ambiguous_price_and_unknown_sku_fail_the_quote():
    db = _FakeDB(
        customer=[
            {
                "terceros_id": 42,
                "tarifas_id": 5,
                "tarifa_codigo": "005",
                "tarifa_nombre": "FERRETERIA AAA",
            }
        ],
        lines=[
            {
                "sku": "KNOWN",
                "name": "SIN PRECIO",
                "price_rows": 0,
                "price_min": None,
                "price_max": None,
                "qty_alm": 3,
                "qty_bd6": 0,
                "qty_sur": 0,
                "qty_dis": 0,
                "qty_bod": 0,
            }
        ],
    )
    parsed, _ = parse_quote_request(
        {"terceros_id": 42, "site": "neiva", "skus": ["MISSING", "KNOWN"]}
    )
    out = fetch_customer_quote(db, parsed)
    assert out["status"] == "error"
    assert out["reason"] == "article_not_found"
    assert out["lines"][0]["status"] == "article_not_found"
    assert "warehouses" not in out["lines"][0]
    assert out["lines"][1]["status"] == "price_missing"
    assert out["lines"][1]["price"] is None

    clash = _FakeDB(
        customer=[
            {
                "terceros_id": 42,
                "tarifas_id": 5,
                "tarifa_codigo": "005",
                "tarifa_nombre": "FERRETERIA AAA",
            }
        ],
        lines=[
            {
                "sku": "0020080005",
                "name": "DOS PRECIOS",
                "price_rows": 2,
                "price_min": 10,
                "price_max": 12,
                "qty_alm": 1,
                "qty_bd6": 0,
                "qty_sur": 0,
                "qty_dis": 0,
                "qty_bod": 0,
            }
        ],
    )
    ambiguous = fetch_customer_quote(clash, _request())
    assert ambiguous["status"] == "error"
    assert ambiguous["reason"] == "price_ambiguous"
    assert ambiguous["lines"][0]["price"] is None


@pytest.mark.unit
def test_identical_duplicate_price_rows_use_that_price():
    db = _FakeDB(
        customer=[
            {
                "terceros_id": 42,
                "tarifas_id": 5,
                "tarifa_codigo": "005",
                "tarifa_nombre": "FERRETERIA AAA",
            }
        ],
        lines=[
            {
                "sku": "0020080005",
                "name": "IGUAL",
                "price_rows": 2,
                "price_min": 50,
                "price_max": 50,
                "qty_alm": 1,
                "qty_bd6": 0,
                "qty_sur": 0,
                "qty_dis": 0,
                "qty_bod": 0,
            }
        ],
    )
    out = fetch_customer_quote(db, _request())
    assert out["status"] == "ok"
    assert out["lines"][0]["price"] == 50


@pytest.mark.unit
def test_unknown_customer_and_erp_down():
    empty = _FakeDB([])
    assert fetch_customer_quote(empty, _request())["reason"] == "customer_not_found"

    down = _FakeDB([], boom_on="customer")
    with pytest.raises(ConnectionError):
        fetch_customer_quote(down, _request())


@pytest.mark.unit
def test_tool_fails_closed_when_erp_raises(monkeypatch: pytest.MonkeyPatch):
    class Boom:
        def __enter__(self):
            raise ConnectionError("erp down")

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("business_analyzer.core.database.Database", lambda: Boom())
    out = _tool_quote_for_customer(
        ToolContext(audience=Audience.SALES),
        {"terceros_id": 42, "site": "neiva", "skus": ["0020080005"]},
    )
    assert out["status"] == "error"
    assert out["reason"] == "erp_unavailable"
    assert out["lines"] == []
    assert "erp down" not in str(out)


@pytest.mark.unit
def test_tool_fails_closed_when_the_price_query_raises(monkeypatch: pytest.MonkeyPatch):
    class Half:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute_query(self, sql, params):
            if "AdmTerceros" in sql:
                return [
                    {
                        "terceros_id": 42,
                        "tarifas_id": 5,
                        "tarifa_codigo": "005",
                        "tarifa_nombre": "FERRETERIA AAA",
                    }
                ]
            raise TimeoutError("price read failed")

    monkeypatch.setattr("business_analyzer.core.database.Database", lambda: Half())
    out = _tool_quote_for_customer(
        ToolContext(audience=Audience.SALES),
        {"terceros_id": 42, "site": "neiva", "skus": ["0020080005"]},
    )
    assert out["status"] == "error"
    assert out["reason"] == "erp_unavailable"
    assert out["lines"] == []
    assert out["tarifa"]["codigo"] == "005"
