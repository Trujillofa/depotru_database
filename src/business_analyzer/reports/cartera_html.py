"""Aesthetic HTML (+ print-friendly) for Cartera / AR aging."""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Dict, List, Mapping, Optional, Sequence

from business_analyzer.ai.formatting import format_currency


def _money(value: Any) -> str:
    try:
        return str(format_currency(float(value), 0))
    except (TypeError, ValueError):
        return "—"


def _f(value: Any, decimals: int = 0) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "—"
    if decimals == 0:
        return f"{n:,.0f}".replace(",", ".")
    t = f"{n:,.{decimals}f}"
    return t.replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(value: Any, decimals: int = 1) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "—"
    return _f(n, decimals) + "%"


def _short(text: Any, n: int = 48) -> str:
    s = str(text or "")
    return s if len(s) <= n else s[: n - 1] + "…"


def build_insights(report: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Rule-based managerial insights (Spanish) from a cartera report dict."""
    summary = report.get("summary") or {}
    as_of = report.get("as_of_date") or ""
    snapshot = (
        report.get("fecha_carga_snapshot") or summary.get("Fecha_Carga_Cartera") or ""
    )
    total = float(summary.get("Cartera_Total") or 0)
    corriente = float(summary.get("Cartera_Corriente") or 0)
    vencida = float(summary.get("Cartera_Vencida") or 0)
    vencida_pct = float(summary.get("Cartera_Vencida_Pct") or 0)
    v90 = float(summary.get("Cartera_Vencida_90_Plus") or 0)
    v90_pct = float(summary.get("Cartera_Vencida_90_Plus_Pct") or 0)
    clientes = int(summary.get("Clientes_Con_Saldo") or 0)
    sobre = int(summary.get("Clientes_Sobre_Cupo") or 0)
    dias_prom = float(summary.get("Dias_Vencidos_Promedio_Ponderado") or 0)
    dso = summary.get("DSO_Dias")
    top_od = list(report.get("top_overdue") or [])
    conc = list(report.get("top_concentration") or [])
    over = list(report.get("over_limit") or [])
    by_v = list(report.get("by_vendedor") or [])
    dso_window = int(report.get("dso_days_window") or 30)

    insights: List[Dict[str, str]] = []

    # ── 1. Executive pulse ────────────────────────────────────────────
    if vencida_pct >= 45 or v90_pct >= 15:
        sev = "danger"
        tone = (
            "La cartera está <strong>bajo presión de cobranza</strong>: "
            "priorice visitas y acuerdos de pago en el top vencido y frene "
            "crédito nuevo a clientes en mora >90 d."
        )
    elif vencida_pct >= 30 or v90_pct >= 10:
        sev = "warning"
        tone = (
            "Nivel de mora <strong>moderado-alto</strong>: hay espacio para "
            "recuperar capital de trabajo con un plan de 7 días enfocado."
        )
    else:
        sev = "info"
        tone = (
            "Mora contenida en términos relativos; mantenga disciplina de cupo "
            "y no deje que el tramo 31–90 d se envejezca a >90 d."
        )

    insights.append(
        {
            "title": "Pulso ejecutivo de cartera",
            "severity": sev,
            "body": (
                f"Al <strong>{escape(str(as_of))}</strong> "
                f"(snapshot <code>{escape(str(snapshot))}</code>), la cartera total es "
                f"<strong>{_money(total)}</strong> en "
                f"<strong>{_f(clientes)}</strong> clientes con saldo: "
                f"corriente <strong>{_money(corriente)}</strong>, "
                f"vencida <strong>{_money(vencida)}</strong> "
                f"(<strong>{_pct(vencida_pct)}</strong>), "
                f"de la cual >90 d representa <strong>{_money(v90)}</strong> "
                f"(<strong>{_pct(v90_pct)}</strong>). "
                f"Días vencidos promedio ponderado: "
                f"<strong>{_f(dias_prom, 1)}</strong>. {tone}"
            ),
        }
    )

    # ── 2. Current vs overdue mix ─────────────────────────────────────
    if total > 0:
        insights.append(
            {
                "title": "Corriente vs vencida",
                "severity": "warning" if vencida_pct >= 35 else "info",
                "body": (
                    f"Del total, <strong>{_pct(100 * corriente / total if total else 0)}</strong> "
                    f"está al día y <strong>{_pct(vencida_pct)}</strong> está vencida. "
                    f"Meta operativa: bajar el tramo >90 d por debajo del 12% "
                    f"(hoy <strong>{_pct(v90_pct)}</strong>) con acuerdos de pronto pago "
                    "y suspensión de despachos a crédito cuando corresponda."
                ),
            }
        )

    # ── 3. Top overdue narrative ──────────────────────────────────────
    if top_od:
        lines = []
        for row in top_od[:5]:
            lines.append(
                f"<li><strong>{escape(_short(row.get('cliente_razon_social'), 50))}</strong>"
                f" · vendedor {escape(_short(row.get('vendedor_nombre'), 24))} · "
                f"vencido <strong>{_money(row.get('vencido'))}</strong> · "
                f"total {_money(row.get('total'))} · "
                f"{_f(row.get('dias_vencidos'))} d · "
                f">90 d {_money(row.get('vencido_90_plus'))}</li>"
            )
        sum_top = sum(float(r.get("vencido") or 0) for r in top_od[:10])
        insights.append(
            {
                "title": "Prioridad de cobranza (top vencidos)",
                "severity": "danger" if vencida_pct >= 40 else "warning",
                "body": (
                    f"Los primeros <strong>{_f(min(len(top_od), 10))}</strong> clientes "
                    f"concentran ~<strong>{_money(sum_top)}</strong> de mora en el listado. "
                    "Top a contactar esta semana:"
                    f"<ol>{''.join(lines)}</ol>"
                    "Acción: llamada + compromiso escrito de pago; escalar a gerencia "
                    "comercial si superan cupo o llevan >90 d."
                ),
            }
        )

    # ── 4. Concentration ──────────────────────────────────────────────
    if conc:
        top3 = conc[:3]
        acum3 = float(top3[-1].get("share_acum") or 0) if top3 else 0
        top10 = conc[:10]
        acum10 = float(top10[-1].get("share_acum") or 0) if top10 else 0
        bits = "; ".join(
            f"<em>{escape(_short(c.get('cliente_razon_social'), 36))}</em> "
            f"({_pct(100 * float(c.get('share_total') or 0))})"
            for c in top3
        )
        sev_c = "warning" if acum10 >= 0.40 else "info"
        insights.append(
            {
                "title": "Concentración de riesgo de crédito",
                "severity": sev_c,
                "body": (
                    f"Top 3 clientes = <strong>{_pct(100 * acum3)}</strong> de la cartera; "
                    f"Top 10 ≈ <strong>{_pct(100 * acum10)}</strong>. "
                    f"Mayores saldos: {bits}. "
                    "Vigile cupos y plazos de estos nombres: un default en el top "
                    "impacta caja de forma desproporcionada."
                ),
            }
        )

    # ── 5. Over credit limit ──────────────────────────────────────────
    if sobre > 0 or over:
        lines = []
        for row in over[:5]:
            lines.append(
                f"<li><strong>{escape(_short(row.get('cliente_razon_social'), 45))}</strong> · "
                f"cupo {_money(row.get('cliente_cupo'))} · "
                f"saldo {_money(row.get('total'))} · "
                f"exceso <strong>{_money(row.get('exceso_cupo'))}</strong></li>"
            )
        insights.append(
            {
                "title": "Clientes sobre cupo de crédito",
                "severity": "danger" if sobre >= 5 else "warning",
                "body": (
                    f"Hay <strong>{_f(sobre)}</strong> cliente(s) con saldo por encima del cupo. "
                    + ("Ejemplos:" f"<ol>{''.join(lines)}</ol>" if lines else "")
                    + "Congelar pedidos a crédito hasta regularizar o ampliar cupo "
                    "con aprobación formal."
                ),
            }
        )
    else:
        insights.append(
            {
                "title": "Cupos de crédito",
                "severity": "success",
                "body": (
                    "No hay clientes sobre cupo en el snapshot. Mantenga la revisión "
                    "periódica de límites vs comportamiento de pago."
                ),
            }
        )

    # ── 6. DSO ────────────────────────────────────────────────────────
    if dso is not None:
        try:
            dso_f = float(dso)
        except (TypeError, ValueError):
            dso_f = None
        if dso_f is not None:
            if dso_f > 55:
                dso_sev = "danger"
                dso_msg = (
                    "DSO elevado: el ciclo de cobro está lento vs una meta típica "
                    "de ~45 días para ferretería B2B."
                )
            elif dso_f > 45:
                dso_sev = "warning"
                dso_msg = (
                    "DSO por encima de la meta de 45 días; acelere cobranza de >60 d."
                )
            else:
                dso_sev = "success"
                dso_msg = "DSO dentro o bajo la meta de 45 días."
            insights.append(
                {
                    "title": f"DSO (ventana {dso_window} d)",
                    "severity": dso_sev,
                    "body": (
                        f"DSO calculado: <strong>{_f(dso_f, 1)} días</strong> "
                        f"(cartera / ventas diarias netas del periodo). "
                        f"Ventas netas usadas: {_money(summary.get('Ventas_Netas_Periodo'))}. "
                        f"{dso_msg}"
                    ),
                }
            )

    # ── 7. By seller ──────────────────────────────────────────────────
    if by_v:
        worst = max(by_v, key=lambda x: float(x.get("vencido") or 0))
        biggest = max(by_v, key=lambda x: float(x.get("total") or 0))
        insights.append(
            {
                "title": "Cartera por vendedor",
                "severity": "warning",
                "body": (
                    f"<strong>{escape(str(worst.get('vendedor_nombre')))}</strong> concentra "
                    f"la mayor mora (<strong>{_money(worst.get('vencido'))}</strong>). "
                    f"<strong>{escape(str(biggest.get('vendedor_nombre')))}</strong> lidera "
                    f"en saldo total (<strong>{_money(biggest.get('total'))}</strong>). "
                    "Asigne metas de recaudo semanal por vendedor sobre su top 5 vencido."
                ),
            }
        )

    # ── 8. 7-day plan ─────────────────────────────────────────────────
    n_od = min(len(top_od), 15)
    n_ol = min(len(over), 10)
    insights.append(
        {
            "title": "Plan de cobranza — próximos 7 días",
            "severity": "success",
            "body": (
                "<ol>"
                f"<li><strong>Hoy–mañana:</strong> contactar los "
                f"<strong>{_f(min(n_od, 5))}</strong> mayores vencidos; "
                "documentar promesa de pago y fecha.</li>"
                f"<li><strong>Esta semana:</strong> recorrer hasta "
                f"<strong>{_f(n_od)}</strong> cuentas del listado de mora y las "
                f"<strong>{_f(n_ol)}</strong> sobre cupo; bloquear crédito si no hay plan.</li>"
                f"<li><strong>Comercial:</strong> alinear vendedores con meta de recaudo "
                f"sobre su cartera vencida (hoy total mora {_money(vencida)}).</li>"
                f"<li><strong>Riesgo:</strong> revisar >90 d "
                f"({_money(v90)}, {_pct(v90_pct)}) para castigo, acuerdo o jurídico.</li>"
                "<li><strong>Seguimiento:</strong> regenerar este informe en 7 días y "
                "comparar % vencida, >90 d, DSO y clientes sobre cupo.</li>"
                "</ol>"
            ),
        }
    )
    return insights


def _sev_class(sev: str) -> str:
    return {
        "danger": "insight-danger",
        "warning": "insight-warning",
        "success": "insight-success",
        "info": "insight-info",
    }.get(sev, "insight-info")


def _table_rows(
    rows: Sequence[Mapping[str, Any]],
    cols: Sequence[tuple],
    limit: int = 20,
) -> str:
    if not rows:
        return "<tr><td colspan='99' class='empty'>Sin filas en este corte</td></tr>"
    parts = []
    for r in list(rows)[:limit]:
        tds = []
        for _h, key, align in cols:
            if callable(key):
                val = key(r)
            else:
                val = r.get(key)
            tds.append(f"<td class='{align}'>{val}</td>")
        parts.append("<tr>" + "".join(tds) + "</tr>")
    return "\n".join(parts)


def render_html(
    report: Mapping[str, Any],
    *,
    insights: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Self-contained aesthetic HTML report in Spanish."""
    summary = report.get("summary") or {}
    insights = insights if insights is not None else build_insights(report)
    as_of = escape(str(report.get("as_of_date") or ""))
    snapshot = escape(str(report.get("fecha_carga_snapshot") or ""))
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    overdue_cols = [
        (
            "Cliente",
            lambda r: escape(_short(r.get("cliente_razon_social"))),
            "left",
        ),
        (
            "Vendedor",
            lambda r: escape(_short(r.get("vendedor_nombre"), 22)),
            "left",
        ),
        ("Vencido", lambda r: _money(r.get("vencido")), "num"),
        ("Total", lambda r: _money(r.get("total")), "num"),
        ("Días", lambda r: _f(r.get("dias_vencidos")), "num"),
        (">90 d", lambda r: _money(r.get("vencido_90_plus")), "num"),
    ]
    conc_cols = [
        (
            "Cliente",
            lambda r: escape(_short(r.get("cliente_razon_social"))),
            "left",
        ),
        ("Total", lambda r: _money(r.get("total")), "num"),
        (
            "%",
            lambda r: _pct(100 * float(r.get("share_total") or 0)),
            "num",
        ),
        (
            "% acum.",
            lambda r: _pct(100 * float(r.get("share_acum") or 0)),
            "num",
        ),
        ("Vencido", lambda r: _money(r.get("vencido")), "num"),
    ]
    over_cols = [
        (
            "Cliente",
            lambda r: escape(_short(r.get("cliente_razon_social"))),
            "left",
        ),
        ("Cupo", lambda r: _money(r.get("cliente_cupo")), "num"),
        ("Total", lambda r: _money(r.get("total")), "num"),
        ("Exceso", lambda r: _money(r.get("exceso_cupo")), "num"),
        (
            "Vendedor",
            lambda r: escape(_short(r.get("vendedor_nombre"), 22)),
            "left",
        ),
    ]
    vend_cols = [
        (
            "Vendedor",
            lambda r: escape(_short(r.get("vendedor_nombre"), 32)),
            "left",
        ),
        ("Clientes", lambda r: _f(r.get("clientes")), "num"),
        ("Total", lambda r: _money(r.get("total")), "num"),
        ("Vencido", lambda r: _money(r.get("vencido")), "num"),
        (">90 d", lambda r: _money(r.get("vencido_90_plus")), "num"),
    ]

    insight_html = "\n".join(
        f"""
        <article class="insight {_sev_class(i.get('severity', 'info'))}">
          <div class="insight-head">
            <span class="insight-num">{idx}</span>
            <h3>{escape(i.get('title', ''))}</h3>
            <span class="sev-tag sev-{escape(str(i.get('severity') or 'info'))}">{escape(str(i.get('severity') or 'info').upper())}</span>
          </div>
          <div class="insight-body">{i.get('body', '')}</div>
        </article>
        """
        for idx, i in enumerate(insights, 1)
    )

    bucket_cards = "\n".join(
        f"""
        <div class="wh-card">
          <div class="wh-code">{escape(str(b.get('label') or ''))}</div>
          <div class="wh-stock">{_money(b.get('amount'))}</div>
          <div class="wh-name">{_pct(b.get('share_pct'))} de la cartera</div>
        </div>
        """
        for b in (report.get("buckets") or [])
    )

    dso_kpi = ""
    if summary.get("DSO_Dias") is not None:
        dso_kpi = (
            f'<div class="kpi"><div class="label">DSO (d)</div>'
            f'<div class="value">{_f(summary.get("DSO_Dias"), 1)}</div></div>'
        )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Cartera / Aging — {as_of}</title>
  <style>
    :root {{
      --primary: #0f2744;
      --secondary: #1d4ed8;
      --accent: #059669;
      --warning: #d97706;
      --danger: #dc2626;
      --bg: #f1f5f9;
      --card: #ffffff;
      --text: #0f172a;
      --muted: #64748b;
      --border: #e2e8f0;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.55;
    }}
    .wrap {{ max-width: 1180px; margin: 0 auto; padding: 1.5rem 1.25rem 3rem; }}
    header.hero {{
      background: linear-gradient(135deg, #0f2744 0%, #7c2d12 55%, #ea580c 100%);
      color: #fff;
      border-radius: 1.25rem;
      padding: 2rem 1.75rem;
      margin-bottom: 1.5rem;
      box-shadow: 0 20px 40px rgba(15, 39, 68, 0.25);
    }}
    header.hero h1 {{ font-size: 1.85rem; font-weight: 750; letter-spacing: -0.02em; }}
    header.hero .sub {{ opacity: 0.92; margin-top: 0.4rem; font-size: 0.98rem; }}
    header.hero .meta {{
      margin-top: 1rem;
      display: flex; flex-wrap: wrap; gap: 0.5rem;
    }}
    .chip {{
      background: rgba(255,255,255,0.16);
      border: 1px solid rgba(255,255,255,0.25);
      padding: 0.3rem 0.7rem;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 600;
    }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 0.85rem;
      margin-bottom: 1.5rem;
    }}
    .kpi {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 1rem;
      padding: 1rem 0.9rem;
      text-align: center;
      box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
    }}
    .kpi .label {{ font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }}
    .kpi .value {{ font-size: 1.2rem; font-weight: 750; color: var(--primary); margin-top: 0.25rem; }}
    .kpi .value.danger {{ color: var(--danger); }}
    .kpi .value.warning {{ color: var(--warning); }}
    .kpi .value.success {{ color: var(--accent); }}
    section {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 1.1rem;
      padding: 1.25rem 1.35rem;
      margin-bottom: 1.25rem;
      box-shadow: 0 6px 18px rgba(15, 23, 42, 0.04);
    }}
    section h2 {{
      font-size: 1.15rem;
      margin-bottom: 0.85rem;
      color: var(--primary);
      border-bottom: 2px solid #fed7aa;
      padding-bottom: 0.45rem;
    }}
    .insights {{ display: grid; gap: 0.85rem; }}
    .insight {{
      border-radius: 0.95rem;
      padding: 1rem 1.1rem;
      border-left: 5px solid #94a3b8;
      background: #f8fafc;
    }}
    .insight-head {{
      display: flex; align-items: center; gap: 0.55rem; flex-wrap: wrap;
      margin-bottom: 0.45rem;
    }}
    .insight-num {{
      display: inline-flex; align-items: center; justify-content: center;
      width: 1.55rem; height: 1.55rem; border-radius: 999px;
      background: var(--primary); color: #fff; font-size: 0.75rem; font-weight: 800;
    }}
    .insight h3 {{ font-size: 0.98rem; margin: 0; flex: 1 1 auto; }}
    .sev-tag {{
      font-size: 0.65rem; font-weight: 800; letter-spacing: 0.04em;
      padding: 0.15rem 0.45rem; border-radius: 999px; text-transform: uppercase;
    }}
    .sev-danger {{ background: #fee2e2; color: #991b1b; }}
    .sev-warning {{ background: #fef3c7; color: #92400e; }}
    .sev-success {{ background: #dcfce7; color: #166534; }}
    .sev-info {{ background: #dbeafe; color: #1e40af; }}
    .insight-body {{ font-size: 0.92rem; color: #334155; }}
    .insight-body ol {{ margin: 0.45rem 0 0.35rem 1.25rem; }}
    .insight-body li {{ margin-bottom: 0.25rem; }}
    .insight-danger {{ border-left-color: var(--danger); background: #fef2f2; }}
    .insight-danger .insight-num {{ background: var(--danger); }}
    .insight-warning {{ border-left-color: var(--warning); background: #fffbeb; }}
    .insight-warning .insight-num {{ background: var(--warning); }}
    .insight-success {{ border-left-color: var(--accent); background: #ecfdf5; }}
    .insight-success .insight-num {{ background: var(--accent); }}
    .insight-info {{ border-left-color: var(--secondary); background: #eff6ff; }}
    .insight-info .insight-num {{ background: var(--secondary); }}
    .section-lead {{ font-size: 0.88rem; color: var(--muted); margin: -0.35rem 0 0.85rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.86rem; }}
    th {{
      text-align: left; background: #f1f5f9; color: #334155; font-weight: 650;
      padding: 0.55rem 0.5rem; border-bottom: 1px solid var(--border); white-space: nowrap;
    }}
    td {{ padding: 0.5rem; border-bottom: 1px solid #f1f5f9; vertical-align: top; }}
    td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    td.center {{ text-align: center; }}
    td.empty {{ text-align: center; color: var(--muted); padding: 1rem; }}
    tr:hover td {{ background: #f8fafc; }}
    .wh-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 0.75rem;
    }}
    .wh-card {{
      border: 1px solid var(--border);
      border-radius: 0.9rem;
      padding: 0.85rem;
      background: linear-gradient(180deg, #fff, #fff7ed);
    }}
    .wh-code {{ font-weight: 700; font-size: 0.82rem; color: var(--primary); }}
    .wh-name {{ font-size: 0.78rem; color: var(--muted); margin-top: 0.25rem; }}
    .wh-stock {{ font-size: 1.05rem; font-weight: 750; color: #9a3412; margin-top: 0.35rem; }}
    footer {{ text-align: center; color: var(--muted); font-size: 0.8rem; margin-top: 1rem; }}
    code {{ font-size: 0.82em; background: #f1f5f9; padding: 0.05rem 0.3rem; border-radius: 0.3rem; }}
    @media print {{
      body {{ background: #fff; }}
      header.hero {{ box-shadow: none; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
      section {{ box-shadow: none; break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1>Cartera / Cuentas por Cobrar</h1>
      <p class="sub">Aging, mora, concentración, cupos y plan de cobranza · Deposito Trujillo</p>
      <div class="meta">
        <span class="chip">Fecha {as_of}</span>
        <span class="chip">Snapshot {snapshot}</span>
        <span class="chip">banco_cartera</span>
        <span class="chip">Generado {escape(generated)}</span>
      </div>
    </header>

    <div class="kpi-grid">
      <div class="kpi"><div class="label">Cartera total</div><div class="value">{_money(summary.get('Cartera_Total'))}</div></div>
      <div class="kpi"><div class="label">Corriente</div><div class="value success">{_money(summary.get('Cartera_Corriente'))}</div></div>
      <div class="kpi"><div class="label">Vencida</div><div class="value danger">{_money(summary.get('Cartera_Vencida'))}</div></div>
      <div class="kpi"><div class="label">% Vencida</div><div class="value warning">{_pct(summary.get('Cartera_Vencida_Pct'))}</div></div>
      <div class="kpi"><div class="label">% >90 d</div><div class="value danger">{_pct(summary.get('Cartera_Vencida_90_Plus_Pct'))}</div></div>
      <div class="kpi"><div class="label">Clientes</div><div class="value">{_f(summary.get('Clientes_Con_Saldo'))}</div></div>
      <div class="kpi"><div class="label">Sobre cupo</div><div class="value warning">{_f(summary.get('Clientes_Sobre_Cupo'))}</div></div>
      {dso_kpi}
    </div>

    <section>
      <h2>Insights y plan de cobranza</h2>
      <p class="section-lead">
        Lectura gerencial automática: total AR, corriente vs vencida, top mora,
        concentración, cupos y plan a 7 días.
      </p>
      <div class="insights">{insight_html}</div>
    </section>

    <section>
      <h2>Buckets de aging</h2>
      <div class="wh-grid">{bucket_cards or '<p class="empty">Sin buckets</p>'}</div>
    </section>

    <section>
      <h2>Top clientes vencidos</h2>
      <p class="section-lead">Prioridad de contacto para cobranza.</p>
      <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>Cliente</th><th>Vendedor</th><th class="num">Vencido</th>
          <th class="num">Total</th><th class="num">Días</th><th class="num">>90 d</th>
        </tr></thead>
        <tbody>
          {_table_rows(report.get('top_overdue') or [], overdue_cols, 25)}
        </tbody>
      </table>
      </div>
    </section>

    <section>
      <h2>Concentración de cartera</h2>
      <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>Cliente</th><th class="num">Total</th><th class="num">%</th>
          <th class="num">% acum.</th><th class="num">Vencido</th>
        </tr></thead>
        <tbody>
          {_table_rows(report.get('top_concentration') or [], conc_cols, 25)}
        </tbody>
      </table>
      </div>
    </section>

    <section>
      <h2>Clientes sobre cupo</h2>
      <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>Cliente</th><th class="num">Cupo</th><th class="num">Total</th>
          <th class="num">Exceso</th><th>Vendedor</th>
        </tr></thead>
        <tbody>
          {_table_rows(report.get('over_limit') or [], over_cols, 25)}
        </tbody>
      </table>
      </div>
    </section>

    <section>
      <h2>Por vendedor</h2>
      <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>Vendedor</th><th class="num">Clientes</th><th class="num">Total</th>
          <th class="num">Vencido</th><th class="num">>90 d</th>
        </tr></thead>
        <tbody>
          {_table_rows(report.get('by_vendedor') or [], vend_cols, 20)}
        </tbody>
      </table>
      </div>
    </section>

    <section>
      <h2>Metodología</h2>
      <div class="insight-body" style="font-size:0.9rem;color:#475569">
        <p><strong>Fuente:</strong> SmartBusiness <code>banco_cartera</code>,
        snapshot con <code>fecha_carga = MAX(fecha_carga)</code>
        (o el más reciente ≤ fecha de referencia).</p>
        <p style="margin-top:0.5rem"><strong>KPIs:</strong> alineados a Q9 del pack KPI
        (% vencida, % >90 d, clientes sobre cupo, DSO opcional via
        <code>banco_datos</code> excluyendo códigos de prueba).</p>
        <p style="margin-top:0.5rem"><strong>v1:</strong> no usa J3 <code>CarCarteraCliente</code>.</p>
      </div>
    </section>

    <footer>
      Deposito Trujillo · Business Data Analyzer · Cartera Aging · {escape(generated)}
    </footer>
  </div>
</body>
</html>
"""
