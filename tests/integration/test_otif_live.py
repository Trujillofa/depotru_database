"""Live OTIF invariants (requires J3System MSSQL)."""

from __future__ import annotations

import pytest

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_otif import OtifRunner


@pytest.fixture(scope="module")
def december_report():
    runner = OtifRunner(Database())
    return runner.build_report("2024-12-01", "2024-12-31")


@pytest.mark.requires_db
@pytest.mark.integration
def test_december_2024_summary_baseline(december_report):
    summary = december_report["summary"]
    assert int(summary["Total_Entregas"]) == 28985
    assert int(summary["Entregas_A_Tiempo"]) == 19788
    assert int(summary["Entregas_Tarde"]) == 9197
    assert abs(float(summary["OTIF_Pct"]) - 68.269794721407) < 0.1
    assert abs(float(summary["Lead_Time_Promedio_Dias"]) - 1.4337070898740727) < 0.1
    assert abs(float(summary["Fill_Rate_Pct"]) - 98.682076936346) < 0.1


@pytest.mark.requires_db
@pytest.mark.integration
def test_warehouse_rows_balance_on_time_late(december_report):
    for row in december_report["by_warehouse"]:
        total = int(row["Total_Entregas"])
        on_time = int(row["Entregas_A_Tiempo"])
        late = int(row["Entregas_Tarde"])
        assert on_time + late == total
        rate = float(row["OTIF_Pct"])
        assert 0 <= rate <= 100


@pytest.mark.requires_db
@pytest.mark.integration
def test_worst_customers_sorted_by_otif(december_report):
    customers = december_report["worst_customers"]
    assert customers
    rates = [float(c["OTIF_Pct"]) for c in customers]
    assert rates == sorted(rates)


@pytest.mark.requires_db
@pytest.mark.integration
def test_summary_matches_warehouse_aggregation(december_report):
    from business_analyzer.core.j3system_otif import otif_summary_from_warehouse_rows

    aggregated = otif_summary_from_warehouse_rows(december_report["by_warehouse"])
    summary = december_report["summary"]
    assert aggregated["Total_Entregas"] == int(summary["Total_Entregas"])
    assert aggregated["Entregas_A_Tiempo"] == int(summary["Entregas_A_Tiempo"])
    assert abs(aggregated["OTIF_Pct"] - float(summary["OTIF_Pct"])) < 0.05
