"""Shared helpers for manager sales reports."""

import calendar
from decimal import Decimal
from typing import Any, Dict, List, Optional

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


def is_recommendable_product(name: str) -> bool:
    if not name:
        return False
    n = name.lower()
    bad_keywords = ["bolsa plastica", "bolsa plástica", "transporte", "cemento gris"]
    return not any(kw in n for kw in bad_keywords)


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
