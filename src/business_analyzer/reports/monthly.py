# mypy: ignore-errors
"""
Monthly Manager Sales Report — CLI
====================================

Generate and display a monthly manager sales report from the terminal.
Supports text, JSON, HTML, and PDF output formats with charts and AI insights.

Examples:
    python -m business_analyzer.reports.monthly --year 2024 --month 5
    python -m business_analyzer.reports.monthly --year 2024 --month 5 --format html --output report.html
    python -m business_analyzer.reports.monthly --year 2024 --month 5 --format pdf --output report.pdf
    python -m business_analyzer.reports.monthly --year 2024 --month 5 --format json --no-ai
"""

import argparse
import json
import sys
from typing import Any, Dict

try:
    from ..analysis.manager_report import ManagerSalesReport
    from ..core.database import ConnectionType
    from .ai_insights import ReportAIInsights
    from .html_generator import HTMLReportGenerator
    from .matplotlib_charts import ReportChartGenerator
    from .pdf_generator import PDFReportGenerator
except ImportError:
    import sys
    from pathlib import Path

    src_path = Path(__file__).parent.parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from business_analyzer.analysis.manager_report import ManagerSalesReport
    from business_analyzer.core.database import ConnectionType
    from business_analyzer.reports.ai_insights import ReportAIInsights
    from business_analyzer.reports.html_generator import HTMLReportGenerator
    from business_analyzer.reports.matplotlib_charts import ReportChartGenerator
    from business_analyzer.reports.pdf_generator import PDFReportGenerator


def _print_summary(report: Dict[str, Any]) -> None:
    meta = report.get("metadata", {})
    summary = report.get("summary", {})
    formatted = report.get("formatted", {}).get("summary", {})

    print("=" * 60)
    scope = (
        f"Sede {meta.get('branch_name')}"
        if meta.get("branch_name")
        else "Depósito Trujillo (Consolidado)"
    )
    print(
        f"  INFORME DE VENTAS — MES: {meta.get('month_name', '')} {meta.get('year', '')}"
    )
    print(f"  Alcance:      {scope}")
    print("=" * 60)
    print(f"  Período:      {meta.get('start_date', '')} a {meta.get('end_date', '')}")
    print(f"  Registros:    {meta.get('record_count', 0):,}")
    print("-" * 60)

    if not summary:
        print("  No se encontraron datos para el período seleccionado.")
        return

    print(
        f"  Facturación (con IVA):    {formatted.get('total_revenue_with_iva', '$0')}"
    )
    print(
        f"  Facturación (sin IVA):    {formatted.get('total_revenue_without_iva', '$0')}"
    )
    print(f"  Costo Total:              {formatted.get('total_cost', '$0')}")
    print(f"  Ganancia Bruta:           {formatted.get('gross_profit', '$0')}")
    print(f"  Margen Bruto:             {formatted.get('gross_margin_pct', '0%')}")
    print("-" * 60)
    print(f"  Unidades Vendidas:        {formatted.get('total_quantity_sold', '0')}")
    print(f"  N° de Transacciones:      {formatted.get('order_count', '0')}")
    print(f"  Ticket Promedio:          {formatted.get('average_order_value', '$0')}")
    print(f"  Ganancia por Pedido:      {formatted.get('average_order_profit', '$0')}")
    print("=" * 60)


def _print_ai_insights(ai_data: Dict[str, Any]) -> None:
    narrative = ai_data.get("ai_analysis_text")
    if narrative:
        print("\n  🤖 ANÁLISIS INTELIGENTE")
        print("-" * 60)
        for line in narrative.split("\n"):
            print(f"  {line}")
        print("-" * 60)

    summary = ai_data.get("executive_summary", [])
    if summary:
        print("\n  📋 RESUMEN EJECUTIVO")
        for item in summary:
            print(f"  • {item}")

    recommendations = ai_data.get("recommendations", [])
    if recommendations:
        print("\n  💡 RECOMENDACIONES")
        for r in recommendations:
            badge = f"[{r['priority']}]"
            print(f"  {badge:<8} {r['area']:<12} {r['action']}")

    risks = ai_data.get("risks", [])
    if risks:
        print("\n  ⚠️  RIESGOS")
        for r in risks:
            print(f"  [{r['level']}] {r['type']}: {r['description']}")

    opportunities = ai_data.get("opportunities", [])
    if opportunities:
        print("\n  🚀 OPORTUNIDADES")
        for o in opportunities:
            print(f"  [{o['impact']}] {o['type']}: {o['description']}")


def _print_top_products(report: Dict[str, Any]) -> None:
    products = report.get("formatted", {}).get("top_products", [])
    if not products:
        return

    print("\n  TOP 15 PRODUCTOS POR FACTURACIÓN")
    print("-" * 80)
    print(f"  {'#':<4} {'Producto':<30} {'Revenue':<14} {'Qty':<8} {'Margen':<10}")
    print("-" * 80)
    for i, p in enumerate(products, 1):
        name = p["product_name"][:28]
        print(
            f"  {i:<4} {name:<30} {p['total_revenue']:<14} {p['total_quantity']:<8} {p['profit_margin_pct']:<10}"
        )
    print("-" * 80)


def _print_top_customers(report: Dict[str, Any]) -> None:
    customers = report.get("formatted", {}).get("top_customers", [])
    if not customers:
        return

    print("\n  TOP 15 CLIENTES POR FACTURACIÓN (incluye ganancia)")
    print("-" * 90)
    print(
        f"  {'#':<4} {'Cliente':<30} {'Revenue':<14} {'Ganancia':<14} {'Margen':<8} {'Pedidos':<8}"
    )
    print("-" * 90)
    for i, c in enumerate(customers, 1):
        name = c["customer_name"][:28]
        print(
            f"  {i:<4} {name:<30} {c['total_revenue']:<14} {c.get('profit','0'):<14} {c.get('profit_margin_pct','0'):<8} {c['total_orders']:<8}"
        )
    print("-" * 90)


def _print_category_breakdown(report: Dict[str, Any]) -> None:
    categories = report.get("formatted", {}).get("category_breakdown", [])
    if not categories:
        return

    print("\n  DESGLOSE POR CATEGORÍA")
    print("-" * 80)
    print(f"  {'Categoría':<40} {'Revenue':<14} {'Margen':<10}")
    print("-" * 80)
    for c in categories[:10]:
        path = c["category_path"][:38]
        print(f"  {path:<40} {c['total_revenue']:<14} {c['profit_margin_pct']:<10}")
    print("-" * 80)


def _print_inventory_insights(report: Dict[str, Any]) -> None:
    insights = report.get("inventory_insights", {})
    low_stock = insights.get("low_stock_alert", [])
    fast_movers = insights.get("fast_movers_in_month", [])

    if not low_stock and not fast_movers:
        return

    print("\n  ALERTAS DE INVENTARIO (J3System)")
    print("-" * 80)
    if low_stock:
        print("  ⚠️  Stock Bajo (≤ 10 unidades):")
        for item in low_stock[:10]:
            stock = (
                f"{item['current_stock']:.0f}"
                if item["current_stock"] is not None
                else "N/A"
            )
            name = item["product_name"][:30]
            print(
                f"      {name:<32} Vendido: {item['quantity_sold']:<6} Stock: {stock}"
            )
    else:
        print("  ✓ Sin alertas de stock bajo.")

    if fast_movers:
        print("\n  🔥 Productos Más Vendidos del Mes:")
        for item in fast_movers[:5]:
            name = item["product_name"][:30]
            print(f"      {name:<32} Vendido: {item['quantity_sold']}")
    print("-" * 80)


def _print_vendor_sales(report: Dict[str, Any]) -> None:
    vendors = report.get("formatted", {}).get("vendor_sales", [])
    if not vendors:
        return

    print("\n  🏭 VENTAS POR PROVEEDOR")
    print("-" * 80)
    print(
        f"  {'#':<3} {'Proveedor':<22} {'Revenue':<14} {'%':<8} {'Margen':<10} {'Pedidos':<8}"
    )
    print("-" * 80)
    for i, v in enumerate(vendors[:15], 1):
        name = v["vendor_name"][:20]
        print(
            f"  {i:<3} {name:<22} {v['total_revenue']:<14} {v['revenue_pct']:<8} {v['profit_margin_pct']:<10} {v['transactions']:<8}"
        )
    print("-" * 80)


def _print_marca_sales(report: Dict[str, Any]) -> None:
    marcas = report.get("formatted", {}).get("marca_sales", [])
    if not marcas:
        return

    print("\n  🏷️  VENTAS POR MARCA / LÍNEA")
    print("-" * 80)
    print(
        f"  {'#':<3} {'Marca/Línea':<22} {'Revenue':<14} {'%':<8} {'Margen':<10} {'Pedidos':<8}"
    )
    print("-" * 80)
    for i, m in enumerate(marcas[:15], 1):
        name = m["marca_name"][:20]
        print(
            f"  {i:<3} {name:<22} {m['total_revenue']:<14} {m['revenue_pct']:<8} {m['profit_margin_pct']:<10} {m['transactions']:<8}"
        )
    print("-" * 80)


def _print_suggested_orders(report: Dict[str, Any]) -> None:
    suggestions = report.get("formatted", {}).get("customer_order_suggestions", [])
    if not suggestions:
        return

    print("\n  📋 PEDIDOS SUGERIDOS POR CLIENTE")
    print("-" * 110)
    for s in suggestions[:5]:
        print(f"  🏪 {s['customer_name'][:35]}")
        print(f"     Total sugerido: {s['total_suggested']} unidades")
        for i in s.get("suggested_items", [])[:5]:
            stock = i.get("current_stock", "N/A")
            vendor = i.get("primary_vendor", "") or ""
            marca = i.get("marca", "") or ""
            print(f"     ▶ {i['product_name'][:35]}")
            if marca:
                print(f"       Marca: {marca[:20]}")
            if vendor:
                print(f"       Proveedor: {vendor[:20]}")
            print(
                f"       Stock: {stock:<6} Promedio/mes: {i['avg_monthly']:<8} Sugerido: {i['suggested_order']}"
            )
        print("-" * 110)


def _print_cross_sell(report: Dict[str, Any]) -> None:
    recs = report.get("formatted", {}).get("shopping_recommendations", {})
    cross_sell = recs.get("cross_sell", [])
    high_margin = recs.get("high_margin_promote", [])

    if cross_sell:
        print("\n  🔗 RECOMENDACIONES DE COMPRA CRUZADA")
        print("-" * 80)
        for r in cross_sell[:5]:
            with_recom = [
                cr["product_name"][:25] for cr in r.get("recommended_with", [])
            ]
            print(f"  📦 {r['product_name'][:30]}")
            print(f"     Los compradores también llevan: {', '.join(with_recom)}")
        print("-" * 80)

    if high_margin:
        print("\n  ⭐ PRODUCTOS DE ALTO MARGEN (recomendados para promocionar)")
        print("-" * 80)
        print(f"  {'Producto':<35} {'Margen':<10} {'Vendidos':<10}")
        print("-" * 80)
        for p in high_margin[:8]:
            name = p["product_name"][:33]
            print(f"  {name:<35} {p['margin_pct']:<10} {p['quantity_sold']:<10}")
        print("-" * 80)


def _print_customer_vendor_mix(report: Dict[str, Any]) -> None:
    mix = report.get("customer_vendor_mix", [])
    if not mix:
        return
    print("\n  🔗 MIX CLIENTES-PROVEEDORES (Top)")
    print("-" * 80)
    for m in mix[:5]:
        print(
            f"  🏪 {m['customer_name'][:30]} — {m['vendor_count']} proveedores, ${m['total_revenue']:,.0f}".replace(
                ",", "."
            )
        )
        tops = ", ".join(
            [
                f"{v['vendor_name'][:12]}({v['pct']:.0f}%)"
                for v in m.get("top_vendors", [])[:3]
            ]
        )
        print(f"     Principales: {tops}")
    print("-" * 80)


def _print_procurement_plan(report: Dict[str, Any]) -> None:
    plan = report.get("procurement_plan", [])
    if not plan:
        return
    print("\n  🛒 PLAN DE COMPRAS / ABASTECIMIENTO POR PROVEEDOR")
    print("-" * 90)
    for p in plan[:6]:
        print(
            f"  🏭 {p['vendor_name'][:28]} | Unidades sugeridas: {p['total_suggested_units']} | Clientes afectados: {p['affected_customers']}"
        )
        for kp in p.get("key_products", [])[:3]:
            print(
                f"     • {kp['product_name'][:30]}: {kp['suggested_order']} uds (de {kp['affected_customers']} clientes)"
            )
    print("-" * 90)


def _print_abc_analysis(report: Dict[str, Any]) -> None:
    abc = report.get("abc_analysis", {})
    if not abc:
        return
    print("\n  📊 ANÁLISIS ABC (80/15/5)")
    print("-" * 80)
    for dim in ["products", "customers", "vendors"]:
        d = abc.get(dim, {})
        if not d:
            continue
        print(f"  {dim.upper()}:")
        for k in ["a", "b", "c"]:
            if k in d:
                print(
                    f"    {k.upper()}: {d[k].get('count',0)} items, {d[k].get('revenue_pct',0)}% revenue"
                )
    print("-" * 80)


def _print_stock_replenishment(report: Dict[str, Any]) -> None:
    repl = report.get("stock_replenishment_suggestions", []) or report.get(
        "formatted", {}
    ).get("stock_replenishment_suggestions", [])
    if not repl:
        return
    print("\n  🛒 SUGERENCIAS DE REABASTECIMIENTO (STOCK BAJO - J3)")
    print("-" * 80)
    for s in repl[:6]:
        print(
            f"  • {s.get('product_name','')[:35]} | Marca: {s.get('marca','')[:12]} | Prov: {s.get('proveedor','')[:12]} | Stock: {s.get('current_stock')} | Vend: {s.get('recent_sold')}"
        )
    print("-" * 80)


def _print_text_report(report: Dict[str, Any], ai_data: Dict[str, Any]) -> None:
    _print_summary(report)
    _print_ai_insights(ai_data)
    _print_vendor_sales(report)
    _print_marca_sales(report)
    _print_top_products(report)
    _print_top_customers(report)
    _print_category_breakdown(report)
    _print_inventory_insights(report)
    _print_suggested_orders(report)
    _print_cross_sell(report)
    _print_customer_vendor_mix(report)
    _print_procurement_plan(report)
    _print_abc_analysis(report)
    _print_stock_replenishment(report)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera el informe mensual de ventas para gerencia."
    )
    parser.add_argument("--year", type=int, required=True, help="Año del informe")
    parser.add_argument(
        "--month", type=int, required=True, help="Mes del informe (1-12)"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "html", "pdf"],
        default="text",
        help="Formato de salida (default: text)",
    )
    parser.add_argument(
        "--no-j3system",
        action="store_true",
        help="Omitir enriquecimiento con datos de J3System",
    )
    parser.add_argument(
        "--connection-type",
        choices=["direct", "navicat", "ssh_tunnel"],
        default="direct",
        help="Tipo de conexión a la base de datos",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Ruta para guardar el informe (requerido para html/pdf)",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Omitir generación de insights con IA",
    )
    parser.add_argument(
        "--ai-provider",
        type=str,
        default=None,
        help="Proveedor de IA para insights (grok, openai, anthropic, ollama)",
    )
    parser.add_argument(
        "--chart-dir",
        type=str,
        default="reports/charts",
        help="Directorio para guardar gráficos temporales",
    )
    parser.add_argument(
        "--branch",
        type=str,
        default=None,
        help="Sede del informe: sika_center (FEF), calle_5 (FET), almacen_principal (FED)",
    )

    args = parser.parse_args()

    # Validate output path for html/pdf
    if args.format in ("html", "pdf") and not args.output:
        print(
            "❌ Error: --output es requerido para formatos html y pdf",
            file=sys.stderr,
        )
        sys.exit(1)

    branch_code = None
    if args.branch:
        from business_analyzer.analysis.manager_report.helpers import BRANCH_SLUGS

        branch_key = args.branch.strip().lower().replace("-", "_")
        slug_to_code = {slug: code for code, slug in BRANCH_SLUGS.items()}
        branch_code = slug_to_code.get(branch_key)
        if branch_code is None and branch_key.upper() in BRANCH_SLUGS:
            branch_code = branch_key.upper()
        if branch_code is None:
            print(
                f"❌ Error: sede desconocida '{args.branch}'. "
                f"Opciones: {', '.join(sorted(slug_to_code))}",
                file=sys.stderr,
            )
            sys.exit(1)

    try:
        scope_label = f" ({args.branch})" if args.branch else ""
        print(f"📊 Generando informe para {args.month:02d}/{args.year}{scope_label}...")
        report = ManagerSalesReport(
            year=args.year,
            month=args.month,
            use_j3system=not args.no_j3system,
            db_connection_type=ConnectionType(args.connection_type),
            branch_document_code=branch_code,
        )
        data = report.generate()
        print(f"✓ Datos cargados: {data['metadata']['record_count']:,} registros")
    except Exception as e:
        print(f"❌ Error generando el informe: {e}", file=sys.stderr)
        sys.exit(1)

    # Generate AI insights
    ai_data: Dict[str, Any] = {}
    if not args.no_ai:
        try:
            print("🤖 Generando insights con IA...")
            insights = ReportAIInsights(data, provider=args.ai_provider)
            ai_data = insights.generate()
            if ai_data.get("ai_analysis_text"):
                print("✓ Análisis narrativo de IA generado")
            else:
                print("ℹ️ Insights computados sin análisis narrativo")
        except Exception as e:
            print(f"⚠️ Error generando insights de IA: {e}")
            ai_data = {}

    # Generate charts for html/pdf
    chart_paths: Dict[str, str] = {}
    if args.format in ("html", "pdf"):
        try:
            print("📈 Generando gráficos...")
            chart_gen = ReportChartGenerator(data, output_dir=args.chart_dir)
            chart_paths = chart_gen.generate_all()
            print(f"✓ {len(chart_paths)} gráficos generados")
        except Exception as e:
            print(f"⚠️ Error generando gráficos: {e}")

    # Output based on format
    if args.format == "json":
        output_data = {"report": data, "ai_insights": ai_data}
        output = json.dumps(output_data, indent=2, ensure_ascii=False, default=str)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"✓ Informe JSON guardado en: {args.output}")
        else:
            print(output)

    elif args.format == "html":
        try:
            print("🌐 Generando HTML...")
            html_gen = HTMLReportGenerator(data, chart_paths, ai_data)
            html_path = html_gen.generate(args.output)
            print(f"✓ Informe HTML guardado en: {html_path}")
        except Exception as e:
            print(f"❌ Error generando HTML: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.format == "pdf":
        try:
            print("📄 Generando PDF...")
            pdf_gen = PDFReportGenerator(data, chart_paths, ai_data)
            pdf_path = pdf_gen.generate(args.output)
            print(f"✓ Informe PDF guardado en: {pdf_path}")
        except Exception as e:
            print(f"❌ Error generando PDF: {e}", file=sys.stderr)
            sys.exit(1)

    else:  # text
        _print_text_report(data, ai_data)
        if args.output:
            output_data = {"report": data, "ai_insights": ai_data}
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)
            print(f"\n✓ Datos guardados en: {args.output}")


if __name__ == "__main__":
    main()
