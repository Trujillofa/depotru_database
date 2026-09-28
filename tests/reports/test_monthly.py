"""Fixture tests for depotru-report CLI (reports/monthly.py). No live DB."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from business_analyzer.core.database import QueryError
from business_analyzer.reports import monthly


def _formatted_money(label: str = "$1.000") -> dict:
    return {
        "total_revenue_with_iva": label,
        "total_revenue_without_iva": label,
        "total_cost": "$600",
        "gross_profit": "$400",
        "gross_margin_pct": "40,0%",
        "total_quantity_sold": "10",
        "order_count": "3",
        "average_order_value": "$333",
        "average_order_profit": "$133",
    }


@pytest.fixture
def manager_report_payload():
    """Complete manager-report dict covering every text section."""
    return {
        "metadata": {
            "year": 2024,
            "month_name": "Mayo",
            "start_date": "2024-05-01",
            "end_date": "2024-05-31",
            "record_count": 4,
            "branch_name": "Sika Center",
        },
        "summary": {"total_revenue_with_iva": 1000},
        "inventory_insights": {
            "low_stock_alert": [
                {
                    "product_name": "Taladro 12V",
                    "quantity_sold": 8,
                    "current_stock": 3,
                }
            ],
            "fast_movers_in_month": [
                {"product_name": "Cemento gris", "quantity_sold": 40}
            ],
        },
        "customer_vendor_mix": [
            {
                "customer_name": "Cliente Alfa",
                "vendor_count": 2,
                "total_revenue": 1500000,
                "top_vendors": [{"vendor_name": "SIKA", "pct": 80}],
            }
        ],
        "procurement_plan": [
            {
                "vendor_name": "SIKA COLOMBIA",
                "total_suggested_units": 12,
                "affected_customers": 2,
                "key_products": [
                    {
                        "product_name": "Impermeabilizante",
                        "suggested_order": 12,
                        "affected_customers": 2,
                    }
                ],
            }
        ],
        "abc_analysis": {
            "products": {"a": {"count": 1, "revenue_pct": 80}},
            "customers": {"a": {"count": 1, "revenue_pct": 70}},
            "vendors": {},
        },
        "stock_replenishment_suggestions": [
            {
                "product_name": "Taladro 12V",
                "marca": "BOSCH",
                "proveedor": "PROV",
                "current_stock": 3,
                "recent_sold": 8,
            }
        ],
        "formatted": {
            "summary": _formatted_money("$1.210.000"),
            "top_products": [
                {
                    "product_name": "Producto B",
                    "total_revenue": "$250.000",
                    "total_quantity": "20",
                    "profit_margin_pct": "40,0%",
                }
            ],
            "top_customers": [
                {
                    "customer_name": "Cliente B",
                    "total_revenue": "$242.000",
                    "profit": "$100.000",
                    "profit_margin_pct": "41,3%",
                    "total_orders": "1",
                }
            ],
            "category_breakdown": [
                {
                    "category_path": "Electricidad > Cables",
                    "total_revenue": "$250.000",
                    "profit_margin_pct": "40,0%",
                }
            ],
            "vendor_sales": [
                {
                    "vendor_name": "SIKA COLOMBIA",
                    "total_revenue": "$200.000",
                    "revenue_pct": "55,0%",
                    "profit_margin_pct": "38,0%",
                    "transactions": "4",
                }
            ],
            "marca_sales": [
                {
                    "marca_name": "SIKA",
                    "total_revenue": "$180.000",
                    "revenue_pct": "50,0%",
                    "profit_margin_pct": "42,0%",
                    "transactions": "3",
                }
            ],
            "customer_order_suggestions": [
                {
                    "customer_name": "Cliente Alfa",
                    "total_suggested": 6,
                    "suggested_items": [
                        {
                            "product_name": "Impermeabilizante",
                            "current_stock": 2,
                            "avg_monthly": 3,
                            "suggested_order": 6,
                            "primary_vendor": "SIKA",
                            "marca": "SIKA",
                        }
                    ],
                }
            ],
            "shopping_recommendations": {
                "cross_sell": [
                    {
                        "product_name": "Taladro",
                        "recommended_with": [{"product_name": "Broca 8mm"}],
                    }
                ],
                "high_margin_promote": [
                    {
                        "product_name": "Sellador",
                        "margin_pct": "55,0%",
                        "quantity_sold": "9",
                    }
                ],
            },
            "contabilidad": {
                "available": True,
                "period": {"start": "2024-05-01", "end": "2024-05-31"},
                "summary": {"cuadre_ok": True, "movimientos": "12"},
                "balance_summary": {
                    "activo_total": "$10.000",
                    "pasivo_total": "$4.000",
                    "patrimonio_total": "$5.000",
                    "resultado_pyg_acumulado": "$1.000",
                    "ecuacion_ok": True,
                    "ecuacion_diferencia": "$0",
                },
                "pyg_summary": {
                    "ingresos_label": "Ingresos",
                    "ingresos_creditos": "$8.000",
                    "margen_label": "Margen",
                    "margen_bruto_contable": "$3.000",
                    "margen_contable_pct": "37,5%",
                },
                "conciliacion_ingresos": {
                    "conciliacion_label": "Conciliación",
                    "conciliacion_pct": "98,0%",
                    "ingresos_contables_41": "$8.000",
                    "ventas_bi_con_iva": "$8.100",
                },
                "gastos_centro": [{"centro_nombre": "Admin", "total_neto": "$200"}],
            },
        },
    }


@pytest.mark.unit
def test_print_summary_includes_sede_and_colombian_totals(
    manager_report_payload, capsys
):
    monthly._print_summary(manager_report_payload)
    out = capsys.readouterr().out
    assert "Sika Center" in out
    assert "Mayo 2024" in out
    assert "$1.210.000" in out
    assert "40,0%" in out


@pytest.mark.unit
def test_print_summary_empty_period(capsys):
    monthly._print_summary(
        {
            "metadata": {
                "year": 2024,
                "month_name": "Mayo",
                "start_date": "2024-05-01",
                "end_date": "2024-05-31",
                "record_count": 0,
            },
            "summary": {},
            "formatted": {"summary": {}},
        }
    )
    assert "No se encontraron datos" in capsys.readouterr().out


@pytest.mark.unit
def test_print_text_report_covers_money_sections(manager_report_payload, capsys):
    monthly._print_text_report(
        manager_report_payload,
        {
            "ai_analysis_text": "La facturación se sostuvo.",
            "executive_summary": ["Margen saludable"],
            "recommendations": [
                {"priority": "Alta", "area": "Cartera", "action": "Cobrar >90d"}
            ],
            "risks": [
                {"level": "Alto", "type": "Stock", "description": "Taladro bajo"}
            ],
            "opportunities": [
                {
                    "impact": "Alto",
                    "type": "Marca",
                    "description": "Promover SIKA",
                }
            ],
        },
    )
    out = capsys.readouterr().out
    assert "ANÁLISIS INTELIGENTE" in out
    assert "VENTAS POR PROVEEDOR" in out
    assert "VENTAS POR MARCA" in out
    assert "TOP 15 PRODUCTOS" in out
    assert "TOP 15 CLIENTES" in out
    assert "DESGLOSE POR CATEGORÍA" in out
    assert "CONTABILIDAD ERP" in out
    assert "ALERTAS DE INVENTARIO" in out
    assert "PEDIDOS SUGERIDOS" in out
    assert "COMPRA CRUZADA" in out
    assert "MIX CLIENTES-PROVEEDORES" in out
    assert "PLAN DE COMPRAS" in out
    assert "ANÁLISIS ABC" in out
    assert "REABASTECIMIENTO" in out
    assert "Cobrar >90d" in out


@pytest.mark.unit
def test_print_contabilidad_unavailable_note(capsys):
    monthly._print_contabilidad(
        {
            "formatted": {
                "contabilidad": {
                    "available": False,
                    "note": "J3System deshabilitado; contabilidad ERP no consultada.",
                }
            }
        }
    )
    assert "J3System deshabilitado" in capsys.readouterr().out


@pytest.mark.unit
def test_print_helpers_skip_empty_sections(capsys):
    empty = {
        "formatted": {},
        "inventory_insights": {},
        "customer_vendor_mix": [],
        "procurement_plan": [],
        "abc_analysis": {},
        "stock_replenishment_suggestions": [],
    }
    monthly._print_top_products(empty)
    monthly._print_top_customers(empty)
    monthly._print_category_breakdown(empty)
    monthly._print_vendor_sales(empty)
    monthly._print_marca_sales(empty)
    monthly._print_suggested_orders(empty)
    monthly._print_cross_sell(empty)
    monthly._print_customer_vendor_mix(empty)
    monthly._print_procurement_plan(empty)
    monthly._print_abc_analysis(empty)
    monthly._print_stock_replenishment(empty)
    monthly._print_inventory_insights(empty)
    assert capsys.readouterr().out == ""


@pytest.mark.unit
def test_main_requires_output_for_html(monkeypatch):
    monkeypatch.setattr(
        monthly.sys,
        "argv",
        ["monthly", "--year", "2024", "--month", "5", "--format", "html"],
    )
    with pytest.raises(SystemExit) as exc:
        monthly.main()
    assert exc.value.code == 1


@pytest.mark.unit
def test_main_rejects_unknown_branch(monkeypatch):
    monkeypatch.setattr(
        monthly.sys,
        "argv",
        ["monthly", "--year", "2024", "--month", "5", "--branch", "no-existe"],
    )
    with pytest.raises(SystemExit) as exc:
        monthly.main()
    assert exc.value.code == 1


@pytest.mark.unit
def test_main_text_json_and_html_formats(monkeypatch, tmp_path, manager_report_payload):
    report_obj = MagicMock()
    report_obj.generate.return_value = manager_report_payload

    monkeypatch.setattr(
        monthly.sys,
        "argv",
        [
            "monthly",
            "--year",
            "2024",
            "--month",
            "5",
            "--no-ai",
            "--no-j3system",
            "--format",
            "json",
            "--output",
            str(tmp_path / "out.json"),
        ],
    )
    with patch.object(monthly, "ManagerSalesReport", return_value=report_obj):
        monthly.main()
    saved = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert saved["report"]["metadata"]["record_count"] == 4

    html_path = tmp_path / "out.html"
    monkeypatch.setattr(
        monthly.sys,
        "argv",
        [
            "monthly",
            "--year",
            "2024",
            "--month",
            "5",
            "--no-ai",
            "--format",
            "html",
            "--output",
            str(html_path),
            "--branch",
            "sika_center",
        ],
    )
    html_gen = MagicMock()
    html_gen.generate.return_value = str(html_path)
    chart_gen = MagicMock()
    chart_gen.generate_all.return_value = {"daily": "chart.png"}
    with patch.object(monthly, "ManagerSalesReport", return_value=report_obj), patch(
        monthly.__name__ + ".ReportChartGenerator", return_value=chart_gen
    ), patch.object(monthly, "HTMLReportGenerator", return_value=html_gen):
        monthly.main()
    html_gen.generate.assert_called_once()
    assert report_obj.generate.called


@pytest.mark.unit
def test_main_pdf_and_text_output(monkeypatch, tmp_path, manager_report_payload):
    report_obj = MagicMock()
    report_obj.generate.return_value = manager_report_payload
    pdf_gen = MagicMock()
    pdf_gen.generate.return_value = str(tmp_path / "out.pdf")
    chart_gen = MagicMock()
    chart_gen.generate_all.return_value = {}

    monkeypatch.setattr(
        monthly.sys,
        "argv",
        [
            "monthly",
            "--year",
            "2024",
            "--month",
            "5",
            "--no-ai",
            "--format",
            "pdf",
            "--output",
            str(tmp_path / "out.pdf"),
            "--branch",
            "FEF",
        ],
    )
    with patch.object(monthly, "ManagerSalesReport", return_value=report_obj), patch(
        monthly.__name__ + ".ReportChartGenerator", return_value=chart_gen
    ), patch.object(monthly, "PDFReportGenerator", return_value=pdf_gen):
        monthly.main()
    pdf_gen.generate.assert_called_once()

    text_out = tmp_path / "text.json"
    monkeypatch.setattr(
        monthly.sys,
        "argv",
        [
            "monthly",
            "--year",
            "2024",
            "--month",
            "5",
            "--no-ai",
            "--output",
            str(text_out),
        ],
    )
    with patch.object(monthly, "ManagerSalesReport", return_value=report_obj):
        monthly.main()
    assert text_out.is_file()


@pytest.mark.unit
def test_main_query_error_exits_without_wrong_numbers(monkeypatch, capsys):
    report_obj = MagicMock()
    report_obj.generate.side_effect = QueryError("timeout")
    monkeypatch.setattr(
        monthly.sys,
        "argv",
        ["monthly", "--year", "2024", "--month", "5", "--no-ai"],
    )
    with patch.object(monthly, "ManagerSalesReport", return_value=report_obj):
        with pytest.raises(SystemExit) as exc:
            monthly.main()
    assert exc.value.code == 1
    assert "timeout" in capsys.readouterr().err


@pytest.mark.unit
def test_main_does_not_swallow_type_error_as_zero_report(monkeypatch):
    """Programming bugs must not become a friendly zeroed manager report."""
    report_obj = MagicMock()
    report_obj.generate.side_effect = TypeError("broken mapper")
    monkeypatch.setattr(
        monthly.sys,
        "argv",
        ["monthly", "--year", "2024", "--month", "5", "--no-ai"],
    )
    with patch.object(monthly, "ManagerSalesReport", return_value=report_obj):
        with pytest.raises(TypeError, match="broken mapper"):
            monthly.main()
