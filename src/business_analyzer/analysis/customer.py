"""
Customer Analysis Module
========================

Customer segmentation and analytics for business intelligence.

Features:
- Customer segmentation (VIP, High Value, Frequent, Regular, Occasional)
- RFM-style analysis (Revenue, Frequency)
- Customer concentration metrics
- Top customer identification

Usage:
    from src.business_analyzer.analysis.customer import CustomerAnalyzer

    analyzer = CustomerAnalyzer(data)
    customer_metrics = analyzer.analyze()
"""

from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List

from ...config import CustomerSegmentation


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


class CustomerAnalyzer:
    """
    Customer analytics and segmentation analyzer.

    Provides comprehensive customer analysis including:
    - Customer segmentation based on revenue and order frequency
    - Top customer identification
    - Customer concentration metrics
    - Average order value calculations

    Attributes:
        data: List of transaction dictionaries

    Example:
        >>> analyzer = CustomerAnalyzer(transaction_data)
        >>> metrics = analyzer.analyze()
        >>> print(metrics['total_customers'])
        150
    """

    def __init__(self, data: List[Dict[str, Any]]):
        """
        Initialize the CustomerAnalyzer.

        Args:
            data: List of transaction dictionaries containing customer data
        """
        self.data = data

    def analyze(self) -> Dict[str, Any]:
        """
        Perform comprehensive customer analytics.

        Returns:
            Dictionary containing:
            - top_customers: List of top 20 customers by revenue
            - total_customers: Total number of unique customers
            - customer_concentration: Top 10 customer revenue percentage
            - segmentation: Customer distribution by segment
        """
        customer_data = defaultdict(
            lambda: {
                "total_revenue": 0.0,
                "total_orders": 0,
                "products_purchased": set(),
                "dates": [],
            }
        )

        for row in self.data:
            customer = extract_value(
                row,
                ["TercerosNombres", "NombreCliente", "customer_name", "cliente"],
                default="Unknown",
            )
            revenue = extract_value(
                row, ["TotalMasIva", "PrecioTotal", "precio_total_iva"], default=0.0
            )
            product = extract_value(
                row,
                ["ArticulosNombre", "Descripcion", "product_name", "producto"],
                default="Unknown",
            )
            date = extract_value(row, ["Fecha", "date", "fecha"])

            customer_data[customer]["total_revenue"] += revenue
            customer_data[customer]["total_orders"] += 1
            customer_data[customer]["products_purchased"].add(product)
            if date:
                customer_data[customer]["dates"].append(date)

        customers_list = []
        for customer, data in customer_data.items():
            customers_list.append(
                {
                    "customer_name": customer,
                    "total_revenue": round(data["total_revenue"], 2),
                    "total_orders": data["total_orders"],
                    "average_order_value": round(
                        safe_divide(
                            data["total_revenue"], data["total_orders"], default=0.0
                        ),
                        2,
                    ),
                    "product_diversity": len(data["products_purchased"]),
                    "customer_segment": self._segment_customer(
                        data["total_revenue"], data["total_orders"]
                    ),
                }
            )

        customers_list.sort(key=lambda x: x["total_revenue"], reverse=True)

        total_revenue = sum(c["total_revenue"] for c in customers_list)
        top_10_revenue = sum(
            c["total_revenue"] for c in customers_list[: min(10, len(customers_list))]
        )

        return {
            "top_customers": customers_list[:20],
            "total_customers": len(customers_list),
            "customer_concentration": {
                "top_10_percentage": round(
                    safe_divide(top_10_revenue, total_revenue, default=0.0) * 100, 2
                )
            },
            "segmentation": self._aggregate_segments(customers_list),
        }

    def _segment_customer(self, revenue: float, orders: int) -> str:
        """
        Segment customer based on revenue and order frequency.

        Segments:
        - VIP: High revenue (>500k) AND high order frequency (>5)
        - High Value: Revenue >200k
        - Frequent: Orders >10
        - Regular: Revenue >50k
        - Occasional: Below all thresholds

        Args:
            revenue: Total customer revenue
            orders: Number of orders

        Returns:
            Segment name as string
        """
        if (
            revenue > CustomerSegmentation.VIP_REVENUE_THRESHOLD
            and orders > CustomerSegmentation.VIP_ORDERS_THRESHOLD
        ):
            return "VIP"
        elif revenue > CustomerSegmentation.HIGH_VALUE_THRESHOLD:
            return "High Value"
        elif orders > CustomerSegmentation.FREQUENT_ORDERS_THRESHOLD:
            return "Frequent"
        elif revenue > CustomerSegmentation.REGULAR_REVENUE_THRESHOLD:
            return "Regular"
        else:
            return "Occasional"

    def _aggregate_segments(self, customers: List[Dict]) -> Dict[str, int]:
        """
        Aggregate customer segmentation counts.

        Args:
            customers: List of customer dictionaries with 'customer_segment' key

        Returns:
            Dictionary mapping segment names to customer counts
        """
        segments = defaultdict(int)
        for customer in customers:
            segments[customer["customer_segment"]] += 1
        return dict(segments)

    def get_segment_thresholds(self) -> Dict[str, Any]:
        """
        Get current segmentation thresholds.

        Returns:
            Dictionary of threshold values used for segmentation
        """
        return {
            "vip_revenue": CustomerSegmentation.VIP_REVENUE_THRESHOLD,
            "vip_orders": CustomerSegmentation.VIP_ORDERS_THRESHOLD,
            "high_value": CustomerSegmentation.HIGH_VALUE_THRESHOLD,
            "frequent_orders": CustomerSegmentation.FREQUENT_ORDERS_THRESHOLD,
            "regular_revenue": CustomerSegmentation.REGULAR_REVENUE_THRESHOLD,
        }
