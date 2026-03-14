from __future__ import annotations

import statistics
from typing import Any, Dict, List

from .financial_rows import extract_financial_row_values
from .value_utils import as_float


def calculate_financial_metrics(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    revenues_with_iva: List[float] = []
    revenues_without_iva: List[float] = []
    costs: List[float] = []

    for row in data:
        row_values = extract_financial_row_values(row)
        revenue_iva = as_float(row_values["revenue_iva"], 0.0)
        revenue_no_iva = as_float(row_values["revenue_no_iva"], 0.0)
        cost = as_float(row_values["cost"], 0.0)

        if revenue_iva:
            revenues_with_iva.append(revenue_iva)
        if revenue_no_iva:
            revenues_without_iva.append(revenue_no_iva)
        if cost:
            costs.append(cost)

    metrics = {
        "revenue": {
            "total_with_iva": (
                round(sum(revenues_with_iva), 2) if revenues_with_iva else 0
            ),
            "total_without_iva": (
                round(sum(revenues_without_iva), 2) if revenues_without_iva else 0
            ),
            "average_order_value": (
                round(statistics.mean(revenues_with_iva), 2) if revenues_with_iva else 0
            ),
            "median_order_value": (
                round(statistics.median(revenues_with_iva), 2)
                if revenues_with_iva
                else 0
            ),
        },
        "costs": {
            "total_cost": round(sum(costs), 2) if costs else 0,
            "average_cost_per_unit": round(statistics.mean(costs), 2) if costs else 0,
        },
        "profit": {},
    }

    if revenues_without_iva and costs:
        gross_profit = sum(revenues_without_iva) - sum(costs)
        metrics["profit"]["gross_profit"] = round(gross_profit, 2)
        metrics["profit"]["gross_profit_margin"] = round(
            (
                gross_profit / sum(revenues_without_iva)
                if sum(revenues_without_iva) != 0
                else 0
            )
            * 100,
            2,
        )

    return metrics
