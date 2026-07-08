"""Tests for returns reconciliation SQL builders."""

from __future__ import annotations

import pytest

from business_analyzer.core.j3system_devoluciones_conciliacion import (
    bi_returns_filter_sql,
    build_devoluciones_by_category_sql,
    build_devoluciones_by_documento_sql,
    build_devoluciones_summary_sql,
    conciliacion_summary_from_category_rows,
    top_margin_erosion_categories,
    top_reconciliation_gaps,
    validate_devoluciones_sql_period,
)


def test_bi_returns_filter_includes_dve_and_negative_qty():
    filt = bi_returns_filter_sql("b").upper()
    assert "B.CANTIDAD<0" in filt.replace(" ", "")
    assert "'DVE'" in filt


def test_summary_sql_cross_database():
    sql = build_devoluciones_summary_sql("2024-12-01", "2024-12-31").upper()
    assert "INVDEVOLUCIONVENTAS" in sql
    assert "BANCO_DATOS" in sql
    assert "CONCILIACION_PCT" in sql
    assert "UNIDADES_ERP" in sql


def test_category_sql_includes_validated_return_rate():
    sql = build_devoluciones_by_category_sql("2024-12-01", "2024-12-31").upper()
    assert "TASA_DEVOLUCION_VALIDADA_PCT" in sql
    assert "DIFERENCIA_UNIDADES" in sql
    assert "IMPACTO_MARGEN_BI" in sql
    assert "FULLOUTERJOIN" in sql.replace(" ", "")


def test_documento_sql_full_outer_join():
    sql = build_devoluciones_by_documento_sql("2024-01-01", "2024-01-31").upper()
    assert "DOCUMENTOSCODIGO" in sql
    assert "FULLOUTERJOIN" in sql.replace(" ", "")


def test_validate_devoluciones_sql_period_rejects_reversed():
    with pytest.raises(ValueError):
        validate_devoluciones_sql_period("2024-12-31", "2024-01-01")


def test_conciliacion_summary_perfect_match():
    rows = [
        {"Unidades_ERP": 100, "Unidades_BI": 100, "Diferencia_Unidades": 0},
        {"Unidades_ERP": 50, "Unidades_BI": 50, "Diferencia_Unidades": 0},
    ]
    summary = conciliacion_summary_from_category_rows(rows)
    assert summary["Unidades_ERP"] == 150
    assert summary["Conciliacion_Pct"] == 100.0
    assert summary["Categorias_Con_Diferencia"] == 0


def test_conciliacion_summary_with_gap():
    rows = [{"Unidades_ERP": 100, "Unidades_BI": 90, "Diferencia_Unidades": -10}]
    summary = conciliacion_summary_from_category_rows(rows)
    assert summary["Conciliacion_Pct"] == 90.0
    assert summary["Categorias_Con_Diferencia"] == 1


def test_top_reconciliation_gaps_orders_by_abs_diff():
    rows = [
        {"Categoria": "A", "Diferencia_Unidades": 1},
        {"Categoria": "B", "Diferencia_Unidades": -50},
    ]
    gaps = top_reconciliation_gaps(rows, n=1)
    assert gaps[0]["Categoria"] == "B"


def test_top_margin_erosion_categories():
    rows = [
        {"Categoria": "A", "Impacto_Margen_BI": 1000},
        {"Categoria": "B", "Impacto_Margen_BI": 5000},
    ]
    top = top_margin_erosion_categories(rows, n=1)
    assert top[0]["Categoria"] == "B"
