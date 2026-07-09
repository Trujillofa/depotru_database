"""Shared helpers for manager sales reports."""

import calendar
from decimal import Decimal
from typing import Any, Dict, List, Optional

BRANCH_STORES: Dict[str, str] = {
    "FEF": "Sika Center",
    "FET": "Calle 5",
    "FED": "Almacén Principal",
}

BRANCH_SLUGS: Dict[str, str] = {
    "FEF": "sika_center",
    "FET": "calle_5",
    "FED": "almacen_principal",
}

# Physical J3System warehouse codes tied to invoice branches (sedes).
BRANCH_WAREHOUSE_CODES: Dict[str, str] = {
    "FEF": "FLO",
}

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

EXCLUDED_CUSTOMERS = {
    "DEPOSITO TRUJILLO SAS",
    "DEPOSITO TRUJILLO S.A.S",
    "DEPOSITO TRUJILLO",
}

# Exact product names excluded from rankings, KPIs, and recommendations.
EXCLUDED_PRODUCT_NAMES = (
    "SERVICIO DE CORTE",
    "BOLSA BIODEGRADABLE PARA ENTREGA",
)

EXCLUDED_PRODUCT_KEYWORDS = (
    "bolsa plastica",
    "bolsa plástica",
    "bolsa biodegradable",
    "servicio de corte",
    "transporte",
    "cemento gris",
)

BAD_VENDOR_VALUES = {
    "",
    "S/I",
    "S.I",
    "SIN PROVEEDOR",
    "N/A",
    ".",
    "SIN IVA",
    "NA",
}


def is_bad_vendor_value(value: Any) -> bool:
    if value is None:
        return True
    v = str(value).strip().upper()
    return v in BAD_VENDOR_VALUES or len(str(value).strip()) <= 2


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    return numerator / denominator if denominator != 0 else default


def to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def extract_row_value(row: Dict, keys: List[str]) -> Optional[float]:
    for key in keys:
        if key in row and row[key] is not None:
            return to_float(row[key])
    return None


# Backward-compatible aliases
_to_float = to_float
_extract_row_value = extract_row_value
extract_value = extract_row_value


def is_excluded_product(name: str) -> bool:
    if not name:
        return True
    normalized = " ".join(str(name).strip().upper().split())
    if normalized in EXCLUDED_PRODUCT_NAMES:
        return True
    lower = str(name).lower()
    return any(kw in lower for kw in EXCLUDED_PRODUCT_KEYWORDS)


def is_recommendable_product(name: str) -> bool:
    return not is_excluded_product(name)


def balanced_promotion_score(
    revenue: float,
    gross_profit: float,
    margin_pct: float,
    *,
    revenue_norm: float,
    margin_norm: float,
    profit_norm: float,
    min_margin_pct: float = 15.0,
) -> float:
    """
    Sweet-spot score balancing margin % and sales volume.

    Uses the geometric mean of normalized margin and revenue, scaled by
    normalized gross profit — favors products with both healthy margins and
    meaningful sales, not tiny high-margin items alone.
    """
    if (
        margin_pct < min_margin_pct
        or revenue <= 0
        or gross_profit <= 0
        or revenue_norm <= 0
        or margin_norm <= 0
        or profit_norm <= 0
    ):
        return 0.0
    blend = (revenue_norm * margin_norm) ** 0.5
    return blend * profit_norm


def is_likely_supplier_name(name: str) -> bool:
    if not name:
        return False
    n = name.strip().upper()
    if len(n) < 3:
        return False
    product_patterns = [
        "1/",
        "2/",
        "3/",
        "4/",
        "5/",
        "1/2",
        " GR",
        " KG",
        " MM",
        " CAL.",
        " T/",
        "PESADO",
        "LADRILLO ",
        "VARILLA ",
    ]
    if any(p in n for p in product_patterns):
        return False
    if len(n) > 35:
        return False
    return True


# Backward-compatible private aliases
_is_recommendable_product = is_recommendable_product
_is_likely_supplier_name = is_likely_supplier_name


def month_date_range(year: int, month: int) -> tuple[str, str]:
    _, last_day = calendar.monthrange(year, month)
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-{last_day:02d}"
    return start, end


def year_month_to_periodo(year: int, month: int) -> int:
    """Encode SmartBusiness presupuesto/banco_datos periodo (e.g. 20245 = May 2024)."""
    if not (1 <= month <= 12):
        raise ValueError(f"Month must be between 1 and 12, got {month}")
    if month < 10:
        return year * 10 + month
    return year * 100 + month


def periodo_calendar_parts(periodo: int) -> tuple[int, int]:
    """Decode SmartBusiness periodo into (year, month)."""
    if periodo >= 100000:
        return periodo // 100, periodo % 100
    return periodo // 10, periodo % 10


def branch_display_name(document_code: Optional[str]) -> Optional[str]:
    if not document_code:
        return None
    return BRANCH_STORES.get(document_code.upper())


def branch_slug(document_code: Optional[str]) -> Optional[str]:
    if not document_code:
        return None
    return BRANCH_SLUGS.get(document_code.upper())


def branch_warehouse_code(document_code: Optional[str]) -> Optional[str]:
    if not document_code:
        return None
    return BRANCH_WAREHOUSE_CODES.get(document_code.upper())


def report_output_basename(
    year: int,
    month: int,
    fmt: str,
    *,
    branch_document_code: Optional[str] = None,
) -> str:
    slug = branch_slug(branch_document_code)
    if slug:
        return f"report_{slug}_{year}_{month:02d}.{fmt}"
    return f"report_{year}_{month:02d}.{fmt}"
