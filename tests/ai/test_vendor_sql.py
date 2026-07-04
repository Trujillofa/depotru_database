"""Tests for multi-vendor SQL templates and run_sql retry logic."""

from unittest.mock import MagicMock, patch

import pytest

from business_analyzer.ai.base import AIVanna

PINTUCO_UI_BAD_SQL = """
SELECT
    Marca_Proveedor,
    SUM(TotalMasIva) AS Ventas_Totales,
    COUNT(*) AS Numero_Transacciones,
    SUM(TotalSinIva - ValorCosto) AS Ganancia
FROM (
    SELECT
        bd.TotalMasIva,
        bd.TotalSinIva,
        bd.ValorCosto,
        CASE
            WHEN UPPER(LTRIM(RTRIM(COALESCE(bd.proveedor COLLATE DATABASE_DEFAULT, pa.proveedor_descripcion COLLATE DATABASE_DEFAULT, '')))) IN ('PINTUCO')
                THEN UPPER(LTRIM(RTRIM(COALESCE(bd.proveedor COLLATE DATABASE_DEFAULT, pa.proveedor_descripcion COLLATE DATABASE_DEFAULT, ''))))
            WHEN UPPER(LTRIM(RTRIM(COALESCE(bd.marca COLLATE DATABASE_DEFAULT, pa.producto_marca COLLATE DATABASE_DEFAULT, '')))) IN ('PINTUCO')
                THEN UPPER(LTRIM(RTRIM(COALESCE(bd.marca COLLATE DATABASE_DEFAULT, pa.producto_marca COLLATE DATABASE_DEFAULT, ''))))
            WHEN UPPER(bd.ArticulosNombre COLLATE DATABASE_DEFAULT) LIKE '%PINTUCO%' THEN 'PINTUCO'
            ELSE NULL
        END AS Marca_Proveedor
    FROM banco_datos bd
    LEFT JOIN productos_adicional pa
        ON bd.ArticulosCodigo COLLATE DATABASE_DEFAULT
         = pa.producto_codigo COLLATE DATABASE_DEFAULT
    WHERE bd.DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
) AS ventas_marca
WHERE Marca_Proveedor IS NOT NULL
GROUP BY Marca_Proveedor
ORDER BY Ventas_Totales DESC
""".strip()


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

    def test_pintuco_template_prefilters_before_aggregation(self):
        sql = AIVanna._multi_vendor_sales_sql_template(["PINTUCO"])
        lower = sql.lower()
        assert "like '%pintuco%'" in lower
        assert "documentoscodigo not in ('xy', 'as', 'ts', 'yx', 'isc')" in lower
        assert lower.index("and (") < lower.index(") as ventas_marca")

    def test_generate_sql_upgrades_stale_pintuco_cache_missing_prefilter(self):
        stale_sql = """
SELECT Marca_Proveedor, SUM(TotalMasIva) AS Ventas_Totales
FROM (
    SELECT bd.TotalMasIva,
           CASE WHEN bd.proveedor = 'PINTUCO' THEN 'PINTUCO' END AS Marca_Proveedor
    FROM banco_datos bd
    LEFT JOIN productos_adicional pa
        ON bd.ArticulosCodigo COLLATE DATABASE_DEFAULT
         = pa.producto_codigo COLLATE DATABASE_DEFAULT
    WHERE bd.DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
) AS ventas_marca
WHERE Marca_Proveedor IS NOT NULL
GROUP BY Marca_Proveedor
        """.strip()
        cache = MagicMock()
        cache.get.return_value = stale_sql
        vn = object.__new__(AIVanna)
        vn._query_cache = cache

        with patch.object(
            AIVanna, "_is_multi_vendor_sales_question", return_value=True
        ):
            result = AIVanna.generate_sql(vn, "ventas de pintuco")

        assert "like '%pintuco%'" in result.lower()
        assert AIVanna._multi_vendor_sql_has_where_prefilter(result, ["PINTUCO"])
        cache.set.assert_called()

    def test_like_in_case_only_is_not_where_prefilter(self):
        case_only_sql = """
SELECT Marca_Proveedor, SUM(TotalMasIva) AS Ventas_Totales
FROM (
    SELECT bd.TotalMasIva,
           CASE
               WHEN UPPER(bd.ArticulosNombre COLLATE DATABASE_DEFAULT) LIKE '%PINTUCO%'
                   THEN 'PINTUCO'
           END AS Marca_Proveedor
    FROM banco_datos bd
    LEFT JOIN productos_adicional pa
        ON bd.ArticulosCodigo COLLATE DATABASE_DEFAULT
         = pa.producto_codigo COLLATE DATABASE_DEFAULT
    WHERE bd.DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
) AS ventas_marca
WHERE Marca_Proveedor IS NOT NULL
GROUP BY Marca_Proveedor
        """.strip()
        assert not AIVanna._multi_vendor_sql_has_where_prefilter(
            case_only_sql, ["PINTUCO"]
        )
        prepared = AIVanna._prepare_sql_for_execution(case_only_sql)
        assert AIVanna._multi_vendor_sql_has_where_prefilter(prepared, ["PINTUCO"])

    def test_generate_sql_upgrades_cache_when_like_only_in_case(self):
        case_only_sql = """
SELECT Marca_Proveedor, SUM(TotalMasIva) AS Ventas_Totales
FROM (
    SELECT bd.TotalMasIva,
           CASE
               WHEN UPPER(bd.ArticulosNombre COLLATE DATABASE_DEFAULT) LIKE '%PINTUCO%'
                   THEN 'PINTUCO'
           END AS Marca_Proveedor
    FROM banco_datos bd
    LEFT JOIN productos_adicional pa
        ON bd.ArticulosCodigo COLLATE DATABASE_DEFAULT
         = pa.producto_codigo COLLATE DATABASE_DEFAULT
    WHERE bd.DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
) AS ventas_marca
WHERE Marca_Proveedor IS NOT NULL
GROUP BY Marca_Proveedor
        """.strip()
        cache = MagicMock()
        cache.get.return_value = case_only_sql
        vn = object.__new__(AIVanna)
        vn._query_cache = cache

        with patch.object(
            AIVanna, "_is_multi_vendor_sales_question", return_value=True
        ):
            result = AIVanna.generate_sql(vn, "ventas de pintuco")

        assert AIVanna._multi_vendor_sql_has_where_prefilter(result, ["PINTUCO"])
        cache.set.assert_called()

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


class TestPrepareSqlForExecution:
    def test_ui_bad_sql_gets_inner_prefilter_via_prepare(self):
        prepared = AIVanna._prepare_sql_for_execution(PINTUCO_UI_BAD_SQL)
        lower = prepared.lower()
        assert AIVanna._multi_vendor_sql_has_where_prefilter(prepared, ["PINTUCO"])
        assert lower.index("and (") < lower.index(") as ventas_marca")

    def test_prepare_survives_unqualified_doc_filter_normalization(self):
        sql = PINTUCO_UI_BAD_SQL.replace("bd.DocumentosCodigo", "DocumentosCodigo")
        prepared = AIVanna._prepare_sql_for_execution(sql)
        assert AIVanna._multi_vendor_sql_has_where_prefilter(prepared, ["PINTUCO"])
        assert "bd.documentoscodigo" in prepared.lower()

    def test_prepare_adds_inner_doc_filter_not_outer_group_by(self):
        sql = """
SELECT Marca_Proveedor, SUM(TotalMasIva) AS Ventas_Totales
FROM (
    SELECT bd.TotalMasIva,
           CASE WHEN UPPER(bd.ArticulosNombre) LIKE '%PINTUCO%' THEN 'PINTUCO' END AS Marca_Proveedor
    FROM banco_datos bd
    LEFT JOIN productos_adicional pa
        ON bd.ArticulosCodigo COLLATE DATABASE_DEFAULT
         = pa.producto_codigo COLLATE DATABASE_DEFAULT
) AS ventas_marca
WHERE Marca_Proveedor IS NOT NULL
GROUP BY Marca_Proveedor
        """.strip()
        prepared = AIVanna._prepare_sql_for_execution(sql)
        lower = prepared.lower()
        assert "documentoscodigo" in lower
        assert lower.index("documentoscodigo") < lower.index(") as ventas_marca")
        assert "group by marca_proveedor" in lower
        assert "group by marca_proveedor where" not in lower

    def test_run_sql_pipeline_injects_prefilter_for_ui_bad_sql(self, monkeypatch):
        captured = {"sql": None}

        class FakeDb:
            def is_connected(self):
                return True

            def connect(self):
                return None

            def execute_query(self, query):
                captured["sql"] = query
                return [
                    {
                        "Marca_Proveedor": "PINTUCO",
                        "Ventas_Totales": 7_292_373_976,
                    }
                ]

        monkeypatch.setattr(
            "business_analyzer.core.db_factory.get_database",
            lambda reuse=True: FakeDb(),
        )
        monkeypatch.setattr(
            "business_analyzer.core.db_factory.release_thread_connections",
            lambda: None,
        )

        vn = object.__new__(AIVanna)
        AIVanna.run_sql(vn, PINTUCO_UI_BAD_SQL)

        assert captured["sql"] is not None
        assert AIVanna._multi_vendor_sql_has_where_prefilter(
            captured["sql"], ["PINTUCO"]
        )

    def test_run_sql_rebinds_sqlalchemy_before_execute(self, monkeypatch):
        captured = {"sql": None, "rebound": False}

        class FakeDb:
            def is_connected(self):
                return True

            def connect(self):
                return None

            def execute_query(self, query):
                captured["sql"] = query
                return [{"ping": 1}]

        def run_sql_mssql(_sql):
            raise AssertionError("SQLAlchemy path should not execute")

        run_sql_mssql.__qualname__ = "VannaBase.connect_to_mssql.<locals>.run_sql_mssql"

        monkeypatch.setattr(
            "business_analyzer.core.db_factory.get_database",
            lambda reuse=True: FakeDb(),
        )
        monkeypatch.setattr(
            "business_analyzer.core.db_factory.release_thread_connections",
            lambda: None,
        )

        vn = object.__new__(AIVanna)
        vn.run_sql = run_sql_mssql
        AIVanna.run_sql(vn, PINTUCO_UI_BAD_SQL)

        assert captured["sql"] is not None
        assert vn.run_sql.__func__ is AIVanna.run_sql


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


class TestBranchLeastSoldProducts:
    QUESTION = "dame una lista de los productos menos vendidos en el sika center"

    def test_detects_branch_product_ranking(self):
        assert AIVanna._is_branch_product_ranking_question(self.QUESTION)
        assert AIVanna._is_product_ranking_question(self.QUESTION)
        assert not AIVanna._is_multi_vendor_sales_question(self.QUESTION)
        assert AIVanna._extract_vendor_brands(self.QUESTION) == []

    def test_template_uses_fef_articulosnombre_and_asc(self):
        sql = AIVanna._branch_product_ranking_sql_template(self.QUESTION)
        lower = sql.lower()
        assert "documentoscodigo = 'fef'" in lower
        assert "group by articulosnombre" in lower
        assert "order by ventas asc" in lower
        assert "marca_proveedor" not in lower
        assert "productos_adicional" not in lower

    def test_generate_sql_returns_branch_product_ranking(self):
        cache = MagicMock()
        cache.get.return_value = None

        vn = object.__new__(AIVanna)
        vn._query_cache = cache

        result = AIVanna.generate_sql(vn, self.QUESTION)

        lower = result.lower()
        assert "documentoscodigo = 'fef'" in lower
        assert "group by articulosnombre" in lower
        assert "order by ventas asc" in lower
        assert "marca_proveedor" not in lower
        cache.set.assert_called_with(self.QUESTION, result)

    def test_generate_sql_upgrades_stale_brand_rollup_cache(self):
        stale_sql = """
            SELECT Marca_Proveedor, SUM(TotalMasIva) AS Ventas_Totales
            FROM (
                SELECT bd.TotalMasIva,
                    CASE WHEN UPPER(bd.ArticulosNombre) LIKE '%SIKA%' THEN 'SIKA' END AS Marca_Proveedor
                FROM banco_datos bd
                LEFT JOIN productos_adicional pa
                    ON bd.ArticulosCodigo = pa.producto_codigo
                WHERE bd.DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')
            ) x
            GROUP BY Marca_Proveedor
            ORDER BY Ventas_Totales DESC
        """
        cache = MagicMock()
        cache.get.return_value = stale_sql

        vn = object.__new__(AIVanna)
        vn._query_cache = cache

        result = AIVanna.generate_sql(vn, self.QUESTION)

        lower = result.lower()
        assert "documentoscodigo = 'fef'" in lower
        assert "group by articulosnombre" in lower
        assert "marca_proveedor" not in lower
        cache.set.assert_called_with(self.QUESTION, result)

    def test_resolve_top_n_followup_merges_prior_question(self):
        prior = self.QUESTION
        resolved = AIVanna.resolve_question_with_context("top 100", prior)
        assert "sika center" in resolved.lower()
        assert "top 100" in resolved.lower()

    def test_top_n_followup_uses_prior_branch_template(self):
        from vanna_grok import EnhancedAIVanna

        cache = MagicMock()
        cache.get.return_value = None

        vn = object.__new__(EnhancedAIVanna)
        vn._query_cache = cache
        vn._last_question = self.QUESTION

        result = EnhancedAIVanna.generate_sql(vn, "top 100")

        lower = result.lower()
        assert "top 100" in lower
        assert "documentoscodigo = 'fef'" in lower
        assert "order by ventas asc" in lower


class TestBareTopNFollowup:
    def test_bare_top_n_without_context_uses_generic_products(self):
        resolved = AIVanna.resolve_question_with_context("top 100", None)
        assert "productos" in resolved.lower()

        cache = MagicMock()
        cache.get.return_value = None
        vn = object.__new__(AIVanna)
        vn._query_cache = cache
        result = AIVanna.generate_sql(vn, resolved)

        assert "top 100" in result.lower()
        assert "group by articulosnombre" in result.lower()


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


class TestBrandTopProductsTemplate:
    SIKA_QUESTION = "Productos de SIKA más vendidos"
    HIERRO_QUESTION = "Productos más vendidos de HIERRO"
    ACESCO_QUESTION = "Productos ACESCO más vendidos este año"

    def test_detects_sika_product_ranking(self):
        assert AIVanna._is_brand_top_products_question(self.SIKA_QUESTION)
        assert not AIVanna._is_multi_vendor_sales_question(self.SIKA_QUESTION)

    def test_ventas_de_productos_sika_stays_multi_vendor(self):
        assert not AIVanna._is_brand_top_products_question("Ventas de productos SIKA")
        assert AIVanna._is_multi_vendor_sales_question("Ventas de productos SIKA")

    def test_sika_template_groups_by_product(self):
        sql = AIVanna._brand_top_products_sql_template(self.SIKA_QUESTION)
        lower = sql.lower()
        assert "top 10" in lower
        assert "group by articulosnombre" in lower
        assert "like '%sika%'" in lower
        assert "marca_proveedor" not in lower

    def test_hierro_template_filters_category(self):
        sql = AIVanna._brand_top_products_sql_template(self.HIERRO_QUESTION)
        lower = sql.lower()
        assert "categoria" in lower
        assert "'hierro'" in lower
        assert "group by articulosnombre" in lower

    def test_acesco_template_includes_year_filter(self):
        sql = AIVanna._brand_top_products_sql_template(self.ACESCO_QUESTION)
        assert "year(fecha) = year(getdate())" in sql.lower()

    def test_generate_sql_upgrades_stale_brand_rollup_cache(self):
        stale_sql = """
            SELECT Marca_Proveedor, SUM(TotalMasIva) AS Ventas_Totales
            FROM banco_datos
            GROUP BY Marca_Proveedor
        """
        cache = MagicMock()
        cache.get.return_value = stale_sql

        vn = object.__new__(AIVanna)
        vn._query_cache = cache

        result = AIVanna.generate_sql(vn, self.SIKA_QUESTION)

        assert "group by articulosnombre" in result.lower()
        assert "marca_proveedor" not in result.lower()
        cache.set.assert_called_with(self.SIKA_QUESTION, result)


class TestGenericTopProductsTemplate:
    QUESTION = "Top 10 productos más vendidos por facturación este año"

    def test_detects_generic_product_ranking(self):
        assert AIVanna._is_generic_top_products_question(self.QUESTION)
        assert not AIVanna._is_brand_top_products_question(self.QUESTION)

    def test_template_uses_facturacion_and_year(self):
        sql = AIVanna._generic_top_products_sql_template(self.QUESTION)
        lower = sql.lower()
        assert "top 10" in lower
        assert "facturacion_total" in lower
        assert "year(fecha) = year(getdate())" in lower
        assert "group by articulosnombre" in lower


class TestGricolBrand:
    def test_extracts_gricol_from_ventas_gricol(self):
        assert "GRICOL" in AIVanna._extract_vendor_brands("ventas gricol")

    def test_ventas_gricol_uses_multi_vendor_template(self):
        assert AIVanna._is_multi_vendor_sales_question("ventas gricol")
        sql = AIVanna._multi_vendor_sales_sql_template(["GRICOL"])
        lower = sql.lower()
        assert "gricol" in lower
        assert "productos_adicional" in lower
        assert "ventas_totales" in lower
        assert "not like '%agricol%'" in lower

    def test_brand_match_filter_avoids_agricol_false_positive(self):
        clause = AIVanna._brand_match_filter("GRICOL").lower()
        assert "not like '%agricol%'" in clause


class TestBrandAliasesAndMonthly:
    def test_ska_alias_maps_to_sika(self):
        assert "SIKA" in AIVanna._extract_vendor_brands("ventas de SKA")

    def test_sra_alias_maps_to_sika(self):
        assert "SIKA" in AIVanna._extract_vendor_brands("ventas de SRA")

    def test_cermex_alias_maps_to_cemex(self):
        assert "CEMEX" in AIVanna._extract_vendor_brands("ventas de cermex")
        assert "CERMEX" not in AIVanna._extract_vendor_brands("ventas de cermex")

    def test_cermex_monthly_template(self):
        q = "ventas de cermex mes a mes"
        assert AIVanna._is_brand_monthly_sales_question(q)
        sql = AIVanna._brand_monthly_sales_sql_template(q)
        assert "cemex" in sql.lower()
        assert "cermex" not in sql.lower()

    def test_ska_uses_multi_vendor_template(self):
        sql = AIVanna._multi_vendor_sales_sql_template(["SIKA"])
        assert "sika" in sql.lower()
        assert "marca_proveedor" in sql.lower()

    def test_sika_monthly_template(self):
        q = "Cuáles son las ventas de SIKA al mes?"
        assert AIVanna._is_brand_monthly_sales_question(q)
        sql = AIVanna._brand_monthly_sales_sql_template(q)
        lower = sql.lower()
        assert "group by year(fecha)" in lower
        assert "like '%sika%'" in lower
        assert "totalmasiva" in lower

    def test_repair_totalactiva_hallucination(self):
        sql = "SELECT SUM(TotalActiva) FROM banco_datos WHERE DocumentoCodigo = 'FEF'"
        fixed = AIVanna._repair_common_sql_hallucinations(sql)
        assert "TotalMasIva" in fixed
        assert "DocumentosCodigo" in fixed


class TestYearMonthComparison:
    QUESTION = "Ventas por mes comparando años"

    def test_detects_comparison_question(self):
        assert AIVanna._is_year_month_comparison_question(self.QUESTION)

    def test_template_uses_pivot_columns(self):
        sql = AIVanna._year_month_comparison_sql_template(self.QUESTION)
        lower = sql.lower()
        assert "ventas_anio_actual" in lower
        assert "ventas_anio_anterior" in lower
        assert "totalmasiva" in lower
        assert "group by month(fecha)" in lower


class TestConnectToMssql:
    def test_connect_to_mssql_binds_project_run_sql(self):
        vn = object.__new__(AIVanna)
        AIVanna.connect_to_mssql(vn)
        assert vn.run_sql_is_set
        assert vn.dialect == "T-SQL / Microsoft SQL Server"
        assert vn.run_sql.__func__ is AIVanna.run_sql

    def test_connect_to_mssql_odbc_uses_project_run_sql(self, monkeypatch):
        vn = object.__new__(AIVanna)
        monkeypatch.setattr(
            AIVanna,
            "run_sql",
            lambda self, sql, **kwargs: __import__("pandas").DataFrame([{"ping": 1}]),
        )
        AIVanna.connect_to_mssql_odbc(vn)
        assert vn.run_sql_is_set
        assert vn.run_sql.__self__ is vn


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

    def test_retries_on_query_error_wrapped_0x68(self, monkeypatch):
        from business_analyzer.core.database import QueryError

        calls = {"count": 0}

        class FakeDb:
            def is_connected(self):
                return True

            def ping(self):
                return True

            def connect(self):
                return None

            def execute_query(self, _sql):
                calls["count"] += 1
                if calls["count"] == 1:
                    cause = Exception(
                        "08S01 TCP Provider: Error code 0x68 (104) SQLExecDirectW"
                    )
                    raise QueryError("Query failed") from cause
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

    def test_ensure_project_run_sql_rebinds_sqlalchemy_wrapper(self):
        vn = object.__new__(AIVanna)

        def run_sql_mssql(_sql):
            return None

        run_sql_mssql.__qualname__ = "VannaBase.connect_to_mssql.<locals>.run_sql_mssql"
        vn.run_sql = run_sql_mssql
        AIVanna._ensure_project_run_sql(vn)
        assert vn.run_sql.__func__ is AIVanna.run_sql

    def test_ensure_project_run_sql_rebinds_enhanced_vanna(self):
        from vanna_grok import EnhancedAIVanna

        vn = object.__new__(EnhancedAIVanna)

        def run_sql_mssql(_sql):
            return None

        run_sql_mssql.__qualname__ = "VannaBase.connect_to_mssql.<locals>.run_sql_mssql"
        vn.run_sql = run_sql_mssql
        AIVanna._ensure_project_run_sql(vn)
        assert vn.run_sql.__func__ is EnhancedAIVanna.run_sql

    def test_retries_on_connection_reset_0x68(self, monkeypatch):
        calls = {"count": 0}

        class FakeDb:
            def is_connected(self):
                return True

            def ping(self):
                return True

            def connect(self):
                return None

            def execute_query(self, _sql):
                calls["count"] += 1
                if calls["count"] == 1:
                    raise Exception(
                        "08S01 TCP Provider: Error code 0x68 (104) SQLExecDirectW"
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
