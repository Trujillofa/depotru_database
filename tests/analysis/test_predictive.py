"""Tests for predictive demand forecasting."""

from unittest.mock import MagicMock

from business_analyzer.analysis.predictive import (
    _linear_forecast,
    forecast_demand,
    get_top_products,
)
from config import Config


class TestLinearForecast:
    def test_upward_trend(self):
        daily = [10.0, 20.0, 30.0, 40.0]
        assert _linear_forecast(daily, days=30) > 0

    def test_insufficient_data_returns_zero(self):
        assert _linear_forecast([], days=30) == 0
        assert _linear_forecast([5.0], days=30) == 0


class TestForecastDemand:
    def test_uses_database_rows(self):
        mock_db = MagicMock()
        mock_db.execute_query.return_value = [
            {"total_qty": 10},
            {"total_qty": 20},
            {"total_qty": 30},
        ]
        result = forecast_demand("SKU-1", days=30, db=mock_db)
        assert result >= 0
        mock_db.execute_query.assert_called_once()
        args = mock_db.execute_query.call_args[0]
        assert "ArticulosCodigo = %s" in args[0]
        assert args[1][0] == "SKU-1"
        assert args[1][-len(Config.EXCLUDED_DOCUMENT_CODES) :] == tuple(
            Config.EXCLUDED_DOCUMENT_CODES
        )


class TestTopProducts:
    def test_bounded_limit(self):
        mock_db = MagicMock()
        mock_db.execute_query.return_value = [
            {
                "product_id": "A",
                "product_name": "Prod A",
                "total_qty": 100,
            }
        ]
        rows = get_top_products(limit=5, db=mock_db)
        assert len(rows) == 1
        sql, params = mock_db.execute_query.call_args[0]
        assert "TOP 5" in sql
        assert params[-len(Config.EXCLUDED_DOCUMENT_CODES) :] == tuple(
            Config.EXCLUDED_DOCUMENT_CODES
        )
