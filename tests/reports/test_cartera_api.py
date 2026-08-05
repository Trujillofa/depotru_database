"""Tests for Cartera aging web API helpers and report renderers."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from business_analyzer.ai.flask_app import (
    SmartVannaFlaskApp,
    cartera_api_payload,
    cartera_status_text,
)
from business_analyzer.reports.cartera_aging import (
    build_cartera_result,
    cartera_output_basename,
    default_as_of_date,
    render_markdown,
    validate_as_of_date,
)
from business_analyzer.reports.cartera_html import build_insights, render_html


def _fake_report():
    return {
        "as_of_date": "2026-07-28",
        "fecha_carga_snapshot": "2026-07-28 19:00:00",
        "source": "banco_cartera",
        "dso_days_window": 30,
        "include_dso": True,
        "excluded_document_codes": ["XY", "AS", "TS"],
        "summary": {
            "Cartera_Total": 1_730_000,
            "Cartera_Corriente": 600_000,
            "Cartera_Vencida": 1_130_000,
            "Cartera_Vencida_Pct": 65.3,
            "Cartera_Vencida_90_Plus": 1_080_000,
            "Cartera_Vencida_90_Plus_Pct": 62.4,
            "Clientes_Con_Saldo": 3,
            "Clientes_Sobre_Cupo": 2,
            "Documentos_Filas": 4,
            "Dias_Vencidos_Promedio_Ponderado": 120.0,
            "DSO_Dias": 26.0,
            "Ventas_Netas_Periodo": 2_000_000,
            "Dias_Periodo": 30,
            "Bucket_Corriente": 600_000,
            "Bucket_Vencido_30": 50_000,
            "Bucket_Vencido_60": 0,
            "Bucket_Vencido_90": 80_000,
            "Bucket_Vencido_120": 200_000,
            "Bucket_Vencido_360": 800_000,
            "Bucket_Vencido_Superior": 0,
        },
        "buckets": [
            {
                "bucket": "corriente",
                "label": "Corriente (al día)",
                "amount": 600_000,
                "share_pct": 34.7,
            },
            {
                "bucket": "vencido_30",
                "label": "Vencido 1–30 d",
                "amount": 50_000,
                "share_pct": 2.9,
            },
        ],
        "top_overdue": [
            {
                "cliente_razon_social": "Cliente Gamma",
                "vendedor_nombre": "Ana",
                "vencido": 1_000_000,
                "total": 1_000_000,
                "dias_vencidos": 200,
                "vencido_90_plus": 1_000_000,
            }
        ],
        "top_concentration": [
            {
                "cliente_razon_social": "Cliente Gamma",
                "total": 1_000_000,
                "share_total": 0.58,
                "share_acum": 0.58,
                "vencido": 1_000_000,
            }
        ],
        "over_limit": [
            {
                "cliente_razon_social": "Cliente Beta",
                "cliente_cupo": 300_000,
                "total": 500_000,
                "exceso_cupo": 200_000,
                "vendedor_nombre": "Luis",
            }
        ],
        "by_vendedor": [
            {
                "vendedor_nombre": "Ana",
                "clientes": 2,
                "total": 1_230_000,
                "vencido": 1_130_000,
                "vencido_90_plus": 1_080_000,
            }
        ],
        "client_count": 3,
        "document_row_count": 4,
    }


class _StubVanna:
    run_sql_is_set = True


class TestCarteraHelpers:
    def test_default_as_of_date_is_yesterday(self):
        assert default_as_of_date(today=date(2026, 7, 30)) == "2026-07-29"

    def test_validate_as_of_date(self):
        assert validate_as_of_date("2026-07-28") == "2026-07-28"
        with pytest.raises(ValueError):
            validate_as_of_date("28-07-2026")

    def test_basename(self):
        assert (
            cartera_output_basename("2026-07-28", "html")
            == "CARTERA_AGING_2026-07-28.html"
        )
        assert (
            cartera_output_basename("2026-07-28", "pdf")
            == "CARTERA_AGING_2026-07-28.pdf"
        )

    def test_render_markdown_includes_sections(self):
        md = render_markdown(_fake_report())
        assert "Cartera" in md
        assert "Buckets" in md or "aging" in md.lower()
        assert "Top clientes vencidos" in md
        assert "sobre cupo" in md.lower()

    def test_build_insights_spanish_with_severity(self):
        insights = build_insights(_fake_report())
        assert len(insights) >= 4
        titles = " ".join(i["title"] for i in insights)
        assert "cartera" in titles.lower() or "Pulso" in titles
        assert any(
            i.get("severity") in ("danger", "warning", "info", "success")
            for i in insights
        )
        assert any(
            "7 días" in i.get("title", "") or "7 días" in i.get("body", "")
            for i in insights
        )

    def test_render_html_colombian_currency(self):
        html = render_html(_fake_report())
        assert "Cartera" in html
        assert "$1.730.000" in html or "$1.000.000" in html
        assert "Insights" in html or "plan de cobranza" in html.lower()

    def test_build_cartera_result_invalid_date(self):
        result = build_cartera_result(as_of_date="bad")
        assert result["status"] == "error"

    def test_build_cartera_result_writes_file(self, tmp_path):
        class FakeRunner:
            def __init__(self, *a, **k):
                pass

            def build_report(self, as_of):
                r = _fake_report()
                r["as_of_date"] = as_of
                return r

        with patch(
            "business_analyzer.reports.cartera_aging.CarteraAgingRunner",
            FakeRunner,
        ):
            result = build_cartera_result(
                as_of_date="2026-07-28",
                output_dir=tmp_path,
                fmt="html",
            )
        assert result["status"] == "success"
        assert result["format"] == "html"
        path = Path(result["path"])
        assert path.is_file()
        assert path.suffix == ".html"
        html = path.read_text(encoding="utf-8")
        assert "Cartera" in html

    def test_cartera_api_payload(self):
        payload = cartera_api_payload(
            {
                "status": "success",
                "message": "ok",
                "path": "/tmp/CARTERA_AGING_2026-07-28.html",
                "as_of_date": "2026-07-28",
            },
            "cache-1",
        )
        assert payload["type"] == "cartera"
        assert payload["download_url"] == "/reports/CARTERA_AGING_2026-07-28.html"
        assert "2026-07-28" in cartera_status_text(
            {"as_of_date": "2026-07-28", "path": payload["download_url"]}
        )


@pytest.fixture
def cartera_client(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    app = SmartVannaFlaskApp(_StubVanna(), chart=False)
    app.flask_app.config["TESTING"] = True
    with app.flask_app.test_client() as client:
        yield client, tmp_path


class TestCarteraFlaskRoute:
    def test_generate_cartera_endpoint(self, cartera_client):
        client, tmp_path = cartera_client
        html_out = tmp_path / "CARTERA_AGING_2026-07-28.html"
        html_out.write_text("<html>cartera</html>", encoding="utf-8")
        with patch(
            "business_analyzer.reports.cartera_aging.build_cartera_result",
            return_value={
                "status": "success",
                "format": "html",
                "as_of_date": "2026-07-28",
                "path": str(html_out),
                "message": "ok",
                "insights_count": 5,
            },
        ):
            response = client.post(
                "/api/v0/generate_cartera",
                json={"as_of_date": "2026-07-28", "format": "html"},
            )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["type"] == "cartera"
        assert payload["as_of_date"] == "2026-07-28"
        assert payload["download_url"] == "/reports/CARTERA_AGING_2026-07-28.html"

    def test_generate_cartera_requires_date(self, cartera_client):
        client, _ = cartera_client
        response = client.post("/api/v0/generate_cartera", json={})
        assert response.status_code == 200
        assert response.get_json()["type"] == "error"
