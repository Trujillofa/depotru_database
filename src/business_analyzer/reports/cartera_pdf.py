"""PDF export for Cartera / AR aging (ReportLab)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from business_analyzer.ai.formatting import format_currency

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
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


def _money(value: Any) -> str:
    try:
        return str(format_currency(float(value), 0))
    except (TypeError, ValueError):
        return "—"


def _f(value: Any, decimals: int = 0) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "—"
    if decimals == 0:
        return f"{n:,.0f}".replace(",", ".")
    t = f"{n:,.{decimals}f}"
    return t.replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(value: Any, decimals: int = 1) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "—"
    return _f(n, decimals) + "%"


def _short(text: Any, n: int = 36) -> str:
    s = str(text or "")
    return s if len(s) <= n else s[: n - 1] + "…"


def _strip_html(text: str) -> str:
    import re

    t = text or ""
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"</?(strong|em|code|p|div|span)[^>]*>", "", t, flags=re.I)
    t = re.sub(r"</?ol[^>]*>", "\n", t, flags=re.I)
    t = re.sub(r"<li[^>]*>", "• ", t, flags=re.I)
    t = re.sub(r"</li>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    return " ".join(t.split())


def write_cartera_pdf(
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
            name="CarTitle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=colors.HexColor("#0f2744"),
            spaceAfter=8,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CarH2",
            parent=styles["Heading2"],
            fontSize=12,
            textColor=colors.HexColor("#9a3412"),
            spaceBefore=12,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CarBody",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155"),
        )
    )
    styles.add(
        ParagraphStyle(
            name="CarSmall",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#64748b"),
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CarInsight",
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
    story.append(Paragraph("Cartera / Cuentas por Cobrar", styles["CarTitle"]))
    story.append(
        Paragraph(
            f"Fecha {as_of} · snapshot {report.get('fecha_carga_snapshot') or '—'}",
            styles["CarSmall"],
        )
    )
    story.append(Spacer(1, 0.35 * cm))

    kpi_data = [
        ["Total", "Corriente", "Vencida", "% Ven.", "% >90d", "Sobre cupo"],
        [
            _money(summary.get("Cartera_Total")),
            _money(summary.get("Cartera_Corriente")),
            _money(summary.get("Cartera_Vencida")),
            _pct(summary.get("Cartera_Vencida_Pct")),
            _pct(summary.get("Cartera_Vencida_90_Plus_Pct")),
            _f(summary.get("Clientes_Sobre_Cupo")),
        ],
    ]
    kpi_t = Table(kpi_data, colWidths=[2.8 * cm] * 6)
    kpi_t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7c2d12")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#fff7ed")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(kpi_t)
    story.append(Spacer(1, 0.4 * cm))

    if insights is None:
        from business_analyzer.reports.cartera_html import build_insights

        insights = build_insights(report)

    story.append(Paragraph("Insights y plan de cobranza", styles["CarH2"]))
    for ins in insights:
        title = ins.get("title") or "Insight"
        body = _strip_html(ins.get("body") or "")
        story.append(Paragraph(f"<b>{title}.</b> {body}", styles["CarInsight"]))

    def add_table(
        title: str,
        headers: Sequence[str],
        rows: Sequence[Sequence[str]],
        widths: Optional[Sequence[float]] = None,
    ) -> None:
        story.append(Paragraph(title, styles["CarH2"]))
        if not rows:
            story.append(Paragraph("Sin filas en este corte.", styles["CarBody"]))
            return
        data = [list(headers)] + [list(r) for r in rows[:20]]
        t = Table(data, colWidths=list(widths) if widths else None, repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#9a3412")),
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

    bucket_rows = []
    for b in report.get("buckets") or []:
        bucket_rows.append(
            [
                str(b.get("label") or ""),
                _money(b.get("amount")),
                _pct(b.get("share_pct")),
            ]
        )
    add_table(
        "Buckets de aging",
        ["Bucket", "Monto", "%"],
        bucket_rows,
        [8 * cm, 4 * cm, 3 * cm],
    )

    od_rows = []
    for r in report.get("top_overdue") or []:
        od_rows.append(
            [
                _short(r.get("cliente_razon_social"), 28),
                _short(r.get("vendedor_nombre"), 16),
                _money(r.get("vencido")),
                _money(r.get("total")),
                _f(r.get("dias_vencidos")),
            ]
        )
    add_table(
        "Top clientes vencidos",
        ["Cliente", "Vendedor", "Vencido", "Total", "Días"],
        od_rows,
        [5.5 * cm, 3.2 * cm, 2.5 * cm, 2.5 * cm, 1.5 * cm],
    )

    ol_rows = []
    for r in report.get("over_limit") or []:
        ol_rows.append(
            [
                _short(r.get("cliente_razon_social"), 30),
                _money(r.get("cliente_cupo")),
                _money(r.get("total")),
                _money(r.get("exceso_cupo")),
            ]
        )
    add_table(
        "Clientes sobre cupo",
        ["Cliente", "Cupo", "Total", "Exceso"],
        ol_rows,
        [6.5 * cm, 3 * cm, 3 * cm, 3 * cm],
    )

    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            "Deposito Trujillo · Business Data Analyzer · Cartera Aging",
            styles["CarSmall"],
        )
    )

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=1.4 * cm,
        rightMargin=1.4 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
        title=f"Cartera Aging {as_of}",
    )
    doc.build(story)
    return path
