"""Tests for returns reconciliation re-exports."""

from business_analyzer.analysis.devoluciones_conciliacion import (
    DevolucionesConciliacionRunner,
    conciliacion_summary_from_category_rows,
    top_margin_erosion_categories,
    top_reconciliation_gaps,
)


def test_reexports():
    assert DevolucionesConciliacionRunner is not None
    assert callable(conciliacion_summary_from_category_rows)
    assert callable(top_reconciliation_gaps)
    assert callable(top_margin_erosion_categories)
