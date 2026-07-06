"""Tests for SmartVannaFlaskApp chart cache routes."""

import json
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from business_analyzer.ai.flask_app import SmartVannaFlaskApp
from business_analyzer.ai.formatting import format_dataframe


class _StubVanna:
    run_sql_is_set = True
    provider = object()

    def __init__(self):
        self._last_result_df = None

    def run_sql(self, sql: str):
        raw = pd.DataFrame(
            {
                "Año": [2026, 2025],
                "Mes": [7, 10],
                "Nombre_Mes": ["July", "October"],
                "Ventas_Totales": [3_182_633.0, 168_369_055.0],
            }
        )
        self._last_result_df = raw
        return format_dataframe(raw)

    def should_generate_chart(self, df: pd.DataFrame) -> bool:
        return not df.empty

    def generate_plotly_code(self, question, sql, df_metadata, **kwargs):
        return "smart-code"

    def get_plotly_figure(self, plotly_code, df, dark_mode=False, **kwargs):
        from business_analyzer.ai.charts import build_smart_figure

        fig = build_smart_figure(df, question=kwargs.get("question"))
        assert fig is not None
        assert max(fig.data[0].y) > 100_000_000
        return fig


@pytest.fixture
def flask_client():
    app = SmartVannaFlaskApp(_StubVanna(), chart=True)
    app.flask_app.config["TESTING"] = True
    with app.flask_app.test_client() as client:
        yield client, app


class TestSmartVannaFlaskApp:
    def test_run_sql_caches_df_raw(self, flask_client):
        client, app = flask_client
        cache_id = app.cache.generate_id(question="ventas cemex")
        app.cache.set(id=cache_id, field="sql", value="SELECT 1")

        response = client.get(f"/api/v0/run_sql?id={cache_id}")
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["should_generate_chart"] is True

        df_raw = app.cache.get(id=cache_id, field="df_raw")
        assert df_raw is not None
        assert float(df_raw["Ventas_Totales"].iloc[0]) > 3_000_000

    def test_generate_plotly_uses_cached_df_raw(self, flask_client):
        client, app = flask_client
        cache_id = app.cache.generate_id(question="ventas cemex")
        app.cache.set(id=cache_id, field="sql", value="SELECT 1")
        client.get(f"/api/v0/run_sql?id={cache_id}")

        app.cache.set(id=cache_id, field="question", value="ventas cemex mes a mes")
        app.vn._last_result_df = None

        response = client.get(f"/api/v0/generate_plotly_figure?id={cache_id}")
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["type"] == "plotly_figure"
        fig = json.loads(payload["fig"])
        assert fig["data"]
        assert max(fig["data"][0]["y"]) > 100_000_000
        plotly_code = app.cache.get(id=cache_id, field="plotly_code")
        assert plotly_code and "px.bar" in plotly_code
        assert "bdata" not in payload["fig"]
