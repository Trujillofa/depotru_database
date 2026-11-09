(function () {
  "use strict";

  const listEl = document.getElementById("informes-recomendados-list");
  const statusEl = document.getElementById("informes-recomendados-status");
  const appEl = document.getElementById("app");
  if (!listEl) return;

  const reportById = new Map();
  let staticLabelsApplied = false;
  let polishScheduled = false;

  const MONTHS_SHORT = [
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
  ];

  function formatLongDate(value) {
    const match = /^([0-9]{4})-([0-9]{2})-([0-9]{2})$/.exec(value || "");
    if (!match) return "";
    const date = new Date(
      Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
    );
    return (
      date.getUTCDate() +
      " " +
      MONTHS_SHORT[date.getUTCMonth()] +
      " " +
      date.getUTCFullYear()
    );
  }

  function formatWeekLabel(year, week) {
    const isoYear = Number(year);
    const isoWeek = Number(week);
    if (!isoYear || !isoWeek || isoWeek < 1 || isoWeek > 53) return "";
    const jan4 = new Date(Date.UTC(isoYear, 0, 4));
    const weekday = jan4.getUTCDay() || 7;
    const monday = new Date(jan4);
    monday.setUTCDate(jan4.getUTCDate() - weekday + 1 + (isoWeek - 1) * 7);
    const sunday = new Date(monday);
    sunday.setUTCDate(monday.getUTCDate() + 6);

    const startMonth = MONTHS_SHORT[monday.getUTCMonth()];
    const endMonth = MONTHS_SHORT[sunday.getUTCMonth()];
    const range =
      startMonth === endMonth
        ? monday.getUTCDate() + "–" + sunday.getUTCDate() + " " + endMonth
        : monday.getUTCDate() +
          " " +
          startMonth +
          "–" +
          sunday.getUTCDate() +
          " " +
          endMonth;
    return "Semana " + isoWeek + " · " + range;
  }

  const REPORT_TYPES = {
    month: {
      endpoint: "/api/v0/generate_report",
      fields: ["month", "year", "format"],
      payload: (values, report) => ({
        year: Number(values.year),
        month: Number(values.month),
        format: values.format,
        branch: (report.template && report.template.branch) || null,
      }),
      validate: (values) =>
        !Number(values.year) || !Number(values.month) ||
        Number(values.month) < 1 || Number(values.month) > 12
          ? "Indica un año y mes válidos."
          : null,
      button: () => "Generar informe",
    },
    week: {
      endpoint: "/api/v0/generate_kpi_board",
      fields: ["isoYear", "isoWeek"],
      payload: (values) => ({
        iso_year: Number(values.isoYear),
        iso_week: Number(values.isoWeek),
      }),
      validate: (values) =>
        !Number(values.isoYear) ||
        !Number(values.isoWeek) ||
        Number(values.isoWeek) < 1 ||
        Number(values.isoWeek) > 53
          ? "Indica un año y semana ISO válidos."
          : null,
      button: () => "Generar tablero",
    },
    as_of_date: {
      endpoint: (report) =>
        (report.template && report.template.report_kind) === "cartera_aging"
          ? "/api/v0/generate_cartera"
          : "/api/v0/generate_rotacion",
      fields: ["date", "format"],
      formats: [
        { value: "html", label: "HTML" },
        { value: "pdf", label: "PDF" },
      ],
      payload: (values) => ({
        as_of_date: values.date,
        format: values.format,
      }),
      validate: (values) =>
        /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(values.date || "")
          ? null
          : "Indica una fecha válida (AAAA-MM-DD).",
      button: (report) =>
        (report.template && report.template.report_kind) === "cartera_aging"
          ? "Generar cartera"
          : "Generar rotación",
    },
    tsol: {
      endpoint: "/api/v0/generate_tsol",
      fields: ["month", "year", "ytd"],
      payload: (values, report) => ({
        brand: (report.template && report.template.brand) || "sika",
        year: Number(values.year),
        month: Number(values.month),
        ytd: values.ytd === "1",
      }),
      validate: (values) =>
        !Number(values.year) || !Number(values.month)
          ? "Indica año y mes para TSOL."
          : null,
      button: () => "Generar Excel",
    },
  };

  function numberControl(name, value, min, max, className, label) {
    const input = document.createElement("input");
    input.type = "number";
    input.name = name;
    input.className = className;
    input.min = String(min);
    input.max = String(max);
    input.value = String(value);
    input.setAttribute("aria-label", label);
    return input;
  }

  function labeledNumberControl(name, value, min, max, className, label) {
    const wrap = document.createElement("label");
    wrap.className = "informe-field";
    const caption = document.createElement("span");
    caption.className = "informe-field-label";
    caption.textContent = label;
    wrap.appendChild(caption);
    wrap.appendChild(
      numberControl(name, value, min, max, className, label)
    );
    return wrap;
  }

  function selectControl(name, value, options, className, label) {
    const select = document.createElement("select");
    select.name = name;
    select.className = className;
    select.setAttribute("aria-label", label);
    options.forEach((option) => {
      const el = document.createElement("option");
      el.value = String(option.value);
      el.textContent = option.label;
      if (String(option.value) === String(value)) el.selected = true;
      select.appendChild(el);
    });
    return select;
  }

  function dateControl(value) {
    const input = document.createElement("input");
    input.type = "date";
    input.name = "date";
    input.className = "informe-as-of";
    input.value = value || "";
    input.lang = "es-CO";
    input.setAttribute("aria-label", "Fecha de referencia");
    return input;
  }

  function ytdControl() {
    const label = document.createElement("label");
    label.className = "informe-ytd-label";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "ytd";
    input.value = "1";
    input.className = "informe-ytd";
    input.setAttribute("aria-label", "Año a la fecha");
    label.appendChild(input);
    label.appendChild(document.createTextNode(" YTD"));
    return label;
  }

  const FIELD_BUILDERS = {
    month: (ctx) =>
      selectControl(
        "month",
        ctx.defaults.month,
        ctx.monthOptions,
        "informe-month",
        "Mes del informe"
      ),
    year: (ctx) =>
      numberControl(
        "year",
        ctx.defaults.year,
        2015,
        2035,
        "informe-year",
        "Año del informe"
      ),
    format: (ctx) =>
      selectControl(
        "format",
        ctx.defaults.format,
        ctx.formatOptions,
        "informe-format",
        "Formato del informe"
      ),
    isoYear: (ctx) =>
      labeledNumberControl(
        "isoYear",
        ctx.defaults.isoYear,
        2015,
        2035,
        "informe-year",
        "Año"
      ),
    isoWeek: (ctx) =>
      labeledNumberControl(
        "isoWeek",
        ctx.defaults.isoWeek,
        1,
        ctx.defaults.maxIsoWeek,
        "informe-week",
        "Semana"
      ),
    date: (ctx) => dateControl(ctx.defaults.asOfDate),
    ytd: () => ytdControl(),
  };

  function postJSON(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(async (response) => {
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error((data && data.error) || "HTTP " + response.status);
      }
      if (!data) throw new Error("Respuesta vacía del servidor.");
      return data;
    });
  }

  function setStatus(message, isError) {
    if (!statusEl) return;
    statusEl.textContent = message || "";
    statusEl.classList.toggle("is-error", Boolean(isError));
  }

  function setCardStatus(form, message, options) {
    const status = form.querySelector(".informe-status");
    if (!status) return;
    const opts = options || {};
    status.textContent = message || "";
    status.classList.toggle("is-error", Boolean(opts.error));
    if (opts.link) {
      const link = document.createElement("a");
      link.href = opts.link;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = "Abrir informe";
      status.appendChild(document.createTextNode(" "));
      status.appendChild(link);
    }
  }

  function showResult(form, result) {
    if (!result || typeof result !== "object") {
      setCardStatus(form, "Respuesta inesperada del servidor.", { error: true });
      return;
    }
    if (result.type === "error") {
      setCardStatus(form, result.error || "Error generando el informe.", {
        error: true,
      });
      return;
    }
    if (result.type === "text") {
      setCardStatus(form, result.text || "Indica el periodo del informe.");
      return;
    }
    if (
      ["manager_report", "kpi_board", "rotacion", "cartera", "tsol"].includes(
        result.type
      )
    ) {
      const format = String(result.format || "html").toUpperCase();
      setCardStatus(form, result.status_text || "✓ Informe " + format + " listo.", {
        link: result.download_url || null,
      });
      return;
    }
    setCardStatus(form, "Respuesta inesperada del servidor.", { error: true });
  }

  function summaryFor(report) {
    const summary = document.createElement("summary");
    summary.className = "informe-card-head";

    const textWrap = document.createElement("span");
    textWrap.className = "informe-card-text";

    const title = document.createElement("span");
    title.className = "informe-card-title";
    const fullTitle = report.title || "";
    const shortTitle = fullTitle.replace(/^Informe\s+/i, "");
    title.textContent = shortTitle.charAt(0).toUpperCase() + shortTitle.slice(1);
    title.title = fullTitle;
    textWrap.appendChild(title);

    const desc = document.createElement("span");
    desc.className = "informe-card-desc";
    desc.textContent = report.description || "";
    desc.title = report.description || "";
    textWrap.appendChild(desc);

    summary.appendChild(textWrap);
    const chevron = document.createElement("span");
    chevron.className = "informe-chevron";
    chevron.setAttribute("aria-hidden", "true");
    chevron.innerHTML =
      '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" ' +
      'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
      'stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>';
    summary.appendChild(chevron);
    return summary;
  }

  function buildCard(report, ctx) {
    const type = REPORT_TYPES[report.period_type] ? report.period_type : "month";
    const spec = REPORT_TYPES[type];

    const details = document.createElement("details");
    details.className = "informe-card";
    details.name = "informes";
    details.dataset.reportId = report.id;
    details.dataset.type = type;
    details.setAttribute("role", "listitem");
    details.appendChild(summaryFor(report));

    const cardCtx = spec.formats
      ? Object.assign({}, ctx, { formatOptions: spec.formats })
      : ctx;

    const form = document.createElement("form");
    form.className = "informe-card-body";
    form.noValidate = true;

    const period = document.createElement("div");
    period.className = "informe-period";
    spec.fields.forEach((field) => {
      period.appendChild(FIELD_BUILDERS[field](cardCtx));
    });

    const button = document.createElement("button");
    button.type = "submit";
    button.className = "informe-generate-btn";
    button.textContent = spec.button(report);
    period.appendChild(button);

    let hintText = "";
    if (type === "week") {
      hintText = formatWeekLabel(cardCtx.defaults.isoYear, cardCtx.defaults.isoWeek);
    } else if (type === "as_of_date") {
      hintText = formatLongDate(cardCtx.defaults.asOfDate);
    }
    const hint = document.createElement("p");
    hint.className = "informe-hint";
    hint.textContent = hintText;
    hint.hidden = !hintText;

    const status = document.createElement("p");
    status.className = "informe-status";
    status.setAttribute("role", "status");
    status.setAttribute("aria-live", "polite");

    form.appendChild(period);
    form.appendChild(hint);
    form.appendChild(status);
    details.appendChild(form);
    return details;
  }

  function refreshHint(form) {
    const details = form.closest("details");
    const hint = form.querySelector(".informe-hint");
    if (!details || !hint) return;
    const values = Object.fromEntries(new FormData(form).entries());
    let text = "";
    if (details.dataset.type === "week") {
      text = formatWeekLabel(values.isoYear, values.isoWeek);
    } else if (details.dataset.type === "as_of_date") {
      text = formatLongDate(values.date);
    }
    hint.textContent = text;
    hint.hidden = !text;
  }

  function groupOrder(groups) {
    const preferred = ["Gerencial", "Sedes", "Operación", "TSOL"];
    return groups.slice().sort((a, b) => {
      const ia = preferred.indexOf(a);
      const ib = preferred.indexOf(b);
      if (ia === -1 && ib === -1) return a.localeCompare(b, "es");
      if (ia === -1) return 1;
      if (ib === -1) return -1;
      return ia - ib;
    });
  }

  function renderReports(reports, ctx) {
    const buckets = new Map();
    reports.forEach((report) => {
      const group = report.group || "Otros";
      if (!buckets.has(group)) buckets.set(group, []);
      buckets.get(group).push(buildCard(report, ctx));
    });

    listEl.textContent = "";
    let firstCard = null;
    groupOrder(Array.from(buckets.keys())).forEach((group) => {
      const section = document.createElement("section");
      section.className = "ir-group";
      const heading = document.createElement("p");
      heading.className = "ir-group-title";
      heading.textContent = group;
      section.appendChild(heading);
      buckets.get(group).forEach((card) => {
        if (!firstCard) firstCard = card;
        section.appendChild(card);
      });
      listEl.appendChild(section);
    });

    listEl.addEventListener(
      "toggle",
      (event) => {
        const openCard = event.target;
        if (!openCard.open) return;
        listEl.querySelectorAll("details[open]").forEach((other) => {
          if (other !== openCard) other.open = false;
        });
      },
      true
    );

    if (firstCard) firstCard.open = true;

    const countEl = document.getElementById("informes-count");
    if (countEl) {
      countEl.textContent = String(reports.length);
      countEl.hidden = false;
    }
  }

  listEl.addEventListener("input", (event) => {
    const form = event.target.closest("form.informe-card-body");
    if (form) refreshHint(form);
  });

  listEl.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!form.classList || !form.classList.contains("informe-card-body")) return;
    event.preventDefault();

    const details = form.closest("details");
    const report = details && reportById.get(details.dataset.reportId);
    const spec = details && REPORT_TYPES[details.dataset.type];
    if (!report || !spec) return;

    const values = Object.fromEntries(new FormData(form).entries());
    const problem = spec.validate ? spec.validate(values) : null;
    if (problem) {
      setCardStatus(form, problem, { error: true });
      return;
    }

    const button = form.querySelector(".informe-generate-btn");
    form.classList.add("is-busy");
    if (button) button.disabled = true;
    setCardStatus(form, "Generando…");

    try {
      const endpoint =
        typeof spec.endpoint === "function" ? spec.endpoint(report) : spec.endpoint;
      const result = await postJSON(endpoint, spec.payload(values, report));
      showResult(form, result);
    } catch (error) {
      setCardStatus(form, error.message || "No se pudo contactar el servidor.", {
        error: true,
      });
    } finally {
      form.classList.remove("is-busy");
      if (button) button.disabled = false;
    }
  });

  function monthOptions(monthNames) {
    return Object.keys(monthNames)
      .map(Number)
      .sort((a, b) => a - b)
      .map((month) => ({ value: String(month), label: monthNames[String(month)] }));
  }

  function previousMonth(today) {
    const ref = today || new Date();
    const date = new Date(ref.getFullYear(), ref.getMonth() - 1, 1);
    return { year: date.getFullYear(), month: date.getMonth() + 1 };
  }

  function yesterdayISO() {
    const date = new Date();
    date.setDate(date.getDate() - 1);
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return date.getFullYear() + "-" + month + "-" + day;
  }

  const MENU_LABELS = {
    "Training Data": "Datos de entrenamiento",
    "New question": "Nueva pregunta",
    "Sign out": "Cerrar sesión",
  };

  function translateMenuLabels(root) {
    if (!root) return;
    root.querySelectorAll("button, a").forEach((element) => {
      for (const node of element.childNodes) {
        if (node.nodeType !== 3) continue;
        const text = node.textContent.trim();
        if (!MENU_LABELS[text]) continue;
        node.textContent = node.textContent.replace(text, MENU_LABELS[text]);
      }
    });
  }

  function polishStaticLabels() {
    if (staticLabelsApplied || !appEl) return;
    translateMenuLabels(appEl.querySelector("#application-sidebar"));
    translateMenuLabels(appEl.querySelector("footer"));
    appEl.querySelectorAll("footer button span").forEach((span) => {
      if (span.textContent && span.textContent.trim() === "Sidebar") {
        span.textContent = "Menú";
      }
    });
    appEl.querySelectorAll("#application-sidebar button .sr-only").forEach((span) => {
      if (span.textContent && span.textContent.trim() === "Sidebar") {
        span.textContent = "Menú";
      }
    });
    staticLabelsApplied = true;
  }

  function polishShell() {
    if (!appEl) return;
    polishStaticLabels();

    if (document.title !== "SmartBusiness BI") {
      document.title = "SmartBusiness BI";
    }
    const logo = appEl.querySelector("#application-sidebar img");
    if (logo && logo.alt !== "SmartBusiness") {
      logo.alt = "SmartBusiness";
    }

    const input = appEl.querySelector("footer input");
    if (input && input.placeholder !== "Pregunta sobre tus datos…") {
      input.placeholder = "Pregunta sobre tus datos…";
    }

    appEl.querySelectorAll("li p > button").forEach((button) => {
      const paragraph = button.parentElement;
      if (!paragraph || paragraph.dataset.suggestedLabeled) return;
      for (const node of paragraph.childNodes) {
        if (node.nodeType === 3 && node.textContent && node.textContent.trim()) {
          node.textContent = "Preguntas sugeridas";
          break;
        }
      }
      paragraph.dataset.suggestedLabeled = "1";
    });
  }

  function schedulePolish() {
    if (polishScheduled) return;
    polishScheduled = true;
    requestAnimationFrame(() => {
      polishScheduled = false;
      polishShell();
    });
  }

  polishShell();
  if (appEl) {
    new MutationObserver(schedulePolish).observe(appEl, {
      childList: true,
      subtree: true,
    });
  }

  fetch("/api/v0/recommended_reports")
    .then((response) => {
      if (!response.ok) throw new Error("HTTP " + response.status);
      return response.json();
    })
    .then((data) => {
      const reports = (data && data.reports) || [];
      if (!reports.length) {
        setStatus("No hay informes recomendados configurados.", true);
        return;
      }

      const fallbackMonth = previousMonth();
      const monthNames = (data && data.month_names) || {};
      const formatOptions = (data && data.format_options) || [
        { value: "html", label: "HTML" },
        { value: "pdf", label: "PDF" },
      ];
      const defaults = {
        year:
          data && data.default_year != null ? data.default_year : fallbackMonth.year,
        month:
          data && data.default_month != null
            ? data.default_month
            : fallbackMonth.month,
        format: (data && data.default_format) || "html",
        isoYear:
          data && data.default_iso_year != null
            ? data.default_iso_year
            : new Date().getFullYear(),
        isoWeek: (data && data.default_iso_week) || 1,
        maxIsoWeek: (data && data.max_iso_week) || 53,
        asOfDate: (data && data.default_as_of_date) || yesterdayISO(),
      };

      reports.forEach((report) => reportById.set(String(report.id), report));
      renderReports(reports, {
        defaults: defaults,
        monthOptions: monthOptions(monthNames),
        formatOptions: formatOptions,
      });
    })
    .catch((error) => {
      setStatus(
        "No se pudo cargar la lista de informes (" + error.message + ").",
        true
      );
    });
})();
