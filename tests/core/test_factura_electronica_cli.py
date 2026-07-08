"""Tests for electronic invoice CLI."""

from __future__ import annotations

from business_analyzer.core.factura_electronica_cli import main, render_markdown


def test_render_markdown_shows_acceptance_rate():
    report = {
        "period": {"start": "2024-12-01", "end": "2024-12-31"},
        "summary": {
            "Emitidas": 100,
            "Aceptadas": 100,
            "Rechazadas": 0,
            "Tasa_Aceptacion_Pct": 100.0,
            "Tasa_Rechazo_Pct": 0.0,
            "Valor_Total": 1_000_000,
        },
        "by_documento": [
            {
                "DocumentosCodigo": "FED",
                "Emitidas": 80,
                "Aceptadas": 80,
                "Rechazadas": 0,
                "Tasa_Aceptacion_Pct": 100.0,
                "Tasa_Rechazo_Pct": 0.0,
            }
        ],
        "rechazos": [],
    }
    md = render_markdown(report)
    assert "100,00%" in md
    assert "FED" in md
    assert "Sin rechazos" in md


def test_main_writes_file(tmp_path, monkeypatch):
    report = {
        "period": {"start": "2024-12-01", "end": "2024-12-31"},
        "summary": {"Emitidas": 1, "Aceptadas": 1, "Rechazadas": 0},
        "by_documento": [],
        "rechazos": [],
    }

    class FakeRunner:
        def build_report(self, start, end):
            return report

    monkeypatch.setattr(
        "business_analyzer.core.factura_electronica_cli.FacturaElectronicaRunner",
        lambda *a, **k: FakeRunner(),
    )
    out = tmp_path / "fe.md"
    assert (
        main(
            [
                "--start-date",
                "2024-12-01",
                "--end-date",
                "2024-12-31",
                "--output",
                str(out),
            ]
        )
        == 0
    )
    assert out.exists()
