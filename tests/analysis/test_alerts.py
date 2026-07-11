"""
Tests for inventory alerts module.
"""

import pandas as pd
import pytest

from src.business_analyzer.analysis.alerts import InventoryAlerts


@pytest.fixture
def sales_data():
    """Ten days of sales for two products."""
    return pd.DataFrame(
        [
            # Fast mover: 50 units over the window
            {"ArticulosNombre": "Cemento Gris", "Cantidad": 30, "Fecha": "2024-05-01"},
            {"ArticulosNombre": "Cemento Gris", "Cantidad": 20, "Fecha": "2024-05-10"},
            # Slow mover: 5 units
            {"ArticulosNombre": "Llave Allen", "Cantidad": 5, "Fecha": "2024-05-05"},
        ]
    )


class TestVelocityFallback:
    """Behavior without stock data (velocity proxy)."""

    def test_flags_products_above_threshold(self, sales_data):
        alerts = InventoryAlerts(sales_data).analyze_low_stock(threshold=10)

        assert list(alerts["ArticulosNombre"]) == ["Cemento Gris"]
        assert alerts.iloc[0]["total_sold"] == 50
        assert alerts.iloc[0]["transaction_count"] == 2

    def test_daily_avg_uses_observed_date_range(self, sales_data):
        alerts = InventoryAlerts(sales_data).analyze_low_stock(threshold=10)

        # 2024-05-01 → 2024-05-10 inclusive = 10 days
        assert alerts.iloc[0]["daily_avg"] == pytest.approx(5.0)

    def test_daily_avg_defaults_to_30_days_without_dates(self, sales_data):
        no_dates = sales_data.drop(columns=["Fecha"])
        alerts = InventoryAlerts(no_dates).analyze_low_stock(threshold=10)

        assert alerts.iloc[0]["daily_avg"] == pytest.approx(50 / 30)

    def test_empty_data_returns_empty_alerts(self):
        alerts = InventoryAlerts(pd.DataFrame()).analyze_low_stock()

        assert alerts.empty


class TestStockLevels:
    """Behavior with real stock balances."""

    @pytest.fixture
    def stock_data(self):
        return pd.DataFrame(
            [
                {"ArticulosNombre": "Cemento Gris", "Saldo_Actual": 8},
                {"ArticulosNombre": "Llave Allen", "Saldo_Actual": 500},
                {"ArticulosNombre": "Tubo PVC", "Saldo_Actual": 3},  # no sales
            ]
        )

    def test_flags_products_at_or_below_threshold(self, sales_data, stock_data):
        alerts = InventoryAlerts(sales_data, stock_data).analyze_low_stock(threshold=10)

        assert set(alerts["ArticulosNombre"]) == {"Cemento Gris", "Tubo PVC"}

    def test_days_of_cover_ranks_urgency(self, sales_data, stock_data):
        alerts = InventoryAlerts(sales_data, stock_data).analyze_low_stock(threshold=10)

        # Cemento: 8 units / 5 per day = 1.6 days of cover, sorted first;
        # Tubo PVC has no sales → unknown cover, sorted last.
        assert alerts.iloc[0]["ArticulosNombre"] == "Cemento Gris"
        assert alerts.iloc[0]["days_of_cover"] == pytest.approx(1.6)
        assert pd.isna(alerts.iloc[-1]["days_of_cover"])

    def test_healthy_stock_is_not_flagged(self, sales_data, stock_data):
        alerts = InventoryAlerts(sales_data, stock_data).analyze_low_stock(threshold=10)

        assert "Llave Allen" not in set(alerts["ArticulosNombre"])

    def test_stock_balances_are_summed_per_product(self, sales_data):
        per_warehouse = pd.DataFrame(
            [
                {"ArticulosNombre": "Cemento Gris", "Saldo_Actual": 4},
                {"ArticulosNombre": "Cemento Gris", "Saldo_Actual": 4},
            ]
        )
        alerts = InventoryAlerts(sales_data, per_warehouse).analyze_low_stock(
            threshold=10
        )
        cemento = alerts[alerts["ArticulosNombre"] == "Cemento Gris"]

        assert cemento.iloc[0]["current_stock"] == pytest.approx(8.0)


class TestSummary:
    def test_summary_without_stock_data(self, sales_data):
        summary = InventoryAlerts(sales_data).get_summary()

        assert summary["mode"] == "sales_velocity"
        assert summary["threshold"] == 10
        assert summary["total_alerts"] == 1
        assert summary["high_priority"][0]["ArticulosNombre"] == "Cemento Gris"

    def test_summary_with_stock_data(self, sales_data):
        stock = pd.DataFrame([{"ArticulosNombre": "Cemento Gris", "Saldo_Actual": 2}])
        summary = InventoryAlerts(sales_data, stock).get_summary()

        assert summary["mode"] == "stock_levels"
        assert summary["total_alerts"] == 1
        assert summary["high_priority"][0]["current_stock"] == pytest.approx(2.0)

    def test_summary_with_empty_data(self):
        summary = InventoryAlerts(pd.DataFrame()).get_summary()

        assert summary["total_alerts"] == 0
        assert summary["high_priority"] == []
