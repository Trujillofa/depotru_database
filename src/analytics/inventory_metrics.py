from __future__ import annotations

from typing import Any, Callable, Dict, List

from .value_utils import as_float


def analyze_inventory(
    data: List[Dict[str, Any]],
    extract_value: Callable[..., Any],
    fast_mover_threshold: int,
    slow_mover_threshold: int,
) -> Dict[str, Any]:
    inventory: Dict[Any, Dict[str, float]] = {}

    for row in data:
        product = extract_value(
            row,
            ["ArticulosNombre", "Descripcion", "product_name"],
            default="Unknown",
        )
        quantity = extract_value(row, ["Cantidad", "quantity"], default=1)

        if product not in inventory:
            inventory[product] = {"total_sold": 0.0, "transactions": 0.0}

        inventory[product]["total_sold"] += as_float(quantity, 1.0)
        inventory[product]["transactions"] += 1.0

    fast_movers = []
    slow_movers = []

    for product, inventory_metrics in inventory.items():
        velocity = int(inventory_metrics["transactions"])
        total_sold = inventory_metrics["total_sold"]
        if velocity > fast_mover_threshold:
            fast_movers.append(
                {
                    "product": product,
                    "velocity": velocity,
                    "total_sold": total_sold,
                }
            )
        elif velocity < slow_mover_threshold:
            slow_movers.append(
                {
                    "product": product,
                    "velocity": velocity,
                    "total_sold": total_sold,
                }
            )

    return {
        "fast_moving_items": sorted(
            fast_movers, key=lambda product: product["velocity"], reverse=True
        )[:20],
        "slow_moving_items": sorted(
            slow_movers, key=lambda product: product["velocity"]
        )[:20],
    }
