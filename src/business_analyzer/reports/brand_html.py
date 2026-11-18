"""Self-contained HTML renderer for the brand business report."""

from __future__ import annotations

import html
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

MONTH_NAMES_ES = {
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


def _esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _num(value: Any, decimals: int = 0) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    if decimals <= 0:
        return f"{number:,.0f}".replace(",", ".")
    text = f"{number:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def _money(value: Any, decimals: int = 1) -> str:
    try:
        amount = float(value) / 1_000_000
    except (TypeError, ValueError):
        amount = 0.0
    sign = "-" if amount < 0 else ""
    return f"{sign}${_num(abs(amount), decimals)} M"


def _short(text: Any, limit: int = 52) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    cut = value[:limit]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,.-") + "…"


def _pct(value: Any, decimals: int = 2) -> str:
    return f"{_num(value, decimals)}%"


def _delta_pct(current: float, prior: float) -> Optional[float]:
    if not prior:
        return None
    return (current / prior - 1.0) * 100.0


def _delta(current: Any, prior: Any) -> str:
    value = _delta_pct(float(current or 0), float(prior or 0))
    if value is None:
        return "n/a"
    css = "pos" if value >= 0 else "neg"
    return f'<span class="{css}">{value:+.1f}%</span>'.replace(".", ",")


def _bp(current: Any, prior: Any) -> str:
    value = (float(current or 0) - float(prior or 0)) * 100
    css = "pos" if value >= 0 else "neg"
    return f'<span class="{css}">{value:+.0f} pb</span>'


def _table(
    headers: Sequence[str],
    rows: Iterable[Sequence[Any]],
    *,
    numeric: Optional[Sequence[int]] = None,
) -> str:
    numeric_cols = set(numeric or [])
    head = "".join(f"<th>{_esc(header)}</th>" for header in headers)
    body: List[str] = []
    for row in rows:
        cells = []
        for index, cell in enumerate(row):
            cls = ' class="num"' if index in numeric_cols else ""
            cells.append(f"<td{cls}>{cell}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    if not body:
        body.append(
            f'<tr><td colspan="{len(headers)}" class="empty">Sin datos.</td></tr>'
        )
    return (
        f'<div class="table-wrap"><table class="table"><thead><tr>{head}</tr></thead>'
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


def _section(title: str, body: str, note: str = "", anchor: str = "") -> str:
    anchor_attr = f' id="{_esc(anchor)}"' if anchor else ""
    note_html = f'<p class="section-note">{note}</p>' if note else ""
    return (
        f'<section class="section"{anchor_attr}>'
        f"<h2>{_esc(title)}</h2>{note_html}{body}</section>"
    )


def _card(label: str, value: str, sub: str = "", tone: str = "") -> str:
    tone_class = f" {tone}" if tone else ""
    sub_html = f'<span class="kpi-sub">{sub}</span>' if sub else ""
    return (
        f'<div class="kpi{tone_class}"><span class="kpi-label">{_esc(label)}</span>'
        f'<strong class="kpi-value">{value}</strong>{sub_html}</div>'
    )


def _summary(report: Mapping[str, Any]) -> str:
    findings = report.get("findings") or []
    rows = []
    for item in findings:
        priority = str(item.get("priority") or "Media")
        badge = priority.lower()
        rows.append(
            [
                f'<span class="badge {badge}">{_esc(priority)}</span>',
                f"<strong>{_esc(item.get('title'))}</strong>",
                _esc(item.get("evidence")),
                _esc(item.get("risk")),
            ]
        )
    table = _table(
        ["Prioridad", "Hallazgo", "Evidencia", "Riesgo"],
        rows,
    )
    projection = report.get("projection")
    projection_html = ""
    if projection:
        growth = projection.get("growth_pct")
        growth_txt = (
            f"{growth:+.1f}%".replace(".", ",") if growth is not None else "n/a"
        )
        target = projection.get("target_end")
        target_txt = f" al {target}" if target else " del año"
        projection_html = (
            f'<p class="callout"><strong>Proyección indicativa{target_txt}:</strong> '
            f"{_money(projection.get('run_rate'))} "
            f"({growth_txt} vs. año anterior completo). No es un presupuesto.</p>"
        )
    return _section("Resumen ejecutivo", projection_html + table, anchor="resumen")


def _kpis(report: Mapping[str, Any]) -> str:
    current = report["kpis"]["current"]
    prior = report["kpis"]["prior"]
    company_cur = report["kpis"]["company_current"]
    company_prev = report["kpis"]["company_prior"]
    cards = "".join(
        [
            _card(
                "Ventas netas",
                _money(current["rev"]),
                _delta(current["rev"], prior["rev"]),
            ),
            _card(
                "Utilidad bruta",
                _money(current["profit"]),
                _delta(current["profit"], prior["profit"]),
            ),
            _card(
                "Margen bruto",
                _pct(current["margin_pct"]),
                _bp(current["margin_pct"], prior["margin_pct"]),
                "accent",
            ),
            _card(
                "Unidades", _num(current["qty"]), _delta(current["qty"], prior["qty"])
            ),
            _card(
                "Facturas",
                _num(current["invoices"]),
                _delta(current["invoices"], prior["invoices"]),
            ),
            _card(
                "Clientes",
                _num(current["customers"]),
                _delta(current["customers"], prior["customers"]),
            ),
        ]
    )
    share_rev = current["rev"] / company_cur["rev"] * 100 if company_cur["rev"] else 0.0
    prior_share_rev = (
        prior["rev"] / company_prev["rev"] * 100 if company_prev["rev"] else 0.0
    )
    share_profit = (
        current["profit"] / company_cur["profit"] * 100
        if company_cur["profit"]
        else 0.0
    )
    prior_share_profit = (
        prior["profit"] / company_prev["profit"] * 100
        if company_prev["profit"]
        else 0.0
    )
    rows = [
        [
            "Ventas netas",
            _money(current["rev"]),
            _money(prior["rev"]),
            _delta(current["rev"], prior["rev"]),
        ],
        [
            "Ventas con IVA",
            _money(current["rev_iva"]),
            _money(prior["rev_iva"]),
            _delta(current["rev_iva"], prior["rev_iva"]),
        ],
        [
            "Costo de ventas",
            _money(current["cost"]),
            _money(prior["cost"]),
            _delta(current["cost"], prior["cost"]),
        ],
        [
            "Utilidad bruta",
            _money(current["profit"]),
            _money(prior["profit"]),
            _delta(current["profit"], prior["profit"]),
        ],
        [
            "Margen bruto",
            _pct(current["margin_pct"]),
            _pct(prior["margin_pct"]),
            _bp(current["margin_pct"], prior["margin_pct"]),
        ],
        [
            "Unidades",
            _num(current["qty"]),
            _num(prior["qty"]),
            _delta(current["qty"], prior["qty"]),
        ],
        [
            "Precio promedio/unidad",
            _money(current["price_unit"], 0),
            _money(prior["price_unit"], 0),
            _delta(current["price_unit"], prior["price_unit"]),
        ],
        [
            "Facturas",
            _num(current["invoices"]),
            _num(prior["invoices"]),
            _delta(current["invoices"], prior["invoices"]),
        ],
        [
            "Ticket promedio",
            _money(current["avg_ticket"], 0),
            _money(prior["avg_ticket"], 0),
            _delta(current["avg_ticket"], prior["avg_ticket"]),
        ],
        [
            "Clientes activos",
            _num(current["customers"]),
            _num(prior["customers"]),
            _delta(current["customers"], prior["customers"]),
        ],
        [
            "SKUs vendidos",
            _num(current["skus"]),
            _num(prior["skus"]),
            _delta(current["skus"], prior["skus"]),
        ],
        [
            "Devoluciones",
            _money(abs(current["return_rev"])),
            _money(abs(prior["return_rev"])),
            _delta(abs(current["return_rev"]), abs(prior["return_rev"])),
        ],
        [
            "Tasa de devolución",
            _pct(current["return_pct"]),
            _pct(prior["return_pct"]),
            _bp(current["return_pct"], prior["return_pct"]),
        ],
        [
            "Líneas de venta",
            _num(current["lines"]),
            _num(prior["lines"]),
            _delta(current["lines"], prior["lines"]),
        ],
    ]
    kpi_table = _table(
        ["Indicador", "Período actual", "Año anterior", "Variación"],
        rows,
        numeric=[1, 2, 3],
    )
    company_rows = [
        [
            "Ventas netas compañía",
            _money(company_cur["rev"]),
            _money(company_prev["rev"]),
            _delta(company_cur["rev"], company_prev["rev"]),
        ],
        [
            "Utilidad bruta compañía",
            _money(company_cur["profit"]),
            _money(company_prev["profit"]),
            _delta(company_cur["profit"], company_prev["profit"]),
        ],
        [
            "Margen bruto compañía",
            _pct(company_cur["margin_pct"]),
            _pct(company_prev["margin_pct"]),
            _bp(company_cur["margin_pct"], company_prev["margin_pct"]),
        ],
        [
            f"Participación {_esc(report['brand'])} en ventas",
            _pct(share_rev),
            _pct(prior_share_rev),
            _bp(share_rev, prior_share_rev),
        ],
        [
            f"Participación {_esc(report['brand'])} en utilidad",
            _pct(share_profit),
            _pct(prior_share_profit),
            _bp(share_profit, prior_share_profit),
        ],
    ]
    company_table = _table(
        ["Contexto compañía", "Período actual", "Año anterior", "Variación"],
        company_rows,
        numeric=[1, 2, 3],
    )
    return _section(
        "Tablero de resultados",
        f'<div class="kpi-grid">{cards}</div>{kpi_table}'
        f"<h3>Contexto compañía</h3>{company_table}",
        anchor="tablero",
    )


def _annual(report: Mapping[str, Any]) -> str:
    rows = []
    for item in report.get("annual") or []:
        label = str(item.get("year"))
        if item.get("partial"):
            label += " YTD"
        rows.append(
            [
                label,
                _money(item.get("rev")),
                _money(item.get("profit")),
                _pct(item.get("margin_pct")),
                _num(item.get("qty")),
                _num(item.get("customers")),
                _num(item.get("invoices")),
            ]
        )
    return _section(
        "Evolución anual",
        _table(
            [
                "Año",
                "Ventas netas",
                "Utilidad bruta",
                "Margen",
                "Unidades",
                "Clientes",
                "Facturas",
            ],
            rows,
            numeric=[1, 2, 3, 4, 5, 6],
        ),
        anchor="anual",
    )


def _monthly(report: Mapping[str, Any]) -> str:
    rows = []
    for item in report.get("monthly") or []:
        month = item.get("label") or MONTH_NAMES_ES.get(
            item.get("month"), str(item.get("month"))
        )
        if item.get("partial"):
            month += " (parcial)"
        rows.append(
            [
                month,
                _money(item.get("current_rev")),
                _money(item.get("prior_rev")),
                _delta(item.get("current_rev"), item.get("prior_rev")),
                _pct(item.get("current_margin_pct")),
                _pct(item.get("prior_margin_pct")),
                _num(item.get("current_qty")),
            ]
        )
    return _section(
        "Evolución mensual",
        _table(
            [
                "Mes",
                "Período actual",
                "Año anterior",
                "Var.",
                "Margen actual",
                "Margen anterior",
                "Unidades",
            ],
            rows,
            numeric=[1, 2, 3, 4, 5, 6],
        ),
        note="Los meses parciales se comparan contra el mismo tramo de días del año anterior.",
        anchor="mensual",
    )


def _channels(report: Mapping[str, Any]) -> str:
    cur = {str(row.get("code")): row for row in report["warehouses"]["current"]}
    prev = {str(row.get("code")): row for row in report["warehouses"]["prior"]}
    codes = sorted(
        set(cur) | set(prev),
        key=lambda code: float(cur.get(code, {}).get("rev") or 0),
        reverse=True,
    )
    rows = []
    for code in codes:
        current = cur.get(code, {})
        prior = prev.get(code, {})
        current_rev = float(current.get("rev") or 0)
        prior_rev = float(prior.get("rev") or 0)
        rows.append(
            [
                _esc(code or "—"),
                _money(current_rev),
                _money(prior_rev),
                _delta(current_rev, prior_rev),
                _pct(current.get("margin_pct") or 0),
                _pct(current.get("share_pct") or 0),
            ]
        )
    warehouse_table = _table(
        ["Almacén", "Actual", "Año anterior", "Var.", "Margen", "Part."],
        rows,
        numeric=[1, 2, 3, 4, 5],
    )
    branch_rows = []
    for item in report["branches"]["current"]:
        branch_rows.append(
            [
                _esc(item.get("code")),
                _esc(item.get("doc_name") or ""),
                _money(item.get("rev")),
                _pct(item.get("share_pct")),
                _pct(item.get("margin_pct"))
                if float(item.get("rev") or 0) > 0
                else "—",
                _num(item.get("invoices")),
                _num(item.get("customers")),
            ]
        )
    branch_table = _table(
        [
            "Código",
            "Documento",
            "Venta neta",
            "Part.",
            "Margen",
            "Facturas",
            "Clientes",
        ],
        branch_rows,
        numeric=[2, 3, 4, 5, 6],
    )
    prior_docs = {str(row.get("code")): row for row in report["branches"]["prior"]}
    migration_note = ""
    if "FDT" in prior_docs or "FDD" in prior_docs:
        migration_note = (
            '<p class="callout warn"><strong>Comparabilidad:</strong> el año anterior '
            "incluye documentos de entrega FDT/FDD que desaparecen en el período actual. "
            "La comparación por almacén es válida; la comparación por código de documento no.</p>"
        )
    return _section(
        "Canales y sedes",
        "<h3>Por almacén</h3>"
        + warehouse_table
        + "<h3>Por sucursal de facturación</h3>"
        + branch_table
        + migration_note,
        note="Las cifras por almacén están netas de devoluciones; las de sucursal son brutas.",
        anchor="canales",
    )


def _products(report: Mapping[str, Any]) -> str:
    products = report["products"]
    top_rows = []
    for item in products.get("top") or []:
        sku = str(item.get("sku"))
        current_rev = float(item.get("rev") or 0)
        prior_value = float(item.get("prior_rev") or 0)
        top_rows.append(
            [
                _esc(sku),
                _esc(_short(item.get("name"), 52)),
                _money(current_rev),
                _num(item.get("qty")),
                _pct(item.get("margin_pct")),
                _pct(item.get("share_pct")),
                _delta(current_rev, prior_value),
            ]
        )
    top_table = _table(
        ["SKU", "Producto", "Ventas", "Unidades", "Margen", "Part.", "Var."],
        top_rows,
        numeric=[2, 3, 4, 5, 6],
    )
    move_rows = []
    for direction, label in (
        (products.get("gains") or [], "Crecimiento"),
        (products.get("losses") or [], "Caída"),
    ):
        for item in direction:
            delta_value = float(item.get("delta") or 0)
            move_rows.append(
                [
                    _esc(label),
                    _esc(item.get("sku")),
                    _esc(_short(item.get("name"), 48)),
                    _money(item.get("current")),
                    _money(item.get("prior")),
                    f'<span class="{"pos" if delta_value >= 0 else "neg"}">'
                    f"{_money(delta_value)}</span>",
                ]
            )
    moves_table = _table(
        ["Movimiento", "SKU", "Producto", "Actual", "Año anterior", "Delta"],
        move_rows,
        numeric=[3, 4, 5],
    )
    promo = products.get("promo") or {}
    promo_rows = [
        [
            "Ventas promocionadas",
            _money(promo.get("current", {}).get("rev")),
            _money(promo.get("prior", {}).get("rev")),
            _delta(
                promo.get("current", {}).get("rev"), promo.get("prior", {}).get("rev")
            ),
        ],
        [
            "Participación",
            _pct(promo.get("share_pct")),
            _pct(promo.get("prior_share_pct")),
            _bp(promo.get("share_pct"), promo.get("prior_share_pct")),
        ],
        [
            "Margen promocional",
            _pct(promo.get("current", {}).get("margin_pct")),
            _pct(promo.get("prior", {}).get("margin_pct")),
            _bp(
                promo.get("current", {}).get("margin_pct"),
                promo.get("prior", {}).get("margin_pct"),
            ),
        ],
        [
            "Ventas no promocionadas",
            _money(promo.get("base_current", {}).get("rev")),
            _money(promo.get("base_prior", {}).get("rev")),
            _delta(
                promo.get("base_current", {}).get("rev"),
                promo.get("base_prior", {}).get("rev"),
            ),
        ],
        [
            "Margen no promocionado",
            _pct(promo.get("base_current", {}).get("margin_pct")),
            _pct(promo.get("base_prior", {}).get("margin_pct")),
            _bp(
                promo.get("base_current", {}).get("margin_pct"),
                promo.get("base_prior", {}).get("margin_pct"),
            ),
        ],
    ]
    promo_table = _table(
        ["Métrica", "Actual", "Año anterior", "Variación"],
        promo_rows,
        numeric=[1, 2, 3],
    )
    rubro_prev = {
        (row.get("rubro"), row.get("subrubro")): row
        for row in report["rubros"]["prior"]
    }
    rubro_rows = []
    for item in report["rubros"]["current"][:12]:
        key = (item.get("rubro"), item.get("subrubro"))
        prior_value = float((rubro_prev.get(key) or {}).get("rev") or 0)
        rubro_rows.append(
            [
                _esc(item.get("rubro")),
                _esc(item.get("subrubro")),
                _money(item.get("rev")),
                _money(prior_value),
                _delta(item.get("rev"), prior_value),
                _pct(item.get("margin_pct")),
            ]
        )
    rubro_table = _table(
        ["Rubro", "Subrubro", "Actual", "Año anterior", "Var.", "Margen"],
        rubro_rows,
        numeric=[2, 3, 4, 5],
    )
    gap = products.get("master_gap") or {}
    gap_rows = [
        [
            "SKUs sin maestro",
            _num(gap.get("current", {}).get("skus")),
            _num(gap.get("prior", {}).get("skus")),
        ],
        [
            "Ventas sin maestro",
            _money(gap.get("current", {}).get("rev")),
            _money(gap.get("prior", {}).get("rev")),
        ],
        ["Participación", _pct(gap.get("share_pct")), _pct(gap.get("prior_share_pct"))],
    ]
    gap_table = _table(
        ["Brecha de datos maestros", "Actual", "Año anterior"],
        gap_rows,
        numeric=[1, 2],
    )
    return _section(
        "Portafolio de productos",
        "<h3>Top productos</h3>"
        + top_table
        + "<h3>Mayores movimientos</h3>"
        + moves_table
        + "<h3>Promociones</h3>"
        + promo_table
        + "<h3>Rubros</h3>"
        + rubro_table
        + "<h3>Calidad del maestro</h3>"
        + gap_table,
        anchor="productos",
    )


def _customers(report: Mapping[str, Any]) -> str:
    customers = report["customers"]
    rows = []
    for item in customers.get("top") or []:
        rows.append(
            [
                _esc(_short(item.get("name"), 42)),
                _money(item.get("rev")),
                _pct(item.get("share_pct")),
                _pct(item.get("margin_pct")),
                _delta(item.get("rev"), item.get("prior_rev")),
                _num(item.get("invoices")),
            ]
        )
    top_table = _table(
        ["Cliente", "Ventas", "Part.", "Margen", "Var.", "Facturas"],
        rows,
        numeric=[1, 2, 3, 4, 5],
    )
    stats = customers.get("stats") or {}
    recurring = stats.get("recurring") or {}
    new = stats.get("new") or {}
    lost = stats.get("lost") or {}
    stats_rows = [
        [
            "Clientes activos",
            _num(stats.get("customers")),
            _num(stats.get("prior_customers")),
        ],
        ["Concentración top 10", _pct(stats.get("top10_share_pct")), "—"],
        [
            "Clientes recurrentes",
            _num(recurring.get("customers")),
            _num(recurring.get("customers")),
        ],
        [
            "Ventas recurrentes",
            _money(recurring.get("current_rev")),
            _money(recurring.get("prior_rev")),
        ],
        ["Altas / reactivaciones", _num(new.get("customers")), _money(new.get("rev"))],
        ["Bajas", _num(lost.get("customers")), _money(lost.get("rev"))],
    ]
    stats_table = _table(
        ["Métrica", "Actual", "Referencia"],
        stats_rows,
        numeric=[1, 2],
    )
    buckets = stats.get("buckets") or {}
    bucket_rows = []
    for key, label in (
        ("one", "1 factura"),
        ("two_three", "2–3 facturas"),
        ("four_nine", "4–9 facturas"),
        ("ten_plus", "10+ facturas"),
    ):
        value = buckets.get(key) or {}
        bucket_rows.append(
            [
                label,
                _num(value.get("customers")),
                _money(value.get("rev")),
                _pct(value.get("share_pct")),
            ]
        )
    bucket_table = _table(
        ["Frecuencia", "Clientes", "Ventas", "Part."],
        bucket_rows,
        numeric=[1, 2, 3],
    )
    lists = []
    for label, key in (("Altas más grandes", "new"), ("Bajas más grandes", "lost")):
        items = (stats.get(key) or {}).get("top") or []
        list_html = "".join(
            f"<li>{_esc(item.get('name'))} — {_money(item.get('rev'))}</li>"
            for item in items
        )
        lists.append(
            f'<div class="mini"><h4>{_esc(label)}</h4><ul>{list_html}</ul></div>'
        )
    return _section(
        "Clientes",
        "<h3>Top clientes</h3>"
        + top_table
        + "<h3>Concentración y recurrencia</h3>"
        + stats_table
        + "<h3>Frecuencia de compra</h3>"
        + bucket_table
        + '<div class="mini-grid">'
        + "".join(lists)
        + "</div>",
        anchor="clientes",
    )


def _vendors(report: Mapping[str, Any]) -> str:
    rows = []
    for item in report.get("vendors") or []:
        rows.append(
            [
                _esc(_short(item.get("vendor"), 38)),
                _money(item.get("rev")),
                _pct(item.get("share_pct")),
                _pct(item.get("margin_pct")),
                _delta(item.get("rev"), item.get("prior_rev")),
                _num(item.get("customers")),
            ]
        )
    return _section(
        "Fuerza comercial",
        _table(
            ["Vendedor", "Ventas", "Part.", "Margen", "Var.", "Clientes"],
            rows,
            numeric=[1, 2, 3, 4, 5],
        ),
        note="La venta sin vendedor asignado suele corresponder a mostrador o cartera sin responsable.",
        anchor="vendedores",
    )


def _returns(report: Mapping[str, Any]) -> str:
    current = report["returns"]["current"]
    prior = report["returns"]["prior"]
    summary_rows = [
        [
            "Valor devuelto",
            _money(abs(current.get("return_rev"))),
            _money(abs(prior.get("return_rev"))),
            _delta(abs(current.get("return_rev")), abs(prior.get("return_rev"))),
        ],
        [
            "Tasa sobre venta bruta",
            _pct(current.get("return_pct")),
            _pct(prior.get("return_pct")),
            _bp(current.get("return_pct"), prior.get("return_pct")),
        ],
        [
            "Líneas",
            _num(current.get("return_lines")),
            _num(prior.get("return_lines")),
            _delta(current.get("return_lines"), prior.get("return_lines")),
        ],
    ]
    summary_table = _table(
        ["Métrica", "Actual", "Año anterior", "Variación"],
        summary_rows,
        numeric=[1, 2, 3],
    )
    cur_docs = {
        str(row.get("code")): row for row in report["returns"]["by_doc"]["current"]
    }
    prev_docs = {
        str(row.get("code")): row for row in report["returns"]["by_doc"]["prior"]
    }
    doc_rows = []
    for code in sorted(set(cur_docs) | set(prev_docs)):
        current_row = cur_docs.get(code, {})
        prior_row = prev_docs.get(code, {})
        doc_rows.append(
            [
                _esc(code),
                _esc(current_row.get("doc_name") or prior_row.get("doc_name") or ""),
                _money(abs(float(current_row.get("rev") or 0))),
                _money(abs(float(prior_row.get("rev") or 0))),
                _num(current_row.get("lines")),
            ]
        )
    doc_table = _table(
        ["Documento", "Nombre", "Actual", "Año anterior", "Líneas"],
        doc_rows,
        numeric=[2, 3, 4],
    )
    customer_rows = [
        [
            _esc(_short(item.get("name"), 42)),
            _money(abs(float(item.get("rev") or 0))),
        ]
        for item in report["returns"]["top_customers"]
    ]
    customer_table = _table(
        ["Cliente", "Devolución"],
        customer_rows,
        numeric=[1],
    )
    product_rows = [
        [
            _esc(item.get("sku")),
            _esc(_short(item.get("name"), 44)),
            _money(abs(float(item.get("rev") or 0))),
            _num(item.get("qty")),
        ]
        for item in report["returns"]["top_products"]
    ]
    product_table = _table(
        ["SKU", "Producto", "Devolución", "Unidades"],
        product_rows,
        numeric=[2, 3],
    )
    return _section(
        "Devoluciones",
        summary_table
        + "<h3>Por documento</h3>"
        + doc_table
        + "<h3>Top clientes</h3>"
        + customer_table
        + "<h3>Top productos</h3>"
        + product_table,
        anchor="devoluciones",
    )


def _inventory(report: Mapping[str, Any]) -> str:
    inventory = report.get("inventory") or {}
    if not inventory.get("available"):
        return _section(
            "Inventario",
            f'<p class="callout warn">{_esc(inventory.get("message") or "Inventario no disponible.")}</p>',
            anchor="inventario",
        )
    rows = [
        [
            "Valor del inventario",
            _money(inventory.get("total_value")),
            _money(inventory.get("total_value_prior")),
            _delta(inventory.get("total_value"), inventory.get("total_value_prior")),
        ],
        [
            "Unidades en stock",
            _num(inventory.get("total_units")),
            _num(inventory.get("total_units_prior")),
            _delta(inventory.get("total_units"), inventory.get("total_units_prior")),
        ],
        ["Días de inventario", _num(inventory.get("days"), 1), "—", "—"],
        ["Rotación anualizada", f"{_num(inventory.get('turnover'), 2)}x", "—", "—"],
        ["SKUs con stock", _num(inventory.get("stocked_sku_count")), "—", "—"],
        ["SKUs vendidos", _num(report["kpis"]["current"].get("skus")), "—", "—"],
    ]
    summary_table = _table(
        ["Métrica", "Actual", "Cierre anterior", "Variación"],
        rows,
        numeric=[1, 2, 3],
    )
    bucket_rows = []
    for key, label in (
        ("lt1", "< 1 mes"),
        ("m1_3", "1–3 meses"),
        ("m3_6", "3–6 meses"),
        ("gt6", "> 6 meses"),
        ("dead", "Sin venta (stock muerto)"),
    ):
        value = (inventory.get("buckets") or {}).get(key) or {}
        bucket_rows.append(
            [
                label,
                _num(value.get("skus")),
                _money(value.get("value")),
                _pct(value.get("share_pct"), 1),
            ]
        )
    bucket_table = _table(
        ["Cobertura", "SKUs", "Valor", "% del valor"],
        bucket_rows,
        numeric=[1, 2, 3],
    )
    over_rows = []
    for item in inventory.get("overstock") or []:
        coverage = item.get("coverage_months")
        over_rows.append(
            [
                _esc(item.get("sku")),
                _esc(_short(item.get("name"), 44)),
                _num(item.get("stock")),
                f"{_num(coverage, 1)} meses" if coverage is not None else "—",
                _money(item.get("value")),
            ]
        )
    over_table = _table(
        ["SKU", "Producto", "Stock", "Cobertura", "Valor"],
        over_rows,
        numeric=[2, 3, 4],
    )
    dead_rows = [
        [
            _esc(item.get("sku")),
            _esc(_short(item.get("name"), 44)),
            _num(item.get("stock")),
            _money(item.get("value")),
        ]
        for item in inventory.get("dead_stock") or []
    ]
    dead_table = _table(
        ["SKU", "Producto", "Stock", "Valor"],
        dead_rows,
        numeric=[2, 3],
    )
    return _section(
        "Inventario",
        summary_table
        + "<h3>Cobertura</h3>"
        + bucket_table
        + "<h3>Mayores excesos</h3>"
        + over_table
        + "<h3>Stock muerto</h3>"
        + dead_table,
        note="Valorado al último costo de J3System; la cobertura usa las unidades vendidas del período.",
        anchor="inventario",
    )


def _recommendations(report: Mapping[str, Any]) -> str:
    actions = {
        "El crecimiento depende de canales nuevos": (
            "Defender y expandir el canal nuevo; diagnosticar la caída de los canales existentes.",
            "Sostener el crecimiento y recuperar el núcleo",
            "30–60 días",
        ),
        "Mayor peso de promociones": (
            "Gobierno de promociones: margen mínimo, límite de participación y medición de canibalización.",
            "Evitar nueva dilución de margen",
            "30 días",
        ),
        "La base recurrente se contrae": (
            "Plan de retención de cuentas clave y recuperación de clientes recurrentes.",
            "Frenar la caída de la base instalada",
            "15–30 días",
        ),
        "Devoluciones al alza": (
            "Causas raíz por producto y cliente; aprobación y seguimiento semanal.",
            "Bajar la tasa de devolución",
            "60 días",
        ),
        "El inventario crece más que la venta": (
            "Compra controlada y liquidación de SKUs de baja rotación.",
            "Liberar caja y reducir días de inventario",
            "60–90 días",
        ),
        "Inventario de baja rotación": (
            "Liquidación selectiva y revisión de surtido de SKUs >6 meses.",
            "Reducir obsolescencia",
            "60–90 días",
        ),
        "Riesgo de quiebre en alta rotación": (
            "Reposición urgente de SKUs con <1 mes de cobertura.",
            "Evitar pérdida de venta",
            "7–15 días",
        ),
        "Brecha de datos maestros": (
            "Completar marca, rubro, subrubro y proveedor de los SKUs sin maestro.",
            "Reportes confiables por rubro/proveedor",
            "15 días",
        ),
        "Concentración de clientes": (
            "Plan de cuentas clave y diversificación de la cartera.",
            "Reducir dependencia de pocas cuentas",
            "30–60 días",
        ),
        "El margen bruto se movió": (
            "Revisar mezcla, precio y costo de compra por familia.",
            "Recuperar o sostener el margen",
            "30–60 días",
        ),
    }
    rows = []
    for finding in report.get("findings") or []:
        action = actions.get(finding.get("title"))
        if not action:
            continue
        rows.append(
            [
                f'<span class="badge {str(finding.get("priority") or "media").lower()}">'
                f'{_esc(finding.get("priority") or "Media")}</span>',
                _esc(action[0]),
                _esc(action[1]),
                _esc(action[2]),
            ]
        )
    if not rows:
        rows.append(
            [
                '<span class="badge baja">Baja</span>',
                "Mantener el seguimiento mensual de los indicadores.",
                "Monitoreo",
                "30 días",
            ]
        )
    return _section(
        "Plan de acción",
        _table(["Prioridad", "Acción", "Impacto esperado", "Plazo"], rows),
        anchor="plan",
    )


def _methodology(report: Mapping[str, Any]) -> str:
    excluded = ", ".join(report.get("excluded_document_codes") or [])
    period = report["period"]
    items = [
        (
            f"Rango solicitado: {period.get('requested_start', period['start'])} "
            f"a {period.get('requested_end', period['end'])}; "
            f"datos usados: {period['start']} a {period['end']}; "
            f"comparativo: {period['prior_start']} a {period['prior_end']}."
        ),
        "Marca: coincidencia con la marca maestra de `productos_adicional`, categoría de marca o nombre del artículo cuando el maestro no tiene marca.",
        f"Documentos excluidos: {excluded}. Las devoluciones se incluyen y reducen las ventas netas.",
        "Inventario: saldo de J3System en bodegas comerciales (ALM, SUR, BD6, DIS, FLO), excluye servicios; corresponde al año de corte, no al saldo histórico a la fecha final.",
        "La proyección es un run-rate simple del período, no un presupuesto.",
    ]
    body = "<ul>" + "".join(f"<li>{_esc(item)}</li>" for item in items) + "</ul>"
    return _section("Metodología y limitaciones", body, anchor="metodologia")


def render_html(report: Mapping[str, Any]) -> str:
    brand = _esc(report.get("brand_label") or report.get("brand"))
    period = report["period"]
    requested_start = period.get("requested_start", period["start"])
    requested_end = period.get("requested_end", period["end"])
    requested = f"{requested_start} a {requested_end}"
    actual = f"{period['start']} a {period['end']}"
    if requested == actual:
        subtitle = f"{actual} vs. {period['prior_start']} a {period['prior_end']}"
    else:
        subtitle = (
            f"solicitado {requested} · datos {actual} vs. "
            f"{period['prior_start']} a {period['prior_end']}"
        )
    body = "".join(
        [
            _summary(report),
            _kpis(report),
            _annual(report),
            _monthly(report),
            _channels(report),
            _products(report),
            _customers(report),
            _vendors(report),
            _returns(report),
            _inventory(report),
            _recommendations(report),
            _methodology(report),
        ]
    )
    nav = "".join(
        f'<a href="#{anchor}">{label}</a>'
        for anchor, label in (
            ("resumen", "Resumen"),
            ("tablero", "Tablero"),
            ("anual", "Anual"),
            ("mensual", "Mensual"),
            ("canales", "Canales"),
            ("productos", "Productos"),
            ("clientes", "Clientes"),
            ("vendedores", "Vendedores"),
            ("devoluciones", "Devoluciones"),
            ("inventario", "Inventario"),
            ("plan", "Plan"),
        )
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Informe de marca {brand}</title>
<style>
:root {{
  --bg: #f6f7f9;
  --surface: #ffffff;
  --fg: #1b2430;
  --muted: #64748b;
  --border: #dbe2ea;
  --accent: #0f766e;
  --accent-soft: #e6f4f1;
  --good: #15803d;
  --bad: #b91c1c;
  --warn: #b45309;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--bg); color: var(--fg);
  font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
}}
header.hero {{
  background: linear-gradient(135deg, #0f172a, #115e59);
  color: #f8fafc; padding: 28px 24px 22px;
}}
.wrap {{ max-width: 1180px; margin: 0 auto; }}
header.hero h1 {{ margin: 0 0 6px; font-size: 28px; letter-spacing: -0.02em; }}
header.hero .meta {{ color: #cbd5e1; font-size: 13px; }}
nav.toc {{
  position: sticky; top: 0; z-index: 5; background: rgba(255,255,255,.94);
  border-bottom: 1px solid var(--border); padding: 8px 24px;
  backdrop-filter: blur(8px);
}}
nav.toc .wrap {{ display: flex; gap: 16px; overflow-x: auto; }}
nav.toc a {{ color: var(--muted); text-decoration: none; font-size: 12px; white-space: nowrap; }}
nav.toc a:hover {{ color: var(--accent); }}
main {{ padding: 22px 24px 60px; }}
.section {{
  background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
  padding: 20px 22px; margin: 0 0 18px; box-shadow: 0 1px 2px rgba(15,23,42,.04);
}}
.section h2 {{ margin: 0 0 12px; font-size: 20px; }}
.section h3 {{ margin: 22px 0 8px; font-size: 15px; color: #334155; }}
.section-note {{ color: var(--muted); font-size: 12px; margin: -4px 0 12px; }}
.kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 16px; }}
.kpi {{
  border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px;
  background: #fbfcfd;
}}
.kpi.accent {{ background: var(--accent-soft); border-color: #b7e2da; }}
.kpi-label {{ display: block; color: var(--muted); font-size: 12px; }}
.kpi-value {{ display: block; font-size: 22px; margin: 2px 0; letter-spacing: -0.02em; }}
.kpi-sub {{ font-size: 12px; color: var(--muted); }}
.table-wrap {{ overflow-x: auto; margin: 6px 0 10px; }}
table.table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
table.table th, table.table td {{ padding: 7px 9px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: top; }}
table.table th {{ background: #f1f5f9; color: #334155; font-weight: 600; font-size: 12px; white-space: nowrap; }}
table.table td.num, table.table th.num {{ text-align: right; white-space: nowrap; }}
table.table tr:last-child td {{ border-bottom: none; }}
.empty {{ color: var(--muted); text-align: center; }}
.pos {{ color: var(--good); }}
.neg {{ color: var(--bad); }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; }}
.badge.alta {{ background: #fee2e2; color: #991b1b; }}
.badge.media {{ background: #fef3c7; color: #92400e; }}
.badge.baja {{ background: #dcfce7; color: #166534; }}
.callout {{ background: #f8fafc; border-left: 3px solid var(--accent); padding: 10px 12px; border-radius: 0 8px 8px 0; }}
.callout.warn {{ border-left-color: var(--warn); background: #fffbeb; }}
.mini-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }}
.mini {{ border: 1px solid var(--border); border-radius: 10px; padding: 10px 14px; }}
.mini h4 {{ margin: 0 0 6px; font-size: 13px; }}
.mini ul {{ margin: 0; padding-left: 18px; }}
.mini li {{ margin: 3px 0; }}
footer {{ color: var(--muted); font-size: 12px; text-align: center; padding: 10px 0 30px; }}
@media print {{
  header.hero {{ background: #0f172a !important; -webkit-print-color-adjust: exact; }}
  nav.toc {{ display: none; }}
  .section {{ box-shadow: none; break-inside: avoid; }}
}}
</style>
</head>
<body>
<header class="hero"><div class="wrap">
  <h1>Informe de marca — {brand}</h1>
  <div class="meta">Corte {period['end']} · {subtitle} · cifras en millones de COP</div>
</div></header>
<nav class="toc"><div class="wrap">{nav}</div></nav>
<main class="wrap">{body}
<footer>Generado a partir de banco_datos, productos_adicional y J3System. Pueden existir diferencias por redondeo.</footer>
</main>
</body>
</html>"""
