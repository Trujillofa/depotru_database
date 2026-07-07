"""Tests for cotización funnel CLI."""

from __future__ import annotations

import json
from unittest.mock import patch

from business_analyzer.core.cotizacion_funnel_cli import main


def _sample_report() -> dict:
    return {
        "period": {"start": "2024-12-01", "end": "2024-12-31"},
        "summary": {
            "Cotizaciones": 100,
            "Convertidas": 25,
            "Perdidas": 75,
            "Tasa_Conversion_Pct": 25.0,
            "Dias_Promedio_Conversion": 1.0,
        },
        "by_vendor": [
            {
                "Vendedor_Codigo": "102",
                "Vendedor_Nombre": "Vendedor Test",
                "Cotizaciones": 100,
                "Convertidas": 25,
                "Perdidas": 75,
                "Tasa_Conversion_Pct": 25.0,
                "Dias_Promedio_Conversion": 1.0,
            }
        ],
        "top_lost_vendors": [],
        "low_conversion_vendors": [],
    }


@patch("business_analyzer.core.cotizacion_funnel_cli.CotizacionFunnelRunner")
def test_cli_json_output(mock_runner_cls, capsys):
    mock_runner_cls.return_value.build_report.return_value = _sample_report()

    code = main(["--start-date", "2024-12-01", "--end-date", "2024-12-31", "--json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["period"]["start"] == "2024-12-01"
    assert payload["summary"]["Cotizaciones"] == 100
    assert len(payload["by_vendor"]) == 1


@patch("business_analyzer.core.cotizacion_funnel_cli.CotizacionFunnelRunner")
def test_cli_writes_markdown_report(mock_runner_cls, tmp_path):
    mock_runner_cls.return_value.build_report.return_value = _sample_report()
    out = tmp_path / "funnel.md"

    code = main(
        [
            "--start-date",
            "2024-12-01",
            "--end-date",
            "2024-12-31",
            "--output",
            str(out),
        ]
    )

    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "Embudo Cotización" in text
    assert "Vendedor Test" in text
