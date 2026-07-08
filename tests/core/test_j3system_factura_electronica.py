"""Tests for electronic invoice compliance SQL builders."""

from __future__ import annotations

import pytest

from business_analyzer.core.j3system_factura_electronica import (
    build_factura_electronica_by_documento_sql,
    build_factura_electronica_rechazos_sql,
    build_factura_electronica_summary_sql,
    factura_electronica_summary_from_documento_rows,
    is_factura_aceptada_sql,
    validate_factura_electronica_sql_period,
    worst_rejection_document_types,
)


def test_is_factura_aceptada_checks_codigo_cufe():
    expr = is_factura_aceptada_sql().upper()
    assert "CODIGO='200'" in expr.replace(" ", "")
    assert "ENVIADO=1" in expr.replace(" ", "")
    assert "CUFE" in expr


def test_summary_sql_uses_inv_estado_factura_electronica():
    sql = build_factura_electronica_summary_sql("2024-12-01", "2024-12-31").upper()
    assert "INVESTADOFACTURAELECTRONICA" in sql
    assert "TASA_ACEPTACION_PCT" in sql
    assert "TASA_RECHAZO_PCT" in sql
    assert "ADM DOCUMENTOS" not in sql
    assert "ADMDOCUMENTOS" in sql


def test_by_documento_sql_groups_and_orders_rejections():
    sql = build_factura_electronica_by_documento_sql("2024-01-01", "2024-01-31").upper()
    assert "DOCUMENTOSCODIGO" in sql
    assert "GROUPBYDOCUMENTOSCODIGO" in sql.replace(" ", "")
    assert "ORDERBYRECHAZADASDESC" in sql.replace(" ", "")


def test_rechazos_sql_filters_non_accepted():
    sql = build_factura_electronica_rechazos_sql("2024-01-01", "2024-01-31").upper()
    assert "ES_ACEPTADA=0" in sql.replace(" ", "")


def test_validate_period_rejects_reversed():
    with pytest.raises(ValueError):
        validate_factura_electronica_sql_period("2024-12-31", "2024-01-01")


def test_summary_from_documento_rows_weighted():
    rows = [
        {"Emitidas": 100, "Aceptadas": 100, "Rechazadas": 0, "Valor_Total": 1000},
        {"Emitidas": 50, "Aceptadas": 40, "Rechazadas": 10, "Valor_Total": 500},
    ]
    summary = factura_electronica_summary_from_documento_rows(rows)
    assert summary["Emitidas"] == 150
    assert summary["Aceptadas"] == 140
    assert summary["Rechazadas"] == 10
    assert abs(summary["Tasa_Aceptacion_Pct"] - 93.333333) < 0.01


def test_worst_rejection_document_types_filters_zero_rejections():
    rows = [
        {"DocumentosCodigo": "FED", "Rechazadas": 0, "Tasa_Rechazo_Pct": 0},
        {"DocumentosCodigo": "FET", "Rechazadas": 5, "Tasa_Rechazo_Pct": 2.5},
    ]
    worst = worst_rejection_document_types(rows, n=3)
    assert len(worst) == 1
    assert worst[0]["DocumentosCodigo"] == "FET"
