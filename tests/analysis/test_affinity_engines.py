"""Unit tests for affinity engines with mocked database."""

from unittest.mock import Mock

from business_analyzer.analysis.engines.category_fallback import run as run_category
from business_analyzer.analysis.engines.co_occurrence import SOURCE as CO_SOURCE
from business_analyzer.analysis.engines.co_occurrence import run as run_co_occurrence


class TestCoOccurrenceEngine:
    def test_run_maps_sql_rows(self):
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            {
                "sku_a": "A",
                "name_a": "Prod A",
                "sku_b": "B",
                "name_b": "Prod B",
                "co_count": 5,
            }
        ]

        results = run_co_occurrence(mock_db)
        assert len(results) == 1
        assert results[0]["sku_a"] == "A"
        assert results[0]["source"] == CO_SOURCE
        assert results[0]["score"] > 0


class TestCategoryFallbackEngine:
    def test_run_returns_pairs(self):
        mock_db = Mock()
        mock_db.execute_query.return_value = [
            {
                "ArticulosCodigo": "X",
                "ArticulosNombre": "Item X",
                "categoria": "Materiales",
                "subcategoria": "Cemento",
                "total_sales": 100,
            },
            {
                "ArticulosCodigo": "Y",
                "ArticulosNombre": "Item Y",
                "categoria": "Materiales",
                "subcategoria": "Cemento",
                "total_sales": 80,
            },
        ]

        results = run_category(mock_db, active_skus={"X", "Y"})
        assert results
        assert results[0]["source"] == "category_fallback"
        assert results[0]["score"] > 0
