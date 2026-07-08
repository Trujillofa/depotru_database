"""Live electronic invoice compliance invariants (requires J3System MSSQL)."""

from __future__ import annotations

import pytest

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_factura_electronica import (
    FacturaElectronicaRunner,
    factura_electronica_summary_from_documento_rows,
)


@pytest.fixture(scope="module")
def december_report():
    runner = FacturaElectronicaRunner(Database())
    return runner.build_report("2024-12-01", "2024-12-31")


@pytest.mark.requires_db
@pytest.mark.integration
def test_december_2024_perfect_acceptance_baseline(december_report):
    summary = december_report["summary"]
    assert int(summary["Emitidas"]) == 9961
    assert int(summary["Aceptadas"]) == 9961
    assert int(summary["Rechazadas"]) == 0
    assert float(summary["Tasa_Aceptacion_Pct"]) == 100.0
    assert float(summary["Tasa_Rechazo_Pct"]) == 0.0


@pytest.mark.requires_db
@pytest.mark.integration
def test_by_documento_rows_balance_acceptance(december_report):
    for row in december_report["by_documento"]:
        emitidas = int(row["Emitidas"])
        aceptadas = int(row["Aceptadas"])
        rechazadas = int(row["Rechazadas"])
        assert aceptadas + rechazadas == emitidas
        rate = float(row["Tasa_Aceptacion_Pct"])
        assert 0 <= rate <= 100


@pytest.mark.requires_db
@pytest.mark.integration
def test_no_rechazos_in_december_2024(december_report):
    assert december_report["rechazos"] == []


@pytest.mark.requires_db
@pytest.mark.integration
def test_summary_matches_documento_aggregation(december_report):
    aggregated = factura_electronica_summary_from_documento_rows(
        december_report["by_documento"]
    )
    summary = december_report["summary"]
    assert aggregated["Emitidas"] == int(summary["Emitidas"])
    assert aggregated["Aceptadas"] == int(summary["Aceptadas"])
    assert (
        abs(aggregated["Tasa_Aceptacion_Pct"] - float(summary["Tasa_Aceptacion_Pct"]))
        < 0.01
    )
