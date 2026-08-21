"""PDF export for the customer invoice summary (ReportLab)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, List, Mapping, Sequence

from business_analyzer.reports.invoice_summary import cop, fmt_date, qty

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        HRFlowable,
        KeepTogether,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

BRICK = colors.HexColor("#7A3A22")
INK = colors.HexColor("#1A1410")
MUTED = colors.HexColor("#5C534C")
RULE = colors.HexColor("#D4C8BC")
ROW = colors.HexColor("#F7F3EE")
PAGE_W, PAGE_H = A4
MARGIN_X = 1.8 * cm


def write_invoice_summary_pdf(report: Mapping[str, Any], path: Path) -> Path:
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError(
            "ReportLab no está instalado. Instálelo con: pip install reportlab"
        )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    base = getSampleStyleSheet()
    styles = {
        "kicker": ParagraphStyle(
            "kicker",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=BRICK,
            spaceAfter=2,
        ),
        "title": ParagraphStyle(
            "title",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=18,
            leading=22,
            textColor=INK,
            spaceAfter=4,
        ),
        "sub": ParagraphStyle(
            "sub",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=MUTED,
            spaceAfter=8,
        ),
        "h1": ParagraphStyle(
            "h1s",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=12.5,
            leading=16,
            textColor=INK,
            spaceBefore=12,
            spaceAfter=5,
        ),
        "h2": ParagraphStyle(
            "h2s",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=INK,
            spaceBefore=8,
            spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=INK,
            spaceAfter=5,
        ),
        "th": ParagraphStyle(
            "th",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            textColor=colors.white,
        ),
        "thr": ParagraphStyle(
            "thr",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            textColor=colors.white,
            alignment=2,
        ),
        "td": ParagraphStyle(
            "td",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=INK,
        ),
        "tdr": ParagraphStyle(
            "tdr",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=INK,
            alignment=2,
        ),
        "tdb": ParagraphStyle(
            "tdb",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            textColor=INK,
        ),
        "tdbr": ParagraphStyle(
            "tdbr",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            textColor=INK,
            alignment=2,
        ),
        "callout": ParagraphStyle(
            "callout",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=INK,
        ),
        "meta": ParagraphStyle(
            "meta",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=MUTED,
        ),
    }

    content_w = PAGE_W - 2 * MARGIN_X

    def P(text: Any, style: str = "td") -> Paragraph:
        return Paragraph(str(text), styles[style])

    def table(
        headers: Sequence[str],
        rows: Sequence[Sequence[Any]],
        col_widths: Sequence[float],
        right_cols: set[int] | None = None,
        last_bold: bool = False,
    ) -> Table:
        right = set(right_cols or [])
        data = [[P(h, "thr" if i in right else "th") for i, h in enumerate(headers)]]
        for r_i, row in enumerate(rows):
            is_last = last_bold and r_i == len(rows) - 1
            cells = []
            for i, cell in enumerate(row):
                if is_last:
                    st = "tdbr" if i in right else "tdb"
                else:
                    st = "tdr" if i in right else "td"
                cells.append(P(cell, st))
            data.append(cells)
        grid = Table(data, colWidths=list(col_widths), repeatRows=1)
        cmds: List[Any] = [
            ("BACKGROUND", (0, 0), (-1, 0), BRICK),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("BOX", (0, 0), (-1, -1), 0.4, RULE),
            ("LINEBELOW", (0, 1), (-1, -2), 0.2, RULE),
        ]
        for i in range(1, len(data)):
            if i % 2 == 0:
                cmds.append(("BACKGROUND", (0, i), (-1, i), ROW))
        if last_bold:
            cmds.append(("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EFE6DC")))
            cmds.append(("LINEABOVE", (0, -1), (-1, -1), 0.6, BRICK))
        grid.setStyle(TableStyle(cmds))
        return grid

    def callout(text: str) -> Table:
        inner = Table([[P(text, "callout")]], colWidths=[content_w - 8])
        inner.setStyle(
            TableStyle(
                [
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("BACKGROUND", (0, 0), (-1, -1), ROW),
                    ("LINEBEFORE", (0, 0), (0, -1), 3, BRICK),
                ]
            )
        )
        return inner

    def header_footer(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(BRICK)
        canvas.rect(0, PAGE_H - 6, PAGE_W, 6, fill=1, stroke=0)
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.6)
        canvas.line(MARGIN_X, 1.4 * cm, PAGE_W - MARGIN_X, 1.4 * cm)
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 7.5)
        name = str((report.get("customer") or {}).get("name") or "Cliente")
        canvas.drawString(MARGIN_X, 1.0 * cm, f"Depósito Trujillo  ·  {name[:48]}")
        canvas.drawRightString(PAGE_W - MARGIN_X, 1.0 * cm, str(doc.page))
        canvas.restoreState()

    summary = report.get("summary") or {}
    customer = report.get("customer") or {}
    invoices = list(report.get("invoices") or [])
    story: list = []
    story.append(P("RESUMEN COMERCIAL DE FACTURAS", "kicker"))
    story.append(P(str(customer.get("name") or "Cliente"), "title"))
    sub = f"Identificación {customer.get('nit') or '—'}"
    if report.get("obra"):
        sub += f"  ·  {report.get('obra')}"
    if invoices:
        sub += f"  ·  {invoices[0].get('sede') or ''}"
    story.append(P(sub, "sub"))
    story.append(HRFlowable(width="100%", thickness=1.2, color=BRICK, spaceAfter=8))
    story.append(
        P(
            "Resumen de facturas electrónicas de venta. "
            "No reemplaza las facturas DIAN.",
            "body",
        )
    )
    story.append(
        callout(
            f"<b>Saldo pendiente: {cop(summary.get('saldo'), cents=False)}.</b>  "
            f"Subtotal {cop(summary.get('total_sin_iva'), cents=False)} + "
            f"IVA {cop(summary.get('iva'))} = total "
            f"{cop(summary.get('total_mas_iva'))}."
        )
    )
    if report.get("missing"):
        listed = ", ".join(str(n) for n in report["missing"])
        story.append(callout(f"No encontradas: {listed}."))
    if report.get("multiple_customers"):
        story.append(callout("Las facturas pertenecen a más de un cliente."))

    story.append(P("Totales", "h1"))
    story.append(
        table(
            ["Concepto", "Valor"],
            [
                [
                    "Subtotal (antes de IVA)",
                    cop(summary.get("total_sin_iva"), cents=False),
                ],
                ["Base gravada", cop(summary.get("base_gravada"), cents=False)],
                ["Exento de IVA", cop(summary.get("exento"), cents=False)],
                ["IVA", cop(summary.get("iva"))],
                ["Total facturado", cop(summary.get("total_mas_iva"))],
                ["Pagos aplicados", cop(summary.get("pagos"), cents=False)],
                ["Saldo en cartera", cop(summary.get("saldo"), cents=False)],
            ],
            [content_w * 0.62, content_w * 0.38],
            right_cols={1},
            last_bold=True,
        )
    )

    story.append(P("Facturas", "h1"))
    inv_rows = [
        [
            str(inv.get("numero")),
            fmt_date(inv.get("fecha")),
            fmt_date(inv.get("vence")),
            cop(inv.get("total_sin_iva"), cents=False),
            cop(inv.get("iva")),
            cop(inv.get("total_mas_iva")),
        ]
        for inv in invoices
    ]
    inv_rows.append(
        [
            "Total",
            "",
            "",
            cop(summary.get("total_sin_iva"), cents=False),
            cop(summary.get("iva")),
            cop(summary.get("total_mas_iva")),
        ]
    )
    story.append(
        table(
            ["Factura", "Fecha", "Vence", "Subtotal", "IVA", "Total"],
            inv_rows,
            [
                content_w * 0.14,
                content_w * 0.16,
                content_w * 0.16,
                content_w * 0.18,
                content_w * 0.18,
                content_w * 0.18,
            ],
            right_cols={3, 4, 5},
            last_bold=True,
        )
    )

    if report.get("families"):
        story.append(P("Composición", "h1"))
        story.append(
            table(
                ["Familia", "Total con IVA"],
                [
                    [f.get("categoria"), cop(f.get("total_mas_iva"))]
                    for f in report["families"]
                ],
                [content_w * 0.62, content_w * 0.38],
                right_cols={1},
            )
        )

    story.append(P("Detalle por factura", "h1"))
    for inv in invoices:
        line_rows = []
        for item in inv.get("lines") or []:
            label = str(item.get("nombre") or "")
            if item.get("exento"):
                label += " (exento IVA)"
            line_rows.append(
                [
                    label,
                    qty(item.get("cantidad")),
                    cop(item.get("unitario_sin_iva"), cents=False),
                    cop(item.get("total_mas_iva")),
                ]
            )
        story.append(
            KeepTogether(
                [
                    P(
                        f"Factura {inv.get('numero')}  ·  "
                        f"{fmt_date(inv.get('fecha'))}  ·  "
                        f"{cop(inv.get('total_mas_iva'))}",
                        "h2",
                    ),
                    table(
                        ["Artículo", "Cant.", "Vlr. unit.", "Total"],
                        line_rows,
                        [
                            content_w * 0.50,
                            content_w * 0.12,
                            content_w * 0.18,
                            content_w * 0.20,
                        ],
                        right_cols={1, 2, 3},
                    ),
                    Spacer(1, 4),
                ]
            )
        )

    if report.get("repeated"):
        story.append(P("Artículos que se repiten", "h1"))
        story.append(
            table(
                ["Artículo", "Facturas", "Cant.", "Subtotal"],
                [
                    [
                        r.get("nombre"),
                        " + ".join(str(n) for n in r.get("facturas") or []),
                        qty(r.get("cantidad")),
                        cop(r.get("total_sin_iva"), cents=False),
                    ]
                    for r in report["repeated"]
                ],
                [
                    content_w * 0.40,
                    content_w * 0.28,
                    content_w * 0.12,
                    content_w * 0.20,
                ],
                right_cols={2, 3},
            )
        )

    story.append(Spacer(1, 12))
    story.append(
        P(
            f"Depósito Trujillo · Elaborado el {fmt_date(date.today())}",
            "meta",
        )
    )

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=MARGIN_X,
        rightMargin=MARGIN_X,
        topMargin=1.6 * cm,
        bottomMargin=1.8 * cm,
        title=f"Resumen de facturas — {customer.get('name') or 'Cliente'}",
        author="Depósito Trujillo",
    )
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return path
