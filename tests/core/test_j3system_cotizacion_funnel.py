"""Tests for J3System quote-to-invoice funnel SQL builders."""

from __future__ import annotations

import pytest

from business_analyzer.core.j3system_cotizacion_funnel import (
    build_cotizacion_funnel_by_vendor_sql,
    build_cotizacion_funnel_summary_sql,
    numero_cotiza_from_documento_sql,
    parse_numero_cotiza,
    validate_funnel_sql_period,
)


def test_numero_cotiza_expr_uses_document_number_not_venta_id():
    expr = numero_cotiza_from_documento_sql("c")
    assert "NumeroDocumento" in expr
    assert "VentaID" not in expr
    assert expr.startswith("'CT-'")


def test_summary_sql_links_via_inv_ventas_totales():
    sql = build_cotizacion_funnel_summary_sql("2024-12-01", "2024-12-31").upper()
    assert "INVVENTASTOTALES" in sql
    assert "NUMEROCOTIZA" in sql
    assert "INVVENTAS" in sql
    assert "INVCOTIZACAB" in sql
    assert "DOCUMENTOSCODIGO = 'CT'" in sql
    assert "V.FECHA >= C.FECHA" in sql
    assert "TASA_CONVERSION_PCT" in sql


def test_vendor_sql_includes_vendedor_and_perdidas():
    sql = build_cotizacion_funnel_by_vendor_sql("2024-01-01", "2024-01-31").upper()
    assert "ADM VENDEDOR" not in sql  # no space in identifier
    assert "ADMVENDEDOR" in sql
    assert "PERDIDAS" in sql
    assert "VENDEDOR_CODIGO" in sql


def test_validate_funnel_sql_period_rejects_bad_dates():
    with pytest.raises(ValueError):
        validate_funnel_sql_period("2024-13-01", "2024-12-31")
    with pytest.raises(ValueError):
        validate_funnel_sql_period("2024-12-31", "2024-01-01")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("CT-28606", 28606),
        ("28606", 28606),
        ("", None),
        (None, None),
        ("CT-ABC", None),
    ],
)
def test_parse_numero_cotiza(raw, expected):
    assert parse_numero_cotiza(raw) == expected
