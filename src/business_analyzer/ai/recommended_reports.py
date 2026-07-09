"""Curated manager-report shortcuts for the Vanna web UI."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from business_analyzer.reports.kpi_control_board import (
    iso_weeks_in_year,
    last_completed_iso_week,
)

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
            "description": (
                "Ventas consolidadas con KPIs, gráficos y contabilidad ERP."
            ),
            "template": {},
        },
        {
            "id": "manager-ai",
            "title": "Informe gerencial con IA",
            "description": (
                "Informe mensual con narrativa de insights generados por IA."
            ),
            "template": {"with_ai": True},
        },
        {
            "id": "manager-sika-center",
            "title": "Informe Sika Center",
            "description": "Ventas de la sede Sika Center (FEF) para el periodo elegido.",
            "template": {"branch": "sika_center"},
        },
        {
            "id": "manager-calle-5",
            "title": "Informe Calle 5",
            "description": "Ventas de la sede Calle 5 (FET) para el periodo elegido.",
            "template": {"branch": "calle_5"},
        },
        {
            "id": "manager-almacen-principal",
            "title": "Informe Almacén Principal",
            "description": (
                "Ventas del almacén principal (FED) para el periodo elegido."
            ),
            "template": {"branch": "almacen_principal"},
        },
        {
            "id": "kpi-control-board",
            "title": "KPI Control Board",
            "description": (
                "Tablero semanal (lun–dom): scorecard Q1–Q17, cartera, OTIF "
                "y contabilidad ERP."
            ),
            "period_type": "week",
            "template": {"report_kind": "kpi_control_board"},
        },
    ]


def get_recommended_reports(*, today: Optional[date] = None) -> List[Dict[str, Any]]:
    """Catalog entries with default-period actions for API consumers."""
    default_year, default_month = previous_calendar_month(today=today)
    reports: List[Dict[str, Any]] = []
    default_iso_year, default_iso_week = last_completed_iso_week(today=today)
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
        template = entry["template"]
        action = build_manager_action(
            year=default_year,
            month=default_month,
            fmt=template.get("format", "html"),
            branch=template.get("branch"),
            with_ai=template.get("with_ai", False),
        )
        reports.append({**entry, "action": action})
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
        "default_format": "html",
        "format_options": FORMAT_OPTIONS,
        "month_names": {str(k): v for k, v in MONTH_NAMES_ES.items()},
    }


RECOMMENDED_REPORTS_CSS = """
#informes-recomendados {
  width: min(340px, 32vw);
  flex-shrink: 0;
  border-left: 1px solid #e5e7eb;
  background: linear-gradient(180deg, #f8fafc 0%, #eff6ff 100%);
  padding: 1rem 1rem 1.25rem;
  overflow-y: auto;
  max-height: 100vh;
  box-sizing: border-box;
}
.dark #informes-recomendados,
html.dark #informes-recomendados,
body.dark #informes-recomendados {
  border-left-color: #334155;
  background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
}
#informes-recomendados h2 {
  margin: 0 0 0.35rem;
  font-size: 1rem;
  font-weight: 700;
  color: #1e3a5f;
  letter-spacing: 0.01em;
}
.dark #informes-recomendados h2 { color: #e2e8f0; }
#informes-recomendados .informes-subtitle {
  margin: 0 0 0.85rem;
  font-size: 0.78rem;
  color: #64748b;
  line-height: 1.35;
}
.dark #informes-recomendados .informes-subtitle { color: #94a3b8; }
.informes-recomendados-list {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}
.informe-card {
  display: block;
  width: 100%;
  text-align: left;
  border: 1px solid #dbeafe;
  border-radius: 0.65rem;
  background: #ffffff;
  padding: 0.65rem 0.75rem;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.informe-card:hover {
  border-color: #2563eb;
  box-shadow: 0 6px 18px rgba(37, 99, 235, 0.12);
}
.informe-card.is-busy {
  opacity: 0.65;
  pointer-events: none;
}
.dark .informe-card {
  background: #1e293b;
  border-color: #334155;
  color: #e2e8f0;
}
.informe-card-title {
  display: block;
  font-size: 0.86rem;
  font-weight: 600;
  color: #1e3a5f;
  margin-bottom: 0.2rem;
}
.dark .informe-card-title { color: #f1f5f9; }
.informe-card-desc {
  display: block;
  font-size: 0.74rem;
  color: #64748b;
  line-height: 1.35;
  margin-bottom: 0.55rem;
}
.dark .informe-card-desc { color: #94a3b8; }
.informe-period {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  align-items: center;
}
.informe-month,
.informe-year,
.informe-week,
.informe-format {
  font-size: 0.78rem;
  border: 1px solid #cbd5e1;
  border-radius: 0.4rem;
  padding: 0.3rem 0.45rem;
  background: #f8fafc;
  color: #1e293b;
}
.informe-month { flex: 1 1 6.5rem; min-width: 0; }
.informe-year { width: 4.5rem; }
.informe-week { width: 4.5rem; }
.informe-format { flex: 1 1 4.5rem; min-width: 0; }
.dark .informe-month,
.dark .informe-year,
.dark .informe-week,
.dark .informe-format {
  background: #0f172a;
  border-color: #475569;
  color: #e2e8f0;
}
.informe-generate-btn {
  flex: 1 1 100%;
  margin-top: 0.15rem;
  font-size: 0.78rem;
  font-weight: 600;
  border: none;
  border-radius: 0.4rem;
  padding: 0.4rem 0.6rem;
  background: #2563eb;
  color: #ffffff;
  cursor: pointer;
  transition: background 0.15s;
}
.informe-generate-btn:hover { background: #1d4ed8; }
.informe-generate-btn:disabled {
  opacity: 0.65;
  cursor: wait;
}
.informes-recomendados-status {
  margin: 0.85rem 0 0;
  font-size: 0.75rem;
  color: #166534;
  min-height: 1.1rem;
  line-height: 1.35;
  word-break: break-word;
}
.informes-recomendados-status.is-error { color: #b91c1c; }
body.informes-layout {
  display: flex;
  flex-direction: row;
  align-items: stretch;
  min-height: 100vh;
  margin: 0;
}
body.informes-layout #app {
  flex: 1 1 auto;
  min-width: 0;
}
@media (max-width: 960px) {
  body.informes-layout { flex-direction: column; }
  #informes-recomendados {
    width: 100%;
    max-height: none;
    border-left: none;
    border-top: 1px solid #e5e7eb;
  }
}
""".strip()


RECOMMENDED_REPORTS_PANEL_HTML = """
<aside id="informes-recomendados" class="informes-recomendados" aria-label="Informes recomendados">
  <h2>Informes recomendados</h2>
  <p class="informes-subtitle">Informes mensuales (mes/año/formato) o KPI semanal (año/semana ISO).</p>
  <div id="informes-recomendados-list" class="informes-recomendados-list" role="list"></div>
  <p id="informes-recomendados-status" class="informes-recomendados-status" aria-live="polite"></p>
</aside>
""".strip()


RECOMMENDED_REPORTS_JS = """
(function () {
  const listEl = document.getElementById("informes-recomendados-list");
  const statusEl = document.getElementById("informes-recomendados-status");
  if (!listEl) return;

  function setStatus(message, isError) {
    if (!statusEl) return;
    statusEl.textContent = message || "";
    statusEl.classList.toggle("is-error", Boolean(isError));
  }

  function buildAction(template, year, month, fmt, monthNames) {
    const monthName = (monthNames[String(month)] || "").toLowerCase();
    let question = "Genera el informe gerencial de " + monthName + " " + year;
    if (fmt === "pdf") question += " en PDF";
    else if (fmt === "json") question += " en JSON";
    if (template && template.with_ai) question += " con análisis de IA";
    const branch = template && template.branch;
    if (branch) question += " para " + String(branch).replace(/_/g, " ");
    const action = {
      type: "generate_report",
      year: year,
      month: month,
      format: fmt,
      question: question,
    };
    if (branch) action.branch = branch;
    return action;
  }

  function shortStatus(result) {
    if (result.status_text) return result.status_text;
    const fmt = String(result.format || "html").toUpperCase();
    return "✓ Informe " + fmt + " listo.";
  }

  async function triggerReport(action) {
    const payload = {
      year: action.year,
      month: action.month,
      format: action.format || "html",
      question: action.question || null,
      branch: action.branch || null,
    };
    const response = await fetch("/api/v0/generate_report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return response.json();
  }

  async function triggerKpiBoard(isoYear, isoWeek) {
    const response = await fetch("/api/v0/generate_kpi_board", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ iso_year: isoYear, iso_week: isoWeek }),
    });
    return response.json();
  }

  function handleGenerateResult(result) {
    if (result.type === "manager_report" || result.type === "kpi_board") {
      setStatus(shortStatus(result), false);
      if (result.download_url) window.open(result.download_url, "_blank");
      return;
    }
    if (result.type === "error") {
      setStatus(result.error || "Error generando el informe.", true);
      return;
    }
    if (result.type === "text") {
      setStatus(result.text || "Indica el periodo del informe.", false);
      return;
    }
    setStatus("Respuesta inesperada del servidor.", true);
  }

  function renderWeekCard(report, defaults) {
    const card = document.createElement("div");
    card.className = "informe-card";
    card.setAttribute("role", "listitem");
    card.dataset.reportId = report.id;

    const title = document.createElement("span");
    title.className = "informe-card-title";
    title.textContent = report.title;

    const desc = document.createElement("span");
    desc.className = "informe-card-desc";
    desc.textContent = report.description;

    const period = document.createElement("div");
    period.className = "informe-period";

    const yearInput = document.createElement("input");
    yearInput.type = "number";
    yearInput.className = "informe-year";
    yearInput.min = "2015";
    yearInput.max = "2035";
    yearInput.value = String(defaults.iso_year);
    yearInput.setAttribute("aria-label", "Año ISO del tablero");

    const weekInput = document.createElement("input");
    weekInput.type = "number";
    weekInput.className = "informe-week";
    weekInput.min = "1";
    weekInput.max = String(defaults.max_iso_week || 53);
    weekInput.value = String(defaults.iso_week);
    weekInput.setAttribute("aria-label", "Semana ISO");

    const generateBtn = document.createElement("button");
    generateBtn.type = "button";
    generateBtn.className = "informe-generate-btn";
    generateBtn.textContent = "Generar tablero";

    period.appendChild(yearInput);
    period.appendChild(weekInput);
    period.appendChild(generateBtn);

    card.appendChild(title);
    card.appendChild(desc);
    card.appendChild(period);
    listEl.appendChild(card);

    generateBtn.addEventListener("click", async () => {
      const isoYear = parseInt(yearInput.value, 10);
      const isoWeek = parseInt(weekInput.value, 10);
      if (!isoYear || !isoWeek || isoWeek < 1 || isoWeek > 53) {
        setStatus("Indica un año y semana ISO válidos.", true);
        return;
      }
      card.classList.add("is-busy");
      generateBtn.disabled = true;
      setStatus("Generando tablero KPI…", false);
      try {
        const result = await triggerKpiBoard(isoYear, isoWeek);
        handleGenerateResult(result);
      } catch (err) {
        setStatus("No se pudo contactar el servidor.", true);
      } finally {
        card.classList.remove("is-busy");
        generateBtn.disabled = false;
      }
    });
  }

  function renderCard(report, defaults, monthNames, formatOptions) {
    if (report.period_type === "week") {
      renderWeekCard(report, defaults);
      return;
    }
    const card = document.createElement("div");
    card.className = "informe-card";
    card.setAttribute("role", "listitem");
    card.dataset.reportId = report.id;

    const title = document.createElement("span");
    title.className = "informe-card-title";
    title.textContent = report.title;

    const desc = document.createElement("span");
    desc.className = "informe-card-desc";
    desc.textContent = report.description;

    const period = document.createElement("div");
    period.className = "informe-period";

    const monthSelect = document.createElement("select");
    monthSelect.className = "informe-month";
    monthSelect.setAttribute("aria-label", "Mes del informe");
    Object.keys(monthNames)
      .map(Number)
      .sort((a, b) => a - b)
      .forEach((m) => {
        const opt = document.createElement("option");
        opt.value = String(m);
        opt.textContent = monthNames[String(m)];
        if (m === defaults.month) opt.selected = true;
        monthSelect.appendChild(opt);
      });

    const yearInput = document.createElement("input");
    yearInput.type = "number";
    yearInput.className = "informe-year";
    yearInput.min = "2015";
    yearInput.max = "2035";
    yearInput.value = String(defaults.year);
    yearInput.setAttribute("aria-label", "Año del informe");

    const formatSelect = document.createElement("select");
    formatSelect.className = "informe-format";
    formatSelect.setAttribute("aria-label", "Formato del informe");
    formatOptions.forEach((opt) => {
      const option = document.createElement("option");
      option.value = opt.value;
      option.textContent = opt.label;
      if (opt.value === defaults.format) option.selected = true;
      formatSelect.appendChild(option);
    });

    const generateBtn = document.createElement("button");
    generateBtn.type = "button";
    generateBtn.className = "informe-generate-btn";
    generateBtn.textContent = "Generar informe";

    period.appendChild(monthSelect);
    period.appendChild(yearInput);
    period.appendChild(formatSelect);
    period.appendChild(generateBtn);

    card.appendChild(title);
    card.appendChild(desc);
    card.appendChild(period);
    listEl.appendChild(card);

    generateBtn.addEventListener("click", async () => {
      const year = parseInt(yearInput.value, 10);
      const month = parseInt(monthSelect.value, 10);
      if (!year || !month || month < 1 || month > 12) {
        setStatus("Indica un año y mes válidos.", true);
        return;
      }
      card.classList.add("is-busy");
      generateBtn.disabled = true;
      setStatus("Generando informe…", false);
      try {
        const fmt = formatSelect.value || "html";
        const action = buildAction(
          report.template || {},
          year,
          month,
          fmt,
          monthNames
        );
        const result = await triggerReport(action);
        handleGenerateResult(result);
      } catch (err) {
        setStatus("No se pudo contactar el servidor.", true);
      } finally {
        card.classList.remove("is-busy");
        generateBtn.disabled = false;
      }
    });
  }

  fetch("/api/v0/recommended_reports")
    .then((r) => r.json())
    .then((data) => {
      const reports = (data && data.reports) || [];
      const monthNames = (data && data.month_names) || {};
      const formatOptions = (data && data.format_options) || [
        { value: "html", label: "HTML" },
        { value: "pdf", label: "PDF" },
      ];
      const defaults = {
        year: (data && data.default_year) || new Date().getFullYear(),
        month: (data && data.default_month) || new Date().getMonth() || 12,
        format: (data && data.default_format) || "html",
        iso_year: (data && data.default_iso_year) || new Date().getFullYear(),
        iso_week: (data && data.default_iso_week) || 1,
        max_iso_week: (data && data.max_iso_week) || 53,
      };
      if (!reports.length) {
        setStatus("No hay informes recomendados configurados.", true);
        return;
      }
      reports.forEach((report) =>
        renderCard(report, defaults, monthNames, formatOptions)
      );
    })
    .catch(() => setStatus("No se pudo cargar la lista de informes.", true));
})();
""".strip()


def inject_recommended_reports_ui(html: str) -> str:
    """Inject sidebar panel, styles, and loader script into Vanna index HTML."""
    if "informes-recomendados" in html:
        return html

    css_block = (
        f'<style id="informes-recomendados-styles">{RECOMMENDED_REPORTS_CSS}</style>'
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
        f'<script id="informes-recomendados-loader">'
        f"{RECOMMENDED_REPORTS_JS}</script>"
    )
    if "</body>" in html:
        html = html.replace("</body>", f"{script_block}\n  </body>", 1)

    return html
