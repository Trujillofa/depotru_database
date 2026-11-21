"""HTML report contract: formatting and AI narrative rendering."""

from pathlib import Path

from business_analyzer.reports.html_generator import HTMLReportGenerator


def _data():
    return {
        "metadata": {"year": 2026, "month_name": "Octubre"},
        "summary": {
            "gross_margin_pct": 45.6,
            "average_order_value_without_iva": 144353,
        },
        "formatted": {
            "summary": {
                "total_revenue_with_iva": "$117.497.953",
                "total_revenue_without_iva": "$98.737.775",
                "gross_profit": "$19.458.159",
                "gross_margin_pct": "45,6%",
                "total_quantity_sold": "3.213",
                "order_count": "684",
                "average_order_value": "$171.781",
                "average_order_value_without_iva": "$144.353",
                "average_order_profit": "$28.448",
            },
            "top_products": [],
            "top_customers": [],
            "vendor_sales": [],
            "marca_sales": [],
            "customer_vendor_mix": [],
            "customer_order_suggestions": [
                {
                    "customer_name": "CLIENTE UNO",
                    "total_suggested": "1",
                    "suggested_items": [
                        {
                            "product_name": "PRODUCTO UNO",
                            "sku": "001",
                            "avg_monthly": "4,8",
                            "suggested_order": "1",
                            "current_stock": "N/A",
                            "primary_vendor": "SIKA",
                            "marca": "SIKA",
                        }
                    ],
                }
            ],
            "procurement_plan": [],
            "abc_analysis": {},
            "stock_replenishment_suggestions": [],
        },
    }


def _ai():
    return {
        "ai_analysis_text": "## INFORME\n\n**Análisis** del mes.\n\n---\n\nCierre.",
        "executive_summary": ["Facturación $98.737.775"],
        "recommendations": [],
        "risks": [],
        "opportunities": [],
    }


def test_html_report_contract(tmp_path: Path):
    out = tmp_path / "report.html"
    HTMLReportGenerator(_data(), {}, _ai()).generate(str(out))
    html = out.read_text(encoding="utf-8")

    assert "<strong>Análisis</strong>" in html
    assert "**" not in html
    assert "$$" not in html
    assert "45,6%" in html
    assert "Ticket Promedio (con IVA)" in html
    assert "Sin IVA: $144.353" in html
    assert "cliente(s)" not in html
    assert "1 clientes" not in html
    assert '<th class="num">Stock</th>' not in html  # column hidden
