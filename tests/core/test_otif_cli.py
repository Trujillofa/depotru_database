"""Tests for OTIF CLI."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from business_analyzer.core.otif_cli import main, render_markdown


def _sample_report() -> dict:
    return {
        "period": {"start": "2024-12-01", "end": "2024-12-31"},
        "summary": {
            "Total_Entregas": 28985,
            "Entregas_A_Tiempo": 19788,
            "Entregas_Tarde": 9197,
            "OTIF_Pct": 68.27,
            "Lead_Time_Promedio_Dias": 1.43,
            "Fill_Rate_Pct": 98.68,
        },
        "by_warehouse": [
            {
                "Almacen_Codigo": "BOD",
                "Total_Entregas": 353,
                "Entregas_A_Tiempo": 13,
                "Entregas_Tarde": 340,
                "OTIF_Pct": 3.68,
                "Lead_Time_Promedio_Dias": 5.0,
                "Fill_Rate_Pct": 99.0,
            }
        ],
        "worst_customers": [
            {
                "Cliente": "CLIENTE TEST",
                "Total_Entregas": 26,
                "OTIF_Pct": 0.0,
                "Lead_Time_Promedio_Dias": 10.0,
            }
        ],
        "worst_warehouses": [],
    }


def test_render_markdown_includes_otif_metrics():
    md = render_markdown(_sample_report())
    assert "OTIF" in md
    assert "68,27%" in md
    assert "BOD" in md
    assert "CLIENTE TEST" in md


@patch("business_analyzer.core.otif_cli.OtifRunner")
def test_main_writes_markdown_file(mock_runner_cls, tmp_path):
    runner = MagicMock()
    runner.build_report.return_value = _sample_report()
    mock_runner_cls.return_value = runner

    out = tmp_path / "otif.md"
    rc = main(
        ["--start-date", "2024-12-01", "--end-date", "2024-12-31", "--output", str(out)]
    )
    assert rc == 0
    assert out.exists()
    assert "OTIF" in out.read_text(encoding="utf-8")
