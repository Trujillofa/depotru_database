"""Tests for returns reconciliation CLI."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from business_analyzer.core.devoluciones_conciliacion_cli import main, render_markdown


def _sample_report() -> dict:
    return {
        "period": {"start": "2024-12-01", "end": "2024-12-31"},
        "summary": {
            "Unidades_ERP": 9978,
            "Unidades_BI": 9978,
            "Diferencia_Unidades": 0,
            "Conciliacion_Pct": 100.0,
            "Categorias_Con_Diferencia": 0,
            "Tasa_Devolucion_Validada_Pct": 1.2,
        },
        "by_documento": [
            {
                "DocumentosCodigo": "DVE",
                "Unidades_ERP": 9209,
                "Unidades_BI": 9209,
                "Diferencia_Unidades": 0,
            }
        ],
        "top_gaps": [],
        "top_margin_erosion": [
            {
                "Categoria": "CUBIERTA TRAPEZOIDAL",
                "Impacto_Margen_BI": 500000,
                "Tasa_Devolucion_Validada_Pct": 0.5,
            }
        ],
        "by_category": [],
    }


def test_render_markdown_shows_perfect_conciliacion():
    md = render_markdown(_sample_report())
    assert "100,00%" in md
    assert "9978" in md.replace(".", "")
    assert "CUBIERTA TRAPEZOIDAL" in md


@patch(
    "business_analyzer.core.devoluciones_conciliacion_cli.DevolucionesConciliacionRunner"
)
def test_main_writes_file(mock_runner_cls, tmp_path):
    runner = MagicMock()
    runner.build_report.return_value = _sample_report()
    mock_runner_cls.return_value = runner

    out = tmp_path / "dev.md"
    rc = main(
        ["--start-date", "2024-12-01", "--end-date", "2024-12-31", "--output", str(out)]
    )
    assert rc == 0
    assert out.exists()
