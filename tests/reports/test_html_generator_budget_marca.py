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
        },
    }
    gen = HTMLReportGenerator(data, chart_paths={})
    out = tmp_path / "report.html"
    gen.generate(str(out))

    html = out.read_text(encoding="utf-8")
    assert "Presupuesto vs Real" in html
    assert "Ventas por Marca Real" in html
    assert "SIKA" in html
    assert "Vendedor A" in html
