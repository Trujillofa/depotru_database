"""Tests for cotización funnel aggregation helpers."""

from __future__ import annotations

from business_analyzer.analysis.cotizacion_funnel import (
    funnel_summary_from_vendor_rows,
    low_conversion_vendors,
    top_lost_vendors,
)


def test_funnel_summary_aggregates_vendor_rows():
    rows = [
        {
            "Cotizaciones": 100,
            "Convertidas": 40,
            "Perdidas": 60,
            "Tasa_Conversion_Pct": 40.0,
            "Dias_Promedio_Conversion": 1.0,
        },
        {
            "Cotizaciones": 50,
            "Convertidas": 10,
            "Perdidas": 40,
            "Tasa_Conversion_Pct": 20.0,
            "Dias_Promedio_Conversion": 3.0,
        },
    ]
    summary = funnel_summary_from_vendor_rows(rows)
    assert summary["Cotizaciones"] == 150
    assert summary["Convertidas"] == 50
    assert summary["Perdidas"] == 100
    assert abs(summary["Tasa_Conversion_Pct"] - (50 / 150 * 100)) < 0.01
    assert abs(summary["Dias_Promedio_Conversion"] - 1.4) < 0.01


def test_top_lost_vendors_orders_by_perdidas():
    rows = [
        {"Vendedor_Nombre": "A", "Perdidas": 5, "Tasa_Conversion_Pct": 50},
        {"Vendedor_Nombre": "B", "Perdidas": 20, "Tasa_Conversion_Pct": 10},
        {"Vendedor_Nombre": "C", "Perdidas": 12, "Tasa_Conversion_Pct": 30},
    ]
    top = top_lost_vendors(rows, n=2)
    assert [r["Vendedor_Nombre"] for r in top] == ["B", "C"]


def test_low_conversion_vendors_filters_volume_and_rate():
    rows = [
        {"Vendedor_Nombre": "A", "Cotizaciones": 15, "Tasa_Conversion_Pct": 10},
        {"Vendedor_Nombre": "B", "Cotizaciones": 5, "Tasa_Conversion_Pct": 5},
        {"Vendedor_Nombre": "C", "Cotizaciones": 20, "Tasa_Conversion_Pct": 25},
    ]
    low = low_conversion_vendors(rows, min_quotes=10, max_rate_pct=20.0)
    assert len(low) == 1
    assert low[0]["Vendedor_Nombre"] == "A"
