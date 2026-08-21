"""Self-contained HTML for the customer invoice summary."""

from __future__ import annotations

from datetime import date
from html import escape
from typing import Any, Mapping

from business_analyzer.reports.invoice_summary import cop, fmt_date, qty


def render_html(report: Mapping[str, Any]) -> str:
    summary = report.get("summary") or {}
    customer = report.get("customer") or {}
    invoices = list(report.get("invoices") or [])
    name = escape(str(customer.get("name") or "Cliente"))
    nit = escape(str(customer.get("nit") or "—"))
    obra = escape(str(report.get("obra") or ""))
    sede = escape(
        str((invoices[0].get("sede") if invoices else "") or "Sede comercial")
    )
    vendedor = escape(str((invoices[0].get("vendedor") if invoices else "") or "—"))
    generated = fmt_date(date.today())

    inv_rows = []
    for inv in invoices:
        inv_rows.append(
            "<tr>"
            f"<td>{escape(str(inv.get('numero')))}</td>"
            f"<td>{escape(fmt_date(inv.get('fecha')))}</td>"
            f"<td>{escape(fmt_date(inv.get('vence')))}</td>"
            f"<td class='num'>{cop(inv.get('total_sin_iva'), cents=False)}</td>"
            f"<td class='num'>{cop(inv.get('iva'))}</td>"
            f"<td class='num'>{cop(inv.get('total_mas_iva'))}</td>"
            f"<td class='num'>{cop(inv.get('saldo'), cents=False)}</td>"
            "</tr>"
        )
    inv_rows.append(
        "<tr class='total'>"
        "<td colspan='3'><strong>Total</strong></td>"
        f"<td class='num'><strong>"
        f"{cop(summary.get('total_sin_iva'), cents=False)}</strong></td>"
        f"<td class='num'><strong>{cop(summary.get('iva'))}</strong></td>"
        f"<td class='num'><strong>{cop(summary.get('total_mas_iva'))}</strong></td>"
        f"<td class='num'><strong>"
        f"{cop(summary.get('saldo'), cents=False)}</strong></td>"
        "</tr>"
    )

    fam_rows = "".join(
        f"<tr><td>{escape(str(f.get('categoria')))}</td>"
        f"<td class='num'>{cop(f.get('total_mas_iva'))}</td></tr>"
        for f in (report.get("families") or [])
    )

    detail = []
    for inv in invoices:
        rows = []
        for item in inv.get("lines") or []:
            label = str(item.get("nombre") or "")
            if item.get("exento"):
                label += " (exento IVA)"
            rows.append(
                "<tr>"
                f"<td>{escape(label)}</td>"
                f"<td class='num'>{qty(item.get('cantidad'))}</td>"
                f"<td class='num'>{cop(item.get('unitario_sin_iva'), cents=False)}</td>"
                f"<td class='num'>{cop(item.get('total_mas_iva'))}</td>"
                "</tr>"
            )
        detail.append(
            f"<h3>Factura {escape(str(inv.get('numero')))} · "
            f"{escape(fmt_date(inv.get('fecha')))} · "
            f"{cop(inv.get('total_mas_iva'))}</h3>"
            "<table><thead><tr><th>Artículo</th><th>Cant.</th>"
            "<th>Vlr. unit.</th><th>Total</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

    repeated_html = ""
    if report.get("repeated"):
        rrows = []
        for item in report["repeated"]:
            facts = " + ".join(str(n) for n in item.get("facturas") or [])
            rrows.append(
                "<tr>"
                f"<td>{escape(str(item.get('nombre')))}</td>"
                f"<td>{escape(facts)}</td>"
                f"<td class='num'>{qty(item.get('cantidad'))}</td>"
                f"<td class='num'>{cop(item.get('total_sin_iva'), cents=False)}</td>"
                "</tr>"
            )
        repeated_html = (
            "<section><h2>Artículos que se repiten</h2>"
            "<table><thead><tr><th>Artículo</th><th>Facturas</th>"
            "<th>Cant.</th><th>Subtotal</th></tr></thead>"
            f"<tbody>{''.join(rrows)}</tbody></table></section>"
        )

    alerts = []
    if report.get("missing"):
        listed = ", ".join(str(n) for n in report["missing"])
        alerts.append(f"<div class='callout'>No encontradas: {escape(listed)}.</div>")
    if report.get("multiple_customers"):
        alerts.append(
            "<div class='callout'>Las facturas pertenecen a más de un cliente.</div>"
        )

    obra_chip = f'<span class="chip">{obra}</span>' if obra else ""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Resumen de facturas — {name}</title>
  <style>
    :root {{
      --brick: #7A3A22;
      --ink: #1A1410;
      --muted: #5C534C;
      --bg: #F7F3EE;
      --card: #ffffff;
      --rule: #D4C8BC;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: "Segoe UI", system-ui, sans-serif;
      background: var(--bg);
      color: var(--ink);
      line-height: 1.5;
    }}
    .wrap {{ max-width: 1080px; margin: 0 auto; padding: 1.5rem 1.2rem 3rem; }}
    header {{
      background: var(--brick);
      color: #fff;
      border-radius: 1rem;
      padding: 1.6rem 1.5rem;
      margin-bottom: 1.25rem;
    }}
    header p.kicker {{
      font-size: 0.75rem; letter-spacing: 0.08em;
      text-transform: uppercase; opacity: 0.85;
    }}
    header h1 {{ font-size: 1.7rem; margin: 0.25rem 0 0.4rem; }}
    header .sub {{ opacity: 0.92; font-size: 0.95rem; }}
    .chips {{ margin-top: 0.8rem; display: flex; flex-wrap: wrap; gap: 0.4rem; }}
    .chip {{
      background: rgba(255,255,255,0.14);
      border: 1px solid rgba(255,255,255,0.28);
      padding: 0.25rem 0.65rem;
      border-radius: 999px;
      font-size: 0.78rem;
    }}
    .kpis {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 0.7rem;
      margin-bottom: 1.1rem;
    }}
    .kpi {{
      background: var(--card);
      border: 1px solid var(--rule);
      border-radius: 0.8rem;
      padding: 0.85rem;
    }}
    .kpi .label {{
      font-size: 0.7rem; text-transform: uppercase;
      color: var(--muted); letter-spacing: 0.04em;
    }}
    .kpi .value {{ font-size: 1.15rem; font-weight: 700; margin-top: 0.2rem; }}
    section {{
      background: var(--card);
      border: 1px solid var(--rule);
      border-radius: 0.9rem;
      padding: 1.1rem 1.2rem;
      margin-bottom: 1rem;
    }}
    h2 {{ font-size: 1.1rem; margin-bottom: 0.7rem; color: var(--brick); }}
    h3 {{ font-size: 0.95rem; margin: 1rem 0 0.4rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
    th {{
      background: var(--brick);
      color: #fff;
      text-align: left;
      padding: 0.4rem 0.5rem;
      font-weight: 600;
    }}
    td {{
      padding: 0.38rem 0.5rem;
      border-bottom: 1px solid var(--rule);
      vertical-align: top;
    }}
    tr:nth-child(even) td {{ background: #F7F3EE; }}
    tr.total td {{ background: #EFE6DC; border-top: 2px solid var(--brick); }}
    .num {{ text-align: right; white-space: nowrap; }}
    .callout {{
      border-left: 4px solid var(--brick);
      background: #EFE6DC;
      padding: 0.7rem 0.9rem;
      margin-bottom: 0.8rem;
      border-radius: 0 0.5rem 0.5rem 0;
    }}
    footer {{ font-size: 0.78rem; color: var(--muted); margin-top: 1.2rem; }}
    @media print {{
      body {{ background: #fff; }}
      header {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <p class="kicker">Resumen comercial de facturas</p>
      <h1>{name}</h1>
      <p class="sub">CC/NIT {nit} · {sede} · Asesor {vendedor}</p>
      <div class="chips">
        <span class="chip">{summary.get('invoice_count') or 0} facturas</span>
        {obra_chip}
        <span class="chip">Saldo {cop(summary.get('saldo'), cents=False)}</span>
      </div>
    </header>
    {''.join(alerts)}
    <div class="kpis">
      <div class="kpi">
        <div class="label">Subtotal</div>
        <div class="value">{cop(summary.get('total_sin_iva'), cents=False)}</div>
      </div>
      <div class="kpi">
        <div class="label">IVA</div>
        <div class="value">{cop(summary.get('iva'))}</div>
      </div>
      <div class="kpi">
        <div class="label">Total</div>
        <div class="value">{cop(summary.get('total_mas_iva'))}</div>
      </div>
      <div class="kpi">
        <div class="label">Saldo</div>
        <div class="value">{cop(summary.get('saldo'), cents=False)}</div>
      </div>
    </div>
    <section>
      <h2>Facturas</h2>
      <table>
        <thead><tr><th>Factura</th><th>Fecha</th><th>Vence</th><th>Subtotal</th><th>IVA</th><th>Total</th><th>Saldo</th></tr></thead>
        <tbody>{''.join(inv_rows)}</tbody>
      </table>
    </section>
    <section>
      <h2>Composición</h2>
      <table>
        <thead><tr><th>Familia</th><th>Total con IVA</th></tr></thead>
        <tbody>{fam_rows}</tbody>
      </table>
    </section>
    <section>
      <h2>Detalle por factura</h2>
      {''.join(detail)}
    </section>
    {repeated_html}
    <footer>Depósito Trujillo · {generated} · No reemplaza las facturas DIAN.</footer>
  </div>
</body>
</html>
"""
