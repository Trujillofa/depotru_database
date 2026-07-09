"""Unit tests for KPI scorecard baselines, WoW drop, and return impact."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.utils.generate_kpi_control_board import (  # noqa: E402
    biggest_wow_margin_drop,
    compute_scorecard,
    estimated_return_margin_impact,
    pick_current_and_baseline_q1,
    previous_iso_week_range,
    trend_start_for,
)


def _q1_row(year: int, week: int, margin: float, profit: float, ticket: float):
    return {
        "Anio": year,
        "Semana_ISO": week,
        "Margen_Bruto_Pct": margin,
        "Ganancia_Bruta": profit,
        "Ticket_Promedio": ticket,
    }


def test_trend_start_for_lookback():
    assert trend_start_for("2026-06-29") == "2026-06-01"


def test_previous_iso_week_range():
    assert previous_iso_week_range("2026-06-29") == ("2026-06-22", "2026-06-28")


def test_pick_current_uses_focus_week_and_prior_baseline():
    rows = [
        _q1_row(2026, 23, 12.0, 100.0, 10.0),
        _q1_row(2026, 24, 13.0, 110.0, 11.0),
        _q1_row(2026, 25, 14.0, 120.0, 12.0),
        _q1_row(2026, 26, 15.0, 130.0, 13.0),
        _q1_row(2026, 27, 16.0, 140.0, 14.0),
    ]
    current, baseline = pick_current_and_baseline_q1(
        rows, focus_end="2026-07-05"
    )  # ISO week 27
    assert int(current["Semana_ISO"]) == 27
    assert len(baseline) == 4
    assert [int(r["Semana_ISO"]) for r in baseline] == [23, 24, 25, 26]


def test_single_week_q1_has_no_baseline():
    rows = [_q1_row(2026, 27, 13.7, 220_000_000.0, 270_000.0)]
    current, baseline = pick_current_and_baseline_q1(rows, focus_end="2026-07-05")
    assert int(current["Semana_ISO"]) == 27
    assert baseline == []


def test_compute_scorecard_multi_week_baseline_differs_from_current():
    results = {
        "Q1": [
            _q1_row(2026, 23, 10.0, 100.0, 10.0),
            _q1_row(2026, 24, 10.0, 100.0, 10.0),
            _q1_row(2026, 25, 10.0, 100.0, 10.0),
            _q1_row(2026, 26, 10.0, 100.0, 10.0),
            _q1_row(2026, 27, 14.0, 200.0, 20.0),
        ],
        "Q4": [{"Concentracion_Top10_Pct": 25.0}],
    }
    sc = compute_scorecard(results, focus_end="2026-07-05")
    assert sc["margen"]["baseline"] == 10.0
    assert sc["margen"]["current"] == 14.0
    assert sc["margen"]["delta"] == 4.0
    assert sc["ganancia"]["baseline"] == 100.0
    assert sc["ganancia"]["current"] == 200.0
    assert sc["ganancia"]["delta"] == 100.0  # +100%
    # Snapshot KPIs must not fake baseline == current
    assert sc["dso"]["baseline"] is None
    assert sc["concentracion"]["baseline"] is None
    assert sc["otif"]["baseline"] is None


def test_compute_scorecard_single_week_null_baseline():
    results = {
        "Q1": [_q1_row(2026, 27, 13.7, 1_000_000.0, 50_000.0)],
        "Q4": [],
        "Q9": [{"DSO_Dias": 52.0, "Cartera_Vencida_90_Plus_Pct": 12.3}],
    }
    sc = compute_scorecard(results, focus_end="2026-07-05")
    assert sc["margen"]["baseline"] is None
    assert sc["margen"]["current"] == 13.7
    # Delta falls back to vs target (current+1pp)
    assert sc["margen"]["target"] == 14.7
    assert sc["margen"]["delta"] == -1.0
    assert sc["dso"]["current"] == 52.0
    assert sc["dso"]["target"] == 45.0
    assert sc["dso"]["baseline"] is None
    assert sc["dso"]["delta"] == 7.0


def test_biggest_wow_margin_drop_picks_worst():
    current = [
        {
            "Categoria": "A",
            "Subcategoria": "A1",
            "Ventas_Netas": 5_000_000.0,
            "Margen_Bruto_Pct": 12.0,
        },
        {
            "Categoria": "B",
            "Subcategoria": "B1",
            "Ventas_Netas": 5_000_000.0,
            "Margen_Bruto_Pct": 8.0,
        },
    ]
    prev = [
        {
            "Categoria": "A",
            "Subcategoria": "A1",
            "Ventas_Netas": 5_000_000.0,
            "Margen_Bruto_Pct": 14.0,
        },
        {
            "Categoria": "B",
            "Subcategoria": "B1",
            "Ventas_Netas": 5_000_000.0,
            "Margen_Bruto_Pct": 15.0,
        },
    ]
    drop = biggest_wow_margin_drop(current, prev, min_ventas=1_000_000.0)
    assert drop is not None
    assert drop["Categoria"] == "B"
    assert drop["Drop_Pp"] == 7.0


def test_biggest_wow_margin_drop_empty_without_prev():
    assert biggest_wow_margin_drop([{"Categoria": "X"}], []) is None


def test_estimated_return_margin_impact():
    rows = [
        {"Categoria": "C1", "Tasa_Devolucion_Pct": 10.0, "Ganancia_Bruta": 1_000_000.0},
        {"Categoria": "C2", "Tasa_Devolucion_Pct": 5.0, "Ganancia_Bruta": 2_000_000.0},
        {"Categoria": "C3", "Tasa_Devolucion_Pct": 50.0, "Ganancia_Bruta": -100.0},
    ]
    impact = estimated_return_margin_impact(rows)
    assert impact["total"] == 100_000.0 + 100_000.0
    assert len(impact["top"]) == 2
