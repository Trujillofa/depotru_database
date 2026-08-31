"""Customer invoice summary report for CLI and Vanna web UI."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from business_analyzer.ai.base import Config
from business_analyzer.core.database import Database
from business_analyzer.core.invoice_summary import (
    InvoiceSummaryRunner,
    parse_invoice_numbers,
)

MONTHS_SHORT = {
    1: "ene",
    2: "feb",
    3: "mar",
    4: "abr",
    5: "may",
    6: "jun",
    7: "jul",
    8: "ago",
    9: "sep",
    10: "oct",
    11: "nov",
    12: "dic",
}


def cop(value: Any, *, cents: bool = True) -> str:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "—"
    if cents:
        text = f"{num:,.2f}"
        return "$" + text.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"${num:,.0f}".replace(",", ".")


def qty(value: Any) -> str:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "—"
    if abs(num - round(num)) < 1e-9:
        return f"{int(round(num)):,}".replace(",", ".")
    text = f"{num:.2f}"
    return text.replace(".", ",")


def fmt_date(value: Any) -> str:
    if not value:
        return "—"
    if isinstance(value, date):
        d = value
    else:
        try:
            d = date.fromisoformat(str(value)[:10])
        except ValueError:
            return str(value)
    return f"{d.day} {MONTHS_SHORT[d.month]} {d.year}"


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", ascii_text).strip("_").lower()
    return slug[:40]


def invoice_summary_output_basename(fmt: str = "html", slug: str = "") -> str:
    ext = {
        "html": "html",
        "pdf": "pdf",
        "markdown": "md",
        "md": "md",
        "json": "json",
    }.get((fmt or "html").lower(), "html")
    if slug:
        return f"RESUMEN_FACTURAS_{slug}.{ext}"
    return f"RESUMEN_FACTURAS.{ext}"


def render_markdown(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") or {}
    customer = report.get("customer") or {}
    invoices = list(report.get("invoices") or [])
    title_name = customer.get("name") or "Cliente"
    obra = report.get("obra")
    lines = [
        f"# Resumen de facturas — {title_name}",
        "",
        f"**Cliente:** {title_name}",
        f"**Identificación:** {customer.get('nit') or '—'}",
    ]
    if obra:
        lines.append(f"**Obra:** {obra}")
    if invoices:
        lines.append(f"**Asesor:** {invoices[0].get('vendedor') or '—'}")
        lines.append(f"**Sede:** {invoices[0].get('sede') or 'Sede comercial'}")
    lines.extend(
        [
            "",
            "Este documento es un **resumen comercial**. "
            "No reemplaza las facturas DIAN.",
            "",
            "## Totales",
            "",
            "| Concepto | Valor |",
            "|---|---|",
            f"| Subtotal (antes de IVA) | "
            f"**{cop(summary.get('total_sin_iva'), cents=False)}** |",
            f"| Base gravada (19%) | {cop(summary.get('base_gravada'), cents=False)} |",
            f"| Exento de IVA | {cop(summary.get('exento'), cents=False)} |",
            f"| IVA | **{cop(summary.get('iva'))}** |",
            f"| **Total facturado** | **{cop(summary.get('total_mas_iva'))}** |",
            f"| Pagos aplicados | {cop(summary.get('pagos'), cents=False)} |",
            f"| **Saldo en cartera** | **{cop(summary.get('saldo'), cents=False)}** |",
            "",
            "## Facturas",
            "",
            "| Factura | Fecha | Vence | Subtotal | IVA | Total | Saldo |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for inv in invoices:
        lines.append(
            f"| {inv.get('numero')} | {fmt_date(inv.get('fecha'))} | "
            f"{fmt_date(inv.get('vence'))} | "
            f"{cop(inv.get('total_sin_iva'), cents=False)} | "
            f"{cop(inv.get('iva'))} | {cop(inv.get('total_mas_iva'))} | "
            f"{cop(inv.get('saldo'), cents=False)} |"
        )
    lines.append(
        f"| **Total** | | | **{cop(summary.get('total_sin_iva'), cents=False)}** | "
        f"**{cop(summary.get('iva'))}** | **{cop(summary.get('total_mas_iva'))}** | "
        f"**{cop(summary.get('saldo'), cents=False)}** |"
    )

    if report.get("families"):
        lines.extend(
            ["", "## Composición", "", "| Familia | Total con IVA |", "|---|---:|"]
        )
        for fam in report["families"]:
            lines.append(
                f"| {fam.get('categoria')} | {cop(fam.get('total_mas_iva'))} |"
            )

    lines.extend(["", "## Detalle por factura", ""])
    for inv in invoices:
        lines.append(
            f"### Factura {inv.get('numero')} — {fmt_date(inv.get('fecha'))} — "
            f"{cop(inv.get('total_mas_iva'))}"
        )
        lines.append("")
        lines.append("| Artículo | Cant. | Vlr. unit. | Total |")
        lines.append("|---|---:|---:|---:|")
        for item in inv.get("lines") or []:
            name = item.get("nombre") or ""
            if item.get("exento"):
                name += " (exento IVA)"
            lines.append(
                f"| {name} | {qty(item.get('cantidad'))} | "
                f"{cop(item.get('unitario_sin_iva'), cents=False)} | "
                f"{cop(item.get('total_mas_iva'))} |"
            )
        lines.append("")

    if report.get("repeated"):
        lines.extend(
            [
                "## Artículos que se repiten entre facturas",
                "",
                "| Artículo | Facturas | Cant. | Subtotal |",
                "|---|---|---:|---:|",
            ]
        )
        for item in report["repeated"]:
            facts = " + ".join(str(n) for n in item.get("facturas") or [])
            lines.append(
                f"| {item.get('nombre')} | {facts} | {qty(item.get('cantidad'))} | "
                f"{cop(item.get('total_sin_iva'), cents=False)} |"
            )
        lines.append("")

    missing = report.get("missing") or []
    if missing:
        listed = ", ".join(str(n) for n in missing)
        lines.extend(
            [
                "## Facturas no encontradas",
                "",
                f"No aparecen en ventas: {listed}.",
                "",
            ]
        )
    if report.get("multiple_customers"):
        lines.extend(
            [
                "## Varios clientes",
                "",
                "Las facturas pertenecen a más de un cliente. El total consolidado "
                "mezcla cuentas distintas.",
                "",
            ]
        )
    lines.append(f"*Depósito Trujillo · Elaborado el {fmt_date(date.today())}*")
    return "\n".join(lines)


def build_invoice_summary_result(
    *,
    invoices: str | Sequence[int] = "",
    document_code: Optional[str] = None,
    output_dir: Optional[Path] = None,
    fmt: str = "html",
    db: Optional[Database] = None,
    report: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    if isinstance(invoices, str):
        numbers = parse_invoice_numbers(invoices)
    else:
        numbers = [int(n) for n in invoices]
    if not numbers:
        return {
            "status": "error",
            "message": "Indica al menos un número de factura.",
        }

    fmt_norm = (fmt or "html").strip().lower()
    if fmt_norm in ("md", "markdown"):
        fmt_norm = "markdown"
    if fmt_norm not in ("html", "pdf", "markdown", "json"):
        return {
            "status": "error",
            "message": f"Formato inválido: {fmt!r} (use html, pdf, markdown o json)",
        }

    if report is None:
        try:
            runner = InvoiceSummaryRunner(db, document_code=document_code)
            report = runner.build_report(numbers)
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "error",
                "message": f"Error consultando facturas: {exc}",
            }

    if not report.get("invoices"):
        missing = ", ".join(str(n) for n in report.get("missing") or numbers)
        return {
            "status": "error",
            "message": f"No se encontraron las facturas: {missing}.",
        }

    slug = slugify(str((report.get("customer") or {}).get("name") or "cliente"))
    out_dir = Path(output_dir) if output_dir else Config.ensure_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / invoice_summary_output_basename(fmt_norm, slug=slug)

    try:
        if fmt_norm == "html":
            from business_analyzer.reports.invoice_summary_html import render_html

            path.write_text(render_html(report), encoding="utf-8")
        elif fmt_norm == "pdf":
            from business_analyzer.reports.invoice_summary_pdf import (
                write_invoice_summary_pdf,
            )

            write_invoice_summary_pdf(report, path)
        elif fmt_norm == "json":
            path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        else:
            path.write_text(render_markdown(report), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "message": f"Error escribiendo informe ({fmt_norm}): {exc}",
        }

    summary = report.get("summary") or {}
    customer = report.get("customer") or {}
    return {
        "status": "success",
        "format": fmt_norm if fmt_norm != "markdown" else "markdown",
        "path": str(path.resolve()),
        "invoice_count": summary.get("invoice_count"),
        "customer_name": customer.get("name"),
        "summary": summary,
        "missing": list(report.get("missing") or []),
        "message": (
            f"Resumen de facturas — {customer.get('name') or 'cliente'} "
            f"({summary.get('invoice_count')} docs, "
            f"{cop(summary.get('total_mas_iva'))})\n"
            f"Archivo: {path.name}"
        ),
    }
