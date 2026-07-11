"""
Alerts module for Business Data Analyzer.

Identifies items below safety stock thresholds and provides inventory insights.
"""

from typing import Any, Dict, Optional

import pandas as pd

#: Fallback observation window (days) when sales dates are unavailable.
DEFAULT_PERIOD_DAYS = 30.0


class InventoryAlerts:
    """
    Inventory alert system to identify stock-outs and low inventory.

    When ``stock_data`` is provided (current balances per product, as produced
    by the J3System existencias queries), alerts flag products at or below the
    safety-stock threshold, ranked by days of cover
    (``current_stock / average daily sales``).

    Without stock levels, sales velocity is used as a proxy: the fastest
    moving products are the ones most exposed to a stock-out.
    """

    #: Column identifying the product in both ``data`` and ``stock_data``.
    PRODUCT_COLUMN = "ArticulosNombre"
    #: Column in ``stock_data`` holding the current stock balance.
    STOCK_COLUMN = "Saldo_Actual"

    def __init__(self, data: pd.DataFrame, stock_data: Optional[pd.DataFrame] = None):
        self.data = data
        self.stock_data = stock_data
        self.default_buffer = 10  # Default safety stock units

    def analyze_low_stock(self, threshold: Optional[int] = None) -> pd.DataFrame:
        """
        Identify products with low inventory.

        With stock data: products whose current stock is at or below the
        threshold, with ``days_of_cover`` computed from average daily sales,
        most urgent first (``days_of_cover`` is NaN for products without
        recent sales, which sort last).

        Without stock data: products whose total sales volume exceeds the
        threshold (velocity proxy), highest volume first.
        """
        limit = threshold if threshold is not None else self.default_buffer
        velocity = self._sales_velocity()

        if self._has_stock_data():
            return self._low_stock_from_balances(velocity, limit)

        # Velocity proxy: fast movers are the most exposed to stock-outs.
        alerts = velocity[velocity["total_sold"] > limit].sort_values(
            "total_sold", ascending=False
        )
        return alerts.reset_index()

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of inventory alerts."""
        alerts = self.analyze_low_stock()

        return {
            "total_alerts": len(alerts),
            "high_priority": alerts.head(5).to_dict("records"),
            "threshold": self.default_buffer,
            "mode": "stock_levels" if self._has_stock_data() else "sales_velocity",
        }

    def _has_stock_data(self) -> bool:
        return (
            self.stock_data is not None
            and not self.stock_data.empty
            and self.PRODUCT_COLUMN in self.stock_data.columns
            and self.STOCK_COLUMN in self.stock_data.columns
        )

    def _sales_velocity(self) -> pd.DataFrame:
        """Per-product sales totals and average daily sales."""
        required = {self.PRODUCT_COLUMN, "Cantidad"}
        if self.data.empty or not required.issubset(self.data.columns):
            return pd.DataFrame(
                columns=["total_sold", "transaction_count", "daily_avg"]
            ).rename_axis(self.PRODUCT_COLUMN)

        velocity = self.data.groupby(self.PRODUCT_COLUMN).agg(
            total_sold=("Cantidad", "sum"),
            transaction_count=("Cantidad", "count"),
        )
        velocity["daily_avg"] = velocity["total_sold"] / self._period_days()
        return velocity

    def _period_days(self) -> float:
        """Observed sales window in days, from the actual date range."""
        if "Fecha" not in self.data.columns:
            return DEFAULT_PERIOD_DAYS
        fechas = pd.to_datetime(self.data["Fecha"], errors="coerce").dropna()
        if fechas.empty:
            return DEFAULT_PERIOD_DAYS
        return float(max((fechas.max() - fechas.min()).days + 1, 1))

    def _low_stock_from_balances(
        self, velocity: pd.DataFrame, limit: float
    ) -> pd.DataFrame:
        stock = (
            self.stock_data.groupby(self.PRODUCT_COLUMN)[self.STOCK_COLUMN]
            .sum()
            .rename("current_stock")
        )
        # The stock snapshot is authoritative: products without a balance row
        # have unknown stock (never invent stock), so they are not evaluated.
        merged = velocity.join(stock, how="right")
        for column in ("total_sold", "transaction_count", "daily_avg"):
            merged[column] = merged[column].fillna(0.0)

        low = merged[merged["current_stock"] <= limit].copy()
        low["days_of_cover"] = (low["current_stock"] / low["daily_avg"]).where(
            low["daily_avg"] > 0
        )
        low = low.sort_values(["days_of_cover", "current_stock"], na_position="last")
        return low.reset_index()
