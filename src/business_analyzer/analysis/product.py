"""
Product Analysis Module
=======================

Product performance and profitability analytics.

Features:
- Top selling products identification
- Profit margin calculations
- Product categorization (star products, underperformers)
- SKU tracking

Usage:
    from src.business_analyzer.analysis.product import ProductAnalyzer

    analyzer = ProductAnalyzer(data)
    product_metrics = analyzer.analyze()
"""

from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List

from ...config import ProfitabilityConfig


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Perform division with zero-check to prevent crashes.

    Args:
        numerator: The dividend
        denominator: The divisor
        default: Value to return if denominator is zero (default: 0.0)

    Returns:
        Result of division, or default if denominator is zero
    """
    return numerator / denominator if denominator != 0 else default


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


class ProductAnalyzer:
    """
    Product performance and profitability analyzer.

    Provides comprehensive product analysis including:
    - Top selling products by revenue
    - Profit margin calculations
    - Star product identification (>30% margin)
    - Underperforming product identification (<10% margin)
    - Transaction frequency analysis

    Attributes:
        data: List of transaction dictionaries

    Example:
        >>> analyzer = ProductAnalyzer(transaction_data)
        >>> metrics = analyzer.analyze()
        >>> print(f"Total products: {metrics['total_products']}")
        >>> print(f"Star products: {len(metrics['star_products'])}")
    """

    def __init__(self, data: List[Dict[str, Any]]):
        """
        Initialize the ProductAnalyzer.

        Args:
            data: List of transaction dictionaries containing product data
        """
        self.data = data

    def analyze(self) -> Dict[str, Any]:
        """
        Perform comprehensive product analytics.

        Returns:
            Dictionary containing:
            - top_products: List of top 30 products by revenue
            - total_products: Total number of unique products
            - underperforming_products: Products with <10% margin
            - star_products: Products with >30% margin (top 10)
        """
        product_data = defaultdict(
            lambda: {
                "sku": "",
                "total_revenue": 0.0,
                "total_cost": 0.0,
                "total_quantity": 0,
                "transactions": 0,
            }
        )

        for row in self.data:
            product = extract_value(
                row,
                ["ArticulosNombre", "Descripcion", "product_name", "producto"],
                default="Unknown",
            )
            sku = extract_value(row, ["ArticulosCodigo"], default="")
            revenue = extract_value(row, ["TotalSinIva"], default=0.0)
            cost = extract_value(row, ["ValorCosto"], default=0.0)
            quantity = extract_value(
                row, ["Cantidad", "quantity", "cantidad"], default=1
            )

            product_data[product]["sku"] = sku
            product_data[product]["total_revenue"] += revenue
            product_data[product]["total_cost"] += cost
            product_data[product]["total_quantity"] += quantity
            product_data[product]["transactions"] += 1

        products_list = []
        for product, data in product_data.items():
            profit = data["total_revenue"] - data["total_cost"]
            profit_margin = (
                safe_divide(profit, data["total_revenue"], default=0.0) * 100
            )

            products_list.append(
                {
                    "product_name": product,
                    "sku": data["sku"],
                    "total_revenue": round(data["total_revenue"], 2),
                    "total_quantity": data["total_quantity"],
                    "profit": round(profit, 2),
                    "profit_margin": round(profit_margin, 2),
                    "transactions": data["transactions"],
                }
            )

        products_list.sort(key=lambda x: x["total_revenue"], reverse=True)

        return {
            "top_products": products_list[:30],
            "total_products": len(products_list),
            "underperforming_products": [
                p
                for p in products_list
                if p["profit_margin"] < ProfitabilityConfig.LOW_MARGIN_THRESHOLD
            ],
            "star_products": [
                p
                for p in products_list
                if p["profit_margin"] > ProfitabilityConfig.STAR_PRODUCT_MARGIN
            ][:10],
        }

    def get_profitability_thresholds(self) -> Dict[str, float]:
        """
        Get current profitability thresholds.

        Returns:
            Dictionary of threshold values used for product classification
        """
        return {
            "low_margin": ProfitabilityConfig.LOW_MARGIN_THRESHOLD,
            "star_product": ProfitabilityConfig.STAR_PRODUCT_MARGIN,
            "critical": ProfitabilityConfig.CRITICAL_MARGIN,
        }

    def analyze_product_by_name(self, product_name: str) -> Dict[str, Any]:
        """
        Analyze a specific product by name.

        Args:
            product_name: Name of the product to analyze

        Returns:
            Product metrics dictionary or None if not found
        """
        all_products = self.analyze()["top_products"]
        for product in all_products:
            if product["product_name"] == product_name:
                return product
        return None
