"""CLI for J3System accounting (libro mayor / PyG) report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_contabilidad import ContabilidadRunner

REPO_ROOT = Path(__file__).resolve().parents[3]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Contabilidad ERP (ConMovimiento + PUC + centros de costo)"
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


def format_money(value: float) -> str:
    return f"${value:,.0f}".replace(",", ".")


def render_markdown(report: dict) -> str:
    period = report["period"]
    summary = report.get("summary") or {}
    balance_summary = report.get("balance_summary") or {}
    pyg_summary = report.get("pyg_summary") or {}
    conc = report.get("conciliacion_ingresos") or {}
    help_text = report.get("metric_help") or {}
    lines = [
        "# Contabilidad — Libro Mayor J3System",
        "",
        f"- **Periodo:** {period['start']} a {period['end']}",
        "- **Fuente:** `ConMovimiento` + `ConMovimientoDetalle` + `AdmCuentasPuc`",
        "",
        "## Balance — clases 1–3 (saldos acumulados al cierre)",
        "",
        f"_{help_text.get('balance_intro', '')}_",
        "",
        f"- **Activo (clase 1):** "
        f"{format_money(float(balance_summary.get('Activo_Total', 0)))}",
        f"- **Pasivo (clase 2):** "
        f"{format_money(float(balance_summary.get('Pasivo_Total', 0)))}",
        f"- **Patrimonio (clase 3):** "
        f"{format_money(float(balance_summary.get('Patrimonio_Total', 0)))}",
        f"- **Ecuación contable:** "
        f"{'OK' if balance_summary.get('Ecuacion_OK') else 'Revisar'}",
    ]
    for row in report.get("balance_clase", []):
        lines.append(
            f"  - Clase {row.get('Clase_Puc')} {row.get('Tipo_Cuenta')}: "
            f"saldo {format_money(float(row.get('Saldo_Acumulado', 0)))}"
        )
    lines.extend(
        [
            "",
            "## PyG — clases 4–6 (movimientos del periodo)",
            "",
            f"_{help_text.get('pyg_intro', '')}_",
            "",
            f"- **Cuadre (D = C):** {'Sí' if int(summary.get('Cuadre_OK', 0)) else 'No'}",
            f"- **Ingresos operacionales (clase 4):** "
            f"{format_money(float(pyg_summary.get('Ingresos_Creditos', 0)))}",
            f"- **Costos de ventas (clase 6):** "
            f"{format_money(float(pyg_summary.get('Costos_Debitos', 0)))}",
            f"- **Gastos operativos (clase 5):** "
            f"{format_money(float(pyg_summary.get('Gastos_Debitos', 0)))}",
            f"- **Margen bruto contable:** "
            f"{format_money(float(pyg_summary.get('Margen_Bruto_Contable', 0)))} "
            f"({format_pct(float(pyg_summary.get('Margen_Contable_Pct', 0)))})",
            "",
            "## Conciliación ingresos contables vs BI",
            "",
            f"_{help_text.get('conciliacion_ingresos', '')}_",
            "",
            f"- **Ingresos grupo PUC 41:** "
            f"{format_money(float(conc.get('Ingresos_Contables_41', 0)))}",
            f"- **Ventas BI con IVA:** "
            f"{format_money(float(conc.get('Ventas_BI_Con_Iva', 0)))}",
            f"- **% conciliación:** "
            f"{format_pct(float(conc.get('Conciliacion_Ingresos_Pct', 0)))}",
            "",
            "## Gastos por centro de costo (top)",
            "",
            "| Centro | Gastos | Costos | Total |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in report.get("gastos_centro", [])[:12]:
        lines.append(
            f"| {row.get('SubCentroCostoNombre', '').strip()} | "
            f"{format_money(abs(float(row.get('Gastos_Neto', 0))))} | "
            f"{format_money(abs(float(row.get('Costos_Neto', 0))))} | "
            f"{format_money(abs(float(row.get('Total_Gasto_Costo_Neto', 0))))} |"
        )

    lines.extend(["", "## Top cuentas de gasto (clase 5)", ""])
    for row in report.get("top_gastos", [])[:10]:
        lines.append(
            f"- **{row.get('CuentasPucCodigo')}** {row.get('CuentasPucNombre')} — "
            f"{format_money(abs(float(row.get('Saldo_Neto', 0))))}"
        )

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    runner = ContabilidadRunner(Database())
    report = runner.build_report(args.start_date, args.end_date)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 0

    markdown = render_markdown(report)
    if args.output:
        out = Path(args.output).resolve()
    else:
        out = REPO_ROOT / "reports" / f"CONTABILIDAD_{args.end_date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    print(f"✅ Reporte contabilidad generado: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
