from __future__ import annotations

from typing import Any, Callable, Dict, List

from .value_utils import as_float


def analyze_profitability(
    data: List[Dict[str, Any]],
    extract_value: Callable[..., Any],
    safe_divide: Callable[[float, float, float], float],
) -> Dict[str, Any]:
    by_category: Dict[Any, Dict[str, float]] = {}

    for row in data:
        revenue = extract_value(
            row, ["TotalSinIva", "PrecioUnitario", "precio_total"], default=0
        )
        cost = extract_value(
            row, ["ValorCosto", "CostoUnitario", "cost", "costo"], default=0
        )
        category = extract_value(
            row, ["Categoria", "category"], default="Uncategorized"
        )

        if category not in by_category:
            by_category[category] = {"revenue": 0.0, "cost": 0.0}

        by_category[category]["revenue"] += as_float(revenue, 0.0)
        by_category[category]["cost"] += as_float(cost, 0.0)

    category_margins = {}
    for category, profitability_metrics in by_category.items():
        profit = profitability_metrics["revenue"] - profitability_metrics["cost"]
        margin = safe_divide(profit, profitability_metrics["revenue"], 0) * 100
        category_margins[category] = {
            "revenue": round(profitability_metrics["revenue"], 2),
            "profit": round(profit, 2),
            "margin": round(margin, 2),
        }

    return {
        "by_category": dict(
            sorted(
                category_margins.items(),
                key=lambda category: category[1]["margin"],
                reverse=True,
            )
        )
    }
