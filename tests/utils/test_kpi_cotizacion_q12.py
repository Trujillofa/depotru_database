"""Tests for Q12 cotización funnel KPI pack block."""

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


def test_sql_pack_includes_q12_cotizacion_funnel():
    blocks = load_query_blocks(
        ROOT / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
    )
    assert "Q12" in blocks
    sql = blocks["Q12"].upper()
    assert "J3SYSTEM.DBO.INVCOTIZACAB" in sql
    assert "J3SYSTEM.DBO.INVVENTASTOTALES" in sql
    assert "NUMEROCOTIZA" in sql
    assert "CT-' + CAST" in blocks["Q12"]
    assert "V.FECHA >= C.FECHA" in sql
    assert "TASA_CONVERSION_PCT" in sql
    assert "PERDIDAS" in sql


def test_load_query_blocks_requires_q1_through_q15():
    blocks = load_query_blocks(
        ROOT / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
    )
    assert set(blocks.keys()) >= {f"Q{i}" for i in range(1, 17)}


def test_compute_scorecard_includes_conversion_from_q12():
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
        "Q12": [
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
        ],
    }
    scorecard = compute_scorecard(results)
    assert abs(scorecard["conversion_cotiza"]["current"] - (50 / 150 * 100)) < 0.01
    assert scorecard["conversion_cotiza"]["target"] == 30.0
    assert abs(scorecard["dias_conversion"]["current"] - 1.4) < 0.01
    assert scorecard["dias_conversion"]["target"] == 7.0
