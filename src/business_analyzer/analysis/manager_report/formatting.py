"""Colombian formatting for manager report display."""

from typing import Any, Dict, List, Optional

from business_analyzer.ai.formatting import (
    format_currency,
    format_integer,
    format_percentage,
)
from business_analyzer.core.j3system_contabilidad import CONTABILIDAD_METRIC_HELP


def format_for_display(
    summary: Dict[str, Any],
    top_products: List[Dict[str, Any]],
    top_customers: List[Dict[str, Any]],
    category_breakdown: List[Dict[str, Any]],
    daily_trend: List[Dict[str, Any]],
    vendor_sales: List[Dict[str, Any]],
    marca_sales: List[Dict[str, Any]],
    customer_vendor_mix: List[Dict[str, Any]],
    order_suggestions: List[Dict[str, Any]],
    recommendations: Dict[str, Any],
    procurement_plan: List[Dict[str, Any]],
    abc_analysis: Dict[str, Any],
    stock_replenish: List[Dict[str, Any]],
    warehouse_sales: Dict[str, Any],
    budget_vs_actual: Optional[Dict[str, Any]] = None,
    contabilidad: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create Colombian-formatted strings for UI/report display."""
    return {
        "summary": {
            "total_revenue_with_iva": format_currency(
                summary.get("total_revenue_with_iva", 0), 0
            ),
            "total_revenue_without_iva": format_currency(
                summary.get("total_revenue_without_iva", 0), 0
            ),
            "total_cost": format_currency(summary.get("total_cost", 0), 0),
            "gross_profit": format_currency(summary.get("gross_profit", 0), 0),
            "gross_margin_pct": format_percentage(
                summary.get("gross_margin_pct", 0), 1
            ),
            "total_quantity_sold": format_integer(
                summary.get("total_quantity_sold", 0)
            ),
            "order_count": format_integer(summary.get("order_count", 0)),
            "average_order_value": format_currency(
                summary.get("average_order_value", 0), 0
            ),
            "average_order_profit": format_currency(
                summary.get("average_order_profit", 0), 0
            ),
        },
        "top_products": [
            {
                "product_name": p["product_name"],
                "sku": p["sku"],
                "total_revenue": format_currency(p["total_revenue"], 0),
                "total_quantity": format_integer(p["total_quantity"]),
                "profit": format_currency(p["profit"], 0),
                "profit_margin_pct": format_percentage(p["profit_margin_pct"], 1),
                "transactions": format_integer(p["transactions"]),
            }
            for p in top_products
        ],
        "top_customers": [
            {
                "customer_name": c["customer_name"],
                "total_revenue": format_currency(c["total_revenue"], 0),
                "profit": format_currency(c.get("profit", 0), 0),
                "profit_margin_pct": format_percentage(
                    c.get("profit_margin_pct", 0), 1
                ),
                "total_orders": format_integer(c["total_orders"]),
                "average_order_value": format_currency(c["average_order_value"], 0),
                "total_quantity": format_integer(c["total_quantity"]),
            }
            for c in top_customers
        ],
        "category_breakdown": [
            {
                "category_path": c["category_path"],
                "total_revenue": format_currency(c["total_revenue"], 0),
                "profit": format_currency(c["profit"], 0),
                "profit_margin_pct": format_percentage(c["profit_margin_pct"], 1),
                "total_quantity": format_integer(c["total_quantity"]),
                "transactions": format_integer(c["transactions"]),
            }
            for c in category_breakdown
        ],
        "daily_trend": [
            {
                "date": d["date"],
                "revenue_with_iva": format_currency(d["revenue_with_iva"], 0),
                "revenue_without_iva": format_currency(d["revenue_without_iva"], 0),
                "profit": format_currency(d["profit"], 0),
                "profit_margin_pct": format_percentage(d["profit_margin_pct"], 1),
                "quantity": format_integer(d["quantity"]),
                "orders": format_integer(d["orders"]),
            }
            for d in daily_trend
        ],
        "vendor_sales": [
            {
                "vendor_name": v["vendor_name"],
                "total_revenue": format_currency(v["total_revenue"], 0),
                "profit": format_currency(v["profit"], 0),
                "profit_margin_pct": format_percentage(v["profit_margin_pct"], 1),
                "revenue_pct": f"{v['revenue_pct']:.1f}%",
                "transactions": format_integer(v["transactions"]),
            }
            for v in vendor_sales
        ],
        "marca_sales": [
            {
                "marca_name": m["marca_name"],
                "total_revenue": format_currency(m["total_revenue"], 0),
                "profit": format_currency(m["profit"], 0),
                "profit_margin_pct": format_percentage(m["profit_margin_pct"], 1),
                "revenue_pct": f"{m['revenue_pct']:.1f}%",
                "transactions": format_integer(m["transactions"]),
            }
            for m in marca_sales
        ],
        "customer_vendor_mix": [
            {
                "customer_name": m["customer_name"],
                "total_revenue": format_currency(m["total_revenue"], 0),
                "vendor_count": format_integer(m["vendor_count"]),
                "top_vendors": [
                    {
                        "vendor_name": tv["vendor_name"],
                        "revenue": format_currency(tv["revenue"], 0),
                        "pct": f"{tv['pct']:.1f}%",
                    }
                    for tv in m.get("top_vendors", [])
                ],
            }
            for m in customer_vendor_mix
        ],
        "customer_order_suggestions": [
            {
                "customer_name": s["customer_name"],
                "suggested_items": [
                    {
                        "product_name": i["product_name"],
                        "sku": i["sku"],
                        "avg_monthly": f"{i['avg_monthly']:.1f}",
                        "suggested_order": format_integer(i["suggested_order"]),
                        "current_stock": (
                            f"{i['current_stock']:.0f}"
                            if i["current_stock"] is not None
                            else "N/A"
                        ),
                        "primary_vendor": i.get("primary_vendor", ""),
                        "marca": i.get("marca", ""),
                    }
                    for i in s.get("suggested_items", [])
                ],
                "total_suggested": format_integer(s["total_suggested"]),
            }
            for s in order_suggestions
        ],
        "shopping_recommendations": {
            "cross_sell": [
                {
                    "product_name": r["product_name"],
                    "buyers": format_integer(r["buyers"]),
                    "revenue": format_currency(r["revenue"], 0),
                    "recommended_with": [
                        {
                            "product_name": cr["product_name"],
                            "common_customers": cr["common_customers"],
                        }
                        for cr in r.get("recommended_with", [])
                    ],
                }
                for r in recommendations.get("cross_sell", [])
            ],
            "high_margin_promote": [
                {
                    "product_name": p["product_name"],
                    "margin_pct": format_percentage(p["margin_pct"], 1),
                    "revenue": format_currency(p["revenue"], 0),
                    "gross_profit": format_currency(p.get("gross_profit", 0), 0),
                    "quantity_sold": format_integer(p["quantity_sold"]),
                }
                for p in recommendations.get("high_margin_promote", [])
            ],
        },
        "procurement_plan": [
            {
                "vendor_name": p["vendor_name"],
                "total_suggested_units": format_integer(
                    p.get("total_suggested_units", 0)
                ),
                "affected_customers": format_integer(p.get("affected_customers", 0)),
                "key_products_count": format_integer(len(p.get("key_products", []))),
                "key_products": [
                    {
                        "product_name": kp["product_name"],
                        "sku": kp.get("sku", ""),
                        "suggested_order": format_integer(kp.get("suggested_order", 0)),
                        "affected_customers": format_integer(
                            kp.get("affected_customers", 0)
                        ),
                    }
                    for kp in p.get("key_products", [])[:5]
                ],
            }
            for p in procurement_plan
        ],
        "abc_analysis": {
            "products": abc_analysis.get("products", {}),
            "customers": abc_analysis.get("customers", {}),
            "vendors": abc_analysis.get("vendors", {}),
        },
        "stock_replenishment_suggestions": [
            {
                "sku": s.get("sku", ""),
                "product_name": s.get("product_name", ""),
                "marca": s.get("marca", ""),
                "proveedor": s.get("proveedor", ""),
                "current_stock": s.get("current_stock"),
                "recent_sold": s.get("recent_sold"),
            }
            for s in stock_replenish
        ],
        "warehouse_sales": {
            "breakdown": [
                {
                    "warehouse_code": w["warehouse_code"],
                    "warehouse_name": w["warehouse_name"],
                    "sale_count": format_integer(w["sale_count"]),
                    "revenue_without_iva": format_currency(w["revenue_without_iva"], 0),
                    "revenue_with_iva": format_currency(w["revenue_with_iva"], 0),
                    "quantity": format_integer(int(w.get("quantity", 0))),
                    "revenue_pct": f"{w['revenue_pct']:.1f}%",
                }
                for w in warehouse_sales.get("breakdown", [])
            ],
            "sales_detail": [
                {
                    "venta_id": format_integer(d.get("venta_id", 0)),
                    "numero_documento": d.get("numero_documento"),
                    "fecha": d.get("fecha"),
                    "nro_factura": d.get("nro_factura"),
                    "warehouse_code": d.get("warehouse_code"),
                    "warehouse_name": d.get("warehouse_name"),
                }
                for d in warehouse_sales.get("sales_detail", [])
            ],
            "note": warehouse_sales.get("note"),
        },
        "budget_vs_actual": _format_budget_vs_actual(budget_vs_actual or {}),
        "contabilidad": _format_contabilidad(contabilidad or {}),
    }


def _format_contabilidad(data: Dict[str, Any]) -> Dict[str, Any]:
    if not data.get("available"):
        return {
            "available": False,
            "note": data.get("note"),
            "period": data.get("period") or {},
            "summary": {},
            "balance_summary": {},
            "balance_clase": [],
            "pyg_acumulado_clase": [],
            "pyg_summary": {},
            "conciliacion_ingresos": {},
            "pyg_clase": [],
            "gastos_centro": [],
            "top_gastos": [],
            "metric_help": data.get("metric_help") or dict(CONTABILIDAD_METRIC_HELP),
        }

    summary = data.get("summary") or {}
    balance = data.get("balance_summary") or {}
    pyg = data.get("pyg_summary") or {}
    conc = data.get("conciliacion_ingresos") or {}
    metric_help = data.get("metric_help") or dict(CONTABILIDAD_METRIC_HELP)
    return {
        "available": True,
        "note": data.get("note"),
        "period": data.get("period") or {},
        "metric_help": metric_help,
        "summary": {
            "movimientos": format_integer(summary.get("movimientos", 0)),
            "lineas": format_integer(summary.get("lineas", 0)),
            "total_debitos": format_currency(summary.get("total_debitos", 0), 0),
            "total_creditos": format_currency(summary.get("total_creditos", 0), 0),
            "cuadre_ok": summary.get("cuadre_ok", False),
            "cuadre_label": "Cuadre contable (D = C)",
            "cuadre_help": metric_help.get("cuadre", ""),
        },
        "balance_summary": {
            "activo_total": format_currency(balance.get("activo_total", 0), 0),
            "pasivo_total": format_currency(balance.get("pasivo_total", 0), 0),
            "patrimonio_total": format_currency(balance.get("patrimonio_total", 0), 0),
            "pasivo_mas_patrimonio": format_currency(
                balance.get("pasivo_mas_patrimonio", 0), 0
            ),
            "resultado_pyg_acumulado": format_currency(
                balance.get("resultado_pyg_acumulado", 0), 0
            ),
            "ecuacion_diferencia_bruta": format_currency(
                balance.get("ecuacion_diferencia_bruta", 0), 0
            ),
            "ecuacion_diferencia": format_currency(
                balance.get("ecuacion_diferencia", 0), 0
            ),
            "ecuacion_ok": balance.get("ecuacion_ok", False),
            "corte_fecha": balance.get("corte_fecha") or "",
            "ecuacion_label": (
                "Ecuación contable (Activo = Pasivo + Patrimonio + resultado acum.)"
            ),
            "ecuacion_help": metric_help.get("ecuacion_contable", ""),
            "resultado_pyg_help": metric_help.get("resultado_pyg_acumulado", ""),
        },
        "pyg_acumulado_clase": [
            {
                "clase_puc": row.get("clase_puc", ""),
                "tipo_cuenta": row.get("tipo_cuenta", ""),
                "total_debitos": format_currency(row.get("total_debitos", 0), 0),
                "total_creditos": format_currency(row.get("total_creditos", 0), 0),
                "saldo_acumulado": format_currency(row.get("saldo_acumulado", 0), 0),
            }
            for row in data.get("pyg_acumulado_clase", [])
        ],
        "balance_clase": [
            {
                "clase_puc": row.get("clase_puc", ""),
                "tipo_cuenta": row.get("tipo_cuenta", ""),
                "total_debitos": format_currency(row.get("total_debitos", 0), 0),
                "total_creditos": format_currency(row.get("total_creditos", 0), 0),
                "saldo_acumulado": format_currency(row.get("saldo_acumulado", 0), 0),
            }
            for row in data.get("balance_clase", [])
        ],
        "pyg_summary": {
            "ingresos_creditos": format_currency(pyg.get("ingresos_creditos", 0), 0),
            "costos_debitos": format_currency(pyg.get("costos_debitos", 0), 0),
            "gastos_debitos": format_currency(pyg.get("gastos_debitos", 0), 0),
            "margen_bruto_contable": format_currency(
                pyg.get("margen_bruto_contable", 0), 0
            ),
            "margen_contable_pct": format_percentage(
                pyg.get("margen_contable_pct", 0), 1
            ),
            "ingresos_label": "Ingresos operacionales (clase 4, créditos del periodo)",
            "costos_label": "Costos de ventas (clase 6, débitos del periodo)",
            "gastos_label": "Gastos operativos (clase 5, débitos del periodo)",
            "margen_label": "Margen bruto contable (cl. 4 − cl. 6)",
            "margen_help": metric_help.get("margen_bruto_contable", ""),
            "margen_pct_help": metric_help.get("margen_contable_pct", ""),
        },
        "conciliacion_ingresos": {
            "ingresos_contables_41": format_currency(
                conc.get("ingresos_contables_41", 0), 0
            ),
            "ventas_bi_con_iva": format_currency(conc.get("ventas_bi_con_iva", 0), 0),
            "ventas_bi_sin_iva": format_currency(conc.get("ventas_bi_sin_iva", 0), 0),
            "diferencia_con_iva": format_currency(conc.get("diferencia_con_iva", 0), 0),
            "conciliacion_pct": format_percentage(conc.get("conciliacion_pct", 0), 1),
            "conciliacion_label": "Conciliación ingresos contables vs BI",
            "ingresos_41_label": "Ingresos grupo PUC 41 (libro mayor, créditos)",
            "ventas_bi_label": "Ventas BI con IVA (banco_datos, mismo periodo)",
            "diferencia_label": "Diferencia contable − BI (con IVA)",
            "conciliacion_help": metric_help.get("conciliacion_ingresos", ""),
        },
        "pyg_clase": [
            {
                "clase_puc": row.get("clase_puc", ""),
                "tipo_cuenta": row.get("tipo_cuenta", ""),
                "total_creditos": format_currency(row.get("total_creditos", 0), 0),
                "total_debitos": format_currency(row.get("total_debitos", 0), 0),
                "saldo_neto": format_currency(row.get("saldo_neto", 0), 0),
            }
            for row in data.get("pyg_clase", [])
        ],
        "gastos_centro": [
            {
                "centro_codigo": row.get("centro_codigo", ""),
                "centro_nombre": row.get("centro_nombre", ""),
                "gastos_neto": format_currency(row.get("gastos_neto", 0), 0),
                "costos_neto": format_currency(row.get("costos_neto", 0), 0),
                "total_neto": format_currency(row.get("total_neto", 0), 0),
            }
            for row in data.get("gastos_centro", [])
        ],
        "top_gastos": [
            {
                "cuenta_codigo": row.get("cuenta_codigo", ""),
                "cuenta_nombre": row.get("cuenta_nombre", ""),
                "saldo_neto": format_currency(row.get("saldo_neto", 0), 0),
            }
            for row in data.get("top_gastos", [])
        ],
    }


def _format_budget_vs_actual(data: Dict[str, Any]) -> Dict[str, Any]:
    if not data.get("available"):
        return {
            "available": False,
            "note": data.get("note"),
            "periodo": data.get("periodo"),
            "summary": {},
            "sellers": [],
            "underperformers": [],
        }

    summary = data.get("summary") or {}
    return {
        "available": True,
        "note": data.get("note"),
        "periodo": data.get("periodo"),
        "summary": {
            "presupuesto_total": format_currency(
                summary.get("presupuesto_total", 0), 0
            ),
            "ventas_reales_total": format_currency(
                summary.get("ventas_reales_total", 0), 0
            ),
            "cumplimiento_pct": format_percentage(
                summary.get("cumplimiento_pct", 0), 1
            ),
            "brecha_total": format_currency(summary.get("brecha_total", 0), 0),
            "vendedores_con_meta": format_integer(
                summary.get("vendedores_con_meta", 0)
            ),
            "vendedores_bajo_90pct": format_integer(
                summary.get("vendedores_bajo_90pct", 0)
            ),
        },
        "sellers": [
            {
                "vendedor_codigo": s.get("vendedor_codigo", ""),
                "vendedor_nombre": s.get("vendedor_nombre", ""),
                "presupuesto": format_currency(s.get("presupuesto", 0), 0),
                "ventas_reales": format_currency(s.get("ventas_reales", 0), 0),
                "cumplimiento_pct": format_percentage(s.get("cumplimiento_pct", 0), 1),
                "brecha": format_currency(s.get("brecha", 0), 0),
                "presupuesto_share_pct": format_percentage(
                    s.get("presupuesto_share_pct", 0), 1
                ),
            }
            for s in data.get("sellers", [])
        ],
        "underperformers": [
            {
                "vendedor_codigo": s.get("vendedor_codigo", ""),
                "vendedor_nombre": s.get("vendedor_nombre", ""),
                "presupuesto": format_currency(s.get("presupuesto", 0), 0),
                "ventas_reales": format_currency(s.get("ventas_reales", 0), 0),
                "cumplimiento_pct": format_percentage(s.get("cumplimiento_pct", 0), 1),
                "brecha": format_currency(s.get("brecha", 0), 0),
            }
            for s in data.get("underperformers", [])
        ],
    }
