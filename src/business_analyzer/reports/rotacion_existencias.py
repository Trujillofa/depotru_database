"""Rotación de Existencias report builder for CLI and Vanna web UI."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from business_analyzer.ai.base import Config
from business_analyzer.core.database import Database
from business_analyzer.core.inventory_turnover import (
    DEMAND_MODE_COMPANY,
    DEMAND_MODE_WAREHOUSE,
    InventoryTurnoverRunner,
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def default_as_of_date(*, today: Optional[date] = None) -> str:
    """Default as-of date: yesterday (sales often lag the current calendar day)."""
    ref = today or date.today()
    return (ref - timedelta(days=1)).isoformat()


def rotacion_output_basename(as_of_date: str, fmt: str = "html") -> str:
    ext = {
        "html": "html",
        "pdf": "pdf",
        "markdown": "md",
        "md": "md",
        "json": "json",
    }.get((fmt or "html").lower(), "html")
    return f"ROTACION_EXISTENCIAS_{as_of_date}.{ext}"


def validate_as_of_date(as_of_date: str) -> str:
    raw = (as_of_date or "").strip()
    if not _DATE_RE.fullmatch(raw):
        raise ValueError(f"Fecha inválida (use YYYY-MM-DD): {as_of_date!r}")
    # Ensure calendar-valid
    date.fromisoformat(raw)
    return raw


def _fmt_num(value: Any, decimals: int = 1) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "—"
    if decimals == 0:
        return f"{n:,.0f}".replace(",", ".")
    text = f"{n:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def _short(text: Any, n: int = 42) -> str:
    s = str(text or "")
    return s if len(s) <= n else s[: n - 1] + "…"


def _detail_row_md(row: Mapping[str, Any]) -> str:
    cover = row.get("Dias_Cobertura_Comercial")
    cover_txt = _fmt_num(cover, 1) if cover is not None else "—"
    return (
        f"| {row.get('SKU')} | {_short(row.get('Producto'))} | "
        f"{row.get('AlmacenCodigo')} | {_fmt_num(row.get('Stock'), 0)} | "
        f"{_fmt_num(row.get('Venta_Comercial_Nd'), 0)} | {cover_txt} | "
        f"{_fmt_num(row.get('Salida_Fisica_Ytd'), 0)} |"
    )


def render_markdown(report: Mapping[str, Any]) -> str:
    """Spanish decision markdown for a built inventory-turnover report dict."""
    summary = report.get("summary") or {}
    policy = report.get("warehouse_policy") or {}
    allow = policy.get("allowlist") or []
    excluded = report.get("excluded_document_codes") or []
    days = int(report.get("velocity_days") or 90)

    lines = [
        "# Rotación de Existencias",
        "",
        f"- **Fecha referencia:** {report.get('as_of_date')}",
        f"- **Ventana demanda comercial:** {days} días",
        (
            f"- **Modo demanda:** `{report.get('demand_mode')}` — "
            f"{report.get('demand_mode_label')}"
        ),
        f"- **Bodegas comerciales:** {', '.join(f'`{c}`' for c in allow)}",
        (
            "- **Exclusión demanda comercial (DocumentosCodigo):** "
            + ", ".join(f"`{c}`" for c in excluded)
        ),
        (
            "- **Fuentes stock:** `InvDetalleExistencias`; "
            "demanda: J3 `InvVentas`/`InvVentasDetalle` (modo warehouse) o "
            "`banco_datos` (modo company)"
        ),
        (
            "- **Cobertura:** `Stock / Venta_Diaria_Comercial` "
            "(misma bodega en modo warehouse)"
        ),
        (
            f"- **Filas detalle (SKU×bodega):** "
            f"{_fmt_num(report.get('detail_row_count'), 0)}"
        ),
        "",
    ]
    notes = report.get("data_quality_notes") or []
    if notes:
        lines.append("## Avisos de calidad de datos")
        lines.append("")
        for n in notes:
            lines.append(f"- ⚠️ {n}")
        lines.append("")

    lines.extend(
        [
            "## Resumen ejecutivo",
            "",
            f"- **Filas con stock o venta:** {_fmt_num(summary.get('Filas'), 0)}",
            (
                f"- **Posiciones con stock > 0:** "
                f"{_fmt_num(summary.get('SKUs_Con_Stock'), 0)}"
            ),
            (
                f"- **Posiciones con venta comercial:** "
                f"{_fmt_num(summary.get('SKUs_Con_Venta'), 0)}"
            ),
            f"- **QUIEBRE:** {_fmt_num(summary.get('QUIEBRE'), 0)}",
            f"- **BAJA_COBERTURA:** {_fmt_num(summary.get('BAJA_COBERTURA'), 0)}",
            f"- **SALUDABLE:** {_fmt_num(summary.get('SALUDABLE'), 0)}",
            f"- **SOBRESTOCK:** {_fmt_num(summary.get('SOBRESTOCK'), 0)}",
            f"- **MUERTO:** {_fmt_num(summary.get('MUERTO'), 0)}",
            (
                f"- **Stock total (unidades):** "
                f"{_fmt_num(summary.get('Stock_Total_Unidades'), 0)}"
            ),
            (
                f"- **Stock en MUERTO:** "
                f"{_fmt_num(summary.get('Stock_Unidades_Muerto'), 0)} "
                f"({_fmt_num(100 * float(summary.get('Share_Unidades_Muerto') or 0), 1)}%)"
            ),
            (
                f"- **Mediana días cobertura (con demanda):** "
                f"{_fmt_num(summary.get('Mediana_Dias_Cobertura'), 1)}"
            ),
            "",
            "## A — Comprar / transferir (QUIEBRE, 1 fila por SKU = peor bodega)",
            "",
            (
                "| SKU | Producto | Bodega | Stock | Venta comercial | Días cob. | "
                "Salida física YTD |"
            ),
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )

    quiebre = report.get("action_quiebre") or []
    if not quiebre:
        lines.append("| — | *(sin filas)* | — | — | — | — | — |")
    for row in quiebre:
        lines.append(_detail_row_md(row))

    lines.extend(
        [
            "",
            "## B — Capital atrapado (MUERTO + SOBRESTOCK)",
            "",
            "| SKU | Producto | Bodega | Stock | Venta comercial | Días cob. | Bandera |",
            "|---|---|---|---:|---:|---:|---|",
        ]
    )
    capital = report.get("action_capital_atrapado") or []
    if not capital:
        lines.append("| — | *(sin filas)* | — | — | — | — | — |")
    for row in capital:
        cover = row.get("Dias_Cobertura_Comercial")
        cover_txt = _fmt_num(cover, 1) if cover is not None else "—"
        lines.append(
            f"| {row.get('SKU')} | {_short(row.get('Producto'))} | "
            f"{row.get('AlmacenCodigo')} | {_fmt_num(row.get('Stock'), 0)} | "
            f"{_fmt_num(row.get('Venta_Comercial_Nd'), 0)} | {cover_txt} | "
            f"{row.get('Bandera')} |"
        )

    lines.extend(
        [
            "",
            "## C — Traslados sugeridos (superávit → quiebre, mismo SKU)",
            "",
            (
                "| SKU | Producto | Desde | Hacia | Stock origen | Stock dest. | "
                "Venta dest. | Sugerido mover |"
            ),
            "|---|---|---|---|---:|---:|---:|---:|",
        ]
    )
    transfers = report.get("suggested_transfers") or []
    if not transfers:
        lines.append("| — | *(sin pares superávit/quiebre)* | — | — | — | — | — | — |")
    for row in transfers:
        lines.append(
            f"| {row.get('SKU')} | {_short(row.get('Producto'))} | "
            f"{row.get('Desde')} | {row.get('Hacia')} | "
            f"{_fmt_num(row.get('Stock_Origen'), 0)} | "
            f"{_fmt_num(row.get('Stock_Destino'), 0)} | "
            f"{_fmt_num(row.get('Venta_Destino_Nd'), 0)} | "
            f"{_fmt_num(row.get('Sugerido_Mover'), 1)} |"
        )

    lines.extend(
        [
            "",
            "## ABC por demanda comercial (SKU)",
            "",
            "| ABC | SKU | Producto | Venta comercial | Stock total | % venta acum. |",
            "|---|---|---|---:|---:|---:|",
        ]
    )
    for row in report.get("abc") or []:
        lines.append(
            f"| {row.get('ABC')} | {row.get('SKU')} | {_short(row.get('Producto'))} | "
            f"{_fmt_num(row.get('Venta_Comercial_Nd'), 0)} | "
            f"{_fmt_num(row.get('Stock'), 0)} | "
            f"{_fmt_num(100 * float(row.get('Share_Venta_Acum') or 0), 1)}% |"
        )

    lines.extend(["", "## Por bodega comercial", ""])
    for row in report.get("by_warehouse") or []:
        med = row.get("Mediana_Dias_Cobertura")
        med_txt = _fmt_num(med, 1) if med is not None else "—"
        lines.append(
            f"- **{row.get('AlmacenCodigo')}** ({row.get('AlmacenNombre')}): "
            f"QUIEBRE={_fmt_num(row.get('QUIEBRE'), 0)}, "
            f"MUERTO={_fmt_num(row.get('MUERTO'), 0)}, "
            f"SOBRESTOCK={_fmt_num(row.get('SOBRESTOCK'), 0)}, "
            f"stock={_fmt_num(row.get('Stock_Total'), 0)}, "
            f"med. cob.={med_txt} d"
        )

    lines.extend(
        [
            "",
            "## Metodología",
            "",
            (
                "1. **Demanda comercial** (`Venta_Comercial_Nd`): "
                f"modo `{report.get('demand_mode')}` — {report.get('demand_mode_label')}. "
                f"Exclusión de venta `{', '.join(excluded)}` "
                "(no aplica a salidas de inventario TS/ISC)."
            ),
            (
                "2. **Stock**: `InvDetalleExistencias.SaldoActual` (incluye negativos); "
                f"solo bodegas {', '.join(allow)}."
            ),
            (
                "3. **Salida física YTD**: suma mensual `SalidasEne…Dic` en existencias "
                "(movimientos de inventario ya contados en el ERP)."
            ),
            (
                "4. **Banderas:** QUIEBRE (stock≤0 o cob.<7d con demanda en esa bodega), "
                "BAJA_COBERTURA (7–30d), SALUDABLE (30–120d), SOBRESTOCK (>120d), "
                "MUERTO (stock>0 sin venta comercial en esa bodega)."
            ),
            (
                "5. La exclusión de códigos de documento es un **filtro de hechos de venta**, "
                "no implica que esos documentos no muevan inventario físico."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def build_rotacion_result(
    *,
    as_of_date: str,
    top_n: int = 50,
    demand_mode: str = DEMAND_MODE_WAREHOUSE,
    velocity_days: int = 90,
    min_velocity: float = 20.0,
    output_dir: Optional[Path] = None,
    write_json: bool = False,
    fmt: str = "html",
    db: Optional[Database] = None,
) -> Dict[str, Any]:
    """Run turnover analysis and write HTML / PDF / markdown for UI/CLI."""
    try:
        as_of = validate_as_of_date(as_of_date)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    mode = (demand_mode or DEMAND_MODE_WAREHOUSE).strip().lower()
    if mode not in (DEMAND_MODE_WAREHOUSE, DEMAND_MODE_COMPANY):
        return {
            "status": "error",
            "message": (
                f"demand_mode inválido: {demand_mode!r} "
                f"(use '{DEMAND_MODE_WAREHOUSE}' o '{DEMAND_MODE_COMPANY}')"
            ),
        }

    fmt_norm = (fmt or "html").strip().lower()
    if fmt_norm in ("md", "markdown"):
        fmt_norm = "markdown"
    if fmt_norm not in ("html", "pdf", "markdown", "json"):
        return {
            "status": "error",
            "message": (f"Formato inválido: {fmt!r} (use html, pdf, markdown o json)"),
        }

    try:
        runner = InventoryTurnoverRunner(
            db or Database(),
            velocity_days=int(velocity_days),
            min_velocity_qty=float(min_velocity),
            top_n=int(top_n),
            demand_mode=mode,
        )
        report = runner.build_report(as_of)
    except Exception as exc:  # noqa: BLE001 — surface to API
        return {
            "status": "error",
            "message": f"Error generando rotación de existencias: {exc}",
        }

    from business_analyzer.reports.rotacion_html import build_insights, render_html

    insights = build_insights(report)
    report = dict(report)
    report["insights"] = insights

    out_dir = Path(output_dir) if output_dir else Config.ensure_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / rotacion_output_basename(as_of, fmt_norm)

    try:
        if fmt_norm == "html":
            path.write_text(render_html(report, insights=insights), encoding="utf-8")
        elif fmt_norm == "pdf":
            from business_analyzer.reports.rotacion_pdf import write_rotacion_pdf

            write_rotacion_pdf(report, path, insights=insights)
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
        "demand_mode": mode,
        "path": str(path.resolve()),
        "summary": summary,
        "insights_count": len(insights),
        "message": (
            f"Rotación de Existencias generada — {as_of} ({fmt_norm.upper()})\n"
            f"QUIEBRE={summary.get('QUIEBRE', 0)}, "
            f"MUERTO={summary.get('MUERTO', 0)}, "
            f"SOBRESTOCK={summary.get('SOBRESTOCK', 0)}\n"
            f"Insights={len(insights)} · Archivo: {filename}"
        ),
    }
