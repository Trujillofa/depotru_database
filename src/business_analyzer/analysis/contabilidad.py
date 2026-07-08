"""Accounting analysis (re-exports from core)."""

from business_analyzer.core.j3system_contabilidad import (
    ContabilidadRunner,
    conciliacion_ingresos_from_row,
    pyg_summary_from_clase_rows,
)

__all__ = [
    "ContabilidadRunner",
    "pyg_summary_from_clase_rows",
    "conciliacion_ingresos_from_row",
]
