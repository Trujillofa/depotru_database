"""Unit tests for depotru_kernel."""

import pytest

from depotru_kernel.attribution import attribute_sale, resolve_seller
from depotru_kernel.auth import (
    Audience,
    ToolScope,
    audience_may_use,
    scopes_for_audience,
)
from depotru_kernel.documents import (
    CANONICAL_EXCLUDED_DOCUMENT_CODES,
    excluded_document_sql_in_list,
)
from depotru_kernel.money import format_cop, format_pct


@pytest.mark.unit
def test_excluded_codes_canonical():
    assert "XY" in CANONICAL_EXCLUDED_DOCUMENT_CODES
    assert "AS" in CANONICAL_EXCLUDED_DOCUMENT_CODES
    assert "TS" in CANONICAL_EXCLUDED_DOCUMENT_CODES
    sql = excluded_document_sql_in_list()
    assert "'XY'" in sql
    assert "'ISC'" in sql


@pytest.mark.unit
def test_format_cop_and_pct():
    assert format_cop(1234567) == "$1.234.567"
    assert format_pct(45.6) == "45,6%"
    assert format_cop(None) == "-"


@pytest.mark.unit
def test_public_audience_scopes():
    scopes = scopes_for_audience(Audience.PUBLIC)
    assert ToolScope.PUBLIC_CATALOG in scopes
    assert ToolScope.SALES_MARGIN not in scopes
    assert audience_may_use(Audience.PUBLIC, ToolScope.PUBLIC_STOCK)
    assert not audience_may_use(Audience.PUBLIC, ToolScope.SALES_MARGIN)


@pytest.mark.unit
def test_attribute_sale_asignado_beats_factura_huber_betsy():
    # Asignado 163 (Betsy book) must win even if Factura says HUBER
    code = attribute_sale(
        code="044",
        name="HUBER SANTIAGO ENCISO",
        asignado="163-BETSY GUZMAN",
    )
    assert code == "163"


@pytest.mark.unit
def test_resolve_seller_display():
    result = resolve_seller(code="095", name="DANIEL ENRIQUE CAICEDO")
    assert result["code"] == "095"
    assert result["is_pool"] is False
    assert "DANIEL" in (result["display_name"] or "")
