"""
Alerts module for Business Data Analyzer.

Identifies items below safety stock thresholds and provides inventory insights.
"""

from typing import Any, Dict, List

import pandas as pd


class InventoryAlerts:
    """
    Inventory Alert system to identify stock-outs and low inventory.
    """

    def __init__(self, data: pd.DataFrame):
        self.data = data
        self.default_buffer = 10  # Default safety stock units

    def analyze_low_stock(self, threshold: int = None) -> pd.DataFrame:
        """
        Identify products with low inventory based on a threshold.

        This is a placeholder implementation that simulates inventory analysis
        based on sales velocity if actual stock levels aren't in the primary table.
        """
        limit = threshold if threshold is not None else self.default_buffer

        # In a real scenario, we would join with an inventory table.
        # Here we calculate velocity as a proxy for stock needs.
        velocity = (
            self.data.groupby("ArticulosNombre")
            .agg({"Cantidad": "sum", "Fecha": "count"})
            .rename(columns={"Cantidad": "total_sold", "Fecha": "transaction_count"})
        )

        velocity["daily_avg"] = velocity["total_sold"] / 30  # Approximate monthly

        # Flag items needing attention (simplified logic)
        alerts = velocity[velocity["total_sold"] > limit].sort_values(
            "total_sold", ascending=False
        )

        return alerts

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of inventory alerts."""
        alerts = self.analyze_low_stock()

        return {
            "total_alerts": len(alerts),
            "high_priority": alerts.head(5).to_dict("records"),
            "threshold": self.default_buffer,
        }
