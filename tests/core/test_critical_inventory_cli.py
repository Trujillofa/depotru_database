"""Tests for critical inventory CLI."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from business_analyzer.core.critical_inventory_cli import main, render_markdown


def _sample_report() -> dict:
    return {
        "as_of_date": "2024-12-31",
        "velocity_days": 90,
        "summary": {
            "SKUs_Criticos": 2,
            "SKUs_Quiebre_7d": 1,
            "SKUs_Stock_Bajo": 1,
            "Promedio_Dias_Cobertura": 4.5,
        },
        "critical_skus": [
            {
                "SKU": "0020030001",
                "Producto": "CEMENTO GRIS",
                "AlmacenCodigo": "FLO",
                "Saldo_Actual": 5,
                "Cantidad_90d": 1000,
                "Dias_Cobertura": 0.45,
                "Prioridad": "QUIEBRE_INMINENTE",
            }
        ],
        "by_warehouse": [
            {
                "AlmacenCodigo": "FLO",
                "AlmacenNombre": "FLORENCIA",
                "SKUs_Criticos": 10,
                "SKUs_Quiebre_7d": 3,
                "Promedio_Dias_Cobertura": 5.2,
            }
        ],
        "top_warehouses": [],
    }


def test_render_markdown_includes_summary_and_sku():
    md = render_markdown(_sample_report())
    assert "Inventario Crítico" in md
    assert "0020030001" in md
    assert "QUIEBRE_INMINENTE" in md
    assert "FLO" in md


@patch("business_analyzer.core.critical_inventory_cli.CriticalInventoryRunner")
def test_main_writes_markdown_file(mock_runner_cls, tmp_path):
    runner = MagicMock()
    runner.build_report.return_value = _sample_report()
    mock_runner_cls.return_value = runner

    out = tmp_path / "inv.md"
    rc = main(["--as-of-date", "2024-12-31", "--output", str(out)])
    assert rc == 0
    assert out.exists()
    assert "0020030001" in out.read_text(encoding="utf-8")


@patch("business_analyzer.core.critical_inventory_cli.CriticalInventoryRunner")
def test_main_json_stdout(mock_runner_cls, capsys):
    runner = MagicMock()
    runner.build_report.return_value = _sample_report()
    mock_runner_cls.return_value = runner

    rc = main(["--as-of-date", "2024-12-31", "--json"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "0020030001" in captured.out
