# mypy: ignore-errors
"""
AI Insights for Manager Sales Reports
=======================================

Generate intelligent business insights, recommendations, and risk
alerts from monthly sales report data using configured AI providers.

Usage:
    from src.business_analyzer.reports.ai_insights import ReportAIInsights

    insights = ReportAIInsights(report_data)
    result = insights.generate()
"""

import os
from typing import Any, Dict, List, Optional

import pandas as pd

try:
    from ..ai.base import Config as AIConfig
    from ..ai.base import create_ai_client, retry_on_failure
    from ..ai.circuit_breaker import CircuitBreakerError, with_circuit_breaker
    from ..ai.formatting import (
        format_currency,
        format_integer,
        format_number,
        format_percentage,
    )
except ImportError:
    import sys
    from pathlib import Path

    src_path = Path(__file__).parent.parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from business_analyzer.ai.base import Config as AIConfig
    from business_analyzer.ai.base import create_ai_client, retry_on_failure
    from business_analyzer.ai.circuit_breaker import (
        CircuitBreakerError,
        with_circuit_breaker,
    )
    from business_analyzer.ai.formatting import (
        format_currency,
        format_integer,
        format_number,
        format_percentage,
    )


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    return numerator / denominator if denominator != 0 else default


class ReportAIInsights:
    """
    Generate AI-powered insights from monthly sales report data.

    Uses the configured AI provider (Grok, OpenAI, Anthropic, or Ollama)
    to analyze trends, identify risks, and recommend actions.

    Attributes:
        data: Report dictionary from ManagerSalesReport.generate()
        provider: AI provider name
        ai_client: Initialized AI client
    """

    def __init__(self, data: Dict[str, Any], provider: Optional[str] = None):
        self.data = data
        self.provider = (provider or AIConfig.AI_PROVIDER).lower()
        self.ai_client = None
        if self.provider in ("grok", "openai"):
            try:
                self.ai_client, _, _ = create_ai_client(self.provider)
            except Exception:
                pass
        elif self.provider == "anthropic":
            try:
                from anthropic import Anthropic

                self.ai_client = Anthropic(api_key=AIConfig.ANTHROPIC_API_KEY)
            except Exception:
                pass

    def generate(self) -> Dict[str, Any]:
        """
        Generate all AI insights.

        Returns:
            Dictionary with:
            - executive_summary: 3-5 key takeaways
            - recommendations: prioritized action items
            - risks: business risks detected
            - opportunities: growth opportunities
            - ai_analysis_text: full AI-generated narrative (if provider available)
        """
        result = {
            "executive_summary": self._compute_executive_summary(),
            "recommendations": self._compute_recommendations(),
            "risks": self._compute_risks(),
            "opportunities": self._compute_opportunities(),
            "ai_analysis_text": None,
        }

        if self.ai_client:
            try:
                result["ai_analysis_text"] = self._generate_ai_narrative()
            except Exception:
                result[
                    "ai_analysis_text"
                ] = "⚠️ No se pudo generar el análisis con IA en este momento."

        return result

    def _compute_executive_summary(self) -> List[str]:
        """Compute data-driven executive summary points."""
        summary = self.data.get("summary", {})
        top_products = self.data.get("top_products", [])
        top_customers = self.data.get("top_customers", [])
        daily_trend = self.data.get("daily_trend", [])
        insights = []

        revenue = summary.get("total_revenue_without_iva", 0)
        profit = summary.get("gross_profit", 0)
        margin = summary.get("gross_margin_pct", 0)
        orders = summary.get("order_count", 0)
        aov = summary.get("average_order_value", 0)

        # Revenue level
        if revenue >= 5_000_000_000:
            insights.append(
                f"💰 Mes excepcional con facturación superior a ${format_currency(revenue, 0)} sin IVA."
            )
        elif revenue >= 1_000_000_000:
            insights.append(
                f"📈 Buen desempeño mensual con facturación de ${format_currency(revenue, 0)} sin IVA."
            )
        elif revenue > 0:
            insights.append(
                f"📊 Facturación del mes: ${format_currency(revenue, 0)} sin IVA."
            )

        # Margin health
        if margin >= 20:
            insights.append(
                f"✅ Margen bruto saludable del {format_percentage(margin, 1)}, por encima del benchmark de 20%."
            )
        elif margin >= 10:
            insights.append(
                f"⚠️ Margen bruto de {format_percentage(margin, 1)} — está dentro del rango aceptable pero con espacio de mejora."
            )
        elif margin > 0:
            insights.append(
                f"🚨 Margen bruto bajo ({format_percentage(margin, 1)}). Revisar estructura de costos y precios."
            )
        elif revenue > 0:
            insights.append("❌ Margen negativo. Se está vendiendo a pérdida.")

        # Customer concentration
        if top_customers:
            top1_pct = (
                safe_divide(top_customers[0]["total_revenue"], revenue, 0.0) * 100
            )
            if top1_pct > 30:
                insights.append(
                    f"⚠️ Alta concentración: el cliente principal representa el {format_percentage(top1_pct, 1)} de las ventas."
                )
            elif top1_pct > 15:
                insights.append(
                    f"📌 El cliente principal aporta el {format_percentage(top1_pct, 1)} de las ventas."
                )

        # Product dependency
        if top_products:
            top1_product_pct = (
                safe_divide(top_products[0]["total_revenue"], revenue, 0.0) * 100
            )
            if top1_product_pct > 20:
                insights.append(
                    f"⚠️ Dependencia de producto: '{top_products[0]['product_name'][:30]}' representa el {format_percentage(top1_product_pct, 1)} de las ventas."
                )

        # Daily trend volatility
        if len(daily_trend) >= 7:
            revenues = [d["revenue_with_iva"] for d in daily_trend]
            import statistics

            mean_rev = statistics.mean(revenues) if revenues else 0
            std_rev = statistics.stdev(revenues) if len(revenues) > 1 else 0
            cv = safe_divide(std_rev, mean_rev, 0.0) * 100
            if cv > 50:
                insights.append(
                    f"📉 Alta volatilidad en ventas diarias (CV: {format_percentage(cv, 1)}). Revisar patrones de demanda."
                )

        # Order count
        if orders > 0:
            insights.append(
                f"🛒 {format_number(orders, 'order_count')} transacciones con ticket promedio de ${format_currency(aov, 0)}."
            )

        cont = self.data.get("contabilidad") or {}
        if cont.get("available"):
            conc_pct = (cont.get("conciliacion_ingresos") or {}).get(
                "conciliacion_pct", 0
            )
            margen_cont = (cont.get("pyg_summary") or {}).get("margen_contable_pct", 0)
            balance = cont.get("balance_summary") or {}
            activo = balance.get("activo_total", 0)
            insights.append(
                f"📒 Contabilidad ERP: activo {format_currency(activo, 0)} al cierre; "
                f"conciliación ingresos {format_percentage(conc_pct, 1)}; "
                f"margen bruto contable {format_percentage(margen_cont, 1)}."
            )

        return insights

    def _compute_recommendations(self) -> List[Dict[str, str]]:
        """Compute prioritized business recommendations."""
        summary = self.data.get("summary", {})
        top_products = self.data.get("top_products", [])
        top_customers = self.data.get("top_customers", [])
        inventory = self.data.get("inventory_insights", {})
        categories = self.data.get("category_breakdown", [])
        recs: List[Dict[str, str]] = []

        margin = summary.get("gross_margin_pct", 0)
        revenue = summary.get("total_revenue_without_iva", 0)

        # Margin-based recommendations
        if margin < 15:
            recs.append(
                {
                    "priority": "Alta",
                    "area": "Pricing",
                    "action": "Revisar lista de precios de productos con margen < 10%. Considerar renegociación con proveedores.",
                }
            )

        # Low stock alerts
        low_stock = inventory.get("low_stock_alert", [])
        if low_stock:
            skus = ", ".join([i["sku"] for i in low_stock[:5]])
            recs.append(
                {
                    "priority": "Alta",
                    "area": "Inventario",
                    "action": f"Reabastecer urgentemente {len(low_stock)} productos con stock bajo. SKUs: {skus}",
                }
            )

        # Top customer nurturing
        if top_customers and len(top_customers) >= 3:
            recs.append(
                {
                    "priority": "Media",
                    "area": "Clientes",
                    "action": f"Contactar a '{top_customers[0]['customer_name'][:25]}' para ofrecer descuentos por volumen y fidelización.",
                }
            )

        # Underperforming categories
        underperforming = [c for c in categories if c.get("profit_margin_pct", 0) < 5]
        if underperforming:
            cat_names = ", ".join(
                [c["category_path"].split(" > ")[0][:20] for c in underperforming[:3]]
            )
            recs.append(
                {
                    "priority": "Media",
                    "area": "Categorías",
                    "action": f"Evaluar rentabilidad de categorías con margen bajo: {cat_names}.",
                }
            )

        # Vendor concentration
        vendor_sales = self.data.get("vendor_sales", [])
        if vendor_sales and len(vendor_sales) >= 3:
            top_vendor_pct = vendor_sales[0].get("revenue_pct", 0)
            if top_vendor_pct > 15:
                recs.append(
                    {
                        "priority": "Media",
                        "area": "Proveedores",
                        "action": f"'{vendor_sales[0]['vendor_name']}' representa {top_vendor_pct:.1f}% de las compras. Evaluar diversificación de proveedores.",
                    }
                )

        # Suggested orders
        suggestions = self.data.get("customer_order_suggestions", [])
        if suggestions:
            total = sum(s.get("total_suggested", 0) for s in suggestions[:5])
            recs.append(
                {
                    "priority": "Media",
                    "area": "Compras",
                    "action": f"Generar órdenes de compra para los {len(suggestions)} clientes analizados ({format_integer(total)} unidades sugeridas). Programar llamadas de ventas.",
                }
            )

        # Procurement plan (vendor-aggregated shopping suggestions)
        plan = self.data.get("procurement_plan", [])
        if plan:
            top_v = plan[0]
            recs.append(
                {
                    "priority": "Alta",
                    "area": "Abastecimiento",
                    "action": f"Priorizar negociación con '{top_v['vendor_name'][:20]}' para ~{top_v.get('total_suggested_units',0)} unidades (afecta {top_v.get('affected_customers',0)} clientes top).",
                }
            )

        # Cross-sell opportunity
        if top_products:
            recs.append(
                {
                    "priority": "Baja",
                    "area": "Ventas",
                    "action": f"Crear bundles con '{top_products[0]['product_name'][:25]}' para aumentar ticket promedio.",
                }
            )

        cross_sell = self.data.get("shopping_recommendations", {}).get("cross_sell", [])
        if len(cross_sell) >= 3:
            recs.append(
                {
                    "priority": "Baja",
                    "area": "Marketplace",
                    "action": "Configurar 'los clientes que compraron X también compraron Y' en el sistema POS basado en patrones de compra.",
                }
            )

        return recs

    def _compute_risks(self) -> List[Dict[str, str]]:
        """Identify business risks from the data."""
        summary = self.data.get("summary", {})
        top_customers = self.data.get("top_customers", [])
        top_products = self.data.get("top_products", [])
        inventory = self.data.get("inventory_insights", {})
        risks: List[Dict[str, str]] = []

        revenue = summary.get("total_revenue_without_iva", 0)
        margin = summary.get("gross_margin_pct", 0)

        # Concentration risk
        if top_customers:
            top3_rev = sum(c["total_revenue"] for c in top_customers[:3])
            top3_pct = safe_divide(top3_rev, revenue, 0.0) * 100
            if top3_pct > 50:
                risks.append(
                    {
                        "level": "Alto",
                        "type": "Concentración de Clientes",
                        "description": f"El top 3 de clientes representa el {format_percentage(top3_pct, 1)} de las ventas. Pérdida de uno impactaría gravemente.",
                    }
                )

        # Product concentration
        if top_products:
            top3_prod_rev = sum(p["total_revenue"] for p in top_products[:3])
            top3_prod_pct = safe_divide(top3_prod_rev, revenue, 0.0) * 100
            if top3_prod_pct > 40:
                risks.append(
                    {
                        "level": "Medio",
                        "type": "Dependencia de Productos",
                        "description": f"Los 3 productos principales concentran el {format_percentage(top3_prod_pct, 1)} de las ventas.",
                    }
                )

        # Vendor dependency risk
        vendor_sales = self.data.get("vendor_sales", [])
        if vendor_sales:
            top_v_pct = vendor_sales[0].get("revenue_pct", 0)
            if top_v_pct > 25:
                risks.append(
                    {
                        "level": "Alto",
                        "type": "Dependencia de Proveedores",
                        "description": f"{vendor_sales[0]['vendor_name']} concentra el {top_v_pct:.1f}% de las ventas. Riesgo de desabastecimiento o aumento de precios.",
                    }
                )

        # Margin risk
        if margin < 10:
            risks.append(
                {
                    "level": "Alto",
                    "type": "Rentabilidad",
                    "description": f"Margen bruto de {format_percentage(margin, 1)} es insuficiente para cubrir gastos operativos típicos.",
                }
            )

        # Stockout risk
        low_stock = inventory.get("low_stock_alert", [])
        if len(low_stock) >= 5:
            risks.append(
                {
                    "level": "Medio",
                    "type": "Desabastecimiento",
                    "description": f"{len(low_stock)} productos con stock crítico (≤10 unidades) podrían generar pérdida de ventas.",
                }
            )

        return risks

    def _compute_opportunities(self) -> List[Dict[str, str]]:
        """Identify growth opportunities."""
        summary = self.data.get("summary", {})
        top_products = self.data.get("top_products", [])
        categories = self.data.get("category_breakdown", [])
        ops: List[Dict[str, str]] = []

        aov = summary.get("average_order_value", 0)
        margin = summary.get("gross_margin_pct", 0)

        # Margin improvement
        if margin < 20:
            ops.append(
                {
                    "impact": "Alto",
                    "type": "Optimización de Margen",
                    "description": f"Subir el margen de {format_percentage(margin, 1)} a 20% aumentaría la ganancia bruta en aprox. ${format_currency(summary.get('gross_profit', 0) * (20 / max(margin, 1) - 1), 0)}.",
                }
            )

        # High-margin star products
        stars = [p for p in top_products if p.get("profit_margin_pct", 0) > 20]
        if stars:
            ops.append(
                {
                    "impact": "Medio",
                    "type": "Productos Estrella",
                    "description": f"Promocionar {len(stars)} productos con margen >20% para mejorar rentabilidad general.",
                }
            )

        # AOV improvement
        if aov < 300_000:
            ops.append(
                {
                    "impact": "Medio",
                    "type": "Ticket Promedio",
                    "description": f"Implementar venta cruzada para elevar el ticket de ${format_currency(aov, 0)} a $300.000.",
                }
            )

        # Category expansion
        if categories and len(categories) > 1:
            top_cat = categories[0]
            ops.append(
                {
                    "impact": "Bajo",
                    "type": "Expansión de Categoría",
                    "description": f"La categoría '{top_cat['category_path'].split(' > ')[0]}' lidera. Evaluar ampliar SKU en esa línea.",
                }
            )

        return ops

    def _generate_ai_narrative(self) -> str:
        """Generate full AI narrative using the configured provider."""
        summary = self.data.get("summary", {})
        top_products = self.data.get("top_products", [])[:5]
        top_customers = self.data.get("top_customers", [])[:5]
        categories = self.data.get("category_breakdown", [])[:5]
        meta = self.data.get("metadata", {})

        vendor_sales = self.data.get("vendor_sales", [])[:5]
        suggestions = self.data.get("customer_order_suggestions", [])[:3]
        recommendations = self.data.get("shopping_recommendations", {})
        plan = self.data.get("procurement_plan", [])[:3]
        mix = self.data.get("customer_vendor_mix", [])[:3]
        contabilidad = self.data.get("contabilidad")
        prompt = self._build_prompt(
            summary,
            top_products,
            top_customers,
            categories,
            meta,
            vendor_sales,
            suggestions,
            recommendations,
            plan,
            mix,
            contabilidad,
        )

        if self.provider in ("grok", "openai"):
            return self._call_openai(prompt)
        elif self.provider == "anthropic":
            return self._call_anthropic(prompt)
        return "⚠️ Proveedor no soportado para análisis narrativo."

    def _build_prompt(
        self,
        summary: Dict[str, Any],
        top_products: List[Dict],
        top_customers: List[Dict],
        categories: List[Dict],
        meta: Dict[str, Any],
        vendor_sales: Optional[List[Dict]] = None,
        suggestions: Optional[List[Dict]] = None,
        recommendations: Optional[Dict] = None,
        plan: Optional[List[Dict]] = None,
        mix: Optional[List[Dict]] = None,
        contabilidad: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build the AI prompt from report data."""
        month_name = meta.get("month_name", "")
        year = meta.get("year", "")
        revenue = format_currency(summary.get("total_revenue_without_iva", 0), 0)
        profit = format_currency(summary.get("gross_profit", 0), 0)
        margin = format_percentage(summary.get("gross_margin_pct", 0), 1)
        orders = format_number(summary.get("order_count", 0), "order_count")
        aov = format_currency(summary.get("average_order_value", 0), 0)

        products_text = "\n".join(
            [
                f"  {i+1}. {p['product_name'][:40]} — Rev: ${format_currency(p['total_revenue'], 0)}, Margen: {format_percentage(p['profit_margin_pct'], 1)}"
                for i, p in enumerate(top_products)
            ]
        )

        customers_text = "\n".join(
            [
                f"  {i+1}. {c['customer_name'][:35]} — ${format_currency(c['total_revenue'], 0)} ({c['total_orders']} pedidos)"
                for i, c in enumerate(top_customers)
            ]
        )

        categories_text = "\n".join(
            [
                f"  {i+1}. {c['category_path'][:40]} — ${format_currency(c['total_revenue'], 0)}, Margen: {format_percentage(c['profit_margin_pct'], 1)}"
                for i, c in enumerate(categories)
            ]
        )

        vendors_text = ""
        if vendor_sales:
            vendors_text = "\n" + "\n".join(
                [
                    f"  {i+1}. {v['vendor_name'][:25]} — ${format_currency(v['total_revenue'], 0)}, Margen: {format_percentage(v['profit_margin_pct'], 1)}, {v['revenue_pct']:.1f}% de participación"
                    for i, v in enumerate(vendor_sales)
                ]
            )

        suggestions_text = ""
        if suggestions:
            sug_lines = []
            for s in suggestions[:3]:
                items_summary = ", ".join(
                    [i["product_name"][:25] for i in s.get("suggested_items", [])[:3]]
                )
                sug_lines.append(
                    f"  • {s['customer_name'][:30]}: {s['total_suggested']} unidades sugeridas — {items_summary}"
                )
            suggestions_text = "\n" + "\n".join(sug_lines)

        plan_text = ""
        if plan:
            plines = []
            for p in plan[:3]:
                plines.append(
                    f"  • {p['vendor_name'][:22]}: {p.get('total_suggested_units',0)} uds sugeridas para {p.get('affected_customers',0)} clientes"
                )
            plan_text = "\n" + "\n".join(plines)

        mix_text = ""
        if mix:
            mlines = []
            for m in mix[:3]:
                tops = ", ".join(
                    [f"{v['vendor_name'][:10]}" for v in m.get("top_vendors", [])[:2]]
                )
                mlines.append(
                    f"  • {m['customer_name'][:26]} compra de {m.get('vendor_count',0)} prov. (ej: {tops})"
                )
            mix_text = "\n" + "\n".join(mlines)

        contabilidad_text = ""
        if contabilidad and contabilidad.get("available"):
            pyg = contabilidad.get("pyg_summary") or {}
            conc = contabilidad.get("conciliacion_ingresos") or {}
            contabilidad_text = (
                f"\nCONTABILIDAD ERP (ConMovimiento / PUC):\n"
                f"  • Ingresos clase 4: ${format_currency(pyg.get('ingresos_creditos', 0), 0)}\n"
                f"  • Margen bruto contable: ${format_currency(pyg.get('margen_bruto_contable', 0), 0)} "
                f"({format_percentage(pyg.get('margen_contable_pct', 0), 1)})\n"
                f"  • Conciliación ingresos 41 vs BI: {format_percentage(conc.get('conciliacion_pct', 0), 1)}"
            )

        return f"""Eres el Director de Análisis de una ferretería colombiana grande. Escribe un informe ejecutivo en español para la gerencia.

PERÍODO: {month_name} {year}
RESUMEN FINANCIERO:
  • Facturación (sin IVA): {revenue}
  • Ganancia Bruta: {profit}
  • Margen Bruto: {margin}
  • Transacciones: {orders}
  • Ticket Promedio: {aov}

TOP 5 PRODUCTOS:
{products_text}

TOP 5 CLIENTES:
{customers_text}

TOP 5 CATEGORÍAS:
{categories_text}

TOP 5 PROVEEDORES:{vendors_text}

PEDIDOS SUGERIDOS (basado en consumo YTD completo del año):{suggestions_text}

PLAN DE COMPRAS CONSOLIDADO (agregado por proveedor para abastecimiento):{plan_text}

MIX TOP CLIENTES-PROVEEDORES:{mix_text}
{contabilidad_text}

INSTRUCCIONES:
1. Escribe un ANÁLISIS EJECUTIVO de 4-5 párrafos que interprete estos números, incluyendo concentración por proveedor y patrones de compra por cliente.
2. Identifica 3 INSIGHTS CLAVE con evidencia de los datos (usa el plan de compras y el mix cuando sea relevante).
3. Propón 3 RECOMENDACIONES CONCRETAS y priorizadas (incluye sugerencias de órdenes a proveedores y cross-sell a clientes).
4. Menciona 1 RIESGO y 1 OPORTUNIDAD.
5. Termina con una frase de cierre motivacional para el equipo de ventas.

Tono: profesional, directo, orientado a la acción. No uses tablas. Usa emojis ocasionalmente.
"""

    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI-compatible API."""
        model = "grok-4-1-fast-non-reasoning" if self.provider == "grok" else "gpt-4"
        response = self.ai_client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Eres un director de análisis de negocios experto en retail colombiano. Escribes informes ejecutivos concisos, profesionales y accionables.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1200,
        )
        return response.choices[0].message.content.strip()

    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic Claude API."""
        response = self.ai_client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1200,
            temperature=0.7,
            system="Eres un director de análisis de negocios experto en retail colombiano. Escribes informes ejecutivos concisos, profesionales y accionables.",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
