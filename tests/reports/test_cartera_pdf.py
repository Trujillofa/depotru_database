"""Fixture tests for Cartera PDF export. No live DB."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from business_analyzer.reports.cartera_pdf import (
    _f,
    _money,
    _pct,
    _short,
    _strip_html,
    write_cartera_pdf,
)


def _cartera_report():
    return {
        "as_of_date": "2026-07-28",
        "fecha_carga_snapshot": "2026-07-28 19:00:00",
        "summary": {
            "Cartera_Total": 1_730_000,
            "Cartera_Corriente": 600_000,
            "Cartera_Vencida": 1_130_000,
            "Cartera_Vencida_Pct": 65.3,
            "Cartera_Vencida_90_Plus_Pct": 62.4,
            "Clientes_Sobre_Cupo": 2,
        },
        "buckets": [
            {
                "label": "Corriente (al día)",
                "amount": 600_000,
                "share_pct": 34.7,
            }
        ],
        "top_overdue": [
            {
                "cliente_razon_social": "Cliente Gamma con nombre muy largo para truncar",
                "vendedor_nombre": "Ana Pérez",
                "vencido": 1_000_000,
                "total": 1_000_000,
                "dias_vencidos": 200,
            }
        ],
        "over_limit": [
            {
                "cliente_razon_social": "Cliente Beta",
                "cliente_cupo": 300_000,
                "total": 500_000,
                "exceso_cupo": 200_000,
            }
        ],
    }


@pytest.mark.unit
def test_money_and_pct_use_colombian_separators():
    assert _money(1_730_000) == "$1.730.000"
    assert _money("bad") == "—"
    assert _money(None) == "—"
    assert _f(1234.56, 0) == "1.235" or _f(1234, 0) == "1.234"
    assert _f(12.5, 1) == "12,5"
    assert _f(None) == "—"
    assert _pct(65.3) == "65,3%"
    assert _pct("x") == "—"


@pytest.mark.unit
def test_short_and_strip_html():
    assert _short("abc", 10) == "abc"
    assert _short("abcdefghij", 6).endswith("…")
    assert _short(None) == ""
    text = _strip_html("<p>Hola <strong>mundo</strong></p><br/><li>item</li>")
    assert "Hola" in text
    assert "mundo" in text
    assert "<" not in text
    assert "item" in text


@pytest.mark.unit
def test_write_cartera_pdf_creates_pdf(tmp_path: Path):
    path = tmp_path / "cartera.pdf"
    insights = [{"title": "Pulso", "body": "Cobrar <strong>ya</strong>."}]
    out = write_cartera_pdf(_cartera_report(), path, insights=insights)
    assert out == path
    assert path.is_file()
    assert path.stat().st_size > 200
    assert path.read_bytes()[:4] == b"%PDF"


@pytest.mark.unit
def test_write_cartera_pdf_empty_tables_and_default_insights(tmp_path: Path):
    path = tmp_path / "empty.pdf"
    report = {
        "as_of_date": "2026-07-28",
        "summary": {},
        "buckets": [],
        "top_overdue": [],
        "over_limit": [],
    }
    with patch(
        "business_analyzer.reports.cartera_html.build_insights",
        return_value=[{"title": "Sin mora", "body": "Cartera al día."}],
    ):
        write_cartera_pdf(report, path)
    assert path.read_bytes()[:4] == b"%PDF"


@pytest.mark.unit
def test_write_cartera_pdf_requires_reportlab(tmp_path: Path):
    with patch("business_analyzer.reports.cartera_pdf.REPORTLAB_AVAILABLE", False):
        with pytest.raises(RuntimeError, match="ReportLab"):
            write_cartera_pdf(_cartera_report(), tmp_path / "x.pdf")
