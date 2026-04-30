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
