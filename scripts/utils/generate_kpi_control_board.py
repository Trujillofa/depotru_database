#!/usr/bin/env python3
"""
Generate a weekly KPI control board from the SQL KPI pack.

Reads query blocks from:
  scripts/analysis/kpi_sql_pack.sql.template

Writes markdown board to:
  reports/KPI_CONTROL_BOARD_<year>_W<week>.md

Environment variables required:
  DB_SERVER, DB_USER, DB_PASSWORD
Optional:
  DB_PORT (default 1433), DB_NAME (default SmartBusiness)
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List

import pymssql

ROOT_DIR = Path(__file__).resolve().parents[2]
SQL_PACK_PATH = ROOT_DIR / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
OUTPUT_DIR = ROOT_DIR / "reports"

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT_DIR / ".env")
except ImportError:
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate weekly KPI control board markdown from SQL pack"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default=(date.today() - timedelta(days=90)).isoformat(),
        help="Start date (YYYY-MM-DD). Default: 90 days ago.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=date.today().isoformat(),
        help="End date (YYYY-MM-DD). Default: today.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional custom output markdown path.",
    )
    return parser.parse_args()


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def get_connection() -> pymssql.Connection:
    server = require_env("DB_SERVER")
    user = require_env("DB_USER")
    password = require_env("DB_PASSWORD")
    database = os.getenv("DB_NAME", "SmartBusiness")
    port = os.getenv("DB_PORT", "1433")

    return pymssql.connect(
        server=server,
        user=user,
        password=password,
        database=database,
        port=port,
        login_timeout=30,
        timeout=180,
    )


def to_native(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def load_query_blocks(sql_path: Path) -> Dict[str, str]:
    content = sql_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"/\*\s*Q(?P<num>\d+)\)\s*.*?\*/\s*(?P<sql>.*?)(?=(?:/\*\s*Q\d+\)|\Z))",
        re.DOTALL,
    )

    blocks: Dict[str, str] = {}
    for match in pattern.finditer(content):
        number = match.group("num")
        sql = match.group("sql").strip()
        blocks[f"Q{number}"] = sql

    required = {f"Q{i}" for i in range(1, 9)}
    missing = sorted(required - set(blocks.keys()))
    if missing:
        raise ValueError(f"Missing query blocks in SQL pack: {', '.join(missing)}")

    return blocks


def render_query(sql: str, start_date: str, end_date: str) -> str:
    rendered = sql.replace("@start_date", f"'{start_date}'")
    rendered = rendered.replace("@end_date", f"'{end_date}'")
    return rendered


def execute_query(conn: pymssql.Connection, sql: str) -> List[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute(sql)
    if cursor.description is None:
        cursor.close()
        raise ValueError("Query did not return a result set")
    columns = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    cursor.close()

    result: List[Dict[str, Any]] = []
    for row in rows:
        parsed = {columns[i]: to_native(row[i]) for i in range(len(columns))}
        result.append(parsed)
    return result


def mean(values: List[float]) -> float:
    valid = [v for v in values if v is not None]
    if not valid:
        return 0.0
    return sum(valid) / len(valid)


def as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def format_currency(value: float, decimals: int = 0) -> str:
    if decimals == 0:
        return f"${value:,.0f}".replace(",", ".")
    return (
        f"${value:,.{decimals}f}".replace(",", "TMP")
        .replace(".", ",")
        .replace("TMP", ".")
    )


def format_pct(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}%".replace(".", ",")


def format_delta(value: float, kind: str) -> str:
    if kind == "pp":
        return f"{value:+.2f} pp".replace(".", ",")
    return format_pct(value, 2) if value else "0,00%"


def status_higher_is_better(current: float, target: float) -> str:
    if current >= target:
        return "🟢"
    if current >= target * 0.97:
        return "🟡"
    return "🔴"


def status_lower_is_better(current: float, target: float) -> str:
    if current <= target:
        return "🟢"
    if current <= target * 1.03:
        return "🟡"
    return "🔴"


def compute_scorecard(
    results: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Dict[str, Any]]:
    q1 = sorted(
        results["Q1"],
        key=lambda r: (as_float(r.get("Anio")), as_float(r.get("Semana_ISO"))),
    )
    q4 = results["Q4"]

    if not q1:
        raise ValueError("Q1 returned no data; cannot compute scorecard")

    current = q1[-1]
    baseline_rows = q1[-5:-1] if len(q1) >= 5 else q1[:-1]
    if not baseline_rows:
        baseline_rows = q1

    baseline_margin = mean([as_float(r.get("Margen_Bruto_Pct")) for r in baseline_rows])
    baseline_profit = mean([as_float(r.get("Ganancia_Bruta")) for r in baseline_rows])
    baseline_ticket = mean([as_float(r.get("Ticket_Promedio")) for r in baseline_rows])

    current_margin = as_float(current.get("Margen_Bruto_Pct"))
    current_profit = as_float(current.get("Ganancia_Bruta"))
    current_ticket = as_float(current.get("Ticket_Promedio"))

    concentration_current = (
        as_float(q4[0].get("Concentracion_Top10_Pct")) if q4 else 0.0
    )
    concentration_baseline = concentration_current

    margin_target = baseline_margin + 1.0
    profit_target = baseline_profit * 1.05
    ticket_target = baseline_ticket * 1.05
    concentration_target = max(concentration_baseline - 2.0, 0.0)

    return {
        "margen": {
            "baseline": baseline_margin,
            "target": margin_target,
            "current": current_margin,
            "delta": current_margin - baseline_margin,
            "status": status_higher_is_better(current_margin, margin_target),
            "delta_kind": "pp",
        },
        "ganancia": {
            "baseline": baseline_profit,
            "target": profit_target,
            "current": current_profit,
            "delta": ((current_profit / baseline_profit - 1) * 100)
            if baseline_profit
            else 0.0,
            "status": status_higher_is_better(current_profit, profit_target),
            "delta_kind": "pct",
        },
        "ticket": {
            "baseline": baseline_ticket,
            "target": ticket_target,
            "current": current_ticket,
            "delta": ((current_ticket / baseline_ticket - 1) * 100)
            if baseline_ticket
            else 0.0,
            "status": status_higher_is_better(current_ticket, ticket_target),
            "delta_kind": "pct",
        },
        "concentracion": {
            "baseline": concentration_baseline,
            "target": concentration_target,
            "current": concentration_current,
            "delta": concentration_current - concentration_baseline,
            "status": status_lower_is_better(
                concentration_current, concentration_target
            ),
            "delta_kind": "pp",
        },
    }


def top_rows(rows: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
    return rows[: min(n, len(rows))]


def render_markdown(
    start_date: str,
    end_date: str,
    scorecard: Dict[str, Dict[str, Any]],
    results: Dict[str, List[Dict[str, Any]]],
) -> str:
    q2 = results["Q2"]
    q3 = results["Q3"]
    q5 = results["Q5"]
    q7 = results["Q7"]

    top_gain = top_rows(q2, 5)
    bottom_margin = sorted(q2, key=lambda r: as_float(r.get("Margen_Bruto_Pct")))[:5]
    critical_skus = [
        r for r in q3 if r.get("Prioridad") in {"ACCION_INMEDIATA", "ACCION_ALTA"}
    ][:10]
    low_margin_customers = sorted(
        q5, key=lambda r: as_float(r.get("Margen_Bruto_Pct"))
    )[:5]
    returns_top = top_rows(q7, 5)

    lines: List[str] = []
    lines.append("# KPI Control Board (Weekly)")
    lines.append("")
    lines.append("## 1) Control Header")
    lines.append("")
    lines.append(
        f"- **Week (ISO):** {datetime.fromisoformat(end_date).isocalendar().week}"
    )
    lines.append(f"- **Date range:** {start_date} to {end_date}")
    lines.append(
        "- **Prepared by:** Auto-generated (scripts/utils/generate_kpi_control_board.py)"
    )
    lines.append("- **Reviewed with:** Comercial / Compras / Operaciones / Finanzas")
    lines.append("")
    lines.append("## 2) North-Star KPI Scorecard")
    lines.append("")
    lines.append(
        "| KPI | Formula | Baseline | Target | This Week | vs Baseline | Status |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---|")
    lines.append(
        "| Margen Bruto % | `SUM(TotalSinIva-ValorCosto)/SUM(TotalSinIva)*100` "
        f"| {format_pct(scorecard['margen']['baseline'])} "
        f"| {format_pct(scorecard['margen']['target'])} "
        f"| {format_pct(scorecard['margen']['current'])} "
        f"| {format_delta(scorecard['margen']['delta'], 'pp')} "
        f"| {scorecard['margen']['status']} |"
    )
    lines.append(
        "| Ganancia Bruta ($) | `SUM(TotalSinIva-ValorCosto)` "
        f"| {format_currency(scorecard['ganancia']['baseline'])} "
        f"| {format_currency(scorecard['ganancia']['target'])} "
        f"| {format_currency(scorecard['ganancia']['current'])} "
        f"| {format_delta(scorecard['ganancia']['delta'], 'pct')} "
        f"| {scorecard['ganancia']['status']} |"
    )
    lines.append(
        "| Ticket Promedio ($) | `SUM(TotalMasIva)/COUNT(*)` "
        f"| {format_currency(scorecard['ticket']['baseline'])} "
        f"| {format_currency(scorecard['ticket']['target'])} "
        f"| {format_currency(scorecard['ticket']['current'])} "
        f"| {format_delta(scorecard['ticket']['delta'], 'pct')} "
        f"| {scorecard['ticket']['status']} |"
    )
    lines.append(
        "| Concentración Top-10 Clientes % | `Facturación Top10 / Facturación Total * 100` "
        f"| {format_pct(scorecard['concentracion']['baseline'])} "
        f"| {format_pct(scorecard['concentracion']['target'])} "
        f"| {format_pct(scorecard['concentracion']['current'])} "
        f"| {format_delta(scorecard['concentracion']['delta'], 'pp')} "
        f"| {scorecard['concentracion']['status']} |"
    )

    lines.append("")
    lines.append("## 3) Diagnostic Cut (Where we win/lose)")
    lines.append("")
    lines.append("### 3.1 Category/Subcategory")
    lines.append("- **Top 5 by ganancia:**")
    for row in top_gain:
        lines.append(
            f"  - {row.get('Categoria')} / {row.get('Subcategoria')} | "
            f"Ganancia: {format_currency(as_float(row.get('Ganancia_Bruta')))} | "
            f"Margen: {format_pct(as_float(row.get('Margen_Bruto_Pct')))}"
        )
    lines.append("- **Bottom 5 by margen:**")
    for row in bottom_margin:
        lines.append(
            f"  - {row.get('Categoria')} / {row.get('Subcategoria')} | "
            f"Margen: {format_pct(as_float(row.get('Margen_Bruto_Pct')))} | "
            f"Ganancia: {format_currency(as_float(row.get('Ganancia_Bruta')))}"
        )
    lines.append(
        "- **Biggest WoW drop in margen:** completar con comparación semana anterior."
    )

    lines.append("")
    lines.append("### 3.2 SKU Focus (High Volume + Low Margin)")
    lines.append("- **Critical SKUs (ACCION_INMEDIATA / ACCION_ALTA):**")
    for row in critical_skus:
        lines.append(
            f"  - {row.get('SKU')} | {row.get('Producto')} | Volumen: {int(as_float(row.get('Unidades'))):,} | "
            f"Margen: {format_pct(as_float(row.get('Margen_Bruto_Pct')))} | Prioridad: {row.get('Prioridad')}"
        )

    lines.append("")
    lines.append("### 3.3 Customer Concentration")
    lines.append(
        f"- **Top-10 concentration %:** {format_pct(scorecard['concentracion']['current'])}"
    )
    lines.append("- **Top customers with low margin (< target floor):**")
    for row in low_margin_customers:
        lines.append(
            f"  - {row.get('Cliente')} | Margen: {format_pct(as_float(row.get('Margen_Bruto_Pct')))} | "
            f"Facturación: {format_currency(as_float(row.get('Facturacion_Con_IVA')))}"
        )

    lines.append("")
    lines.append("### 3.4 Returns and Margin Erosion")
    lines.append("- **Categories with highest return rate %:**")
    for row in returns_top:
        lines.append(
            f"  - {row.get('Categoria')} | Tasa devolución: {format_pct(as_float(row.get('Tasa_Devolucion_Pct')))} | "
            f"Ganancia: {format_currency(as_float(row.get('Ganancia_Bruta')))}"
        )
    lines.append("- **Estimated margin impact:** completar con análisis comercial.")

    lines.append("")
    lines.append("## 4) Weekly Action Plan (Execution)")
    lines.append("")
    lines.append(
        "| Priority | Lever | Action | Owner | Due Date | Expected KPI Impact |"
    )
    lines.append("|---|---|---|---|---|---|")
    lines.append("| High | Pricing |  |  |  | +pp margen |")
    lines.append("| High | Mix/Bundles |  |  |  | +ticket / +margen |")
    lines.append("| Medium | Customer Terms |  |  |  | +margen cliente |")
    lines.append("| Medium | Inventory |  |  |  | +capital / +margen |")

    lines.append("")
    lines.append("## 5) SQL Blocks Used (Traceability)")
    lines.append("")
    for q in range(1, 9):
        lines.append(f"- [x] Q{q}")

    return "\n".join(lines) + "\n"


def resolve_output_path(end_date: str, custom_output: str) -> Path:
    if custom_output:
        return Path(custom_output).resolve()

    year, week, _ = datetime.fromisoformat(end_date).isocalendar()
    return OUTPUT_DIR / f"KPI_CONTROL_BOARD_{year}_W{week:02d}.md"


def generate_kpi_control_board(
    start_date: str,
    end_date: str,
    output: str = "",
) -> Path:
    output_path = resolve_output_path(end_date, output)
    blocks = load_query_blocks(SQL_PACK_PATH)

    results: Dict[str, List[Dict[str, Any]]] = {}
    conn = get_connection()
    try:
        for key in [f"Q{i}" for i in range(1, 9)]:
            query = render_query(blocks[key], start_date, end_date)
            results[key] = execute_query(conn, query)
    finally:
        conn.close()

    scorecard = compute_scorecard(results)
    markdown = render_markdown(start_date, end_date, scorecard, results)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")

    return output_path


def main() -> None:
    args = parse_args()
    output_path = generate_kpi_control_board(
        start_date=args.start_date,
        end_date=args.end_date,
        output=args.output,
    )

    print(f"✅ KPI control board generated: {output_path}")


if __name__ == "__main__":
    main()
