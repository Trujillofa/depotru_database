"""
Financial Analysis Module
=========================

Financial metrics and KPIs calculation for business intelligence.

Features:
- Revenue calculations (with/without IVA)
- Cost analysis
- Gross profit and margin calculations
- Average and median order values
- Financial KPIs

Usage:
    from src.business_analyzer.analysis.financial import FinancialAnalyzer

    analyzer = FinancialAnalyzer(data)
    financial_metrics = analyzer.analyze()
"""

import statistics
from decimal import Decimal
from typing import Any, Dict, List


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


class FinancialAnalyzer:
    """
    Financial metrics and KPIs calculator.

    Provides comprehensive financial analysis including:
    - Revenue calculations (with and without IVA/tax)
    - Cost analysis
    - Gross profit calculations
    - Profit margin percentages
    - Average and median order values

    Attributes:
        data: List of transaction dictionaries

    Example:
        >>> analyzer = FinancialAnalyzer(transaction_data)
        >>> metrics = analyzer.analyze()
        >>> print(f"Total revenue: ${metrics['revenue']['total_with_iva']:,.2f}")
        >>> print(f"Gross margin: {metrics['profit']['gross_profit_margin']:.1f}%")
    """

    def __init__(self, data: List[Dict[str, Any]]):
        """
        Initialize the FinancialAnalyzer.

        Args:
            data: List of transaction dictionaries containing financial data
        """
        self.data = data

    def analyze(self) -> Dict[str, Any]:
        """
        Calculate comprehensive financial KPIs.

        Returns:
            Dictionary containing:
            - revenue: Revenue metrics (total with/without IVA, average, median)
            - costs: Cost metrics (total, average per unit)
            - profit: Profit metrics (gross profit, margin percentage)
        """
        revenues_with_iva = []
        revenues_without_iva = []
        costs = []

        for row in self.data:
            revenue_iva = extract_value(
                row, ["TotalMasIva", "PrecioTotal", "precio_total_iva"]
            )
            revenue_no_iva = extract_value(
                row, ["TotalSinIva", "PrecioUnitario", "precio_total"]
            )
            cost = extract_value(row, ["ValorCosto", "CostoUnitario", "cost", "costo"])

            if revenue_iva:
                revenues_with_iva.append(revenue_iva)
            if revenue_no_iva:
                revenues_without_iva.append(revenue_no_iva)
            if cost:
                costs.append(cost)

        metrics = {
            "revenue": {
                "total_with_iva": (
                    round(sum(revenues_with_iva), 2) if revenues_with_iva else 0.0
                ),
                "total_without_iva": (
                    round(sum(revenues_without_iva), 2) if revenues_without_iva else 0.0
                ),
                "average_order_value": (
                    round(statistics.mean(revenues_with_iva), 2)
                    if revenues_with_iva
                    else 0.0
                ),
                "median_order_value": (
                    round(statistics.median(revenues_with_iva), 2)
                    if revenues_with_iva
                    else 0.0
                ),
            },
            "costs": {
                "total_cost": round(sum(costs), 2) if costs else 0.0,
                "average_cost_per_unit": (
                    round(statistics.mean(costs), 2) if costs else 0.0
                ),
            },
            "profit": {},
        }

        if revenues_without_iva and costs:
            gross_profit = sum(revenues_without_iva) - sum(costs)
            metrics["profit"]["gross_profit"] = round(gross_profit, 2)
            metrics["profit"]["gross_profit_margin"] = round(
                safe_divide(gross_profit, sum(revenues_without_iva), default=0.0) * 100,
                2,
            )

        return metrics

    def calculate_iva_collected(self) -> float:
        """
        Calculate total IVA (tax) collected.

        Returns:
            Total IVA amount (revenue with IVA - revenue without IVA)
        """
        revenues_with_iva = []
        revenues_without_iva = []

        for row in self.data:
            revenue_iva = extract_value(
                row, ["TotalMasIva", "PrecioTotal", "precio_total_iva"]
            )
            revenue_no_iva = extract_value(
                row, ["TotalSinIva", "PrecioUnitario", "precio_total"]
            )

            if revenue_iva:
                revenues_with_iva.append(revenue_iva)
            if revenue_no_iva:
                revenues_without_iva.append(revenue_no_iva)

        total_with_iva = sum(revenues_with_iva) if revenues_with_iva else 0.0
        total_without_iva = sum(revenues_without_iva) if revenues_without_iva else 0.0

        return round(total_with_iva - total_without_iva, 2)

    def get_revenue_breakdown(self) -> Dict[str, float]:
        """
        Get revenue breakdown by type.

        Returns:
            Dictionary with revenue components
        """
        metrics = self.analyze()
        revenue = metrics.get("revenue", {})

        total_with_iva = revenue.get("total_with_iva", 0.0)
        total_without_iva = revenue.get("total_without_iva", 0.0)

        return {
            "sales_revenue": total_without_iva,
            "iva_tax": total_with_iva - total_without_iva,
            "total_with_iva": total_with_iva,
        }
