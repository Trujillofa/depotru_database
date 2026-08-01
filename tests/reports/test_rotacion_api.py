"""Tests for Rotación de Existencias web API helpers."""

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
    rotacion_api_payload,
    rotacion_status_text,
)
from business_analyzer.reports.rotacion_existencias import (
    build_rotacion_result,
    default_as_of_date,
    render_markdown,
    rotacion_output_basename,
    validate_as_of_date,
)


class _StubVanna:
    run_sql_is_set = True


class TestRotacionHelpers:
    def test_default_as_of_date_is_yesterday(self):
        assert default_as_of_date(today=date(2026, 7, 30)) == "2026-07-29"

    def test_validate_as_of_date(self):
        assert validate_as_of_date("2026-07-28") == "2026-07-28"
        with pytest.raises(ValueError):
            validate_as_of_date("28-07-2026")

    def test_basename(self):
        assert (
            rotacion_output_basename("2026-07-28", "html")
            == "ROTACION_EXISTENCIAS_2026-07-28.html"
        )
        assert (
            rotacion_output_basename("2026-07-28", "pdf")
            == "ROTACION_EXISTENCIAS_2026-07-28.pdf"
        )

    def test_render_markdown_includes_sections(self):
        md = render_markdown(
            {
                "as_of_date": "2026-07-28",
                "velocity_days": 90,
                "demand_mode": "warehouse",
                "demand_mode_label": "test",
                "excluded_document_codes": ["XY"],
                "detail_row_count": 1,
                "warehouse_policy": {"allowlist": ["ALM"]},
                "summary": {"Filas": 1, "QUIEBRE": 1, "MUERTO": 0, "SOBRESTOCK": 0},
                "action_quiebre": [],
                "action_capital_atrapado": [],
                "suggested_transfers": [],
                "abc": [],
                "by_warehouse": [],
            }
        )
        assert "Rotación de Existencias" in md
        assert "Traslados sugeridos" in md

    def test_build_rotacion_result_invalid_date(self):
        result = build_rotacion_result(as_of_date="bad")
        assert result["status"] == "error"

    def test_build_rotacion_result_writes_file(self, tmp_path):
        fake_report = {
            "as_of_date": "2026-07-28",
            "velocity_days": 90,
            "demand_mode": "warehouse",
            "demand_mode_label": "test",
            "excluded_document_codes": ["XY"],
            "detail_row_count": 0,
            "warehouse_policy": {"allowlist": ["ALM"]},
            "summary": {
                "Filas": 0,
                "QUIEBRE": 0,
                "MUERTO": 0,
                "SOBRESTOCK": 0,
                "Share_Unidades_Muerto": 0,
            },
            "action_quiebre": [],
            "action_capital_atrapado": [],
            "suggested_transfers": [],
            "abc": [],
            "by_warehouse": [],
            "data_quality_notes": [],
        }

        class FakeRunner:
            def __init__(self, *a, **k):
                pass

            def build_report(self, as_of):
                return {**fake_report, "as_of_date": as_of}

        with patch(
            "business_analyzer.reports.rotacion_existencias.InventoryTurnoverRunner",
            FakeRunner,
        ):
            result = build_rotacion_result(
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
        assert "Rotación de Existencias" in html
        assert "Insights" in html or "insights" in html.lower()

    def test_rotacion_api_payload(self):
        payload = rotacion_api_payload(
            {
                "status": "success",
                "message": "ok",
                "path": "/tmp/ROTACION_EXISTENCIAS_2026-07-28.html",
                "as_of_date": "2026-07-28",
                "demand_mode": "warehouse",
            },
            "cache-1",
        )
        assert payload["type"] == "rotacion"
        assert (
            payload["download_url"] == "/reports/ROTACION_EXISTENCIAS_2026-07-28.html"
        )
        assert "2026-07-28" in rotacion_status_text(
            {"as_of_date": "2026-07-28", "path": payload["download_url"]}
        )


@pytest.fixture
def rotacion_client(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    app = SmartVannaFlaskApp(_StubVanna(), chart=False)
    app.flask_app.config["TESTING"] = True
    with app.flask_app.test_client() as client:
        yield client, tmp_path


class TestRotacionFlaskRoute:
    def test_generate_rotacion_endpoint(self, rotacion_client):
        client, tmp_path = rotacion_client
        output = tmp_path / "ROTACION_EXISTENCIAS_2026-07-28.md"
        output.write_text("# Rotación\n", encoding="utf-8")

        html_out = tmp_path / "ROTACION_EXISTENCIAS_2026-07-28.html"
        html_out.write_text("<html>rotacion</html>", encoding="utf-8")
        with patch(
            "business_analyzer.reports.rotacion_existencias.build_rotacion_result",
            return_value={
                "status": "success",
                "format": "html",
                "as_of_date": "2026-07-28",
                "demand_mode": "warehouse",
                "path": str(html_out),
                "message": "ok",
            },
        ):
            response = client.post(
                "/api/v0/generate_rotacion",
                json={"as_of_date": "2026-07-28", "format": "html"},
            )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["type"] == "rotacion"
        assert payload["as_of_date"] == "2026-07-28"
        assert (
            payload["download_url"] == "/reports/ROTACION_EXISTENCIAS_2026-07-28.html"
        )

    def test_generate_rotacion_requires_date(self, rotacion_client):
        client, _ = rotacion_client
        response = client.post("/api/v0/generate_rotacion", json={})
        assert response.status_code == 200
        assert response.get_json()["type"] == "error"
