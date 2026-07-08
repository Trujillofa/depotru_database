"""Unit tests for contabilidad shaping in manager report."""

from business_analyzer.analysis.manager_report.aggregations import (
    contabilidad_from_runner_report,
)


def test_contabilidad_from_runner_report_shapes_pyg_and_conciliacion():
    raw = {
        "period": {"start": "2024-12-01", "end": "2024-12-31"},
        "summary": {
            "Movimientos": 10,
            "Lineas": 100,
            "Total_Debitos": 1_000.0,
            "Total_Creditos": 1_000.0,
            "Cuadre_OK": 1,
        },
        "pyg_clase": [],
        "pyg_summary": {
            "Ingresos_Creditos": 800.0,
            "Costos_Debitos": 500.0,
            "Gastos_Debitos": 100.0,
            "Margen_Bruto_Contable": 300.0,
            "Margen_Contable_Pct": 37.5,
        },
        "conciliacion_ingresos": {
            "Ingresos_Contables_41": 790.0,
            "Ventas_BI_Con_Iva": 750.0,
            "Ventas_BI_Sin_Iva": 630.0,
            "Diferencia_Con_Iva": 40.0,
            "Conciliacion_Ingresos_Pct": 94.9,
        },
        "gastos_centro": [],
        "top_gastos": [],
    }

    result = contabilidad_from_runner_report(raw)

    assert result["available"] is True
    assert result["summary"]["cuadre_ok"] is True
    assert result["pyg_summary"]["margen_contable_pct"] == 37.5
    assert result["conciliacion_ingresos"]["conciliacion_pct"] == 94.9


def test_contabilidad_from_runner_report_empty_movimientos():
    result = contabilidad_from_runner_report({"summary": {"Movimientos": 0}})

    assert result["available"] is False
    assert "Sin movimientos" in (result.get("note") or "")
