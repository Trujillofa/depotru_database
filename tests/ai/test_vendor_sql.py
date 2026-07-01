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
        assert "collate database_default" in lower
        assert "articulosnombre" in lower
        assert "pavco" in lower
        assert "euroceramica" in lower
        assert "marca_proveedor" in lower

    def test_generate_sql_upgrades_stale_cache(self):
        stale_sql = (
            "SELECT proveedor FROM banco_datos bd "
            "LEFT JOIN productos_adicional pa ON bd.ArticulosCodigo = pa.producto_codigo "
            "WHERE proveedor IN ('EUROCERAMICA')"
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


class TestTopCustomersTemplate:
    QUESTION = "Top 10 clientes con mayor facturación"

    def test_detects_top_customers_question(self):
        assert AIVanna._is_top_customers_question(self.QUESTION)

    def test_template_normalizes_names_and_includes_margin(self):
        sql = AIVanna._top_customers_sql_template(self.QUESTION)
        lower = sql.lower()
        assert "replace(replace" in lower
        assert "ganancia_neta" in lower
        assert "margen_promedio" in lower
        assert "group by" in lower
        assert "top 10" in lower

    def test_year_filter_for_current_year(self):
        sql = AIVanna._top_customers_sql_template(
            "Top 5 clientes con mayor facturación este año"
        )
        assert "year(fecha) = year(getdate())" in sql.lower()
        assert "top 5" in sql.lower()

    def test_generate_sql_upgrades_stale_top_customers_cache(self):
        stale_sql = """
            SELECT TOP 10 TercerosNombres AS Cliente,
                SUM(TotalMasIva) AS Facturacion_Total
            FROM banco_datos
            GROUP BY TercerosNombres
        """
        cache = MagicMock()
        cache.get.return_value = stale_sql

        vn = object.__new__(AIVanna)
        vn._query_cache = cache

        with patch.object(AIVanna, "_is_top_customers_question", return_value=True):
            result = AIVanna.generate_sql(vn, self.QUESTION)

        assert "ganancia_neta" in result.lower()
        assert "replace(replace" in result.lower()
        cache.set.assert_called_with(self.QUESTION, result)


class TestVendedorPerformanceTemplate:
    QUESTION = "Vendedores con mejor desempeño este mes"

    def test_detects_vendedor_performance_question(self):
        assert AIVanna._is_vendedor_performance_question(self.QUESTION)

    def test_excludes_named_vendor_drilldown(self):
        assert not AIVanna._is_vendedor_performance_question(
            "Ventas del vendedor CARLOS EFREY PASCUAS"
        )

    def test_template_unifies_vendor_and_uses_calendar_month(self):
        sql = AIVanna._vendedor_performance_sql_template(self.QUESTION)
        lower = sql.lower()
        assert "coalesce(" in lower
        assert "vendedorasignado" in lower
        assert "month(fecha) = month(getdate())" in lower
        assert "group by vendedorfactura, vendedor_codigo" not in lower
        assert "total_vendido" in lower
        assert "ganancia_generada" in lower

    def test_mes_pasado_filter(self):
        sql = AIVanna._vendedor_performance_sql_template(
            "Top 5 vendedores con mejor desempeño el mes pasado"
        )
        assert "dateadd(month, -1, getdate())" in sql.lower()
        assert "top 5" in sql.lower()

    def test_generate_sql_upgrades_stale_vendedor_cache(self):
        stale_sql = """
            SELECT TOP 10 COALESCE(VendedorFactura, vendedor_codigo) AS Vendedor,
                COUNT(*) AS Ventas_Este_Mes, SUM(TotalMasIva) AS Total_Vendido
            FROM banco_datos
            WHERE Fecha >= DATEADD(MONTH, -1, GETDATE())
            GROUP BY VendedorFactura, vendedor_codigo
            ORDER BY Total_Vendido DESC
        """
        cache = MagicMock()
        cache.get.return_value = stale_sql

        vn = object.__new__(AIVanna)
        vn._query_cache = cache

        with patch.object(
            AIVanna, "_is_vendedor_performance_question", return_value=True
        ):
            result = AIVanna.generate_sql(vn, self.QUESTION)

        assert "month(fecha) = month(getdate())" in result.lower()
        assert "group by vendedorfactura, vendedor_codigo" not in result.lower()
        cache.set.assert_called_with(self.QUESTION, result)


class TestDocumentTypeSalesTemplate:
    QUESTION = "Comparación de ventas por tipo de documento"

    def test_detects_document_type_question(self):
        assert AIVanna._is_document_type_sales_question(self.QUESTION)

    def test_template_uses_totalmasiva_and_sales_documents_only(self):
        sql = AIVanna._document_type_sales_sql_template(self.QUESTION)
        lower = sql.lower()
        assert "totalmasiva" in lower
        assert "documentoscodigo in ('fed', 'fef', 'fet')" in lower
        assert "ventatotal" not in lower
        assert "ganancia_total" in lower
        assert "descripcion" in lower

    def test_generate_sql_upgrades_stale_document_cache(self):
        stale_sql = """
            SELECT DocumentosCodigo, SUM(VentaTotal) AS Ventas_Total
            FROM banco_datos
            WHERE DocumentosCodigo NOT IN ('Y', 'AS')
            GROUP BY DocumentosCodigo
        """
        cache = MagicMock()
        cache.get.return_value = stale_sql

        vn = object.__new__(AIVanna)
        vn._query_cache = cache

        with patch.object(
            AIVanna, "_is_document_type_sales_question", return_value=True
        ):
            result = AIVanna.generate_sql(vn, self.QUESTION)

        assert "totalmasiva" in result.lower()
        assert "documentoscodigo in ('fed', 'fef', 'fet')" in result.lower()
        cache.set.assert_called_with(self.QUESTION, result)


class TestDailyAverageByMonthTemplate:
    QUESTION = "Promedio de ventas diarias por mes"

    def test_detects_daily_average_question(self):
        assert AIVanna._is_daily_average_by_month_question(self.QUESTION)

    def test_template_uses_totalmasiva_and_daily_subquery(self):
        sql = AIVanna._daily_average_by_month_sql_template()
        lower = sql.lower()
        assert "sum(totalmasiva)" in lower
        assert "group by fecha" in lower
        assert "promedio_ventas_diarias" in lower

    def test_generate_sql_upgrades_stale_daily_average_cache(self):
        stale_sql = """
            SELECT AVG(Ventas_Diarias) FROM (
                SELECT Fecha, SUM(Total) AS Ventas_Diarias
                FROM banco_datos GROUP BY Fecha
            ) x
        """
        cache = MagicMock()
        cache.get.return_value = stale_sql

        vn = object.__new__(AIVanna)
        vn._query_cache = cache

        with patch.object(
            AIVanna, "_is_daily_average_by_month_question", return_value=True
        ):
            result = AIVanna.generate_sql(vn, self.QUESTION)

        assert "sum(totalmasiva)" in result.lower()
        cache.set.assert_called_with(self.QUESTION, result)


class TestBranchStoreSalesTemplate:
    SIKA_CENTER_QUESTION = "Ventas de la sede Sika Center por mes"
    SIKA_BRAND_QUESTION = "Ventas de productos SIKA"
    CALLE5_QUESTION = "Ventas de Calle 5 este año"

    def test_detects_sika_center_branch_question(self):
        assert AIVanna._is_branch_store_sales_question(self.SIKA_CENTER_QUESTION)

    def test_sika_center_not_multi_vendor(self):
        assert not AIVanna._is_multi_vendor_sales_question(self.SIKA_CENTER_QUESTION)

    def test_sika_brand_still_multi_vendor(self):
        assert AIVanna._is_multi_vendor_sales_question(self.SIKA_BRAND_QUESTION)

    def test_sika_center_template_uses_fef_document_code(self):
        sql = AIVanna._branch_store_sql_template(self.SIKA_CENTER_QUESTION)
        lower = sql.lower()
        assert "documentoscodigo = 'fef'" in lower
        assert "marca_proveedor" not in lower
        assert "productos_adicional" not in lower
        assert "año desc, mes desc" in lower

    def test_calle5_template_uses_fet_document_code(self):
        sql = AIVanna._branch_store_sql_template(self.CALLE5_QUESTION)
        lower = sql.lower()
        assert "documentoscodigo = 'fet'" in lower
        assert "year(fecha) = year(getdate())" in lower

    def test_generate_sql_upgrades_stale_sika_center_cache(self):
        stale_sql = """
            SELECT Marca_Proveedor, SUM(TotalMasIva) AS Ventas_Totales
            FROM (
                SELECT bd.TotalMasIva, pa.proveedor_descripcion AS Marca_Proveedor
                FROM banco_datos bd
                LEFT JOIN productos_adicional pa
                    ON bd.ArticulosCodigo = pa.producto_codigo
                WHERE UPPER(bd.ArticulosNombre) LIKE '%SIKA%'
            ) x
            GROUP BY Marca_Proveedor
        """
        cache = MagicMock()
        cache.get.return_value = stale_sql

        vn = object.__new__(AIVanna)
        vn._query_cache = cache

        result = AIVanna.generate_sql(vn, self.SIKA_CENTER_QUESTION)

        assert "documentoscodigo = 'fef'" in result.lower()
        assert "marca_proveedor" not in result.lower()
        cache.set.assert_called_with(self.SIKA_CENTER_QUESTION, result)


class TestLastNDaysSalesTemplate:
    QUESTION = "Ventas de los últimos 30 días"

    def test_detects_last_n_days_question(self):
        assert AIVanna._is_last_n_days_sales_question(self.QUESTION)

    def test_extracts_days_window(self):
        assert AIVanna._extract_days_window(self.QUESTION) == 30
        assert AIVanna._extract_days_window("Ventas últimos 7 días") == 7

    def test_template_uses_totalmasiva_and_groups_by_fecha(self):
        sql = AIVanna._last_n_days_sales_sql_template(self.QUESTION)
        lower = sql.lower()
        assert "sum(totalmasiva)" in lower
        assert "ventas_diarias" in lower
        assert "group by fecha" in lower
        assert "dateadd(day, -30" in lower

    def test_generate_sql_upgrades_stale_last_days_cache(self):
        stale_sql = """
            SELECT Fecha, COUNT(*) AS Numero_Transacciones
            FROM tabla
            GROUP BY Fecha
        """
        cache = MagicMock()
        cache.get.return_value = stale_sql

        vn = object.__new__(AIVanna)
        vn._query_cache = cache

        result = AIVanna.generate_sql(vn, self.QUESTION)

        assert "sum(totalmasiva)" in result.lower()
        assert "ventas_diarias" in result.lower()
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
