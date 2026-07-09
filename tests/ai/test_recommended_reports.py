"""Tests for Vanna recommended-reports catalog and UI hooks."""

from __future__ import annotations

import json
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

import pandas as pd

from business_analyzer.ai.flask_app import SmartVannaFlaskApp
from business_analyzer.ai.formatting import format_dataframe
from business_analyzer.ai.recommended_reports import (
    build_manager_action,
    get_recommended_reports,
    inject_recommended_reports_ui,
    previous_calendar_month,
    recommended_reports_payload,
)


class _ReportStubVanna:
    run_sql_is_set = True
    provider = "grok"

    def __init__(self, report_result=None):
        self._report_result = report_result
        self._last_result_df = None
        self.last_build = None

    def generate_sql(self, question, allow_llm_to_see_data=True, **kwargs):
        self._manager_report_result = self._report_result
        return None

    def pop_manager_report_result(self):
        result = getattr(self, "_manager_report_result", None)
        self._manager_report_result = None
        return result

    def route_manager_report_question(self, question: str):
        return self._report_result

    def _build_manager_report(self, year, month, fmt, *, branch_document_code=None):
        self.last_build = {
            "year": year,
            "month": month,
            "format": fmt,
            "branch": branch_document_code,
        }
        result = dict(self._report_result or {})
        result["format"] = fmt
        return result


class TestRecommendedReportsCatalog:
    def test_previous_calendar_month(self):
        assert previous_calendar_month(today=date(2026, 7, 8)) == (2026, 6)
        assert previous_calendar_month(today=date(2026, 1, 15)) == (2025, 12)

    def test_catalog_has_manager_shortcut_with_stable_fields(self):
        reports = get_recommended_reports(today=date(2026, 7, 8))
        assert len(reports) >= 1
        entry = reports[0]
        assert entry["id"] == "manager"
        assert entry["title"]
        assert entry["description"]
        assert "template" in entry
        action = entry["action"]
        assert action["type"] == "generate_report"
        assert action["year"] == 2026
        assert action["month"] == 6
        assert action["format"] == "html"
        assert "question" in action

    def test_payload_includes_period_defaults_and_month_names(self):
        payload = recommended_reports_payload(today=date(2024, 12, 15))
        assert "reports" in payload
        assert len(payload["reports"]) == 6
        assert payload["default_year"] == 2024
        assert payload["default_month"] == 11
        assert payload["month_names"]["12"] == "Diciembre"

    def test_build_manager_action_pdf_question(self):
        action = build_manager_action(year=2024, month=12, fmt="pdf")
        assert action["format"] == "pdf"
        assert "en PDF" in action["question"]

    def test_format_options_include_json(self):
        payload = recommended_reports_payload(today=date(2026, 7, 8))
        values = {opt["value"] for opt in payload["format_options"]}
        assert values == {"html", "pdf", "json"}

    def test_build_manager_action_with_ai_and_branch(self):
        action = build_manager_action(
            year=2024,
            month=5,
            fmt="html",
            with_ai=True,
            branch="sika_center",
        )
        assert "mayo 2024" in action["question"]
        assert "con análisis de IA" in action["question"]
        assert "sika center" in action["question"]
        assert action["branch"] == "sika_center"

    def test_inject_recommended_reports_ui_adds_panel_and_period_controls(self):
        html = '<html><head></head><body class="bg-white dark:bg-slate-900"><div id="app"></div></body></html>'
        patched = inject_recommended_reports_ui(html)
        assert 'id="informes-recomendados"' in patched
        assert "Informes recomendados" in patched
        assert "informes-recomendados-loader" in patched
        assert "informe-period" in patched
        assert "informe-month" in patched
        assert "informe-year" in patched
        assert "informe-generate-btn" in patched
        assert "informe-format" in patched
        assert "informe-week" in patched
        assert "generate_kpi_board" in patched


@pytest.fixture
def report_client(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    success = {
        "status": "success",
        "message": "Informe listo",
        "path": str(tmp_path / "report_2024_05.html"),
        "format": "html",
        "year": 2024,
        "month": 5,
        "summary": {"total_revenue_with_iva": "$1"},
        "record_count": 100,
    }
    stub = _ReportStubVanna(success)
    app = SmartVannaFlaskApp(stub, chart=False)
    app.flask_app.config["TESTING"] = True
    with app.flask_app.test_client() as client:
        yield client, stub, success


class TestRecommendedReportsFlaskRoutes:
    def test_recommended_reports_api(self, report_client, tmp_path):
        client, _, _ = report_client
        response = client.get("/api/v0/recommended_reports")
        assert response.status_code == 200
        payload = response.get_json()
        assert len(payload["reports"]) >= 1
        first = payload["reports"][0]
        assert {"id", "title", "description", "action", "template"} <= set(first.keys())
        assert {
            "default_year",
            "default_month",
            "default_iso_year",
            "default_iso_week",
            "max_iso_week",
            "default_format",
            "format_options",
            "month_names",
        } <= set(payload.keys())
        kpi_entry = next(
            r for r in payload["reports"] if r["id"] == "kpi-control-board"
        )
        assert kpi_entry["period_type"] == "week"
        assert kpi_entry["action"]["type"] == "generate_kpi_board"

        evidence = tmp_path / "recommended-reports.json"
        evidence.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    def test_index_includes_recommended_panel(self, report_client, tmp_path):
        client, _, _ = report_client
        response = client.get("/")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "informes-recomendados" in body
        assert "Informes recomendados" in body
        (tmp_path / "vanna-index.html").write_text(body, encoding="utf-8")

    def test_catalog_html_entry_triggers_manager_report(self, report_client, tmp_path):
        client, stub, success = report_client
        catalog = client.get("/api/v0/recommended_reports").get_json()
        html_entry = next(r for r in catalog["reports"] if r["id"] == "manager")
        response = client.post("/api/v0/generate_report", json=html_entry["action"])
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["type"] == "manager_report"
        assert payload["text"]
        assert payload["status_text"]
        assert payload["format"] == "html"
        assert stub.last_build["format"] == "html"
        assert payload["download_url"] == "/reports/report_2024_05.html"
        (tmp_path / "report-trigger-html.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2)
        )

    def test_catalog_pdf_entry_uses_explicit_format(self, report_client, tmp_path):
        client, stub, success = report_client
        catalog = client.get("/api/v0/recommended_reports").get_json()
        pdf_action = build_manager_action(year=2024, month=5, fmt="pdf")
        response = client.post("/api/v0/generate_report", json=pdf_action)
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["type"] == "manager_report"
        assert stub.last_build is not None
        assert stub.last_build["format"] == "pdf"
        assert payload["format"] == "pdf"
        (tmp_path / "report-trigger-pdf.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2)
        )

    def test_catalog_json_entry_uses_explicit_format(self, report_client, tmp_path):
        client, stub, _ = report_client
        json_action = build_manager_action(year=2024, month=5, fmt="json")
        response = client.post("/api/v0/generate_report", json=json_action)
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["type"] == "manager_report"
        assert stub.last_build["format"] == "json"
        assert payload["format"] == "json"
