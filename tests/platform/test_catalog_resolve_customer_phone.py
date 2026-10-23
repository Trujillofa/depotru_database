"""catalog.resolve_customer_phone: one usable list, or a person chooses.

Isolated B3 unit tests: run with --noconftest --disable-plugin-autoload. The
database module is replaced before core imports; no settings or credentials
are loaded. The phone is PII, so every fixture is generated at runtime from a
deterministic helper — no literal phone number, credential, or URL is stored
in this file, and no assert prints a phone value.
"""

from __future__ import annotations

import importlib
import json
import re
import socket
import sys
from types import ModuleType

import pytest

from depotru_kernel.auth import Audience, ToolScope, audience_may_use
from depotru_tools.builtins import _tool_resolve_customer_phone, register_builtin_tools
from depotru_tools.registry import ToolContext, ToolPermissionError, ToolRegistry

pytestmark = pytest.mark.unit
TOOL = "catalog.resolve_customer_phone"
IDENTITY_KEY = "verified_customer_terceros_id"
PRIVATE_SENTINEL = "SYNTHETIC-PRIVATE-DO-NOT-RETURN"
PHONE_COLUMNS = ("TercerosCelular", "TercerosCelular2", "TelefonoContacto")


def _fake_digits(seed: int, length: int = 10) -> str:
    """Deterministic synthetic digit string with a leading 1-9 digit."""
    body: list[str] = []
    state = seed
    for _ in range(length - 1):
        state = (state * 1103515245 + 12345) % 2**31
        body.append(str(state % 10))
    return str(1 + (seed % 9)) + "".join(body)


def _phone_pair(seed: int) -> tuple[str, str]:
    """A synthetic national phone and its ``57``-prefixed international form."""
    national = _fake_digits(seed)
    return national, "57" + national


def _row(**overrides) -> dict:
    base = {
        "terceros_id": 10,
        "tarifas_id": 5,
        "tarifa_codigo": "005",
        "tarifa_nombre": "FERRETERIA AAA",
        "TercerosNombres": "NO MOSTRAR",
        "TercerosIdentificacion": "900111",
        "ValorCosto": 1,
    }
    base.update(overrides)
    return base


def _dump_contains(payload: object, needle: str) -> bool:
    return needle in json.dumps(payload, ensure_ascii=False, default=str)


@pytest.fixture
def harness(monkeypatch):
    def forbidden_network(*args, **kwargs):
        raise AssertionError("Network forbidden in isolated B3 tests")

    monkeypatch.setattr(socket.socket, "connect", forbidden_network)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden_network)
    monkeypatch.setattr(socket, "create_connection", forbidden_network)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden_network)

    class FakeDB:
        constructed = 0
        calls: list = []
        rows: list = []
        boom = False

        def __init__(self):
            type(self).constructed += 1

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute_query(self, sql, params):
            self.calls.append((sql, params))
            if self.boom:
                raise RuntimeError(PRIVATE_SENTINEL)
            return list(self.rows)

        @staticmethod
        def validate_sql_identifier(value, label):
            assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value)
            return value

    database = ModuleType("business_analyzer.core.database")
    database.Database = FakeDB
    database.DatabaseError = RuntimeError
    database.ConnectionType = object
    database.env_database_name = lambda key, default: default
    monkeypatch.setitem(sys.modules, database.__name__, database)

    tracked = (
        "business_analyzer.core.j3system_customer_phone",
        "business_analyzer.core.j3system_customer_quote",
        "business_analyzer.core.j3system_sales_warehouse",
        "business_analyzer.core.website_warehouse_policy",
    )
    saved = {name: sys.modules.get(name) for name in tracked}
    for name in tracked:
        sys.modules.pop(name, None)

    module = importlib.import_module("business_analyzer.core.j3system_customer_phone")
    registry = ToolRegistry()
    register_builtin_tools(registry)

    class Harness:
        db = FakeDB
        tools = registry

        def __init__(self):
            self.module = module

        def invoke(self, params, audience=Audience.SALES, extras=None):
            context_extras = {} if extras is None else extras
            context = ToolContext(audience=audience, extras=context_extras)
            return registry.call(TOOL, params, context=context)

    try:
        yield Harness()
    finally:
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


def test_registration_sales_only(harness):
    spec = harness.tools.get(TOOL)
    assert spec.scope == ToolScope.SALES_PORTFOLIO
    assert spec.public_safe is False
    assert set(spec.parameters_schema) == {"phone"}
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
    national, _ = _phone_pair(11)
    assert TOOL not in {s["name"] for s in harness.tools.list_tools(audience)}
    with pytest.raises(ToolPermissionError):
        harness.invoke({"phone": national}, audience=audience)
    result = _tool_resolve_customer_phone(ToolContext(audience=audience), {})
    assert result == {"status": "error", "reason": "audience_not_allowed"}
    assert harness.db.constructed == 0


def test_handler_validates_phone_before_database(harness):
    national, _ = _phone_pair(12)
    extras = {IDENTITY_KEY: 99}
    context = ToolContext(audience=Audience.SALES, extras=extras)
    # A junk phone fails closed before any Database is constructed and clears stale identity.
    for bad in ("0" * 7, "x" * 41, "abc"):
        out = _tool_resolve_customer_phone(context, {"phone": bad})
        assert out["reason"] == "phone_invalid"
        assert IDENTITY_KEY not in extras
    assert harness.db.constructed == 0
    # A valid phone does construct and query once, then stores the server-side ID.
    harness.db.rows = [_row()]
    out = _tool_resolve_customer_phone(context, {"phone": national})
    assert out["status"] == "ok"
    assert harness.db.constructed == 1
    assert extras == {IDENTITY_KEY: 10}


@pytest.mark.parametrize(
    ("rows", "reason"),
    [
        ([], "customer_not_found"),
        ([_row(tarifas_id=None, tarifa_codigo="", tarifa_nombre="")], "tariff_missing"),
        (
            [_row(tarifas_id=6, tarifa_codigo="006", tarifa_nombre="AL COSTO")],
            "tariff_refused",
        ),
        (
            [_row(terceros_id=4), _row(terceros_id=5)],
            "phone_ambiguous",
        ),
    ],
)
def test_non_success_resolution_never_sets_verified_context(harness, rows, reason):
    national, _ = _phone_pair(61)
    extras = {IDENTITY_KEY: 99}
    harness.db.rows = rows

    result = harness.invoke({"phone": national}, extras=extras)

    assert result["reason"] == reason
    assert IDENTITY_KEY not in extras
    assert national not in json.dumps(extras)


@pytest.mark.parametrize(
    "params,reason",
    [
        ({}, "phone_required"),
        ({"phone": None}, "phone_required"),
        ({"phone": ""}, "phone_required"),
        ({"phone": "   "}, "phone_required"),
        ({"extra": True}, "unexpected_parameters"),
        ({"phone": "x", "extra": "y"}, "unexpected_parameters"),
    ],
)
def test_handler_closed_schema(harness, params, reason):
    assert (
        _tool_resolve_customer_phone(ToolContext(audience=Audience.SALES), params)[
            "reason"
        ]
        == reason
    )
    assert harness.db.constructed == 0


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        (None, "phone_required"),
        ("", "phone_required"),
        ("   ", "phone_required"),
        (0, "phone_required"),
        (-1, "phone_required"),
        (True, "phone_invalid"),
        (False, "phone_invalid"),
        (1.5, "phone_invalid"),
        ([], "phone_invalid"),
        ({}, "phone_invalid"),
        ("abc", "phone_invalid"),
        ("12a4567890", "phone_invalid"),
        ("123", "phone_invalid"),
        ("0" * 7, "phone_invalid"),
        ("1" * 16, "phone_invalid"),
        ("x" * 41, "phone_invalid"),
        ("\u0661\u0662\u0663\u0664\u0665\u0666\u0667", "phone_invalid"),
    ],
)
def test_phone_keys_reject_junk(harness, raw, reason):
    assert harness.module.phone_keys(raw) == reason


def test_country_code_and_national_are_one_pair(harness):
    national, international = _phone_pair(21)
    assert harness.module.phone_keys(national) == (national, international)
    assert harness.module.phone_keys(international) == (international, national)
    # A positive int renders to the same digit keys as its decimal string.
    assert harness.module.phone_keys(int(national)) == (national, international)
    # Separators are dropped; the same pair results.
    formatted = f"+57 {national[:3]} {national[3:6]} {national[6:]}"
    assert harness.module.phone_keys(formatted) == (international, national)


def test_bound_parameter_shape(harness):
    assert harness.module.build_phone_match_sql(1).count("%s") == 3
    assert harness.module.build_phone_match_sql(2).count("%s") == 6
    with pytest.raises(ValueError):
        harness.module.build_phone_match_sql(3)


def test_sql_selects_no_phone_and_no_forbidden_fragments(harness):
    sql = harness.module.build_phone_match_sql(2)
    select_part = sql.split("FROM", 1)[0]
    where_part = sql.split("WHERE", 1)[1]
    for column in PHONE_COLUMNS:
        assert column in where_part
        assert column not in select_part
    assert "TercerosIdentificacion" not in sql
    for fragment in harness.module.FORBIDDEN_SQL_FRAGMENTS:
        assert fragment not in sql


def test_all_phone_columns_have_bound_or_predicates(harness):
    sql = harness.module.build_phone_match_sql(2)
    where_part = sql.split("WHERE", 1)[1]
    branches = where_part.split(" OR ")
    assert len(branches) == len(PHONE_COLUMNS)
    for column, branch in zip(PHONE_COLUMNS, branches, strict=True):
        assert f"ISNULL(t.{column}, '')" in branch
        assert branch.count("IN (") == 1
        assert branch.count("%s") == 2


def test_fetch_binds_keys_and_hides_phone(harness):
    national, international = _phone_pair(33)
    db = harness.db()
    db.rows = [_row()]
    out = harness.module.fetch_customer_by_phone(db, national)
    assert out["status"] == "ok"
    sql, params = db.calls[0]
    assert params == (national, international) * 3
    assert national not in sql and international not in sql


def test_fetch_invalid_phone_never_queries(harness):
    db = harness.db()
    db.boom = True
    out = harness.module.fetch_customer_by_phone(db, "0" * 7)
    assert out == {"status": "error", "reason": "phone_invalid"}
    assert db.calls == []


def test_fetch_erp_failure_is_redacted(harness):
    national, _ = _phone_pair(32)
    db = harness.db()
    db.boom = True
    out = harness.module.fetch_customer_by_phone(db, national)
    assert out == {"status": "error", "reason": "erp_unavailable"}
    assert not _dump_contains(out, PRIVATE_SENTINEL)
    assert not _dump_contains(out, national)

    class _NonListDB:
        def execute_query(self, sql, params):
            return {"not": "a list"}

    out = harness.module.fetch_customer_by_phone(_NonListDB(), national)
    assert out == {"status": "error", "reason": "erp_unavailable"}


def test_one_usable_list_among_several_rows(harness):
    rows = [
        _row(terceros_id=1, tarifas_id=None, tarifa_codigo="", tarifa_nombre=""),
        _row(terceros_id=2),
        _row(
            terceros_id=3, tarifas_id=6, tarifa_codigo="006", tarifa_nombre="AL COSTO"
        ),
    ]
    out = harness.module.decide_phone_rows(rows)
    assert out["status"] == "ok"
    assert out["terceros_id"] == 2
    assert out["tarifa"] == {"codigo": "005", "nombre": "FERRETERIA AAA"}
    for sentinel in ("NO MOSTRAR", "900111", "ValorCosto"):
        assert not _dump_contains(out, sentinel)


def test_single_matched_row_resolves(harness):
    out = harness.module.decide_phone_rows([_row()])
    assert out["status"] == "ok"
    assert out["terceros_id"] == 10


def test_two_usable_lists_are_ambiguous_without_phone(harness):
    national, _ = _phone_pair(41)
    rows = [
        _row(terceros_id=8, tarifa_codigo="001"),
        _row(terceros_id=3, tarifa_codigo="002"),
    ]
    out = harness.module.decide_phone_rows(rows)
    assert out["reason"] == "phone_ambiguous"
    assert out["truncated"] is False
    assert [c["terceros_id"] for c in out["candidates"]] == [3, 8]
    assert set(out["candidates"][0]) == {"terceros_id", "tarifa_codigo"}
    for sentinel in ("NO MOSTRAR", "900111", "identificacion", national):
        assert not _dump_contains(out, sentinel)


def test_two_distinct_ids_stay_ambiguous(harness):
    rows = [
        _row(terceros_id=4, tarifa_codigo="001"),
        _row(terceros_id=5, tarifa_codigo="005"),
    ]
    out = harness.module.decide_phone_rows(rows)
    assert out["reason"] == "phone_ambiguous"
    assert len(out["candidates"]) == 2


def test_more_than_twelve_usable_are_truncated(harness):
    rows = [_row(terceros_id=index) for index in range(1, 14)]
    out = harness.module.decide_phone_rows(rows)
    assert out["reason"] == "phone_ambiguous"
    assert out["truncated"] is True
    assert out["candidates"] == []


def test_no_usable_list_fails_closed(harness):
    assert harness.module.decide_phone_rows([]) == {
        "status": "error",
        "reason": "customer_not_found",
    }
    several = harness.module.decide_phone_rows(
        [
            _row(terceros_id=1, tarifas_id=None, tarifa_codigo="", tarifa_nombre=""),
            _row(terceros_id=2, tarifas_id=0, tarifa_codigo="", tarifa_nombre=""),
        ]
    )
    assert several == {"status": "error", "reason": "customer_not_found"}

    refused = harness.module.decide_phone_rows(
        [_row(tarifas_id=6, tarifa_codigo="006", tarifa_nombre="AL COSTO")]
    )
    assert refused == {"status": "error", "reason": "tariff_refused"}

    missing = harness.module.decide_phone_rows(
        [_row(tarifas_id=None, tarifa_codigo="", tarifa_nombre="")]
    )
    assert missing == {"status": "error", "reason": "tariff_missing"}


def test_duplicate_id_does_not_guess(harness):
    out = harness.module.decide_phone_rows([_row(), _row()])
    assert out == {"status": "error", "reason": "erp_unavailable"}


def test_driver_error_never_logs_or_leaks(harness, caplog, capsys):
    national, _ = _phone_pair(51)
    db = harness.db()
    db.boom = True
    out = harness.module.fetch_customer_by_phone(db, national)
    assert out == {"status": "error", "reason": "erp_unavailable"}
    assert not caplog.records
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""
