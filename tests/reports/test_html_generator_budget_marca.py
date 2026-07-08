"""HTML report sections for presupuesto and marca real."""

from business_analyzer.reports.html_generator import HTMLReportGenerator


def test_html_includes_budget_and_marca_real_sections(tmp_path):
    data = {
        "metadata": {"year": 2024, "month_name": "Mayo"},
        "summary": {"gross_margin_pct": 25.0},
        "formatted": {
            "summary": {
                "total_revenue_with_iva": "$1.000.000",
                "total_revenue_without_iva": "$840.000",
                "gross_profit": "$200.000",
                "gross_margin_pct": "25,0%",
                "total_quantity_sold": "100",
                "order_count": "40",
                "average_order_value": "$25.000",
                "average_order_profit": "$5.000",
            },
            "marca_sales": [
                {
                    "marca_name": "SIKA",
                    "total_revenue": "$100.000",
                    "revenue_pct": "10,0%",
                    "profit_margin_pct": "30,0%",
                }
            ],
            "budget_vs_actual": {
                "available": True,
                "periodo": 202405,
                "summary": {
                    "presupuesto_total": "$1.000.000",
                    "ventas_reales_total": "$850.000",
                    "cumplimiento_pct": "85,0%",
                    "brecha_total": "$150.000",
                },
                "sellers": [
                    {
                        "vendedor_nombre": "Vendedor A",
                        "vendedor_codigo": "095",
                        "presupuesto": "$500.000",
                        "ventas_reales": "$400.000",
                        "cumplimiento_pct": "80,0%",
                        "brecha": "$100.000",
                    }
                ],
                "underperformers": [],
            },
            "contabilidad": {
                "available": True,
                "note": None,
                "period": {"start": "2024-05-01", "end": "2024-05-31"},
                "metric_help": {
                    "balance_intro": "Saldos acumulados al cierre.",
                    "pyg_intro": "Movimientos del periodo.",
                    "conciliacion_ingresos": "Compara PUC 41 vs BI.",
                },
                "balance_summary": {
                    "activo_total": "$2.000.000",
                    "pasivo_total": "$800.000",
                    "patrimonio_total": "$1.200.000",
                    "pasivo_mas_patrimonio": "$2.000.000",
                    "ecuacion_diferencia": "$0",
                    "ecuacion_ok": True,
                    "corte_fecha": "2024-05-31",
                    "ecuacion_label": "Ecuación contable",
                },
                "balance_clase": [
                    {
                        "clase_puc": "1",
                        "tipo_cuenta": "Activo",
                        "total_debitos": "$2.500.000",
                        "total_creditos": "$500.000",
                        "saldo_acumulado": "$2.000.000",
                    }
                ],
                "summary": {
                    "movimientos": "100",
                    "lineas": "500",
                    "total_debitos": "$1.000.000",
                    "total_creditos": "$1.000.000",
                    "cuadre_ok": True,
                },
                "pyg_summary": {
                    "ingresos_creditos": "$500.000",
                    "costos_debitos": "$300.000",
                    "gastos_debitos": "$50.000",
                    "margen_bruto_contable": "$200.000",
                    "margen_contable_pct": "40,0%",
                    "ingresos_label": "Ingresos operacionales (clase 4)",
                    "costos_label": "Costos de ventas (clase 6)",
                    "gastos_label": "Gastos operativos (clase 5)",
                    "margen_label": "Margen bruto contable",
                    "margen_help": "Ingresos menos costos.",
                },
                "conciliacion_ingresos": {
                    "ingresos_contables_41": "$480.000",
                    "ventas_bi_con_iva": "$450.000",
                    "ventas_bi_sin_iva": "$380.000",
                    "diferencia_con_iva": "$30.000",
                    "conciliacion_pct": "93,8%",
                    "conciliacion_label": "Conciliación ingresos",
                    "ingresos_41_label": "Ingresos grupo PUC 41",
                    "ventas_bi_label": "Ventas BI con IVA",
                    "diferencia_label": "Diferencia",
                    "conciliacion_help": "Compara libro mayor vs BI.",
                },
                "pyg_clase": [
                    {
                        "clase_puc": "4",
                        "tipo_cuenta": "Ingresos",
                        "total_creditos": "$500.000",
                        "total_debitos": "$0",
                        "saldo_neto": "$500.000",
                    }
                ],
                "gastos_centro": [
                    {
                        "centro_codigo": "01",
                        "centro_nombre": "SALA PRINCIPAL",
                        "gastos_neto": "$10.000",
                        "costos_neto": "$200.000",
                        "total_neto": "$210.000",
                    }
                ],
                "top_gastos": [],
            },
        },
    }
    gen = HTMLReportGenerator(data, chart_paths={})
    out = tmp_path / "report.html"
    gen.generate(str(out))

    html = out.read_text(encoding="utf-8")
    assert "Presupuesto vs Real" in html
    assert "Ventas por Marca Real" in html
    assert "Balance y PyG" in html
    assert "Estado de situación financiera" in html
    assert "Activo (clase 1)" in html
    assert "SALA PRINCIPAL" in html
    assert "SIKA" in html
    assert "Vendedor A" in html
