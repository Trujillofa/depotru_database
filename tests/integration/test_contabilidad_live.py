"""Live accounting invariants (requires J3System MSSQL)."""

from __future__ import annotations

import pytest

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_contabilidad import ContabilidadRunner


@pytest.fixture(scope="module")
def december_report():
    runner = ContabilidadRunner(Database())
    return runner.build_report("2024-12-01", "2024-12-31")


@pytest.mark.requires_db
@pytest.mark.integration
def test_december_2024_cuadre_baseline(december_report):
    summary = december_report["summary"]
    assert int(summary["Movimientos"]) == 14349
    assert int(summary["Lineas"]) == 127715
    assert int(summary["Cuadre_OK"]) == 1
    assert abs(float(summary["Diferencia_Cuadre"])) < 0.01


@pytest.mark.requires_db
@pytest.mark.integration
def test_pyg_has_three_classes(december_report):
    classes = {row["Clase_Puc"] for row in december_report["pyg_clase"]}
    assert classes == {"4", "5", "6"}


@pytest.mark.requires_db
@pytest.mark.integration
def test_conciliacion_ingresos_near_bi(december_report):
    conc = december_report["conciliacion_ingresos"]
    assert float(conc["Ingresos_Contables_41"]) > 8_000_000_000
    assert float(conc["Ventas_BI_Con_Iva"]) > 8_000_000_000
    assert abs(float(conc["Conciliacion_Ingresos_Pct"]) - 94.022298) < 0.1


@pytest.mark.requires_db
@pytest.mark.integration
def test_balance_has_three_classes(december_report):
    classes = {row["Clase_Puc"] for row in december_report["balance_clase"]}
    assert classes == {"1", "2", "3"}
    balance = december_report["balance_summary"]
    assert float(balance["Activo_Total"]) > 0
    assert float(balance["Pasivo_Total"]) > 0
    assert float(balance["Patrimonio_Total"]) > 0


@pytest.mark.requires_db
@pytest.mark.integration
def test_accounting_equation_adjusted_for_open_pyg(december_report):
    """Bruta gap ~$1.56B is explained by open PyG balances (classes 4–6)."""
    balance = december_report["balance_summary"]
    pyg_acum = december_report.get("pyg_acumulado_clase") or []
    assert len(pyg_acum) == 3
    assert abs(float(balance["Ecuacion_Diferencia_Bruta"]) - 1_558_791_907) < 1_000_000
    assert abs(float(balance["Resultado_PyG_Acumulado"]) - 1_558_791_907) < 1_000_000
    assert abs(float(balance["Ecuacion_Diferencia"])) < 500_000
    assert balance["Ecuacion_OK"] is True


@pytest.mark.requires_db
@pytest.mark.integration
def test_gastos_centro_has_sala_principal(december_report):
    centros = [
        r["SubCentroCostoNombre"].strip() for r in december_report["gastos_centro"]
    ]
    assert "SALA PRINCIPAL" in centros
