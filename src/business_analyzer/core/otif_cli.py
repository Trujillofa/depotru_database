"""CLI for J3System OTIF (delivery compliance) report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_otif import OtifRunner

REPO_ROOT = Path(__file__).resolve().parents[3]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cumplimiento de entregas OTIF (InvHistoricoEntregas + InvVentas)"
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
        "# Cumplimiento de Entregas (OTIF) — J3System",
        "",
        f"- **Periodo:** {period['start']} a {period['end']}",
        "- **Fuente:** `InvHistoricoEntregas` (Tipo = Entrega)",
        "- **A tiempo:** `FechaEntrega` ≤ `FechaProximaEntrega`",
        "- **Lead time:** días entre `FechaFactura` y fecha de entrega",
        "",
        "## Resumen",
        "",
        f"- **Total entregas:** {int(summary.get('Total_Entregas', 0)):,}".replace(
            ",", "."
        ),
        f"- **A tiempo:** {int(summary.get('Entregas_A_Tiempo', 0)):,}".replace(
            ",", "."
        ),
        f"- **Tarde:** {int(summary.get('Entregas_Tarde', 0)):,}".replace(",", "."),
        f"- **OTIF %:** {format_pct(float(summary.get('OTIF_Pct', 0)))}",
        f"- **Lead time prom.:** {float(summary.get('Lead_Time_Promedio_Dias', 0)):.1f} días",
        f"- **Fill rate %:** {format_pct(float(summary.get('Fill_Rate_Pct', 0)))}",
        "",
        "## Por bodega (peor OTIF primero)",
        "",
        "| Bodega | Entregas | A tiempo | Tarde | OTIF % | Lead prom. | Fill % |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in report.get("by_warehouse", []):
        lines.append(
            f"| {row.get('Almacen_Codigo')} | "
            f"{int(row.get('Total_Entregas', 0))} | "
            f"{int(row.get('Entregas_A_Tiempo', 0))} | "
            f"{int(row.get('Entregas_Tarde', 0))} | "
            f"{format_pct(float(row.get('OTIF_Pct', 0)))} | "
            f"{float(row.get('Lead_Time_Promedio_Dias', 0)):.1f} | "
            f"{format_pct(float(row.get('Fill_Rate_Pct', 0)))} |"
        )

    worst_c = report.get("worst_customers", [])
    if worst_c:
        lines.extend(["", "## Clientes con peor SLA (≥20 entregas)", ""])
        for row in worst_c[:10]:
            lines.append(
                f"- {row.get('Cliente')} — "
                f"{format_pct(float(row.get('OTIF_Pct', 0)))} OTIF "
                f"({int(row.get('Total_Entregas', 0))} entregas, "
                f"lead {float(row.get('Lead_Time_Promedio_Dias', 0)):.1f}d)"
            )

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runner = OtifRunner(Database())
    report = runner.build_report(args.start_date, args.end_date)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    markdown = render_markdown(report)
    if args.output:
        out = Path(args.output).resolve()
    else:
        out = REPO_ROOT / "reports" / f"OTIF_{args.end_date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    print(f"✅ Reporte OTIF generado: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
