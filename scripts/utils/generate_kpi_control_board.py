#!/usr/bin/env python3
"""
Generate a weekly KPI control board from the SQL KPI pack.

Reads query blocks from:
  scripts/analysis/kpi_sql_pack.sql.template

Writes markdown board to:
  reports/KPI_CONTROL_BOARD_<year>_W<week>.md

Environment variables required:
  DB_SERVER (or DB_HOST), DB_USER, DB_PASSWORD
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
from typing import Any, Dict, List, Optional, Tuple

import pymssql

try:
    from business_analyzer.ai.base import (  # pyright: ignore[reportMissingImports]
        AIVanna,
    )

    _ai = AIVanna()
except Exception:
    _ai = None

try:
    from business_analyzer.core.j3system_cotizacion_funnel import (  # noqa: E402
        funnel_summary_from_vendor_rows,
    )
except ImportError:
    funnel_summary_from_vendor_rows = None

try:
    from business_analyzer.core.j3system_critical_inventory import (  # noqa: E402
        critical_inventory_summary_from_rows,
    )
except ImportError:
    critical_inventory_summary_from_rows = None

try:
    from business_analyzer.core.j3system_otif import (  # noqa: E402
        otif_summary_from_warehouse_rows,
    )
except ImportError:
    otif_summary_from_warehouse_rows = None

try:
    from business_analyzer.core.j3system_devoluciones_conciliacion import (  # noqa: E402
        conciliacion_summary_from_category_rows,
    )
except ImportError:
    conciliacion_summary_from_category_rows = None

try:
    from business_analyzer.core.j3system_factura_electronica import (  # noqa: E402
        factura_electronica_summary_from_documento_rows,
    )
except ImportError:
    factura_electronica_summary_from_documento_rows = None

try:
    from business_analyzer.core.j3system_contabilidad import (  # noqa: E402
        pyg_summary_from_clase_rows,
    )
except ImportError:
    pyg_summary_from_clase_rows = None

ROOT_DIR = Path(__file__).resolve().parents[2]
SQL_PACK_PATH = ROOT_DIR / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
OUTPUT_DIR = ROOT_DIR / "reports"

# Extra history for Q1 trend baseline when the board window is a single ISO week.
Q1_TREND_LOOKBACK_DAYS = 28

# Fixed operational targets (tune in one place; do not invent new business goals ad hoc).
KPI_TARGETS: Dict[str, float] = {
    "dso_days": 45.0,
    "cartera_90_pct": 12.0,
    "presupuesto_pct": 100.0,
    "conversion_pct": 30.0,
    "conv_days": 7.0,
    "skus_criticos": 25.0,
    "cobertura_days": 7.0,
    "quiebre_7d": 5.0,
    "otif_pct": 85.0,
    "lead_time_days": 3.0,
    "fill_rate_pct": 95.0,
    "conciliacion_pct": 99.0,
    "fe_aceptacion_pct": 99.5,
    "fe_rechazo_pct": 0.5,
    "margen_contable_pct": 15.0,
    "min_ventas_wow": 1_000_000.0,  # COP net sales floor for WoW category comparison
}

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


def get_db_server() -> str:
    server = (os.getenv("DB_SERVER") or os.getenv("DB_HOST") or "").strip()
    if not server:
        raise ValueError("Missing required environment variable: DB_SERVER or DB_HOST")
    return server


def get_connection() -> pymssql.Connection:
    server = get_db_server()
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

    required = {f"Q{i}" for i in range(1, 18)}
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


def format_delta(value: Optional[float], kind: str) -> str:
    if value is None:
        return "—"
    if kind == "pp":
        return f"{value:+.2f} pp".replace(".", ",")
    if kind == "days":
        return f"{value:+.0f} días"
    if kind == "count":
        return f"{value:+.0f}"
    return format_pct(value, 2) if value else "0,00%"


def format_optional_pct(value: Optional[float], decimals: int = 2) -> str:
    if value is None:
        return "—"
    return format_pct(value, decimals)


def format_optional_currency(value: Optional[float], decimals: int = 0) -> str:
    if value is None:
        return "—"
    return format_currency(value, decimals)


def format_optional_number(value: Optional[float], decimals: int = 0) -> str:
    if value is None:
        return "—"
    if decimals == 0:
        return f"{value:.0f}"
    return f"{value:.{decimals}f}".replace(".", ",")


def trend_start_for(
    board_start: str, *, lookback_days: int = Q1_TREND_LOOKBACK_DAYS
) -> str:
    """Start date for Q1 trend query (lookback before the board window)."""
    start = date.fromisoformat(board_start)
    return (start - timedelta(days=lookback_days)).isoformat()


def previous_iso_week_range(board_start: str) -> Tuple[str, str]:
    """Inclusive Mon–Sun window for the ISO week before ``board_start``."""
    start = date.fromisoformat(board_start)
    prev_end = start - timedelta(days=1)
    prev_start = start - timedelta(days=7)
    return prev_start.isoformat(), prev_end.isoformat()


def pick_current_and_baseline_q1(
    q1_rows: List[Dict[str, Any]],
    *,
    focus_end: Optional[str] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Return (current week row, up to 4 prior weekly rows for baseline)."""
    q1 = sorted(
        q1_rows,
        key=lambda r: (as_float(r.get("Anio")), as_float(r.get("Semana_ISO"))),
    )
    if not q1:
        raise ValueError("Q1 returned no data; cannot compute scorecard")

    current_idx = len(q1) - 1
    if focus_end:
        end = date.fromisoformat(focus_end)
        focus_year, focus_week, _ = end.isocalendar()
        for i, row in enumerate(q1):
            if (
                int(as_float(row.get("Anio"))) == focus_year
                and int(as_float(row.get("Semana_ISO"))) == focus_week
            ):
                current_idx = i
                break

    current = q1[current_idx]
    prior = q1[:current_idx]
    baseline_rows = prior[-4:] if prior else []
    return current, baseline_rows


def biggest_wow_margin_drop(
    q2_current: List[Dict[str, Any]],
    q2_prev: List[Dict[str, Any]],
    *,
    min_ventas: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Largest WoW margin pp drop among categories with enough sales both weeks."""
    floor = min_ventas if min_ventas is not None else KPI_TARGETS["min_ventas_wow"]
    prev_map: Dict[Tuple[Any, Any], Dict[str, Any]] = {}
    for row in q2_prev:
        key = (row.get("Categoria"), row.get("Subcategoria"))
        prev_map[key] = row

    best: Optional[Dict[str, Any]] = None
    for row in q2_current:
        key = (row.get("Categoria"), row.get("Subcategoria"))
        prev = prev_map.get(key)
        if not prev:
            continue
        ventas_cur = as_float(row.get("Ventas_Netas"))
        ventas_prev = as_float(prev.get("Ventas_Netas"))
        if ventas_cur < floor or ventas_prev < floor:
            continue
        margin_cur = as_float(row.get("Margen_Bruto_Pct"))
        margin_prev = as_float(prev.get("Margen_Bruto_Pct"))
        drop = margin_prev - margin_cur  # positive = worsened
        if drop <= 0:
            continue
        candidate = {
            "Categoria": row.get("Categoria"),
            "Subcategoria": row.get("Subcategoria"),
            "Margen_Prev": margin_prev,
            "Margen_Actual": margin_cur,
            "Drop_Pp": drop,
            "Ventas_Netas": ventas_cur,
        }
        if best is None or candidate["Drop_Pp"] > best["Drop_Pp"]:
            best = candidate
    return best


def estimated_return_margin_impact(
    q7_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Approximate margin $ at risk from returns: sum(tasa/100 * ganancia).

    Heuristic only — uses category return rate applied to net ganancia in period.
    """
    impact = 0.0
    top: List[Dict[str, Any]] = []
    for row in q7_rows:
        tasa = as_float(row.get("Tasa_Devolucion_Pct"))
        ganancia = as_float(row.get("Ganancia_Bruta"))
        # Only count erosion from categories with positive profit contribution
        if tasa <= 0 or ganancia <= 0:
            continue
        cat_impact = (tasa / 100.0) * ganancia
        impact += cat_impact
        top.append(
            {
                "Categoria": row.get("Categoria"),
                "Tasa_Devolucion_Pct": tasa,
                "Impacto_Estimado": cat_impact,
            }
        )
    top_sorted = sorted(top, key=lambda r: r["Impacto_Estimado"], reverse=True)[:3]
    return {"total": impact, "top": top_sorted}


def _metric(
    *,
    current: float,
    target: float,
    baseline: Optional[float] = None,
    higher_is_better: bool = True,
    delta_kind: str = "pp",
    pct_delta_vs_baseline: bool = False,
) -> Dict[str, Any]:
    """Build a scorecard metric. ``baseline=None`` means no period baseline (show —)."""
    if baseline is not None:
        if pct_delta_vs_baseline:
            delta: Optional[float] = (
                ((current / baseline - 1) * 100) if baseline else 0.0
            )
        else:
            delta = current - baseline
    else:
        # No honest prior period: report gap vs target in the delta column.
        if pct_delta_vs_baseline:
            delta = ((current / target - 1) * 100) if target else 0.0
        else:
            delta = current - target

    status_fn = status_higher_is_better if higher_is_better else status_lower_is_better
    return {
        "baseline": baseline,
        "target": target,
        "current": current,
        "delta": delta,
        "status": status_fn(current, target),
        "delta_kind": delta_kind,
    }


def generate_narrative(
    scorecard: Dict[str, Dict[str, Any]], results: Dict[str, List[Dict[str, Any]]]
) -> str:
    """Generate AI narrative summary for KPI board."""
    if _ai is None:
        return "AI narrative unavailable (AIVanna init failed)."
    try:
        margin = scorecard.get("margen", {}).get("current", 0.0)
        profit = scorecard.get("ganancia", {}).get("current", 0.0)
        ticket = scorecard.get("ticket", {}).get("current", 0.0)
        concentration = scorecard.get("concentracion", {}).get("current", 0.0)
        dso = scorecard.get("dso", {}).get("current", 0.0)
        cartera_90 = scorecard.get("cartera_90", {}).get("current", 0.0)
        presupuesto = scorecard.get("presupuesto", {}).get("current", 0.0)
        q2 = results.get("Q2", [])
        top_cat = q2[0].get("Categoria", "N/A") if q2 else "N/A"
        q11 = results.get("Q11", [])
        top_marca = q11[0].get("Marca", "N/A") if q11 else "N/A"
        q12 = results.get("Q12", [])
        if funnel_summary_from_vendor_rows and q12:
            funnel = funnel_summary_from_vendor_rows(q12)
            conv_rate = funnel.get("Tasa_Conversion_Pct", 0.0)
            conv_days = funnel.get("Dias_Promedio_Conversion", 0.0)
        else:
            conv_rate = 0.0
            conv_days = 0.0
        q13 = results.get("Q13", [])
        if critical_inventory_summary_from_rows and q13:
            inv = critical_inventory_summary_from_rows(q13)
            skus_criticos = inv.get("SKUs_Criticos", 0)
            dias_cobertura = inv.get("Promedio_Dias_Cobertura", 0.0)
        else:
            skus_criticos = 0
            dias_cobertura = 0.0
        q14 = results.get("Q14", [])
        if otif_summary_from_warehouse_rows and q14:
            otif = otif_summary_from_warehouse_rows(q14)
            otif_pct = otif.get("OTIF_Pct", 0.0)
            lead_time = otif.get("Lead_Time_Promedio_Dias", 0.0)
        else:
            otif_pct = 0.0
            lead_time = 0.0
        q15 = results.get("Q15", [])
        if conciliacion_summary_from_category_rows and q15:
            dev = conciliacion_summary_from_category_rows(q15)
            conc_pct = dev.get("Conciliacion_Pct", 0.0)
            tasa_dev = dev.get("Tasa_Devolucion_Validada_Pct", 0.0)
        else:
            conc_pct = 0.0
            tasa_dev = 0.0
        q16 = results.get("Q16", [])
        if factura_electronica_summary_from_documento_rows and q16:
            fe = factura_electronica_summary_from_documento_rows(q16)
            fe_aceptacion = fe.get("Tasa_Aceptacion_Pct", 0.0)
            fe_rechazo = fe.get("Tasa_Rechazo_Pct", 0.0)
        else:
            fe_aceptacion = 0.0
            fe_rechazo = 0.0
        q17 = results.get("Q17", [])
        if pyg_summary_from_clase_rows and q17:
            cont = pyg_summary_from_clase_rows(q17)
            margen_cont_pct = cont.get("Margen_Contable_Pct", 0.0)
            ingresos_cont = cont.get("Ingresos_Creditos", 0.0)
        else:
            margen_cont_pct = 0.0
            ingresos_cont = 0.0
        prompt = (
            f"Escribe un párrafo ejecutivo en español (máximo 150 palabras) "
            f"analizando el rendimiento semanal de la ferretería: "
            f"Margen Bruto {margin:.2f}%, Ganancia Bruta ${profit:,.0f}, "
            f"Ticket Promedio ${ticket:,.0f}, Concentración Top-10 {concentration:.2f}%, "
            f"DSO {dso:.0f} días, Cartera vencida >90d {cartera_90:.2f}%, "
            f"Cumplimiento presupuesto MTD {presupuesto:.2f}%, "
            f"Tasa conversión cotizaciones {conv_rate:.2f}% "
            f"(días prom. {conv_days:.1f}), "
            f"SKUs inventario crítico {skus_criticos} "
            f"(cobertura prom. {dias_cobertura:.1f} días), "
            f"OTIF entregas {otif_pct:.2f}% "
            f"(lead time {lead_time:.1f} días), "
            f"Conciliación devoluciones {conc_pct:.2f}% "
            f"(tasa validada {tasa_dev:.2f}%), "
            f"Aceptación factura electrónica {fe_aceptacion:.2f}% "
            f"(rechazo {fe_rechazo:.2f}%), "
            f"Margen contable {margen_cont_pct:.2f}% "
            f"(ingresos contables ${ingresos_cont:,.0f}), "
            f"Categoría top: {top_cat}, Marca real top: {top_marca}. "
            f"Incluye una recomendación comercial accionable."
        )
        message_log = [
            _ai.system_message(
                "Eres un asistente de datos para una ferretería colombiana. "
                "Escribe en español colombiano usando formato de moneda COP "
                "con separador de miles con punto."
            ),
            _ai.user_message(prompt),
        ]
        summary = _ai.submit_prompt(message_log)
        return str(summary)
    except Exception as e:
        return f"AI narrative generation failed: {e}"


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
    results: Dict[str, List[Dict[str, Any]]],
    *,
    focus_end: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    current, baseline_rows = pick_current_and_baseline_q1(
        results["Q1"], focus_end=focus_end
    )
    q4 = results.get("Q4") or []

    if baseline_rows:
        baseline_margin: Optional[float] = mean(
            [as_float(r.get("Margen_Bruto_Pct")) for r in baseline_rows]
        )
        baseline_profit: Optional[float] = mean(
            [as_float(r.get("Ganancia_Bruta")) for r in baseline_rows]
        )
        baseline_ticket: Optional[float] = mean(
            [as_float(r.get("Ticket_Promedio")) for r in baseline_rows]
        )
    else:
        baseline_margin = None
        baseline_profit = None
        baseline_ticket = None

    current_margin = as_float(current.get("Margen_Bruto_Pct"))
    current_profit = as_float(current.get("Ganancia_Bruta"))
    current_ticket = as_float(current.get("Ticket_Promedio"))

    concentration_current = (
        as_float(q4[0].get("Concentracion_Top10_Pct")) if q4 else 0.0
    )
    # No multi-period concentration series yet — do not fake baseline == current.
    concentration_baseline: Optional[float] = None

    q9 = results.get("Q9", [])
    q9_row = q9[0] if q9 else {}
    current_dso = as_float(q9_row.get("DSO_Dias"))
    current_cartera_90 = as_float(q9_row.get("Cartera_Vencida_90_Plus_Pct"))

    q10 = results.get("Q10", [])
    if q10:
        total_meta = sum(as_float(r.get("Meta_Prorrateada")) for r in q10)
        total_mtd = sum(as_float(r.get("Ventas_MTD")) for r in q10)
        current_presupuesto = (total_mtd / total_meta * 100.0) if total_meta else 0.0
    else:
        current_presupuesto = 0.0

    q12 = results.get("Q12", [])
    if funnel_summary_from_vendor_rows and q12:
        funnel = funnel_summary_from_vendor_rows(q12)
        current_conversion = as_float(funnel.get("Tasa_Conversion_Pct"))
        current_conv_days = as_float(funnel.get("Dias_Promedio_Conversion"))
    else:
        current_conversion = 0.0
        current_conv_days = 0.0

    q13 = results.get("Q13", [])
    if critical_inventory_summary_from_rows and q13:
        inv = critical_inventory_summary_from_rows(q13)
        current_skus_criticos = as_float(inv.get("SKUs_Criticos"))
        current_cobertura = as_float(inv.get("Promedio_Dias_Cobertura"))
        current_quiebre_7d = as_float(inv.get("SKUs_Quiebre_7d"))
    else:
        current_skus_criticos = 0.0
        current_cobertura = 0.0
        current_quiebre_7d = 0.0

    q14 = results.get("Q14", [])
    if otif_summary_from_warehouse_rows and q14:
        otif = otif_summary_from_warehouse_rows(q14)
        current_otif = as_float(otif.get("OTIF_Pct"))
        current_lead_time = as_float(otif.get("Lead_Time_Promedio_Dias"))
        current_fill_rate = as_float(otif.get("Fill_Rate_Pct"))
    else:
        current_otif = 0.0
        current_lead_time = 0.0
        current_fill_rate = 0.0

    q15 = results.get("Q15", [])
    if conciliacion_summary_from_category_rows and q15:
        dev = conciliacion_summary_from_category_rows(q15)
        current_conciliacion = as_float(dev.get("Conciliacion_Pct"))
        current_tasa_dev = as_float(dev.get("Tasa_Devolucion_Validada_Pct"))
        current_gap_cats = as_float(dev.get("Categorias_Con_Diferencia"))
    else:
        current_conciliacion = 0.0
        current_tasa_dev = 0.0
        current_gap_cats = 0.0

    q16 = results.get("Q16", [])
    if factura_electronica_summary_from_documento_rows and q16:
        fe = factura_electronica_summary_from_documento_rows(q16)
        current_fe_aceptacion = as_float(fe.get("Tasa_Aceptacion_Pct"))
        current_fe_rechazo = as_float(fe.get("Tasa_Rechazo_Pct"))
        current_fe_emitidas = as_float(fe.get("Emitidas"))
    else:
        current_fe_aceptacion = 0.0
        current_fe_rechazo = 0.0
        current_fe_emitidas = 0.0

    q17 = results.get("Q17", [])
    if pyg_summary_from_clase_rows and q17:
        cont = pyg_summary_from_clase_rows(q17)
        current_margen_contable = as_float(cont.get("Margen_Bruto_Contable"))
        current_margen_contable_pct = as_float(cont.get("Margen_Contable_Pct"))
        current_ingresos_contables = as_float(cont.get("Ingresos_Creditos"))
        current_gastos_contables = as_float(cont.get("Gastos_Debitos"))
    else:
        current_margen_contable = 0.0
        current_margen_contable_pct = 0.0
        current_ingresos_contables = 0.0
        current_gastos_contables = 0.0

    # Dynamic targets: vs multi-week baseline when available, else vs this week.
    ref_margin = baseline_margin if baseline_margin is not None else current_margin
    ref_profit = baseline_profit if baseline_profit is not None else current_profit
    ref_ticket = baseline_ticket if baseline_ticket is not None else current_ticket
    margin_target = ref_margin + 1.0
    profit_target = ref_profit * 1.05 if ref_profit else current_profit * 1.05
    ticket_target = ref_ticket * 1.05 if ref_ticket else current_ticket * 1.05
    concentration_target = max(concentration_current - 2.0, 0.0)

    return {
        "margen": _metric(
            current=current_margin,
            target=margin_target,
            baseline=baseline_margin,
            higher_is_better=True,
            delta_kind="pp",
        ),
        "ganancia": _metric(
            current=current_profit,
            target=profit_target,
            baseline=baseline_profit,
            higher_is_better=True,
            delta_kind="pct",
            pct_delta_vs_baseline=True,
        ),
        "ticket": _metric(
            current=current_ticket,
            target=ticket_target,
            baseline=baseline_ticket,
            higher_is_better=True,
            delta_kind="pct",
            pct_delta_vs_baseline=True,
        ),
        "concentracion": _metric(
            current=concentration_current,
            target=concentration_target,
            baseline=concentration_baseline,
            higher_is_better=False,
            delta_kind="pp",
        ),
        "dso": _metric(
            current=current_dso,
            target=KPI_TARGETS["dso_days"],
            baseline=None,
            higher_is_better=False,
            delta_kind="days",
        ),
        "cartera_90": _metric(
            current=current_cartera_90,
            target=KPI_TARGETS["cartera_90_pct"],
            baseline=None,
            higher_is_better=False,
            delta_kind="pp",
        ),
        "presupuesto": _metric(
            current=current_presupuesto,
            target=KPI_TARGETS["presupuesto_pct"],
            baseline=None,
            higher_is_better=True,
            delta_kind="pp",
        ),
        "conversion_cotiza": _metric(
            current=current_conversion,
            target=KPI_TARGETS["conversion_pct"],
            baseline=None,
            higher_is_better=True,
            delta_kind="pp",
        ),
        "dias_conversion": _metric(
            current=current_conv_days,
            target=KPI_TARGETS["conv_days"],
            baseline=None,
            higher_is_better=False,
            delta_kind="days",
        ),
        "skus_criticos": _metric(
            current=current_skus_criticos,
            target=KPI_TARGETS["skus_criticos"],
            baseline=None,
            higher_is_better=False,
            delta_kind="count",
        ),
        "cobertura_critica": _metric(
            current=current_cobertura,
            target=KPI_TARGETS["cobertura_days"],
            baseline=None,
            higher_is_better=True,
            delta_kind="days",
        ),
        "quiebre_7d": _metric(
            current=current_quiebre_7d,
            target=KPI_TARGETS["quiebre_7d"],
            baseline=None,
            higher_is_better=False,
            delta_kind="count",
        ),
        "otif": _metric(
            current=current_otif,
            target=KPI_TARGETS["otif_pct"],
            baseline=None,
            higher_is_better=True,
            delta_kind="pp",
        ),
        "lead_time_entrega": _metric(
            current=current_lead_time,
            target=KPI_TARGETS["lead_time_days"],
            baseline=None,
            higher_is_better=False,
            delta_kind="days",
        ),
        "fill_rate": _metric(
            current=current_fill_rate,
            target=KPI_TARGETS["fill_rate_pct"],
            baseline=None,
            higher_is_better=True,
            delta_kind="pp",
        ),
        "conciliacion_devoluciones": _metric(
            current=current_conciliacion,
            target=KPI_TARGETS["conciliacion_pct"],
            baseline=None,
            higher_is_better=True,
            delta_kind="pp",
        ),
        "tasa_devolucion_validada": {
            "baseline": None,
            "target": current_tasa_dev,
            "current": current_tasa_dev,
            "delta": None,
            "status": "🟢",
            "delta_kind": "pp",
        },
        "categorias_brecha_dev": _metric(
            current=current_gap_cats,
            target=0.0,
            baseline=None,
            higher_is_better=False,
            delta_kind="count",
        ),
        "factura_electronica_aceptacion": _metric(
            current=current_fe_aceptacion,
            target=KPI_TARGETS["fe_aceptacion_pct"],
            baseline=None,
            higher_is_better=True,
            delta_kind="pp",
        ),
        "factura_electronica_rechazo": _metric(
            current=current_fe_rechazo,
            target=KPI_TARGETS["fe_rechazo_pct"],
            baseline=None,
            higher_is_better=False,
            delta_kind="pp",
        ),
        "facturas_electronicas_emitidas": {
            "baseline": None,
            "target": current_fe_emitidas,
            "current": current_fe_emitidas,
            "delta": None,
            "status": "🟢",
            "delta_kind": "count",
        },
        "margen_contable": {
            "baseline": None,
            "target": current_margen_contable,
            "current": current_margen_contable,
            "delta": None,
            "status": "🟢",
            "delta_kind": "currency",
        },
        "margen_contable_pct": _metric(
            current=current_margen_contable_pct,
            target=KPI_TARGETS["margen_contable_pct"],
            baseline=None,
            higher_is_better=True,
            delta_kind="pp",
        ),
        "ingresos_contables": {
            "baseline": None,
            "target": current_ingresos_contables,
            "current": current_ingresos_contables,
            "delta": None,
            "status": "🟢",
            "delta_kind": "currency",
        },
        "gastos_contables": {
            "baseline": None,
            "target": current_gastos_contables,
            "current": current_gastos_contables,
            "delta": None,
            "status": "🟢",
            "delta_kind": "currency",
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
    q9 = results.get("Q9", [])
    q9_row = q9[0] if q9 else {}
    q10 = results.get("Q10", [])
    q11 = results.get("Q11", [])
    q12 = results.get("Q12", [])
    q13 = results.get("Q13", [])
    q14 = results.get("Q14", [])
    q15 = results.get("Q15", [])
    q16 = results.get("Q16", [])
    q17 = results.get("Q17", [])
    inv_summary = (
        critical_inventory_summary_from_rows(q13)
        if critical_inventory_summary_from_rows and q13
        else {}
    )
    otif_summary = (
        otif_summary_from_warehouse_rows(q14)
        if otif_summary_from_warehouse_rows and q14
        else {}
    )
    dev_summary = (
        conciliacion_summary_from_category_rows(q15)
        if conciliacion_summary_from_category_rows and q15
        else {}
    )
    fe_summary = (
        factura_electronica_summary_from_documento_rows(q16)
        if factura_electronica_summary_from_documento_rows and q16
        else {}
    )
    cont_summary = (
        pyg_summary_from_clase_rows(q17) if pyg_summary_from_clase_rows and q17 else {}
    )
    funnel_summary = (
        funnel_summary_from_vendor_rows(q12)
        if funnel_summary_from_vendor_rows and q12
        else {}
    )

    top_gain = top_rows(q2, 5)
    top_marcas = top_rows(q11, 5)
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
        "| KPI | Formula | Baseline | Target | This Week | vs Baseline* | Status |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---|")
    lines.append(
        "| Margen Bruto % | `SUM(TotalSinIva-ValorCosto)/SUM(TotalSinIva)*100` "
        f"| {format_optional_pct(scorecard['margen']['baseline'])} "
        f"| {format_pct(scorecard['margen']['target'])} "
        f"| {format_pct(scorecard['margen']['current'])} "
        f"| {format_delta(scorecard['margen']['delta'], 'pp')} "
        f"| {scorecard['margen']['status']} |"
    )
    lines.append(
        "| Ganancia Bruta ($) | `SUM(TotalSinIva-ValorCosto)` "
        f"| {format_optional_currency(scorecard['ganancia']['baseline'])} "
        f"| {format_currency(scorecard['ganancia']['target'])} "
        f"| {format_currency(scorecard['ganancia']['current'])} "
        f"| {format_delta(scorecard['ganancia']['delta'], 'pct')} "
        f"| {scorecard['ganancia']['status']} |"
    )
    lines.append(
        "| Ticket Promedio ($) | `SUM(TotalMasIva)/COUNT(*)` "
        f"| {format_optional_currency(scorecard['ticket']['baseline'])} "
        f"| {format_currency(scorecard['ticket']['target'])} "
        f"| {format_currency(scorecard['ticket']['current'])} "
        f"| {format_delta(scorecard['ticket']['delta'], 'pct')} "
        f"| {scorecard['ticket']['status']} |"
    )
    lines.append(
        "| Concentración Top-10 Clientes % | `Facturación Top10 / Facturación Total * 100` "
        f"| {format_optional_pct(scorecard['concentracion']['baseline'])} "
        f"| {format_pct(scorecard['concentracion']['target'])} "
        f"| {format_pct(scorecard['concentracion']['current'])} "
        f"| {format_delta(scorecard['concentracion']['delta'], 'pp')} "
        f"| {scorecard['concentracion']['status']} |"
    )
    lines.append(
        "| DSO (días) | `Cartera Total / (Ventas Netas / días periodo)` "
        f"| {format_optional_number(scorecard['dso']['baseline'], 0)} "
        f"| {scorecard['dso']['target']:.0f} "
        f"| {scorecard['dso']['current']:.0f} "
        f"| {format_delta(scorecard['dso']['delta'], 'days')} "
        f"| {scorecard['dso']['status']} |"
    )
    lines.append(
        "| Cartera vencida >90d % | `SUM(vencido_90+120+360+superior)/Cartera*100` "
        f"| {format_optional_pct(scorecard['cartera_90']['baseline'])} "
        f"| {format_pct(scorecard['cartera_90']['target'])} "
        f"| {format_pct(scorecard['cartera_90']['current'])} "
        f"| {format_delta(scorecard['cartera_90']['delta'], 'pp')} "
        f"| {scorecard['cartera_90']['status']} |"
    )
    lines.append(
        "| Cumplimiento Presupuesto MTD % | `Ventas MTD / Meta prorrateada * 100` "
        f"| {format_optional_pct(scorecard['presupuesto']['baseline'])} "
        f"| {format_pct(scorecard['presupuesto']['target'])} "
        f"| {format_pct(scorecard['presupuesto']['current'])} "
        f"| {format_delta(scorecard['presupuesto']['delta'], 'pp')} "
        f"| {scorecard['presupuesto']['status']} |"
    )
    lines.append(
        "| Tasa Conversión Cotizaciones % | `Convertidas / Cotizaciones * 100` (J3System) "
        f"| {format_optional_pct(scorecard['conversion_cotiza']['baseline'])} "
        f"| {format_pct(scorecard['conversion_cotiza']['target'])} "
        f"| {format_pct(scorecard['conversion_cotiza']['current'])} "
        f"| {format_delta(scorecard['conversion_cotiza']['delta'], 'pp')} "
        f"| {scorecard['conversion_cotiza']['status']} |"
    )
    lines.append(
        "| Días Cotización → Factura | `AVG(DATEDIFF)` post-cotización (J3System) "
        f"| {format_optional_number(scorecard['dias_conversion']['baseline'], 1)} "
        f"| {scorecard['dias_conversion']['target']:.1f} "
        f"| {scorecard['dias_conversion']['current']:.1f} "
        f"| {format_delta(scorecard['dias_conversion']['delta'], 'days')} "
        f"| {scorecard['dias_conversion']['status']} |"
    )
    lines.append(
        "| SKUs Inventario Crítico | Top-N bajo umbral + alta rotación 90d "
        f"| {format_optional_number(scorecard['skus_criticos']['baseline'], 0)} "
        f"| {scorecard['skus_criticos']['target']:.0f} "
        f"| {scorecard['skus_criticos']['current']:.0f} "
        f"| {format_delta(scorecard['skus_criticos']['delta'], 'count')} "
        f"| {scorecard['skus_criticos']['status']} |"
    )
    lines.append(
        "| Cobertura Inventario (días prom.) | `Saldo / venta_diaria` SKUs críticos "
        f"| {format_optional_number(scorecard['cobertura_critica']['baseline'], 1)} "
        f"| {scorecard['cobertura_critica']['target']:.1f} "
        f"| {scorecard['cobertura_critica']['current']:.1f} "
        f"| {format_delta(scorecard['cobertura_critica']['delta'], 'days')} "
        f"| {scorecard['cobertura_critica']['status']} |"
    )
    lines.append(
        "| OTIF Entregas % | `A tiempo / total` (InvHistoricoEntregas) "
        f"| {format_optional_pct(scorecard['otif']['baseline'])} "
        f"| {format_pct(scorecard['otif']['target'])} "
        f"| {format_pct(scorecard['otif']['current'])} "
        f"| {format_delta(scorecard['otif']['delta'], 'pp')} "
        f"| {scorecard['otif']['status']} |"
    )
    lines.append(
        "| Lead Time Entrega (días prom.) | `AVG(FechaEntrega - FechaFactura)` "
        f"| {format_optional_number(scorecard['lead_time_entrega']['baseline'], 1)} "
        f"| {scorecard['lead_time_entrega']['target']:.1f} "
        f"| {scorecard['lead_time_entrega']['current']:.1f} "
        f"| {format_delta(scorecard['lead_time_entrega']['delta'], 'days')} "
        f"| {scorecard['lead_time_entrega']['status']} |"
    )
    lines.append(
        "| Conciliación Devoluciones % | `1 - |ERP-BI|/ERP` por unidades "
        f"| {format_optional_pct(scorecard['conciliacion_devoluciones']['baseline'])} "
        f"| {format_pct(scorecard['conciliacion_devoluciones']['target'])} "
        f"| {format_pct(scorecard['conciliacion_devoluciones']['current'])} "
        f"| {format_delta(scorecard['conciliacion_devoluciones']['delta'], 'pp')} "
        f"| {scorecard['conciliacion_devoluciones']['status']} |"
    )
    lines.append(
        "| Aceptación Factura Electrónica % | `Aceptadas / Emitidas` (DIAN) "
        f"| {format_optional_pct(scorecard['factura_electronica_aceptacion']['baseline'])} "
        f"| {format_pct(scorecard['factura_electronica_aceptacion']['target'])} "
        f"| {format_pct(scorecard['factura_electronica_aceptacion']['current'])} "
        f"| {format_delta(scorecard['factura_electronica_aceptacion']['delta'], 'pp')} "
        f"| {scorecard['factura_electronica_aceptacion']['status']} |"
    )
    lines.append(
        "| Rechazo Factura Electrónica % | `Rechazadas / Emitidas` (DIAN) "
        f"| {format_optional_pct(scorecard['factura_electronica_rechazo']['baseline'])} "
        f"| {format_pct(scorecard['factura_electronica_rechazo']['target'])} "
        f"| {format_pct(scorecard['factura_electronica_rechazo']['current'])} "
        f"| {format_delta(scorecard['factura_electronica_rechazo']['delta'], 'pp')} "
        f"| {scorecard['factura_electronica_rechazo']['status']} |"
    )
    lines.append(
        "| Margen Contable % | `(Ingresos 4 - Costos 6) / Ingresos` (PUC) "
        f"| {format_optional_pct(scorecard['margen_contable_pct']['baseline'])} "
        f"| {format_pct(scorecard['margen_contable_pct']['target'])} "
        f"| {format_pct(scorecard['margen_contable_pct']['current'])} "
        f"| {format_delta(scorecard['margen_contable_pct']['delta'], 'pp')} "
        f"| {scorecard['margen_contable_pct']['status']} |"
    )
    lines.append("")
    lines.append(
        "*\\* vs Baseline: for north-star sales KPIs with Q1 history, delta is vs "
        "prior-week average; when baseline is `—`, delta is vs target.*"
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
    wow = biggest_wow_margin_drop(q2, results.get("Q2_prev") or [])
    if wow:
        lines.append(
            f"- **Biggest WoW drop in margen:** {wow.get('Categoria')} / "
            f"{wow.get('Subcategoria')} | "
            f"{format_pct(wow['Margen_Prev'])} → {format_pct(wow['Margen_Actual'])} "
            f"({format_delta(-wow['Drop_Pp'], 'pp')}) | "
            f"Ventas: {format_currency(wow['Ventas_Netas'])}"
        )
    else:
        lines.append(
            "- **Biggest WoW drop in margen:** sin comparación (falta semana anterior "
            "o sin categorías con ventas suficientes en ambas semanas)."
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
    ret_impact = estimated_return_margin_impact(q7)
    lines.append(
        f"- **Estimated margin impact:** {format_currency(ret_impact['total'])} "
        f"(heurística: Σ tasa_devolución% × ganancia_bruta por categoría)"
    )
    for row in ret_impact.get("top") or []:
        lines.append(
            f"  - {row.get('Categoria')} | impacto: "
            f"{format_currency(as_float(row.get('Impacto_Estimado')))} | "
            f"tasa: {format_pct(as_float(row.get('Tasa_Devolucion_Pct')))}"
        )

    lines.append("")
    lines.append("### 3.5 Cartera y Riesgo de Crédito (banco_cartera)")
    if q9_row:
        fecha_carga = q9_row.get("Fecha_Carga_Cartera", "N/A")
        lines.append(f"- **Snapshot cartera:** {fecha_carga}")
        lines.append(
            f"- **Cartera total:** {format_currency(as_float(q9_row.get('Cartera_Total')))} | "
            f"**Vencida:** {format_pct(as_float(q9_row.get('Cartera_Vencida_Pct')))} | "
            f"**>90d:** {format_pct(as_float(q9_row.get('Cartera_Vencida_90_Plus_Pct')))}"
        )
        lines.append(
            f"- **DSO:** {as_float(q9_row.get('DSO_Dias')):.0f} días | "
            f"**Ventas netas periodo:** {format_currency(as_float(q9_row.get('Ventas_Netas_Periodo')))} | "
            f"**Días periodo:** {int(as_float(q9_row.get('Dias_Periodo')))}"
        )
        lines.append(
            f"- **Clientes con saldo:** {int(as_float(q9_row.get('Clientes_Con_Saldo'))):,} | "
            f"**Sobre cupo:** {int(as_float(q9_row.get('Clientes_Sobre_Cupo'))):,} | "
            f"**Días vencidos prom. ponderado:** {as_float(q9_row.get('Dias_Vencidos_Promedio_Ponderado')):.1f}"
        )
    else:
        lines.append("- **Sin datos de cartera (Q9 vacío).**")

    lines.append("")
    lines.append("### 3.6 Presupuesto vs Real (presupuesto_vendedores)")
    if q10:
        under = [
            r
            for r in q10
            if as_float(r.get("Meta_Prorrateada")) > 0
            and as_float(r.get("Cumplimiento_Prorrateado_Pct")) < 90.0
        ]
        lines.append(
            f"- **Periodo:** {q10[0].get('Periodo', 'N/A')} | "
            f"**Cumplimiento consolidado MTD:** "
            f"{format_pct(scorecard['presupuesto']['current'])}"
        )
        lines.append("- **Top 5 vendedores por meta mensual:**")
        for row in q10[:5]:
            lines.append(
                f"  - {row.get('Vendedor_Nombre')} ({row.get('Vendedor_Codigo')}) | "
                f"MTD: {format_currency(as_float(row.get('Ventas_MTD')))} | "
                f"Meta prorr.: {format_currency(as_float(row.get('Meta_Prorrateada')))} | "
                f"Cumpl.: {format_pct(as_float(row.get('Cumplimiento_Prorrateado_Pct')))}"
            )
        if under:
            lines.append("- **Bajo 90% cumplimiento (acción comercial):**")
            for row in under[:5]:
                lines.append(
                    f"  - {row.get('Vendedor_Nombre')} — "
                    f"{format_pct(as_float(row.get('Cumplimiento_Prorrateado_Pct')))} "
                    f"(brecha {format_currency(as_float(row.get('Brecha_MTD')))})"
                )
    else:
        lines.append("- **Sin datos de presupuesto (Q10 vacío).**")

    lines.append("")
    lines.append("### 3.7 Margen por marca real (productos_adicional)")
    if top_marcas:
        lines.append(
            "- **Top 5 marcas por ganancia bruta** "
            "(COALESCE producto_marca, banco_datos.marca):"
        )
        for row in top_marcas:
            lines.append(
                f"  - {row.get('Marca')} | Ganancia: "
                f"{format_currency(as_float(row.get('Ganancia_Bruta')))} | "
                f"Margen: {format_pct(as_float(row.get('Margen_Bruto_Pct')))} | "
                f"Ventas: {format_currency(as_float(row.get('Ventas_Netas')))}"
            )
    else:
        lines.append("- **Sin datos de marca (Q11 vacío).**")

    lines.append("")
    lines.append("### 3.8 Embudo cotización → factura (J3System InvCotiza*)")
    if funnel_summary:
        lines.append(
            f"- **Cotizaciones:** {int(as_float(funnel_summary.get('Cotizaciones'))):,} | "
            f"**Convertidas:** {int(as_float(funnel_summary.get('Convertidas'))):,} | "
            f"**Perdidas:** {int(as_float(funnel_summary.get('Perdidas'))):,} | "
            f"**Tasa:** {format_pct(as_float(funnel_summary.get('Tasa_Conversion_Pct')))} | "
            f"**Días prom.:** {as_float(funnel_summary.get('Dias_Promedio_Conversion')):.1f}"
        )
        lines.append("- **Top 5 vendedores por cotizaciones:**")
        for row in q12[:5]:
            lines.append(
                f"  - {row.get('Vendedor_Nombre')} ({row.get('Vendedor_Codigo')}) | "
                f"Cotiz.: {int(as_float(row.get('Cotizaciones')))} | "
                f"Conv.: {int(as_float(row.get('Convertidas')))} | "
                f"Tasa: {format_pct(as_float(row.get('Tasa_Conversion_Pct')))}"
            )
        lost = sorted(q12, key=lambda r: as_float(r.get("Perdidas")), reverse=True)[:5]
        if lost:
            lines.append("- **Mayor volumen perdido (sin factura):**")
            for row in lost:
                lines.append(
                    f"  - {row.get('Vendedor_Nombre')} — "
                    f"{int(as_float(row.get('Perdidas')))} perdidas "
                    f"({format_pct(as_float(row.get('Tasa_Conversion_Pct')))})"
                )
    else:
        lines.append("- **Sin datos de embudo cotización (Q12 vacío).**")

    lines.append("")
    lines.append("### 3.9 Inventario crítico y quiebres (InvDetalleExistencias)")
    if inv_summary:
        lines.append(
            f"- **SKUs críticos (top 25):** {int(as_float(inv_summary.get('SKUs_Criticos'))):,} | "
            f"**Quiebre <7d:** {int(as_float(inv_summary.get('SKUs_Quiebre_7d'))):,} | "
            f"**Stock ≤10:** {int(as_float(inv_summary.get('SKUs_Stock_Bajo'))):,} | "
            f"**Cobertura prom.:** {as_float(inv_summary.get('Promedio_Dias_Cobertura')):.1f} días"
        )
        lines.append("- **Top 10 SKUs por riesgo de quiebre (menor cobertura):**")
        for row in q13[:10]:
            dias = row.get("Dias_Cobertura")
            dias_txt = f"{as_float(dias):.1f}" if dias is not None else "—"
            lines.append(
                f"  - {row.get('SKU')} | {row.get('Producto', '')[:50]} | "
                f"{row.get('AlmacenCodigo')} | Stock: {as_float(row.get('Saldo_Actual')):.0f} | "
                f"Venta 90d: {as_float(row.get('Cantidad_90d')):.0f} | "
                f"Cobertura: {dias_txt}d | {row.get('Prioridad')}"
            )
    else:
        lines.append("- **Sin datos de inventario crítico (Q13 vacío).**")

    lines.append("")
    lines.append("### 3.10 OTIF — cumplimiento de entregas (InvHistoricoEntregas)")
    if otif_summary:
        lines.append(
            f"- **Total entregas:** {int(as_float(otif_summary.get('Total_Entregas'))):,} | "
            f"**A tiempo:** {int(as_float(otif_summary.get('Entregas_A_Tiempo'))):,} | "
            f"**OTIF:** {format_pct(as_float(otif_summary.get('OTIF_Pct')))} | "
            f"**Lead prom.:** {as_float(otif_summary.get('Lead_Time_Promedio_Dias')):.1f}d | "
            f"**Fill rate:** {format_pct(as_float(otif_summary.get('Fill_Rate_Pct')))}"
        )
        lines.append("- **Bodegas con peor OTIF:**")
        for row in q14[:5]:
            lines.append(
                f"  - {row.get('Almacen_Codigo')} | "
                f"OTIF: {format_pct(as_float(row.get('OTIF_Pct')))} | "
                f"Entregas: {int(as_float(row.get('Total_Entregas')))} | "
                f"Lead: {as_float(row.get('Lead_Time_Promedio_Dias')):.1f}d"
            )
    else:
        lines.append("- **Sin datos OTIF (Q14 vacío).**")

    lines.append("")
    lines.append("### 3.11 Conciliación devoluciones ERP vs BI")
    if dev_summary:
        lines.append(
            f"- **Unidades ERP:** {int(as_float(dev_summary.get('Unidades_ERP'))):,} | "
            f"**BI:** {int(as_float(dev_summary.get('Unidades_BI'))):,} | "
            f"**Conciliación:** {format_pct(as_float(dev_summary.get('Conciliacion_Pct')))} | "
            f"**Tasa validada:** {format_pct(as_float(dev_summary.get('Tasa_Devolucion_Validada_Pct')))} | "
            f"**Brechas categoría:** {int(as_float(dev_summary.get('Categorias_Con_Diferencia')))}"
        )
        gaps = sorted(
            q15,
            key=lambda r: abs(as_float(r.get("Diferencia_Unidades"))),
            reverse=True,
        )
        gap_rows = [r for r in gaps if as_float(r.get("Diferencia_Unidades")) != 0][:5]
        if gap_rows:
            lines.append("- **Categorías con brecha (top):**")
            for row in gap_rows:
                lines.append(
                    f"  - {row.get('Categoria')} | ERP: {int(as_float(row.get('Unidades_ERP')))} | "
                    f"BI: {int(as_float(row.get('Unidades_BI')))} | "
                    f"Δ: {int(as_float(row.get('Diferencia_Unidades')))}"
                )
        else:
            lines.append("- **Sin brechas por categoría en el periodo (ERP = BI).**")
        erosion = sorted(
            q15, key=lambda r: as_float(r.get("Impacto_Margen_BI")), reverse=True
        )[:5]
        lines.append("- **Mayor erosión de margen (devoluciones):**")
        for row in erosion:
            lines.append(
                f"  - {row.get('Categoria')} | "
                f"Impacto: {format_currency(as_float(row.get('Impacto_Margen_BI')))} | "
                f"Tasa validada: {format_pct(as_float(row.get('Tasa_Devolucion_Validada_Pct')))}"
            )
    else:
        lines.append("- **Sin datos de conciliación devoluciones (Q15 vacío).**")

    lines.append("")
    lines.append("### 3.12 Factura electrónica DIAN")
    if fe_summary:
        lines.append(
            f"- **Emitidas:** {int(as_float(fe_summary.get('Emitidas'))):,} | "
            f"**Aceptadas:** {int(as_float(fe_summary.get('Aceptadas'))):,} | "
            f"**Rechazadas:** {int(as_float(fe_summary.get('Rechazadas'))):,} | "
            f"**Aceptación:** {format_pct(as_float(fe_summary.get('Tasa_Aceptacion_Pct')))} | "
            f"**Rechazo:** {format_pct(as_float(fe_summary.get('Tasa_Rechazo_Pct')))}"
        )
        rechazos = [r for r in q16 if as_float(r.get("Rechazadas")) > 0][:5]
        if rechazos:
            lines.append("- **Tipos de documento con rechazos:**")
            for row in rechazos:
                lines.append(
                    f"  - {row.get('DocumentosCodigo')} | "
                    f"Rechazadas: {int(as_float(row.get('Rechazadas')))} | "
                    f"Rechazo: {format_pct(as_float(row.get('Tasa_Rechazo_Pct')))}"
                )
        else:
            lines.append("- **Sin rechazos DIAN en el periodo.**")
        top_emit = sorted(q16, key=lambda r: as_float(r.get("Emitidas")), reverse=True)[
            :5
        ]
        lines.append("- **Mayor volumen electrónico:**")
        for row in top_emit:
            lines.append(
                f"  - {row.get('DocumentosCodigo')} | "
                f"Emitidas: {int(as_float(row.get('Emitidas')))} | "
                f"Aceptación: {format_pct(as_float(row.get('Tasa_Aceptacion_Pct')))}"
            )
    else:
        lines.append("- **Sin datos de factura electrónica (Q16 vacío).**")

    lines.append("")
    lines.append("### 3.13 Contabilidad — PyG PUC")
    if cont_summary:
        lines.append(
            f"- **Ingresos (créditos clase 4):** "
            f"{format_currency(as_float(cont_summary.get('Ingresos_Creditos')))} | "
            f"**Costos (débitos clase 6):** "
            f"{format_currency(as_float(cont_summary.get('Costos_Debitos')))} | "
            f"**Gastos (débitos clase 5):** "
            f"{format_currency(as_float(cont_summary.get('Gastos_Debitos')))}"
        )
        lines.append(
            f"- **Margen bruto contable:** "
            f"{format_currency(as_float(cont_summary.get('Margen_Bruto_Contable')))} | "
            f"**Margen %:** {format_pct(as_float(cont_summary.get('Margen_Contable_Pct')))}"
        )
        for row in q17:
            lines.append(
                f"  - Clase {row.get('Clase_Puc')} ({row.get('Tipo_Cuenta')}) | "
                f"Créditos: {format_currency(as_float(row.get('Total_Creditos')))} | "
                f"Débitos: {format_currency(as_float(row.get('Total_Debitos')))} | "
                f"Saldo: {format_currency(as_float(row.get('Saldo_Neto')))}"
            )
    else:
        lines.append("- **Sin datos contables (Q17 vacío).**")

    lines.append("")
    lines.append("## 4) Weekly Action Plan (Execution)")
    lines.append("")
    lines.append(
        "| Priority | Lever | Action | Owner | Due Date | Expected KPI Impact |"
    )
    lines.append("|---|---|---|---|---|---|")
    lines.append("| High | Pricing |  |  |  | +pp margen |")
    lines.append("| High | Mix/Bundles |  |  |  | +ticket / +margen |")
    lines.append(
        "| High | Customer Terms / Cobranza | Revisar clientes sobre cupo y >90d vencidos | Finanzas |  | -DSO / -cartera 90+ |"
    )
    lines.append("| Medium | Customer Terms |  |  |  | +margen cliente |")
    lines.append("| Medium | Inventory |  |  |  | +capital / +margen |")

    lines.append("")
    lines.append("## 6) AI Narrative Summary")
    lines.append("")
    narrative = generate_narrative(scorecard, results)
    lines.append(narrative)
    lines.append("")

    lines.append("## 5) SQL Blocks Used (Traceability)")
    lines.append("")
    for q in range(1, 18):
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
    q1_start = trend_start_for(start_date)
    prev_start, prev_end = previous_iso_week_range(start_date)

    results: Dict[str, List[Dict[str, Any]]] = {}
    conn = get_connection()
    try:
        for key in [f"Q{i}" for i in range(1, 18)]:
            # Q1 needs multi-week history so north-star baselines are meaningful
            # when the board window is a single ISO week.
            q_start = q1_start if key == "Q1" else start_date
            query = render_query(blocks[key], q_start, end_date)
            results[key] = execute_query(conn, query)
        results["Q2_prev"] = execute_query(
            conn, render_query(blocks["Q2"], prev_start, prev_end)
        )
    finally:
        conn.close()

    scorecard = compute_scorecard(results, focus_end=end_date)
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
