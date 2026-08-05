"""Cartera / AR aging report builder for CLI and Vanna web UI."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from business_analyzer.ai.base import Config
from business_analyzer.ai.formatting import format_currency
from business_analyzer.core.cartera_aging import CarteraAgingRunner
from business_analyzer.core.database import Database

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def default_as_of_date(*, today: Optional[date] = None) -> str:
    """Default as-of date: yesterday."""
    ref = today or date.today()
    return (ref - timedelta(days=1)).isoformat()


def cartera_output_basename(as_of_date: str, fmt: str = "html") -> str:
    ext = {
        "html": "html",
        "pdf": "pdf",
        "markdown": "md",
        "md": "md",
        "json": "json",
    }.get((fmt or "html").lower(), "html")
    return f"CARTERA_AGING_{as_of_date}.{ext}"


def validate_as_of_date(as_of_date: str) -> str:
    raw = (as_of_date or "").strip()
    if not _DATE_RE.fullmatch(raw):
        raise ValueError(f"Fecha inválida (use YYYY-MM-DD): {as_of_date!r}")
    date.fromisoformat(raw)
    return raw


def _fmt_money(value: Any) -> str:
    try:
        return str(format_currency(float(value), 0))
    except (TypeError, ValueError):
        return "—"


def _fmt_pct(value: Any, decimals: int = 1) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "—"
    t = f"{n:,.{decimals}f}"
    return t.replace(",", "X").replace(".", ",").replace("X", ".") + "%"


def _fmt_num(value: Any, decimals: int = 0) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "—"
    if decimals == 0:
        return f"{n:,.0f}".replace(",", ".")
    t = f"{n:,.{decimals}f}"
    return t.replace(",", "X").replace(".", ",").replace("X", ".")


def _short(text: Any, n: int = 42) -> str:
    s = str(text or "")
    return s if len(s) <= n else s[: n - 1] + "…"


def render_markdown(report: Mapping[str, Any]) -> str:
    """Spanish decision markdown for a built cartera aging report dict."""
    summary = report.get("summary") or {}
    excluded = report.get("excluded_document_codes") or []
    dso_window = int(report.get("dso_days_window") or 30)

    lines = [
        "# Cartera / Cuentas por Cobrar (Aging)",
        "",
        f"- **Fecha referencia:** {report.get('as_of_date')}",
        f"- **Snapshot fecha_carga:** {report.get('fecha_carga_snapshot')}",
        f"- **Fuente:** `{report.get('source') or 'banco_cartera'}` (último snapshot)",
        f"- **Clientes con saldo:** {_fmt_num(summary.get('Clientes_Con_Saldo'), 0)}",
        f"- **Filas documento (snapshot):** {_fmt_num(summary.get('Documentos_Filas'), 0)}",
        "",
        "## Resumen ejecutivo",
        "",
        f"- **Cartera total:** {_fmt_money(summary.get('Cartera_Total'))}",
        f"- **Corriente (al día):** {_fmt_money(summary.get('Cartera_Corriente'))}",
        (
            f"- **Vencida:** {_fmt_money(summary.get('Cartera_Vencida'))} "
            f"({_fmt_pct(summary.get('Cartera_Vencida_Pct'))})"
        ),
        (
            f"- **Vencida >90 d:** {_fmt_money(summary.get('Cartera_Vencida_90_Plus'))} "
            f"({_fmt_pct(summary.get('Cartera_Vencida_90_Plus_Pct'))})"
        ),
        f"- **Clientes sobre cupo:** {_fmt_num(summary.get('Clientes_Sobre_Cupo'), 0)}",
        (
            f"- **Días vencidos prom. ponderado:** "
            f"{_fmt_num(summary.get('Dias_Vencidos_Promedio_Ponderado'), 1)}"
        ),
    ]
    if summary.get("DSO_Dias") is not None:
        lines.append(
            f"- **DSO ({dso_window} d):** {_fmt_num(summary.get('DSO_Dias'), 1)} días "
            f"(ventas netas periodo: {_fmt_money(summary.get('Ventas_Netas_Periodo'))})"
        )
        lines.append(
            f"- **Exclusión ventas DSO (DocumentosCodigo):** "
            + ", ".join(f"`{c}`" for c in excluded)
        )

    lines.extend(
        [
            "",
            "## Buckets de aging",
            "",
            "| Bucket | Monto | % cartera |",
            "|---|---:|---:|",
        ]
    )
    for b in report.get("buckets") or []:
        lines.append(
            f"| {b.get('label')} | {_fmt_money(b.get('amount'))} | "
            f"{_fmt_pct(b.get('share_pct'))} |"
        )

    lines.extend(
        [
            "",
            "## Top clientes vencidos",
            "",
            "| Cliente | Vendedor | Vencido | Total | Días | >90 d |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    overdue = report.get("top_overdue") or []
    if not overdue:
        lines.append("| — | *(sin filas)* | — | — | — | — |")
    for row in overdue:
        lines.append(
            f"| {_short(row.get('cliente_razon_social'))} | "
            f"{_short(row.get('vendedor_nombre'), 20)} | "
            f"{_fmt_money(row.get('vencido'))} | "
            f"{_fmt_money(row.get('total'))} | "
            f"{_fmt_num(row.get('dias_vencidos'), 0)} | "
            f"{_fmt_money(row.get('vencido_90_plus'))} |"
        )

    lines.extend(
        [
            "",
            "## Concentración de cartera (Top clientes)",
            "",
            "| Cliente | Total | % | % acum. | Vencido |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in report.get("top_concentration") or []:
        lines.append(
            f"| {_short(row.get('cliente_razon_social'))} | "
            f"{_fmt_money(row.get('total'))} | "
            f"{_fmt_pct(100 * float(row.get('share_total') or 0))} | "
            f"{_fmt_pct(100 * float(row.get('share_acum') or 0))} | "
            f"{_fmt_money(row.get('vencido'))} |"
        )

    lines.extend(
        [
            "",
            "## Clientes sobre cupo de crédito",
            "",
            "| Cliente | Cupo | Total | Exceso | Vendedor |",
            "|---|---:|---:|---:|---|",
        ]
    )
    over = report.get("over_limit") or []
    if not over:
        lines.append("| — | *(ninguno sobre cupo)* | — | — | — |")
    for row in over:
        lines.append(
            f"| {_short(row.get('cliente_razon_social'))} | "
            f"{_fmt_money(row.get('cliente_cupo'))} | "
            f"{_fmt_money(row.get('total'))} | "
            f"{_fmt_money(row.get('exceso_cupo'))} | "
            f"{_short(row.get('vendedor_nombre'), 20)} |"
        )

    lines.extend(
        [
            "",
            "## Por vendedor",
            "",
            "| Vendedor | Clientes | Total | Vencido | >90 d |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in report.get("by_vendedor") or []:
        lines.append(
            f"| {_short(row.get('vendedor_nombre'), 28)} | "
            f"{_fmt_num(row.get('clientes'), 0)} | "
            f"{_fmt_money(row.get('total'))} | "
            f"{_fmt_money(row.get('vencido'))} | "
            f"{_fmt_money(row.get('vencido_90_plus'))} |"
        )

    lines.extend(
        [
            "",
            "## Metodología",
            "",
            (
                "1. **Snapshot:** `banco_cartera` con `fecha_carga = MAX(fecha_carga)` "
                "(o el más reciente con fecha ≤ referencia)."
            ),
            (
                "2. **Agregación:** saldos por cliente (`cliente_uid`); buckets "
                "`corriente`, `vencido_30`…`vencido_superior`."
            ),
            (
                "3. **% vencida / >90 d:** alineado a Q9 del KPI pack "
                "(`vencido` y suma 90+120+360+superior sobre total)."
            ),
            (
                f"4. **DSO (opcional):** cartera × {dso_window} / ventas netas del periodo; "
                "ventas en `banco_datos` con "
                f"`DocumentosCodigo NOT IN ({', '.join(excluded)})`."
            ),
            "5. **v1:** sin J3 `CarCarteraCliente`.",
            "",
        ]
    )
    return "\n".join(lines)


def build_cartera_result(
    *,
    as_of_date: str,
    top_n: int = 25,
    dso_days: int = 30,
    include_dso: bool = True,
    output_dir: Optional[Path] = None,
    write_json: bool = False,
    fmt: str = "html",
    db: Optional[Database] = None,
) -> Dict[str, Any]:
    """Run cartera aging analysis and write HTML / PDF / markdown / JSON."""
    try:
        as_of = validate_as_of_date(as_of_date)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    fmt_norm = (fmt or "html").strip().lower()
    if fmt_norm in ("md", "markdown"):
        fmt_norm = "markdown"
    if fmt_norm not in ("html", "pdf", "markdown", "json"):
        return {
            "status": "error",
            "message": (f"Formato inválido: {fmt!r} (use html, pdf, markdown o json)"),
        }

    try:
        runner = CarteraAgingRunner(
            db or Database(),
            top_n=int(top_n),
            dso_days=int(dso_days),
            include_dso=bool(include_dso),
        )
        report = runner.build_report(as_of)
    except Exception as exc:  # noqa: BLE001 — surface to API
        return {
            "status": "error",
            "message": f"Error generando cartera / aging: {exc}",
        }

    from business_analyzer.reports.cartera_html import build_insights, render_html

    insights = build_insights(report)
    report = dict(report)
    report["insights"] = insights

    out_dir = Path(output_dir) if output_dir else Config.ensure_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / cartera_output_basename(as_of, fmt_norm)

    try:
        if fmt_norm == "html":
            path.write_text(render_html(report, insights=insights), encoding="utf-8")
        elif fmt_norm == "pdf":
            from business_analyzer.reports.cartera_pdf import write_cartera_pdf

            write_cartera_pdf(report, path, insights=insights)
        elif fmt_norm == "json":
            path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        else:
            path.write_text(render_markdown(report), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "message": f"Error escribiendo informe ({fmt_norm}): {exc}",
        }

    if write_json and fmt_norm != "json":
        path.with_suffix(".json").write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8"
        )

    summary = report.get("summary") or {}
    filename = path.name
    return {
        "status": "success",
        "format": fmt_norm if fmt_norm != "markdown" else "markdown",
        "as_of_date": as_of,
        "path": str(path.resolve()),
        "summary": summary,
        "insights_count": len(insights),
        "message": (
            f"Cartera / Aging generada — {as_of} ({fmt_norm.upper()})\n"
            f"Total={_fmt_money(summary.get('Cartera_Total'))}, "
            f"Vencida={_fmt_pct(summary.get('Cartera_Vencida_Pct'))}, "
            f">90d={_fmt_pct(summary.get('Cartera_Vencida_90_Plus_Pct'))}\n"
            f"Insights={len(insights)} · Archivo: {filename}"
        ),
    }
