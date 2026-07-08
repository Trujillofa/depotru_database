"""Tests for Q16 electronic invoice KPI pack block."""

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


def test_sql_pack_includes_q16_factura_electronica():
    blocks = load_query_blocks(
        ROOT / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
    )
    assert "Q16" in blocks
    sql = blocks["Q16"].upper()
    assert "INVESTADOFACTURAELECTRONICA" in sql
    assert "TASA_ACEPTACION_PCT" in sql
    assert "TASA_RECHAZO_PCT" in sql
    assert "ES_ACEPTADA" in sql


def test_load_query_blocks_requires_q1_through_q17():
    blocks = load_query_blocks(
        ROOT / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
    )
    assert set(blocks.keys()) >= {f"Q{i}" for i in range(1, 18)}


def test_compute_scorecard_includes_factura_electronica_from_q16():
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
        "Q16": [
            {
                "DocumentosCodigo": "FED",
                "Emitidas": 100,
                "Aceptadas": 98,
                "Rechazadas": 2,
                "Tasa_Aceptacion_Pct": 98.0,
                "Tasa_Rechazo_Pct": 2.0,
            },
            {
                "DocumentosCodigo": "FET",
                "Emitidas": 50,
                "Aceptadas": 50,
                "Rechazadas": 0,
                "Tasa_Aceptacion_Pct": 100.0,
                "Tasa_Rechazo_Pct": 0.0,
            },
        ],
    }
    scorecard = compute_scorecard(results)
    assert abs(scorecard["factura_electronica_aceptacion"]["current"] - 98.666) < 0.1
    assert scorecard["factura_electronica_aceptacion"]["target"] == 99.5
    assert abs(scorecard["factura_electronica_rechazo"]["current"] - 1.333) < 0.1
