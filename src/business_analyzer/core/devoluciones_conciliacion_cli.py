"""CLI for ERP vs BI returns reconciliation report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_devoluciones_conciliacion import (
    DevolucionesConciliacionRunner,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Conciliación devoluciones ERP (InvDevolucionVentas) vs BI (banco_datos)"
        )
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
        "# Conciliación Devoluciones ERP vs BI",
        "",
        f"- **Periodo:** {period['start']} a {period['end']}",
        "- **ERP:** `InvDevolucionVentas` + `InvDevolucionVentasDetalle` (J3System)",
        "- **BI:** `banco_datos` (Cantidad < 0 o DVE/DVD/DDD/DDT)",
        "",
        "## Resumen",
        "",
        f"- **Unidades ERP:** {int(summary.get('Unidades_ERP', 0)):,}".replace(
            ",", "."
        ),
        f"- **Unidades BI:** {int(summary.get('Unidades_BI', 0)):,}".replace(",", "."),
        f"- **Diferencia:** {int(summary.get('Diferencia_Unidades', 0)):,}".replace(
            ",", "."
        ),
        f"- **Conciliación:** {format_pct(float(summary.get('Conciliacion_Pct', 0)))}",
        f"- **Categorías con brecha:** {int(summary.get('Categorias_Con_Diferencia', 0))}",
        f"- **Tasa devolución validada:** "
        f"{format_pct(float(summary.get('Tasa_Devolucion_Validada_Pct', 0)))}",
        "",
        "## Por tipo de documento",
        "",
        "| Código | ERP | BI | Diferencia |",
        "|---|---:|---:|---:|",
    ]
    for row in report.get("by_documento", []):
        lines.append(
            f"| {row.get('DocumentosCodigo')} | "
            f"{int(row.get('Unidades_ERP', 0))} | "
            f"{int(row.get('Unidades_BI', 0))} | "
            f"{int(row.get('Diferencia_Unidades', 0))} |"
        )

    gaps = report.get("top_gaps", [])
    if gaps:
        lines.extend(["", "## Brechas por categoría (top)", ""])
        for row in gaps[:10]:
            lines.append(
                f"- **{row.get('Categoria')}** — ERP: {int(row.get('Unidades_ERP', 0))}, "
                f"BI: {int(row.get('Unidades_BI', 0))}, "
                f"Δ {int(row.get('Diferencia_Unidades', 0))} "
                f"({format_pct(float(row.get('Diferencia_Pct', 0)))})"
            )

    erosion = report.get("top_margin_erosion", [])
    if erosion:
        lines.extend(["", "## Mayor erosión de margen (devoluciones BI)", ""])
        for row in erosion[:8]:
            lines.append(
                f"- **{row.get('Categoria')}** — impacto margen "
                f"${float(row.get('Impacto_Margen_BI', 0)):,.0f}".replace(",", ".")
                + f", tasa validada {format_pct(float(row.get('Tasa_Devolucion_Validada_Pct', 0)))}"
            )

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runner = DevolucionesConciliacionRunner(Database())
    report = runner.build_report(args.start_date, args.end_date)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    markdown = render_markdown(report)
    if args.output:
        out = Path(args.output).resolve()
    else:
        out = REPO_ROOT / "reports" / f"DEVOLUCIONES_CONCILIACION_{args.end_date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    print(f"✅ Conciliación devoluciones generada: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
