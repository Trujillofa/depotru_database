"""Live returns reconciliation invariants (requires MSSQL cross-db)."""

from __future__ import annotations

import pytest

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_devoluciones_conciliacion import (
    DevolucionesConciliacionRunner,
)


@pytest.fixture(scope="module")
def december_report():
    runner = DevolucionesConciliacionRunner(Database())
    return runner.build_report("2024-12-01", "2024-12-31")


@pytest.mark.requires_db
@pytest.mark.integration
def test_december_2024_perfect_unit_reconciliation(december_report):
    summary = december_report["summary"]
    assert int(summary["Unidades_ERP"]) == 9978
    assert int(summary["Unidades_BI"]) == 9978
    assert int(summary["Diferencia_Unidades"]) == 0
    assert float(summary["Conciliacion_Pct"]) == 100.0


@pytest.mark.requires_db
@pytest.mark.integration
def test_by_documento_dve_matches(december_report):
    dve = next(
        r for r in december_report["by_documento"] if r["DocumentosCodigo"] == "DVE"
    )
    assert int(dve["Unidades_ERP"]) == int(dve["Unidades_BI"])
    assert int(dve["Diferencia_Unidades"]) == 0


@pytest.mark.requires_db
@pytest.mark.integration
def test_category_rows_have_required_columns(december_report):
    assert december_report["by_category"]
    row = december_report["by_category"][0]
    assert "Categoria" in row
    assert "Unidades_ERP" in row
    assert "Unidades_BI" in row
    assert "Tasa_Devolucion_Validada_Pct" in row


@pytest.mark.requires_db
@pytest.mark.integration
def test_summary_matches_category_aggregation(december_report):
    from business_analyzer.core.j3system_devoluciones_conciliacion import (
        conciliacion_summary_from_category_rows,
    )

    aggregated = conciliacion_summary_from_category_rows(december_report["by_category"])
    summary = december_report["summary"]
    assert aggregated["Unidades_ERP"] == int(summary["Unidades_ERP"])
    assert aggregated["Unidades_BI"] == int(summary["Unidades_BI"])
