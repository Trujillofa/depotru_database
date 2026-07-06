"""Tests for sales anomaly detection."""

from unittest.mock import MagicMock

import pytest

from business_analyzer.analysis.anomaly import check_sales_anomaly


class TestCheckSalesAnomaly:
    def test_detects_large_drop(self):
        mock_db = MagicMock()
        mock_db.execute_query.side_effect = [
            [{"total_sales": 50_000}],
            [{"avg_sales": 100_000}],
        ]
        result = check_sales_anomaly(threshold_pct=20.0, db=mock_db)
        assert result["anomaly"] is True
        assert result["drop_pct"] == pytest.approx(50.0)

    def test_no_anomaly_when_within_threshold(self):
        mock_db = MagicMock()
        mock_db.execute_query.side_effect = [
            [{"total_sales": 95_000}],
            [{"avg_sales": 100_000}],
        ]
        result = check_sales_anomaly(threshold_pct=20.0, db=mock_db)
        assert result["anomaly"] is False

    def test_no_avg_data(self):
        mock_db = MagicMock()
        mock_db.execute_query.side_effect = [
            [{"total_sales": 10_000}],
            [{"avg_sales": None}],
        ]
        result = check_sales_anomaly(db=mock_db)
        assert result["anomaly"] is False
        assert result["avg_sales"] == 0.0
