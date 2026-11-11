"""TSOL sell-out / inventory mapping for manufacturer templates.

Fills the "información mínima TSOL-GENERAL" workbook (Ventas + Inventario)
from SmartBusiness ``banco_datos`` and J3System masters. Used for Sika /
Pintuco (AkzoNobel) sell-out feeds.

Pintuco grain follows the J3 txt dump (SKU prefix ``009``, electronic
invoices plus DVE/DVF/DVD, signed NC in Excel). Sell-out includes **all
bodegas** — the txt ``Ventas`` file is ALM-only (~23% omitted); that
warehouse cap is not applied here. Sika matches proveedor/nombre
``SIKA%`` until a Sika dump exists.

Dates are DDMMYYYY text (Colombian convention). Municipality is DIVIPOLA
(departamento 2 + municipio 3). ``CodigoDIAN`` on ``AdmCiudad`` is empty,
so the code is composed from ``AdmDepartamento.DepartamentoCodigo`` +
``AdmCiudad.CiudadCodigo``.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, cast

from business_analyzer.core.database import Database, qualified_sb_table
from business_analyzer.core.inventory_warehouse_policy import (
    turnover_warehouse_sql_in_list,
)
from business_analyzer.core.j3system_sales_warehouse import qualified_j3_table
from business_analyzer.core.website_warehouse_policy import sql_in_list
from depotru_kernel.documents import excluded_document_sql_in_list

# Pintuco: línea 009 from the J3 dump. No warehouse cap (all bodegas).
BRANDS = {
    "sika": {"like": "SIKA%", "exclude": ("S.IVA",)},
    "pintuco": {"like": "PINTUCO%", "exclude": (), "sku_prefix": "009"},
}

INVOICE_DOC_CODES: Tuple[str, ...] = ("FED", "FEF", "FET")
RETURN_DOC_CODES: Tuple[str, ...] = ("DVE", "DVF", "DVD")

VENTAS_HEADERS: Tuple[str, ...] = (
    "NUMERO\nFACTURAS",
    "FECHA VENTA",
    "CODIGO VENDEDOR",
    "NOMBRE VENDEDOR",
    "CEDULA VENDEDOR",
    "CODIGO DE MUNICIPIO",
    "NOMBRE DEL MUNICIPIO",
    "COD. CLIENTE",
    "NOM.CLIENTE",
    "NIT CLIENTE",
    "DIRECCIÓN CLIENTE",
    "CÓDIGO .PRODUCTO",
    "DESCRIPCIÓN. PRODUCTO",
    "CODIGO DE BARRA",
    "CODIGO TIPO NEGOCIO",
    "NOMBRE TIPO NEGOCIO",
    "CANTIDAD",
    "COSTO",
    "VALOR TOTAL VENTA",
)

INVENTARIO_HEADERS: Tuple[str, ...] = (
    "FECHA",
    "CODIGO",
    "NOMBRE PRODUCTO",
    "CANTIDAD",
    "UN MEDIDA",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def previous_calendar_month(*, today: Optional[date] = None) -> Tuple[int, int]:
    ref = today or date.today()
    last = ref.replace(day=1) - timedelta(days=1)
    return last.year, last.month


def month_bounds(year: int, month: int) -> Tuple[date, date]:
    if month < 1 or month > 12:
        raise ValueError(f"Mes inválido: {month}")
    start = date(int(year), int(month), 1)
    last_day = calendar.monthrange(start.year, start.month)[1]
    end_exclusive = start + timedelta(days=last_day)
    return start, end_exclusive


def validate_year_month(year: int, month: int) -> Tuple[int, int]:
    month_bounds(year, month)
    if int(year) < 2000 or int(year) > 2100:
        raise ValueError(f"Año inválido: {year}")
    return int(year), int(month)


def normalize_brand(brand: str) -> str:
    raw = (brand or "").strip().lower()
    if raw in ("", "all", "*"):
        return "all"
    if raw not in BRANDS:
        allowed = ", ".join(sorted(BRANDS) + ["all"])
        raise ValueError(f"Marca inválida: {brand!r}. Use {allowed}.")
    return raw


def _sql_ident(column: str) -> str:
    ident = str(column or "").strip()
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_\.]*$", ident):
        raise ValueError(f"Invalid SQL column: {column!r}")
    return ident


def brand_match_sql(column: str, brand: str) -> str:
    """SQL fragment matching a brand on a varchar column. Brand is whitelist."""
    ident = _sql_ident(column)
    key = normalize_brand(brand)
    if key == "all":
        return "1 = 1"
    spec = BRANDS[key]
    like = spec["like"].replace("'", "''")
    parts = [f"UPPER(LTRIM(RTRIM({ident}))) LIKE '{like}'"]
    for extra in spec.get("exclude") or ():
        safe = str(extra).replace("'", "''")
        parts.append(f"UPPER(LTRIM(RTRIM({ident}))) <> '{safe}'")
    return "(" + " AND ".join(parts) + ")"


def product_filter_sql(
    brand: str,
    *,
    article_col: str,
    proveedor_col: str,
    nombre_col: str,
) -> str:
    """SKU-prefix filter when the brand dump uses one; else proveedor/nombre."""
    key = normalize_brand(brand)
    if key == "all":
        return "1 = 1"
    prefix = BRANDS[key].get("sku_prefix")
    if prefix:
        safe = Database.validate_sql_identifier(str(prefix), "sku prefix")
        return f"{_sql_ident(article_col)} LIKE '{safe}%'"
    return (
        f"({brand_match_sql(proveedor_col, brand)}"
        f" OR {brand_match_sql(nombre_col, brand)})"
    )


def warehouse_filter_sql(brand: str, column: str) -> str:
    """Optional bodega IN-list. Empty/missing means all warehouses."""
    key = normalize_brand(brand)
    if key == "all" or key not in BRANDS:
        return "1 = 1"
    warehouses = BRANDS[key].get("warehouses")
    if not warehouses:
        return "1 = 1"
    return f"{_sql_ident(column)} IN ({sql_in_list(warehouses)})"


def sales_document_filter_sql(column: str) -> str:
    """Electronic invoices plus electronic credit notes (J3 dump includes NC)."""
    ident = _sql_ident(column)
    codes = sql_in_list(INVOICE_DOC_CODES + RETURN_DOC_CODES)
    return f"{ident} IN ({codes})"


def _as_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _as_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clean(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def format_tsol_date(value: Any) -> str:
    """DDMMYYYY zero-padded text, as in the TSOL sample sheet."""
    parsed = _as_date(value)
    if parsed is None:
        return ""
    return f"{parsed.day:02d}{parsed.month:02d}{parsed.year:04d}"


def format_nit(identificacion: Any, dv: Any = None) -> str:
    ident = re.sub(r"[\s.]", "", _clean(identificacion))
    check = _clean(dv)
    if ident and check and check not in {".", "-"}:
        return f"{ident}-{check}"
    return ident


def format_divipola(departamento_codigo: Any, ciudad_codigo: Any) -> str:
    dept = re.sub(r"\D", "", str(departamento_codigo or ""))
    city = re.sub(r"\D", "", str(ciudad_codigo or ""))
    if not dept or not city:
        return ""
    return dept.zfill(2) + city.zfill(3)


def _money(value: Any) -> float:
    return round(_as_float(value), 2)


def assemble_venta_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    nombre = _clean(row.get("TercerosRazonSocial")) or _clean(
        row.get("TercerosNombres")
    )
    ciudad = _clean(row.get("CiudadNombre"))
    return {
        "NUMERO\nFACTURAS": _clean(row.get("NumeroDocumento")),
        "FECHA VENTA": format_tsol_date(row.get("Fecha")),
        "CODIGO VENDEDOR": _clean(row.get("VendedorCodigo")),
        "NOMBRE VENDEDOR": _clean(row.get("VendedorNombre"))
        or _clean(row.get("VendedorFactura")),
        "CEDULA VENDEDOR": _clean(row.get("Cedula")),
        "CODIGO DE MUNICIPIO": format_divipola(
            row.get("DepartamentoCodigo"), row.get("CiudadCodigo")
        ),
        "NOMBRE DEL MUNICIPIO": ciudad,
        "COD. CLIENTE": _clean(row.get("TercerosID")),
        "NOM.CLIENTE": nombre,
        "NIT CLIENTE": format_nit(
            row.get("TercerosIdentificacion"), row.get("TercerosDv")
        ),
        "DIRECCIÓN CLIENTE": _clean(row.get("TercerosDireccion")),
        "CÓDIGO .PRODUCTO": _clean(row.get("ArticulosCodigo")),
        "DESCRIPCIÓN. PRODUCTO": _clean(row.get("ArticulosNombre")),
        "CODIGO DE BARRA": _clean(row.get("BarrasCodigo")),
        "CODIGO TIPO NEGOCIO": _clean(row.get("TipoNegocioCodigo")),
        "NOMBRE TIPO NEGOCIO": _clean(row.get("TipoNegocioNombre")),
        "CANTIDAD": _as_float(row.get("Cantidad")),
        "COSTO": _money(row.get("ValorCosto")),
        "VALOR TOTAL VENTA": _money(row.get("TotalSinIva")),
    }


def assemble_inventario_row(row: Mapping[str, Any], *, as_of: date) -> Dict[str, Any]:
    unidad = _clean(row.get("MedidasCodigo")) or "UN"
    return {
        "FECHA": format_tsol_date(as_of),
        "CODIGO": _clean(row.get("ArticulosCodigo")),
        "NOMBRE PRODUCTO": _clean(row.get("ArticulosNombre")),
        "CANTIDAD": _as_float(row.get("Cantidad")),
        "UN MEDIDA": unidad,
    }


PLACEHOLDER_NITS = {"222222222222", "22222222", "0", "0000000000"}
GENERIC_CUSTOMER_NAMES = {
    "CONSUMIDOR FINAL",
    "CONSUMIDOR  FINAL",
    "CLIENTE GENERAL",
}


def _normalized(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().upper()


def quality_summary(
    ventas: Sequence[Mapping[str, Any]],
    inventario: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    n = len(ventas)

    def missing(key: str) -> int:
        return sum(1 for row in ventas if not _clean(row.get(key)))

    return {
        "venta_rows": n,
        "inventario_rows": len(inventario),
        "venta_total": round(
            sum(_as_float(r.get("VALOR TOTAL VENTA")) for r in ventas), 2
        ),
        "venta_costo": round(sum(_as_float(r.get("COSTO")) for r in ventas), 2),
        "missing_nit": missing("NIT CLIENTE"),
        "missing_direccion": missing("DIRECCIÓN CLIENTE"),
        "missing_municipio": missing("CODIGO DE MUNICIPIO"),
        "missing_tipo_negocio": missing("CODIGO TIPO NEGOCIO"),
        "missing_cedula_vendedor": missing("CEDULA VENDEDOR"),
        "missing_barcode": missing("CODIGO DE BARRA"),
        "placeholder_nit": sum(
            1 for r in ventas if _clean(r.get("NIT CLIENTE")) in PLACEHOLDER_NITS
        ),
        "generic_customer": sum(
            1
            for r in ventas
            if _normalized(r.get("NOM.CLIENTE")) in GENERIC_CUSTOMER_NAMES
        ),
        "inventory_negative": sum(
            1 for r in inventario if _as_float(r.get("CANTIDAD")) < 0
        ),
    }


def quality_issues(quality: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """High-signal blockers for a manufacturer sell-out submission."""
    issues: List[Dict[str, Any]] = []
    rows = int(quality.get("venta_rows") or 0)
    if rows and int(quality.get("missing_barcode") or 0) == rows:
        issues.append(
            {
                "id": "barcode_empty_all",
                "severity": "medium",
                "rows": rows,
                "note": "AdmBarras/InvDatosCodigo no tienen EAN; la columna va vacía.",
            }
        )
    for key, issue_id, severity in (
        ("placeholder_nit", "placeholder_nit", "high"),
        ("missing_tipo_negocio", "blank_tipo_negocio", "high"),
        ("missing_cedula_vendedor", "blank_cedula_vendedor", "high"),
        ("inventory_negative", "inventory_negative", "high"),
    ):
        count = int(quality.get(key) or 0)
        if count:
            issues.append({"id": issue_id, "severity": severity, "rows": count})
    return issues


def build_sales_sql(
    brand: str,
    *,
    sb_database: Optional[str] = None,
    j3_database: Optional[str] = None,
) -> str:
    bd = qualified_sb_table("banco_datos", sb_database)
    terceros = qualified_j3_table("AdmTerceros", j3_database)
    ciudad = qualified_j3_table("AdmCiudad", j3_database)
    depto = qualified_j3_table("AdmDepartamento", j3_database)
    tipos = qualified_j3_table("AdmTiposNegocio", j3_database)
    vendedor = qualified_j3_table("AdmVendedor", j3_database)
    barras = qualified_j3_table("AdmBarras", j3_database)
    excluded = excluded_document_sql_in_list()
    product_sql = product_filter_sql(
        brand,
        article_col="bd.ArticulosCodigo",
        proveedor_col="bd.proveedor",
        nombre_col="bd.ArticulosNombre",
    )
    warehouse_sql = warehouse_filter_sql(brand, "bd.AlmacenCodigo")
    docs_sql = sales_document_filter_sql("bd.DocumentosCodigo")
    return f"""
SELECT
    bd.NumeroDocumento,
    bd.Fecha,
    bd.VendedorFactura,
    v.VendedorCodigo,
    v.VendedorNombre,
    v.Cedula,
    d.DepartamentoCodigo,
    c.CiudadCodigo,
    c.CiudadNombre,
    bd.TercerosID,
    t.TercerosRazonSocial,
    t.TercerosNombres,
    t.TercerosIdentificacion,
    t.TercerosDv,
    t.TercerosDireccion,
    bd.ArticulosCodigo,
    bd.ArticulosNombre,
    bar.BarrasCodigo,
    tn.Codigo AS TipoNegocioCodigo,
    tn.Nombre AS TipoNegocioNombre,
    bd.Cantidad,
    bd.ValorCosto,
    bd.TotalSinIva
FROM {bd} bd
LEFT JOIN {terceros} t ON t.TercerosID = bd.TercerosID
LEFT JOIN {ciudad} c ON c.CiudadID = t.CiudadID
LEFT JOIN {depto} d ON d.DepartamentoID = c.DepartamentoID
LEFT JOIN {tipos} tn ON tn.TipoNegocioID = t.TipoNegocioID
LEFT JOIN {vendedor} v ON v.VendedorID = bd.VendedorID
LEFT JOIN (
    SELECT ArticulosID, MIN(BarrasCodigo) AS BarrasCodigo
    FROM {barras}
    WHERE BarrasCodigo IS NOT NULL
      AND LTRIM(RTRIM(BarrasCodigo)) <> ''
    GROUP BY ArticulosID
) bar ON bar.ArticulosID = bd.ArticulosID
WHERE bd.Fecha >= %s
  AND bd.Fecha < %s
  AND bd.DocumentosCodigo NOT IN ({excluded})
  AND {docs_sql}
  AND {product_sql}
  AND {warehouse_sql}
ORDER BY bd.Fecha, bd.NumeroDocumento, bd.ArticulosCodigo
""".strip()


def build_inventory_sql(
    brand: str,
    *,
    inventory_year: int,
    j3_database: Optional[str] = None,
) -> str:
    detalle = qualified_j3_table("InvDetalleExistencias", j3_database)
    existencias = qualified_j3_table("InvExistencias", j3_database)
    articulos = qualified_j3_table("AdmArticulos", j3_database)
    almacen = qualified_j3_table("AdmAlmacen", j3_database)
    medidas = qualified_j3_table("AdmMedidas", j3_database)
    key = normalize_brand(brand)
    spec = BRANDS.get(key) or {}
    warehouses = spec.get("warehouses")
    if warehouses:
        wh_in = sql_in_list(warehouses)
    else:
        wh_in = turnover_warehouse_sql_in_list()
    year = int(inventory_year)
    product_sql = product_filter_sql(
        brand,
        article_col="a.ArticulosCodigo",
        proveedor_col="a.ArticulosMarca",
        nombre_col="a.ArticulosNombre",
    )
    # Pintuco dump lists the full 009 catalog including zero stock.
    if spec.get("sku_prefix"):
        if warehouses:
            stock_case = (
                f"WHEN al.AlmacenCodigo IN ({wh_in}) AND d.Ano = {year} "
                "THEN d.SaldoActual"
            )
        else:
            stock_case = f"WHEN d.Ano = {year} THEN d.SaldoActual"
        return f"""
SELECT
    a.ArticulosCodigo,
    a.ArticulosNombre,
    CAST(COALESCE(SUM(CASE {stock_case} END), 0) AS DECIMAL(18, 4))
        AS Cantidad,
    MAX(m.MedidasCodigo) AS MedidasCodigo
FROM {articulos} a
LEFT JOIN {existencias} e ON e.ArticulosID = a.ArticulosID
LEFT JOIN {detalle} d ON d.ExistenciasID = e.ExistenciasID
LEFT JOIN {almacen} al ON al.AlmacenID = d.AlmacenID
LEFT JOIN {medidas} m ON m.MedidasID = a.MedidasID
WHERE {product_sql}
GROUP BY a.ArticulosCodigo, a.ArticulosNombre
ORDER BY a.ArticulosCodigo
""".strip()
    return f"""
SELECT
    a.ArticulosCodigo,
    a.ArticulosNombre,
    SUM(CAST(d.SaldoActual AS DECIMAL(18, 4))) AS Cantidad,
    MAX(m.MedidasCodigo) AS MedidasCodigo
FROM {detalle} d
JOIN {existencias} e ON e.ExistenciasID = d.ExistenciasID
JOIN {articulos} a ON a.ArticulosID = e.ArticulosID
JOIN {almacen} al ON al.AlmacenID = d.AlmacenID
LEFT JOIN {medidas} m ON m.MedidasID = a.MedidasID
WHERE d.Ano = {year}
  AND al.AlmacenCodigo IN ({wh_in})
  AND {product_sql}
GROUP BY a.ArticulosCodigo, a.ArticulosNombre
HAVING SUM(CAST(d.SaldoActual AS DECIMAL(18, 4))) > 0
ORDER BY a.ArticulosCodigo
""".strip()


class TsolExportRunner:
    """Load sell-out lines and commercial stock for a TSOL workbook."""

    def __init__(
        self,
        db: Optional[Database] = None,
        *,
        sb_database: Optional[str] = None,
        j3_database: Optional[str] = None,
    ) -> None:
        self.db = db or Database()
        self.sb_database = sb_database
        self.j3_database = j3_database

    def _execute(
        self, sql: str, params: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        self.db.connect()
        rows = cast(
            List[Dict[str, Any]],
            self.db.execute_query(sql, params),
        )
        return [dict(row) for row in rows]

    def fetch_sales(
        self, brand: str, start: date, end_exclusive: date
    ) -> List[Dict[str, Any]]:
        sql = build_sales_sql(
            brand, sb_database=self.sb_database, j3_database=self.j3_database
        )
        return self._execute(sql, (start, end_exclusive))

    def fetch_inventory(self, brand: str, inventory_year: int) -> List[Dict[str, Any]]:
        sql = build_inventory_sql(
            brand, inventory_year=inventory_year, j3_database=self.j3_database
        )
        return self._execute(sql)

    def build_export(
        self,
        brand: str,
        year: Optional[int] = None,
        month: Optional[int] = None,
        *,
        start: Optional[date] = None,
        end: Optional[date] = None,
        today: Optional[date] = None,
    ) -> Dict[str, Any]:
        brand_key = normalize_brand(brand)
        ref = today or date.today()
        if start is not None or end is not None:
            if start is None or end is None:
                raise ValueError("start and end are required together")
            if end < start:
                raise ValueError("end must be on or after start")
            end_exclusive = end + timedelta(days=1)
            as_of = end if end <= ref else ref
            year = start.year
            month = start.month
        else:
            if year is None or month is None:
                year, month = previous_calendar_month(today=ref)
            year, month = validate_year_month(year, month)
            start, end_exclusive = month_bounds(year, month)
            as_of = end_exclusive - timedelta(days=1)
            if as_of > ref:
                as_of = ref
        raw_sales = self.fetch_sales(brand_key, start, end_exclusive)
        raw_stock = self.fetch_inventory(brand_key, as_of.year)
        ventas = [assemble_venta_row(row) for row in raw_sales]
        inventario = [assemble_inventario_row(row, as_of=as_of) for row in raw_stock]
        quality = quality_summary(ventas, inventario)
        return {
            "brand": brand_key,
            "year": year,
            "month": month,
            "period_start": start.isoformat(),
            "period_end": as_of.isoformat(),
            "as_of_date": as_of.isoformat(),
            "ventas": ventas,
            "inventario": inventario,
            "quality": quality,
        }
