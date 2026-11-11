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

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from business_analyzer.ai.base import create_ai_client
from business_analyzer.ai.formatting import (
    format_currency,
    format_integer,
    format_number,
    format_percentage,
)
from business_analyzer.core.config import Config as AIConfig


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
        self.provider = (
            provider or os.getenv("REPORT_AI_PROVIDER") or AIConfig.AI_PROVIDER
        ).lower()
        self.ai_client = None
        self.ai_config: Dict[str, Any] = {}
        self.use_cli = False
        if self.provider == "commandcode":
            # Local Command Code CLI subscription (no API key handling here).
            self.use_cli = True
            self.ai_config = {
                "model": os.getenv("COMMANDCODE_MODEL", "deepseek/deepseek-v4.1-flash")
            }
        elif self.provider in ("grok", "openai", "deepseek", "openrouter", "groq"):
            try:
                self.ai_client, self.ai_config, _ = create_ai_client(self.provider)
            except Exception:
                logging.getLogger(__name__).exception(
                    "Failed to create AI client for %s", self.provider
                )
        elif self.provider == "anthropic":
            try:
                from anthropic import Anthropic

                self.ai_client = Anthropic(api_key=AIConfig.ANTHROPIC_API_KEY)
            except Exception:
                pass
        self.backends = self._resolve_backends(self.provider)

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

        if self.backends:
            try:
                result["ai_analysis_text"] = self._generate_ai_narrative()
            except Exception:
                logging.getLogger(__name__).exception(
                    "AI narrative generation failed provider=%s", self.provider
                )
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
        margin = summary.get("gross_margin_pct", 0)
        orders = summary.get("order_count", 0)
        aov = summary.get("average_order_value", 0)

        # Revenue level
        if revenue >= 5_000_000_000:
            insights.append(
                f"💰 Mes excepcional con facturación superior a {format_currency(revenue, 0)} sin IVA."
            )
        elif revenue >= 1_000_000_000:
            insights.append(
                f"📈 Buen desempeño mensual con facturación de {format_currency(revenue, 0)} sin IVA."
            )
        elif revenue > 0:
            insights.append(
                f"📊 Facturación del mes: {format_currency(revenue, 0)} sin IVA."
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
                    f"⚠️ Dependencia de producto: '{top_products[0]['product_name']}' representa el {format_percentage(top1_product_pct, 1)} de las ventas."
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
                f"🛒 {format_number(orders, 'order_count')} transacciones con ticket promedio (con IVA) de {format_currency(aov, 0)}."
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
                    "action": f"Contactar a '{top_customers[0]['customer_name']}' para ofrecer descuentos por volumen y fidelización.",
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
                        "action": f"'{vendor_sales[0]['vendor_name']}' representa {format_percentage(top_vendor_pct, 1)} de las compras. Evaluar diversificación de proveedores.",
                    }
                )

        # Suggested orders
        suggestions = self.data.get("customer_order_suggestions", [])
        if suggestions:
            total = sum(s.get("total_suggested", 0) for s in suggestions)
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
                    "action": f"Priorizar negociación con '{top_v['vendor_name']}' para ~{top_v.get('total_suggested_units',0)} unidades (afecta {top_v.get('affected_customers',0)} clientes top).",
                }
            )

        # Cross-sell opportunity
        if top_products:
            recs.append(
                {
                    "priority": "Baja",
                    "area": "Ventas",
                    "action": f"Crear bundles con '{top_products[0]['product_name']}' para aumentar ticket promedio.",
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
                        "description": f"{vendor_sales[0]['vendor_name']} concentra el {format_percentage(top_v_pct, 1)} de las ventas. Riesgo de desabastecimiento o aumento de precios.",
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
                    "description": f"Subir el margen de {format_percentage(margin, 1)} a 20% aumentaría la ganancia bruta en aprox. {format_currency(summary.get('gross_profit', 0) * (20 / max(margin, 1) - 1), 0)}.",
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
                    "description": f"Implementar venta cruzada para elevar el ticket promedio (con IVA) de {format_currency(aov, 0)} a $300.000.",
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

        cache_file = None
        if os.getenv("REPORT_AI_CACHE", "1") != "0":
            try:
                cache_file = self._narrative_cache_file(prompt)
                if cache_file.exists():
                    cached = cache_file.read_text(encoding="utf-8").strip()
                    if self._narrative_is_valid(cached):
                        return cached
            except OSError:
                cache_file = None

        errors: List[str] = []
        for provider in self.backends:
            try:
                text = self._call_provider(provider, prompt)
                text = self._strip_cli_trailing_offer(text).strip()
                if not self._narrative_is_valid(text):
                    raise RuntimeError(f"narrativa incompleta ({len(text)} caracteres)")
                if cache_file is not None:
                    try:
                        cache_file.write_text(text, encoding="utf-8")
                    except OSError:
                        pass
                return text
            except Exception as exc:  # noqa: BLE001 - try the next backend
                logging.getLogger(__name__).warning(
                    "Narrative backend %s failed: %s", provider, exc
                )
                errors.append(f"{provider}: {exc}")
        raise RuntimeError(
            "Ningún proveedor de narrativa respondió: " + "; ".join(errors)
        )

    @staticmethod
    def _resolve_backends(primary: str) -> List[str]:
        raw = os.getenv("REPORT_AI_FALLBACK_PROVIDERS", "openrouter")
        chain = [primary]
        for item in raw.split(","):
            name = item.strip().lower()
            if name and name not in chain:
                chain.append(name)
        return chain

    def _call_provider(self, provider: str, prompt: str) -> str:
        if provider == "commandcode":
            return self._call_commandcode(
                prompt,
                model=os.getenv("COMMANDCODE_MODEL", "deepseek/deepseek-v4.1-flash"),
            )
        if provider == "anthropic":
            if self.provider == "anthropic" and self.ai_client is not None:
                return self._call_anthropic(prompt)
            from anthropic import Anthropic

            client = Anthropic(api_key=AIConfig.ANTHROPIC_API_KEY)
            return self._call_anthropic(prompt, client=client)
        if provider in ("grok", "openai", "deepseek", "openrouter", "groq"):
            if self.provider == provider and self.ai_client is not None:
                return self._call_openai(prompt)
            client, config, _ = create_ai_client(provider)
            return self._call_openai(prompt, client=client, config=config)
        raise ValueError(f"Proveedor no soportado para narrativa: {provider}")

    @staticmethod
    def _narrative_cache_file(prompt: str) -> Path:
        root = Path(
            os.getenv("REPORT_AI_CACHE_DIR", "~/.cache/depotru-report-narratives")
        ).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return root / f"{digest}.md"

    @staticmethod
    def _narrative_is_valid(text: str) -> bool:
        if not text or len(text) < 1200:
            return False
        lowered = text.lower()
        signals = ("análisis", "insight", "recomend", "cierre", "riesgo")
        return sum(1 for word in signals if word in lowered) >= 2

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
        aov_sin_iva = format_currency(
            summary.get("average_order_value_without_iva", 0), 0
        )

        products_text = "\n".join(
            [
                f"  {i+1}. {p['product_name'][:40]} — Rev: {format_currency(p['total_revenue'], 0)}, Margen: {format_percentage(p['profit_margin_pct'], 1)}"
                for i, p in enumerate(top_products)
            ]
        )

        customers_text = "\n".join(
            [
                f"  {i+1}. {c['customer_name'][:35]} — {format_currency(c['total_revenue'], 0)} ({c['total_orders']} pedidos)"
                for i, c in enumerate(top_customers)
            ]
        )

        categories_text = "\n".join(
            [
                f"  {i+1}. {c['category_path'][:40]} — {format_currency(c['total_revenue'], 0)}, Margen: {format_percentage(c['profit_margin_pct'], 1)}"
                for i, c in enumerate(categories)
            ]
        )

        vendors_text = ""
        if vendor_sales:
            vendors_text = "\n" + "\n".join(
                [
                    f"  {i+1}. {v['vendor_name'][:25]} — {format_currency(v['total_revenue'], 0)}, Margen: {format_percentage(v['profit_margin_pct'], 1)}, {format_percentage(v['revenue_pct'], 1)} de participación"
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
                f"  • Ingresos clase 4: {format_currency(pyg.get('ingresos_creditos', 0), 0)}\n"
                f"  • Margen bruto contable: {format_currency(pyg.get('margen_bruto_contable', 0), 0)} "
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
  • Ticket Promedio (con IVA): {aov}
  • Ticket Promedio (sin IVA): {aov_sin_iva}

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
Devuelve únicamente el informe final: sin preguntas de seguimiento, sin ofrecer guardar
archivos y sin comentarios sobre el formato de salida. Usa solo los datos suministrados:
no inventes hallazgos, problemas de calidad ni cifras que no aparezcan arriba.
"""

    def _call_openai(
        self,
        prompt: str,
        *,
        client: Any = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Call OpenAI-compatible API (Grok, OpenAI, DeepSeek, OpenRouter)."""
        client = client or self.ai_client
        config = config or self.ai_config
        model = (config or {}).get("model")
        if not model:
            if self.provider == "grok":
                model = "grok-4-1-fast-non-reasoning"
            elif self.provider == "deepseek":
                model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
            else:
                model = "gpt-4"
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "Eres un director de análisis de negocios experto en retail colombiano. Escribes informes ejecutivos concisos, profesionales y accionables.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=2500,
        )
        return response.choices[0].message.content.strip()

    @staticmethod
    def _strip_cli_trailing_offer(text: str) -> str:
        """Drop agent-style closing offers/questions from headless CLI output."""
        import re

        offer = re.compile(
            r"(¿\s*(quieres|deseas|prefieres|te\s+gustar[ií]a)|si\s+(quieres|deseas)|"
            r"puedo\s+(dejarlo|generarlo|guardarlo|exportarlo)|d[eé]jame\s+saber|"
            r"av[ií]same|quedo\s+atento)",
            re.I,
        )
        paragraphs = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
        while paragraphs and offer.search(paragraphs[-1]):
            paragraphs.pop()
        return "\n\n".join(paragraphs).strip()

    def _call_commandcode(self, prompt: str, *, model: str = "") -> str:
        """Call the local Command Code CLI (subscription auth, headless)."""
        import shutil
        import subprocess

        binary = os.getenv("COMMANDCODE_BIN") or shutil.which("commandcode")
        if not binary:
            raise RuntimeError(
                "commandcode CLI no está instalado; use otro proveedor de IA"
            )
        model = (model or (self.ai_config or {}).get("model") or "").strip()
        cmd = [
            binary,
            "-p",
            prompt,
            "--no-session",
            "--output-format",
            "text",
            "--max-turns",
            "3",
        ]
        if model:
            cmd += ["-m", model]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=int(os.getenv("COMMANDCODE_TIMEOUT", "420")),
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[-400:]
            raise RuntimeError(f"Command Code falló ({proc.returncode}): {detail}")
        text = self._strip_cli_trailing_offer(proc.stdout.strip())
        if not text:
            raise RuntimeError("Command Code no devolvió texto")
        return text

    def _call_anthropic(self, prompt: str, *, client: Any = None) -> str:
        """Call Anthropic Claude API."""
        client = client or self.ai_client
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=2500,
            temperature=0.7,
            system="Eres un director de análisis de negocios experto en retail colombiano. Escribes informes ejecutivos concisos, profesionales y accionables.",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
