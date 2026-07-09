"""Tests for weekly KPI control board API helpers."""

from __future__ import annotations

import os
import sys
from datetime import date
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from business_analyzer.ai.flask_app import (
    SmartVannaFlaskApp,
    kpi_board_api_payload,
    kpi_board_status_text,
)
from business_analyzer.reports.kpi_control_board import (
    iso_week_date_range,
    iso_weeks_in_year,
    kpi_board_output_basename,
    last_completed_iso_week,
)


class _StubVanna:
    run_sql_is_set = True


class TestKpiControlBoardHelpers:
    def test_last_completed_iso_week(self):
        # Wednesday 2026-07-08 -> previous week is ISO week 27 of 2026
        assert last_completed_iso_week(today=date(2026, 7, 8)) == (2026, 27)

    def test_iso_week_date_range(self):
        start, end = iso_week_date_range(2026, 27)
        assert start == "2026-06-29"
        assert end == "2026-07-05"

    def test_iso_weeks_in_year(self):
        assert iso_weeks_in_year(2026) in (52, 53)

    def test_kpi_board_output_basename(self):
        assert kpi_board_output_basename(2026, 7) == "KPI_CONTROL_BOARD_2026_W07.md"

    def test_kpi_board_status_text(self):
        text = kpi_board_status_text(
            {
                "iso_year": 2026,
                "iso_week": 27,
                "start_date": "2026-06-29",
                "end_date": "2026-07-05",
                "path": "/tmp/KPI_CONTROL_BOARD_2026_W27.md",
            }
        )
        assert "semana 27 2026" in text
        assert "KPI_CONTROL_BOARD_2026_W27.md" in text

    def test_kpi_board_api_payload_success(self):
        payload = kpi_board_api_payload(
            {
                "status": "success",
                "message": "ok",
                "path": "/tmp/KPI_CONTROL_BOARD_2026_W27.md",
                "iso_year": 2026,
                "iso_week": 27,
                "start_date": "2026-06-29",
                "end_date": "2026-07-05",
            },
            "cache-kpi",
        )
        assert payload["type"] == "kpi_board"
        assert payload["download_url"] == "/reports/KPI_CONTROL_BOARD_2026_W27.md"
        assert payload["status_text"]


@pytest.fixture
def kpi_client(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    app = SmartVannaFlaskApp(_StubVanna(), chart=False)
    app.flask_app.config["TESTING"] = True
    with app.flask_app.test_client() as client:
        yield client, tmp_path


class TestKpiBoardFlaskRoute:
    def test_generate_kpi_board_endpoint(self, kpi_client):
        client, tmp_path = kpi_client
        output = tmp_path / "KPI_CONTROL_BOARD_2026_W27.md"
        output.write_text("# KPI\n", encoding="utf-8")

        with patch(
            "business_analyzer.reports.kpi_control_board.build_kpi_board_result",
            return_value={
                "status": "success",
                "format": "markdown",
                "iso_year": 2026,
                "iso_week": 27,
                "start_date": "2026-06-29",
                "end_date": "2026-07-05",
                "path": str(output),
                "message": "ok",
            },
        ):
            response = client.post(
                "/api/v0/generate_kpi_board",
                json={"iso_year": 2026, "iso_week": 27},
            )

        assert response.status_code == 200
        payload = response.get_json()
        assert payload["type"] == "kpi_board"
        assert payload["iso_week"] == 27
        assert payload["download_url"] == "/reports/KPI_CONTROL_BOARD_2026_W27.md"

    def test_generate_kpi_board_requires_period(self, kpi_client):
        client, _ = kpi_client
        response = client.post("/api/v0/generate_kpi_board", json={})
        assert response.status_code == 200
        assert response.get_json()["type"] == "error"
