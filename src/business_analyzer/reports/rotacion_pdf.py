"""PDF export for Rotación de Existencias (ReportLab)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def _f(value: Any, decimals: int = 0) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "—"
    if decimals == 0:
        return f"{n:,.0f}".replace(",", ".")
    t = f"{n:,.{decimals}f}"
    return t.replace(",", "X").replace(".", ",").replace("X", ".")


def _short(text: Any, n: int = 36) -> str:
    s = str(text or "")
    return s if len(s) <= n else s[: n - 1] + "…"


def _strip_html(text: str) -> str:
    """Very small strip for insight bodies (bold/code/ol)."""
    import re

    t = text or ""
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"</?(strong|em|code|p|div|span)[^>]*>", "", t, flags=re.I)
    t = re.sub(r"</?ol[^>]*>", "\n", t, flags=re.I)
    t = re.sub(r"<li[^>]*>", "• ", t, flags=re.I)
    t = re.sub(r"</li>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    return " ".join(t.split())


def write_rotacion_pdf(
    report: Mapping[str, Any],
    path: Path,
    *,
    insights: Optional[List[Dict[str, str]]] = None,
) -> Path:
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError(
            "ReportLab no está instalado. Instálelo con: pip install reportlab"
        )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="RotTitle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#0f2744"),
            spaceAfter=8,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="RotH2",
            parent=styles["Heading2"],
            fontSize=12,
            textColor=colors.HexColor("#1e40af"),
            spaceBefore=12,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="RotBody",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="RotSmall",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#64748b"),
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="RotInsight",
            parent=styles["Normal"],
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#1e293b"),
            leftIndent=4,
            spaceAfter=6,
        )
    )

    summary = report.get("summary") or {}
    as_of = report.get("as_of_date") or ""
    story: list = []
    story.append(Paragraph("Rotación de Existencias", styles["RotTitle"]))
    story.append(
        Paragraph(
            f"Fecha {as_of} · ventana {report.get('velocity_days', 90)} d · "
            f"modo {report.get('demand_mode', 'warehouse')}",
            styles["RotSmall"],
        )
    )
    story.append(Spacer(1, 0.35 * cm))

    # KPI strip
    kpi_data = [
        ["Posiciones", "Quiebre", "Sobrestock", "Muerto", "Stock uds", "Med. cob."],
        [
            _f(summary.get("Filas")),
            _f(summary.get("QUIEBRE")),
            _f(summary.get("SOBRESTOCK")),
            _f(summary.get("MUERTO")),
            _f(summary.get("Stock_Total_Unidades")),
            _f(summary.get("Mediana_Dias_Cobertura"), 1)
            if summary.get("Mediana_Dias_Cobertura") is not None
            else "—",
        ],
    ]
    kpi_t = Table(kpi_data, colWidths=[2.8 * cm] * 6)
    kpi_t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#eff6ff")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(kpi_t)
    story.append(Spacer(1, 0.4 * cm))

    if insights is None:
        from business_analyzer.reports.rotacion_html import build_insights

        insights = build_insights(report)

    story.append(Paragraph("Insights y plan de acción", styles["RotH2"]))
    for ins in insights:
        title = ins.get("title") or "Insight"
        body = _strip_html(ins.get("body") or "")
        story.append(Paragraph(f"<b>{title}.</b> {body}", styles["RotInsight"]))

    def add_table(
        title: str,
        headers: Sequence[str],
        rows: Sequence[Sequence[str]],
        widths: Optional[Sequence[float]] = None,
    ) -> None:
        story.append(Paragraph(title, styles["RotH2"]))
        if not rows:
            story.append(Paragraph("Sin filas en este corte.", styles["RotBody"]))
            return
        data = [list(headers)] + [list(r) for r in rows[:20]]
        t = Table(data, colWidths=list(widths) if widths else None, repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                    ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f8fafc")],
                    ),
                ]
            )
        )
        story.append(t)

    q_rows = []
    for r in report.get("action_quiebre") or []:
        q_rows.append(
            [
                str(r.get("SKU") or ""),
                _short(r.get("Producto"), 28),
                str(r.get("AlmacenCodigo") or ""),
                _f(r.get("Stock")),
                _f(r.get("Venta_Comercial_Nd")),
                _f(r.get("Dias_Cobertura_Comercial"), 1)
                if r.get("Dias_Cobertura_Comercial") is not None
                else "—",
            ]
        )
    add_table(
        "A · Quiebre (prioridad compra)",
        ["SKU", "Producto", "Bod.", "Stock", "Venta", "Cob."],
        q_rows,
        [2.2 * cm, 5.5 * cm, 1.3 * cm, 1.8 * cm, 2 * cm, 1.5 * cm],
    )

    c_rows = []
    for r in report.get("action_capital_atrapado") or []:
        c_rows.append(
            [
                str(r.get("SKU") or ""),
                _short(r.get("Producto"), 26),
                str(r.get("AlmacenCodigo") or ""),
                _f(r.get("Stock")),
                _f(r.get("Venta_Comercial_Nd")),
                str(r.get("Bandera") or ""),
            ]
        )
    add_table(
        "B · Capital atrapado",
        ["SKU", "Producto", "Bod.", "Stock", "Venta", "Bandera"],
        c_rows,
        [2.2 * cm, 5 * cm, 1.3 * cm, 1.8 * cm, 1.8 * cm, 2.2 * cm],
    )

    t_rows = []
    for r in report.get("suggested_transfers") or []:
        t_rows.append(
            [
                str(r.get("SKU") or ""),
                _short(r.get("Producto"), 22),
                f"{r.get('Desde')}→{r.get('Hacia')}",
                _f(r.get("Sugerido_Mover"), 1),
                _f(r.get("Venta_Destino_Nd")),
            ]
        )
    add_table(
        "C · Traslados sugeridos",
        ["SKU", "Producto", "Ruta", "Mover", "Venta dest."],
        t_rows,
        [2.2 * cm, 5.5 * cm, 2.2 * cm, 1.8 * cm, 2.2 * cm],
    )

    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            "Deposito Trujillo · Business Data Analyzer · Rotación de Existencias",
            styles["RotSmall"],
        )
    )

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=1.4 * cm,
        rightMargin=1.4 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title=f"Rotación de Existencias {as_of}",
    )
    doc.build(story)
    return path
