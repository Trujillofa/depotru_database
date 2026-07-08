"""
HTML Report Generator for Manager Sales Reports
=================================================

Generates a professional, self-contained HTML report with embedded
charts, tables, AI insights, and Colombian formatting.

Usage:
    from src.business_analyzer.reports.html_generator import HTMLReportGenerator

    gen = HTMLReportGenerator(report_data, chart_paths, ai_insights)
    html_path = gen.generate(output_path="report_mayo_2024.html")
"""

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Template


def _shopping_section(recommendations: Any, key: str) -> List[Any]:
    if isinstance(recommendations, dict):
        value = recommendations.get(key, [])
        return value if isinstance(value, list) else []
    return []


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Informe de Ventas — {{ report_scope }} — {{ month_name }} {{ year }}</title>
    <style>
        :root {
            --primary: #1e3a5f;
            --secondary: #2563eb;
            --accent: #16a34a;
            --warning: #f59e0b;
            --danger: #dc2626;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text: #1f2937;
            --text-muted: #6b7280;
            --border: #e5e7eb;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 0;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
        header {
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            color: white;
            padding: 2.5rem 2rem;
            text-align: center;
            margin-bottom: 2rem;
            border-radius: 0 0 1.5rem 1.5rem;
        }
        header h1 { font-size: 2rem; font-weight: 700; margin-bottom: 0.5rem; }
        header p { opacity: 0.9; font-size: 1rem; }
        .badge {
            display: inline-block;
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .badge-success { background: #dcfce7; color: #166534; }
        .badge-warning { background: #fef3c7; color: #92400e; }
        .badge-danger { background: #fee2e2; color: #991b1b; }
        .badge-info { background: #dbeafe; color: #1e40af; }
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .kpi-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 1rem;
            padding: 1.5rem;
            text-align: center;
            transition: transform 0.15s, box-shadow 0.15s;
        }
        .kpi-card:hover { transform: translateY(-3px); box-shadow: 0 10px 25px rgba(0,0,0,0.08); }
        .kpi-label { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.5rem; }
        .kpi-value { font-size: 1.6rem; font-weight: 700; color: var(--primary); }
        .kpi-value.green { color: var(--accent); }
        .kpi-value.red { color: var(--danger); }
        .kpi-value.blue { color: var(--secondary); }
        .kpi-value.orange { color: var(--warning); }
        .section { background: var(--card-bg); border: 1px solid var(--border); border-radius: 1rem; padding: 1.5rem; margin-bottom: 1.5rem; }
        .section h2 { font-size: 1.25rem; color: var(--primary); margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }
        .section h3 { font-size: 1rem; color: var(--text-muted); margin: 1rem 0 0.5rem; }
        .chart-container { text-align: center; margin: 1rem 0; }
        .chart-container img { max-width: 100%; height: auto; border-radius: 0.5rem; border: 1px solid var(--border); }
        table { width: 100%; border-collapse: collapse; margin-top: 0.5rem; }
        th, td { padding: 0.6rem 0.75rem; text-align: left; border-bottom: 1px solid var(--border); font-size: 0.9rem; }
        th { background: #f1f5f9; font-weight: 600; color: var(--primary); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.03em; }
        tr:hover { background: #f8fafc; }
        td.num { font-family: 'SF Mono', monospace; text-align: right; }
        .insights-box {
            background: linear-gradient(135deg, #eff6ff, #f0fdf4);
            border-left: 4px solid var(--secondary);
            padding: 1.25rem;
            border-radius: 0.5rem;
            margin: 1rem 0;
        }
        .insights-box h4 { color: var(--primary); margin-bottom: 0.5rem; font-size: 0.95rem; }
        .insights-box ul { margin-left: 1.2rem; }
        .insights-box li { margin-bottom: 0.4rem; font-size: 0.9rem; }
        .recommendation {
            display: flex; gap: 0.75rem; align-items: flex-start;
            padding: 0.75rem; border-radius: 0.5rem; margin-bottom: 0.5rem;
            background: #f8fafc; border: 1px solid var(--border);
        }
        .risk-card { padding: 0.75rem; border-radius: 0.5rem; margin-bottom: 0.5rem; border-left: 3px solid; }
        .risk-high { background: #fef2f2; border-left-color: var(--danger); }
        .risk-medium { background: #fffbeb; border-left-color: var(--warning); }
        .risk-low { background: #f0fdf4; border-left-color: var(--accent); }
        .opportunity-card { background: #eff6ff; border-left: 3px solid var(--secondary); padding: 0.75rem; border-radius: 0.5rem; margin-bottom: 0.5rem; }
        .ai-narrative { background: #faf5ff; border: 1px solid #e9d5ff; border-radius: 0.75rem; padding: 1.5rem; line-height: 1.8; white-space: pre-wrap; }
        .footer { text-align: center; padding: 2rem; color: var(--text-muted); font-size: 0.8rem; margin-top: 2rem; }
        .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
        @media (max-width: 768px) {
            .two-col { grid-template-columns: 1fr; }
            .kpi-grid { grid-template-columns: repeat(2, 1fr); }
            .container { padding: 1rem; }
            header h1 { font-size: 1.5rem; }
        }
    </style>
</head>
<body>
    <header>
        <h1>📊 Informe de Ventas Mensual</h1>
        <p>{{ month_name }} {{ year }} &nbsp;|&nbsp; {{ report_scope }} &nbsp;|&nbsp; Generado: {{ generated_at }}</p>
    </header>

    <div class="container">
        <!-- KPI Cards -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-label">Facturación (con IVA)</div>
                <div class="kpi-value blue">{{ formatted_summary.total_revenue_with_iva }}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Facturación (sin IVA)</div>
                <div class="kpi-value">{{ formatted_summary.total_revenue_without_iva }}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Ganancia Bruta</div>
                <div class="kpi-value green">{{ formatted_summary.gross_profit }}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Margen Bruto</div>
                <div class="kpi-value {% if summary.gross_margin_pct >= 20 %}green{% elif summary.gross_margin_pct >= 10 %}orange{% else %}red{% endif %}">{{ formatted_summary.gross_margin_pct }}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Transacciones</div>
                <div class="kpi-value">{{ formatted_summary.order_count }}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Ticket Promedio</div>
                <div class="kpi-value orange">{{ formatted_summary.average_order_value }}</div>
            </div>
        </div>

        <!-- AI Narrative -->
        {% if ai_narrative %}
        <div class="section">
            <h2>🤖 Análisis Inteligente</h2>
            <div class="ai-narrative">{{ ai_narrative }}</div>
        </div>
        {% endif %}

        <!-- Executive Summary -->
        {% if executive_summary %}
        <div class="section">
            <h2>📋 Resumen Ejecutivo</h2>
            <div class="insights-box">
                <ul>
                {% for item in executive_summary %}
                    <li>{{ item }}</li>
                {% endfor %}
                </ul>
            </div>
        </div>
        {% endif %}

        <!-- Daily Trend Chart -->
        <div class="section">
            <h2>📈 Tendencia Diaria</h2>
            <div class="chart-container">
                <img src="data:image/png;base64,{{ charts.daily_trend }}" alt="Tendencia Diaria">
            </div>
        </div>

        <!-- Top Products -->
        <div class="section">
            <h2>🏆 Top Productos</h2>
            <div class="chart-container">
                <img src="data:image/png;base64,{{ charts.top_products }}" alt="Top Productos">
            </div>
            <table>
                <thead>
                    <tr><th>#</th><th>Producto</th><th>SKU</th><th class="num">Facturación</th><th class="num">Cantidad</th><th class="num">Margen</th></tr>
                </thead>
                <tbody>
                {% for p in formatted_top_products %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td>{{ p.product_name }}</td>
                        <td><code>{{ p.sku }}</code></td>
                        <td class="num">{{ p.total_revenue }}</td>
                        <td class="num">{{ p.total_quantity }}</td>
                        <td class="num">{{ p.profit_margin_pct }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- Top Customers -->
        <div class="section">
            <h2>👥 Top Clientes</h2>
            <div class="chart-container">
                <img src="data:image/png;base64,{{ charts.top_customers }}" alt="Top Clientes">
            </div>
            <table>
                <thead>
                    <tr><th>#</th><th>Cliente</th><th class="num">Facturación</th><th class="num">Ganancia</th><th class="num">Margen</th><th class="num">Pedidos</th><th class="num">AOV</th></tr>
                </thead>
                <tbody>
                {% for c in formatted_top_customers %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td>{{ c.customer_name }}</td>
                        <td class="num">{{ c.total_revenue }}</td>
                        <td class="num">{{ c.profit or "0" }}</td>
                        <td class="num">{{ c.profit_margin_pct or "0" }}</td>
                        <td class="num">{{ c.total_orders }}</td>
                        <td class="num">{{ c.average_order_value }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- Categories -->
        <div class="two-col">
            <div class="section">
                <h2>🥧 Distribución por Categoría</h2>
                <div class="chart-container">
                    <img src="data:image/png;base64,{{ charts.category_pie }}" alt="Categorías Pie">
                </div>
            </div>
            <div class="section">
                <h2>📊 Categorías — Facturación y Margen</h2>
                <div class="chart-container">
                    <img src="data:image/png;base64,{{ charts.category_bar }}" alt="Categorías Bar">
                </div>
            </div>
        </div>

        <!-- Budget vs Actual -->
        {% if budget_vs_actual.available %}
        <div class="section" style="border-left: 4px solid #2563eb;">
            <h2>🎯 Presupuesto vs Real (Vendedores)</h2>
            <p style="color:var(--text-muted); font-size:0.85rem;">
                Periodo {{ budget_vs_actual.periodo }} — metas de <code>presupuesto_vendedores</code> vs ventas netas en <code>banco_datos</code>.
            </p>
            <div class="kpi-grid" style="display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:0.75rem; margin-bottom:1rem;">
                <div class="kpi-card" style="background:#eff6ff; border-radius:0.5rem; padding:0.75rem;">
                    <div style="font-size:0.8rem; color:var(--text-muted);">Meta total</div>
                    <div style="font-size:1.1rem; font-weight:700;">{{ budget_vs_actual.summary.presupuesto_total }}</div>
                </div>
                <div class="kpi-card" style="background:#f0fdf4; border-radius:0.5rem; padding:0.75rem;">
                    <div style="font-size:0.8rem; color:var(--text-muted);">Ventas reales</div>
                    <div style="font-size:1.1rem; font-weight:700;">{{ budget_vs_actual.summary.ventas_reales_total }}</div>
                </div>
                <div class="kpi-card" style="background:#fff7ed; border-radius:0.5rem; padding:0.75rem;">
                    <div style="font-size:0.8rem; color:var(--text-muted);">Cumplimiento</div>
                    <div style="font-size:1.1rem; font-weight:700;">{{ budget_vs_actual.summary.cumplimiento_pct }}</div>
                </div>
                <div class="kpi-card" style="background:#fef2f2; border-radius:0.5rem; padding:0.75rem;">
                    <div style="font-size:0.8rem; color:var(--text-muted);">Brecha</div>
                    <div style="font-size:1.1rem; font-weight:700;">{{ budget_vs_actual.summary.brecha_total }}</div>
                </div>
            </div>
            <table>
                <thead>
                    <tr><th>#</th><th>Vendedor</th><th class="num">Meta</th><th class="num">Real</th><th class="num">Cumplimiento</th><th class="num">Brecha</th></tr>
                </thead>
                <tbody>
                {% for s in budget_vs_actual.sellers[:15] %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td>{{ s.vendedor_nombre }} <span style="color:var(--text-muted); font-size:0.8rem;">({{ s.vendedor_codigo }})</span></td>
                        <td class="num">{{ s.presupuesto }}</td>
                        <td class="num">{{ s.ventas_reales }}</td>
                        <td class="num">{{ s.cumplimiento_pct }}</td>
                        <td class="num">{{ s.brecha }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
            {% if budget_vs_actual.underperformers %}
            <h3>Vendedores bajo 90% de cumplimiento</h3>
            <ul style="margin:0; padding-left:1.2rem; color:var(--text-muted);">
                {% for s in budget_vs_actual.underperformers[:8] %}
                <li>{{ s.vendedor_nombre }} — {{ s.cumplimiento_pct }} (brecha {{ s.brecha }})</li>
                {% endfor %}
            </ul>
            {% endif %}
        </div>
        {% elif budget_vs_actual.note %}
        <div class="section">
            <h2>🎯 Presupuesto vs Real</h2>
            <p style="color:var(--text-muted);">{{ budget_vs_actual.note }}</p>
        </div>
        {% endif %}

        <!-- Contabilidad ERP (Q17) -->
        {% if contabilidad.available %}
        <div class="section" style="border-left: 4px solid #7c3aed;">
            <h2>📒 Contabilidad ERP — Balance y PyG (PUC)</h2>
            <p style="color:var(--text-muted); font-size:0.85rem;">
                Ventas del periodo {{ contabilidad.period.start }} a {{ contabilidad.period.end }}.
                Fuente consolidada: <code>ConMovimiento</code> + <code>ConMovimientoDetalle</code> + PUC.
                Los saldos de balance (clases 1–3) son acumulados al cierre; PyG (clases 4–6) refleja solo el periodo.
            </p>

            <h3>Estado de situación financiera (clases 1–3)</h3>
            <p style="color:var(--text-muted); font-size:0.82rem; margin-top:0;">
                {{ contabilidad.metric_help.balance_intro }}
                Corte: <strong>{{ contabilidad.balance_summary.corte_fecha }}</strong>.
                {{ contabilidad.balance_summary.ecuacion_label }}:
                {% if contabilidad.balance_summary.ecuacion_ok %}<span style="color:var(--accent);">OK</span>{% else %}<span style="color:var(--warning);">Dif. {{ contabilidad.balance_summary.ecuacion_diferencia }}</span>{% endif %}.
                <span style="display:block; margin-top:0.25rem;">{{ contabilidad.balance_summary.ecuacion_help }}</span>
            </p>
            <div class="kpi-grid" style="display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:0.75rem; margin:0.75rem 0 1rem;">
                <div class="kpi-card" style="background:#eff6ff; border-radius:0.5rem; padding:0.75rem;">
                    <div style="font-size:0.75rem; color:var(--text-muted);">Activo (clase 1)</div>
                    <div style="font-size:1.05rem; font-weight:700;">{{ contabilidad.balance_summary.activo_total }}</div>
                </div>
                <div class="kpi-card" style="background:#fef2f2; border-radius:0.5rem; padding:0.75rem;">
                    <div style="font-size:0.75rem; color:var(--text-muted);">Pasivo (clase 2)</div>
                    <div style="font-size:1.05rem; font-weight:700;">{{ contabilidad.balance_summary.pasivo_total }}</div>
                </div>
                <div class="kpi-card" style="background:#f0fdf4; border-radius:0.5rem; padding:0.75rem;">
                    <div style="font-size:0.75rem; color:var(--text-muted);">Patrimonio (clase 3)</div>
                    <div style="font-size:1.05rem; font-weight:700;">{{ contabilidad.balance_summary.patrimonio_total }}</div>
                </div>
                <div class="kpi-card" style="background:#f5f3ff; border-radius:0.5rem; padding:0.75rem;">
                    <div style="font-size:0.75rem; color:var(--text-muted);">Pasivo + Patrimonio</div>
                    <div style="font-size:1.05rem; font-weight:700;">{{ contabilidad.balance_summary.pasivo_mas_patrimonio }}</div>
                </div>
                <div class="kpi-card" style="background:#fff7ed; border-radius:0.5rem; padding:0.75rem;">
                    <div style="font-size:0.75rem; color:var(--text-muted);">Resultado PyG acum. (cl. 4–6)</div>
                    <div style="font-size:1.05rem; font-weight:700;">{{ contabilidad.balance_summary.resultado_pyg_acumulado }}</div>
                    <div style="font-size:0.7rem; color:var(--text-muted); margin-top:0.2rem;">{{ contabilidad.balance_summary.resultado_pyg_help }}</div>
                </div>
            </div>
            {% if contabilidad.balance_clase %}
            <table>
                <thead>
                    <tr><th>Clase</th><th>Tipo</th><th class="num">Débitos acum.</th><th class="num">Créditos acum.</th><th class="num">Saldo acumulado</th></tr>
                </thead>
                <tbody>
                {% for row in contabilidad.balance_clase %}
                    <tr>
                        <td>{{ row.clase_puc }}</td>
                        <td>{{ row.tipo_cuenta }}</td>
                        <td class="num">{{ row.total_debitos }}</td>
                        <td class="num">{{ row.total_creditos }}</td>
                        <td class="num">{{ row.saldo_acumulado }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
            {% endif %}

            <h3 style="margin-top:1.25rem;">Estado de resultados — PyG (clases 4–6)</h3>
            <p style="color:var(--text-muted); font-size:0.82rem; margin-top:0;">
                {{ contabilidad.metric_help.pyg_intro }}
                {{ contabilidad.summary.cuadre_label }}:
                {% if contabilidad.summary.cuadre_ok %}OK{% else %}Revisar{% endif %}
                ({{ contabilidad.summary.movimientos }} movimientos, {{ contabilidad.summary.lineas }} líneas).
            </p>
            <div class="kpi-grid" style="display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:0.75rem; margin:0.75rem 0 1rem;">
                <div class="kpi-card" style="background:#eff6ff; border-radius:0.5rem; padding:0.75rem;">
                    <div style="font-size:0.75rem; color:var(--text-muted);">{{ contabilidad.pyg_summary.ingresos_label }}</div>
                    <div style="font-size:1.05rem; font-weight:700;">{{ contabilidad.pyg_summary.ingresos_creditos }}</div>
                </div>
                <div class="kpi-card" style="background:#fff7ed; border-radius:0.5rem; padding:0.75rem;">
                    <div style="font-size:0.75rem; color:var(--text-muted);">{{ contabilidad.pyg_summary.costos_label }}</div>
                    <div style="font-size:1.05rem; font-weight:700;">{{ contabilidad.pyg_summary.costos_debitos }}</div>
                </div>
                <div class="kpi-card" style="background:#fef2f2; border-radius:0.5rem; padding:0.75rem;">
                    <div style="font-size:0.75rem; color:var(--text-muted);">{{ contabilidad.pyg_summary.gastos_label }}</div>
                    <div style="font-size:1.05rem; font-weight:700;">{{ contabilidad.pyg_summary.gastos_debitos }}</div>
                </div>
                <div class="kpi-card" style="background:#f5f3ff; border-radius:0.5rem; padding:0.75rem;">
                    <div style="font-size:0.75rem; color:var(--text-muted);">{{ contabilidad.pyg_summary.margen_label }}</div>
                    <div style="font-size:1.05rem; font-weight:700;">{{ contabilidad.pyg_summary.margen_bruto_contable }} ({{ contabilidad.pyg_summary.margen_contable_pct }})</div>
                    <div style="font-size:0.72rem; color:var(--text-muted); margin-top:0.25rem;">{{ contabilidad.pyg_summary.margen_help }}</div>
                </div>
            </div>
            <table>
                <thead>
                    <tr><th>Clase PUC</th><th>Tipo</th><th class="num">Créditos periodo</th><th class="num">Débitos periodo</th><th class="num">Saldo neto</th></tr>
                </thead>
                <tbody>
                {% for row in contabilidad.pyg_clase %}
                    <tr>
                        <td>{{ row.clase_puc }}</td>
                        <td>{{ row.tipo_cuenta }}</td>
                        <td class="num">{{ row.total_creditos }}</td>
                        <td class="num">{{ row.total_debitos }}</td>
                        <td class="num">{{ row.saldo_neto }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>

            <h3 style="margin-top:1.25rem;">{{ contabilidad.conciliacion_ingresos.conciliacion_label }}</h3>
            <p style="color:var(--text-muted); font-size:0.82rem; margin-top:0;">
                {{ contabilidad.conciliacion_ingresos.conciliacion_help }}
            </p>
            <table style="margin-top:0.5rem; max-width:720px;">
                <tbody>
                    <tr>
                        <td>{{ contabilidad.conciliacion_ingresos.ingresos_41_label }}</td>
                        <td class="num"><strong>{{ contabilidad.conciliacion_ingresos.ingresos_contables_41 }}</strong></td>
                    </tr>
                    <tr>
                        <td>{{ contabilidad.conciliacion_ingresos.ventas_bi_label }}</td>
                        <td class="num"><strong>{{ contabilidad.conciliacion_ingresos.ventas_bi_con_iva }}</strong></td>
                    </tr>
                    <tr>
                        <td>{{ contabilidad.conciliacion_ingresos.diferencia_label }}</td>
                        <td class="num">{{ contabilidad.conciliacion_ingresos.diferencia_con_iva }}</td>
                    </tr>
                    <tr>
                        <td>% conciliación</td>
                        <td class="num"><strong>{{ contabilidad.conciliacion_ingresos.conciliacion_pct }}</strong></td>
                    </tr>
                </tbody>
            </table>
            {% if contabilidad.gastos_centro %}
            <h3>Gastos por centro de costo (top)</h3>
            <table>
                <thead>
                    <tr><th>Centro</th><th class="num">Gastos</th><th class="num">Costos</th><th class="num">Total</th></tr>
                </thead>
                <tbody>
                {% for row in contabilidad.gastos_centro[:10] %}
                    <tr>
                        <td>{{ row.centro_nombre }}</td>
                        <td class="num">{{ row.gastos_neto }}</td>
                        <td class="num">{{ row.costos_neto }}</td>
                        <td class="num">{{ row.total_neto }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
            {% endif %}
        </div>
        {% elif contabilidad.note %}
        <div class="section">
            <h2>📒 Contabilidad ERP</h2>
            <p style="color:var(--text-muted);">{{ contabilidad.note }}</p>
        </div>
        {% endif %}

        <!-- Margin Comparison -->
        <div class="section">
            <h2>🔍 Facturación vs Margen por Producto</h2>
            <div class="chart-container">
                <img src="data:image/png;base64,{{ charts.margin_comparison }}" alt="Margen Comparación">
            </div>
        </div>

        <!-- Vendor Sales -->
        <div class="section">
            <h2>🏭 Ventas por Proveedor</h2>
            <table>
                <thead>
                    <tr><th>#</th><th>Proveedor</th><th class="num">Facturación</th><th class="num">% Participación</th><th class="num">Margen</th><th class="num">Pedidos</th></tr>
                </thead>
                <tbody>
                {% for v in vendor_sales %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td>{{ v.vendor_name }}</td>
                        <td class="num">{{ v.total_revenue }}</td>
                        <td class="num">{{ v.revenue_pct }}</td>
                        <td class="num">{{ v.profit_margin_pct }}</td>
                        <td class="num">{{ v.transactions }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
            {% if vendor_sales_chart %}
            <div class="chart-container">
                <img src="data:image/png;base64,{{ vendor_sales_chart }}" alt="Ventas por Proveedor">
            </div>
            {% endif %}
        </div>

        <!-- Marca / Brand Sales (focus on MARCAS from SmartBusiness classification + masters) -->
        <div class="section">
            <h2>🏷️ Ventas por Marca Real</h2>
            <p style="color:var(--text-muted); font-size:0.85rem;">Marca autoritativa desde <code>productos_adicional.producto_marca</code>, con respaldo en <code>banco_datos.marca</code> cuando el maestro no tiene valor.</p>
            <table>
                <thead>
                    <tr><th>#</th><th>Marca/Línea</th><th class="num">Facturación</th><th class="num">% Part.</th><th class="num">Margen</th><th class="num">Pedidos</th></tr>
                </thead>
                <tbody>
                {% for m in marca_sales %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td>{{ m.marca_name }}</td>
                        <td class="num">{{ m.total_revenue }}</td>
                        <td class="num">{{ m.revenue_pct }}</td>
                        <td class="num">{{ m.profit_margin_pct }}</td>
                        <td class="num">{{ m.transactions }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- Customer-Vendor Mix -->
        {% if customer_vendor_mix %}
        <div class="section">
            <h2>🔗 Relación Clientes-Proveedores</h2>
            <p style="color:var(--text-muted); font-size:0.9rem; margin-bottom:0.5rem;">Clientes top y sus principales proveedores (mezcla de demanda por origen).</p>
            {% for m in customer_vendor_mix[:8] %}
            <div style="background:#f8fafc; border:1px solid var(--border); border-radius:0.5rem; padding:0.6rem; margin-bottom:0.4rem; font-size:0.9rem;">
                <strong>🏪 {{ m.customer_name[:32] }}</strong> — {{ m.vendor_count }} proveedores, {{ m.total_revenue }}
                <br>
                <span style="color:var(--text-muted);">Principales:</span>
                {% for tv in m.top_vendors %}
                    <span class="badge badge-info">{{ tv.vendor_name[:14] }} {{ tv.pct }}</span>
                {% endfor %}
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <!-- Suggested Orders -->
        {% if order_suggestions %}
        <div class="section">
            <h2>📋 Pedidos Sugeridos por Cliente</h2>
            {% for s in order_suggestions %}
            <div style="background:#f8fafc; border:1px solid var(--border); border-radius:0.5rem; padding:1rem; margin-bottom:0.75rem;">
                <h3 style="margin:0 0 0.5rem; color:var(--primary);">🏪 {{ s.customer_name }}</h3>
                <p style="margin:0 0 0.5rem; color:var(--text-muted);">Total sugerido: <strong>{{ s.total_suggested }}</strong> unidades</p>
                <table>
                    <thead>
                        <tr><th>Producto</th><th>Marca</th><th>Proveedor</th><th class="num">Stock</th><th class="num">Prom./Mes</th><th class="num">Sugerido</th></tr>
                    </thead>
                    <tbody>
                    {% for i in s.suggested_items %}
                        <tr>
                            <td><code>{{ i.sku }}</code> {{ i.product_name[:40] }}</td>
                            <td>{{ i.marca[:16] if i.marca else "—" }}</td>
                            <td>{{ i.primary_vendor[:18] if i.primary_vendor else "—" }}</td>
                            <td class="num" style="color:{% if i.current_stock != 'N/A' and i.current_stock|int <= 5 %}var(--danger){% endif %}">{{ i.current_stock }}</td>
                            <td class="num">{{ i.avg_monthly }}</td>
                            <td class="num"><strong>{{ i.suggested_order }}</strong></td>
                        </tr>
                    {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <!-- Procurement / Shopping Plan (new aggregated view) -->
        {% if procurement_plan %}
        <div class="section" style="border-left: 4px solid #16a34a;">
            <h2>🛒 Plan de Compras Sugerido (por Proveedor)</h2>
            <p style="color:var(--text-muted); font-size:0.9rem;">Consolidado de pedidos sugeridos por cliente, agrupados por proveedor para facilitar negociación y abastecimiento. Mezcla de vendors + patrones de clientes YTD.</p>
            {% for p in procurement_plan[:8] %}
            <div style="background:#ecfdf5; border:1px solid #a7f3d0; border-radius:0.5rem; padding:0.6rem; margin-bottom:0.5rem;">
                <strong>🏭 {{ p.vendor_name }}</strong> — {{ p.total_suggested_units }} unidades totales, {{ p.affected_customers }} clientes, {{ p.key_products_count }} productos clave
                {% if p.key_products_count|int > 0 and p.key_products %}
                <details style="margin-top:0.3rem;">
                    <summary style="cursor:pointer; font-size:0.85rem; color:var(--secondary);">Ver productos sugeridos</summary>
                    <ul style="margin:0.3rem 0 0; padding-left:1.2rem; font-size:0.85rem;">
                    {% for kp in p.key_products %}
                        <li><code>{{ kp.sku or '' }}</code> {{ kp.product_name[:28] }}: <strong>{{ kp.suggested_order }}</strong> uds ({{ kp.affected_customers }} clientes)</li>
                    {% endfor %}
                    </ul>
                </details>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <!-- ABC Analysis -->
        {% if abc_analysis %}
        <div class="section">
            <h2>📊 Análisis ABC (80/15/5)</h2>
            <p style="font-size:0.9rem; color:var(--text-muted);">Clasificación por contribución a facturación. A: ~80%, B: ~15%, C: resto (larga cola).</p>
            {% for dim in ["products", "customers", "vendors"] %}
            {% set d = abc_analysis[dim] %}
            {% if d %}
            <h3 style="font-size:1rem; margin:0.5rem 0 0.25rem;">{{ dim|capitalize }}</h3>
            <table style="width:100%; font-size:0.9rem;">
                <tr><td>A</td><td>{{ d.a.count }} items</td><td>{{ d.a.revenue_pct }}% rev</td></tr>
                <tr><td>B</td><td>{{ d.b.count }} items</td><td>{{ d.b.revenue_pct }}% rev</td></tr>
                <tr><td>C</td><td>{{ d.c.count }} items</td><td>{{ d.c.revenue_pct }}% rev</td></tr>
            </table>
            {% endif %}
            {% endfor %}
        </div>
        {% endif %}

        <!-- Stock Replenishment / Shopping from J3 (missing stock) -->
        {% if stock_replenishment_suggestions %}
        <div class="section" style="border-left:4px solid #f59e0b;">
            <h2>🛒 Sugerencias de Compra por Stock Bajo (J3System)</h2>
            <p style="font-size:0.85rem;">Items con stock crítico + alto movimiento. Usa datos de existencias J3 + ventas.</p>
            <ul style="font-size:0.9rem;">
            {% for s in stock_replenishment_suggestions[:6] %}
                <li><strong>{{ s.product_name[:35] }}</strong> ({{ s.marca or s.proveedor }}) — Stock: {{ s.current_stock }} | Vendidos: {{ s.recent_sold }}</li>
            {% endfor %}
            </ul>
        </div>
        {% endif %}

        <!-- Cross-sell Recommendations -->
        {% if cross_sell %}
        <div class="section">
            <h2>🔗 Recomendaciones de Compra Cruzada</h2>
            {% for r in cross_sell %}
            <div style="background:#faf5ff; border:1px solid #e9d5ff; border-radius:0.5rem; padding:0.75rem; margin-bottom:0.5rem;">
                <strong>📦 {{ r.product_name }}</strong> ({{ r.buyers }} compradores)
                <br>
                <span style="color:var(--text-muted); font-size:0.9rem;">También compran: </span>
                {% for cr in r.recommended_with %}
                    <span class="badge badge-info">{{ cr.product_name[:20] }}{% if not loop.last %}, {% endif %}</span>
                {% endfor %}
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <!-- Balanced margin × sales promote -->
        {% if high_margin_promote %}
        <div class="section">
            <h2>⭐ Productos Recomendados (Margen × Ventas)</h2>
            <p style="color:var(--text-muted); margin-bottom:1rem; font-size:0.9rem;">
                Productos con buen margen y ventas significativas — no solo margen alto en bajo volumen.
            </p>
            <table>
                <thead>
                    <tr><th>Producto</th><th class="num">Margen</th><th class="num">Vendidos</th><th class="num">Facturación</th><th class="num">Ganancia</th></tr>
                </thead>
                <tbody>
                {% for p in high_margin_promote %}
                    <tr>
                        <td>{{ p.product_name[:45] }}</td>
                        <td class="num" style="color:var(--accent);">{{ p.margin_pct }}</td>
                        <td class="num">{{ p.quantity_sold }}</td>
                        <td class="num">{{ p.revenue }}</td>
                        <td class="num" style="color:var(--accent);">{{ p.gross_profit }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}

        <!-- Recommendations -->
        {% if recommendations %}
        <div class="section">
            <h2>💡 Recomendaciones</h2>
            {% for r in recommendations %}
            <div class="recommendation">
                <span class="badge {% if r.priority == 'Alta' %}badge-danger{% elif r.priority == 'Media' %}badge-warning{% else %}badge-info{% endif %}">{{ r.priority }}</span>
                <div>
                    <strong>{{ r.area }}</strong> — {{ r.action }}
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <!-- Risks -->
        {% if risks %}
        <div class="section">
            <h2>⚠️ Riesgos Identificados</h2>
            {% for r in risks %}
            <div class="risk-card risk-{% if r.level == 'Alto' %}high{% elif r.level == 'Medio' %}medium{% else %}low{% endif %}">
                <span class="badge {% if r.level == 'Alto' %}badge-danger{% elif r.level == 'Medio' %}badge-warning{% else %}badge-success{% endif %}">{{ r.level }}</span>
                <strong>{{ r.type }}</strong> — {{ r.description }}
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <!-- Opportunities -->
        {% if opportunities %}
        <div class="section">
            <h2>🚀 Oportunidades</h2>
            {% for o in opportunities %}
            <div class="opportunity-card">
                <span class="badge badge-info">{{ o.impact }}</span>
                <strong>{{ o.type }}</strong> — {{ o.description }}
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <!-- Inventory -->
        {% if inventory_low_stock %}
        <div class="section">
            <h2>📦 Alertas de Inventario</h2>
            <table>
                <thead>
                    <tr><th>SKU</th><th>Producto</th><th class="num">Vendido</th><th class="num">Stock Actual</th></tr>
                </thead>
                <tbody>
                {% for item in inventory_low_stock %}
                    <tr>
                        <td><code>{{ item.sku }}</code></td>
                        <td>{{ item.product_name }}</td>
                        <td class="num">{{ item.quantity_sold }}</td>
                        <td class="num" style="color:{% if item.current_stock is not none and item.current_stock <= 5 %}var(--danger){% else %}var(--warning){% endif %}">{{ item.current_stock if item.current_stock is not none else 'N/A' }}</td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}

        <div class="footer">
            Informe generado automáticamente por Business Data Analyzer &nbsp;|&nbsp; {{ generated_at }}
        </div>
    </div>
</body>
</html>
"""


class HTMLReportGenerator:
    """
    Generate a self-contained HTML report with embedded base64 charts.

    Attributes:
        data: Report dictionary
        chart_paths: Dict of chart name -> file path
        ai_insights: Insights dictionary from ReportAIInsights
        template: Jinja2 HTML template
    """

    def __init__(
        self,
        data: Dict[str, Any],
        chart_paths: Dict[str, str],
        ai_insights: Optional[Dict[str, Any]] = None,
    ):
        self.data = data
        self.chart_paths = chart_paths
        self.ai_insights = ai_insights or {}
        self.template = Template(HTML_TEMPLATE)

    def generate(self, output_path: str) -> str:
        """
        Generate the HTML report and save to file.

        Args:
            output_path: Path to save the HTML file

        Returns:
            Absolute path to the generated HTML file
        """
        charts_b64 = self._encode_charts()
        context = self._build_context(charts_b64)
        html = self.template.render(**context)

        out = Path(output_path)
        out.write_text(html, encoding="utf-8")
        return str(out.absolute())

    def _encode_charts(self) -> Dict[str, str]:
        """Read chart PNGs and encode as base64 data URIs."""
        encoded: Dict[str, str] = {}
        for name, path in self.chart_paths.items():
            if path and Path(path).exists():
                data = Path(path).read_bytes()
                encoded[name] = base64.b64encode(data).decode("ascii")
            else:
                encoded[name] = ""
        return encoded

    def _build_context(self, charts_b64: Dict[str, str]) -> Dict[str, Any]:
        """Build the Jinja2 template context."""
        meta = self.data.get("metadata", {})
        formatted = self.data.get("formatted", {})

        branch_name = meta.get("branch_name")
        report_scope = (
            f"Sede {branch_name}" if branch_name else "Depósito Trujillo (Consolidado)"
        )

        return {
            "year": meta.get("year", ""),
            "month_name": meta.get("month_name", ""),
            "report_scope": report_scope,
            "branch_name": branch_name,
            "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "summary": self.data.get("summary", {}),
            "formatted_summary": formatted.get("summary", {}),
            "charts": charts_b64,
            "formatted_top_products": formatted.get("top_products", []),
            "formatted_top_customers": formatted.get("top_customers", []),
            "ai_narrative": self.ai_insights.get("ai_analysis_text"),
            "executive_summary": self.ai_insights.get("executive_summary", []),
            "recommendations": self.ai_insights.get("recommendations", []),
            "risks": self.ai_insights.get("risks", []),
            "opportunities": self.ai_insights.get("opportunities", []),
            "inventory_low_stock": self.data.get("inventory_insights", {}).get(
                "low_stock_alert", []
            ),
            "vendor_sales": formatted.get("vendor_sales", []),
            "vendor_sales_chart": charts_b64.get("vendor_sales"),
            "marca_sales": formatted.get("marca_sales", []),
            "customer_vendor_mix": formatted.get("customer_vendor_mix", []),
            "order_suggestions": formatted.get("customer_order_suggestions", []),
            "cross_sell": _shopping_section(
                formatted.get("shopping_recommendations"), "cross_sell"
            ),
            "high_margin_promote": _shopping_section(
                formatted.get("shopping_recommendations"), "high_margin_promote"
            ),
            "procurement_plan": formatted.get("procurement_plan", []),
            "abc_analysis": formatted.get("abc_analysis", {}),
            "stock_replenishment_suggestions": formatted.get(
                "stock_replenishment_suggestions", []
            ),
            "budget_vs_actual": formatted.get(
                "budget_vs_actual",
                {"available": False, "note": None, "summary": {}, "sellers": []},
            ),
            "contabilidad": formatted.get(
                "contabilidad",
                {
                    "available": False,
                    "note": None,
                    "period": {},
                    "metric_help": {},
                    "summary": {},
                    "balance_summary": {},
                    "balance_clase": [],
                    "pyg_summary": {},
                    "conciliacion_ingresos": {},
                    "pyg_clase": [],
                    "gastos_centro": [],
                    "top_gastos": [],
                },
            ),
        }
