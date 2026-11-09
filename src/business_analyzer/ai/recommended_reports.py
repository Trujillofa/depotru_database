"""Curated manager-report shortcuts for the Vanna web UI."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from business_analyzer.reports.kpi_control_board import (
    iso_weeks_in_year,
    last_completed_iso_week,
)
from business_analyzer.reports.rotacion_existencias import default_as_of_date

MONTH_NAMES_ES: Dict[int, str] = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}

REPORT_GROUPS: Dict[str, str] = {
    "manager": "Gerencial",
    "manager-ai": "Gerencial",
    "kpi-control-board": "Gerencial",
    "manager-sika-center": "Sedes",
    "manager-calle-5": "Sedes",
    "manager-almacen-principal": "Sedes",
    "rotacion-existencias": "Operación",
    "cartera-aging": "Operación",
    "tsol-sika": "TSOL",
    "tsol-pintuco": "TSOL",
}


def previous_calendar_month(*, today: Optional[date] = None) -> tuple[int, int]:
    """Return (year, month) for the month before ``today``."""
    ref = today or date.today()
    if ref.month == 1:
        return ref.year - 1, 12
    return ref.year, ref.month - 1


def build_manager_action(
    *,
    year: int,
    month: int,
    fmt: str = "html",
    branch: Optional[str] = None,
    with_ai: bool = False,
) -> Dict[str, Any]:
    month_name = MONTH_NAMES_ES[month]
    question = f"Genera el informe gerencial de {month_name.lower()} {year}"
    if fmt == "pdf":
        question += " en PDF"
    elif fmt == "json":
        question += " en JSON"
    if with_ai:
        question += " con análisis de IA"
    if branch:
        question += f" para {branch.replace('_', ' ')}"
    action: Dict[str, Any] = {
        "type": "generate_report",
        "year": year,
        "month": month,
        "format": fmt,
        "question": question,
    }
    if branch:
        action["branch"] = branch
    return action


FORMAT_OPTIONS: List[Dict[str, str]] = [
    {"value": "html", "label": "HTML"},
    {"value": "pdf", "label": "PDF"},
    {"value": "json", "label": "JSON"},
]


def get_recommended_report_templates() -> List[Dict[str, Any]]:
    """Declarative catalog; period and output format are chosen in the UI."""
    return [
        {
            "id": "manager",
            "title": "Informe gerencial",
            "description": "Ventas consolidadas, KPIs y contabilidad ERP.",
            "template": {},
        },
        {
            "id": "manager-ai",
            "title": "Informe gerencial con IA",
            "description": "Narrativa mensual generada por IA.",
            "template": {"with_ai": True},
        },
        {
            "id": "manager-sika-center",
            "title": "Informe Sika Center",
            "description": "Ventas de la sede Sika Center (FEF).",
            "template": {"branch": "sika_center"},
        },
        {
            "id": "manager-calle-5",
            "title": "Informe Calle 5",
            "description": "Ventas de la sede Calle 5 (FET).",
            "template": {"branch": "calle_5"},
        },
        {
            "id": "manager-almacen-principal",
            "title": "Informe Almacén Principal",
            "description": "Ventas del almacén principal (FED).",
            "template": {"branch": "almacen_principal"},
        },
        {
            "id": "kpi-control-board",
            "title": "KPI Control Board",
            "description": "Semanal: scorecard Q1–Q17, cartera, OTIF y ERP.",
            "period_type": "week",
            "template": {"report_kind": "kpi_control_board"},
        },
        {
            "id": "rotacion-existencias",
            "title": "Rotación de Existencias",
            "description": "Quiebre, capital atrapado y traslados por bodega.",
            "period_type": "as_of_date",
            "template": {"report_kind": "rotacion_existencias"},
        },
        {
            "id": "cartera-aging",
            "title": "Cartera / Aging",
            "description": "Mora por buckets, top vencidos y plan de cobro.",
            "period_type": "as_of_date",
            "template": {"report_kind": "cartera_aging"},
        },
        {
            "id": "tsol-sika",
            "title": "TSOL Sika",
            "description": "Excel Ventas + Inventario, mes o YTD.",
            "period_type": "tsol",
            "template": {"brand": "sika"},
        },
        {
            "id": "tsol-pintuco",
            "title": "TSOL Pintuco",
            "description": "Excel línea 009, mes o YTD.",
            "period_type": "tsol",
            "template": {"brand": "pintuco"},
        },
    ]


def get_recommended_reports(*, today: Optional[date] = None) -> List[Dict[str, Any]]:
    """Catalog entries with default-period actions for API consumers."""
    default_year, default_month = previous_calendar_month(today=today)
    reports: List[Dict[str, Any]] = []
    default_iso_year, default_iso_week = last_completed_iso_week(today=today)
    as_of = default_as_of_date(today=today)
    for entry in get_recommended_report_templates():
        if entry.get("period_type") == "week":
            reports.append(
                {
                    **entry,
                    "action": {
                        "type": "generate_kpi_board",
                        "iso_year": default_iso_year,
                        "iso_week": default_iso_week,
                    },
                }
            )
            continue
        if entry.get("period_type") == "as_of_date":
            kind = (entry.get("template") or {}).get("report_kind")
            if kind == "cartera_aging":
                action_type = "generate_cartera"
            else:
                action_type = "generate_rotacion"
            reports.append(
                {
                    **entry,
                    "action": {
                        "type": action_type,
                        "as_of_date": as_of,
                    },
                }
            )
            continue
        if entry.get("period_type") == "tsol":
            brand = (entry.get("template") or {}).get("brand") or "sika"
            reports.append(
                {
                    **entry,
                    "action": {
                        "type": "generate_tsol",
                        "brand": brand,
                        "year": default_year,
                        "month": default_month,
                        "ytd": False,
                    },
                }
            )
            continue
        template = entry["template"]
        action = build_manager_action(
            year=default_year,
            month=default_month,
            fmt=template.get("format", "html"),
            branch=template.get("branch"),
            with_ai=template.get("with_ai", False),
        )
        reports.append({**entry, "action": action})
    for report in reports:
        report["group"] = REPORT_GROUPS.get(report["id"], "Otros")
    return reports


def recommended_reports_payload(*, today: Optional[date] = None) -> Dict[str, Any]:
    default_year, default_month = previous_calendar_month(today=today)
    default_iso_year, default_iso_week = last_completed_iso_week(today=today)
    return {
        "reports": get_recommended_reports(today=today),
        "default_year": default_year,
        "default_month": default_month,
        "default_iso_year": default_iso_year,
        "default_iso_week": default_iso_week,
        "max_iso_week": iso_weeks_in_year(default_iso_year),
        "default_as_of_date": default_as_of_date(today=today),
        "default_format": "html",
        "format_options": FORMAT_OPTIONS,
        "month_names": {str(k): v for k, v in MONTH_NAMES_ES.items()},
    }


RECOMMENDED_REPORTS_PANEL_HTML = """
<aside id="informes-recomendados" class="informes-recomendados"
       aria-label="Informes recomendados">
  <div class="ir-header">
    <div class="ir-header-row">
      <h2>Informes recomendados</h2>
      <span id="informes-count" class="ir-count" hidden></span>
    </div>
    <p class="informes-subtitle">Elige un informe, ajusta el periodo y genera.</p>
  </div>
  <div id="informes-recomendados-list" class="informes-recomendados-list"></div>
  <p id="informes-recomendados-status" class="informes-recomendados-status"
     aria-live="polite"></p>
</aside>
""".strip()


def inject_recommended_reports_ui(html: str) -> str:
    """Inject sidebar panel plus stylesheet/script links into Vanna index HTML."""
    if "informes-recomendados" in html:
        return html

    css_block = (
        '<link id="informes-recomendados-styles" rel="stylesheet" '
        'href="/assets/informes.css">'
    )
    if "</head>" in html:
        html = html.replace("</head>", f"{css_block}\n</head>", 1)

    body_tag = '<body class="bg-white dark:bg-slate-900">'
    if body_tag in html:
        html = html.replace(
            body_tag,
            '<body class="bg-white dark:bg-slate-900 informes-layout">',
            1,
        )
    elif "<body" in html:
        html = html.replace("<body", '<body class="informes-layout"', 1)

    app_div = '<div id="app"></div>'
    if app_div in html:
        html = html.replace(
            app_div,
            f"{app_div}\n    {RECOMMENDED_REPORTS_PANEL_HTML}",
            1,
        )

    script_block = (
        '<script id="informes-recomendados-loader" '
        'src="/assets/informes.js" defer></script>'
    )
    if "</body>" in html:
        html = html.replace("</body>", f"{script_block}\n  </body>", 1)

    return html
