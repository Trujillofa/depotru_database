"""Tests for Q15 returns reconciliation KPI pack block."""

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


def test_sql_pack_includes_q15_devoluciones():
    blocks = load_query_blocks(
        ROOT / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
    )
    assert "Q15" in blocks
    sql = blocks["Q15"].upper()
    assert "INVDEVOLUCIONVENTAS" in sql
    assert "BANCO_DATOS" in sql
    assert "DIFERENCIA_UNIDADES" in sql
    assert "TASA_DEVOLUCION_VALIDADA_PCT" in sql
    assert "'DVE'" in sql


def test_load_query_blocks_requires_q1_through_q16():
    blocks = load_query_blocks(
        ROOT / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
    )
    assert set(blocks.keys()) >= {f"Q{i}" for i in range(1, 17)}


def test_compute_scorecard_includes_conciliacion_from_q15():
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
        "Q15": [
            {
                "Unidades_ERP": 100,
                "Unidades_BI": 100,
                "Diferencia_Unidades": 0,
                "Unidades_Vendidas": 10000,
            },
            {
                "Unidades_ERP": 50,
                "Unidades_BI": 45,
                "Diferencia_Unidades": -5,
                "Unidades_Vendidas": 5000,
            },
        ],
    }
    scorecard = compute_scorecard(results)
    assert abs(scorecard["conciliacion_devoluciones"]["current"] - 96.666) < 0.1
    assert scorecard["conciliacion_devoluciones"]["target"] == 99.0
    assert scorecard["categorias_brecha_dev"]["current"] == 1
