#!/usr/bin/env python3
"""Generar reporte comprensivo PRODUCTOS SIKA en español"""
import json

with open('/home/yderf/sika_analysis_report.json', 'r') as f:
    data = json.load(f)

report = []

# ENCABEZADO
report.append("# PRODUCTOS SIKA - Análisis Empresarial Comprensivo")
report.append(f"**Período:** 2024-2025 (Año Completo)")
report.append(f"**Generado:** {data['generated_at']}")
report.append(f"**Filtro:** `{data['filter']}`")
report.append("")
report.append("**Nota:** Todos los valores excluyen impuestos (valores antes de IVA)")
report.append("")
report.append("---")
report.append("")

# RESUMEN EJECUTIVO
report.append("## Resumen Ejecutivo")
report.append("")

s24 = data['summary'].get('2024', {})
s25 = data['summary'].get('2025', {})

if s24 and s25:
    rev_growth = ((s25['net_revenue'] - s24['net_revenue']) / s24['net_revenue'] * 100)
    profit_growth = ((s25['net_profit'] - s24['net_profit']) / s24['net_profit'] * 100)
    cust_growth = ((s25['unique_customers'] - s24['unique_customers']) / s24['unique_customers'] * 100)

    report.append("### Aspectos Destacados")
    report.append("")
    report.append(f"- **Crecimiento de Ingresos:** {rev_growth:+.1f}% interanual (${s24['net_revenue']:,.0f} → ${s25['net_revenue']:,.0f})")
    report.append(f"- **Crecimiento de Utilidad:** {profit_growth:+.1f}% interanual (${s24['net_profit']:,.0f} → ${s25['net_profit']:,.0f})")
    report.append(f"- **Crecimiento de Clientes:** {cust_growth:+.1f}% interanual ({int(s24['unique_customers']):,} → {int(s25['unique_customers']):,} clientes)")
    report.append(f"- **Mejora de Margen:** {(s24['net_profit']/s24['net_revenue']*100):.1f}% → {(s25['net_profit']/s25['net_revenue']*100):.1f}%")
    report.append("")

# TABLA COMPARATIVA ANUAL
report.append("## Comparación de Desempeño Anual")
report.append("")
report.append("| Métrica | 2024 | 2025 | Cambio | % Cambio |")
report.append("|---------|------|------|--------|----------|")

if s24 and s25:
    metrics = [
        ("Ingresos (sin IVA)", 'net_revenue', True),
        ("Utilidad", 'net_profit', True),
        ("Margen de Utilidad %", None, False),
        ("Clientes", 'unique_customers', False),
        ("Transacciones", 'transactions', False),
        ("Ticket Promedio", 'avg_transaction_value', True),
        ("Productos Vendidos", 'net_units', False),
        ("Devoluciones", 'returns', False),
    ]

    for label, key, is_currency in metrics:
        if key is None:  # Margen de utilidad
            v24 = s24['net_profit'] / s24['net_revenue'] * 100
            v25 = s25['net_profit'] / s25['net_revenue'] * 100
            change = v25 - v24
            pct = (change / v24 * 100) if v24 else 0
            report.append(f"| {label} | {v24:.1f}% | {v25:.1f}% | {change:+.1f}pp | {pct:+.1f}% |")
        else:
            v24 = s24[key]
            v25 = s25[key]
            change = v25 - v24
            pct = (change / v24 * 100) if v24 else 0

            if is_currency:
                report.append(f"| {label} | ${v24:,.0f} | ${v25:,.0f} | ${change:,.0f} | {pct:+.1f}% |")
            else:
                report.append(f"| {label} | {v24:,.0f} | {v25:,.0f} | {change:,.0f} | {pct:+.1f}% |")

report.append("")

# TENDENCIAS MENSUALES
report.append("## Tendencias de Ventas Mensuales")
report.append("")
report.append("### Comparación Mensual 2024 vs 2025")
report.append("")
report.append("| Mes | Ingresos 2024 | Clientes 2024 | Ingresos 2025 | Clientes 2025 | Crecimiento % |")
report.append("|-----|---------------|---------------|---------------|---------------|---------------|")

month_names = {1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
               7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}

# Agrupar por mes
monthly_2024 = {int(m['month']): m for m in data['monthly_sales'] if m['year'] == 2024}
monthly_2025 = {int(m['month']): m for m in data['monthly_sales'] if m['year'] == 2025}

for month_num in range(1, 13):
    m24 = monthly_2024.get(month_num, {})
    m25 = monthly_2025.get(month_num, {})

    if m24 or m25:
        month = month_names[month_num]
        rev24 = m24.get('revenue', 0)
        cust24 = int(m24.get('customers', 0))
        rev25 = m25.get('revenue', 0)
        cust25 = int(m25.get('customers', 0))

        growth = ((rev25 - rev24) / rev24 * 100) if rev24 else 0

        r24_str = f"${rev24:,.0f}" if rev24 else "-"
        c24_str = f"{cust24:,}" if cust24 else "-"
        r25_str = f"${rev25:,.0f}" if rev25 else "-"
        c25_str = f"{cust25:,}" if cust25 else "-"
        g_str = f"{growth:+.1f}%" if rev24 and rev25 else "-"

        report.append(f"| {month} | {r24_str} | {c24_str} | {r25_str} | {c25_str} | {g_str} |")

report.append("")

# ANÁLISIS DE CLIENTES
report.append("## Análisis de Clientes")
report.append("")

# Segmentación de Clientes
report.append("### Segmentación de Clientes")
report.append("")
report.append("| Segmento | Año | Clientes | Ingresos | Ingreso Prom/Cliente | % del Total |")
report.append("|----------|-----|----------|----------|---------------------|-------------|")

# Calcular ingresos totales por año
total_2024 = sum(s['segment_revenue'] for s in data['customer_segments'] if s['ano'] == 2024)
total_2025 = sum(s['segment_revenue'] for s in data['customer_segments'] if s['ano'] == 2025)

segment_names = {
    'VIP (>50M)': 'VIP (>$50M)',
    'High Value (10M-50M)': 'Alto Valor ($10M-50M)',
    'Medium (5M-10M)': 'Medio ($5M-10M)',
    'Regular (1M-5M)': 'Regular ($1M-5M)',
    'Occasional (<1M)': 'Ocasional (<$1M)'
}

for seg in data['customer_segments']:
    year = int(seg['ano'])
    total = total_2024 if year == 2024 else total_2025
    pct = (seg['segment_revenue'] / total * 100) if total else 0
    seg_name = segment_names.get(seg['segment'], seg['segment'])

    report.append(f"| {seg_name} | {year} | {int(seg['num_customers']):,} | "
                 f"${seg['segment_revenue']:,.0f} | ${seg['avg_revenue_per_customer']:,.0f} | {pct:.1f}% |")

report.append("")

# Top Clientes
report.append("### Top 20 Clientes por Ingresos")
report.append("")
report.append("#### 2024 - Principales Clientes")
report.append("")
report.append("| # | Cliente | Pedidos | Ingresos | Utilidad | Pedido Prom | Margen % |")
report.append("|---|---------|---------|----------|----------|-------------|----------|")

top_2024 = sorted([c for c in data['top_customers'] if c['year'] == 2024],
                   key=lambda x: x['total_revenue'], reverse=True)[:20]
for i, cust in enumerate(top_2024, 1):
    margin = (cust['total_profit'] / cust['total_revenue'] * 100) if cust['total_revenue'] else 0
    cust_name = (cust['customer_name'] or 'Desconocido')[:35]
    report.append(f"| {i} | {cust_name} | {int(cust['num_orders']):,} | "
                 f"${cust['total_revenue']:,.0f} | ${cust['total_profit']:,.0f} | "
                 f"${cust['avg_order_value']:,.0f} | {margin:.1f}% |")

report.append("")
report.append("#### 2025 - Principales Clientes")
report.append("")
report.append("| # | Cliente | Pedidos | Ingresos | Utilidad | Pedido Prom | Margen % |")
report.append("|---|---------|---------|----------|----------|-------------|----------|")

top_2025 = sorted([c for c in data['top_customers'] if c['year'] == 2025],
                   key=lambda x: x['total_revenue'], reverse=True)[:20]
for i, cust in enumerate(top_2025, 1):
    margin = (cust['total_profit'] / cust['total_revenue'] * 100) if cust['total_revenue'] else 0
    cust_name = (cust['customer_name'] or 'Desconocido')[:35]
    report.append(f"| {i} | {cust_name} | {int(cust['num_orders']):,} | "
                 f"${cust['total_revenue']:,.0f} | ${cust['total_profit']:,.0f} | "
                 f"${cust['avg_order_value']:,.0f} | {margin:.1f}% |")

report.append("")

# ANÁLISIS DE PROVEEDORES - REMOVIDO (SIKA es el proveedor implícito)

# ANÁLISIS DE PRODUCTOS
report.append("## Análisis de Desempeño de Productos")
report.append("")

# Desempeño por Subcategoría
report.append("### Desempeño por Subcategoría")
report.append("")
report.append("| Subcategoría | Año | Productos | Clientes | Ingresos | Utilidad | Margen % | Trans. |")
report.append("|--------------|-----|-----------|----------|----------|----------|----------|--------|")

for subcat in data['subcategory_performance']:
    subcat_name = (subcat['subcategoria'] or 'N/A')[:20]
    report.append(f"| {subcat_name} | {int(subcat['year'])} | {int(subcat['num_products']):,} | "
                 f"{int(subcat['num_customers']):,} | ${subcat['revenue']:,.0f} | "
                 f"${subcat['profit']:,.0f} | {subcat['margin_pct']:.1f}% | {int(subcat['transactions']):,} |")

report.append("")

# Top 15 Productos Más Rentables
report.append("### Top 15 Productos Más Rentables")
report.append("")
report.append("#### 2024")
report.append("")
report.append("| # | Producto | SKU | Ingresos | Utilidad | Margen % | Clientes |")
report.append("|---|----------|-----|----------|----------|----------|----------|")

prof_2024 = sorted([p for p in data['most_profitable'] if p['year'] == 2024],
                    key=lambda x: x['profit'], reverse=True)[:15]
for i, prod in enumerate(prof_2024, 1):
    prod_name = (prod['product_name'] or 'Desconocido')[:45]
    report.append(f"| {i} | {prod_name} | {prod['sku']} | ${prod['revenue']:,.0f} | "
                 f"${prod['profit']:,.0f} | {prod['margin_pct']:.1f}% | {int(prod['unique_customers']):,} |")

report.append("")
report.append("#### 2025")
report.append("")
report.append("| # | Producto | SKU | Ingresos | Utilidad | Margen % | Clientes |")
report.append("|---|----------|-----|----------|----------|----------|----------|")

prof_2025 = sorted([p for p in data['most_profitable'] if p['year'] == 2025],
                    key=lambda x: x['profit'], reverse=True)[:15]
for i, prod in enumerate(prof_2025, 1):
    prod_name = (prod['product_name'] or 'Desconocido')[:45]
    report.append(f"| {i} | {prod_name} | {prod['sku']} | ${prod['revenue']:,.0f} | "
                 f"${prod['profit']:,.0f} | {prod['margin_pct']:.1f}% | {int(prod['unique_customers']):,} |")

report.append("")

# INSIGHTS Y RECOMENDACIONES
report.append("## Hallazgos Clave y Recomendaciones Estratégicas")
report.append("")

if s24 and s25:
    report.append("### 📈 Desempeño de Crecimiento")
    report.append("")

    rev_growth = ((s25['net_revenue'] - s24['net_revenue']) / s24['net_revenue'] * 100)
    profit_growth = ((s25['net_profit'] - s24['net_profit']) / s24['net_profit'] * 100)

    if rev_growth > 15:
        report.append(f"- **Fuerte Crecimiento de Ingresos:** {rev_growth:.1f}% interanual indica demanda robusta del mercado para PRODUCTOS SIKA")
    else:
        report.append(f"- **Crecimiento Moderado de Ingresos:** {rev_growth:.1f}% interanual - considerar estrategias de expansión")

    if profit_growth > rev_growth:
        report.append(f"- **Expansión de Márgenes:** Utilidad creciendo más rápido que ingresos ({profit_growth:.1f}% vs {rev_growth:.1f}%) muestra mejora en eficiencia operativa")

    report.append("")

    # Patrones mensuales
    report.append("### 📅 Patrones Estacionales")
    report.append("")

    # Encontrar mejores/peores meses
    monthly_sorted_24 = sorted(monthly_2024.items(), key=lambda x: x[1].get('revenue', 0), reverse=True)
    monthly_sorted_25 = sorted(monthly_2025.items(), key=lambda x: x[1].get('revenue', 0), reverse=True)

    if monthly_sorted_24:
        best_month_24 = month_names[monthly_sorted_24[0][0]]
        best_rev_24 = monthly_sorted_24[0][1]['revenue']
        worst_month_24 = month_names[monthly_sorted_24[-1][0]]

        report.append(f"**Análisis 2024:**")
        report.append(f"- Mejor mes: **{best_month_24}** (${best_rev_24:,.0f})")
        report.append(f"- Mes más débil: **{worst_month_24}**")
        report.append("")

    if monthly_sorted_25 and len(monthly_2025) > 0:
        best_month_25 = month_names[monthly_sorted_25[0][0]]
        best_rev_25 = monthly_sorted_25[0][1]['revenue']
        report.append(f"**Análisis 2025:**")
        report.append(f"- Mejor mes: **{best_month_25}** (${best_rev_25:,.0f})")
        report.append("")

    # Insights de clientes
    report.append("### 👥 Hallazgos de Clientes")
    report.append("")

    cust_growth = ((s25['unique_customers'] - s24['unique_customers']) / s24['unique_customers'] * 100)
    report.append(f"- **Crecimiento de Base de Clientes:** {cust_growth:+.1f}% ({int(s24['unique_customers']):,} → {int(s25['unique_customers']):,})")

    # Concentración de clientes
    if top_2024:
        top5_revenue = sum(c['total_revenue'] for c in top_2024[:5])
        top5_pct = (top5_revenue / s24['net_revenue'] * 100) if s24['net_revenue'] else 0
        report.append(f"- **Concentración de Clientes (2024):** Top 5 clientes representan {top5_pct:.1f}% de ingresos")

    if top_2025:
        top5_revenue_25 = sum(c['total_revenue'] for c in top_2025[:5])
        top5_pct_25 = (top5_revenue_25 / s25['net_revenue'] * 100) if s25['net_revenue'] else 0
        report.append(f"- **Concentración de Clientes (2025):** Top 5 clientes representan {top5_pct_25:.1f}% de ingresos")

        if top5_pct_25 < top5_pct:
            report.append("  - ✅ Reducción de concentración indica diversificación saludable de clientes")
        else:
            report.append("  - ⚠️ Aumento de concentración - considerar iniciativas de adquisición de clientes")

    report.append("")

    # Insights de proveedores - REMOVIDO (SIKA es el proveedor implícito)

    # Insights de productos
    report.append("### 🛍️ Portafolio de Productos")
    report.append("")

    sku_count = int(s24['unique_products'])
    report.append(f"- **SKUs Activos:** {sku_count} productos")

    if prof_2024 and prof_2025:
        top_product_24 = prof_2024[0]
        top_product_25 = prof_2025[0]
        top_prod_contrib_24 = (top_product_24['revenue'] / s24['net_revenue'] * 100) if s24['net_revenue'] else 0

        report.append(f"- **Producto Estrella (2024):** {top_product_24['product_name'][:50]}")
        report.append(f"  - Ingresos: ${top_product_24['revenue']:,.0f} ({top_prod_contrib_24:.1f}% del total)")
        report.append(f"- **Producto Estrella (2025):** {top_product_25['product_name'][:50]}")
        report.append(f"  - Ingresos: ${top_product_25['revenue']:,.0f}")

        if top_product_24['product_name'] != top_product_25['product_name']:
            report.append(f"  - 📊 **Cambio en liderazgo:** {top_product_25['product_name'][:40]} superó a {top_product_24['product_name'][:40]}")

    report.append("")

    # Recomendaciones
    report.append("### 💡 Recomendaciones Estratégicas")
    report.append("")

    if rev_growth > 15 and profit_growth > 20:
        report.append("1. **Escalar Operaciones:**")
        report.append("   - Trayectoria de crecimiento fuerte sugiere oportunidad para expansión de capacidad")
        report.append("   - Considerar optimización de inventario para meses de alta demanda (Mar, May, Jul)")
        report.append("")

    if cust_growth < 10:
        report.append("2. **Adquisición de Clientes:**")
        report.append("   - Enfocarse en adquisición de nuevos clientes para impulsar crecimiento")
        report.append("   - Desarrollar programas de referidos con clientes existentes")
        report.append("")

    if top5_pct > 25:
        report.append("3. **Reducir Riesgo de Concentración:**")
        report.append("   - Desarrollar estrategias para diversificar base de clientes")
        report.append("   - Implementar planes de retención para clientes medianos (evitar dependencia de VIPs)")
        report.append("")

    report.append("4. **Optimización de Inventario:**")
    report.append("   - Alinear niveles de stock con patrones de demanda mensual")
    report.append("   - Aumentar stock en meses de alto rendimiento (Marzo, Mayo, Julio)")
    report.append("")

    report.append("5. **Programa de Retención de Clientes:**")
    report.append("   - Implementar incentivos de lealtad para segmentos VIP y Alto Valor (63% de ingresos)")
    report.append("   - Crear programa de beneficios escalonados por volumen de compra")
    report.append("")

    report.append("6. **Optimización de Mix de Productos:**")
    report.append("   - Duplicar esfuerzos en productos SIKA MULTI-SEAL (crecimiento más rápido)")
    report.append("   - Investigar productos con rendimiento decreciente")
    report.append("")

    # Alerta de devoluciones
    returns_growth = ((s25['returns'] - s24['returns']) / s24['returns'] * 100) if s24['returns'] else 0
    if returns_growth > 100:
        report.append("7. **URGENTE - Gestión de Devoluciones:**")
        report.append(f"   - ⚠️ **Incremento crítico de devoluciones:** {returns_growth:+.0f}% ({int(s24['returns']):,} → {int(s25['returns']):,} unidades)")
        report.append("   - Realizar análisis de causa raíz inmediato")
        report.append("   - Revisar control de calidad con proveedor SIKA")
        report.append("   - Verificar procesos de almacenamiento y manejo")
        report.append("")

    report.append("8. **Expansión de Mercado:**")
    report.append("   - Objetivo: Crecer en meses de bajo rendimiento (Ene, Jun, Nov)")
    report.append("   - Enfoque en convertir clientes \"Ocasionales\" a \"Regulares\"")

report.append("")
report.append("---")
report.append("")
report.append("## Glosario de Términos")
report.append("")
report.append("- **Ingresos (sin IVA):** Ventas totales antes de impuestos")
report.append("- **Utilidad:** Ganancia neta después de costos")
report.append("- **Margen:** Porcentaje de utilidad sobre ingresos")
report.append("- **Ticket Promedio:** Valor promedio por transacción")
report.append("- **SKU:** Unidad de Mantenimiento de Stock (código de producto)")
report.append("- **Interanual (YoY):** Año sobre año")
report.append("")
report.append("---")
report.append("")
report.append("*Reporte generado desde base de datos SmartBusiness*")
report.append("")
report.append(f"*Fecha de generación: {data['generated_at']}*")

# Escribir reporte
with open('/home/yderf/REPORTE_SIKA_ESPANOL.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(report))

print("✅ Reporte en español generado: /home/yderf/REPORTE_SIKA_ESPANOL.md")
