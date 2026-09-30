"""Monday cash pack — weekly ops email draft (Phase 3 / issue #65).

Combines existing cartera aging, negative-margin / SIKA SKU alert, and the
weekly KPI board into one Spanish (Colombian) email-ready artifact.

Default delivery is a local HTML + ``.eml`` draft. Nothing is sent unless
``--send`` is passed explicitly. SQL used by live loaders is read-only and
reuses existing cartera / manager-report / KPI-pack queries.
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import smtplib
import ssl
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from email.message import EmailMessage
from html import escape
from pathlib import Path
from typing import Any, Callable, Mapping, Optional, Sequence

from business_analyzer.core.config import Settings, get_settings
from depotru_kernel.documents import CANONICAL_EXCLUDED_DOCUMENT_CODES

CarteraLoader = Callable[[str, int], Mapping[str, Any]]
SalesLoader = Callable[[str, str], Mapping[str, Any]]
KpiWriter = Callable[[str, str, str], Path]
AttachmentWriter = Callable[[Mapping[str, Any], Path], list[Path]]

DEFAULT_TOP_N = 15
DRAFT_FROM = "depotru-monday-cash@localhost"
DRAFT_TO = "preview@localhost"

logger = logging.getLogger(__name__)

_FORMAT_NUMBER = None


def format_number(value: Any, column_name: str = "") -> str:
    """Load ``ai.formatting.format_number`` without importing ``ai.__init__``.

    ``business_analyzer.ai`` hydrates API keys on import; the Monday pack must
    stay runnable for ``--synthetic`` drafts without AI secrets.

    Currency sign placement is ``-$250.000`` (minus before ``$``), matching
    the digits from ``format_number``.
    """
    global _FORMAT_NUMBER
    if _FORMAT_NUMBER is None:
        path = Path(__file__).resolve().parents[1] / "ai" / "formatting.py"
        spec = importlib.util.spec_from_file_location(
            "depotru_formatting_standalone", path
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"No se pudo cargar {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _FORMAT_NUMBER = module.format_number
    text = _FORMAT_NUMBER(value, column_name)
    if text.startswith("$-"):
        return "-$" + text[2:]
    return text


@dataclass
class OverdueRow:
    customer_name: str
    overdue_amount: float
    days_overdue: int
    seller_name: str
    total: float


@dataclass
class NegativeMarginSku:
    sku: str
    product_name: str
    revenue: float
    cost: float
    profit: float
    margin_pct: float
    is_sika: bool


@dataclass
class KpiHighlights:
    week_start: date
    week_end: date
    revenue_with_iva: float
    revenue_without_iva: float
    cost: float
    gross_profit: float
    gross_margin_pct: float
    order_count: int


@dataclass
class MondayCashPack:
    run_date: date
    as_of_date: str
    overdue: list[OverdueRow]
    cartera_summary: dict[str, Any]
    negative_skus: list[NegativeMarginSku]
    kpi: KpiHighlights
    attachments: list[Path] = field(default_factory=list)


@dataclass(frozen=True)
class DraftResult:
    html_path: Path
    eml_path: Path


def last_completed_week(run_date: date) -> tuple[date, date]:
    """Previous completed Mon–Sun week (same window as run_weekly_kpi_board)."""
    current_week_monday = run_date - timedelta(days=run_date.weekday())
    previous_week_sunday = current_week_monday - timedelta(days=1)
    previous_week_monday = previous_week_sunday - timedelta(days=6)
    return previous_week_monday, previous_week_sunday


def rank_overdue_receivables(
    report: Mapping[str, Any],
    top_n: int = DEFAULT_TOP_N,
) -> list[OverdueRow]:
    """Rank overdue AR using the existing cartera ``top_overdue`` payload."""
    rows: Sequence[Mapping[str, Any]] | None = report.get("top_overdue")
    if rows is None:
        from business_analyzer.core.cartera_aging import top_overdue

        rows = top_overdue(report.get("clients") or [], top_n=top_n)
    out: list[OverdueRow] = []
    for row in list(rows)[: max(0, int(top_n))]:
        out.append(
            OverdueRow(
                customer_name=str(row.get("cliente_razon_social") or ""),
                overdue_amount=float(row.get("vencido") or 0),
                days_overdue=int(row.get("dias_vencidos") or 0),
                seller_name=str(row.get("vendedor_nombre") or ""),
                total=float(row.get("total") or 0),
            )
        )
    return out


def is_sika_product(row: Mapping[str, Any]) -> bool:
    blob = " ".join(
        str(row.get(key) or "")
        for key in (
            "product_name",
            "sku",
            "proveedor",
            "vendor_name",
            "marca",
            "marca_name",
        )
    ).lower()
    return "sika" in blob


def select_negative_margin_skus(
    product_rows: Sequence[Mapping[str, Any]],
    top_n: int = DEFAULT_TOP_N,
) -> list[NegativeMarginSku]:
    """SKUs with negative margin, ranked by loss; SIKA flagged by name/vendor."""
    selected: list[NegativeMarginSku] = []
    for row in product_rows:
        revenue = float(row.get("revenue") or row.get("total_revenue") or 0)
        cost = float(row.get("cost") or row.get("total_cost") or 0)
        profit = revenue - cost
        margin_pct = (profit / revenue * 100.0) if revenue else 0.0
        if profit >= 0 and margin_pct >= 0:
            continue
        selected.append(
            NegativeMarginSku(
                sku=str(row.get("sku") or ""),
                product_name=str(row.get("product_name") or ""),
                revenue=revenue,
                cost=cost,
                profit=profit,
                margin_pct=margin_pct,
                is_sika=is_sika_product(row),
            )
        )
    selected.sort(key=lambda item: (item.profit, item.margin_pct))
    return selected[: max(0, int(top_n))]


def normalize_kpi_summary(row: Mapping[str, Any]) -> dict[str, Any]:
    """Accept manager ``summary_from_sql`` output or the raw SQL summary row."""
    if "total_revenue_with_iva" in row:
        return dict(row)
    total_with_iva = float(row.get("total_with_iva") or 0)
    total_without_iva = float(row.get("total_without_iva") or 0)
    total_cost = float(row.get("total_cost") or 0)
    order_count = int(float(row.get("order_count") or 0))
    gross_profit = total_without_iva - total_cost
    margin = (gross_profit / total_without_iva * 100.0) if total_without_iva else 0.0
    return {
        "total_revenue_with_iva": round(total_with_iva, 2),
        "total_revenue_without_iva": round(total_without_iva, 2),
        "total_cost": round(total_cost, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_margin_pct": round(margin, 2),
        "order_count": order_count,
    }


def kpi_highlights_from_summary(
    summary: Mapping[str, Any],
    *,
    week_start: date,
    week_end: date,
) -> KpiHighlights:
    """North-star week KPIs from manager-report summary keys."""
    normalized = normalize_kpi_summary(summary)
    return KpiHighlights(
        week_start=week_start,
        week_end=week_end,
        revenue_with_iva=float(normalized.get("total_revenue_with_iva") or 0),
        revenue_without_iva=float(normalized.get("total_revenue_without_iva") or 0),
        cost=float(normalized.get("total_cost") or 0),
        gross_profit=float(normalized.get("gross_profit") or 0),
        gross_margin_pct=float(normalized.get("gross_margin_pct") or 0),
        order_count=int(normalized.get("order_count") or 0),
    )


def format_pack_numbers(
    overdue: Sequence[OverdueRow],
    skus: Sequence[NegativeMarginSku],
) -> dict[str, list[dict[str, str]]]:
    """Colombian display strings via ``format_number`` (no ad-hoc formatting)."""
    return {
        "overdue": [
            {
                "amount": format_number(row.overdue_amount, "TotalMasIva"),
                "total": format_number(row.total, "TotalMasIva"),
                "days": format_number(row.days_overdue, "Cantidad"),
            }
            for row in overdue
        ],
        "skus": [
            {
                "revenue": format_number(row.revenue, "TotalSinIva"),
                "cost": format_number(row.cost, "ValorCosto"),
                "profit": format_number(row.profit, "Ganancia"),
                "margin": format_number(row.margin_pct, "Margen"),
            }
            for row in skus
        ],
    }


def build_pack(
    *,
    run_date: date,
    as_of_date: str,
    cartera_report: Mapping[str, Any],
    product_rows: Sequence[Mapping[str, Any]],
    kpi_summary: Mapping[str, Any],
    week_start: date,
    week_end: date,
    attachments: Optional[list[Path]] = None,
    top_n: int = DEFAULT_TOP_N,
) -> MondayCashPack:
    return MondayCashPack(
        run_date=run_date,
        as_of_date=as_of_date,
        overdue=rank_overdue_receivables(cartera_report, top_n=top_n),
        cartera_summary=dict(cartera_report.get("summary") or {}),
        negative_skus=select_negative_margin_skus(product_rows, top_n=top_n),
        kpi=kpi_highlights_from_summary(
            kpi_summary, week_start=week_start, week_end=week_end
        ),
        attachments=list(attachments or []),
    )


def _synthetic_cartera_rows() -> list[dict[str, Any]]:
    return [
        {
            "cliente_uid": 1,
            "cliente_nit": "9001",
            "cliente_razon_social": "Cliente Alfa",
            "cliente_ciudad": "Neiva",
            "cliente_departamento": "Huila",
            "vendedor_nombre": "Ana Demo",
            "corriente": 0,
            "vencido": 2_500_000,
            "vencido_30": 0,
            "vencido_60": 0,
            "vencido_90": 0,
            "vencido_120": 2_500_000,
            "vencido_360": 0,
            "vencido_superior": 0,
            "total": 2_500_000,
            "dias_vencidos": 110,
            "cliente_cupo": 3_000_000,
            "fecha_carga": "2026-09-27 08:00:00",
        },
        {
            "cliente_uid": 2,
            "cliente_nit": "9002",
            "cliente_razon_social": "Cliente Beta",
            "cliente_ciudad": "Florencia",
            "cliente_departamento": "Caquetá",
            "vendedor_nombre": "Luis Demo",
            "corriente": 100_000,
            "vencido": 80_000,
            "vencido_30": 80_000,
            "vencido_60": 0,
            "vencido_90": 0,
            "vencido_120": 0,
            "vencido_360": 0,
            "vencido_superior": 0,
            "total": 180_000,
            "dias_vencidos": 18,
            "cliente_cupo": 400_000,
            "fecha_carga": "2026-09-27 08:00:00",
        },
    ]


def _synthetic_product_rows() -> list[dict[str, Any]]:
    return [
        {
            "product_name": "Impermeabilizante Demo SIKA",
            "sku": "SKU-DEMO-SIKA-1",
            "revenue": 1_000_000,
            "cost": 1_250_000,
            "quantity": 10,
            "proveedor": "SIKA COLOMBIA",
        },
        {
            "product_name": "Broca HSS 8mm Demo",
            "sku": "SKU-DEMO-002",
            "revenue": 400_000,
            "cost": 480_000,
            "quantity": 8,
        },
        {
            "product_name": "Cemento gris Demo",
            "sku": "SKU-DEMO-003",
            "revenue": 800_000,
            "cost": 500_000,
            "quantity": 20,
        },
    ]


def _synthetic_cartera_report(as_of: str, top_n: int) -> dict[str, Any]:
    """Minimal cartera payload for dry-run (no ``cartera_aging`` import)."""
    rows = _synthetic_cartera_rows()
    ranked = sorted(
        rows,
        key=lambda row: (
            -float(row["vencido"]),
            -int(row["dias_vencidos"]),
            -float(row["total"]),
        ),
    )[: max(0, int(top_n))]
    total = sum(float(row["total"]) for row in rows)
    vencido = sum(float(row["vencido"]) for row in rows)
    pct = (vencido / total * 100.0) if total else 0.0
    return {
        "as_of_date": as_of,
        "summary": {
            "Cartera_Total": total,
            "Cartera_Vencida": vencido,
            "Cartera_Vencida_Pct": pct,
        },
        "top_overdue": ranked,
    }


def build_synthetic_pack(
    *,
    run_date: date,
    top_n: int = DEFAULT_TOP_N,
) -> MondayCashPack:
    """Deterministic pack for local dry-run (no database, no real customers)."""
    week_start, week_end = last_completed_week(run_date)
    as_of = week_end.isoformat()
    report = _synthetic_cartera_report(as_of, top_n)
    kpi_summary = normalize_kpi_summary(
        {
            "total_with_iva": 12_345_678,
            "total_without_iva": 10_000_000,
            "total_cost": 7_000_000,
            "order_count": 40,
        }
    )
    return build_pack(
        run_date=run_date,
        as_of_date=as_of,
        cartera_report=report,
        product_rows=_synthetic_product_rows(),
        kpi_summary=kpi_summary,
        week_start=week_start,
        week_end=week_end,
        top_n=top_n,
    )


def default_cartera_loader(as_of_date: str, top_n: int) -> Mapping[str, Any]:
    from business_analyzer.core.cartera_aging import CarteraAgingRunner

    return CarteraAgingRunner(top_n=top_n).build_report(as_of_date)


def default_sales_loader(start: str, end: str) -> Mapping[str, Any]:
    from business_analyzer.analysis.manager_report.queries import SalesQueryRunner

    year = int(start[:4])
    month = int(start[5:7])
    return SalesQueryRunner(start, end, year, month=month).fetch_sql_aggregations()


def default_kpi_writer(start: str, end: str, output: str) -> Path:
    generate = _load_script_attr(
        "scripts/utils/generate_kpi_control_board.py",
        "generate_kpi_control_board",
    )
    return Path(generate(start_date=start, end_date=end, output=output))


def default_attachment_writer(
    report: Mapping[str, Any], output_dir: Path
) -> list[Path]:
    """Write existing cartera HTML/PDF from an already-built report dict."""
    from business_analyzer.reports.cartera_html import build_insights, render_html

    as_of = str(report.get("as_of_date") or "sin-fecha")
    insights = build_insights(report)
    html_path = output_dir / f"CARTERA_AGING_{as_of}.html"
    html_path.write_text(render_html(report, insights=insights), encoding="utf-8")
    paths = [html_path]
    try:
        from business_analyzer.reports.cartera_pdf import write_cartera_pdf

        pdf_path = output_dir / f"CARTERA_AGING_{as_of}.pdf"
        write_cartera_pdf(report, pdf_path, insights=insights)
        paths.append(pdf_path)
    except (OSError, RuntimeError, ValueError, ImportError) as exc:
        # Optional PDF; the HTML draft is enough if ReportLab is missing.
        logger.warning("No se adjuntó el PDF de cartera: %s", exc)
    return paths


def build_live_pack(
    *,
    run_date: date,
    as_of_date: str,
    top_n: int,
    output_dir: Path,
    cartera_loader: Optional[CarteraLoader] = None,
    sales_loader: Optional[SalesLoader] = None,
    kpi_writer: Optional[KpiWriter] = None,
    attachment_writer: Optional[AttachmentWriter] = None,
) -> MondayCashPack:
    week_start, week_end = last_completed_week(run_date)
    report = (cartera_loader or default_cartera_loader)(as_of_date, top_n)
    sales = (sales_loader or default_sales_loader)(
        week_start.isoformat(), week_end.isoformat()
    )
    kpi_summary = normalize_kpi_summary(sales.get("summary") or {})
    attachments: list[Path] = []
    writer = attachment_writer or default_attachment_writer
    attachments.extend(writer(report, output_dir))
    year, week, _ = week_end.isocalendar()
    kpi_path = output_dir / f"KPI_CONTROL_BOARD_{year}_W{week:02d}.md"
    try:
        written = (kpi_writer or default_kpi_writer)(
            week_start.isoformat(), week_end.isoformat(), str(kpi_path)
        )
        attachments.append(Path(written))
    except (OSError, RuntimeError, ValueError, ImportError) as exc:
        # KPI markdown is optional; the email body still has north-star numbers.
        logger.warning("No se adjuntó el tablero KPI semanal: %s", exc)
    return build_pack(
        run_date=run_date,
        as_of_date=as_of_date,
        cartera_report=report,
        product_rows=sales.get("product_margins") or [],
        kpi_summary=kpi_summary,
        week_start=week_start,
        week_end=week_end,
        attachments=attachments,
        top_n=top_n,
    )


def render_email_html(pack: MondayCashPack) -> str:
    excluded = ", ".join(CANONICAL_EXCLUDED_DOCUMENT_CODES)
    money = format_pack_numbers(pack.overdue, pack.negative_skus)
    cartera_total = format_number(
        pack.cartera_summary.get("Cartera_Total"), "TotalMasIva"
    )
    cartera_vencida = format_number(
        pack.cartera_summary.get("Cartera_Vencida"), "TotalMasIva"
    )
    cartera_pct = format_number(
        pack.cartera_summary.get("Cartera_Vencida_Pct"), "Margen"
    )
    kpi_rev = format_number(pack.kpi.revenue_with_iva, "TotalMasIva")
    kpi_profit = format_number(pack.kpi.gross_profit, "Ganancia")
    kpi_margin = format_number(pack.kpi.gross_margin_pct, "Margen")
    kpi_orders = format_number(pack.kpi.order_count, "Cantidad")

    overdue_rows = []
    for overdue, fmt in zip(pack.overdue, money["overdue"]):
        overdue_rows.append(
            "<tr>"
            f"<td>{escape(overdue.customer_name)}</td>"
            f"<td>{escape(overdue.seller_name)}</td>"
            f"<td>{escape(fmt['amount'])}</td>"
            f"<td>{escape(fmt['days'])}</td>"
            f"<td>{escape(fmt['total'])}</td>"
            "</tr>"
        )
    if not overdue_rows:
        overdue_rows.append(
            "<tr><td colspan='5'>Sin cuentas vencidas en el recorte.</td></tr>"
        )

    sku_rows = []
    for sku, fmt in zip(pack.negative_skus, money["skus"]):
        flag = "Sí" if sku.is_sika else "No"
        sku_rows.append(
            "<tr>"
            f"<td>{escape(sku.sku)}</td>"
            f"<td>{escape(sku.product_name)}</td>"
            f"<td>{escape(fmt['profit'])}</td>"
            f"<td>{escape(fmt['margin'])}</td>"
            f"<td>{escape(flag)}</td>"
            "</tr>"
        )
    if not sku_rows:
        sku_rows.append(
            "<tr><td colspan='5'>Sin SKUs con margen negativo en la semana.</td></tr>"
        )

    attach_items = (
        "".join(
            f"<li>{escape(Path(path).name)}</li>"
            for path in pack.attachments
            if path and Path(path).is_file()
        )
        or "<li>Sin adjuntos adicionales.</li>"
    )

    return f"""<!DOCTYPE html>
<html lang="es-CO">
<head>
  <meta charset="utf-8">
  <title>Paquete de caja — lunes {escape(pack.run_date.isoformat())}</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; color: #1f2933; margin: 24px; }}
    h1, h2 {{ color: #102a43; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0 24px; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 8px; text-align: left; }}
    th {{ background: #f0f4f8; }}
    .note {{ background: #fff8e1; padding: 12px; border-left: 4px solid #f0b429; }}
  </style>
</head>
<body>
  <h1>Paquete de caja — lunes {escape(pack.run_date.isoformat())}</h1>
  <p class="note">
    Este es un <strong>borrador</strong> para revisión. Por defecto
    <strong>no se envía</strong> correo. Use <code>--send</code> solo de forma
    explícita.
  </p>
  <p>
    Fecha de cartera: {escape(pack.as_of_date)}. Semana KPI:
    {escape(pack.kpi.week_start.isoformat())} a
    {escape(pack.kpi.week_end.isoformat())}.
  </p>

  <h2>1) Cuentas por cobrar vencidas</h2>
  <p>
    Cartera total {escape(cartera_total)} · vencida {escape(cartera_vencida)}
    ({escape(cartera_pct)}). Ranking por monto y días de mora
    (código existente de cartera / aging).
  </p>
  <table>
    <thead>
      <tr><th>Cliente</th><th>Vendedor</th><th>Vencido</th><th>Días</th><th>Total</th></tr>
    </thead>
    <tbody>
      {''.join(overdue_rows)}
    </tbody>
  </table>

  <h2>2) SKUs con margen negativo / SIKA</h2>
  <p>
    Alerta de margen negativo sobre las agregaciones de producto del informe
    gerencial (sin SQL nuevo). Se marca SIKA cuando el nombre, SKU o proveedor
    lo indica. El convertidor legado
    <code>scripts/analysis/generate_sika_report.py</code> se puede adjuntar
    con <code>--sika-json</code>.
  </p>
  <table>
    <thead>
      <tr><th>SKU</th><th>Producto</th><th>Ganancia</th><th>Margen</th><th>SIKA</th></tr>
    </thead>
    <tbody>
      {''.join(sku_rows)}
    </tbody>
  </table>

  <h2>3) Tablero KPI semanal</h2>
  <p>
    Facturación con IVA {escape(kpi_rev)} · ganancia bruta {escape(kpi_profit)}
    · margen {escape(kpi_margin)} · documentos {escape(kpi_orders)}.
    El tablero completo reutiliza las consultas semanales / gerenciales
    existentes y va como adjunto cuando se genera.
  </p>
  <h3>Adjuntos</h3>
  <ul>{attach_items}</ul>
  <p>
    Consultas de ventas en <code>banco_datos</code> excluyen
    <code>DocumentosCodigo NOT IN ({escape(excluded)})</code>.
    Solo lectura; no hay SQL de escritura.
  </p>
</body>
</html>
"""


def render_email_text(pack: MondayCashPack) -> str:
    money = format_pack_numbers(pack.overdue, pack.negative_skus)
    lines = [
        f"Paquete de caja — lunes {pack.run_date.isoformat()}",
        "Borrador: por defecto no se envía correo.",
        "",
        "Cuentas por cobrar vencidas:",
    ]
    for overdue, fmt in zip(pack.overdue, money["overdue"]):
        lines.append(f"- {overdue.customer_name}: {fmt['amount']} ({fmt['days']} días)")
    lines.extend(["", "SKUs con margen negativo / SIKA:"])
    for sku, fmt in zip(pack.negative_skus, money["skus"]):
        flag = "SIKA" if sku.is_sika else ""
        lines.append(f"- {sku.sku} {sku.product_name}: {fmt['margin']} {flag}")
    lines.extend(
        [
            "",
            (
                f"KPI semana {pack.kpi.week_start.isoformat()} a "
                f"{pack.kpi.week_end.isoformat()}: "
                f"{format_number(pack.kpi.revenue_with_iva, 'TotalMasIva')} "
                f"margen {format_number(pack.kpi.gross_margin_pct, 'Margen')}"
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def write_draft(
    pack: MondayCashPack,
    output_dir: Path,
    settings: Optional[Settings] = None,
) -> DraftResult:
    """Write HTML + RFC 822 ``.eml`` preview. Does not send mail."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cfg = settings or get_settings()
    stem = f"monday_cash_pack_{pack.run_date.isoformat()}"
    html_path = output_dir / f"{stem}.html"
    eml_path = output_dir / f"{stem}.eml"
    html = render_email_html(pack)
    html_path.write_text(html, encoding="utf-8")

    msg = EmailMessage()
    msg["Subject"] = f"Paquete de caja — lunes {pack.run_date.isoformat()}"
    msg["From"] = cfg.MAIL_FROM or DRAFT_FROM
    msg["To"] = cfg.MAIL_TO or DRAFT_TO
    msg.set_content(render_email_text(pack))
    msg.add_alternative(html, subtype="html")
    for path in pack.attachments:
        attachment = Path(path)
        if not attachment.is_file():
            continue
        msg.add_attachment(
            attachment.read_bytes(),
            maintype="application",
            subtype="octet-stream",
            filename=attachment.name,
        )
    eml_path.write_bytes(msg.as_bytes())
    return DraftResult(html_path=html_path, eml_path=eml_path)


def send_draft(eml_path: Path, settings: Optional[Settings] = None) -> None:
    """Send a previously written ``.eml``. Requires SMTP_* / MAIL_* Settings."""
    cfg = settings or get_settings()
    host = (cfg.SMTP_HOST or "").strip()
    mail_to = (cfg.MAIL_TO or "").strip()
    if not host:
        raise RuntimeError(
            "SMTP_HOST no está configurado. El paquete no se envió. "
            "Revise el borrador .eml o configure SMTP_* en Settings."
        )
    if not mail_to:
        raise RuntimeError("MAIL_TO no está configurado. El paquete no se envió.")
    raw = Path(eml_path).read_bytes()
    recipients = [part.strip() for part in mail_to.split(",") if part.strip()]
    from_addr = (cfg.MAIL_FROM or cfg.SMTP_USER or DRAFT_FROM).strip()
    with smtplib.SMTP(host, int(cfg.SMTP_PORT), timeout=30) as smtp:  # nosec B323
        if cfg.SMTP_USE_TLS:
            smtp.starttls(context=ssl.create_default_context())
        if cfg.SMTP_USER:
            smtp.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD or "")
        smtp.sendmail(from_addr, recipients, raw)


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "scripts" / "analysis" / "generate_sika_report.py"
        if candidate.is_file():
            return parent
    return here.parents[3]


def _load_script_attr(relative: str, attr: str) -> Any:
    path = _repo_root() / relative
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, attr)


def render_sika_markdown(json_path: Path, output_path: Path) -> Path:
    """Reuse the existing SIKA JSON→Markdown converter without changing it."""
    generate_report = _load_script_attr(
        "scripts/analysis/generate_sika_report.py", "generate_report"
    )
    generate_report(json_path=str(json_path), output_path=str(output_path))
    return Path(output_path)


def schedule_line() -> str:
    return (
        "# Opt-in. Mondays 08:45 America/Bogota. Draft only — do not add --send.\n"
        "CRON_TZ=America/Bogota\n"
        "45 8 * * 1 "
        "cd /path/to/depotru_database && PYTHONPATH=src "
        "python scripts/reports/run_monday_cash_pack.py "
        ">> ~/business_reports/monday_cash_pack.log 2>&1"
    )


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Paquete de caja del lunes: cartera vencida, margen negativo/SIKA "
            "y tablero KPI semanal. Por defecto solo escribe un borrador."
        )
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Dry-run with synthetic fixtures (no database).",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Send the draft via SMTP Settings. Off by default.",
    )
    parser.add_argument(
        "--output-dir",
        default="",
        help="Directory for HTML/.eml drafts (default: OUTPUT_DIR/monday_cash_pack).",
    )
    parser.add_argument(
        "--run-date",
        default="",
        help="Reference date, ISO 8601 YYYY-MM-DD.",
    )
    parser.add_argument(
        "--as-of-date",
        default="",
        help="Cartera as-of date, ISO 8601 YYYY-MM-DD (default: week end).",
    )
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    parser.add_argument(
        "--sika-json",
        default="",
        help="Optional existing SIKA analysis JSON for generate_sika_report.py.",
    )
    parser.add_argument(
        "--print-schedule",
        action="store_true",
        help="Print an opt-in cron line (America/Bogota) and exit.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    if args.print_schedule:
        print(schedule_line())
        return 0

    run_date = date.fromisoformat(args.run_date) if args.run_date else date.today()
    week_end = last_completed_week(run_date)[1]
    as_of = args.as_of_date or week_end.isoformat()
    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser()
    else:
        from business_analyzer.core.config import Config

        output_dir = Config.ensure_output_dir() / "monday_cash_pack"
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.synthetic:
        pack = build_synthetic_pack(run_date=run_date, top_n=args.top_n)
    else:
        pack = build_live_pack(
            run_date=run_date,
            as_of_date=as_of,
            top_n=args.top_n,
            output_dir=output_dir,
        )

    if args.sika_json:
        sika_out = output_dir / "REPORTE_SIKA_ESPANOL.md"
        pack.attachments.append(render_sika_markdown(Path(args.sika_json), sika_out))

    result = write_draft(pack, output_dir)
    print(f"Borrador HTML: {result.html_path}")
    print(f"Borrador EML: {result.eml_path}")
    if not args.send:
        print("Modo borrador: no se envió correo (use --send explícitamente).")
        return 0
    try:
        send_draft(result.eml_path)
    except (OSError, RuntimeError, ValueError, smtplib.SMTPException) as exc:
        print(f"❌ No se envió el correo: {exc}", file=sys.stderr)
        return 1
    print("Correo enviado (--send).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
