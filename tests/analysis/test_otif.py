"""Tests for OTIF analysis re-exports."""

from business_analyzer.analysis.otif import (
    OtifRunner,
    otif_summary_from_warehouse_rows,
    worst_otif_customers,
    worst_otif_warehouses,
)


def test_reexports():
    assert OtifRunner is not None
    assert callable(otif_summary_from_warehouse_rows)
    assert callable(worst_otif_warehouses)
    assert callable(worst_otif_customers)
