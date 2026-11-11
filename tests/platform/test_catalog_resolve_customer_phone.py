"""catalog.resolve_customer_phone: one usable list, or a person chooses."""

from __future__ import annotations

import json

import pytest

from business_analyzer.core.j3system_customer_phone import (
    FORBIDDEN_SQL_FRAGMENTS,
    build_phone_match_sql,
    decide_phone_rows,
    fetch_customer_by_phone,
    phone_keys,
)
from depotru_kernel.auth import Audience
from depotru_tools.builtins import _tool_resolve_customer_phone
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


def _row(**overrides):
    base = {
        "terceros_id": 10,
        "tarifas_id": 5,
        "tarifa_codigo": "005",
        "tarifa_nombre": "FERRETERIA AAA",
        "identificacion": "1234567890",
        "celular": "3001234567",
        "celular2": "",
        "telefono": "",
        "TercerosNombres": "NO MOSTRAR",
        "ValorCosto": 1,
    }
    base.update(overrides)
    return base


def _dump(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False)


@pytest.mark.unit
def test_sql_binds_keys_and_skips_cost_and_name():
    sql = build_phone_match_sql(2)
    assert sql.count("%s") == 6
    for column in ("TercerosCelular", "TercerosCelular2", "TelefonoContacto"):
        assert column in sql
    assert "TercerosIdentificacion" in sql
    assert "3001234567" not in sql
    for fragment in FORBIDDEN_SQL_FRAGMENTS:
        assert fragment not in sql
    with pytest.raises(ValueError):
        build_phone_match_sql(3)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        (None, "phone_required"),
        ("", "phone_required"),
        ("   ", "phone_required"),
        (True, "phone_invalid"),
        ("abc", "phone_invalid"),
        ("123", "phone_invalid"),
        ("0000000", "phone_invalid"),
        ("0" * 16, "phone_invalid"),
        ("1" * 16, "phone_invalid"),
        ("x" * 41, "phone_invalid"),
    ],
)
def test_junk_phone_does_not_match(raw, reason):
    assert phone_keys(raw) == reason


@pytest.mark.unit
def test_country_code_and_national_number_are_one_key():
    assert phone_keys("+57 300 123 4567") == ("573001234567", "3001234567")
    assert phone_keys("3001234567") == ("3001234567", "573001234567")
    assert phone_keys(3001234567) == ("3001234567", "573001234567")


@pytest.mark.unit
def test_one_usable_list_among_several_rows_is_that_customer():
    rows = [
        _row(terceros_id=1, tarifas_id=None, tarifa_codigo="", tarifa_nombre=""),
        _row(terceros_id=2, celular="573001234567"),
        _row(
            terceros_id=3, tarifas_id=6, tarifa_codigo="006", tarifa_nombre="AL COSTO"
        ),
    ]
    out = decide_phone_rows(rows, ("3001234567", "573001234567"))
    assert out["status"] == "ok"
    assert out["terceros_id"] == 2
    assert out["tarifa"]["codigo"] == "005"
    dumped = _dump(out)
    assert "3001234567" not in dumped
    assert "1234567890" not in dumped
    assert "NO MOSTRAR" not in dumped
    assert "ValorCosto" not in dumped


@pytest.mark.unit
def test_celular2_and_contacto_match_on_their_own():
    celular2 = decide_phone_rows(
        [_row(celular="", celular2="3001234567")],
        ("3001234567",),
    )
    contacto = decide_phone_rows(
        [_row(celular="", telefono="6088712345")],
        ("6088712345",),
    )
    assert celular2["terceros_id"] == 10
    assert contacto["terceros_id"] == 10


@pytest.mark.unit
def test_a_neighbor_row_that_does_not_match_the_digits_is_ignored():
    out = decide_phone_rows(
        [_row(terceros_id=9, celular="3009999999"), _row(terceros_id=4)],
        ("3001234567",),
    )
    assert out["terceros_id"] == 4


@pytest.mark.unit
def test_two_usable_lists_ask_a_person_and_hide_the_phone():
    rows = [
        _row(terceros_id=8, identificacion="900111", tarifa_codigo="001"),
        _row(terceros_id=3, identificacion="900222", tarifa_codigo="002"),
    ]
    out = decide_phone_rows(rows, ("3001234567",))
    assert out["reason"] == "phone_ambiguous"
    assert out["truncated"] is False
    assert [item["terceros_id"] for item in out["candidates"]] == [3, 8]
    assert out["candidates"][0]["identificacion"] == "900222"
    dumped = _dump(out)
    assert "3001234567" not in dumped
    assert "NO MOSTRAR" not in dumped


@pytest.mark.unit
def test_two_ids_with_the_same_cedula_stay_ambiguous():
    rows = [
        _row(terceros_id=4, identificacion="900111", tarifa_codigo="001"),
        _row(terceros_id=5, identificacion="900111", tarifa_codigo="005"),
    ]
    out = decide_phone_rows(rows, ("3001234567",))
    assert out["reason"] == "phone_ambiguous"
    assert len(out["candidates"]) == 2


@pytest.mark.unit
def test_more_than_twelve_usable_lists_do_not_return_a_partial_choice():
    rows = [
        _row(terceros_id=index, identificacion=str(1000 + index))
        for index in range(1, 14)
    ]
    out = decide_phone_rows(rows, ("3001234567",))
    assert out["reason"] == "phone_ambiguous"
    assert out["truncated"] is True
    assert out["candidates"] == []


@pytest.mark.unit
def test_no_usable_list_fails_closed():
    missing = decide_phone_rows([], ("3001234567",))
    assert missing["reason"] == "customer_not_found"

    several = decide_phone_rows(
        [
            _row(terceros_id=1, tarifas_id=None, tarifa_codigo="", tarifa_nombre=""),
            _row(terceros_id=2, tarifas_id=0, tarifa_codigo="", tarifa_nombre=""),
        ],
        ("3001234567",),
    )
    assert several == {"status": "error", "reason": "customer_not_found"}

    refused = decide_phone_rows(
        [_row(tarifas_id=6, tarifa_codigo="006", tarifa_nombre="AL COSTO")],
        ("3001234567",),
    )
    assert refused["reason"] == "tariff_refused"
    assert "candidates" not in refused
    assert "3001234567" not in _dump(refused)

    blank = decide_phone_rows(
        [_row(tarifas_id=None, tarifa_codigo="", tarifa_nombre="")],
        ("3001234567",),
    )
    assert blank["reason"] == "tariff_missing"


@pytest.mark.unit
def test_duplicate_id_does_not_guess():
    out = decide_phone_rows([_row(), _row(celular2="3001234567")], ("3001234567",))
    assert out["reason"] == "erp_unavailable"


class _FakeDB:
    def __init__(self, rows=None, boom=False):
        self.rows = rows if rows is not None else []
        self.boom = boom
        self.calls: list[tuple[str, tuple]] = []

    def execute_query(self, sql, params):
        self.calls.append((sql, params))
        if self.boom:
            raise ConnectionError("host secret")
        return self.rows


@pytest.mark.unit
def test_fetch_binds_both_keys_and_hides_driver_errors():
    db = _FakeDB([_row()])
    out = fetch_customer_by_phone(db, "+57 300 123 4567")
    assert out["status"] == "ok"
    assert db.calls[0][1] == ("573001234567", "3001234567") * 3
    assert "3001234567" not in db.calls[0][0]

    invalid = _FakeDB(boom=True)
    assert fetch_customer_by_phone(invalid, "0000000")["reason"] == "phone_invalid"
    assert invalid.calls == []

    down = _FakeDB(boom=True)
    failed = fetch_customer_by_phone(down, "3001234567")
    assert failed == {"status": "error", "reason": "erp_unavailable"}
    assert "secret" not in _dump(failed)


@pytest.mark.unit
def test_tool_is_sales_only_and_validates_before_the_database(monkeypatch):
    registry = get_default_registry()
    public = {item["name"] for item in registry.list_tools(audience=Audience.PUBLIC)}
    sales = {item["name"] for item in registry.list_tools(audience=Audience.SALES)}
    assert "catalog.resolve_customer_phone" not in public
    assert "catalog.resolve_customer_phone" in sales
    with pytest.raises(ToolPermissionError):
        registry.call(
            "catalog.resolve_customer_phone",
            {"phone": "3001234567"},
            context=ToolContext(audience=Audience.PUBLIC),
        )

    def _explode():
        raise AssertionError("database constructed")

    monkeypatch.setattr(
        "business_analyzer.core.database.Database",
        _explode,
    )
    out = _tool_resolve_customer_phone(
        ToolContext(audience=Audience.SALES),
        {"phone": "0000000"},
    )
    assert out["reason"] == "phone_invalid"
