"""Tests for Q13 critical inventory KPI pack block."""

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


def test_sql_pack_includes_q13_critical_inventory():
    blocks = load_query_blocks(
        ROOT / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
    )
    assert "Q13" in blocks
    sql = blocks["Q13"].upper()
    assert "INVDETALLEEXISTENCIAS" in sql
    assert "BANCO_DATOS" in sql
    assert "DIAS_COBERTURA" in sql
    assert "VENTA_DIARIA_PROMEDIO" in sql
    assert "PRIORIDAD" in sql


def test_load_query_blocks_requires_q1_through_q15():
    blocks = load_query_blocks(
        ROOT / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
    )
    assert set(blocks.keys()) >= {f"Q{i}" for i in range(1, 18)}


def test_compute_scorecard_includes_inventory_from_q13():
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
        "Q13": [
            {
                "SKU": "A",
                "Saldo_Actual": 5,
                "Dias_Cobertura": 2.0,
                "Cantidad_90d": 500,
            },
            {
                "SKU": "B",
                "Saldo_Actual": 8,
                "Dias_Cobertura": 10.0,
                "Cantidad_90d": 200,
            },
        ],
    }
    scorecard = compute_scorecard(results)
    assert scorecard["skus_criticos"]["current"] == 2
    assert scorecard["skus_criticos"]["target"] == 25.0
    assert abs(scorecard["cobertura_critica"]["current"] - 6.0) < 0.01
    assert scorecard["quiebre_7d"]["current"] == 1
