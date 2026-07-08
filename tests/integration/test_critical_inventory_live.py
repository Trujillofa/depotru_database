"""Live critical inventory invariants (requires MSSQL cross-db)."""

from __future__ import annotations

import pytest

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_critical_inventory import CriticalInventoryRunner


@pytest.fixture(scope="module")
def december_report():
    runner = CriticalInventoryRunner(Database(), top_n=25)
    return runner.build_report("2024-12-31")


@pytest.mark.requires_db
@pytest.mark.integration
def test_december_2024_returns_critical_skus(december_report):
    skus = december_report["critical_skus"]
    assert len(skus) > 0
    row = skus[0]
    assert "SKU" in row
    assert "Saldo_Actual" in row
    assert "Cantidad_90d" in row
    assert "Dias_Cobertura" in row
    assert "Prioridad" in row


@pytest.mark.requires_db
@pytest.mark.integration
def test_summary_matches_detail_count(december_report):
    summary = december_report["summary"]
    assert summary["SKUs_Criticos"] == len(december_report["critical_skus"])


@pytest.mark.requires_db
@pytest.mark.integration
def test_by_warehouse_has_aggregates(december_report):
    rows = december_report["by_warehouse"]
    assert rows
    row = rows[0]
    assert "AlmacenCodigo" in row
    assert int(row["SKUs_Criticos"]) > 0


@pytest.mark.requires_db
@pytest.mark.integration
def test_coverage_days_non_negative_when_present(december_report):
    for row in december_report["critical_skus"]:
        dias = row.get("Dias_Cobertura")
        if dias is not None:
            assert float(dias) >= 0
