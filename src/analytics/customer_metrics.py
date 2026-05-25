from __future__ import annotations

from typing import Any, Callable, Dict, List, TypedDict

from .value_utils import as_float, as_int


class CustomerStats(TypedDict):
    total_revenue: float
    total_orders: int
    products_purchased: set[Any]
    dates: List[Any]


def analyze_customers(
    data: List[Dict[str, Any]],
    extract_value: Callable[..., Any],
    segment_customer: Callable[[float, int], str],
    aggregate_segments: Callable[[List[Dict[str, Any]]], Dict[str, int]],
    safe_divide: Callable[[float, float, float], float],
) -> Dict[str, Any]:
    customer_data: Dict[Any, CustomerStats] = {}

    for row in data:
        customer = extract_value(
            row,
            ["TercerosNombres", "NombreCliente", "customer_name", "cliente"],
            default="Unknown",
        )
        revenue = extract_value(
            row, ["TotalMasIva", "PrecioTotal", "precio_total_iva"], default=0
        )
        product = extract_value(
            row,
            ["ArticulosNombre", "Descripcion", "product_name", "producto"],
            default="Unknown",
        )
        date = extract_value(row, ["Fecha", "date", "fecha"])

        if customer not in customer_data:
            customer_data[customer] = {
                "total_revenue": 0.0,
                "total_orders": 0,
                "products_purchased": set(),
                "dates": [],
            }

        customer_data[customer]["total_revenue"] += as_float(revenue, 0.0)
        customer_data[customer]["total_orders"] += 1
        customer_data[customer]["products_purchased"].add(product)
        if date:
            customer_data[customer]["dates"].append(date)

    customers_list = []
    for customer, customer_metrics in customer_data.items():
        customers_list.append(
            {
                "customer_name": customer,
                "total_revenue": round(customer_metrics["total_revenue"], 2),
                "total_orders": customer_metrics["total_orders"],
                "average_order_value": round(
                    safe_divide(
                        customer_metrics["total_revenue"],
                        as_float(customer_metrics["total_orders"], 0.0),
                        0,
                    ),
                    2,
                ),
                "product_diversity": len(customer_metrics["products_purchased"]),
                "customer_segment": segment_customer(
                    as_float(customer_metrics["total_revenue"], 0.0),
                    as_int(customer_metrics["total_orders"], 0),
                ),
            }
        )

    customers_list.sort(key=lambda customer: customer["total_revenue"], reverse=True)

    total_revenue = sum(customer["total_revenue"] for customer in customers_list)
    top_10_revenue = sum(
        customer["total_revenue"]
        for customer in customers_list[: min(10, len(customers_list))]
    )

    return {
        "top_customers": customers_list[:20],
        "total_customers": len(customers_list),
        "customer_concentration": {
            "top_10_percentage": round(
                safe_divide(top_10_revenue, total_revenue, 0) * 100, 2
            )
        },
        "segmentation": aggregate_segments(customers_list),
    }
