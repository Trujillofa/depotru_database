"""R23 — read-only cartera display contract (admin sees all, member own).

Unit contract for ``b2b.cartera_detail`` / ``b2b.cartera_summary``:
fail-closed ERP boundary, decimal-safe amounts, whitelist shaping with
no phone/cost leakage, and buckets that agree with the J3 due dates at
the injected ``now``.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

from depotru_kernel.auth import Audience, ToolScope, scopes_for_audience
from depotru_tools.registry import (
    ToolContext,
    ToolPermissionError,
    get_default_registry,
    reset_default_registry,
)
from modules.b2b.cartera import (
    SUMMARY_MAX_ROWS_CAP,
    J3CarteraClient,
    cartera_detail_response,
    cartera_summary_response,
)


class FakeDb:
    """execute_query(sql, params) -> queued rows; records every call."""

    def __init__(self, queues: list) -> None:
        self.calls: list[str] = []
        self._queues = list(queues)

    def execute_query(self, sql: str, params: Any = None) -> list:
        self.calls.append(" ".join(sql.split()))
        if not self._queues:
            return []
        return self._queues.pop(0)


HEADER = {
    "terceros_id": 11460,
    "identificacion": "900123456",
    "identificacion_dv": "1",
    "nombres": "EMPRESA PRUEBA SAS",
    "ciudad": "NEIVA",
    "cupo": Decimal("5000000.0000"),
}


def doc_row(saldo, *, codigo="FED", num="1", fecha=(2026, 10, 5), vence=(2026, 11, 5)):
    return {
        "documentos_codigo": codigo,
        "numero_factura": num,
        "fecha": date(*fecha),
        "fecha_vence": date(*vence),
        "valor": saldo,
        "saldo": saldo,
    }


NOW = datetime(2026, 11, 4, 10, 0, 0)


def round_tripped(payload: dict) -> dict:
    return json.loads(json.dumps(payload, default=str))


def assert_decimal_safe(payload: Any, path: str = "") -> None:
    if isinstance(payload, bool):
        pytest.fail(f"boolean leaked at {path}")
    if isinstance(payload, float):
        pytest.fail(f"float amount leaked at {path}")
    if isinstance(payload, dict):
        for key, value in payload.items():
            assert_decimal_safe(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            assert_decimal_safe(value, f"{path}[{index}]")


def ok_client(monkeypatch, queues: list):
    monkeypatch.setenv("B2B_ERP_MODE", "j3")
    db = FakeDb(queues)
    return J3CarteraClient(db_factory=lambda: db), db


# ---------------------------------------------------------------------------
# detail
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_detail_ok_amounts_and_buckets(monkeypatch):
    docs = [
        doc_row(Decimal("100000.00")),
        doc_row(Decimal("250000.00"), num="2", vence=(2026, 10, 20)),  # 1-30
        doc_row(Decimal("50000.00"), num="3", vence=(2026, 9, 20)),  # 31-60
        doc_row(
            Decimal("1000.00"), num="4", fecha=(2026, 10, 1), vence=(2026, 10, 10)
        ),  # 1-30
        doc_row(Decimal("7000.00"), num="5", vence=(2025, 1, 1)),  # >360
    ]
    client, _db = ok_client(monkeypatch, [[HEADER], docs])
    resp = cartera_detail_response("11460", client, now=NOW)
    assert resp["status"] == "ok"
    assert resp["currency"] == "COP"
    assert resp["as_of"] == "2026-11-04"
    assert resp["terceros_id"] == "11460"
    assert resp["company_name"] == "EMPRESA PRUEBA SAS"
    assert resp["cupo_total"] == "5000000.0000"
    assert resp["open_total"] == "408000.00"
    assert resp["buckets"]["corriente"] == "100000.00"
    assert resp["buckets"]["vencido_30"] == "251000.00"
    assert resp["buckets"]["vencido_60"] == "50000.00"
    assert resp["buckets"]["vencido_superior"] == "7000.00"
    assert resp["document_count"] == 5
    assert (
        resp["documents"][0]["saldo"] == "100000.00"
    )  # fixture order (SQL sorts live)
    assert resp["documents"][0]["fecha_vence"] == "2026-11-05"
    safe = round_tripped(resp)
    assert_decimal_safe(safe)


@pytest.mark.unit
def test_detail_orders_documents_by_due_date(monkeypatch):
    docs = [
        doc_row(Decimal("50000.00"), num="3", vence=(2026, 9, 20)),
        doc_row(Decimal("100000.00")),
        doc_row(Decimal("250000.00"), num="2", vence=(2026, 10, 20)),
    ]
    client, _db = ok_client(monkeypatch, [[HEADER], docs])
    resp = cartera_detail_response("11460", client, now=NOW)
    nums = [d["numero_factura"] for d in resp["documents"]]
    assert nums == ["3", "1", "2"]


@pytest.mark.unit
def test_detail_invalid_terceros_id_never_touches_erp(monkeypatch):
    client, db = ok_client(monkeypatch, [[HEADER], []])
    for bad in ("", "abc", "0", "-5", None, True, "1146 0"):
        resp = cartera_detail_response(bad, client, now=NOW)
        assert resp["status"] == "unavailable"
        assert resp["reason"] == "terceros_id_invalid"
        assert resp["documents"] == []
    assert db.calls == []  # no ERP query ran
    live = cartera_detail_response("11460", client, now=NOW)
    assert live["status"] == "ok"


@pytest.mark.unit
def test_detail_unknown_customer_fails_closed(monkeypatch):
    client, _db = ok_client(monkeypatch, [[]])
    resp = cartera_detail_response("999", client, now=NOW)
    assert resp["status"] == "unavailable"
    assert resp["reason"] == "customer_not_found"


@pytest.mark.unit
def test_detail_erp_disabled(monkeypatch):
    monkeypatch.delenv("B2B_ERP_MODE", raising=False)
    client = J3CarteraClient(db_factory=lambda: FakeDb([[]]))
    resp = cartera_detail_response("11460", client, now=NOW)
    assert resp["status"] == "unavailable"
    assert resp["reason"] == "b2b_erp_disabled"


@pytest.mark.unit
def test_detail_db_failure_and_timeout_map_fail_closed(monkeypatch):
    monkeypatch.setenv("B2B_ERP_MODE", "j3")

    class Boom:
        def execute_query(self, sql, params=None):
            raise ConnectionError("dead wire")

    class Slow:
        def execute_query(self, sql, params=None):
            raise RuntimeError("connection timeout after 10060 ms")

    resp = cartera_detail_response(
        "1", J3CarteraClient(db_factory=lambda: Boom()), now=NOW
    )
    assert resp == json.loads(json.dumps(resp))
    assert resp["status"] == "unavailable"
    assert resp["reason"] == "j3_unavailable"
    resp2 = cartera_detail_response(
        "1", J3CarteraClient(db_factory=lambda: Slow()), now=NOW
    )
    assert resp2["reason"] == "erp_timeout"


@pytest.mark.unit
def test_detail_no_contact_or_cost_keys_leak(monkeypatch):
    header = dict(HEADER)
    header["phone_bait"] = "3105550000"
    header["cellular"] = "3105550000"
    header["costo"] = Decimal("1.00")
    client, _db = ok_client(monkeypatch, [[header], [doc_row(Decimal("100.00"))]])
    resp = cartera_detail_response("11460", client, now=NOW)
    flat = json.dumps(round_tripped(resp))
    for needle in ("phone_bait", "cellular", "costo", "3105550000"):
        assert needle not in flat
    assert "900123456" in flat  # the member's own NIT is display data


# ---------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------


def summary_row(**over):
    row = {
        "terceros_id": 11460,
        "identificacion": "900123456",
        "nombres": "EMPRESA PRUEBA SAS",
        "ciudad": "NEIVA",
        "cupo": Decimal("5000000.0000"),
        "documents": 2,
        "open_total": Decimal("350000.00"),
        "corriente": Decimal("0.00"),
        "vencido_30": Decimal("250000.00"),
        "vencido_60": Decimal("100000.00"),
        "vencido_90": Decimal("0.00"),
        "vencido_120": Decimal("0.00"),
        "vencido_360": Decimal("0.00"),
        "vencido_superior": Decimal("0.00"),
    }
    row.update(over)
    return row


@pytest.mark.unit
def test_summary_ok_whitelisted_shapes(monkeypatch):
    db_rows = [
        summary_row(),
        summary_row(terceros_id=27633, open_total=Decimal("99.00")),
    ]
    client, _db = ok_client(monkeypatch, [db_rows])
    resp = cartera_summary_response(None, client)
    assert resp["status"] == "ok"
    assert resp["client_count"] == 2
    assert resp["clients"][0]["open_total"] == "350000.00"
    assert resp["clients"][0]["terceros_id"] == "11460"
    assert resp["clients"][0]["buckets"]["vencido_30"] == "250000.00"
    safe = round_tripped(resp)
    assert_decimal_safe(safe)


@pytest.mark.unit
def test_summary_exterior_keys_and_bait_rows_never_pass(monkeypatch):
    row = summary_row()
    row["telefono"] = "3105550000"
    row["celular"] = "3105550000"
    bucket_rows = [["telefono"]], [row]
    del bucket_rows
    client, _db = ok_client(monkeypatch, [[row]])
    resp = cartera_summary_response(None, client)
    flat = json.dumps(round_tripped(resp))
    for needle in ("telefono", "celular", "3105550000"):
        assert needle not in flat


@pytest.mark.unit
def test_summary_cap_bounds(monkeypatch):
    client, db = ok_client(monkeypatch, [[]])
    for bad in (0, -1, SUMMARY_MAX_ROWS_CAP + 1, "1001", "1.5", [200]):
        resp = cartera_summary_response(bad, client)
        assert resp["status"] == "unavailable"
        assert resp["reason"] == "invalid_max_rows"
    assert db.calls == []
    assert cartera_summary_response(None, client)["status"] == "ok"
    assert cartera_summary_response("50", client)["status"] == "ok"
    top_queries = [c for c in db.calls if "TOP " in c]
    assert f"TOP {200}" in top_queries[-2]  # default run = 200 rows
    assert "TOP 50" in top_queries[-1]  # explicit "50"


@pytest.mark.unit
def test_summary_db_failure_fails_closed(monkeypatch):
    monkeypatch.setenv("B2B_ERP_MODE", "j3")

    class Boom:
        def execute_query(self, sql, params=None):
            raise ConnectionError("dead wire")

    resp = cartera_summary_response(None, J3CarteraClient(db_factory=lambda: Boom()))
    assert resp == json.loads(json.dumps(resp))
    assert resp["status"] == "unavailable"
    assert resp["reason"] == "j3_unavailable"


# ---------------------------------------------------------------------------
# registration + audience isolation (R22)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_cartera_tools_are_b2b_scoped():
    try:
        reg = get_default_registry()
        for name in ("b2b.cartera_detail", "b2b.cartera_summary"):
            spec = reg.get(name)
            assert spec.scope is ToolScope.B2B_CARTERA
            assert spec.public_safe is False
    finally:
        reset_default_registry()


@pytest.mark.unit
def test_public_agent_sales_cannot_use_cartera():
    try:
        reg = get_default_registry()
        for audience in (Audience.PUBLIC, Audience.AGENT, Audience.SALES):
            with pytest.raises(ToolPermissionError):
                reg.call(
                    "b2b.cartera_detail",
                    {"terceros_id": "1"},
                    context=ToolContext(audience=audience),
                )
            with pytest.raises(ToolPermissionError):
                reg.call(
                    "b2b.cartera_summary",
                    {"max_rows": 10},
                    context=ToolContext(audience=audience),
                )
    finally:
        reset_default_registry()


@pytest.mark.unit
def test_audience_b2b_includes_cartera_and_public_does_not():
    b2b = scopes_for_audience(Audience.B2B)
    assert {
        ToolScope.B2B_QUOTE,
        ToolScope.B2B_CREDIT,
        ToolScope.B2B_ORDER,
        ToolScope.B2B_STOCK,
        ToolScope.B2B_CARTERA,
    } <= b2b
    public = scopes_for_audience(Audience.PUBLIC)
    assert ToolScope.B2B_CARTERA not in public
