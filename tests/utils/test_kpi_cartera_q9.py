"""Tests for Q9 cartera / DSO KPI pack integration."""

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


def test_sql_pack_includes_q9_banco_cartera():
    blocks = load_query_blocks(
        ROOT / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
    )
    assert "Q9" in blocks
    sql = blocks["Q9"].upper()
    assert "BANCO_CARTERA" in sql
    assert "DSO_DIAS" in sql
    assert "CARTERA_VENCIDA_90_PLUS_PCT" in sql
    assert "BANCO_DATOS" in sql


def test_compute_scorecard_includes_dso_and_cartera_90():
    results = {
        "Q1": [
            {
                "Anio": 2026,
                "Semana_ISO": 27,
                "Margen_Bruto_Pct": 30.0,
                "Ganancia_Bruta": 1_000_000.0,
                "Ticket_Promedio": 50_000.0,
            }
        ],
        "Q4": [{"Concentracion_Top10_Pct": 25.0}],
        "Q9": [
            {
                "DSO_Dias": 52.0,
                "Cartera_Vencida_90_Plus_Pct": 12.3,
                "Cartera_Total": 5_000_000_000.0,
            }
        ],
    }
    scorecard = compute_scorecard(results)
    assert scorecard["dso"]["current"] == 52.0
    assert scorecard["dso"]["target"] == 45.0
    assert scorecard["cartera_90"]["current"] == 12.3
    assert scorecard["cartera_90"]["target"] == 12.0
