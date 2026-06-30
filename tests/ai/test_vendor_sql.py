"""Tests for multi-vendor SQL templates and run_sql retry logic."""

from unittest.mock import MagicMock, patch

import pytest

from business_analyzer.ai.base import AIVanna


class TestMultiVendorSalesTemplate:
    QUESTION = "Ventas de productos PAVCO o EUROCERAMICA"

    def test_detects_multi_vendor_sales_question(self):
        assert AIVanna._is_multi_vendor_sales_question(self.QUESTION)

    def test_extracts_pavco_and_euroceramica(self):
        brands = AIVanna._extract_vendor_brands(self.QUESTION)
        assert "PAVCO" in brands
        assert "EUROCERAMICA" in brands

    def test_template_searches_master_data_and_product_name(self):
        brands = AIVanna._extract_vendor_brands(self.QUESTION)
        sql = AIVanna._multi_vendor_sales_sql_template(brands)
        lower = sql.lower()
        assert "productos_adicional" in lower
        assert "articulosnombre" in lower
        assert "pavco" in lower
        assert "euroceramica" in lower
        assert "marca_proveedor" in lower

    def test_generate_sql_upgrades_stale_cache(self):
        stale_sql = (
            "SELECT proveedor, SUM(TotalMasIva) AS Ventas_Totales "
            "FROM banco_datos WHERE proveedor IN ('PAVCO', 'EUROCERAMICA') "
            "GROUP BY proveedor"
        )
        cache = MagicMock()
        cache.get.return_value = stale_sql

        vn = object.__new__(AIVanna)
        vn._query_cache = cache

        with patch.object(
            AIVanna, "_is_multi_vendor_sales_question", return_value=True
        ):
            with patch.object(
                AIVanna,
                "_extract_vendor_brands",
                return_value=["PAVCO", "EUROCERAMICA"],
            ):
                result = AIVanna.generate_sql(vn, self.QUESTION)

        assert "productos_adicional" in result.lower()
        cache.set.assert_called_with(self.QUESTION, result)


class TestRunSqlRetry:
    def test_retries_on_transient_connection_error(self, monkeypatch):
        calls = {"count": 0}

        class FakeDb:
            def is_connected(self):
                return True

            def connect(self):
                return None

            def execute_query(self, _sql):
                calls["count"] += 1
                if calls["count"] == 1:
                    raise Exception(
                        "08S01 TCP Provider: Error code 0x274C (10060) SQLExecDirectW"
                    )
                return [{"ping": 1}]

        fake_db = FakeDb()
        monkeypatch.setattr(
            "business_analyzer.core.db_factory.get_database",
            lambda reuse=True: fake_db,
        )
        monkeypatch.setattr(
            "business_analyzer.core.db_factory.release_thread_connections",
            lambda: None,
        )
        monkeypatch.setenv("DB_QUERY_RETRIES", "2")

        vn = object.__new__(AIVanna)
        df = AIVanna.run_sql(vn, "SELECT 1 AS ping")
        assert calls["count"] == 2
        assert not df.empty
        assert df.iloc[0]["ping"] == 1
