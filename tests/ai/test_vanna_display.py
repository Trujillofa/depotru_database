"""Tests for Vanna web UI display formatting."""

import pandas as pd
import pytest

from business_analyzer.ai.formatting import format_dataframe


class TestEnhancedVannaDisplay:
    @pytest.fixture
    def enhanced_vanna(self, monkeypatch):
        from vanna.legacy.chromadb.chromadb_vector import ChromaDB_VectorStore
        from vanna.legacy.openai import OpenAI_Chat

        from business_analyzer.ai import base
        from vanna_grok import EnhancedAIVanna

        monkeypatch.setattr(
            ChromaDB_VectorStore, "__init__", lambda self, config=None: None
        )
        monkeypatch.setattr(
            OpenAI_Chat, "__init__", lambda self, client=None, config=None: None
        )
        monkeypatch.setattr(
            base,
            "create_ai_client",
            lambda provider=None: (object(), {"model": "test"}, "openai"),
        )

        return EnhancedAIVanna()

    def test_run_sql_returns_formatted_display(self, enhanced_vanna, monkeypatch):
        raw = pd.DataFrame(
            {
                "Producto": ["CEMENTO"],
                "Facturacion_Total": [4993131],
                "Unidades_Vendidas": [149835],
            }
        )

        monkeypatch.setattr(
            enhanced_vanna.__class__.__bases__[0],
            "run_sql",
            lambda self, sql, **kwargs: raw,
        )

        display = enhanced_vanna.run_sql("SELECT 1")
        assert "$4.993.131" in display.iloc[0]["Facturacion_Total"]
        assert enhanced_vanna._last_result_df.iloc[0]["Facturacion_Total"] == 4993131

    def test_should_generate_chart_uses_raw_df(self, enhanced_vanna):
        enhanced_vanna._last_result_df = pd.DataFrame(
            {"Producto": ["A", "B"], "Facturacion_Total": [1000, 2000]}
        )
        formatted = format_dataframe(enhanced_vanna._last_result_df)
        assert enhanced_vanna.should_generate_chart(formatted) is True
