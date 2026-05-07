"""
Tests for AI package training module.
"""

import os
import sys
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from business_analyzer.ai.training import (
    generate_training_data,
    get_default_training_examples,
    load_autoresearch_training_examples,
)


class TestTrainingExamples:
    """Test training examples."""

    def test_default_examples_not_empty(self):
        """Test that default examples are not empty."""
        examples = get_default_training_examples()
        assert len(examples) > 0

    def test_default_examples_structure(self):
        """Test that default examples have correct structure."""
        examples = get_default_training_examples()
        for question, sql in examples:
            assert isinstance(question, str)
            assert isinstance(sql, str)
            assert len(question) > 0
            assert len(sql) > 0

    def test_default_examples_contain_sql(self):
        """Test that default examples contain SQL."""
        examples = get_default_training_examples()
        for question, sql in examples:
            assert "SELECT" in sql.upper()

    def test_default_examples_include_weekday_spanish_pattern(self):
        """Ensures weekday analysis examples preserve Spanish labels in SQL."""
        examples = get_default_training_examples()
        weekday_examples = [
            sql
            for question, sql in examples
            if "día de la semana" in question.lower()
            or "días de la semana" in question.lower()
        ]
        joined_sql = "\n".join(weekday_examples)
        assert "DATENAME(WEEKDAY, Fecha)" in joined_sql
        assert "WHEN 'Monday' THEN 'Lunes'" in joined_sql
        assert "DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')" in joined_sql

    def test_weekday_order_example_uses_language_independent_sort(self):
        """Weekday order SQL should not depend on SQL Server language settings."""
        examples = get_default_training_examples()
        target_sql = next(
            sql
            for question, sql in examples
            if question == "Ventas por día de la semana en orden"
        )

        assert "WITH ventas_por_dia AS" in target_sql
        assert "DATEPART(WEEKDAY, Fecha)" in target_sql
        assert "@@DATEFIRST" in target_sql
        assert "GROUP BY Dia_Orden" in target_sql
        assert "ORDER BY Dia_Orden" in target_sql
        assert "WHEN 'Monday'" not in target_sql

    def test_sika_vendor_example_uses_normalized_matching(self):
        """Ensure SIKA+vendor example is resilient to casing/whitespace variants."""
        examples = get_default_training_examples()
        target_sql = next(
            sql
            for question, sql in examples
            if "ventas de sika por vendedor carlos efrey pascuas" in question.lower()
        )

        assert "YEAR(Fecha) = YEAR(GETDATE())" in target_sql
        assert (
            "UPPER(LTRIM(RTRIM(COALESCE(proveedor, '')))) LIKE '%SIKA%'" in target_sql
        )
        assert "UPPER(LTRIM(RTRIM(COALESCE(marca, '')))) LIKE '%SIKA%'" in target_sql
        assert (
            "UPPER(LTRIM(RTRIM(COALESCE(categoria, '')))) LIKE '%SIKA%'" in target_sql
        )
        assert (
            "UPPER(LTRIM(RTRIM(COALESCE(subcategoria, '')))) LIKE '%SIKA%'"
            in target_sql
        )

    def test_cemex_example_uses_dynamic_current_year(self):
        """Avoid stale fixed-year filters in CEMEX example."""
        examples = get_default_training_examples()
        target_sql = next(
            sql
            for question, sql in examples
            if "ventas de productos cemex" in question.lower()
        )
        assert "YEAR(Fecha) = YEAR(GETDATE())" in target_sql

    def test_training_examples_include_new_diversity_patterns(self):
        """Training set includes examples for common phrasing and BI edge cases."""
        questions = {question for question, _ in get_default_training_examples()}

        expected_questions = {
            "Dame los clientes top por facturación este mes",
            "Productos de baja rotación en los últimos 90 días",
            "Margen por marca o proveedor",
            "Ventas por departamento y ciudad",
            "Patrón estacional de ventas por mes en los últimos 24 meses",
            "Ventas de la categoría CEMENTO GRIS comparadas por marca",
            "Ventas del Sika Center este año",
            "Ventas de la sede Sika Center por mes",
            "Ventas de Calle 5 este año",
        }

        assert expected_questions.issubset(questions)

    def test_new_examples_keep_document_filter_and_safe_patterns(self):
        """New examples preserve exclusion filters, SQL Server TOP, and safe margin math."""
        examples = dict(get_default_training_examples())

        low_rotation_sql = examples["Productos de baja rotación en los últimos 90 días"]
        assert (
            "DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')"
            in low_rotation_sql
        )
        assert "TOP 20" in low_rotation_sql
        assert "HAVING SUM(Cantidad) > 0" in low_rotation_sql

        brand_margin_sql = examples["Margen por marca o proveedor"]
        assert "NULLIF(TotalSinIva, 0)" in brand_margin_sql
        assert "COALESCE(NULLIF(LTRIM(RTRIM(proveedor)), '')" in brand_margin_sql
        assert "LIMIT" not in brand_margin_sql.upper()

    def test_schema_documentation_warns_about_ambiguous_terms_and_bad_columns(self):
        """Schema training docs should steer the model away from common hallucinations."""
        from business_analyzer.ai.training import train_on_schema

        class Recorder:
            def __init__(self):
                self.documentation = []

            def train(self, ddl=None, documentation=None):
                if documentation:
                    self.documentation.append(documentation)

        recorder = Recorder()
        train_on_schema(recorder)
        docs = "\n".join(recorder.documentation)

        assert "AMBIGUITY RESOLUTION" in docs
        assert 'If user asks for "marca" or "proveedor"' in docs
        assert "NON-EXISTENT COLUMNS TO AVOID" in docs
        assert "total_profit" in docs
        assert "Use TOP N for result limits in SQL Server, not LIMIT" in docs

    def test_sika_center_examples_use_branch_document_code_not_customer(self):
        """SIKA CENTER is a branch/store document type, never a customer filter."""
        examples = dict(get_default_training_examples())
        target_sql = examples["Ventas del Sika Center este año"]

        assert "DocumentosCodigo = 'FEF'" in target_sql
        assert "YEAR(Fecha) = YEAR(GETDATE())" in target_sql
        assert "TercerosNombres" not in target_sql

    def test_schema_documentation_maps_sika_center_to_branch(self):
        """Schema docs must explicitly disambiguate SIKA products vs SIKA CENTER."""
        from business_analyzer.ai.training import train_on_schema

        class Recorder:
            def __init__(self):
                self.documentation = []

            def train(self, ddl=None, documentation=None):
                if documentation:
                    self.documentation.append(documentation)

        recorder = Recorder()
        train_on_schema(recorder)
        docs = "\n".join(recorder.documentation)

        assert "SIKA CENTER is a branch/store, NOT a customer" in docs
        assert "Use DocumentosCodigo = 'FEF'" in docs
        assert "never TercerosNombres" in docs

    def test_sika_center_runtime_template_uses_branch_document_code(self):
        """Runtime SQL repair template protects SIKA CENTER branch prompts."""
        source = (
            Path(__file__).parents[2] / "src" / "business_analyzer" / "ai" / "base.py"
        )
        base_code = source.read_text(encoding="utf-8")

        assert "def _is_sika_center_branch_question" in base_code
        assert 'return "sika center" in lower' in base_code
        assert "def _sika_center_branch_sql_template" in base_code
        assert "def _repair_sika_center_customer_sql" in base_code
        assert "sql = self._repair_sika_center_customer_sql(sql)" in base_code
        template_code = base_code.split("def _sika_center_branch_sql_template", 1)[1]
        template_code = template_code.split("def _weekday_sales_sql_template", 1)[0]

        assert "DocumentosCodigo = 'FEF'" in template_code
        assert "YEAR(Fecha) = YEAR(GETDATE())" in template_code
        assert "MONTH(Fecha) = {month_number}" in template_code
        assert "TercerosNombres" not in template_code

    def test_sika_center_bad_customer_sql_repair_is_wired_before_execution(self):
        """Stale UI SQL with SIKA as customer must be repaired before run_sql executes."""
        source = (
            Path(__file__).parents[2] / "src" / "business_analyzer" / "ai" / "base.py"
        )
        base_code = source.read_text(encoding="utf-8")
        repair_code = base_code.split("def _repair_sika_center_customer_sql", 1)[1]
        repair_code = repair_code.split("def _weekday_sales_sql_template", 1)[0]

        assert '"tercerosnombres" in lower' in repair_code
        assert '"sika" in lower' in repair_code
        assert "return AIVanna._sika_center_branch_sql_template(sql)" in repair_code


class TestGenerateTrainingData:
    """Test training data generation."""

    def test_generate_training_data_basic(self):
        """Test basic training data generation."""
        data = generate_training_data()
        assert len(data) > 0

    def test_generate_training_data_custom_table(self):
        """Test training data generation with custom table."""
        data = generate_training_data(table_name="custom_table")
        assert len(data) > 0
        # Check that custom table name is used
        for question, sql in data:
            assert "custom_table" in sql

    def test_generate_training_data_without_common_queries(self):
        """Test training data generation without common queries."""
        data = generate_training_data(include_common_queries=False)
        assert len(data) == 0


class TestAutoResearchLoader:
    """Test external AutoResearch training-data ingestion."""

    def test_load_jsonl_examples(self, tmp_path: Path):
        """Loads valid question/sql pairs from JSONL."""
        file_path = tmp_path / "examples.jsonl"
        file_path.write_text(
            "\n".join(
                [
                    '{"question":"Top productos","sql":"SELECT TOP 5 ArticulosNombre FROM banco_datos"}',
                    '{"prompt":"Ventas por categoria","completion":"SELECT categoria, SUM(TotalMasIva) FROM banco_datos GROUP BY categoria"}',
                    '{"question":"bad","sql":"DELETE FROM banco_datos"}',
                ]
            ),
            encoding="utf-8",
        )

        examples = load_autoresearch_training_examples(str(file_path))
        assert len(examples) == 2
        assert all(isinstance(q, str) and isinstance(s, str) for q, s in examples)

    def test_injects_document_filter_for_banco_datos(self, tmp_path: Path):
        """Ensures critical DocumentosCodigo filter is injected when missing."""
        file_path = tmp_path / "filter_check.jsonl"
        file_path.write_text(
            '{"question":"Historial cliente","sql":"SELECT TOP 10 * FROM banco_datos ORDER BY Fecha DESC"}\n',
            encoding="utf-8",
        )

        examples = load_autoresearch_training_examples(str(file_path))
        assert len(examples) == 1
        _, sql = examples[0]
        assert "DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')" in sql

    def test_normalizes_existing_document_filter_to_canonical(self, tmp_path: Path):
        """Rewrites shorter/legacy exclusion lists to canonical five-code filter."""
        file_path = tmp_path / "legacy_filter.jsonl"
        file_path.write_text(
            '{"question":"Ingresos","sql":"SELECT * FROM banco_datos WHERE DocumentosCodigo NOT IN (\'XY\', \'AS\', \'TS\')"}\n',
            encoding="utf-8",
        )

        examples = load_autoresearch_training_examples(str(file_path))
        assert len(examples) == 1
        _, sql = examples[0]
        assert "DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')" in sql

    def test_load_tsv_two_columns(self, tmp_path: Path):
        """Loads basic two-column TSV format."""
        file_path = tmp_path / "examples.tsv"
        file_path.write_text(
            "Pregunta\tSQL\n"
            "Top clientes\tSELECT TOP 10 TercerosNombres FROM banco_datos\n",
            encoding="utf-8",
        )

        examples = load_autoresearch_training_examples(str(file_path))
        assert len(examples) == 1
        assert examples[0][0] == "Top clientes"
        assert "SELECT TOP 10" in examples[0][1]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
