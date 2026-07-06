from __future__ import annotations

from typing import Any, Callable, Dict, List, TypedDict

from .value_utils import as_float


class SubcategoryStats(TypedDict):
    revenue: float
    cost: float
    orders: int


class CategoryStats(TypedDict):
    total_revenue: float
    total_cost: float
    orders: int
    subcategories: Dict[Any, SubcategoryStats]


def analyze_categories(
    data: List[Dict[str, Any]],
    extract_value: Callable[..., Any],
    safe_divide: Callable[[float, float, float], float],
) -> Dict[str, Any]:
    category_data: Dict[Any, CategoryStats] = {}

    for row in data:
        categoria = extract_value(row, ["categoria"], default="Unknown")
        subcategoria = extract_value(row, ["subcategoria"], default="Unknown")
        revenue = extract_value(row, ["TotalSinIva"], default=0)
        cost = extract_value(row, ["ValorCosto"], default=0)

        if categoria not in category_data:
            category_data[categoria] = {
                "total_revenue": 0.0,
                "total_cost": 0.0,
                "orders": 0,
                "subcategories": {},
            }
        if subcategoria not in category_data[categoria]["subcategories"]:
            category_data[categoria]["subcategories"][subcategoria] = {
                "revenue": 0.0,
                "cost": 0.0,
                "orders": 0,
            }

        category_data[categoria]["total_revenue"] += as_float(revenue, 0.0)
        category_data[categoria]["total_cost"] += as_float(cost, 0.0)
        category_data[categoria]["orders"] += 1
        category_data[categoria]["subcategories"][subcategoria]["revenue"] += as_float(
            revenue, 0.0
        )
        category_data[categoria]["subcategories"][subcategoria]["cost"] += as_float(
            cost, 0.0
        )
        category_data[categoria]["subcategories"][subcategoria]["orders"] += 1

    categories_list = []
    for categoria, category_metrics in category_data.items():
        profit = category_metrics["total_revenue"] - category_metrics["total_cost"]
        profit_margin = safe_divide(profit, category_metrics["total_revenue"], 0) * 100

        subcats = []
        for subcat, subdata in category_metrics["subcategories"].items():
            subcats.append(
                {
                    "subcategory": subcat,
                    "revenue": round(subdata["revenue"], 2),
                    "orders": subdata["orders"],
                }
            )
        subcats.sort(key=lambda subcategory: subcategory["revenue"], reverse=True)

        categories_list.append(
            {
                "category_name": categoria,
                "total_revenue": round(category_metrics["total_revenue"], 2),
                "total_cost": round(category_metrics["total_cost"], 2),
                "profit": round(profit, 2),
                "profit_margin": round(profit_margin, 2),
                "order_count": category_metrics["orders"],
                "risk_level": (
                    "CRITICAL"
                    if profit_margin < 0
                    else (
                        "HIGH"
                        if profit_margin < 10
                        else "MEDIUM"
                        if profit_margin < 20
                        else "LOW"
                    )
                ),
                "top_subcategories": subcats[:5],
            }
        )

    categories_list.sort(key=lambda category: category["total_revenue"], reverse=True)

    return {
        "category_performance": categories_list,
        "total_categories": len(categories_list),
    }
