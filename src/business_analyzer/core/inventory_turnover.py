"""Inventory turnover (Rotación de Existencias) analytics.

Commercial demand (default): per warehouse from J3 ``InvVentas`` +
``InvVentasDetalle`` + ``AdmDocumentos`` (canonical sales document exclusions).
Fallback: company-wide SKU demand from SmartBusiness ``banco_datos``.

Stock from J3 ``InvDetalleExistencias`` on commercial warehouses only.
Physical exits via monthly ``Salidas*`` (inventory postings; not sales filter).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, cast

from business_analyzer.core.database import Database, qualified_sb_table
from business_analyzer.core.inventory_warehouse_policy import (
    is_turnover_sku_denied,
    turnover_policy_summary,
    turnover_sku_denylist_sql_not_like,
    turnover_warehouse_sql_in_list,
)
from business_analyzer.core.j3system_sales_warehouse import (
    _validate_period_date,
    qualified_j3_table,
)
from depotru_kernel.documents import (
    CANONICAL_EXCLUDED_DOCUMENT_CODES,
    excluded_document_sql_in_list,
)

DEFAULT_VELOCITY_DAYS = 90
DEFAULT_MIN_VELOCITY_QTY = 20
DEFAULT_QUIEBRE_DAYS = 7
DEFAULT_BAJA_COBERTURA_DAYS = 30
DEFAULT_OVERSTOCK_DAYS = 120
DEFAULT_TOP_N = 50
DEFAULT_MIN_STOCK_OVERSTOCK = 1.0

# warehouse = SKU×bodega demand (InvVentasDetalle); company = SKU-only (banco_datos)
DEMAND_MODE_WAREHOUSE = "warehouse"
DEMAND_MODE_COMPANY = "company"
DEFAULT_DEMAND_MODE = DEMAND_MODE_WAREHOUSE

BAND_QUIEBRE = "QUIEBRE"
BAND_BAJA_COBERTURA = "BAJA_COBERTURA"
BAND_SALUDABLE = "SALUDABLE"
BAND_SOBRESTOCK = "SOBRESTOCK"
BAND_MUERTO = "MUERTO"
BAND_SIN_MOVIMIENTO_SIN_STOCK = "SIN_MOVIMIENTO_SIN_STOCK"


def _positive_int(value: int, name: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def classify_turnover_band(
    stock: float,
    venta_comercial_nd: float,
    dias_cobertura: Optional[float],
    *,
    min_velocity_qty: float = DEFAULT_MIN_VELOCITY_QTY,
    quiebre_days: float = DEFAULT_QUIEBRE_DAYS,
    baja_cobertura_days: float = DEFAULT_BAJA_COBERTURA_DAYS,
    overstock_days: float = DEFAULT_OVERSTOCK_DAYS,
    min_stock_overstock: float = DEFAULT_MIN_STOCK_OVERSTOCK,
) -> str:
    """Classify a SKU×warehouse row into an action band (commercial demand)."""
    has_demand = venta_comercial_nd >= min_velocity_qty
    no_sales = venta_comercial_nd <= 0

    if stock <= 0 and no_sales:
        return BAND_SIN_MOVIMIENTO_SIN_STOCK
    if stock <= 0:
        return BAND_QUIEBRE
    if no_sales:
        return BAND_MUERTO
    if dias_cobertura is not None and has_demand and dias_cobertura < quiebre_days:
        return BAND_QUIEBRE
    if (
        dias_cobertura is not None
        and has_demand
        and dias_cobertura < baja_cobertura_days
    ):
        return BAND_BAJA_COBERTURA
    if (
        dias_cobertura is not None
        and stock >= min_stock_overstock
        and dias_cobertura > overstock_days
    ):
        return BAND_SOBRESTOCK
    # Positive stock with commercial demand remaining after quiebre /
    # baja / sobrestock checks (or cover days unavailable). Stock<=0 and
    # no_sales already returned above.
    return BAND_SALUDABLE


def commercial_cover_days(stock: float, venta_diaria: float) -> Optional[float]:
    """Days of cover from commercial daily demand; None if no demand."""
    if venta_diaria <= 0:
        return None
    return stock / venta_diaria


def annualized_turns(
    venta_nd: float, stock: float, velocity_days: int
) -> Optional[float]:
    """Unit turns per year from commercial demand and positive stock."""
    if stock <= 0 or velocity_days <= 0:
        return None
    return (venta_nd * (365.0 / velocity_days)) / stock


def build_commercial_demand_cte(
    *,
    as_of_date: str,
    velocity_days: int = DEFAULT_VELOCITY_DAYS,
    sb_database: Optional[str] = None,
) -> str:
    """CTE: commercial demand per SKU (company-wide; banco_datos + exclusions)."""
    banco = qualified_sb_table("banco_datos", sb_database)
    days = _positive_int(velocity_days, "velocity_days")
    as_of = _validate_period_date(as_of_date, "as_of_date")
    excluded = excluded_document_sql_in_list()
    return f"""
demanda_comercial AS (
    SELECT
        ArticulosCodigo,
        SUM(Cantidad) AS Venta_Comercial_Nd,
        SUM(Cantidad) / {days}.0 AS Venta_Diaria_Comercial
    FROM {banco}
    WHERE Fecha >= DATEADD(DAY, -{days}, CAST('{as_of}' AS DATE))
      AND Fecha <= CAST('{as_of}' AS DATE)
      AND DocumentosCodigo NOT IN ({excluded})
      AND Cantidad <> 0
    GROUP BY ArticulosCodigo
)""".strip()


def build_commercial_demand_by_warehouse_cte(
    *,
    as_of_date: str,
    velocity_days: int = DEFAULT_VELOCITY_DAYS,
    j3_database: Optional[str] = None,
    warehouse_codes: Optional[Sequence[str]] = None,
) -> str:
    """CTE: commercial demand per SKU×warehouse from J3 sales lines.

    Uses ``InvVentasDetalle.AlmacenID`` for physical bodega of the sale and
    ``AdmDocumentos.DocumentosCodigo`` with the same sales exclusions as
    ``banco_datos`` (not inventory-only exits like TS/ISC).
    """
    days = _positive_int(velocity_days, "velocity_days")
    as_of = _validate_period_date(as_of_date, "as_of_date")
    excluded = excluded_document_sql_in_list()
    wh_in = turnover_warehouse_sql_in_list(warehouse_codes)
    inv_ventas = qualified_j3_table("InvVentas", j3_database)
    inv_detalle = qualified_j3_table("InvVentasDetalle", j3_database)
    articulos = qualified_j3_table("AdmArticulos", j3_database)
    almacen = qualified_j3_table("AdmAlmacen", j3_database)
    documentos = qualified_j3_table("AdmDocumentos", j3_database)
    return f"""
demanda_comercial AS (
    SELECT
        art.ArticulosCodigo,
        al.AlmacenCodigo,
        SUM(d.Cantidad) AS Venta_Comercial_Nd,
        SUM(d.Cantidad) / {days}.0 AS Venta_Diaria_Comercial
    FROM {inv_ventas} v
    JOIN {inv_detalle} d ON d.VentaID = v.VentaID
    JOIN {articulos} art ON art.ArticulosID = d.ArticulosID
    JOIN {almacen} al ON al.AlmacenID = d.AlmacenID
    JOIN {documentos} doc ON doc.DocumentosID = v.DocumentosID
    WHERE v.Fecha >= DATEADD(DAY, -{days}, CAST('{as_of}' AS DATE))
      AND v.Fecha <= CAST('{as_of}' AS DATE)
      AND doc.DocumentosCodigo NOT IN ({excluded})
      AND d.Cantidad <> 0
      AND al.AlmacenCodigo IN ({wh_in})
    GROUP BY art.ArticulosCodigo, al.AlmacenCodigo
)""".strip()


def build_commercial_stock_cte(
    *,
    inventory_year: Optional[int] = None,
    j3_database: Optional[str] = None,
    warehouse_codes: Optional[Sequence[str]] = None,
) -> str:
    """CTE: stock on commercial warehouses (negatives kept)."""
    detalle = qualified_j3_table("InvDetalleExistencias", j3_database)
    existencias = qualified_j3_table("InvExistencias", j3_database)
    articulos = qualified_j3_table("AdmArticulos", j3_database)
    almacen = qualified_j3_table("AdmAlmacen", j3_database)
    wh_in = turnover_warehouse_sql_in_list(warehouse_codes)
    sku_deny = turnover_sku_denylist_sql_not_like()
    year_filter = (
        f"d.Ano = {int(inventory_year)}"
        if inventory_year is not None
        else f"d.Ano = (SELECT MAX(Ano) FROM {detalle})"
    )
    # Physical YTD exits from monthly columns (inventory postings, not sales filter)
    salidas_sum = (
        "CAST(d.SalidasEne AS DECIMAL(18,4)) + CAST(d.SalidasFeb AS DECIMAL(18,4)) + "
        "CAST(d.SalidasMar AS DECIMAL(18,4)) + CAST(d.SalidasAbr AS DECIMAL(18,4)) + "
        "CAST(d.SalidasMay AS DECIMAL(18,4)) + CAST(d.SalidasJun AS DECIMAL(18,4)) + "
        "CAST(d.SalidasJul AS DECIMAL(18,4)) + CAST(d.SalidasAgo AS DECIMAL(18,4)) + "
        "CAST(d.SalidasSep AS DECIMAL(18,4)) + CAST(d.SalidasOct AS DECIMAL(18,4)) + "
        "CAST(d.SalidasNov AS DECIMAL(18,4)) + CAST(d.SalidasDic AS DECIMAL(18,4))"
    )
    return f"""
stock_comercial AS (
    SELECT
        a.ArticulosCodigo,
        a.ArticulosNombre,
        al.AlmacenCodigo,
        al.AlmacenNombre,
        CAST(d.SaldoActual AS DECIMAL(18, 4)) AS Stock,
        CAST(d.StockMinimo AS DECIMAL(18, 4)) AS Stock_Minimo,
        CAST(d.StockMaximo AS DECIMAL(18, 4)) AS Stock_Maximo,
        ({salidas_sum}) AS Salida_Fisica_Ytd,
        d.Ano AS Ano_Inventario
    FROM {detalle} d
    JOIN {existencias} e ON e.ExistenciasID = d.ExistenciasID
    JOIN {articulos} a ON a.ArticulosID = e.ArticulosID
    JOIN {almacen} al ON al.AlmacenID = d.AlmacenID
    WHERE {year_filter}
      AND al.AlmacenCodigo IN ({wh_in})
      AND NOT ({sku_deny})
)""".strip()


def build_turnover_detail_sql(
    as_of_date: str,
    *,
    velocity_days: int = DEFAULT_VELOCITY_DAYS,
    top_n: Optional[int] = None,
    inventory_year: Optional[int] = None,
    j3_database: Optional[str] = None,
    sb_database: Optional[str] = None,
    warehouse_codes: Optional[Sequence[str]] = None,
    demand_mode: str = DEFAULT_DEMAND_MODE,
) -> str:
    """SKU×warehouse detail with commercial demand and physical YTD exits.

    ``demand_mode``:
      - ``warehouse`` (default): join demand on SKU + AlmacenCodigo (J3 lines)
      - ``company``: join demand on SKU only (banco_datos company-wide)
    """
    mode = (demand_mode or DEFAULT_DEMAND_MODE).strip().lower()
    if mode not in (DEMAND_MODE_WAREHOUSE, DEMAND_MODE_COMPANY):
        raise ValueError(
            f"demand_mode must be '{DEMAND_MODE_WAREHOUSE}' or "
            f"'{DEMAND_MODE_COMPANY}', got {demand_mode!r}"
        )
    if mode == DEMAND_MODE_WAREHOUSE:
        demand = build_commercial_demand_by_warehouse_cte(
            as_of_date=as_of_date,
            velocity_days=velocity_days,
            j3_database=j3_database,
            warehouse_codes=warehouse_codes,
        )
        join_on = (
            "dc.ArticulosCodigo = sc.ArticulosCodigo "
            "AND dc.AlmacenCodigo = sc.AlmacenCodigo"
        )
    else:
        demand = build_commercial_demand_cte(
            as_of_date=as_of_date,
            velocity_days=velocity_days,
            sb_database=sb_database,
        )
        join_on = "dc.ArticulosCodigo = sc.ArticulosCodigo"
    stock = build_commercial_stock_cte(
        inventory_year=inventory_year,
        j3_database=j3_database,
        warehouse_codes=warehouse_codes,
    )
    _validate_period_date(as_of_date, "as_of_date")
    top_clause = f"TOP ({_positive_int(top_n, 'top_n')}) " if top_n else ""
    return f"""
WITH {demand},
{stock}
SELECT {top_clause}
    sc.ArticulosCodigo AS SKU,
    sc.ArticulosNombre AS Producto,
    sc.AlmacenCodigo,
    sc.AlmacenNombre,
    sc.Stock,
    sc.Stock_Minimo,
    sc.Stock_Maximo,
    sc.Salida_Fisica_Ytd,
    sc.Ano_Inventario,
    ISNULL(dc.Venta_Comercial_Nd, 0) AS Venta_Comercial_Nd,
    ISNULL(dc.Venta_Diaria_Comercial, 0) AS Venta_Diaria_Comercial,
    CASE
        WHEN ISNULL(dc.Venta_Diaria_Comercial, 0) > 0
        THEN sc.Stock / dc.Venta_Diaria_Comercial
        ELSE NULL
    END AS Dias_Cobertura_Comercial
FROM stock_comercial sc
LEFT JOIN demanda_comercial dc ON {join_on}
WHERE sc.Stock <> 0
   OR ISNULL(dc.Venta_Comercial_Nd, 0) <> 0
ORDER BY
    CASE
        WHEN ISNULL(dc.Venta_Diaria_Comercial, 0) > 0
        THEN sc.Stock / dc.Venta_Diaria_Comercial
        ELSE 999999
    END,
    ISNULL(dc.Venta_Comercial_Nd, 0) DESC;
""".strip()


def enrich_detail_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    velocity_days: int = DEFAULT_VELOCITY_DAYS,
    min_velocity_qty: float = DEFAULT_MIN_VELOCITY_QTY,
    quiebre_days: float = DEFAULT_QUIEBRE_DAYS,
    baja_cobertura_days: float = DEFAULT_BAJA_COBERTURA_DAYS,
    overstock_days: float = DEFAULT_OVERSTOCK_DAYS,
) -> List[Dict[str, Any]]:
    """Add Bandera and Rotacion_Anualizada_Comercial to detail rows."""
    out: List[Dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        stock = _as_float(row.get("Stock"))
        venta = _as_float(row.get("Venta_Comercial_Nd"))
        venta_diaria = _as_float(row.get("Venta_Diaria_Comercial"))
        cover = row.get("Dias_Cobertura_Comercial")
        cover_f: Optional[float]
        if cover is None and venta_diaria > 0:
            cover_f = commercial_cover_days(stock, venta_diaria)
        elif cover is None:
            cover_f = None
        else:
            cover_f = _as_float(cover)
            row["Dias_Cobertura_Comercial"] = cover_f
        row["Bandera"] = classify_turnover_band(
            stock,
            venta,
            cover_f,
            min_velocity_qty=min_velocity_qty,
            quiebre_days=quiebre_days,
            baja_cobertura_days=baja_cobertura_days,
            overstock_days=overstock_days,
        )
        row["Rotacion_Anualizada_Comercial"] = annualized_turns(
            venta, stock, velocity_days
        )
        out.append(row)
    return out


def turnover_summary_from_rows(
    rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Executive scorecard from enriched detail rows."""
    if not rows:
        return {
            "Filas": 0,
            "SKUs_Con_Stock": 0,
            "SKUs_Con_Venta": 0,
            "QUIEBRE": 0,
            "BAJA_COBERTURA": 0,
            "SALUDABLE": 0,
            "SOBRESTOCK": 0,
            "MUERTO": 0,
            "SIN_MOVIMIENTO_SIN_STOCK": 0,
            "Stock_Total_Unidades": 0.0,
            "Stock_Unidades_Muerto": 0.0,
            "Share_Unidades_Muerto": 0.0,
            "Mediana_Dias_Cobertura": None,
        }

    bands = {
        BAND_QUIEBRE: 0,
        BAND_BAJA_COBERTURA: 0,
        BAND_SALUDABLE: 0,
        BAND_SOBRESTOCK: 0,
        BAND_MUERTO: 0,
        BAND_SIN_MOVIMIENTO_SIN_STOCK: 0,
    }
    stock_total = 0.0
    stock_muerto = 0.0
    with_stock = 0
    with_venta = 0
    covers: List[float] = []

    for r in rows:
        band = str(r.get("Bandera") or "")
        if band in bands:
            bands[band] += 1
        stock = _as_float(r.get("Stock"))
        venta = _as_float(r.get("Venta_Comercial_Nd"))
        stock_total += stock
        if stock > 0:
            with_stock += 1
        if venta != 0:
            with_venta += 1
        if band == BAND_MUERTO and stock > 0:
            stock_muerto += stock
        cover = r.get("Dias_Cobertura_Comercial")
        if cover is not None and venta > 0:
            covers.append(_as_float(cover))

    covers_sorted = sorted(covers)
    median = None
    if covers_sorted:
        mid = len(covers_sorted) // 2
        if len(covers_sorted) % 2:
            median = covers_sorted[mid]
        else:
            median = (covers_sorted[mid - 1] + covers_sorted[mid]) / 2.0

    share = (stock_muerto / stock_total) if stock_total > 0 else 0.0
    return {
        "Filas": len(rows),
        "SKUs_Con_Stock": with_stock,
        "SKUs_Con_Venta": with_venta,
        **bands,
        "Stock_Total_Unidades": stock_total,
        "Stock_Unidades_Muerto": stock_muerto,
        "Share_Unidades_Muerto": share,
        "Mediana_Dias_Cobertura": median,
    }


def action_quiebre(
    rows: Sequence[Mapping[str, Any]],
    *,
    top_n: int = DEFAULT_TOP_N,
    one_row_per_sku: bool = True,
) -> List[Dict[str, Any]]:
    """Buy/transfer list: QUIEBRE ranked by demand then lowest cover.

    When ``one_row_per_sku`` is True (default), keep the worst commercial
    warehouse per SKU (lowest cover, then highest demand) to reduce noise.
    """
    filtered = [
        dict(r)
        for r in rows
        if r.get("Bandera") == BAND_QUIEBRE
        and not is_turnover_sku_denied(
            str(r.get("SKU") or ""), str(r.get("Producto") or "")
        )
    ]

    def sort_key(r: Mapping[str, Any]) -> tuple:
        cover = r.get("Dias_Cobertura_Comercial")
        cover_f = _as_float(cover) if cover is not None else 999999.0
        return (-_as_float(r.get("Venta_Comercial_Nd")), cover_f)

    if one_row_per_sku:
        best: Dict[str, Dict[str, Any]] = {}
        for r in filtered:
            sku = str(r.get("SKU") or "")
            if not sku:
                continue
            prev = best.get(sku)
            if prev is None:
                best[sku] = r
                continue
            # Prefer lower cover, then higher demand
            c_new = r.get("Dias_Cobertura_Comercial")
            c_old = prev.get("Dias_Cobertura_Comercial")
            c_new_f = _as_float(c_new) if c_new is not None else 999999.0
            c_old_f = _as_float(c_old) if c_old is not None else 999999.0
            if c_new_f < c_old_f or (
                c_new_f == c_old_f
                and _as_float(r.get("Venta_Comercial_Nd"))
                > _as_float(prev.get("Venta_Comercial_Nd"))
            ):
                best[sku] = r
        filtered = list(best.values())

    filtered.sort(key=sort_key)
    return filtered[: max(0, int(top_n))]


def action_capital_atrapado(
    rows: Sequence[Mapping[str, Any]], *, top_n: int = DEFAULT_TOP_N
) -> List[Dict[str, Any]]:
    """Dead + overstock ranked by stock units descending."""
    filtered = [
        dict(r)
        for r in rows
        if r.get("Bandera") in (BAND_MUERTO, BAND_SOBRESTOCK)
        and _as_float(r.get("Stock")) > 0
        and not is_turnover_sku_denied(
            str(r.get("SKU") or ""), str(r.get("Producto") or "")
        )
    ]
    filtered.sort(key=lambda r: -_as_float(r.get("Stock")))
    return filtered[: max(0, int(top_n))]


def suggested_transfers(
    rows: Sequence[Mapping[str, Any]],
    *,
    top_n: int = DEFAULT_TOP_N,
    min_surplus: float = 10.0,
    surplus_bands: Sequence[str] = (BAND_SOBRESTOCK, BAND_SALUDABLE),
) -> List[Dict[str, Any]]:
    """Suggest WH→WH moves: surplus stock vs quiebre deficit for the same SKU."""
    by_sku: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        sku = str(r.get("SKU") or "")
        if not sku or is_turnover_sku_denied(sku, str(r.get("Producto") or "")):
            continue
        by_sku.setdefault(sku, []).append(dict(r))

    suggestions: List[Dict[str, Any]] = []
    for sku, items in by_sku.items():
        deficits = [
            x
            for x in items
            if x.get("Bandera") == BAND_QUIEBRE
            and _as_float(x.get("Venta_Comercial_Nd")) > 0
        ]
        surpluses = [
            x
            for x in items
            if x.get("Bandera") in surplus_bands
            and _as_float(x.get("Stock")) >= min_surplus
        ]
        if not deficits or not surpluses:
            continue
        deficits.sort(key=lambda x: _as_float(x.get("Dias_Cobertura_Comercial") or 0))
        surpluses.sort(key=lambda x: -_as_float(x.get("Stock")))
        for deficit in deficits:
            for surplus in surpluses:
                if surplus.get("AlmacenCodigo") == deficit.get("AlmacenCodigo"):
                    continue
                stock_from = _as_float(surplus.get("Stock"))
                stock_to = _as_float(deficit.get("Stock"))
                need = max(-stock_to, 0.0) + max(
                    _as_float(deficit.get("Venta_Diaria_Comercial")) * 14
                    - max(stock_to, 0.0),
                    0.0,
                )
                move = min(stock_from * 0.5, need if need > 0 else stock_from * 0.25)
                if move < 1:
                    continue
                suggestions.append(
                    {
                        "SKU": sku,
                        "Producto": deficit.get("Producto") or surplus.get("Producto"),
                        "Desde": surplus.get("AlmacenCodigo"),
                        "Hacia": deficit.get("AlmacenCodigo"),
                        "Stock_Origen": stock_from,
                        "Stock_Destino": stock_to,
                        "Venta_Destino_Nd": _as_float(
                            deficit.get("Venta_Comercial_Nd")
                        ),
                        "Sugerido_Mover": round(move, 1),
                        "Bandera_Origen": surplus.get("Bandera"),
                        "Bandera_Destino": deficit.get("Bandera"),
                    }
                )
    suggestions.sort(
        key=lambda x: (
            -_as_float(x.get("Venta_Destino_Nd")),
            -_as_float(x.get("Sugerido_Mover")),
        )
    )
    return suggestions[: max(0, int(top_n))]


def salida_fisica_quality_note(rows: Sequence[Mapping[str, Any]]) -> Optional[str]:
    """Banner when monthly physical exits look empty/stale."""
    if not rows:
        return None
    total = sum(abs(_as_float(r.get("Salida_Fisica_Ytd"))) for r in rows)
    if total <= 0:
        return (
            "Salida física YTD (`SalidasEne…Dic`) es 0 en todas las filas — "
            "posible dato mensual vacío; no usar esa columna para decisiones."
        )
    return None


def abc_by_commercial_velocity(
    rows: Sequence[Mapping[str, Any]],
    *,
    demand_mode: str = DEFAULT_DEMAND_MODE,
) -> List[Dict[str, Any]]:
    """ABC classes on distinct SKUs by commercial units sold (A=80%, B=15%, C=5%).

    For ``warehouse`` demand, sums Venta across bodegas. For ``company`` demand
    (repeated per row), takes max so company-wide qty is not multi-counted.
    """
    mode = (demand_mode or DEFAULT_DEMAND_MODE).strip().lower()
    by_sku: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        sku = str(r.get("SKU") or "")
        if not sku:
            continue
        bucket = by_sku.setdefault(
            sku,
            {
                "SKU": sku,
                "Producto": r.get("Producto"),
                "Venta_Comercial_Nd": 0.0,
                "Stock": 0.0,
            },
        )
        venta = _as_float(r.get("Venta_Comercial_Nd"))
        if mode == DEMAND_MODE_COMPANY:
            if venta > _as_float(bucket["Venta_Comercial_Nd"]):
                bucket["Venta_Comercial_Nd"] = venta
                bucket["Producto"] = r.get("Producto")
        else:
            bucket["Venta_Comercial_Nd"] = (
                _as_float(bucket["Venta_Comercial_Nd"]) + venta
            )
            if r.get("Producto"):
                bucket["Producto"] = r.get("Producto")
        bucket["Stock"] = _as_float(bucket["Stock"]) + _as_float(r.get("Stock"))

    ranked = sorted(by_sku.values(), key=lambda x: -_as_float(x["Venta_Comercial_Nd"]))
    total_venta = sum(_as_float(x["Venta_Comercial_Nd"]) for x in ranked)
    total_stock = sum(max(_as_float(x["Stock"]), 0.0) for x in ranked)
    cum = 0.0
    out: List[Dict[str, Any]] = []
    for item in ranked:
        v = _as_float(item["Venta_Comercial_Nd"])
        cum += v
        share = (cum / total_venta) if total_venta > 0 else 1.0
        if share <= 0.80:
            abc = "A"
        elif share <= 0.95:
            abc = "B"
        else:
            abc = "C"
        stock = max(_as_float(item["Stock"]), 0.0)
        out.append(
            {
                "SKU": item["SKU"],
                "Producto": item["Producto"],
                "Venta_Comercial_Nd": v,
                "Stock": stock,
                "ABC": abc,
                "Share_Venta_Acum": share,
                "Share_Stock": (stock / total_stock) if total_stock > 0 else 0.0,
            }
        )
    return out


def by_warehouse_from_rows(
    rows: Sequence[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Band counts and stock totals per warehouse."""
    buckets: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        code = str(r.get("AlmacenCodigo") or "")
        if not code:
            continue
        b = buckets.setdefault(
            code,
            {
                "AlmacenCodigo": code,
                "AlmacenNombre": r.get("AlmacenNombre"),
                "Filas": 0,
                "QUIEBRE": 0,
                "MUERTO": 0,
                "SOBRESTOCK": 0,
                "SALUDABLE": 0,
                "BAJA_COBERTURA": 0,
                "Stock_Total": 0.0,
                "_covers": [],
            },
        )
        b["Filas"] += 1
        band = str(r.get("Bandera") or "")
        if band in b:
            b[band] += 1
        b["Stock_Total"] += _as_float(r.get("Stock"))
        cover = r.get("Dias_Cobertura_Comercial")
        if cover is not None and _as_float(r.get("Venta_Comercial_Nd")) > 0:
            b["_covers"].append(_as_float(cover))

    out: List[Dict[str, Any]] = []
    for b in buckets.values():
        covers = b.pop("_covers")
        covers.sort()
        median = None
        if covers:
            mid = len(covers) // 2
            median = (
                covers[mid]
                if len(covers) % 2
                else (covers[mid - 1] + covers[mid]) / 2.0
            )
        b["Mediana_Dias_Cobertura"] = median
        out.append(b)
    out.sort(key=lambda x: -_as_float(x.get("QUIEBRE")))
    return out


class InventoryTurnoverRunner:
    """Execute turnover SQL and assemble the decision report."""

    def __init__(
        self,
        db: Optional[Database] = None,
        *,
        j3_database: Optional[str] = None,
        sb_database: Optional[str] = None,
        velocity_days: int = DEFAULT_VELOCITY_DAYS,
        min_velocity_qty: float = DEFAULT_MIN_VELOCITY_QTY,
        quiebre_days: float = DEFAULT_QUIEBRE_DAYS,
        baja_cobertura_days: float = DEFAULT_BAJA_COBERTURA_DAYS,
        overstock_days: float = DEFAULT_OVERSTOCK_DAYS,
        top_n: int = DEFAULT_TOP_N,
        inventory_year: Optional[int] = None,
        warehouse_codes: Optional[Sequence[str]] = None,
        demand_mode: str = DEFAULT_DEMAND_MODE,
    ) -> None:
        self.db = db or Database()
        self.j3_database = j3_database
        self.sb_database = sb_database
        self.velocity_days = velocity_days
        self.min_velocity_qty = min_velocity_qty
        self.quiebre_days = quiebre_days
        self.baja_cobertura_days = baja_cobertura_days
        self.overstock_days = overstock_days
        self.top_n = top_n
        self.inventory_year = inventory_year
        self.warehouse_codes = warehouse_codes
        mode = (demand_mode or DEFAULT_DEMAND_MODE).strip().lower()
        if mode not in (DEMAND_MODE_WAREHOUSE, DEMAND_MODE_COMPANY):
            raise ValueError(f"Invalid demand_mode: {demand_mode!r}")
        self.demand_mode = mode

    def _execute_query(self, sql: str) -> List[Dict[str, Any]]:
        self.db.connect()
        rows = cast(List[Dict[str, Any]], self.db.execute_query(sql))
        return [dict(row) for row in rows]

    def fetch_detail(self, as_of_date: str) -> List[Dict[str, Any]]:
        _validate_period_date(as_of_date, "as_of_date")
        sql = build_turnover_detail_sql(
            as_of_date,
            velocity_days=self.velocity_days,
            top_n=None,
            inventory_year=self.inventory_year,
            j3_database=self.j3_database,
            sb_database=self.sb_database,
            warehouse_codes=self.warehouse_codes,
            demand_mode=self.demand_mode,
        )
        raw = self._execute_query(sql)
        return enrich_detail_rows(
            raw,
            velocity_days=self.velocity_days,
            min_velocity_qty=self.min_velocity_qty,
            quiebre_days=self.quiebre_days,
            baja_cobertura_days=self.baja_cobertura_days,
            overstock_days=self.overstock_days,
        )

    def build_report(self, as_of_date: str) -> Dict[str, Any]:
        detail = self.fetch_detail(as_of_date)
        summary = turnover_summary_from_rows(detail)
        demand_label = (
            "SKU×bodega via InvVentasDetalle (J3)"
            if self.demand_mode == DEMAND_MODE_WAREHOUSE
            else "SKU company-wide via banco_datos (SmartBusiness)"
        )
        return {
            "as_of_date": as_of_date,
            "velocity_days": self.velocity_days,
            "min_velocity_qty": self.min_velocity_qty,
            "demand_mode": self.demand_mode,
            "demand_mode_label": demand_label,
            "excluded_document_codes": list(CANONICAL_EXCLUDED_DOCUMENT_CODES),
            "warehouse_policy": turnover_policy_summary(),
            "summary": summary,
            "action_quiebre": action_quiebre(detail, top_n=self.top_n),
            "action_capital_atrapado": action_capital_atrapado(
                detail, top_n=self.top_n
            ),
            "suggested_transfers": suggested_transfers(detail, top_n=self.top_n),
            "data_quality_notes": [
                n for n in (salida_fisica_quality_note(detail),) if n
            ],
            "abc": abc_by_commercial_velocity(detail, demand_mode=self.demand_mode)[
                : self.top_n
            ],
            "by_warehouse": by_warehouse_from_rows(detail),
            "detail_row_count": len(detail),
        }
