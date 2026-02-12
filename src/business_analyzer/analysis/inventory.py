"""
Inventory Analysis Module
=========================

Inventory velocity and optimization analytics.

Features:
- Fast moving items identification
- Slow moving items identification
- Inventory velocity tracking
- Transaction frequency analysis

Usage:
    from src.business_analyzer.analysis.inventory import InventoryAnalyzer

    analyzer = InventoryAnalyzer(data)
    inventory_metrics = analyzer.analyze()
"""

from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List

from ...config import InventoryConfig


def extract_value(row: Dict, keys: List[str], default=None):
    """Extract value from row using multiple possible keys."""
    for key in keys:
        if key in row and row[key] is not None:
            value = row[key]
            # Handle Decimal types from pymssql
            if isinstance(value, Decimal):
                return float(value)
            # Handle string numbers (but not dates like "2025-01-01")
            if isinstance(value, str):
                # Check if it's a date string (contains hyphens in date format)
                if len(value) > 4 and value[4:5] == "-" and value.count("-") >= 2:
                    return value  # Return date strings as-is
                # Check if it's a numeric string
                cleaned = value.replace(".", "").replace(",", "").replace("-", "")
                if cleaned.isdigit():
                    return float(value.replace(",", ""))
            return value
    return default


class InventoryAnalyzer:
    """
    Inventory velocity and optimization analyzer.

    Provides comprehensive inventory analysis including:
    - Fast moving items identification (>5 transactions)
    - Slow moving items identification (<2 transactions)
    - Inventory velocity tracking
    - Total quantity sold per product

    Attributes:
        data: List of transaction dictionaries

    Example:
        >>> analyzer = InventoryAnalyzer(transaction_data)
        >>> metrics = analyzer.analyze()
        >>> print(f"Fast movers: {len(metrics['fast_moving_items'])}")
        >>> print(f"Slow movers: {len(metrics['slow_moving_items'])}")
    """

    def __init__(self, data: List[Dict[str, Any]]):
        """
        Initialize the InventoryAnalyzer.

        Args:
            data: List of transaction dictionaries containing inventory data
        """
        self.data = data

    def analyze(self) -> Dict[str, Any]:
        """
        Perform inventory velocity analytics.

        Returns:
            Dictionary containing:
            - fast_moving_items: Top 20 products with highest transaction velocity
            - slow_moving_items: Bottom 20 products with lowest transaction velocity
        """
        inventory = defaultdict(lambda: {"total_sold": 0, "transactions": 0})

        for row in self.data:
            product = extract_value(
                row,
                ["ArticulosNombre", "Descripcion", "product_name"],
                default="Unknown",
            )
            quantity = extract_value(row, ["Cantidad", "quantity"], default=1)

            inventory[product]["total_sold"] += quantity
            inventory[product]["transactions"] += 1

        fast_movers = []
        slow_movers = []

        for product, data in inventory.items():
            if data["transactions"] > InventoryConfig.FAST_MOVER_THRESHOLD:
                fast_movers.append(
                    {
                        "product": product,
                        "velocity": data["transactions"],
                        "total_sold": data["total_sold"],
                    }
                )
            elif data["transactions"] < InventoryConfig.SLOW_MOVER_THRESHOLD:
                slow_movers.append(
                    {
                        "product": product,
                        "velocity": data["transactions"],
                        "total_sold": data["total_sold"],
                    }
                )

        return {
            "fast_moving_items": sorted(
                fast_movers, key=lambda x: x["velocity"], reverse=True
            )[:20],
            "slow_moving_items": sorted(slow_movers, key=lambda x: x["velocity"])[:20],
        }

    def get_velocity_thresholds(self) -> Dict[str, int]:
        """
        Get current velocity thresholds.

        Returns:
            Dictionary of threshold values used for velocity classification
        """
        return {
            "fast_mover": InventoryConfig.FAST_MOVER_THRESHOLD,
            "slow_mover": InventoryConfig.SLOW_MOVER_THRESHOLD,
        }

    def analyze_product_velocity(self, product_name: str) -> Dict[str, Any]:
        """
        Analyze velocity for a specific product.

        Args:
            product_name: Name of the product to analyze

        Returns:
            Product velocity metrics or None if not found
        """
        inventory = defaultdict(lambda: {"total_sold": 0, "transactions": 0})

        for row in self.data:
            product = extract_value(
                row,
                ["ArticulosNombre", "Descripcion", "product_name"],
                default="Unknown",
            )
            quantity = extract_value(row, ["Cantidad", "quantity"], default=1)

            inventory[product]["total_sold"] += quantity
            inventory[product]["transactions"] += 1

        if product_name in inventory:
            data = inventory[product_name]
            velocity_class = "normal"
            if data["transactions"] > InventoryConfig.FAST_MOVER_THRESHOLD:
                velocity_class = "fast"
            elif data["transactions"] < InventoryConfig.SLOW_MOVER_THRESHOLD:
                velocity_class = "slow"

            return {
                "product": product_name,
                "velocity": data["transactions"],
                "total_sold": data["total_sold"],
                "velocity_class": velocity_class,
            }

        return None

    def get_inventory_summary(self) -> Dict[str, Any]:
        """
        Get overall inventory summary statistics.

        Returns:
            Dictionary with inventory summary metrics
        """
        inventory = defaultdict(lambda: {"total_sold": 0, "transactions": 0})

        for row in self.data:
            product = extract_value(
                row,
                ["ArticulosNombre", "Descripcion", "product_name"],
                default="Unknown",
            )
            quantity = extract_value(row, ["Cantidad", "quantity"], default=1)

            inventory[product]["total_sold"] += quantity
            inventory[product]["transactions"] += 1

        total_products = len(inventory)
        fast_count = sum(
            1
            for data in inventory.values()
            if data["transactions"] > InventoryConfig.FAST_MOVER_THRESHOLD
        )
        slow_count = sum(
            1
            for data in inventory.values()
            if data["transactions"] < InventoryConfig.SLOW_MOVER_THRESHOLD
        )
        normal_count = total_products - fast_count - slow_count

        return {
            "total_products": total_products,
            "fast_movers": fast_count,
            "slow_movers": slow_count,
            "normal_velocity": normal_count,
            "fast_percentage": round(fast_count / total_products * 100, 2)
            if total_products
            else 0.0,
            "slow_percentage": round(slow_count / total_products * 100, 2)
            if total_products
            else 0.0,
        }
