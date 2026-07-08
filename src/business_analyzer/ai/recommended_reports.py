"""Curated manager-report shortcuts for the Vanna web UI."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

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


def _manager_action(
    *,
    year: int,
    month: int,
    fmt: str = "html",
    branch: Optional[str] = None,
    with_ai: bool = False,
) -> Dict[str, Any]:
    month_name = MONTH_NAMES_ES[month]
    question = f"Genera el informe gerencial de {month_name.lower()} {year}"
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


def get_recommended_reports(*, today: Optional[date] = None) -> List[Dict[str, Any]]:
    """Declarative catalog shared by API, UI, and tests."""
    prev_year, prev_month = previous_calendar_month(today=today)
    prev_label = MONTH_NAMES_ES[prev_month]

    return [
        {
            "id": "manager-prev-month-html",
            "title": f"Informe gerencial — {prev_label} {prev_year}",
            "description": (
                "Ventas consolidadas del mes anterior con KPIs, gráficos y "
                "contabilidad ERP (HTML)."
            ),
            "action": _manager_action(year=prev_year, month=prev_month, fmt="html"),
        },
        {
            "id": "manager-prev-month-pdf",
            "title": f"Informe gerencial PDF — {prev_label} {prev_year}",
            "description": "Mismo informe gerencial en formato PDF para gerencia.",
            "action": _manager_action(year=prev_year, month=prev_month, fmt="pdf"),
        },
        {
            "id": "manager-dic-2024-html",
            "title": "Informe gerencial — Diciembre 2024",
            "description": (
                "Cierre 2024: facturación, márgenes, clientes y ecuación contable."
            ),
            "action": _manager_action(year=2024, month=12, fmt="html"),
        },
        {
            "id": "manager-mayo-2024-ai",
            "title": "Informe gerencial con IA — Mayo 2024",
            "description": (
                "Informe de mayo 2024 con narrativa de insights generados por IA."
            ),
            "action": _manager_action(year=2024, month=5, fmt="html", with_ai=True),
        },
        {
            "id": "manager-sika-dic-2024",
            "title": "Informe Sika Center — Diciembre 2024",
            "description": "Ventas de la sede Sika Center (FEF) en diciembre 2024.",
            "action": _manager_action(
                year=2024, month=12, fmt="html", branch="sika_center"
            ),
        },
    ]


def recommended_reports_payload(*, today: Optional[date] = None) -> Dict[str, Any]:
    return {"reports": get_recommended_reports(today=today)}


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
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}
.informe-card:hover {
  border-color: #2563eb;
  box-shadow: 0 6px 18px rgba(37, 99, 235, 0.12);
  transform: translateY(-1px);
}
.informe-card:disabled {
  opacity: 0.65;
  cursor: wait;
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
}
.dark .informe-card-desc { color: #94a3b8; }
.informes-recomendados-status {
  margin: 0.85rem 0 0;
  font-size: 0.75rem;
  color: #166534;
  min-height: 1.1rem;
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
  <p class="informes-subtitle">Accesos directos al informe gerencial mensual (depotru-report).</p>
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

  function renderCard(report) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "informe-card";
    button.setAttribute("role", "listitem");
    button.dataset.reportId = report.id;
    button.innerHTML =
      '<span class="informe-card-title"></span><span class="informe-card-desc"></span>';
    button.querySelector(".informe-card-title").textContent = report.title;
    button.querySelector(".informe-card-desc").textContent = report.description;
    button.addEventListener("click", async () => {
      button.disabled = true;
      setStatus("Generando informe…", false);
      try {
        const result = await triggerReport(report.action || {});
        if (result.type === "manager_report") {
          setStatus(result.text || "Informe listo.", false);
          if (result.download_url) window.open(result.download_url, "_blank");
        } else if (result.type === "error") {
          setStatus(result.error || "Error generando el informe.", true);
        } else if (result.type === "text") {
          setStatus(result.text || "Indica el periodo del informe.", false);
        } else {
          setStatus("Respuesta inesperada del servidor.", true);
        }
      } catch (err) {
        setStatus("No se pudo contactar el servidor.", true);
      } finally {
        button.disabled = false;
      }
    });
    listEl.appendChild(button);
  }

  fetch("/api/v0/recommended_reports")
    .then((r) => r.json())
    .then((data) => {
      const reports = (data && data.reports) || [];
      if (!reports.length) {
        setStatus("No hay informes recomendados configurados.", true);
        return;
      }
      reports.forEach(renderCard);
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
