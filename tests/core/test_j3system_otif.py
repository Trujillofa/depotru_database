"""Tests for J3System OTIF SQL builders."""

from __future__ import annotations

import pytest

from business_analyzer.core.j3system_otif import (
    build_otif_by_customer_sql,
    build_otif_by_warehouse_sql,
    build_otif_summary_sql,
    fecha_entrega_parsed_sql,
    otif_summary_from_warehouse_rows,
    parse_fecha_entrega,
    validate_otif_sql_period,
    worst_otif_warehouses,
)


def test_fecha_entrega_parsed_uses_convert_style_103():
    expr = fecha_entrega_parsed_sql("e.FechaEntrega")
    assert "CONVERT(DATE" in expr
    assert "103" in expr
    assert "LEFT(e.FechaEntrega, 10)" in expr


def test_summary_sql_uses_inv_historico_entregas():
    sql = build_otif_summary_sql("2024-12-01", "2024-12-31").upper()
    assert "INVHISTORICOENTREGAS" in sql
    assert "OTIF_PCT" in sql
    assert "LEAD_TIME_PROMEDIO_DIAS" in sql
    assert "FILL_RATE_PCT" in sql
    assert "FECHAENTREGA_PARSED<=FECHAPROXIMAENTREGA" in sql.replace(" ", "")


def test_summary_sql_excludes_test_documents():
    sql = build_otif_summary_sql("2024-12-01", "2024-12-31").upper()
    assert "'XY'" in sql
    assert "TIPO='ENTREGA'" in sql.replace(" ", "")


def test_warehouse_sql_groups_by_almacen():
    sql = build_otif_by_warehouse_sql("2024-01-01", "2024-01-31").upper()
    assert "ALMACEN_CODIGO" in sql
    assert "GROUPBYALMACEN" in sql.replace(" ", "")


def test_customer_sql_orders_worst_otif_first():
    sql = build_otif_by_customer_sql("2024-12-01", "2024-12-31").upper()
    assert "ORDER BY OTIF_PCT ASC" in sql
    assert "HAVING COUNT(*) >=" in sql


def test_validate_otif_sql_period_rejects_reversed_dates():
    with pytest.raises(ValueError):
        validate_otif_sql_period("2024-12-31", "2024-01-01")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("28/12/2024 7:37", "2024-12-28"),
        ("10/01/2025 10:39", "2025-01-10"),
        ("", None),
        ("bad", None),
    ],
)
def test_parse_fecha_entrega(raw, expected):
    assert parse_fecha_entrega(raw) == expected


def test_otif_summary_from_warehouse_rows_weighted():
    rows = [
        {
            "Total_Entregas": 100,
            "Entregas_A_Tiempo": 80,
            "Entregas_Tarde": 20,
            "Lead_Time_Promedio_Dias": 2.0,
            "Fill_Rate_Pct": 99.0,
        },
        {
            "Total_Entregas": 50,
            "Entregas_A_Tiempo": 25,
            "Entregas_Tarde": 25,
            "Lead_Time_Promedio_Dias": 4.0,
            "Fill_Rate_Pct": 97.0,
        },
    ]
    summary = otif_summary_from_warehouse_rows(rows)
    assert summary["Total_Entregas"] == 150
    assert summary["Entregas_A_Tiempo"] == 105
    assert abs(summary["OTIF_Pct"] - 70.0) < 0.01
    assert abs(summary["Lead_Time_Promedio_Dias"] - 2.666) < 0.1


def test_worst_otif_warehouses():
    rows = [
        {"Almacen_Codigo": "FLO", "OTIF_Pct": 90.0},
        {"Almacen_Codigo": "BOD", "OTIF_Pct": 3.0},
        {"Almacen_Codigo": "SUR", "OTIF_Pct": 25.0},
    ]
    worst = worst_otif_warehouses(rows, n=2)
    assert worst[0]["Almacen_Codigo"] == "BOD"
    assert worst[1]["Almacen_Codigo"] == "SUR"
