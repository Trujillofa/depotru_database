"""Shared xlsxwriter helpers: content-based column widths and banners."""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional, Sequence


def _display_text(value: Any, currency: bool = False) -> str:
    """Approximate the rendered width of a cell value."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Sí/No"
    if isinstance(value, (dt.date, dt.datetime)):
        return "Miércoles, 30 de septiembre de 2026"
    if isinstance(value, (int, float)):
        if currency:
            return f"${value:,.0f}"
        return f"{value:,.0f}"
    return str(value)


def autofit_columns(
    worksheet: Any,
    rows: Sequence[Sequence[Any]],
    *,
    currency_columns: Sequence[int] = (),
    date_columns: Sequence[int] = (),
    min_width: int = 8,
    max_width: int = 45,
    min_date_width: int = 18,
    padding: int = 2,
    extra_widths: Optional[dict] = None,
) -> None:
    """Set column widths from the longest rendered content (audit V-7/S-9)."""
    widths: dict = {}
    for row in rows:
        for col_index, value in enumerate(row):
            text = _display_text(value, currency=col_index in currency_columns)
            length = len(text)
            if length > widths.get(col_index, 0):
                widths[col_index] = length
    extra_widths = extra_widths or {}
    for col_index in sorted(set(widths) | set(extra_widths) | set(date_columns)):
        width = widths.get(col_index, min_width)
        width = max(min_width, min(max_width, width + padding))
        if col_index in extra_widths:
            width = max(width, extra_widths[col_index])
        if col_index in date_columns:
            width = max(width, min_date_width)
        worksheet.set_column(col_index, col_index, width)


def write_banner(
    worksheet: Any,
    last_col: int,
    title: str,
    subtitle: str,
    title_format: Any,
    subtitle_format: Any,
) -> None:
    """Write a two-row banner above a data block."""
    worksheet.merge_range(0, 0, 0, last_col, title, title_format)
    worksheet.merge_range(1, 0, 1, last_col, subtitle, subtitle_format)
