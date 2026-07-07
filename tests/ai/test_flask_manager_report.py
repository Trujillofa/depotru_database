"""Tests for manager report Flask endpoints in SmartVannaFlaskApp."""

import json
import os
import sys
from unittest.mock import MagicMock

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from business_analyzer.ai.flask_app import (
    SmartVannaFlaskApp,
    manager_report_api_payload,
    manager_report_download_path,
    patched_vanna_js_content,
)
from business_analyzer.ai.formatting import format_dataframe


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

    def is_sql_valid(self, sql):
        return bool(sql)

    def run_sql(self, sql: str):
        raw = pd.DataFrame({"value": [1]})
        self._last_result_df = raw
        return format_dataframe(raw)

    def should_generate_chart(self, df: pd.DataFrame) -> bool:
        return False

    def route_manager_report_question(self, question: str):
        return self._report_result

    def _build_manager_report(self, year, month, fmt, *, branch_document_code=None):
        return self._report_result


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
        yield client, app, tmp_path, success


class TestManagerReportHelpers:
    def test_manager_report_download_path(self):
        assert (
            manager_report_download_path("/tmp/report_2024_05.html")
            == "/reports/report_2024_05.html"
        )
        assert manager_report_download_path(None) is None

    def test_manager_report_api_payload_success(self):
        payload = manager_report_api_payload(
            {
                "status": "success",
                "message": "ok",
                "path": "/tmp/report_2024_05.pdf",
                "format": "pdf",
                "year": 2024,
                "month": 5,
                "summary": {},
                "record_count": 10,
            },
            "cache-1",
        )
        assert payload["type"] == "manager_report"
        assert payload["download_url"] == "/reports/report_2024_05.pdf"
        assert payload["id"] == "cache-1"

    def test_patched_vanna_js_content(self):
        patched = patched_vanna_js_content()
        assert 'if(n.type==="manager_report")' in patched
        assert 'if(E.type==="manager_report")' in patched
        assert 'if(Se(n),n.type==="manager_report")' not in patched
        assert 'if(Se(E),E.type==="manager_report")' not in patched


class TestManagerReportFlaskRoutes:
    def test_generate_sql_returns_manager_report(self, report_client):
        client, app, tmp_path, success = report_client
        response = client.get(
            "/api/v0/generate_sql?question=Genera+el+informe+de+mayo+2024"
        )
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["type"] == "manager_report"
        assert payload["download_url"] == "/reports/report_2024_05.html"
        assert payload["year"] == 2024
        assert payload["month"] == 5

        cache_entries = [
            item
            for item in app.cache.get_all(field_list=["id", "manager_report"])
            if item.get("manager_report")
        ]
        assert cache_entries

    def test_generate_report_endpoint_with_year_month(self, report_client):
        client, app, tmp_path, success = report_client
        response = client.get("/api/v0/generate_report?year=2024&month=5&format=html")
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["type"] == "manager_report"
        assert "Informe listo" in payload["text"]

    def test_generate_report_endpoint_with_question(self, report_client):
        client, app, tmp_path, success = report_client
        response = client.post(
            "/api/v0/generate_report",
            json={"question": "Genera el informe de mayo 2024 en PDF"},
        )
        assert response.status_code == 200
        assert response.get_json()["type"] == "manager_report"

    def test_serve_manager_report_file(self, report_client):
        client, app, tmp_path, success = report_client
        report_file = tmp_path / "report_2024_05.html"
        report_file.write_text("<html>ok</html>", encoding="utf-8")

        response = client.get("/reports/report_2024_05.html")
        assert response.status_code == 200
        assert b"ok" in response.data

    def test_serve_manager_report_rejects_path_traversal(self, report_client):
        client, app, tmp_path, success = report_client
        response = client.get("/reports/../secret.txt")
        assert response.status_code in (403, 404)

    def test_assets_js_is_patched(self, report_client):
        client, app, tmp_path, success = report_client
        response = client.get("/assets/index-35bab439.js")
        assert response.status_code == 200
        assert b"manager_report" in response.data
