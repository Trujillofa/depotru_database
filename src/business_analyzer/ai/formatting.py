"""
Formatting module for AI package.

Contains number formatting utilities for Colombian pesos, percentages, and thousands.
"""

import locale
import pandas as pd
from typing import Any, List, Optional

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
    "Revenue",
    "Ganancia",
    "Ganancia_Neta",
    "total_revenue",
    "Ticket_Promedio",
    "Revenue_Neto",
    "Precio",
    "Costo",
]

# Known percentage columns
PERCENTAGE_COLUMNS = [
    "Margen_Promedio_Pct",
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
        return str(value)

    # 1. EXPLICIT COLUMN MATCH (highest priority)
    if column_name in CURRENCY_COLUMNS:
        return f"${num:,.0f}".replace(",", ".")

    if column_name in PERCENTAGE_COLUMNS:
        return f"{num:,.1f}%".replace(".", ",")

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
