from __future__ import annotations

from typing import Any, Callable, Dict, List, TypedDict

from .value_utils import as_float


class ProductStats(TypedDict):
    sku: str
    total_revenue: float
    total_cost: float
    total_quantity: float
    transactions: int


def analyze_products(
    data: List[Dict[str, Any]],
    extract_value: Callable[..., Any],
    safe_divide: Callable[[float, float, float], float],
    low_margin_threshold: float,
    star_product_margin: float,
) -> Dict[str, Any]:
    product_data: Dict[Any, ProductStats] = {}

    for row in data:
        product = extract_value(
            row,
            ["ArticulosNombre", "Descripcion", "product_name", "producto"],
            default="Unknown",
        )
        sku = extract_value(row, ["ArticulosCodigo"], default="")
        revenue = extract_value(row, ["TotalSinIva"], default=0)
        cost = extract_value(row, ["ValorCosto"], default=0)
        quantity = extract_value(row, ["Cantidad", "quantity", "cantidad"], default=1)

        if product not in product_data:
            product_data[product] = {
                "sku": "",
                "total_revenue": 0.0,
                "total_cost": 0.0,
                "total_quantity": 0.0,
                "transactions": 0,
            }

        product_data[product]["sku"] = sku
        product_data[product]["total_revenue"] += as_float(revenue, 0.0)
        product_data[product]["total_cost"] += as_float(cost, 0.0)
        product_data[product]["total_quantity"] += as_float(quantity, 1.0)
        product_data[product]["transactions"] += 1

    products_list = []
    for product, product_metrics in product_data.items():
        profit = product_metrics["total_revenue"] - product_metrics["total_cost"]
        profit_margin = safe_divide(profit, product_metrics["total_revenue"], 0) * 100

        products_list.append(
            {
                "product_name": product,
                "sku": product_metrics["sku"],
                "total_revenue": round(product_metrics["total_revenue"], 2),
                "total_quantity": product_metrics["total_quantity"],
                "profit": round(profit, 2),
                "profit_margin": round(profit_margin, 2),
                "transactions": product_metrics["transactions"],
            }
        )

    products_list.sort(key=lambda product: product["total_revenue"], reverse=True)

    return {
        "top_products": products_list[:30],
        "total_products": len(products_list),
        "underperforming_products": [
            product
            for product in products_list
            if product["profit_margin"] < low_margin_threshold
        ],
        "star_products": [
            product
            for product in products_list
            if product["profit_margin"] > star_product_margin
        ][:10],
    }
