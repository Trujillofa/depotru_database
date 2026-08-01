"""Aesthetic HTML (+ print-friendly) for Rotación de Existencias."""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Dict, List, Mapping, Optional, Sequence

# escape is used throughout build_insights / render_html


def _f(value: Any, decimals: int = 0) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return "—"
    if decimals == 0:
        return f"{n:,.0f}".replace(",", ".")
    t = f"{n:,.{decimals}f}"
    return t.replace(",", "X").replace(".", ",").replace("X", ".")


def _short(text: Any, n: int = 48) -> str:
    s = str(text or "")
    return s if len(s) <= n else s[: n - 1] + "…"


def build_insights(report: Mapping[str, Any]) -> List[Dict[str, str]]:
    """Rule-based managerial insights (Spanish) from a turnover report dict."""
    summary = report.get("summary") or {}
    quiebre = int(summary.get("QUIEBRE") or 0)
    muerto = int(summary.get("MUERTO") or 0)
    sobre = int(summary.get("SOBRESTOCK") or 0)
    baja = int(summary.get("BAJA_COBERTURA") or 0)
    saludable = int(summary.get("SALUDABLE") or 0)
    filas = int(summary.get("Filas") or 0)
    con_stock = int(summary.get("SKUs_Con_Stock") or 0)
    con_venta = int(summary.get("SKUs_Con_Venta") or 0)
    stock_total = float(summary.get("Stock_Total_Unidades") or 0)
    stock_muerto = float(summary.get("Stock_Unidades_Muerto") or 0)
    share_muerto = float(summary.get("Share_Unidades_Muerto") or 0)
    mediana = summary.get("Mediana_Dias_Cobertura")
    actions_q = list(report.get("action_quiebre") or [])
    capital = list(report.get("action_capital_atrapado") or [])
    transfers = list(report.get("suggested_transfers") or [])
    by_wh = list(report.get("by_warehouse") or [])
    abc = list(report.get("abc") or [])
    notes = list(report.get("data_quality_notes") or [])
    days = int(report.get("velocity_days") or 90)
    as_of = report.get("as_of_date") or ""
    demand_mode = str(report.get("demand_mode") or "warehouse")

    def _pct(n: int, d: int) -> str:
        if d <= 0:
            return "—"
        return _f(100.0 * n / d, 1)

    insights: List[Dict[str, str]] = []

    # ── 1. Executive pulse + portfolio mix ────────────────────────────
    if mediana is not None:
        try:
            med_f = float(mediana)
            if med_f < 14:
                pulse = (
                    f"La mediana de cobertura comercial es de solo "
                    f"<strong>{_f(med_f, 1)} días</strong> en el universo con demanda. "
                    "El surtido activo está <em>tenso</em>: priorice reposición de la "
                    "lista A y traslados de alto impacto antes de ampliar el surtido."
                )
                sev = "danger"
            elif med_f < 45:
                pulse = (
                    f"Cobertura mediana de <strong>{_f(med_f, 1)} días</strong>: "
                    "nivel operativo razonable, con bolsillos de quiebre y sobrestock "
                    "que se corrigen con rebalanceo interno + compra selectiva."
                )
                sev = "warning"
            else:
                pulse = (
                    f"Cobertura mediana alta (<strong>{_f(med_f, 1)} días</strong>): "
                    "hay capital inmovilizado; combine liquidación de sobrestock con "
                    "traslados hacia bodegas en quiebre y frene recompras de clase C."
                )
                sev = "info"
        except (TypeError, ValueError):
            pulse = "No hay mediana de cobertura calculable (poca demanda local)."
            sev = "info"
            med_f = None
    else:
        pulse = (
            "Sin mediana de cobertura: pocas filas con demanda comercial en la ventana. "
            "Verifique que las ventas de las bodegas comerciales estén fluyendo a J3."
        )
        sev = "info"
        med_f = None

    mix_bits = []
    if filas > 0:
        mix_bits.append(
            f"mix de banderas: quiebre <strong>{_pct(quiebre, filas)}%</strong>, "
            f"baja cobertura <strong>{_pct(baja, filas)}%</strong>, "
            f"saludable <strong>{_pct(saludable, filas)}%</strong>, "
            f"sobrestock <strong>{_pct(sobre, filas)}%</strong>, "
            f"muerto <strong>{_pct(muerto, filas)}%</strong>"
        )
    insights.append(
        {
            "title": "Pulso ejecutivo del inventario",
            "severity": sev,
            "body": (
                f"Al <strong>{escape(str(as_of))}</strong>, con ventana de demanda de "
                f"<strong>{days} días</strong> (modo <code>{escape(demand_mode)}</code>) "
                f"y <strong>{_f(filas)}</strong> posiciones SKU×bodega comerciales: "
                f"<strong>{_f(quiebre)}</strong> en quiebre, "
                f"<strong>{_f(baja)}</strong> en baja cobertura, "
                f"<strong>{_f(saludable)}</strong> saludables, "
                f"<strong>{_f(sobre)}</strong> en sobrestock y "
                f"<strong>{_f(muerto)}</strong> muertos. "
                f"Hay stock en <strong>{_f(con_stock)}</strong> posiciones y venta "
                f"comercial en <strong>{_f(con_venta)}</strong>. "
                f"{'; '.join(mix_bits) + '. ' if mix_bits else ''}{pulse}"
            ),
        }
    )

    # ── 2. Dead / trapped capital (with top examples) ─────────────────
    if stock_muerto > 0 and stock_total > 0:
        top_muerto = [
            c for c in capital if str(c.get("Bandera") or "").upper() == "MUERTO"
        ][:3]
        examples = ""
        if top_muerto:
            bits = []
            for c in top_muerto:
                bits.append(
                    f"<em>{escape(_short(c.get('Producto'), 40))}</em> "
                    f"({escape(str(c.get('AlmacenCodigo')))}, "
                    f"{_f(c.get('Stock'))} uds)"
                )
            examples = " Ejemplos: " + "; ".join(bits) + "."
        insights.append(
            {
                "title": "Capital atrapado en stock muerto",
                "severity": "warning" if share_muerto > 0.03 else "info",
                "body": (
                    f"Hay <strong>{_f(stock_muerto)}</strong> unidades en bandera "
                    f"<code>MUERTO</code> "
                    f"(<strong>{_f(share_muerto * 100, 1)}%</strong> del stock positivo "
                    f"comercial, sobre un total de {_f(stock_total)} uds). "
                    f"Sin venta en la bodega durante {days} días: candidatas a "
                    "liquidación, devolución a proveedor, kit/promoción o "
                    f"consolidación en una sola bodega.{examples} "
                    "Regla: no recomprar MUERTO hasta que haya señal de demanda local."
                ),
            }
        )
    elif sobre > 0:
        insights.append(
            {
                "title": "Sobrestock (capital lento)",
                "severity": "warning",
                "body": (
                    f"Hay <strong>{_f(sobre)}</strong> posiciones en sobrestock "
                    f"(cobertura muy alta vs la demanda de {days} d). Aunque no estén "
                    "muertas, inmovilizan espacio y capital de trabajo. Priorice "
                    "traslados a bodegas con quiebre del mismo SKU y frene la recompra."
                ),
            }
        )

    # ── 3. Quiebre priority (top 3 narrative) ─────────────────────────
    if actions_q:
        lines = []
        for i, row in enumerate(actions_q[:3], 1):
            cov = row.get("Dias_Cobertura_Comercial")
            cov_txt = _f(cov, 1) if cov is not None else "—"
            lines.append(
                f"<li><strong>{escape(_short(row.get('Producto'), 55))}</strong> "
                f"(SKU <code>{escape(str(row.get('SKU')))}</code>) · "
                f"bodega <strong>{escape(str(row.get('AlmacenCodigo')))}</strong> · "
                f"stock {_f(row.get('Stock'))} · venta {_f(row.get('Venta_Comercial_Nd'))} · "
                f"cobertura {cov_txt} d</li>"
            )
        risk_sev = (
            "danger"
            if quiebre >= 20 or (med_f is not None and med_f < 14)
            else "warning"
        )
        insights.append(
            {
                "title": "Prioridad de compra / reposición (quiebre)",
                "severity": risk_sev,
                "body": (
                    f"Hay <strong>{_f(quiebre)}</strong> posiciones en quiebre y "
                    f"<strong>{_f(len(actions_q))}</strong> SKUs priorizados en la "
                    f"tabla A (1 fila por SKU, la bodega más crítica). "
                    "Top riesgos por demanda local no cubierta:"
                    f"<ol>{''.join(lines)}</ol>"
                    "Acción: generar OC o reposición interna solo para demanda "
                    "<em>en la bodega</em> (no promedie a nivel compañía). "
                    f"Revise al menos las primeras {_f(min(len(actions_q), 15))} filas de A."
                ),
            }
        )

    # ── 4. Transfers opportunity ──────────────────────────────────────
    if transfers:
        total_sugerido = sum(float(t.get("Sugerido_Mover") or 0) for t in transfers)
        routes: Dict[str, int] = {}
        for t in transfers:
            key = f"{t.get('Desde')}→{t.get('Hacia')}"
            routes[key] = routes.get(key, 0) + 1
        top_routes = sorted(routes.items(), key=lambda x: -x[1])[:3]
        route_txt = ", ".join(
            f"<code>{escape(r)}</code> ({_f(n)})" for r, n in top_routes
        )
        transfer_examples: List[str] = []
        for t in transfers[:3]:
            transfer_examples.append(
                f"<li>~<strong>{_f(t.get('Sugerido_Mover'), 1)}</strong> uds "
                f"<strong>{escape(str(t.get('Desde')))}</strong> → "
                f"<strong>{escape(str(t.get('Hacia')))}</strong> · "
                f"<em>{escape(_short(t.get('Producto'), 45))}</em> "
                f"(venta dest. {_f(t.get('Venta_Destino_Nd'))})</li>"
            )
        insights.append(
            {
                "title": "Oportunidad de traslado interno (ahorro de compra)",
                "severity": "success",
                "body": (
                    f"Se detectaron <strong>{_f(len(transfers))}</strong> pares "
                    f"superávit→quiebre del mismo SKU, por un volumen sugerido de "
                    f"~<strong>{_f(total_sugerido, 1)}</strong> unidades. "
                    f"Rutas más frecuentes: {route_txt}. "
                    "Ejemplos de alto impacto:"
                    f"<ol>{''.join(transfer_examples)}</ol>"
                    "Beneficio: reduce compra externa, baja el sobrestock en origen "
                    "y atiende demanda real en destino sin esperar lead time de proveedor."
                ),
            }
        )
    else:
        insights.append(
            {
                "title": "Traslados internos",
                "severity": "info",
                "body": (
                    "No hay pares claros superávit/quiebre en el top de acciones "
                    "(o el sobrestock de una bodega no cubre el quiebre del mismo SKU "
                    "en otra). Enfóquese en <strong>compra a proveedor</strong> para "
                    "la lista A y en liquidar MUERTO/sobrestock sin contraparte."
                ),
            }
        )

    # ── 5. Warehouse risk map ─────────────────────────────────────────
    if by_wh:
        worst = max(by_wh, key=lambda w: int(w.get("QUIEBRE") or 0))
        most_muerto = max(by_wh, key=lambda w: int(w.get("MUERTO") or 0))
        best_stock = max(by_wh, key=lambda w: float(w.get("Stock_Total") or 0))
        wh_lines = []
        for w in sorted(by_wh, key=lambda x: -int(x.get("QUIEBRE") or 0))[:5]:
            wh_lines.append(
                f"<li><strong>{escape(str(w.get('AlmacenCodigo')))}</strong> "
                f"{escape(_short(w.get('AlmacenNombre'), 24))}: "
                f"Q {_f(w.get('QUIEBRE'))} · M {_f(w.get('MUERTO'))} · "
                f"S {_f(w.get('SOBRESTOCK'))} · stock {_f(w.get('Stock_Total'))} uds"
                f"{' · cob. med. ' + _f(w.get('Mediana_Dias_Cobertura'), 1) + ' d' if w.get('Mediana_Dias_Cobertura') is not None else ''}"
                f"</li>"
            )
        insights.append(
            {
                "title": "Mapa de riesgo por bodega comercial",
                "severity": "warning",
                "body": (
                    f"<strong>{escape(str(worst.get('AlmacenCodigo')))}</strong> concentra "
                    f"el mayor número de quiebres (<strong>{_f(worst.get('QUIEBRE'))}</strong>). "
                    f"<strong>{escape(str(most_muerto.get('AlmacenCodigo')))}</strong> lidera "
                    f"en stock muerto (<strong>{_f(most_muerto.get('MUERTO'))}</strong> pos.). "
                    f"<strong>{escape(str(best_stock.get('AlmacenCodigo')))}</strong> tiene el "
                    f"mayor stock comercial (<strong>{_f(best_stock.get('Stock_Total'))}</strong> uds). "
                    "Lectura rápida por bodega (ordenada por quiebre):"
                    f"<ol>{''.join(wh_lines)}</ol>"
                    "Use traslados C y el desglose de tarjetas para rebalancear antes de comprar."
                ),
            }
        )

    # ── 6. ABC focus + A at risk ──────────────────────────────────────
    if abc:
        a_items = [x for x in abc if x.get("ABC") == "A"]
        b_items = [x for x in abc if x.get("ABC") == "B"]
        c_items = [x for x in abc if x.get("ABC") == "C"]
        a_venta = sum(float(x.get("Venta_Comercial_Nd") or 0) for x in a_items)
        tot_venta = sum(float(x.get("Venta_Comercial_Nd") or 0) for x in abc) or 1
        # SKUs in quiebre that appear in ABC-A
        a_skus = {str(x.get("SKU")) for x in a_items}
        q_a = [q for q in actions_q if str(q.get("SKU")) in a_skus][:5]
        a_risk = ""
        if q_a:
            bits = [
                f"<code>{escape(str(q.get('SKU')))}</code> "
                f"{escape(_short(q.get('Producto'), 35))} "
                f"({escape(str(q.get('AlmacenCodigo')))})"
                for q in q_a
            ]
            a_risk = (
                f" <strong>Alerta:</strong> {_f(len(q_a))} SKU(s) clase A aparecen "
                f"en quiebre prioritario: {', '.join(bits)}. "
                "Trátelos como pedido del día."
            )
        insights.append(
            {
                "title": "Enfoque ABC (proteger la demanda que mueve el negocio)",
                "severity": "danger" if q_a else "info",
                "body": (
                    f"Clase <strong>A</strong>: {_f(len(a_items))} SKUs · "
                    f"~<strong>{_f(100 * a_venta / tot_venta, 1)}%</strong> de la demanda "
                    f"rankeada. B: {_f(len(b_items))} · C: {_f(len(c_items))}. "
                    "No deje quiebres en A: el costo de stock-out (venta perdida + "
                    "imagen) suele superar el de un sobrestock moderado en C."
                    f"{a_risk}"
                ),
            }
        )

    # ── 7. Capital top items (broader) ────────────────────────────────
    if capital:
        top_cap = capital[:3]
        bits = []
        for c in top_cap:
            bits.append(
                f"<li><strong>{escape(_short(c.get('Producto'), 50))}</strong> · "
                f"{escape(str(c.get('AlmacenCodigo')))} · "
                f"bandera <code>{escape(str(c.get('Bandera')))}</code> · "
                f"stock {_f(c.get('Stock'))} · venta {_f(c.get('Venta_Comercial_Nd'))} · "
                f"cob. {_f(c.get('Dias_Cobertura_Comercial'), 1) if c.get('Dias_Cobertura_Comercial') is not None else '—'} d"
                f"</li>"
            )
        insights.append(
            {
                "title": "Mayor capital lento / atrapado (tabla B)",
                "severity": "warning",
                "body": (
                    f"Top {_f(len(top_cap))} posiciones por capital atrapado "
                    f"(muerto + sobrestock):"
                    f"<ol>{''.join(bits)}</ol>"
                    "Antes de recomprar: promoción, kit, traslado a otra bodega, "
                    "o devolución. Congelar OC de estos SKUs en la bodega afectada."
                ),
            }
        )

    # ── 8. Coverage interpretation ────────────────────────────────────
    if med_f is not None:
        if med_f < 21:
            cov_body = (
                f"Mediana de <strong>{_f(med_f, 1)} d</strong> sugiere operación "
                "cerca del mínimo de seguridad en muchas líneas. Eleve el buffer "
                "solo en clase A con demanda estable; no “inflar” todo el catálogo."
            )
            cov_sev = "danger" if med_f < 14 else "warning"
        elif med_f < 60:
            cov_body = (
                f"Mediana de <strong>{_f(med_f, 1)} d</strong> es un rango típico "
                "de ferretería con reposición semanal/quincenal. El valor está en "
                "corregir las colas (quiebre y sobrestock), no en mover el promedio."
            )
            cov_sev = "info"
        else:
            cov_body = (
                f"Mediana de <strong>{_f(med_f, 1)} d</strong> es alta: revise "
                "políticas de compra, mínimos desactualizados y SKUs C con poca "
                "rotación. Meta: bajar capital de trabajo sin crear quiebres en A."
            )
            cov_sev = "warning"
        insights.append(
            {
                "title": "Lectura de cobertura comercial",
                "severity": cov_sev,
                "body": (
                    f"La cobertura se calcula como stock ÷ venta diaria comercial "
                    f"en la <em>misma bodega</em> (ventana {days} d). {cov_body}"
                ),
            }
        )

    for n in notes:
        insights.append(
            {
                "title": "Calidad de datos",
                "severity": "info",
                "body": escape(str(n)),
            }
        )

    # ── 9. 7-day action plan with numbers ─────────────────────────────
    n_q = min(len(actions_q), 15)
    n_t = min(len(transfers), 10)
    n_c = min(len(capital), 10)
    insights.append(
        {
            "title": "Plan de acción — próximos 7 días",
            "severity": "success",
            "body": (
                "<ol>"
                f"<li><strong>Hoy–mañana:</strong> cerrar reposición de las "
                f"<strong>{_f(n_q)}</strong> primeras filas de la tabla A "
                f"(quiebre con demanda real en la bodega). "
                f"{'Priorice SKUs clase A en quiebre.' if abc else ''}</li>"
                f"<li><strong>Esta semana:</strong> ejecutar hasta "
                f"<strong>{_f(n_t)}</strong> traslados de la tabla C "
                f"(misma SKU, superávit→déficit) y documentar en ERP.</li>"
                f"<li><strong>Compras:</strong> congelar OC del top "
                f"<strong>{_f(n_c)}</strong> de capital atrapado (tabla B) "
                "hasta plan de salida (promo/kit/devolución).</li>"
                "<li><strong>Datos:</strong> validar stock negativo y "
                "ajustes de inventario para no distorsionar cobertura.</li>"
                "<li><strong>Seguimiento:</strong> regenerar este informe en 7 días "
                "y comparar quiebre / % muerto / mediana de cobertura.</li>"
                "</ol>"
            ),
        }
    )
    return insights


def _badge_class(band: str) -> str:
    b = (band or "").upper()
    if b in ("QUIEBRE", "QUIEBRE_INMINENTE", "DEBAJO_MINIMO"):
        return "badge-danger"
    if b in ("SOBRESTOCK", "MUERTO", "BAJA_COBERTURA", "STOCK_CRITICO"):
        return "badge-warning"
    if b in ("SALUDABLE",):
        return "badge-success"
    return "badge-info"


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
    """cols: list of (header, key_or_callable, align)."""
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
    policy = report.get("warehouse_policy") or {}
    allow = policy.get("allowlist") or []
    excluded = report.get("excluded_document_codes") or []
    insights = insights if insights is not None else build_insights(report)
    as_of = escape(str(report.get("as_of_date") or ""))
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    def band_cell(r: Mapping[str, Any]) -> str:
        b = str(r.get("Bandera") or "")
        return f"<span class='badge {_badge_class(b)}'>{escape(b)}</span>"

    def cover_cell(r: Mapping[str, Any], key: str = "Dias_Cobertura_Comercial") -> str:
        v = r.get(key)
        if v is None:
            return "—"
        return _f(v, 1)

    quiebre_cols = [
        ("SKU", lambda r: f"<code>{escape(str(r.get('SKU') or ''))}</code>", "left"),
        ("Producto", lambda r: escape(_short(r.get("Producto"))), "left"),
        (
            "Bodega",
            lambda r: f"<strong>{escape(str(r.get('AlmacenCodigo') or ''))}</strong>",
            "center",
        ),
        ("Stock", lambda r: _f(r.get("Stock")), "num"),
        ("Venta comercial", lambda r: _f(r.get("Venta_Comercial_Nd")), "num"),
        ("Días cob.", lambda r: cover_cell(r), "num"),
    ]
    capital_cols = [
        ("SKU", lambda r: f"<code>{escape(str(r.get('SKU') or ''))}</code>", "left"),
        ("Producto", lambda r: escape(_short(r.get("Producto"))), "left"),
        ("Bodega", lambda r: escape(str(r.get("AlmacenCodigo") or "")), "center"),
        ("Stock", lambda r: _f(r.get("Stock")), "num"),
        ("Venta", lambda r: _f(r.get("Venta_Comercial_Nd")), "num"),
        ("Días cob.", lambda r: cover_cell(r), "num"),
        ("Bandera", band_cell, "center"),
    ]
    transfer_cols = [
        ("SKU", lambda r: f"<code>{escape(str(r.get('SKU') or ''))}</code>", "left"),
        ("Producto", lambda r: escape(_short(r.get("Producto"), 40)), "left"),
        ("Desde", lambda r: escape(str(r.get("Desde") or "")), "center"),
        ("Hacia", lambda r: escape(str(r.get("Hacia") or "")), "center"),
        ("Stock origen", lambda r: _f(r.get("Stock_Origen")), "num"),
        ("Stock dest.", lambda r: _f(r.get("Stock_Destino")), "num"),
        ("Venta dest.", lambda r: _f(r.get("Venta_Destino_Nd")), "num"),
        ("Sugerido", lambda r: _f(r.get("Sugerido_Mover"), 1), "num"),
    ]
    abc_cols = [
        (
            "ABC",
            lambda r: f"<span class='badge badge-info'>{escape(str(r.get('ABC') or ''))}</span>",
            "center",
        ),
        ("SKU", lambda r: f"<code>{escape(str(r.get('SKU') or ''))}</code>", "left"),
        ("Producto", lambda r: escape(_short(r.get("Producto"))), "left"),
        ("Venta", lambda r: _f(r.get("Venta_Comercial_Nd")), "num"),
        ("Stock", lambda r: _f(r.get("Stock")), "num"),
        (
            "% acum.",
            lambda r: _f(100 * float(r.get("Share_Venta_Acum") or 0), 1) + "%",
            "num",
        ),
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

    wh_cards = "\n".join(
        f"""
        <div class="wh-card">
          <div class="wh-code">{escape(str(w.get('AlmacenCodigo') or ''))}</div>
          <div class="wh-name">{escape(_short(w.get('AlmacenNombre'), 28))}</div>
          <div class="wh-metrics">
            <span class="pill danger">Q {_f(w.get('QUIEBRE'))}</span>
            <span class="pill warning">M {_f(w.get('MUERTO'))}</span>
            <span class="pill muted">S {_f(w.get('SOBRESTOCK'))}</span>
          </div>
          <div class="wh-stock">Stock {_f(w.get('Stock_Total'))} · cob. med. {_f(w.get('Mediana_Dias_Cobertura'), 1) if w.get('Mediana_Dias_Cobertura') is not None else '—'} d</div>
        </div>
        """
        for w in (report.get("by_warehouse") or [])
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Rotación de Existencias — {as_of}</title>
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
      background: linear-gradient(135deg, #0f2744 0%, #1e40af 55%, #0ea5e9 100%);
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
    .kpi .value {{ font-size: 1.45rem; font-weight: 750; color: var(--primary); margin-top: 0.25rem; }}
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
      border-bottom: 2px solid #dbeafe;
      padding-bottom: 0.45rem;
    }}
    .insights {{ display: grid; gap: 0.85rem; }}
    .insight {{
      border-radius: 0.95rem;
      padding: 1rem 1.1rem;
      border-left: 5px solid #94a3b8;
      background: #f8fafc;
      box-shadow: 0 2px 8px rgba(15, 23, 42, 0.03);
    }}
    .insight-head {{
      display: flex; align-items: center; gap: 0.55rem; flex-wrap: wrap;
      margin-bottom: 0.45rem;
    }}
    .insight-num {{
      display: inline-flex; align-items: center; justify-content: center;
      width: 1.55rem; height: 1.55rem; border-radius: 999px;
      background: var(--primary); color: #fff; font-size: 0.75rem; font-weight: 800;
      flex-shrink: 0;
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
    .section-lead {{
      font-size: 0.88rem; color: var(--muted); margin: -0.35rem 0 0.85rem;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.86rem;
    }}
    th {{
      text-align: left;
      background: #f1f5f9;
      color: #334155;
      font-weight: 650;
      padding: 0.55rem 0.5rem;
      border-bottom: 1px solid var(--border);
      white-space: nowrap;
    }}
    td {{ padding: 0.5rem; border-bottom: 1px solid #f1f5f9; vertical-align: top; }}
    td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    td.center {{ text-align: center; }}
    td.empty {{ text-align: center; color: var(--muted); padding: 1rem; }}
    tr:hover td {{ background: #f8fafc; }}
    .badge {{
      display: inline-block;
      padding: 0.15rem 0.5rem;
      border-radius: 999px;
      font-size: 0.7rem;
      font-weight: 700;
      letter-spacing: 0.03em;
    }}
    .badge-danger {{ background: #fee2e2; color: #991b1b; }}
    .badge-warning {{ background: #fef3c7; color: #92400e; }}
    .badge-success {{ background: #dcfce7; color: #166534; }}
    .badge-info {{ background: #dbeafe; color: #1e40af; }}
    .wh-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 0.75rem;
    }}
    .wh-card {{
      border: 1px solid var(--border);
      border-radius: 0.9rem;
      padding: 0.85rem;
      background: linear-gradient(180deg, #fff, #f8fafc);
    }}
    .wh-code {{ font-weight: 800; font-size: 1.05rem; color: var(--primary); }}
    .wh-name {{ font-size: 0.78rem; color: var(--muted); margin-bottom: 0.45rem; }}
    .wh-metrics {{ display: flex; gap: 0.35rem; flex-wrap: wrap; margin-bottom: 0.35rem; }}
    .pill {{
      font-size: 0.72rem; font-weight: 700; padding: 0.15rem 0.45rem;
      border-radius: 999px; background: #e2e8f0; color: #334155;
    }}
    .pill.danger {{ background: #fee2e2; color: #991b1b; }}
    .pill.warning {{ background: #fef3c7; color: #92400e; }}
    .pill.muted {{ background: #e2e8f0; color: #475569; }}
    .wh-stock {{ font-size: 0.78rem; color: #475569; }}
    footer {{
      text-align: center; color: var(--muted); font-size: 0.8rem; margin-top: 1rem;
    }}
    code {{ font-size: 0.82em; background: #f1f5f9; padding: 0.05rem 0.3rem; border-radius: 0.3rem; }}
    @media print {{
      body {{ background: #fff; }}
      header.hero {{ box-shadow: none; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
      section {{ box-shadow: none; break-inside: avoid; }}
      .kpi:hover, tr:hover td {{ box-shadow: none; background: inherit; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <h1>Rotación de Existencias</h1>
      <p class="sub">Análisis de cobertura, quiebres, capital atrapado y traslados · Deposito Trujillo</p>
      <div class="meta">
        <span class="chip">Fecha {as_of}</span>
        <span class="chip">Ventana {escape(str(report.get('velocity_days') or 90))} d</span>
        <span class="chip">Modo {escape(str(report.get('demand_mode') or 'warehouse'))}</span>
        <span class="chip">Bodegas {escape(', '.join(str(a) for a in allow))}</span>
        <span class="chip">Generado {escape(generated)}</span>
      </div>
    </header>

    <div class="kpi-grid">
      <div class="kpi"><div class="label">Posiciones</div><div class="value">{_f(summary.get('Filas'))}</div></div>
      <div class="kpi"><div class="label">Quiebre</div><div class="value danger">{_f(summary.get('QUIEBRE'))}</div></div>
      <div class="kpi"><div class="label">Baja cobertura</div><div class="value warning">{_f(summary.get('BAJA_COBERTURA'))}</div></div>
      <div class="kpi"><div class="label">Saludable</div><div class="value success">{_f(summary.get('SALUDABLE'))}</div></div>
      <div class="kpi"><div class="label">Sobrestock</div><div class="value warning">{_f(summary.get('SOBRESTOCK'))}</div></div>
      <div class="kpi"><div class="label">Muerto</div><div class="value danger">{_f(summary.get('MUERTO'))}</div></div>
      <div class="kpi"><div class="label">Stock total uds</div><div class="value">{_f(summary.get('Stock_Total_Unidades'))}</div></div>
      <div class="kpi"><div class="label">% stock muerto</div><div class="value warning">{_f(100 * float(summary.get('Share_Unidades_Muerto') or 0), 1)}%</div></div>
      <div class="kpi"><div class="label">Mediana cob. (d)</div><div class="value">{_f(summary.get('Mediana_Dias_Cobertura'), 1) if summary.get('Mediana_Dias_Cobertura') is not None else '—'}</div></div>
    </div>

    <section>
      <h2>Insights y plan de acción</h2>
      <p class="section-lead">
        Lectura gerencial automática a partir de quiebres, cobertura, capital atrapado,
        traslados internos y ABC. Use estas notas para priorizar las tablas A–C.
      </p>
      <div class="insights">{insight_html}</div>
    </section>

    <section>
      <h2>A · Comprar / reponer (quiebre, 1 fila por SKU)</h2>
      <p class="section-lead">Demanda comercial real en la bodega; no promedie a nivel compañía.</p>
      <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>SKU</th><th>Producto</th><th>Bodega</th><th class="num">Stock</th>
          <th class="num">Venta</th><th class="num">Días cob.</th>
        </tr></thead>
        <tbody>
          {_table_rows(report.get('action_quiebre') or [], quiebre_cols, 25)}
        </tbody>
      </table>
      </div>
    </section>

    <section>
      <h2>B · Capital atrapado (muerto + sobrestock)</h2>
      <p class="section-lead">Congelar recompra; plan de salida (promo, kit, traslado o devolución).</p>
      <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>SKU</th><th>Producto</th><th>Bodega</th><th class="num">Stock</th>
          <th class="num">Venta</th><th class="num">Días cob.</th><th>Bandera</th>
        </tr></thead>
        <tbody>
          {_table_rows(report.get('action_capital_atrapado') or [], capital_cols, 25)}
        </tbody>
      </table>
      </div>
    </section>

    <section>
      <h2>C · Traslados sugeridos</h2>
      <p class="section-lead">Mismo SKU: superávit en una bodega → quiebre en otra. Ahorra compra externa.</p>
      <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>SKU</th><th>Producto</th><th>Desde</th><th>Hacia</th>
          <th class="num">Origen</th><th class="num">Destino</th>
          <th class="num">Venta dest.</th><th class="num">Sugerido</th>
        </tr></thead>
        <tbody>
          {_table_rows(report.get('suggested_transfers') or [], transfer_cols, 25)}
        </tbody>
      </table>
      </div>
    </section>

    <section>
      <h2>ABC por demanda comercial</h2>
      <div style="overflow-x:auto">
      <table>
        <thead><tr>
          <th>ABC</th><th>SKU</th><th>Producto</th>
          <th class="num">Venta</th><th class="num">Stock</th><th class="num">% acum.</th>
        </tr></thead>
        <tbody>
          {_table_rows(report.get('abc') or [], abc_cols, 30)}
        </tbody>
      </table>
      </div>
    </section>

    <section>
      <h2>Por bodega comercial</h2>
      <div class="wh-grid">{wh_cards or '<p class="empty">Sin datos de bodega</p>'}</div>
    </section>

    <section>
      <h2>Metodología</h2>
      <div class="insight-body" style="font-size:0.9rem;color:#475569">
        <p><strong>Demanda comercial:</strong> modo
        <code>{escape(str(report.get('demand_mode')))}</code>
        — {escape(str(report.get('demand_mode_label') or ''))}.
        Exclusión de documentos de venta:
        {escape(', '.join(str(c) for c in excluded))}.</p>
        <p style="margin-top:0.5rem"><strong>Stock:</strong> saldo actual J3 (incluye negativos)
        en bodegas comerciales; se excluyen líneas de servicio (transporte, “SERVICIO…”).</p>
        <p style="margin-top:0.5rem"><strong>Cobertura:</strong>
        stock ÷ venta diaria comercial en la misma bodega (modo warehouse).</p>
      </div>
    </section>

    <footer>
      Deposito Trujillo · Business Data Analyzer · Rotación de Existencias · {escape(generated)}
    </footer>
  </div>
</body>
</html>
"""
