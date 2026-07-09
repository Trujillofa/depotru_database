"""Tests for presupuesto vs real (budget) integration."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from business_analyzer.analysis.manager_report.aggregations import (  # noqa: E402
    budget_vs_actual_from_sql,
)
from business_analyzer.analysis.manager_report.helpers import (  # noqa: E402
    year_month_to_periodo,
)
from scripts.utils.generate_kpi_control_board import (  # noqa: E402
    compute_scorecard,
    load_query_blocks,
    presupuesto_summary_from_q10,
)


def test_year_month_to_periodo_encoding():
    assert year_month_to_periodo(2024, 5) == 20245
    assert year_month_to_periodo(2024, 9) == 20249
    assert year_month_to_periodo(2024, 10) == 202410
    assert year_month_to_periodo(2024, 12) == 202412


def test_sql_pack_includes_q10_presupuesto():
    blocks = load_query_blocks(
        ROOT / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
    )
    assert "Q10" in blocks
    sql = blocks["Q10"].upper()
    assert "PRESUPUESTO_VENDEDORES" in sql
    assert "CUMPLIMIENTO_PRORRATEADO_PCT" in sql
    assert "MISMO_MES_HISTORICO" in sql
    assert "META_ORIGEN" in sql
    assert "PERIODO_META" in sql


def test_budget_vs_actual_from_sql_shapes_underperformers():
    payload = {
        "available": True,
        "periodo": 202412,
        "summary": {
            "presupuesto_total": 1000.0,
            "ventas_reales_total": 800.0,
            "cumplimiento_pct": 80.0,
            "brecha_total": 200.0,
        },
        "sellers": [
            {
                "vendedor_codigo": "095",
                "vendedor_nombre": "Vendedor A",
                "presupuesto": 600.0,
                "ventas_reales": 400.0,
                "cumplimiento_pct": 66.7,
                "brecha": 200.0,
            },
            {
                "vendedor_codigo": "003",
                "vendedor_nombre": "Vendedor B",
                "presupuesto": 400.0,
                "ventas_reales": 400.0,
                "cumplimiento_pct": 100.0,
                "brecha": 0.0,
            },
        ],
    }
    result = budget_vs_actual_from_sql(payload)
    assert result["available"] is True
    assert result["summary"]["cumplimiento_pct"] == 80.0
    assert len(result["underperformers"]) == 1
    assert result["underperformers"][0]["vendedor_codigo"] == "095"


def test_compute_scorecard_includes_presupuesto_from_q10():
    results = {
        "Q1": [
            {
                "Anio": 2024,
                "Semana_ISO": 50,
                "Margen_Bruto_Pct": 20.0,
                "Ganancia_Bruta": 1_000_000.0,
                "Ticket_Promedio": 40_000.0,
            }
        ],
        "Q4": [{"Concentracion_Top10_Pct": 20.0}],
        "Q9": [{"DSO_Dias": 30.0, "Cartera_Vencida_90_Plus_Pct": 10.0}],
        "Q10": [
            {
                "Periodo": 202412,
                "Periodo_Meta": 202412,
                "Meta_Origen": "periodo_actual",
                "Meta_Prorrateada": 500.0,
                "Ventas_MTD": 450.0,
                "Cumplimiento_Prorrateado_Pct": 90.0,
            },
            {
                "Periodo": 202412,
                "Periodo_Meta": 202412,
                "Meta_Origen": "periodo_actual",
                "Meta_Prorrateada": 500.0,
                "Ventas_MTD": 400.0,
                "Cumplimiento_Prorrateado_Pct": 80.0,
            },
        ],
    }
    scorecard = compute_scorecard(results)
    assert scorecard["presupuesto"]["current"] == 85.0
    assert scorecard["presupuesto"]["target"] == 100.0
    assert scorecard["presupuesto"]["available"] is True
    assert scorecard["presupuesto"]["meta_origen"] == "periodo_actual"


def test_presupuesto_summary_null_when_no_meta():
    summary = presupuesto_summary_from_q10(
        [
            {
                "Periodo": 20267,
                "Periodo_Meta": None,
                "Meta_Origen": "sin_meta",
                "Meta_Prorrateada": 0.0,
                "Ventas_MTD": 1_000_000.0,
            }
        ]
    )
    assert summary["available"] is False
    assert summary["cumplimiento_pct"] is None
    assert summary["total_ventas_mtd"] == 1_000_000.0


def test_compute_scorecard_presupuesto_nd_without_meta():
    results = {
        "Q1": [
            {
                "Anio": 2026,
                "Semana_ISO": 27,
                "Margen_Bruto_Pct": 13.0,
                "Ganancia_Bruta": 100.0,
                "Ticket_Promedio": 50.0,
            }
        ],
        "Q4": [],
        "Q10": [
            {
                "Periodo": 20267,
                "Periodo_Meta": None,
                "Meta_Origen": "sin_meta",
                "Meta_Prorrateada": 0.0,
                "Ventas_MTD": 500_000.0,
                "Cumplimiento_Prorrateado_Pct": None,
            }
        ],
    }
    scorecard = compute_scorecard(results)
    assert scorecard["presupuesto"]["current"] is None
    assert scorecard["presupuesto"]["status"] == "⚪"
    assert scorecard["presupuesto"]["available"] is False


def test_compute_scorecard_presupuesto_historic_month_proxy():
    results = {
        "Q1": [
            {
                "Anio": 2026,
                "Semana_ISO": 27,
                "Margen_Bruto_Pct": 13.0,
                "Ganancia_Bruta": 100.0,
                "Ticket_Promedio": 50.0,
            }
        ],
        "Q4": [],
        "Q10": [
            {
                "Periodo": 20267,
                "Periodo_Meta": 20247,
                "Meta_Origen": "mismo_mes_historico",
                "Meta_Prorrateada": 1_000_000.0,
                "Ventas_MTD": 580_000.0,
                "Cumplimiento_Prorrateado_Pct": 58.0,
            }
        ],
    }
    scorecard = compute_scorecard(results)
    assert scorecard["presupuesto"]["available"] is True
    assert abs(scorecard["presupuesto"]["current"] - 58.0) < 0.01
    assert scorecard["presupuesto"]["meta_origen"] == "mismo_mes_historico"
    assert scorecard["presupuesto"]["periodo_meta"] == 20247
