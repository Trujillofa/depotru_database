# mypy: ignore-errors
"""
PDF Report Generator for Manager Sales Reports
================================================

Generates a professional PDF report with charts, tables,
and AI insights using ReportLab.

Usage:
    from src.business_analyzer.reports.pdf_generator import PDFReportGenerator

    gen = PDFReportGenerator(report_data, chart_paths, ai_insights)
    pdf_path = gen.generate("report_mayo_2024.pdf")
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        Image,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    # Define minimal stubs so the module loads without reportlab
    colors = None  # type: ignore
    TA_CENTER = TA_LEFT = TA_RIGHT = 0  # type: ignore
    A4 = (595, 842)  # type: ignore
    getSampleStyleSheet = ParagraphStyle = None  # type: ignore
    cm = mm = 1  # type: ignore
    Image = PageBreak = Paragraph = SimpleDocTemplate = Spacer = Table = TableStyle = None  # type: ignore


def _format_currency_label(value: float) -> str:
    """Compact currency for PDF labels."""
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}MM".replace(".", ",")
    if value >= 1_000_000:
        return f"${value / 1_000_000:.0f}M".replace(".", ",")
    if value >= 1_000:
        return f"${value / 1_000:.0f}K".replace(".", ",")
    return f"${value:,.0f}".replace(",", ".")


class PDFReportGenerator:
    """
    Generate a professional PDF report using ReportLab.

    Attributes:
        data: Report dictionary from ManagerSalesReport
        chart_paths: Dict of chart name -> file path
        ai_insights: Insights dictionary
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
        self.styles = self._create_styles()

    def _create_styles(self) -> Dict[str, ParagraphStyle]:
        """Create custom paragraph styles."""
        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="KPIValue",
                fontSize=20,
                textColor=colors.HexColor("#1e3a5f"),
                alignment=TA_CENTER,
                spaceAfter=4,
                fontName="Helvetica-Bold",
            )
        )
        styles.add(
            ParagraphStyle(
                name="KPILabel",
                fontSize=9,
                textColor=colors.HexColor("#6b7280"),
                alignment=TA_CENTER,
                spaceAfter=2,
                fontName="Helvetica",
            )
        )
        styles.add(
            ParagraphStyle(
                name="SectionTitle",
                fontSize=14,
                textColor=colors.HexColor("#1e3a5f"),
                spaceAfter=12,
                spaceBefore=16,
                fontName="Helvetica-Bold",
                borderWidth=0,
                borderColor=colors.HexColor("#2563eb"),
                borderPadding=5,
                leftIndent=0,
            )
        )
        styles.add(
            ParagraphStyle(
                name="InsightBullet",
                fontSize=10,
                textColor=colors.HexColor("#374151"),
                leftIndent=12,
                spaceAfter=6,
                fontName="Helvetica",
            )
        )
        styles.add(
            ParagraphStyle(
                name="AIAnalysis",
                fontSize=10,
                textColor=colors.HexColor("#4b5563"),
                leftIndent=8,
                rightIndent=8,
                spaceAfter=6,
                leading=14,
                fontName="Helvetica",
            )
        )
        styles.add(
            ParagraphStyle(
                name="RiskHigh",
                fontSize=10,
                textColor=colors.HexColor("#991b1b"),
                backColor=colors.HexColor("#fef2f2"),
                leftIndent=8,
                rightIndent=8,
                spaceAfter=6,
                borderPadding=6,
                fontName="Helvetica",
            )
        )
        styles.add(
            ParagraphStyle(
                name="RiskMedium",
                fontSize=10,
                textColor=colors.HexColor("#92400e"),
                backColor=colors.HexColor("#fffbeb"),
                leftIndent=8,
                rightIndent=8,
                spaceAfter=6,
                borderPadding=6,
                fontName="Helvetica",
            )
        )
        styles.add(
            ParagraphStyle(
                name="Opportunity",
                fontSize=10,
                textColor=colors.HexColor("#1e40af"),
                backColor=colors.HexColor("#eff6ff"),
                leftIndent=8,
                rightIndent=8,
                spaceAfter=6,
                borderPadding=6,
                fontName="Helvetica",
            )
        )
        return styles

    def generate(self, output_path: str) -> str:
        """Generate the PDF report."""
        if not REPORTLAB_AVAILABLE:
            raise ImportError(
                "ReportLab no está instalado. " "Instálalo con: pip install reportlab"
            )
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=1.5 * cm,
            bottomMargin=1.5 * cm,
        )

        story: List[Any] = []
        self._add_header(story)
        self._add_kpi_cards(story)

        if self.ai_insights.get("ai_analysis_text"):
            self._add_ai_analysis(story)

        if self.ai_insights.get("executive_summary"):
            self._add_executive_summary(story)

        self._add_chart_section(story, "Tendencia Diaria", "daily_trend")
        self._add_chart_section(story, "Top Productos por Facturación", "top_products")
        self._add_product_table(story)
        story.append(PageBreak())

        self._add_chart_section(story, "Top Clientes", "top_customers")
        self._add_chart_section(story, "Ventas por Proveedor", "vendor_sales")
        self._add_customer_table(story)
        self._add_chart_section(story, "Distribución por Categoría", "category_pie")
        self._add_chart_section(
            story, "Categorías — Facturación y Margen", "category_bar"
        )
        story.append(PageBreak())

        self._add_chart_section(story, "Facturación vs Margen", "margin_comparison")
        self._add_kpi_summary_chart(story)

        if self.ai_insights.get("recommendations"):
            self._add_recommendations(story)

        if self.ai_insights.get("risks"):
            self._add_risks(story)

        if self.ai_insights.get("opportunities"):
            self._add_opportunities(story)

        self._add_contabilidad_section(story)
        self._add_inventory_table(story)
        self._add_procurement_plan(story)
        self._add_customer_vendor_mix(story)
        self._add_footer(story)

        doc.build(story)
        return str(Path(output_path).absolute())

    def _add_header(self, story: List[Any]) -> None:
        """Add report header."""
        meta = self.data.get("metadata", {})
        month_name = meta.get("month_name", "")
        year = meta.get("year", "")

        branch_name = meta.get("branch_name")
        report_scope = (
            f"Sede {branch_name}" if branch_name else "Depósito Trujillo (Consolidado)"
        )

        title = Paragraph(
            f'<font size="22" color="#1e3a5f"><b>Informe de Ventas Mensual</b></font>',
            self.styles["Title"],
        )
        subtitle = Paragraph(
            f'<font size="11" color="#6b7280">{month_name} {year} — {report_scope} — '
            f'Generado: {datetime.now().strftime("%d/%m/%Y %H:%M")}</font>',
            self.styles["Normal"],
        )
        story.extend([title, Spacer(1, 4 * mm), subtitle, Spacer(1, 8 * mm)])

    def _add_kpi_cards(self, story: List[Any]) -> None:
        """Add KPI summary as a table."""
        formatted = self.data.get("formatted", {}).get("summary", {})
        summary = self.data.get("summary", {})

        kpi_data = [
            [
                Paragraph(
                    formatted.get("total_revenue_with_iva", "$0"),
                    self.styles["KPIValue"],
                ),
                Paragraph(
                    formatted.get("total_revenue_without_iva", "$0"),
                    self.styles["KPIValue"],
                ),
                Paragraph(formatted.get("gross_profit", "$0"), self.styles["KPIValue"]),
            ],
            [
                Paragraph("FACTURACIÓN (IVA)", self.styles["KPILabel"]),
                Paragraph("FACTURACIÓN (SIN IVA)", self.styles["KPILabel"]),
                Paragraph("GANANCIA BRUTA", self.styles["KPILabel"]),
            ],
            [
                Paragraph(
                    formatted.get("gross_margin_pct", "0%"), self.styles["KPIValue"]
                ),
                Paragraph(formatted.get("order_count", "0"), self.styles["KPIValue"]),
                Paragraph(
                    formatted.get("average_order_value", "$0"), self.styles["KPIValue"]
                ),
            ],
            [
                Paragraph("MARGEN BRUTO", self.styles["KPILabel"]),
                Paragraph("TRANSACCIONES", self.styles["KPILabel"]),
                Paragraph("TICKET PROMEDIO", self.styles["KPILabel"]),
            ],
        ]

        margin_color = colors.HexColor(
            "#16a34a"
            if summary.get("gross_margin_pct", 0) >= 20
            else "#f59e0b"
            if summary.get("gross_margin_pct", 0) >= 10
            else "#dc2626"
        )

        table = Table(kpi_data, colWidths=[5.5 * cm, 5.5 * cm, 5.5 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                    ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#f8fafc")),
                    ("TEXTCOLOR", (0, 2), (0, 2), margin_color),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LINEBELOW", (0, 1), (-1, 1), 0.5, colors.HexColor("#e5e7eb")),
                    ("LINEBELOW", (0, 3), (-1, 3), 0.5, colors.HexColor("#e5e7eb")),
                ]
            )
        )
        story.extend([table, Spacer(1, 6 * mm)])

    def _add_ai_analysis(self, story: List[Any]) -> None:
        """Add AI-generated narrative."""
        story.append(Paragraph("🤖 Análisis Inteligente", self.styles["SectionTitle"]))
        text = self.ai_insights.get("ai_analysis_text", "")
        # Split into paragraphs for better rendering
        for para in text.split("\n\n"):
            if para.strip():
                story.append(
                    Paragraph(
                        para.strip().replace("\n", "<br/>"), self.styles["AIAnalysis"]
                    )
                )
        story.append(Spacer(1, 4 * mm))

    def _add_executive_summary(self, story: List[Any]) -> None:
        """Add executive summary bullets."""
        story.append(Paragraph("📋 Resumen Ejecutivo", self.styles["SectionTitle"]))
        for item in self.ai_insights.get("executive_summary", []):
            story.append(Paragraph(f"• {item}", self.styles["InsightBullet"]))
        story.append(Spacer(1, 4 * mm))

    def _add_chart_section(self, story: List[Any], title: str, chart_key: str) -> None:
        """Add a chart image section."""
        path = self.chart_paths.get(chart_key)
        if not path or not Path(path).exists():
            return

        story.append(Paragraph(title, self.styles["SectionTitle"]))
        img = Image(path, width=16 * cm, height=8 * cm)
        img.hAlign = "CENTER"
        story.extend([img, Spacer(1, 4 * mm)])

    def _add_kpi_summary_chart(self, story: List[Any]) -> None:
        """Add the KPI summary visual chart."""
        path = self.chart_paths.get("kpi_summary")
        if not path or not Path(path).exists():
            return
        story.append(
            Paragraph("Resumen de Indicadores Clave", self.styles["SectionTitle"])
        )
        img = Image(path, width=16 * cm, height=9 * cm)
        img.hAlign = "CENTER"
        story.extend([img, Spacer(1, 4 * mm)])

    def _add_product_table(self, story: List[Any]) -> None:
        """Add top products table."""
        products = self.data.get("top_products", [])[:10]
        if not products:
            return

        story.append(Paragraph("Top 10 Productos", self.styles["SectionTitle"]))
        data = [["#", "Producto", "SKU", "Facturación", "Cantidad", "Margen"]]
        for i, p in enumerate(products, 1):
            data.append(
                [
                    str(i),
                    p["product_name"][:35],
                    p["sku"],
                    _format_currency_label(p["total_revenue"]),
                    str(p["total_quantity"]),
                    f"{p['profit_margin_pct']:.1f}%",
                ]
            )

        table = Table(
            data, colWidths=[1 * cm, 6.5 * cm, 2.5 * cm, 2.5 * cm, 2 * cm, 2 * cm]
        )
        table.setStyle(self._table_style())
        story.extend([table, Spacer(1, 6 * mm)])

    def _add_customer_table(self, story: List[Any]) -> None:
        """Add top customers table."""
        customers = self.data.get("top_customers", [])[:10]
        if not customers:
            return

        story.append(Paragraph("Top 10 Clientes", self.styles["SectionTitle"]))
        data = [["#", "Cliente", "Facturación", "Pedidos", "AOV"]]
        for i, c in enumerate(customers, 1):
            data.append(
                [
                    str(i),
                    c["customer_name"][:35],
                    _format_currency_label(c["total_revenue"]),
                    str(c["total_orders"]),
                    _format_currency_label(c["average_order_value"]),
                ]
            )

        table = Table(data, colWidths=[1 * cm, 7 * cm, 3 * cm, 2.5 * cm, 3 * cm])
        table.setStyle(self._table_style())
        story.extend([table, Spacer(1, 6 * mm)])

    def _add_contabilidad_section(self, story: List[Any]) -> None:
        """Add ERP accounting PyG summary when available."""
        cont = self.data.get("formatted", {}).get("contabilidad", {})
        if not cont.get("available"):
            return

        pyg = cont.get("pyg_summary", {})
        conc = cont.get("conciliacion_ingresos", {})
        story.append(
            Paragraph("📒 Contabilidad ERP — PyG PUC", self.styles["SectionTitle"])
        )
        data = [
            ["Métrica", "Valor"],
            ["Ingresos (clase 4)", pyg.get("ingresos_creditos", "$0")],
            ["Margen bruto contable", pyg.get("margen_bruto_contable", "$0")],
            ["Margen contable %", pyg.get("margen_contable_pct", "0%")],
            ["Conciliación ingresos", conc.get("conciliacion_pct", "0%")],
            ["Ingresos contables 41", conc.get("ingresos_contables_41", "$0")],
            ["Ventas BI con IVA", conc.get("ventas_bi_con_iva", "$0")],
        ]
        table = Table(data, colWidths=[7 * cm, 9 * cm])
        table.setStyle(self._table_style())
        story.extend([table, Spacer(1, 6 * mm)])

    def _add_inventory_table(self, story: List[Any]) -> None:
        """Add low stock inventory table."""
        low_stock = self.data.get("inventory_insights", {}).get("low_stock_alert", [])
        if not low_stock:
            return

        story.append(
            Paragraph(
                "⚠️ Alertas de Inventario (Stock Bajo)", self.styles["SectionTitle"]
            )
        )
        data = [["SKU", "Producto", "Vendido", "Stock Actual"]]
        for item in low_stock[:15]:
            stock = (
                f"{item['current_stock']:.0f}"
                if item["current_stock"] is not None
                else "N/A"
            )
            stock_color = (
                "#dc2626"
                if item["current_stock"] is not None and item["current_stock"] <= 5
                else "#f59e0b"
            )
            data.append(
                [
                    item["sku"],
                    item["product_name"][:35],
                    str(item["quantity_sold"]),
                    Paragraph(
                        f'<font color="{stock_color}">{stock}</font>',
                        self.styles["Normal"],
                    ),
                ]
            )

        table = Table(data, colWidths=[3 * cm, 7.5 * cm, 2.5 * cm, 3 * cm])
        table.setStyle(self._table_style())
        story.extend([table, Spacer(1, 6 * mm)])

    def _add_procurement_plan(self, story: List[Any]) -> None:
        """Add the consolidated vendor procurement / shopping plan."""
        plan = self.data.get("procurement_plan", [])
        if not plan:
            return
        story.append(
            Paragraph(
                "🛒 Plan de Compras Sugerido (por Proveedor)",
                self.styles["SectionTitle"],
            )
        )
        story.append(
            Paragraph(
                "Agrupación de pedidos sugeridos por cliente (basado en YTD completo del año) para guiar compras a proveedores.",
                self.styles["Normal"],
            )
        )
        story.append(Spacer(1, 3 * mm))
        data = [["Proveedor", "Unidades Sug.", "Clientes", "Productos Clave"]]
        for p in plan[:8]:
            kpc = len(p.get("key_products", []))
            data.append(
                [
                    p["vendor_name"][:30],
                    str(p.get("total_suggested_units", 0)),
                    str(p.get("affected_customers", 0)),
                    str(kpc),
                ]
            )
        t = Table(data, colWidths=[6 * cm, 3 * cm, 2.5 * cm, 3 * cm])
        t.setStyle(self._table_style())
        story.extend([t, Spacer(1, 4 * mm)])
        # Show top key products for first 2 vendors
        for p in plan[:2]:
            kps = p.get("key_products", [])[:3]
            if kps:
                story.append(
                    Paragraph(
                        f"<b>De {p['vendor_name'][:25]}:</b>", self.styles["Normal"]
                    )
                )
                for kp in kps:
                    story.append(
                        Paragraph(
                            f"  • {kp['product_name'][:28]}: {kp.get('suggested_order',0)} uds ({kp.get('affected_customers',0)} cl.)",
                            self.styles["Normal"],
                        )
                    )
        story.append(Spacer(1, 4 * mm))

    def _add_customer_vendor_mix(self, story: List[Any]) -> None:
        """Add brief customer-vendor mix summary."""
        mix = self.data.get("customer_vendor_mix", [])
        if not mix:
            return
        story.append(
            Paragraph("🔗 Mix Clientes-Proveedores (Top 5)", self.styles["SectionTitle"])
        )
        for m in mix[:5]:
            tops = ", ".join(
                [
                    f"{v['vendor_name'][:10]}({v.get('pct',0):.0f}%)"
                    for v in m.get("top_vendors", [])[:2]
                ]
            )
            story.append(
                Paragraph(
                    f"<b>{m['customer_name'][:28]}</b> — {m.get('vendor_count',0)} prov., {m.get('total_revenue',0):,.0f} — {tops}".replace(
                        ",", "."
                    ),
                    self.styles["Normal"],
                )
            )
        story.append(Spacer(1, 4 * mm))

    def _add_recommendations(self, story: List[Any]) -> None:
        """Add recommendations section."""
        story.append(Paragraph("💡 Recomendaciones", self.styles["SectionTitle"]))
        for rec in self.ai_insights.get("recommendations", []):
            badge_color = {
                "Alta": "#dc2626",
                "Media": "#f59e0b",
                "Baja": "#2563eb",
            }.get(rec.get("priority", ""), "#6b7280")
            text = f'<b>[<font color="{badge_color}">{rec["priority"]}</font>] {rec["area"]}</b> — {rec["action"]}'
            story.append(Paragraph(text, self.styles["InsightBullet"]))
        story.append(Spacer(1, 4 * mm))

    def _add_risks(self, story: List[Any]) -> None:
        """Add risks section."""
        story.append(Paragraph("⚠️ Riesgos Identificados", self.styles["SectionTitle"]))
        for risk in self.ai_insights.get("risks", []):
            style_name = {
                "Alto": "RiskHigh",
                "Medio": "RiskMedium",
            }.get(risk.get("level", ""), "InsightBullet")
            text = f'<b>[{risk["level"]}] {risk["type"]}</b> — {risk["description"]}'
            story.append(Paragraph(text, self.styles[style_name]))
        story.append(Spacer(1, 4 * mm))

    def _add_opportunities(self, story: List[Any]) -> None:
        """Add opportunities section."""
        story.append(Paragraph("🚀 Oportunidades", self.styles["SectionTitle"]))
        for opp in self.ai_insights.get("opportunities", []):
            text = f'<b>[{opp["impact"]}] {opp["type"]}</b> — {opp["description"]}'
            story.append(Paragraph(text, self.styles["Opportunity"]))
        story.append(Spacer(1, 4 * mm))

    def _add_footer(self, story: List[Any]) -> None:
        """Add footer text."""
        story.append(Spacer(1, 10 * mm))
        story.append(
            Paragraph(
                f'<font size="8" color="#9ca3af">Informe generado automáticamente por Business Data Analyzer — '
                f'{datetime.now().strftime("%d/%m/%Y %H:%M")}</font>',
                ParagraphStyle(
                    "Footer",
                    alignment=TA_CENTER,
                    fontSize=8,
                    textColor=colors.HexColor("#9ca3af"),
                ),
            )
        )

    def _table_style(self) -> TableStyle:
        """Return consistent table styling."""
        return TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f8fafc")],
                ),
            ]
        )
