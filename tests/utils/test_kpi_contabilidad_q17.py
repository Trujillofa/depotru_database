"""Tests for Q17 accounting KPI pack block."""

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


def test_sql_pack_includes_q17_contabilidad():
    blocks = load_query_blocks(
        ROOT / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
    )
    assert "Q17" in blocks
    sql = blocks["Q17"].upper()
    assert "CONMOVIMIENTO" in sql
    assert "CLASE_PUC" in sql
    assert "SALDO_NETO" in sql


def test_load_query_blocks_requires_q1_through_q17():
    blocks = load_query_blocks(
        ROOT / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
    )
    assert set(blocks.keys()) >= {f"Q{i}" for i in range(1, 18)}


def test_compute_scorecard_includes_contabilidad_from_q17():
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
        "Q17": [
            {
                "Clase_Puc": "4",
                "Total_Creditos": 1_000_000,
                "Total_Debitos": 100_000,
                "Saldo_Neto": 900_000,
            },
            {
                "Clase_Puc": "5",
                "Total_Creditos": 50_000,
                "Total_Debitos": 200_000,
                "Saldo_Neto": -150_000,
            },
            {
                "Clase_Puc": "6",
                "Total_Creditos": 20_000,
                "Total_Debitos": 600_000,
                "Saldo_Neto": -580_000,
            },
        ],
    }
    scorecard = compute_scorecard(results)
    assert scorecard["margen_contable"]["current"] == 400_000
    assert abs(scorecard["margen_contable_pct"]["current"] - 40.0) < 0.01
