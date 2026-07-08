"""CLI for critical inventory and stock-break report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_critical_inventory import CriticalInventoryRunner

REPO_ROOT = Path(__file__).resolve().parents[3]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Inventario crítico y quiebres de stock "
            "(InvDetalleExistencias + velocidad banco_datos 90d)"
        )
    )
    parser.add_argument(
        "--as-of-date",
        default=date.today().isoformat(),
        help="Reference date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--velocity-days",
        type=int,
        default=90,
        help="Sales velocity window in days (default: 90)",
    )
    parser.add_argument(
        "--low-threshold",
        type=int,
        default=10,
        help="Low stock alert threshold when StockMinimo is zero (default: 10)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=50,
        help="Max critical SKUs to return (default: 50)",
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
    return f"{value:.1f}".replace(".", ",")


def render_markdown(report: dict) -> str:
    summary = report.get("summary") or {}
    lines = [
        "# Inventario Crítico y Quiebres de Stock",
        "",
        f"- **Fecha referencia:** {report['as_of_date']}",
        f"- **Ventana velocidad:** {report.get('velocity_days', 90)} días",
        "- **Fuentes:** `InvDetalleExistencias` (J3System) + `banco_datos` (SmartBusiness)",
        "- **Cobertura (días):** `SaldoActual / venta_diaria_promedio`",
        "",
        "## Resumen",
        "",
        f"- **SKUs críticos (top {len(report.get('critical_skus', []))}):** "
        f"{int(summary.get('SKUs_Criticos', 0)):,}".replace(",", "."),
        f"- **Quiebre <7 días cobertura:** {int(summary.get('SKUs_Quiebre_7d', 0)):,}".replace(
            ",", "."
        ),
        f"- **Stock ≤10 unidades:** {int(summary.get('SKUs_Stock_Bajo', 0)):,}".replace(
            ",", "."
        ),
        f"- **Promedio días cobertura:** "
        f"{float(summary.get('Promedio_Dias_Cobertura', 0)):.1f}",
        "",
        "## Top SKUs críticos (menor cobertura primero)",
        "",
        "| SKU | Producto | Bodega | Stock | Venta 90d | Días cob. | Prioridad |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for row in report.get("critical_skus", [])[:25]:
        dias = row.get("Dias_Cobertura")
        dias_txt = f"{float(dias):.1f}" if dias is not None else "—"
        lines.append(
            f"| {row.get('SKU')} | {row.get('Producto', '')[:40]} | "
            f"{row.get('AlmacenCodigo')} | "
            f"{float(row.get('Saldo_Actual', 0)):.0f} | "
            f"{float(row.get('Cantidad_90d', 0)):.0f} | "
            f"{dias_txt} | {row.get('Prioridad')} |"
        )

    by_wh = report.get("by_warehouse", [])
    if by_wh:
        lines.extend(["", "## Por bodega", ""])
        for row in by_wh[:10]:
            prom = row.get("Promedio_Dias_Cobertura")
            prom_txt = f"{float(prom):.1f}" if prom is not None else "—"
            lines.append(
                f"- **{row.get('AlmacenCodigo')}** ({row.get('AlmacenNombre')}): "
                f"{int(row.get('SKUs_Criticos', 0))} SKUs críticos, "
                f"{int(row.get('SKUs_Quiebre_7d', 0))} quiebre <7d, "
                f"prom. cobertura {prom_txt} días"
            )

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runner = CriticalInventoryRunner(
        Database(),
        velocity_days=args.velocity_days,
        low_stock_threshold=args.low_threshold,
        top_n=args.top_n,
    )
    report = runner.build_report(args.as_of_date)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    markdown = render_markdown(report)
    if args.output:
        out = Path(args.output).resolve()
    else:
        out = REPO_ROOT / "reports" / f"CRITICAL_INVENTORY_{args.as_of_date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    print(f"✅ Inventario crítico generado: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
