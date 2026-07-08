"""Tests for critical inventory analysis re-exports."""

from business_analyzer.analysis.critical_inventory import (
    CriticalInventoryRunner,
    critical_inventory_summary_from_rows,
    top_critical_by_warehouse,
)


def test_reexports():
    assert CriticalInventoryRunner is not None
    assert callable(critical_inventory_summary_from_rows)
    assert callable(top_critical_by_warehouse)
