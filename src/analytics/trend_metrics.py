from __future__ import annotations

from typing import Any, Callable, Dict, List

from .value_utils import as_float


def analyze_trends(
    data: List[Dict[str, Any]],
    extract_value: Callable[..., Any],
) -> Dict[str, Any]:
    monthly_data: Dict[str, Dict[str, float]] = {}
    category_data: Dict[Any, float] = {}

    for row in data:
        date = extract_value(row, ["Fecha", "date", "fecha"])
        revenue = extract_value(
            row, ["TotalMasIva", "PrecioTotal", "precio_total_iva"], default=0
        )
        category = extract_value(
            row, ["Categoria", "category", "categoria"], default="Uncategorized"
        )

        if date:
            month_key = (
                f"{date.year}-{date.month:02d}" if hasattr(date, "year") else "2025-10"
            )
            if month_key not in monthly_data:
                monthly_data[month_key] = {"revenue": 0.0, "transactions": 0.0}
            monthly_data[month_key]["revenue"] += as_float(revenue, 0.0)
            monthly_data[month_key]["transactions"] += 1.0

        category_data[category] = category_data.get(category, 0.0) + as_float(
            revenue, 0.0
        )

    return {
        "monthly_trends": dict(sorted(monthly_data.items())),
        "category_distribution": dict(
            sorted(
                category_data.items(), key=lambda category: category[1], reverse=True
            )
        ),
    }
