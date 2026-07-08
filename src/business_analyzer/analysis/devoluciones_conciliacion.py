"""Returns reconciliation analysis (re-exports from core)."""

from business_analyzer.core.j3system_devoluciones_conciliacion import (
    DevolucionesConciliacionRunner,
    conciliacion_summary_from_category_rows,
    top_margin_erosion_categories,
    top_reconciliation_gaps,
)

__all__ = [
    "DevolucionesConciliacionRunner",
    "conciliacion_summary_from_category_rows",
    "top_reconciliation_gaps",
    "top_margin_erosion_categories",
]
