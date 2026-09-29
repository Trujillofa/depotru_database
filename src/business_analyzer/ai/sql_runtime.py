"""SQL generation, cache upgrades, and Database-backed execution.

``generate_sql`` must sit on a mixin that precedes OpenAI_Chat in the
AIVanna MRO so ``super().generate_sql`` still resolves to Vanna.
``AIVanna`` is late-bound by ``business_analyzer.ai.vanna``.
"""

from __future__ import annotations

import os
import time

from .circuit_breaker import CircuitBreakerError, with_circuit_breaker

# Late-bound by business_analyzer.ai.vanna after AIVanna is composed.
AIVanna = None


class SqlRuntimeMixin:
    """generate_sql / run_sql / MSSQL connect for AIVanna."""

    def _is_sqlalchemy_run_sql(self) -> bool:
        func = getattr(self.run_sql, "__func__", self.run_sql)
        return getattr(func, "__qualname__", "").endswith("run_sql_mssql")

    def _is_project_run_sql(self) -> bool:
        """True when run_sql is our Database-backed implementation."""
        func = getattr(self.run_sql, "__func__", self.run_sql)
        module = getattr(func, "__module__", "")
        qualname = getattr(func, "__qualname__", "")
        if "business_analyzer" in module:
            return True
        return qualname.endswith(("AIVanna.run_sql", "EnhancedAIVanna.run_sql"))

    def _bind_project_run_sql(self) -> None:
        """Keep Vanna on the resilient Database-backed run_sql (not SQLAlchemy)."""
        for cls in type(self).__mro__:
            if cls.__name__ == "EnhancedAIVanna" and "run_sql" in cls.__dict__:
                self.run_sql = cls.__dict__["run_sql"].__get__(self, type(self))
                self.run_sql_is_set = True
                return
            if cls is AIVanna and "run_sql" in cls.__dict__:
                self.run_sql = cls.__dict__["run_sql"].__get__(self, type(self))
                self.run_sql_is_set = True
                return
        self.run_sql = AIVanna.run_sql.__get__(self, AIVanna)
        self.run_sql_is_set = True

    def _ensure_project_run_sql(self) -> None:
        """Re-bind if Vanna's SQLAlchemy connect_to_mssql replaced run_sql."""
        if self._is_sqlalchemy_run_sql() or not self._is_project_run_sql():
            self._bind_project_run_sql()

    def connect_to_mssql(self, odbc_conn_str: str = "", **kwargs):
        """Register MSSQL dialect; SQL runs through project Database layer."""
        self.dialect = "T-SQL / Microsoft SQL Server"
        self._bind_project_run_sql()

    def generate_sql(
        self, question: str, allow_llm_to_see_data: bool = True, **kwargs
    ) -> str:
        """
        Generate SQL with circuit breaker and retry logic.
        """
        try:
            self._manager_report_result = None
            if question:
                routed = self.route_manager_report_question(question)
                if routed is not None:
                    self._manager_report_result = routed
                    return None
                if self._is_brand_by_warehouse_question(question):
                    template = self._brand_sales_by_warehouse_sql_template(question)
                    if template:
                        self._query_cache.set(question, template)
                        return template
                if self._is_brand_at_warehouse_question(question):
                    template = self._brand_sales_at_warehouse_sql_template(question)
                    if template:
                        self._query_cache.set(question, template)
                        return template
                if self._is_brand_by_branch_question(question):
                    template = self._brand_sales_by_branch_sql_template(question)
                    if template:
                        self._query_cache.set(question, template)
                        return template
                if self._is_j3system_warehouse_question(question):
                    template = self._j3system_warehouse_sql_template(question)
                    if template:
                        self._query_cache.set(question, template)
                        return template

            cached = self._query_cache.get(question)
            if cached:
                if self._is_document_type_sales_question(question):
                    cached_lower = cached.lower()
                    needs_upgrade = (
                        "ventatotal" in cached_lower
                        or "sum(total)" in cached_lower
                        or "documentoscodigo in ('fed', 'fef', 'fet')"
                        not in cached_lower
                    )
                    if needs_upgrade:
                        template = self._document_type_sales_sql_template(question)
                        if template:
                            self._query_cache.set(question, template)
                            return template
                if self._is_year_month_comparison_question(question):
                    cached_lower = cached.lower()
                    needs_upgrade = (
                        "totalactiva" in cached_lower
                        or "totalventas" in cached_lower
                        or "ventas_anio_actual" not in cached_lower
                    )
                    if needs_upgrade:
                        template = self._year_month_comparison_sql_template(question)
                        if template:
                            self._query_cache.set(question, template)
                            return template
                if self._is_daily_average_by_month_question(question):
                    cached_lower = cached.lower()
                    needs_upgrade = (
                        "ventatotal" in cached_lower
                        or "sum(total)" in cached_lower
                        or "sum(totalmasiva)" not in cached_lower
                    )
                    if needs_upgrade:
                        template = self._daily_average_by_month_sql_template()
                        if template:
                            self._query_cache.set(question, template)
                            return template
                if self._is_vendedor_performance_question(question):
                    cached_lower = cached.lower()
                    needs_upgrade = (
                        "group by vendedorfactura, vendedor_codigo" in cached_lower
                        or (
                            "este mes" in (question or "").lower()
                            and "month(fecha) = month(getdate())" not in cached_lower
                            and "dateadd(month, -1" in cached_lower
                        )
                    )
                    if needs_upgrade:
                        template = self._vendedor_performance_sql_template(question)
                        if template:
                            self._query_cache.set(question, template)
                            return template
                if self._is_branch_product_ranking_question(question):
                    cached_lower = cached.lower()
                    doc_code = (self._branch_document_code(question) or "fef").lower()
                    needs_upgrade = (
                        "marca_proveedor" in cached_lower
                        or "productos_adicional" in cached_lower
                        or "group by articulosnombre" not in cached_lower
                        or f"documentoscodigo = '{doc_code}'" not in cached_lower
                    )
                    if needs_upgrade:
                        template = self._branch_product_ranking_sql_template(question)
                        if template:
                            self._query_cache.set(question, template)
                            return template
                if self._is_branch_store_sales_question(question):
                    cached_lower = cached.lower()
                    doc_code = (self._branch_document_code(question) or "fef").lower()
                    needs_upgrade = (
                        "marca_proveedor" in cached_lower
                        or "productos_adicional" in cached_lower
                        or f"documentoscodigo = '{doc_code}'" not in cached_lower
                    )
                    if needs_upgrade:
                        template = self._branch_store_sql_template(question)
                        if template:
                            self._query_cache.set(question, template)
                            return template
                if self._is_last_n_days_sales_question(question):
                    cached_lower = cached.lower()
                    needs_upgrade = (
                        "ventatotal" in cached_lower
                        or "sum(total)" in cached_lower
                        or "tabla" in cached_lower
                        or "sum(totalmasiva)" not in cached_lower
                    )
                    if needs_upgrade:
                        template = self._last_n_days_sales_sql_template(question)
                        if template:
                            self._query_cache.set(question, template)
                            return template
                if self._is_credit_vs_cash_question(question):
                    cached_lower = cached.lower()
                    needs_upgrade = "diascredito" not in cached_lower
                    if needs_upgrade:
                        template = self._credit_vs_cash_sql_template(question)
                        if template:
                            self._query_cache.set(question, template)
                            return template
                if self._is_top_customers_question(question):
                    cached_lower = cached.lower()
                    needs_upgrade = (
                        "ganancia_neta" not in cached_lower
                        or "replace(replace" not in cached_lower
                    )
                    if needs_upgrade:
                        template = self._top_customers_sql_template(question)
                        if template:
                            self._query_cache.set(question, template)
                            return template
                if self._is_brand_top_products_question(question):
                    cached_lower = cached.lower()
                    brands = self._extract_vendor_brands(question)
                    needs_upgrade = (
                        "marca_proveedor" in cached_lower
                        or "group by articulosnombre" not in cached_lower
                        or "group by bd.articulosnombre" not in cached_lower
                        or (brands and "productos_adicional" not in cached_lower)
                    )
                    if needs_upgrade:
                        template = self._brand_top_products_sql_template(question)
                        if template:
                            self._query_cache.set(question, template)
                            return template
                if self._is_generic_top_products_question(question):
                    cached_lower = cached.lower()
                    needs_upgrade = (
                        "group by articulosnombre" not in cached_lower
                        or "marca_proveedor" in cached_lower
                    )
                    if needs_upgrade:
                        template = self._generic_top_products_sql_template(question)
                        if template:
                            self._query_cache.set(question, template)
                            return template
                if self._is_brand_monthly_sales_question(question):
                    cached_lower = cached.lower()
                    needs_upgrade = (
                        "totalactiva" in cached_lower
                        or "totalventas" in cached_lower
                        or "group by year(fecha)" not in cached_lower
                    )
                    if needs_upgrade:
                        template = self._brand_monthly_sales_sql_template(question)
                        if template:
                            self._query_cache.set(question, template)
                            return template
                if self._is_brand_by_warehouse_question(question):
                    cached_lower = cached.lower()
                    needs_upgrade = (
                        "invimpresionfactura" in cached_lower
                        or "bd.almacencodigo" not in cached_lower
                        or "documentoscodigo in ('fed', 'fef', 'fet')" in cached_lower
                        or (
                            "from banco_datos" not in cached_lower
                            and "invventas" in cached_lower
                        )
                    )
                    if needs_upgrade:
                        template = self._brand_sales_by_warehouse_sql_template(question)
                        if template:
                            self._query_cache.set(question, template)
                            return template
                if self._is_brand_by_branch_question(question):
                    cached_lower = cached.lower()
                    needs_upgrade = (
                        "invimpresionfactura" in cached_lower
                        or "documentoscodigo in ('fed', 'fef', 'fet')"
                        not in cached_lower
                        or (
                            "from banco_datos" not in cached_lower
                            and "invventas" in cached_lower
                        )
                    )
                    if needs_upgrade:
                        template = self._brand_sales_by_branch_sql_template(question)
                        if template:
                            self._query_cache.set(question, template)
                            return template
                if self._is_j3system_warehouse_question(question):
                    cached_lower = cached.lower()
                    needs_upgrade = "invimpresionfactura" in cached_lower
                    if needs_upgrade:
                        template = self._j3system_warehouse_sql_template(question)
                        if template:
                            self._query_cache.set(question, template)
                            return template
                if self._is_multi_vendor_sales_question(question):
                    cached_lower = cached.lower()
                    brands = self._extract_vendor_brands(question)
                    missing_prefilter = (
                        not AIVanna._multi_vendor_sql_has_where_prefilter(
                            cached, brands
                        )
                    )
                    needs_upgrade = (
                        "productos_adicional" not in cached_lower
                        or "collate database_default" not in cached_lower
                        or "totalmasiva" not in cached_lower
                        or "from banco_datos" not in cached_lower
                        or missing_prefilter
                    )
                    if needs_upgrade:
                        template = self._multi_vendor_sales_sql_template(brands)
                        if template:
                            self._query_cache.set(question, template)
                            return template
                return cached

            if self._is_document_type_sales_question(question):
                template = self._document_type_sales_sql_template(question)
                if template:
                    self._query_cache.set(question, template)
                    return template
            if self._is_year_month_comparison_question(question):
                template = self._year_month_comparison_sql_template(question)
                if template:
                    self._query_cache.set(question, template)
                    return template
            if self._is_daily_average_by_month_question(question):
                template = self._daily_average_by_month_sql_template()
                if template:
                    self._query_cache.set(question, template)
                    return template
            if self._is_vendedor_performance_question(question):
                template = self._vendedor_performance_sql_template(question)
                if template:
                    self._query_cache.set(question, template)
                    return template
            if self._is_branch_product_ranking_question(question):
                template = self._branch_product_ranking_sql_template(question)
                if template:
                    self._query_cache.set(question, template)
                    return template
            if self._is_branch_store_sales_question(question):
                template = self._branch_store_sql_template(question)
                if template:
                    self._query_cache.set(question, template)
                    return template
            if self._is_last_n_days_sales_question(question):
                template = self._last_n_days_sales_sql_template(question)
                if template:
                    self._query_cache.set(question, template)
                    return template
            if self._is_credit_vs_cash_question(question):
                template = self._credit_vs_cash_sql_template(question)
                if template:
                    self._query_cache.set(question, template)
                    return template
            if self._is_top_customers_question(question):
                template = self._top_customers_sql_template(question)
                if template:
                    self._query_cache.set(question, template)
                    return template
            if self._is_brand_top_products_question(question):
                template = self._brand_top_products_sql_template(question)
                if template:
                    self._query_cache.set(question, template)
                    return template
            if self._is_generic_top_products_question(question):
                template = self._generic_top_products_sql_template(question)
                if template:
                    self._query_cache.set(question, template)
                    return template
            if self._is_brand_monthly_sales_question(question):
                template = self._brand_monthly_sales_sql_template(question)
                if template:
                    self._query_cache.set(question, template)
                    return template
            if self._is_brand_by_warehouse_question(question):
                template = self._brand_sales_by_warehouse_sql_template(question)
                if template:
                    self._query_cache.set(question, template)
                    return template
            if self._is_brand_by_branch_question(question):
                template = self._brand_sales_by_branch_sql_template(question)
                if template:
                    self._query_cache.set(question, template)
                    return template
            if self._is_multi_vendor_sales_question(question):
                brands = self._extract_vendor_brands(question)
                template = self._multi_vendor_sales_sql_template(brands)
                if template:
                    self._query_cache.set(question, template)
                    return template
            # Apply circuit breaker based on provider
            decorator = with_circuit_breaker(self.provider)
            decorated_gen = decorator(super().generate_sql)
            generated = decorated_gen(
                question=question, allow_llm_to_see_data=allow_llm_to_see_data, **kwargs
            )
            if isinstance(generated, str):
                normalized = generated.strip().upper()
                if (
                    normalized
                    and "SELECT" not in normalized
                    and "WITH" not in normalized
                ):
                    print(
                        "⚠️ Model returned non-SQL response; skipping execution for this question."
                    )
                    return None

                if self._is_document_type_sales_question(question):
                    generated_lower = generated.lower()
                    if "from banco_datos" in generated_lower:
                        post_candidate = self._document_type_sales_sql_template(
                            question
                        )
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                if self._is_year_month_comparison_question(question):
                    generated_lower = generated.lower()
                    if "from banco_datos" in generated_lower:
                        post_candidate = self._year_month_comparison_sql_template(
                            question
                        )
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                if self._is_daily_average_by_month_question(question):
                    generated_lower = generated.lower()
                    if "from banco_datos" in generated_lower:
                        post_candidate = self._daily_average_by_month_sql_template()
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                if self._is_vendedor_performance_question(question):
                    generated_lower = generated.lower()
                    if "from banco_datos" in generated_lower:
                        post_candidate = self._vendedor_performance_sql_template(
                            question
                        )
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                if self._is_branch_product_ranking_question(question):
                    generated_lower = generated.lower()
                    if "from banco_datos" in generated_lower:
                        post_candidate = self._branch_product_ranking_sql_template(
                            question
                        )
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                if self._is_branch_store_sales_question(question):
                    generated_lower = generated.lower()
                    if "from banco_datos" in generated_lower:
                        post_candidate = self._branch_store_sql_template(question)
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                if self._is_last_n_days_sales_question(question):
                    generated_lower = generated.lower()
                    if "from banco_datos" in generated_lower:
                        post_candidate = self._last_n_days_sales_sql_template(question)
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                if self._is_credit_vs_cash_question(question):
                    generated_lower = generated.lower()
                    if "from banco_datos" in generated_lower:
                        post_candidate = self._credit_vs_cash_sql_template(question)
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                if self._is_top_customers_question(question):
                    generated_lower = generated.lower()
                    if "from banco_datos" in generated_lower:
                        post_candidate = self._top_customers_sql_template(question)
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                if self._is_brand_top_products_question(question):
                    generated_lower = generated.lower()
                    if "from banco_datos" in generated_lower:
                        post_candidate = self._brand_top_products_sql_template(question)
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                if self._is_generic_top_products_question(question):
                    generated_lower = generated.lower()
                    if "from banco_datos" in generated_lower:
                        post_candidate = self._generic_top_products_sql_template(
                            question
                        )
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                if self._is_brand_monthly_sales_question(question):
                    generated_lower = generated.lower()
                    if "from banco_datos" in generated_lower:
                        post_candidate = self._brand_monthly_sales_sql_template(
                            question
                        )
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                if self._is_brand_by_warehouse_question(question):
                    generated_lower = generated.lower()
                    if (
                        "from banco_datos" in generated_lower
                        or "invimpresionfactura" in generated_lower
                        or "invventas" in generated_lower
                    ):
                        post_candidate = self._brand_sales_by_warehouse_sql_template(
                            question
                        )
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                if self._is_brand_by_branch_question(question):
                    generated_lower = generated.lower()
                    if (
                        "from banco_datos" in generated_lower
                        or "invimpresionfactura" in generated_lower
                        or "invventas" in generated_lower
                    ):
                        post_candidate = self._brand_sales_by_branch_sql_template(
                            question
                        )
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                if self._is_brand_profit_question(question):
                    generated_lower = generated.lower()
                    if "from banco_datos" in generated_lower:
                        post_candidate = self._brand_profit_sql_template()
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                if self._is_weekday_sales_question(question):
                    generated_lower = generated.lower()
                    if "from banco_datos" in generated_lower:
                        post_candidate = self._weekday_sales_sql_template()
                        self._query_cache.set(question, post_candidate)
                        return post_candidate
                repaired_generated = self._repair_sika_center_customer_sql(generated)
                repaired_generated = self._repair_common_sql_hallucinations(
                    repaired_generated
                )
                post_candidate = self._ensure_document_exclusion(repaired_generated)
                self._query_cache.set(question, post_candidate)
                return post_candidate
            return generated
        except CircuitBreakerError as e:
            print(f"🛑 AI Provider {self.provider.upper()} is currently offline: {e}")
            return None
        except Exception as e:
            print(f"⚠️ Error generating SQL with {self.provider.upper()}: {e}")
            raise

    def run_sql(self, sql: str, **kwargs):
        """Execute SQL via shared Database layer (pooling, timeouts, retry)."""
        import pandas as pd

        from business_analyzer.core.database import QueryError
        from business_analyzer.core.db_factory import (
            get_database,
            release_thread_connections,
        )

        self._ensure_project_run_sql()

        if not sql:
            return pd.DataFrame()

        sql = self._prepare_sql_for_execution(sql)

        def _with_customer_space_normalization(query: str) -> str:
            normalized = query.replace(
                "TercerosNombres LIKE",
                "REPLACE(REPLACE(TercerosNombres, '  ', ' '), '  ', ' ') LIKE",
            )
            normalized = normalized.replace(
                "tercerosnombres like",
                "REPLACE(REPLACE(tercerosnombres, '  ', ' '), '  ', ' ') like",
            )
            return normalized

        from business_analyzer.core.database import is_transient_db_error

        def _is_transient_connection_error(error: Exception) -> bool:
            if is_transient_db_error(error):
                return True
            if isinstance(error, QueryError) and error.__cause__ is not None:
                return is_transient_db_error(error.__cause__)
            return False

        def _execute_via_database(query: str) -> pd.DataFrame:
            db = get_database(reuse=True)
            if not db.is_connected():
                db.connect()
            rows = db.execute_query(query)
            if not isinstance(rows, list):
                return pd.DataFrame()
            return pd.DataFrame(rows) if rows else pd.DataFrame()

        max_attempts = int(os.getenv("DB_QUERY_RETRIES", "2")) + 1
        last_error: Exception | None = None

        for attempt in range(max_attempts):
            try:
                df = _execute_via_database(sql)
                if (
                    df.empty
                    and "tercerosnombres" in sql.lower()
                    and " like " in sql.lower()
                ):
                    normalized_sql = _with_customer_space_normalization(sql)
                    if normalized_sql != sql:
                        normalized_df = _execute_via_database(normalized_sql)
                        if not normalized_df.empty:
                            return normalized_df
                return df
            except Exception as e:
                last_error = e
                if _is_transient_connection_error(e) and attempt < max_attempts - 1:
                    print(
                        f"⚠️ Conexión DB inestable (intento {attempt + 1}/{max_attempts}); "
                        "reintentando…"
                    )
                    release_thread_connections()
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break

        if last_error is not None:
            print(f"❌ Database error executing SQL: {last_error}")
            raise last_error
        return pd.DataFrame()

    def connect_to_mssql_odbc(self):
        """Connect & verify via project Database layer (pooling, timeouts, retry)."""
        self.connect_to_mssql()
        self._bind_project_run_sql()
        df = self.run_sql("SELECT 1 AS ping;")
        if df is not None and not df.empty:
            print("✓ MSSQL connected & ping successful!")
        else:
            raise ValueError("Ping returned empty—check DB access")
