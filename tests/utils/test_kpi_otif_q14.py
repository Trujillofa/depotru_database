"""Tests for Q14 OTIF KPI pack block."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.utils.generate_kpi_control_board import (  # noqa: E402
    compute_scorecard,
    load_query_blocks,
)


def test_sql_pack_includes_q14_otif():
    blocks = load_query_blocks(
        ROOT / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
    )
    assert "Q14" in blocks
    sql = blocks["Q14"].upper()
    assert "INVHISTORICOENTREGAS" in sql
    assert "OTIF_PCT" in sql
    assert "LEAD_TIME_PROMEDIO_DIAS" in sql
    assert "CONVERT(DATE" in sql


def test_load_query_blocks_requires_q1_through_q16():
    blocks = load_query_blocks(
        ROOT / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
    )
    assert set(blocks.keys()) >= {f"Q{i}" for i in range(1, 18)}


def test_compute_scorecard_includes_otif_from_q14():
    results = {
        "Q1": [
            {
                "Anio": 2024,
                "Semana_ISO": 52,
                "Margen_Bruto_Pct": 25.0,
                "Ganancia_Bruta": 1_000_000.0,
                "Ticket_Promedio": 50_000.0,
            }
        ],
        "Q4": [{"Concentracion_Top10_Pct": 22.0}],
        "Q14": [
            {
                "Almacen_Codigo": "ALM",
                "Total_Entregas": 100,
                "Entregas_A_Tiempo": 80,
                "Entregas_Tarde": 20,
                "OTIF_Pct": 80.0,
                "Lead_Time_Promedio_Dias": 2.0,
                "Fill_Rate_Pct": 99.0,
            },
            {
                "Almacen_Codigo": "SUR",
                "Total_Entregas": 50,
                "Entregas_A_Tiempo": 25,
                "Entregas_Tarde": 25,
                "OTIF_Pct": 50.0,
                "Lead_Time_Promedio_Dias": 4.0,
                "Fill_Rate_Pct": 97.0,
            },
        ],
    }
    scorecard = compute_scorecard(results)
    assert abs(scorecard["otif"]["current"] - 70.0) < 0.01
    assert scorecard["otif"]["target"] == 85.0
    assert abs(scorecard["lead_time_entrega"]["current"] - 2.666) < 0.1
