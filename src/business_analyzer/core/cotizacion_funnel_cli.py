"""CLI for J3System quote-to-invoice funnel report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_cotizacion_funnel import (
    CotizacionFunnelRunner,
    funnel_summary_from_vendor_rows,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Embudo cotización → factura (J3System InvCotiza* → InvVentas)"
    )
    parser.add_argument(
        "--start-date",
        default=(date.today() - timedelta(days=90)).isoformat(),
        help="Start date YYYY-MM-DD (default: 90 days ago)",
    )
    parser.add_argument(
        "--end-date",
        default=date.today().isoformat(),
        help="End date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional markdown output path",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON instead of markdown",
    )
    return parser.parse_args(argv)


def format_pct(value: float) -> str:
    return f"{value:.2f}%".replace(".", ",")


def render_markdown(report: dict) -> str:
    period = report["period"]
    summary = report.get("summary") or funnel_summary_from_vendor_rows(
        report.get("by_vendor", [])
    )
    cot = int(summary.get("Cotizaciones", 0))
    conv = int(summary.get("Convertidas", 0))
    lost = int(summary.get("Perdidas", 0))
    lines = [
        "# Embudo Cotización → Factura (J3System)",
        "",
        f"- **Periodo:** {period['start']} a {period['end']}",
        "- **Enlace:** `InvVentasTotales.NumeroCotiza` = `CT-{NumeroDocumento}`",
        "- **Nota:** No usar join por `VentaID` (reutilización de IDs entre tipos de documento)",
        "",
        "## Resumen",
        "",
        f"- **Cotizaciones:** {cot:,}".replace(",", "."),
        f"- **Convertidas:** {conv:,}".replace(",", "."),
        f"- **Perdidas:** {lost:,}".replace(",", "."),
        f"- **Tasa conversión:** {format_pct(float(summary.get('Tasa_Conversion_Pct', 0)))}",
        f"- **Días promedio conversión:** {float(summary.get('Dias_Promedio_Conversion', 0)):.1f}",
        "",
        "## Por vendedor (top 10 por volumen)",
        "",
        "| Vendedor | Cotizaciones | Convertidas | Perdidas | Tasa % | Días prom. |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in report.get("by_vendor", [])[:10]:
        lines.append(
            f"| {row.get('Vendedor_Nombre')} ({row.get('Vendedor_Codigo')}) | "
            f"{int(row.get('Cotizaciones', 0))} | "
            f"{int(row.get('Convertidas', 0))} | "
            f"{int(row.get('Perdidas', 0))} | "
            f"{format_pct(float(row.get('Tasa_Conversion_Pct', 0)))} | "
            f"{float(row.get('Dias_Promedio_Conversion', 0)):.1f} |"
        )

    lines.extend(["", "## Mayor volumen perdido (top 5)", ""])
    for row in report.get("top_lost_vendors", [])[:5]:
        lines.append(
            f"- {row.get('Vendedor_Nombre')} — "
            f"{int(row.get('Perdidas', 0))} cotizaciones sin factura "
            f"({format_pct(float(row.get('Tasa_Conversion_Pct', 0)))} conversión)"
        )

    low = report.get("low_conversion_vendors", [])
    if low:
        lines.extend(["", "## Baja conversión (≥10 cotizaciones, <20%)", ""])
        for row in low[:5]:
            lines.append(
                f"- {row.get('Vendedor_Nombre')} — "
                f"{format_pct(float(row.get('Tasa_Conversion_Pct', 0)))} "
                f"({int(row.get('Cotizaciones', 0))} cotizaciones)"
            )

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runner = CotizacionFunnelRunner(Database())
    report = runner.build_report(args.start_date, args.end_date)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    markdown = render_markdown(report)
    if args.output:
        out = Path(args.output).resolve()
    else:
        out = REPO_ROOT / "reports" / f"COTIZACION_FUNNEL_{args.end_date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    print(f"✅ Embudo cotización generado: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
