"""J3System sales-to-warehouse SQL builders.

See docs/reference/j3system-sales-warehouse-query.md for schema notes.
"""

from __future__ import annotations

import os
import re
from typing import Optional, Tuple

from business_analyzer.core.database import Database, env_database_name

WAREHOUSE_CODES: Tuple[str, ...] = (
    "ALM",
    "SUR",
    "BD6",
    "DIS",
    "BOD",
    "BDT",
    "FLO",
    "CEN",
    "MDL",
    "EXH",
    "TRA",
    "CON",
    "B.ROT",
    "EXD",
)

# Codes that collide with common Spanish tokens (e.g. "con" = with).
_AMBIGUOUS_WAREHOUSE_CODES = frozenset({"CON"})

_VENDOR_BRANDS = frozenset(
    {
        "pavco",
        "euroceramica",
        "cemex",
        "sika",
        "acesco",
        "hylsa",
        "corona",
        "pintuco",
        "gricol",
        "holcim",
    }
)

WAREHOUSE_CODE_TO_NAME = {
    "ALM": "001",
    "SUR": "SUR",
    "BD6": "BD6",
    "DIS": "DISTRIBUCIONES",
    "BOD": "MANGUERAS",
    "BDT": "BODEGA AJUSTES TEMPORALES",
    "FLO": "ALMACEN FLORENCIA (Sika Center)",
    "CEN": "005 GARANTIAS",
    "MDL": "MERCADO LIBRE",
    "EXH": "BOD EXHIBICION ALMACEN",
    "TRA": "MCIA COMITECAFE",
    "CON": "CONTABILIDAD",
    "B.ROT": "PRODUCTOS DE BAJA ROTACION",
    "EXD": "BOD EXHIBICION DISTRIBUCIONES",
}


def qualified_j3_table(table: str, j3_database: Optional[str] = None) -> str:
    """Return a validated ``J3System.dbo.<table>`` reference."""
    db_name = j3_database or env_database_name("DB_NAME_J3SYSTEM", "J3System")
    validated_db = Database.validate_sql_identifier(db_name, "j3 database")
    validated_table = Database.validate_sql_identifier(table, "table")
    return f"{validated_db}.dbo.{validated_table}"


def _sales_warehouse_from_clause(j3_database: Optional[str] = None) -> str:
    """Line-level sales joined to warehouse via ``InvVentasDetalle.AlmacenID``."""
    inv_ventas = qualified_j3_table("InvVentas", j3_database)
    inv_detalle = qualified_j3_table("InvVentasDetalle", j3_database)
    adm_almacen = qualified_j3_table("AdmAlmacen", j3_database)
    return (
        f"FROM {inv_ventas} v "
        f"JOIN {inv_detalle} d ON d.VentaID = v.VentaID "
        f"LEFT JOIN {adm_almacen} a ON a.AlmacenID = d.AlmacenID"
    )


def build_sales_warehouse_detail_sql(
    *,
    top_n: Optional[int] = None,
    warehouse_code: Optional[str] = None,
    j3_database: Optional[str] = None,
) -> str:
    """Line-level sales with warehouse code and decoded name."""
    top_clause = f"TOP {int(top_n)} " if top_n else ""
    where_parts = ["a.AlmacenCodigo IS NOT NULL", "a.AlmacenCodigo <> ''"]
    if warehouse_code:
        code = warehouse_code.strip().upper()
        if code not in WAREHOUSE_CODES:
            raise ValueError(f"Unknown warehouse code: {warehouse_code}")
        where_parts.append(f"a.AlmacenCodigo = '{code}'")
    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    from_clause = _sales_warehouse_from_clause(j3_database)
    return (
        f"SELECT {top_clause}"
        "v.VentaID, "
        "v.NumeroDocumento, "
        "v.Fecha, "
        "v.NroFactura, "
        "v.TercerosID, "
        "a.AlmacenCodigo AS Almancen, "
        "a.AlmacenNombre "
        f"{from_clause} "
        f"{where_sql} "
        "ORDER BY v.Fecha DESC"
    ).strip()


def _validate_period_date(value: str, label: str = "date") -> str:
    """Validate YYYY-MM-DD for safe interpolation in J3System period filters."""
    if not value or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


def build_sales_by_warehouse_sql(
    *,
    j3_database: Optional[str] = None,
) -> str:
    """Aggregate sale count per warehouse code."""
    from_clause = _sales_warehouse_from_clause(j3_database)
    return (
        "SELECT "
        "a.AlmacenCodigo AS Codigo_Almacen, "
        "a.AlmacenNombre AS Nombre_Almacen, "
        "COUNT(DISTINCT v.VentaID) AS Numero_Ventas "
        f"{from_clause} "
        "WHERE a.AlmacenCodigo IS NOT NULL AND a.AlmacenCodigo <> '' "
        "GROUP BY a.AlmacenCodigo, a.AlmacenNombre "
        "ORDER BY Numero_Ventas DESC"
    )


def build_warehouse_breakdown_for_period_sql(
    start_date: str,
    end_date: str,
    *,
    j3_database: Optional[str] = None,
) -> str:
    """Monthly manager-report breakdown: sales and revenue per warehouse code."""
    start = _validate_period_date(start_date, "start_date")
    end = _validate_period_date(end_date, "end_date")
    from_clause = _sales_warehouse_from_clause(j3_database)
    return (
        "SELECT "
        "a.AlmacenCodigo AS warehouse_code, "
        "a.AlmacenNombre AS warehouse_name, "
        "COUNT(DISTINCT v.VentaID) AS sale_count, "
        "SUM(d.VentaSinIva) AS revenue_without_iva, "
        "SUM(d.VentaMasIva) AS revenue_with_iva, "
        "SUM(d.Cantidad) AS quantity "
        f"{from_clause} "
        f"WHERE v.Fecha BETWEEN '{start}' AND '{end}' "
        "AND a.AlmacenCodigo IS NOT NULL AND a.AlmacenCodigo <> '' "
        "GROUP BY a.AlmacenCodigo, a.AlmacenNombre "
        "ORDER BY SUM(d.VentaSinIva) DESC"
    )


def build_one_warehouse_per_sale_for_period_sql(
    start_date: str,
    end_date: str,
    *,
    top_n: Optional[int] = None,
    j3_database: Optional[str] = None,
) -> str:
    """One warehouse per sale within a date range (manager report detail)."""
    start = _validate_period_date(start_date, "start_date")
    end = _validate_period_date(end_date, "end_date")
    top_clause = f"TOP {int(top_n)} " if top_n else ""
    inv_ventas = qualified_j3_table("InvVentas", j3_database)
    inv_detalle = qualified_j3_table("InvVentasDetalle", j3_database)
    adm_almacen = qualified_j3_table("AdmAlmacen", j3_database)
    return (
        f"SELECT {top_clause}"
        "v.VentaID, "
        "v.NumeroDocumento, "
        "v.Fecha, "
        "v.NroFactura, "
        "a.AlmacenCodigo AS warehouse_code, "
        "a.AlmacenNombre AS warehouse_name "
        f"FROM {inv_ventas} v "
        "CROSS APPLY ("
        "SELECT TOP 1 d.AlmacenID "
        f"FROM {inv_detalle} d "
        "WHERE d.VentaID = v.VentaID "
        "ORDER BY d.AlmacenID"
        ") wh "
        f"LEFT JOIN {adm_almacen} a ON a.AlmacenID = wh.AlmacenID "
        f"WHERE v.Fecha BETWEEN '{start}' AND '{end}' "
        "ORDER BY v.Fecha DESC"
    )


def build_one_warehouse_per_sale_sql(
    *,
    j3_database: Optional[str] = None,
) -> str:
    """One row per sale using the first non-empty ``Almancen`` line item."""
    inv_ventas = qualified_j3_table("InvVentas", j3_database)
    inv_detalle = qualified_j3_table("InvVentasDetalle", j3_database)
    adm_almacen = qualified_j3_table("AdmAlmacen", j3_database)
    return (
        "SELECT "
        "v.VentaID, "
        "v.NumeroDocumento, "
        "v.Fecha, "
        "v.NroFactura, "
        "a.AlmacenCodigo AS Almancen, "
        "a.AlmacenNombre "
        f"FROM {inv_ventas} v "
        "CROSS APPLY ("
        "SELECT TOP 1 d.AlmacenID "
        f"FROM {inv_detalle} d "
        "WHERE d.VentaID = v.VentaID "
        "ORDER BY d.AlmacenID"
        ") wh "
        f"LEFT JOIN {adm_almacen} a ON a.AlmacenID = wh.AlmacenID "
        "ORDER BY v.Fecha DESC"
    )


def _has_warehouse_context(question: str) -> bool:
    lower = (question or "").lower()
    return any(
        token in lower
        for token in (
            "almacén",
            "almacen",
            "bodega",
            "warehouse",
            "almancen",
            "código",
            "codigo",
            "j3system",
            "j3 system",
        )
    )


def _has_sale_context(question: str) -> bool:
    lower = (question or "").lower()
    return bool(re.search(r"\b(ventas?|facturas?|facturaci[oó]n)\b", lower))


def _has_vendor_brand_context(question: str) -> bool:
    """True when question names a product vendor/brand (not Sika Center branch)."""
    lower = (question or "").lower()
    if "sika center" in lower:
        return False
    return any(brand in lower for brand in _VENDOR_BRANDS)


def _is_physical_warehouse_breakdown_question(question: str) -> bool:
    """Brand/all sales grouped by physical warehouse code (AlmacenCodigo / bodega)."""
    lower = (question or "").lower()
    return any(
        phrase in lower
        for phrase in (
            "por almacén",
            "por almacen",
            "por bodega",
        )
    )


def _is_store_branch_breakdown_question(question: str) -> bool:
    """Aggregate sales by invoice branch/sede (FED/FEF/FET), not physical warehouse."""
    lower = (question or "").lower()
    return any(
        phrase in lower
        for phrase in (
            "por sede",
            "por sucursal",
            "por tienda",
            "por documento",
            "por facturación",
            "por facturacion",
        )
    )


def _is_branch_breakdown_question(question: str) -> bool:
    """Any sede or physical-warehouse breakdown (excludes bare J3System routing)."""
    return _is_physical_warehouse_breakdown_question(
        question
    ) or _is_store_branch_breakdown_question(question)


def warehouse_display_name_sql(column: str = "bd.AlmacenCodigo") -> str:
    """SQL expression for warehouse label with known aliases (e.g. FLO → Sika Center)."""
    alias_codes = ("FLO", "DIS", "BD6", "ALM")
    cases = "\n".join(
        f"            WHEN {column} = '{code}' THEN '{name}'"
        for code, name in WAREHOUSE_CODE_TO_NAME.items()
        if code in alias_codes
    )
    return (
        f"CASE\n{cases}\n"
        f"            ELSE COALESCE(a.AlmacenNombre, {column})\n        END"
    )


def _is_spanish_con_preposition(question: str) -> bool:
    """True when ``con`` is the Spanish preposition, not warehouse code ``CON``."""
    lower = (question or "").lower()
    return bool(
        re.search(
            r"\b(?:ventas?|productos?|clientes?|listar|dame|facturas?)\s+con\b",
            lower,
        )
        or re.search(r"\bcon\s+su\s+almac[eé]n\b", lower)
    )


def extract_warehouse_code(question: str) -> Optional[str]:
    """Return a known warehouse code mentioned in the question, if any."""
    upper = (question or "").upper()
    lower = (question or "").lower()
    warehouse_context = _has_warehouse_context(question)
    for code in sorted(WAREHOUSE_CODES, key=len, reverse=True):
        if not re.search(rf"\b{re.escape(code)}\b", upper):
            continue
        if code in _AMBIGUOUS_WAREHOUSE_CODES:
            if not warehouse_context:
                continue
            if _is_spanish_con_preposition(question):
                continue
            if not re.search(
                r"\b(?:almac[eé]n|bodega|almancen)\s+con\b|\bcon\s+contabilidad\b",
                lower,
            ):
                continue
        return code
    return None


def is_j3system_warehouse_question(question: str) -> bool:
    """Detect NL questions about J3System warehouse-per-sale lookups."""
    lower = (question or "").lower()
    if any(
        token in lower
        for token in (
            "j3system",
            "j3 system",
            "invventas",
            "invimpresionfactura",
            "almancen",
        )
    ):
        return True

    has_warehouse = _has_warehouse_context(question)
    has_sale = _has_sale_context(question)
    if has_warehouse and has_sale:
        if "sika center" in lower or "calle 5" in lower:
            return False
        if _has_vendor_brand_context(question) and _is_branch_breakdown_question(
            question
        ):
            return False
        return True

    code = extract_warehouse_code(question)
    if has_sale and code:
        # Brand scoped to one warehouse (e.g. "ventas de sika en flo") → banco_datos.
        if _has_vendor_brand_context(question) and not _is_branch_breakdown_question(
            question
        ):
            return False
        return True

    return False


def is_aggregated_warehouse_question(question: str) -> bool:
    """Detect grouping/totals questions (sales per warehouse)."""
    lower = (question or "").lower()
    return any(
        token in lower
        for token in (
            "agrupad",
            "por almacén",
            "por almacen",
            "por bodega",
            "totales",
            "cantidad de ventas",
            "número de ventas",
            "numero de ventas",
        )
    )


def is_one_warehouse_per_sale_question(question: str) -> bool:
    """Detect requests for deduplicated one-warehouse-per-sale output."""
    lower = (question or "").lower()
    return any(
        token in lower
        for token in (
            "una bodega por venta",
            "un almacén por venta",
            "un almacen por venta",
            "sin duplicar",
            "distinct",
            "primera bodega",
            "primer almacén",
            "primer almacen",
        )
    )


def build_sales_warehouse_sql_for_question(
    question: str,
    *,
    j3_database: Optional[str] = None,
) -> str:
    """Pick the best warehouse SQL template for a natural-language question."""
    code = extract_warehouse_code(question)
    if is_one_warehouse_per_sale_question(question):
        return build_one_warehouse_per_sale_sql(j3_database=j3_database)
    if is_aggregated_warehouse_question(question):
        return build_sales_by_warehouse_sql(j3_database=j3_database)
    top_match = re.search(r"top\s*(\d+)", (question or "").lower())
    top_n = int(top_match.group(1)) if top_match else None
    return build_sales_warehouse_detail_sql(
        top_n=top_n,
        warehouse_code=code,
        j3_database=j3_database,
    )
