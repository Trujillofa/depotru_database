"""CLI for J3System electronic invoice (DIAN) compliance report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_factura_electronica import FacturaElectronicaRunner

REPO_ROOT = Path(__file__).resolve().parents[3]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cumplimiento factura electrónica DIAN (InvEstadoFacturaElectronica)"
    )
    parser.add_argument(
        "--start-date",
        default=(date.today() - timedelta(days=30)).isoformat(),
        help="Start date YYYY-MM-DD (default: 30 days ago)",
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
    summary = report.get("summary") or {}
    lines = [
        "# Factura Electrónica — Cumplimiento DIAN",
        "",
        f"- **Periodo:** {period['start']} a {period['end']}",
        "- **Fuente:** `InvEstadoFacturaElectronica` (J3System)",
        "- **Aceptada:** `Codigo = 200`, `Enviado = 1`, CUFE válido",
        "",
        "## Resumen",
        "",
        f"- **Emitidas:** {int(summary.get('Emitidas', 0)):,}".replace(",", "."),
        f"- **Aceptadas:** {int(summary.get('Aceptadas', 0)):,}".replace(",", "."),
        f"- **Rechazadas:** {int(summary.get('Rechazadas', 0)):,}".replace(",", "."),
        f"- **Tasa aceptación:** {format_pct(float(summary.get('Tasa_Aceptacion_Pct', 0)))}",
        f"- **Tasa rechazo:** {format_pct(float(summary.get('Tasa_Rechazo_Pct', 0)))}",
        f"- **Valor total:** ${float(summary.get('Valor_Total', 0)):,.0f}".replace(
            ",", "."
        ),
        "",
        "## Por tipo de documento",
        "",
        "| Código | Emitidas | Aceptadas | Rechazadas | Aceptación % | Rechazo % |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in report.get("by_documento", []):
        lines.append(
            f"| {row.get('DocumentosCodigo')} | "
            f"{int(row.get('Emitidas', 0))} | "
            f"{int(row.get('Aceptadas', 0))} | "
            f"{int(row.get('Rechazadas', 0))} | "
            f"{format_pct(float(row.get('Tasa_Aceptacion_Pct', 0)))} | "
            f"{format_pct(float(row.get('Tasa_Rechazo_Pct', 0)))} |"
        )

    rechazos = report.get("rechazos", [])
    if rechazos:
        lines.extend(["", "## Rechazos recientes", ""])
        for row in rechazos[:10]:
            lines.append(
                f"- **{row.get('Documento')}** ({row.get('DocumentosCodigo')}) — "
                f"{row.get('FechaFactura')} | código {row.get('Codigo')} | "
                f"${float(row.get('Total', 0)):,.0f}".replace(",", ".")
            )
    else:
        lines.extend(["", "## Rechazos recientes", "", "- Sin rechazos en el periodo."])

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runner = FacturaElectronicaRunner(Database())
    report = runner.build_report(args.start_date, args.end_date)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    markdown = render_markdown(report)
    if args.output:
        out = Path(args.output).resolve()
    else:
        out = REPO_ROOT / "reports" / f"FACTURA_ELECTRONICA_{args.end_date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    print(f"✅ Reporte factura electrónica generado: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
