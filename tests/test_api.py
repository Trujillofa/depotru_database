"""Tests for FastAPI REST endpoints."""

import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402


@pytest.fixture
def client():
    return TestClient(api.app)


class TestHealthEndpoint:
    def test_health_no_auth(self, client):
        with patch.dict(os.environ, {"API_KEY": ""}, clear=False):
            resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"


class TestApiKeyAuth:
    def test_rejects_missing_key_when_configured(self, client):
        with patch.dict(os.environ, {"API_KEY": "secret-key"}, clear=False):
            resp = client.get("/analyze")
        assert resp.status_code == 401

    def test_accepts_valid_key(self, client):
        with patch.dict(os.environ, {"API_KEY": "secret-key"}, clear=False):
            with patch.object(api.Config, "has_direct_db_config", return_value=False):
                with patch.object(api.Config, "NCX_FILE_PATH", "/nonexistent.ncx"):
                    resp = client.get("/analyze", headers={"X-API-Key": "secret-key"})
        assert resp.status_code == 200


class TestWhatIfEndpoint:
    def test_uses_config_excluded_document_codes(self, client):
        mock_db = MagicMock()
        mock_db.execute_query.return_value = [{"margin_pct": 25.0, "profit": 1000.0}]
        captured: dict = {}

        def _capture_query(sql, params):
            captured["sql"] = sql
            captured["params"] = params
            return mock_db.execute_query.return_value

        mock_db.execute_query.side_effect = _capture_query

        with patch.dict(os.environ, {"API_KEY": ""}, clear=False):
            with patch("api.Database") as mock_db_cls:
                mock_db_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
                mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)
                resp = client.post(
                    "/scenarios/what-if",
                    json={
                        "product_id": "SKU-1",
                        "price_change_pct": 1.0,
                        "cost_change_pct": 0.0,
                        "volume_change_pct": 5.0,
                    },
                )

        assert resp.status_code == 200
        assert captured["params"][0] == "SKU-1"
        assert captured["params"][1:] == tuple(api.Config.EXCLUDED_DOCUMENT_CODES)


class TestAsyncLoopUsage:
    def test_analyze_uses_running_loop(self, client):
        with patch.dict(os.environ, {"API_KEY": ""}, clear=False):
            with patch.object(api.Config, "has_direct_db_config", return_value=False):
                with patch.object(api.Config, "NCX_FILE_PATH", "/nonexistent.ncx"):
                    with patch(
                        "api.asyncio.get_running_loop",
                        wraps=asyncio.get_running_loop,
                    ) as get_running_loop:
                        resp = client.get("/analyze")
        assert resp.status_code == 200
        get_running_loop.assert_called()


class TestForecastEndpoints:
    def test_forecast_product(self, client):
        with patch.dict(os.environ, {"API_KEY": ""}, clear=False):
            with patch("api.forecast_demand", return_value=42):
                with patch("api.Database") as mock_db_cls:
                    mock_db_cls.return_value.__enter__ = MagicMock(
                        return_value=MagicMock()
                    )
                    mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)
                    resp = client.get("/forecast/SKU-99?days=14")
        assert resp.status_code == 200
        body = resp.json()
        assert body["product_id"] == "SKU-99"
        assert body["projected_units"] == 42
        assert body["forecast_days"] == 14

    def test_top_products(self, client):
        with patch.dict(os.environ, {"API_KEY": ""}, clear=False):
            with patch(
                "api.get_top_products",
                return_value=[
                    {
                        "product_id": "A",
                        "product_name": "Prod A",
                        "total_qty": 50,
                    }
                ],
            ):
                with patch("api.Database") as mock_db_cls:
                    mock_db_cls.return_value.__enter__ = MagicMock(
                        return_value=MagicMock()
                    )
                    mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)
                    resp = client.get("/forecast/top-products?limit=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["product_id"] == "A"
