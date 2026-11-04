"""Released J3 customer-quote adapter for b2b.quote (R11/R12/R22).

Not catalog.quote_search. Not the dirty feat/tsol-export candidate (that
returns warehouse qty). This adapter reads AdmPrecios at Cantidad=0 for the
staff-linked TercerosID tariff and omits stock.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

import pytest

from modules.b2b.contracts import SKU_MAX_LEN, ErpUnavailableError
from modules.b2b.erp import J3CustomerQuoteClient, get_b2b_erp_client
from modules.b2b.j3_customer_quote import (
    FORBIDDEN_SQL_FRAGMENTS,
    build_customer_quote_lines_sql,
    build_customer_tariff_sql,
    fetch_customer_quote,
    parse_terceros_id,
)

FORBIDDEN = FORBIDDEN_SQL_FRAGMENTS + (
    "ArticulosVenta",
    "PreciosIncremento",
    "SaldoActual",
    "InvDetalleExistencias",
    "warehouse_qty",
    "qty_alm",
    "TercerosNombres",
    "TercerosCelular",
    "TercerosIdentificacion",
    "ArticulosCosto",
)


class FakeDb:
    def __init__(
        self,
        tariff_rows: Optional[list[dict[str, Any]]] = None,
        price_rows: Optional[list[dict[str, Any]]] = None,
        raise_error: Optional[Exception] = None,
    ) -> None:
        self.tariff_rows = list(tariff_rows or [])
        self.price_rows = list(price_rows or [])
        self.raise_error = raise_error
        self.calls: list[tuple[str, tuple]] = []

    def execute_query(self, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
        if self.raise_error is not None:
            raise self.raise_error
        self.calls.append((sql, params))
        if "AdmTerceros" in sql:
            return list(self.tariff_rows)
        return list(self.price_rows)


_TARIFF_OK = {
    "terceros_id": 90123456,
    "tarifas_id": 1,
    "tarifa_codigo": "001",
    "tarifa_nombre": "PUBLICO GENERAL",
}
_TARIFF_006 = {
    "terceros_id": 90123456,
    "tarifas_id": 6,
    "tarifa_codigo": "006",
    "tarifa_nombre": "AL COSTO",
}


@pytest.mark.unit
def test_tariff_sql_is_parameterized_and_has_no_pii_or_list_price():
    sql = build_customer_tariff_sql()
    assert "%s" in sql
    assert "AdmTerceros" in sql
    assert "AdmTarifas" in sql
    assert "TercerosID = %s" in sql.replace("\n", " ")
    for frag in FORBIDDEN:
        assert frag not in sql, frag


@pytest.mark.unit
def test_price_sql_uses_admprecios_cantidad_zero_and_omits_stock():
    sql = build_customer_quote_lines_sql(skus=["CEMENTO-50", "CLAVOS-2I"])
    assert "AdmPrecios" in sql
    assert "Cantidad = 0" in sql
    assert "TarifasID = %s" in sql.replace("\n", " ")
    assert "'CEMENTO-50'" in sql
    assert "'CLAVOS-2I'" in sql
    assert "ArticulosVenta" not in sql
    assert "PreciosIncremento" not in sql
    assert "SaldoActual" not in sql
    assert "InvDetalleExistencias" not in sql
    assert "AdmAlmacen" not in sql
    for frag in FORBIDDEN:
        assert frag.lower() not in sql.lower(), frag


@pytest.mark.unit
def test_price_sql_rejects_injection_skus():
    with pytest.raises(ValueError):
        build_customer_quote_lines_sql(skus=["CEMENTO-50'; DROP TABLE AdmPrecios;--"])


@pytest.mark.unit
def test_fetch_happy_path_decimal_net_price_no_warehouse():
    db = FakeDb(
        tariff_rows=[_TARIFF_OK],
        price_rows=[
            {
                "sku": "CEMENTO-50",
                "price_rows": 1,
                "price_min": Decimal("38500.00"),
                "price_max": Decimal("38500.00"),
            }
        ],
    )
    rows = fetch_customer_quote(db, "neiva", "90123456", ["CEMENTO-50"])
    assert db.calls[0][1] == (90123456,)
    assert db.calls[1][1] == (1,)
    assert len(rows) == 1
    assert rows[0]["sku"] == "CEMENTO-50"
    assert rows[0]["net_price"] == Decimal("38500.00")
    assert rows[0]["tariff_id"] == "1"
    assert rows[0]["tariff_code"] == "001"
    assert "warehouse_qty" not in rows[0]
    assert "warehouses" not in rows[0]


@pytest.mark.unit
def test_refused_tariff_006_does_not_read_prices():
    db = FakeDb(tariff_rows=[_TARIFF_006], price_rows=[{"sku": "X"}])
    rows = fetch_customer_quote(db, "neiva", "90123456", ["CEMENTO-50"])
    assert len(db.calls) == 1  # tariff only
    assert len(rows) == 1
    assert rows[0]["sku"] == "CEMENTO-50"
    assert "net_price" not in rows[0]
    assert rows[0]["tariff_id"] == "6"
    assert rows[0]["tariff_code"] == "006"
    assert rows[0]["tariff_name"] == "AL COSTO"


@pytest.mark.unit
def test_missing_customer_is_unavailable():
    db = FakeDb(tariff_rows=[])
    with pytest.raises(ErpUnavailableError):
        fetch_customer_quote(db, "neiva", "90123456", ["CEMENTO-50"])


@pytest.mark.unit
def test_ambiguous_price_omits_net_price():
    db = FakeDb(
        tariff_rows=[_TARIFF_OK],
        price_rows=[
            {
                "sku": "CEMENTO-50",
                "price_rows": 2,
                "price_min": Decimal("10.00"),
                "price_max": Decimal("20.00"),
            }
        ],
    )
    rows = fetch_customer_quote(db, "neiva", "90123456", ["CEMENTO-50"])
    assert "net_price" not in rows[0]


@pytest.mark.unit
def test_parse_terceros_id_rejects_junk():
    assert parse_terceros_id("90123456") == 90123456
    assert parse_terceros_id(90123456) == 90123456
    assert parse_terceros_id("0") is None
    assert parse_terceros_id("abc") is None
    assert parse_terceros_id(True) is None


@pytest.mark.unit
def test_client_disabled_unless_j3_mode(monkeypatch):
    monkeypatch.delenv("B2B_ERP_MODE", raising=False)
    client = J3CustomerQuoteClient(db_factory=lambda: FakeDb())
    with pytest.raises(ErpUnavailableError, match="b2b_erp_disabled"):
        client.customer_quote("neiva", "90123456", ["CEMENTO-50"])


@pytest.mark.unit
def test_client_j3_mode_uses_fetch(monkeypatch):
    monkeypatch.setenv("B2B_ERP_MODE", "j3")
    db = FakeDb(
        tariff_rows=[_TARIFF_OK],
        price_rows=[
            {
                "sku": "CEMENTO-50",
                "price_rows": 1,
                "price_min": Decimal("38500.00"),
                "price_max": Decimal("38500.00"),
            }
        ],
    )
    client = J3CustomerQuoteClient(db_factory=lambda: db)
    rows = client.customer_quote("florencia", "90123456", ["CEMENTO-50"])
    assert rows[0]["net_price"] == Decimal("38500.00")


@pytest.mark.unit
def test_default_client_is_j3_adapter():
    assert isinstance(get_b2b_erp_client(), J3CustomerQuoteClient)


@pytest.mark.unit
def test_sku_cap_matches_contract():
    assert SKU_MAX_LEN == 40
