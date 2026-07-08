"""Tests for accounting CLI."""

from __future__ import annotations

from business_analyzer.core.contabilidad_cli import main, render_markdown


def test_render_markdown_shows_cuadre():
    report = {
        "period": {"start": "2024-12-01", "end": "2024-12-31"},
        "summary": {
            "Movimientos": 100,
            "Lineas": 500,
            "Total_Debitos": 1_000_000,
            "Total_Creditos": 1_000_000,
            "Cuadre_OK": 1,
        },
        "pyg_summary": {
            "Ingresos_Creditos": 800_000,
            "Costos_Debitos": 500_000,
            "Gastos_Debitos": 50_000,
            "Margen_Bruto_Contable": 300_000,
            "Margen_Contable_Pct": 37.5,
        },
        "conciliacion_ingresos": {"Conciliacion_Ingresos_Pct": 94.0},
        "gastos_centro": [],
        "top_gastos": [],
    }
    md = render_markdown(report)
    assert "Cuadre OK" in md
    assert "94,00%" in md


def test_main_writes_file(tmp_path, monkeypatch):
    report = {
        "period": {"start": "2024-12-01", "end": "2024-12-31"},
        "summary": {"Movimientos": 1, "Cuadre_OK": 1},
        "pyg_summary": {},
        "conciliacion_ingresos": {},
        "gastos_centro": [],
        "top_gastos": [],
    }

    class FakeRunner:
        def build_report(self, start, end):
            return report

    monkeypatch.setattr(
        "business_analyzer.core.contabilidad_cli.ContabilidadRunner",
        lambda *a, **k: FakeRunner(),
    )
    out = tmp_path / "cont.md"
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
