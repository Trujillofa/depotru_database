"""
Formatting module for AI package.

Contains number formatting utilities for Colombian pesos, percentages, and thousands.
"""

import locale
import re
from typing import Any, List, Optional

import pandas as pd

# English-to-Spanish weekday translations for SQL DATENAME output
WEEKDAY_TRANSLATIONS = {
    "monday": "Lunes",
    "tuesday": "Martes",
    "wednesday": "Miércoles",
    "thursday": "Jueves",
    "friday": "Viernes",
    "saturday": "Sábado",
    "sunday": "Domingo",
}

# Set Colombian locale for number formatting (fallback to Spanish/default)
try:
    locale.setlocale(locale.LC_ALL, "es_CO.UTF-8")
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, "es_ES.UTF-8")
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, "en_US.UTF-8")
        except locale.Error:
            pass

# Known currency columns (explicit detection for reliability)
CURRENCY_COLUMNS = [
    "TotalMasIva",
    "TotalSinIva",
    "ValorCosto",
    "Facturacion_Total",
    "Facturacion",
    "Ventas_Totales",
    "Ventas",
    "Revenue",
    "Ganancia",
    "Ganancia_Neta",
    "Ganancia_Generada",
    "Ganancia_Total",
    "Total_Vendido",
    "Ventas_Total",
    "Ventas_Anio_Actual",
    "Ventas_Anio_Anterior",
    "Ventas_Diarias",
    "Promedio_Ventas_Diarias",
    "Promedio_Por_Documento",
    "total_revenue",
    "Ticket_Promedio",
    "Revenue_Neto",
    "Precio",
    "Costo",
]

INTEGER_COLUMNS = [
    "Cantidad",
    "Unidades_Vendidas",
    "Unidades",
    "Numero_Transacciones",
    "Numero_Ventas",
    "Numero_Compras",
    "Cantidad_Vendida",
    "Unidades_Vendidas",
    "Unidades",
    "Cantidad_KG",
    "Cantidad_Total",
    "Ventas_Este_Mes",
    "Numero_Documentos",
    "Promedio_Transacciones_Diarias",
    "Clientes_Unicos",
    "order_count",
]

# Known percentage columns
PERCENTAGE_COLUMNS = [
    "Margen_Promedio_Pct",
    "Margen_Promedio",
    "profit_margin_pct",
    "Margen",
    "margin_pct",
    "percentage",
]

# Currency keywords for fallback detection
CURRENCY_KEYWORDS = [
    "revenue",
    "ganancia",
    "facturacion",
    "total",
    "costo",
    "precio",
    "valor",
    "ingreso",
    "profit",
    "cost",
    "iva",
]

# Percentage keywords for fallback detection
PERCENTAGE_KEYWORDS = ["margen", "margin", "pct", "porcentaje", "%"]


def format_number(value: Any, column_name: str = "") -> str:
    """
    Bulletproof number formatting with explicit column detection.

    Priority:
    1. Explicit column name match (most reliable)
    2. Keyword detection (fallback)
    3. Type-based formatting (default)

    Examples:
    - TotalMasIva: 1234567 → "$1.234.567"
    - Margen_Promedio_Pct: 45.6 → "45,6%"
    - Cantidad: 1234 → "1.234"
    - None/NaN → "-"
    """
    # Handle nulls first
    if pd.isna(value) or value is None:
        return "-"

    # Try to convert to number
    try:
        num = float(value)
    except (ValueError, TypeError):
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in WEEKDAY_TRANSLATIONS:
                return WEEKDAY_TRANSLATIONS[normalized]
        return str(value)

    # 1. EXPLICIT COLUMN MATCH (highest priority)
    if column_name in CURRENCY_COLUMNS:
        return f"${num:,.0f}".replace(",", ".")

    if column_name in PERCENTAGE_COLUMNS:
        return f"{num:,.1f}%".replace(".", ",")

    if column_name in INTEGER_COLUMNS:
        return f"{int(num):,}".replace(",", ".")

    # 2. KEYWORD DETECTION (fallback)
    col_lower = column_name.lower()

    if any(kw in col_lower for kw in CURRENCY_KEYWORDS):
        return f"${num:,.0f}".replace(",", ".")

    if any(kw in col_lower for kw in PERCENTAGE_KEYWORDS):
        return f"{num:,.1f}%".replace(".", ",")

    # 3. TYPE-BASED FORMATTING (default)
    if num == int(num):
        return f"{int(num):,}".replace(",", ".")
    else:
        return f"{num:,.2f}".replace(",", "TEMP").replace(".", ",").replace("TEMP", ".")


def _parse_colombian_display_number(value: Any, column_name: str = "") -> Any:
    """Best-effort parse of Colombian-formatted display strings back to numbers."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return value

    col_lower = column_name.lower()
    if text.endswith("%"):
        cleaned = text[:-1].strip().replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return value

    if text.startswith("$"):
        cleaned = text[1:].strip()
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(".", "")
        try:
            return float(cleaned)
        except ValueError:
            return value

    if re.fullmatch(r"\d{1,3}(\.\d{3})+", text):
        try:
            return int(text.replace(".", ""))
        except ValueError:
            return value

    # US thousands + decimal: 43,513,462.2216
    if re.fullmatch(r"-?[\d,]+\.\d+", text):
        try:
            return float(text.replace(",", ""))
        except ValueError:
            return value

    # US thousands integer: 43,513,462
    if "," in text and re.fullmatch(r"-?[\d,]+", text):
        try:
            return float(text.replace(",", ""))
        except ValueError:
            return value

    normalized = text.replace(",", ".")
    try:
        if col_lower in {c.lower() for c in INTEGER_COLUMNS} or col_lower in {
            "año",
            "ano",
            "anio",
            "mes",
            "dia",
        }:
            return int(float(normalized))
        return float(normalized)
    except ValueError:
        return value


def coerce_chart_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Restore numeric dtypes from Colombian-formatted table display strings."""
    if df is None or df.empty:
        return df

    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_numeric_dtype(out[col]):
            continue
        parsed = out[col].map(lambda v: _parse_colombian_display_number(v, col))
        if parsed.map(lambda v: isinstance(v, (int, float)) and not pd.isna(v)).any():
            out[col] = pd.to_numeric(parsed, errors="coerce")
    return out


def format_dataframe(df: pd.DataFrame, max_rows: int = 100) -> pd.DataFrame:
    """
    Apply beautiful formatting to entire dataframe.

    Args:
        df: DataFrame to format
        max_rows: Maximum rows to display (default 100)

    Returns:
        Formatted DataFrame with string values
    """
    if df is None or df.empty:
        return df

    # Limit rows for display
    df_display = df.head(max_rows).copy()

    # Apply formatting to each column
    for col in df_display.columns:
        df_display[col] = df_display[col].apply(lambda x: format_number(x, col))

    # Warn if truncated
    if len(df) > max_rows:
        print(f"\n⚠️ Mostrando solo las primeras {max_rows} filas (total: {len(df):,})")

    return df_display


def format_currency(value: float, decimals: int = 0) -> str:
    """
    Format a number as Colombian currency.

    Args:
        value: Number to format
        decimals: Number of decimal places (default 0)

    Returns:
        Formatted currency string (e.g., "$1.234.567")
    """
    if pd.isna(value) or value is None:
        return "-"

    try:
        num = float(value)
        if decimals == 0:
            return f"${num:,.0f}".replace(",", ".")
        else:
            return (
                f"${num:,.{decimals}f}".replace(",", "TEMP")
                .replace(".", ",")
                .replace("TEMP", ".")
            )
    except (ValueError, TypeError):
        return str(value)


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    Format a number as percentage.

    Args:
        value: Number to format (e.g., 0.456 for 45.6%)
        decimals: Number of decimal places (default 1)

    Returns:
        Formatted percentage string (e.g., "45,6%")
    """
    if pd.isna(value) or value is None:
        return "-"

    try:
        num = float(value)
        if decimals == 0:
            return f"{num:,.0f}%".replace(".", ",")
        else:
            return f"{num:,.{decimals}f}%".replace(".", ",")
    except (ValueError, TypeError):
        return str(value)


def format_integer(value: Any) -> str:
    """
    Format a number as integer with thousand separators.

    Args:
        value: Number to format

    Returns:
        Formatted integer string (e.g., "1.234")
    """
    if pd.isna(value) or value is None:
        return "-"

    try:
        num = int(float(value))
        return f"{num:,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(value)
