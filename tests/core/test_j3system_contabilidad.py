"""Tests for accounting SQL builders."""

from __future__ import annotations

import pytest

from business_analyzer.core.j3system_contabilidad import (
    balance_summary_from_clase_rows,
    build_contabilidad_balance_clase_sql,
    build_contabilidad_conciliacion_ingresos_sql,
    build_contabilidad_gastos_centro_sql,
    build_contabilidad_pyg_acumulado_clase_sql,
    build_contabilidad_pyg_clase_sql,
    build_contabilidad_summary_sql,
    conciliacion_ingresos_from_row,
    puc_signed_balance_sql,
    pyg_summary_from_clase_rows,
    validate_contabilidad_sql_period,
)


def test_puc_signed_balance_uses_naturaleza():
    expr = puc_signed_balance_sql().upper()
    assert "CUENTASPUCNATURALEZA" in expr.replace(" ", "")
    assert "MOVIMIENTODETALLETIPO" in expr.replace(" ", "")


def test_summary_sql_uses_con_movimiento():
    sql = build_contabilidad_summary_sql("2024-12-01", "2024-12-31").upper()
    assert "CONMOVIMIENTO" in sql
    assert "CONMOVIMIENTODETALLE" in sql
    assert "CUADRE_OK" in sql
    assert "ADMDOCUMENTOS" in sql


def test_balance_clase_sql_filters_123_cumulative():
    sql = build_contabilidad_balance_clase_sql("2024-12-31").upper()
    assert "MOVIMIENTOS_ACUMULADOS" in sql
    assert "SALDO_ACUMULADO" in sql
    assert "ACTIVO" in sql
    assert "2024-12-31" in sql


def test_balance_summary_from_clase_rows_balanced():
    rows = [
        {"Clase_Puc": "1", "Saldo_Acumulado": 1_000_000},
        {"Clase_Puc": "2", "Saldo_Acumulado": -400_000},
        {"Clase_Puc": "3", "Saldo_Acumulado": -600_000},
    ]
    summary = balance_summary_from_clase_rows(rows)
    assert summary["Activo_Total"] == 1_000_000
    assert summary["Pasivo_Total"] == 400_000
    assert summary["Patrimonio_Total"] == 600_000
    assert summary["Ecuacion_OK"] is True
    assert summary["Ecuacion_Diferencia_Bruta"] == 0.0


def test_balance_summary_adjusts_for_open_pyg():
    balance_rows = [
        {"Clase_Puc": "1", "Saldo_Acumulado": 22_618_603_367},
        {"Clase_Puc": "2", "Saldo_Acumulado": -8_720_061_703},
        {"Clase_Puc": "3", "Saldo_Acumulado": -12_339_749_757},
    ]
    pyg_rows = [
        {"Clase_Puc": "4", "Saldo_Acumulado": 247_000},
        {"Clase_Puc": "5", "Saldo_Acumulado": -286_000_000},
        {"Clase_Puc": "6", "Saldo_Acumulado": -1_272_000_000},
    ]
    summary = balance_summary_from_clase_rows(balance_rows, pyg_rows)
    assert abs(summary["Ecuacion_Diferencia_Bruta"] - 1_558_791_907) < 1
    assert abs(summary["Resultado_PyG_Acumulado"] - (-1_557_753_000)) < 1_000_000
    tolerancia = max(summary["Activo_Total"] * 0.0001, 500_000.0)
    assert abs(summary["Ecuacion_Diferencia"]) < tolerancia
    assert summary["Ecuacion_OK"] is True


def test_pyg_acumulado_clase_sql_filters_456_cumulative():
    sql = build_contabilidad_pyg_acumulado_clase_sql("2024-12-31").upper()
    assert "MOVIMIENTOS_ACUMULADOS" in sql
    assert "SALDO_ACUMULADO" in sql
    assert "2024-12-31" in sql


def test_pyg_clase_sql_filters_456():
    sql = build_contabilidad_pyg_clase_sql("2024-01-01", "2024-01-31").upper()
    assert "CLASE_PUC" in sql
    assert "SALDO_NETO" in sql
    assert "INGRESOS" in sql


def test_gastos_centro_sql_joins_subcentro():
    sql = build_contabilidad_gastos_centro_sql("2024-01-01", "2024-01-31").upper()
    assert "ADMSUBCENTROCOSTO" in sql
    assert "SUBCENTROCOSTOCODIGO" in sql


def test_conciliacion_ingresos_cross_database():
    sql = build_contabilidad_conciliacion_ingresos_sql(
        "2024-12-01", "2024-12-31"
    ).upper()
    assert "BANCO_DATOS" in sql
    assert "CONCILIACION_INGRESOS_PCT" in sql
    assert "LEFT(P.CUENTASPUCCODIGO,2)='41'" in sql.replace(" ", "")


def test_validate_period_rejects_reversed():
    with pytest.raises(ValueError):
        validate_contabilidad_sql_period("2024-12-31", "2024-01-01")


def test_pyg_summary_from_clase_rows():
    rows = [
        {
            "Clase_Puc": "4",
            "Total_Creditos": 1000,
            "Total_Debitos": 100,
            "Saldo_Neto": 900,
        },
        {
            "Clase_Puc": "5",
            "Total_Creditos": 50,
            "Total_Debitos": 200,
            "Saldo_Neto": -150,
        },
        {
            "Clase_Puc": "6",
            "Total_Creditos": 20,
            "Total_Debitos": 600,
            "Saldo_Neto": -580,
        },
    ]
    summary = pyg_summary_from_clase_rows(rows)
    assert summary["Ingresos_Creditos"] == 1000
    assert summary["Costos_Debitos"] == 600
    assert summary["Margen_Bruto_Contable"] == 400
    assert abs(summary["Margen_Contable_Pct"] - 40.0) < 0.01


def test_conciliacion_ingresos_from_row():
    row = conciliacion_ingresos_from_row(
        {
            "Ingresos_Contables_41": 1000,
            "Ventas_BI_Con_Iva": 950,
            "Conciliacion_Ingresos_Pct": 95.0,
        }
    )
    assert row["Conciliacion_Ingresos_Pct"] == 95.0
