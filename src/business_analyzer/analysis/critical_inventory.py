"""Critical inventory analysis (re-exports from core)."""

from business_analyzer.core.j3system_critical_inventory import (
    CriticalInventoryRunner,
    critical_inventory_summary_from_rows,
    top_critical_by_warehouse,
)

__all__ = [
    "CriticalInventoryRunner",
    "critical_inventory_summary_from_rows",
    "top_critical_by_warehouse",
]
