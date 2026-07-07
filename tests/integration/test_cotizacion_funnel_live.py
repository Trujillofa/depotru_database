"""Live cotización funnel invariants (requires J3System MSSQL)."""

from __future__ import annotations

import pytest

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_cotizacion_funnel import CotizacionFunnelRunner


@pytest.fixture(scope="module")
def december_report():
    runner = CotizacionFunnelRunner(Database())
    return runner.build_report("2024-12-01", "2024-12-31")


@pytest.mark.requires_db
@pytest.mark.integration
def test_december_2024_summary_baseline(december_report):
    summary = december_report["summary"]
    assert int(summary["Cotizaciones"]) == 1920
    assert int(summary["Convertidas"]) == 477
    assert int(summary["Perdidas"]) == 1443
    assert abs(float(summary["Tasa_Conversion_Pct"]) - 24.84375) < 0.1


@pytest.mark.requires_db
@pytest.mark.integration
def test_vendor_rows_balance_convertidas_perdidas(december_report):
    for row in december_report["by_vendor"]:
        cot = int(row["Cotizaciones"])
        conv = int(row["Convertidas"])
        lost = int(row["Perdidas"])
        assert conv + lost == cot
        assert conv <= cot
        rate = float(row["Tasa_Conversion_Pct"])
        assert 0 <= rate <= 100


@pytest.mark.requires_db
@pytest.mark.integration
def test_summary_matches_vendor_aggregation(december_report):
    from business_analyzer.core.j3system_cotizacion_funnel import (
        funnel_summary_from_vendor_rows,
    )

    aggregated = funnel_summary_from_vendor_rows(december_report["by_vendor"])
    summary = december_report["summary"]
    assert aggregated["Cotizaciones"] == int(summary["Cotizaciones"])
    assert aggregated["Convertidas"] == int(summary["Convertidas"])
    assert aggregated["Perdidas"] == int(summary["Perdidas"])
