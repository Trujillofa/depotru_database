"""Tests for affinity co-occurrence mart helpers."""

from unittest.mock import Mock, patch

from business_analyzer.analysis.affinity_mart import (
    rows_to_engine_results,
    use_mart_preferred,
)
from business_analyzer.analysis.engines.co_occurrence import run as run_co_occurrence


class TestAffinityMartHelpers:
    def test_rows_to_engine_results_normalizes_scores(self):
        rows = [
            {
                "sku_a": "A",
                "sku_b": "B",
                "name_a": "Prod A",
                "name_b": "Prod B",
                "co_count": 10,
            },
            {
                "sku_a": "C",
                "sku_b": "D",
                "name_a": "Prod C",
                "name_b": "Prod D",
                "co_count": 5,
            },
        ]
        results = rows_to_engine_results(rows, active_skus={"A", "B", "C", "D"})
        assert len(results) == 2
        assert results[0]["score"] == 1.0
        assert results[1]["score"] == 0.5

    @patch.dict("os.environ", {"AFFINITY_USE_MART": "1"})
    def test_use_mart_preferred_enabled(self):
        assert use_mart_preferred() is True


class TestCoOccurrenceMartPath:
    @patch("business_analyzer.analysis.engines.co_occurrence.use_mart_preferred")
    @patch("business_analyzer.analysis.engines.co_occurrence.mart_table_exists")
    @patch(
        "business_analyzer.analysis.engines.co_occurrence.fetch_co_occurrence_from_mart"
    )
    def test_run_reads_mart_when_enabled(self, mock_fetch, mock_exists, mock_use_mart):
        mock_use_mart.return_value = True
        mock_exists.return_value = True
        mock_fetch.return_value = [
            {
                "sku_a": "A",
                "sku_b": "B",
                "name_a": "Prod A",
                "name_b": "Prod B",
                "co_count": 4,
            }
        ]
        mock_db = Mock()

        results = run_co_occurrence(mock_db, active_skus={"A", "B"})
        assert len(results) == 1
        assert results[0]["source"] == "co_occurrence"
        mock_fetch.assert_called_once_with(mock_db)
