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
        return self._report_result


class TestRecommendedReportsCatalog:
    def test_previous_calendar_month(self):
        assert previous_calendar_month(today=date(2026, 7, 8)) == (2026, 6)
        assert previous_calendar_month(today=date(2026, 1, 15)) == (2025, 12)

    def test_catalog_has_manager_shortcut_with_stable_fields(self):
        reports = get_recommended_reports(today=date(2026, 7, 8))
        assert len(reports) >= 1
        entry = reports[0]
        assert entry["id"] == "manager-prev-month-html"
        assert entry["title"]
        assert entry["description"]
        action = entry["action"]
        assert action["type"] == "generate_report"
        assert action["year"] == 2026
        assert action["month"] == 6
        assert action["format"] == "html"
        assert "question" in action

    def test_payload_wraps_reports(self):
        payload = recommended_reports_payload(today=date(2024, 12, 15))
        assert "reports" in payload
        assert len(payload["reports"]) >= 3

    def test_inject_recommended_reports_ui_adds_panel(self):
        html = '<html><head></head><body class="bg-white dark:bg-slate-900"><div id="app"></div></body></html>'
        patched = inject_recommended_reports_ui(html)
        assert 'id="informes-recomendados"' in patched
        assert "Informes recomendados" in patched
        assert "informes-recomendados-loader" in patched


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
    app = SmartVannaFlaskApp(_ReportStubVanna(success), chart=False)
    app.flask_app.config["TESTING"] = True
    with app.flask_app.test_client() as client:
        yield client, success


class TestRecommendedReportsFlaskRoutes:
    def test_recommended_reports_api(self, report_client, tmp_path):
        client, _ = report_client
        response = client.get("/api/v0/recommended_reports")
        assert response.status_code == 200
        payload = response.get_json()
        assert len(payload["reports"]) >= 1
        first = payload["reports"][0]
        assert {"id", "title", "description", "action"} <= set(first.keys())

        evidence = tmp_path / "recommended-reports.json"
        evidence.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    def test_index_includes_recommended_panel(self, report_client, tmp_path):
        client, _ = report_client
        response = client.get("/")
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "informes-recomendados" in body
        assert "Informes recomendados" in body
        (tmp_path / "vanna-index.html").write_text(body, encoding="utf-8")

    def test_catalog_entry_triggers_manager_report(self, report_client, tmp_path):
        client, success = report_client
        catalog = client.get("/api/v0/recommended_reports").get_json()
        action = catalog["reports"][0]["action"]
        response = client.post("/api/v0/generate_report", json=action)
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["type"] == "manager_report"
        assert payload["text"]
        assert payload["download_url"] == "/reports/report_2024_05.html"
        (tmp_path / "report-trigger.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2)
        )
