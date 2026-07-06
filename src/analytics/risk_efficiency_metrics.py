from __future__ import annotations

import statistics
from typing import Any, Callable, Dict, List


def calculate_risk_metrics() -> Dict[str, Any]:
    return {
        "customer_concentration_risk": "Moderate",
        "supplier_concentration_risk": "Moderate",
        "note": "Monitor concentration to avoid dependency",
    }


def calculate_operational_efficiency(
    data: List[Dict[str, Any]],
    extract_value: Callable[..., Any],
) -> Dict[str, Any]:
    total_transactions = len(data)
    revenues = [
        extract_value(row, ["PrecioTotal", "precio_total_iva"], default=0)
        for row in data
    ]

    return {
        "total_transactions": total_transactions,
        "revenue_per_transaction": (
            round(statistics.mean(revenues), 2) if revenues else 0
        ),
    }
