"""Tests for J3System critical inventory SQL builders."""

from __future__ import annotations

import pytest

from business_analyzer.core.j3system_critical_inventory import (
    build_critical_inventory_by_warehouse_sql,
    build_critical_inventory_sql,
    critical_inventory_summary_from_rows,
    top_critical_by_warehouse,
    validate_inventory_as_of_date,
)


def test_critical_inventory_sql_cross_database_join():
    sql = build_critical_inventory_sql("2024-12-31").upper()
    assert "SMARTBUSINESS.DBO.BANCO_DATOS" in sql
    assert "J3SYSTEM.DBO.INVDETALLEEXISTENCIAS" in sql
    assert "J3SYSTEM.DBO.INVEXISTENCIAS" in sql
    assert "J3SYSTEM.DBO.ADMARTICULOS" in sql
    assert "J3SYSTEM.DBO.ADMALMACEN" in sql
    assert "DIAS_COBERTURA" in sql
    assert "VENTA_DIARIA_PROMEDIO" in sql
    assert "PRIORIDAD" in sql


def test_critical_inventory_sql_excludes_test_documents():
    sql = build_critical_inventory_sql("2024-12-31").upper()
    assert "'XY'" in sql
    assert "'AS'" in sql
    assert "'TS'" in sql


def test_warehouse_sql_aggregates_by_almacen():
    sql = build_critical_inventory_by_warehouse_sql("2024-12-31").upper()
    assert "SKUS_CRITICOS" in sql
    assert "PROMEDIO_DIAS_COBERTURA" in sql
    assert "GROUP BY" in sql


def test_validate_inventory_as_of_date_rejects_bad_dates():
    with pytest.raises(ValueError):
        validate_inventory_as_of_date("31-12-2024")


def test_critical_inventory_summary_from_rows():
    rows = [
        {"Dias_Cobertura": 2.0, "Saldo_Actual": 5},
        {"Dias_Cobertura": 10.0, "Saldo_Actual": 20},
        {"Dias_Cobertura": None, "Saldo_Actual": 8},
    ]
    summary = critical_inventory_summary_from_rows(rows)
    assert summary["SKUs_Criticos"] == 3
    assert summary["SKUs_Quiebre_7d"] == 1
    assert summary["SKUs_Stock_Bajo"] == 2
    assert abs(summary["Promedio_Dias_Cobertura"] - 6.0) < 0.01


def test_top_critical_by_warehouse():
    rows = [
        {"AlmacenCodigo": "FLO", "AlmacenNombre": "Florencia"},
        {"AlmacenCodigo": "FLO", "AlmacenNombre": "Florencia"},
        {"AlmacenCodigo": "BD6", "AlmacenNombre": "BD6"},
    ]
    ranked = top_critical_by_warehouse(rows)
    assert ranked[0]["AlmacenCodigo"] == "FLO"
    assert ranked[0]["SKUs_Criticos"] == 2
