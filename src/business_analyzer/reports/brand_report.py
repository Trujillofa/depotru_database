"""Brand business report builder (current period vs. same period last year).

Powers the Vanna "Informe de marca" card, the ``depotru-brand-report`` CLI, and
JSON/HTML outputs. All figures come from ``banco_datos`` plus the optional
``productos_adicional`` master and ``J3System`` inventory.

Usage:
    from business_analyzer.reports.brand_report import build_brand_report_result

    result = build_brand_report_result(brand="SIKA", year=2026)
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    from config import Config
except ImportError:  # pragma: no cover - direct module execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
    from config import Config

from business_analyzer.core.database import Database
from business_analyzer.core.db_factory import get_database
from business_analyzer.core.inventory_warehouse_policy import (
    turnover_sku_denylist_sql_not_like,
    turnover_warehouse_sql_in_list,
)

logger = logging.getLogger(__name__)

REPORT_PREFIX = "INFORME_MARCA"
SUPPORTED_FORMATS = ("html", "json")
MONTH_NAMES_ES = (
    "",
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)
_BRAND_RE = re.compile(r"[^A-Z0-9]+")
_NAME_FALLBACK_MIN_LEN = 4
_BRANDS_CACHE: Dict[Any, Tuple[float, Dict[str, Any]]] = {}
_BRANDS_CACHE_TTL = 600.0


def _to_float(value: Any) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int:
    try:
        return int(float(value)) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def normalize_brand(brand: str) -> str:
    """Trim/collapse whitespace; keep the display form, reject empty values."""
    text = " ".join(str(brand or "").split())
    if not text:
        raise ValueError("La marca es obligatoria.")
    if len(text) > 80:
        raise ValueError("La marca no puede superar 80 caracteres.")
    return text


def brand_slug(brand: str) -> str:
    slug = _BRAND_RE.sub("_", normalize_brand(brand).upper()).strip("_")
    return slug or "MARCA"


def brand_report_basename(
    brand: str, start_date: Any, end_date: Any, fmt: str = "html"
) -> str:
    ext = "json" if (fmt or "").lower() == "json" else "html"
    start = start_date.isoformat() if isinstance(start_date, date) else str(start_date)
    end = end_date.isoformat() if isinstance(end_date, date) else str(end_date)
    return f"{REPORT_PREFIX}_{brand_slug(brand)}_{start}_{end}.{ext}"


def _month_end(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def _same_day_prior_year(value: date) -> date:
    try:
        return value.replace(year=value.year - 1)
    except ValueError:  # Feb 29 -> Feb 28
        return value.replace(year=value.year - 1, day=28)


def resolve_brand_period_range(
    start_date: date,
    end_date: date,
    *,
    max_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Resolve current/prior windows for an explicit date range.

    ``end_date`` is the requested end; the actual window is clipped to
    ``max_date`` so available data is never invented. The prior-year window
    always mirrors the actual current window.
    """
    latest = max_date or date.today()
    requested_start = start_date
    requested_end = end_date
    if requested_start > requested_end:
        raise ValueError(
            f"La fecha inicial ({requested_start.isoformat()}) no puede ser "
            f"posterior a la final ({requested_end.isoformat()})."
        )
    if requested_start > latest:
        raise ValueError(
            f"No hay datos desde {requested_start.isoformat()}; "
            f"el último dato disponible es {latest.isoformat()}."
        )
    actual_start = requested_start
    actual_end = min(requested_end, latest)
    if actual_end < actual_start:
        raise ValueError(
            f"El rango solicitado no tiene datos; el último dato disponible "
            f"es {latest.isoformat()}."
        )

    prior_start = _same_day_prior_year(actual_start)
    prior_end = _same_day_prior_year(actual_end)
    if actual_end == _month_end(actual_end.year, actual_end.month):
        prior_end = _month_end(prior_end.year, prior_end.month)
    days = (actual_end - actual_start).days + 1
    prior_days = (prior_end - prior_start).days + 1
    full_year = (
        requested_start.month == 1
        and requested_start.day == 1
        and requested_end.month == 12
        and requested_end.day == 31
        and requested_start.year == requested_end.year
    )
    year_incomplete = actual_start != date(
        actual_start.year, 1, 1
    ) or actual_end != date(actual_end.year, 12, 31)
    return {
        "year": actual_end.year,
        "start": actual_start,
        "end": actual_end,
        "requested_start": requested_start,
        "requested_end": requested_end,
        "prior_year": actual_end.year - 1,
        "prior_start": prior_start,
        "prior_end": prior_end,
        "days": days,
        "prior_days": prior_days,
        "partial": year_incomplete,
        "clamped": actual_end < requested_end,
        "full_year": full_year,
        "as_of": actual_end.isoformat(),
        "requested_as_of": requested_end.isoformat(),
    }


def resolve_brand_period(
    year: int, as_of: Optional[date] = None, *, max_date: Optional[date] = None
) -> Dict[str, Any]:
    """Legacy year/as-of resolver (kept for CLI/API compatibility).

    A past year closes on Dec 31; the latest year closes on the database max
    date. When no ``as_of`` is supplied for the latest year, the requested
    window is the full year and the actual window is clipped to available data.
    """
    if year < 2000 or year > 2100:
        raise ValueError(f"Año inválido: {year}")
    latest = max_date or date.today()
    if year > latest.year:
        raise ValueError(
            f"No hay datos para {year}; el último dato disponible es {latest.isoformat()}."
        )

    requested_start = date(year, 1, 1)
    requested_end = as_of or date(year, 12, 31)
    period = resolve_brand_period_range(requested_start, requested_end, max_date=latest)
    return period


def default_brand_as_of(*, today: Optional[date] = None) -> str:
    """Yesterday, matching the other as-of reports."""
    ref = today or date.today()
    return (ref - timedelta(days=1)).isoformat()


def validate_brand_as_of(value: str) -> date:
    raw = str(value or "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        raise ValueError(f"Fecha inválida (use YYYY-MM-DD): {value!r}")
    return date.fromisoformat(raw)


def _fmt_number(value: Any, decimals: int = 0) -> str:
    number = _to_float(value)
    if decimals <= 0:
        return f"{number:,.0f}".replace(",", ".")
    text = f"{number:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_money(value: Any, decimals: int = 1) -> str:
    return f"${_fmt_number(_to_float(value) / 1_000_000, decimals)} M"


def _fmt_pct(value: Any, decimals: int = 2) -> str:
    return f"{_fmt_number(value, decimals)}%"


def _delta_pct(current: float, prior: float) -> Optional[float]:
    if not prior:
        return None
    return (current / prior - 1.0) * 100.0


def _fmt_delta(current: float, prior: float) -> str:
    delta = _delta_pct(current, prior)
    if delta is None:
        return "n/a"
    return f"{delta:+.1f}%".replace(".", ",")


def _bp_delta(current_pct: float, prior_pct: float) -> str:
    return f"{(current_pct - prior_pct) * 100:+.0f} pb".replace(".", ",")


class BrandReportBuilder:
    """Build a brand-level P&L, customer, product, returns and inventory report."""

    def __init__(
        self,
        brand: str,
        year: Optional[int] = None,
        as_of: Optional[date] = None,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        db: Optional[Database] = None,
        top_n: int = 15,
        include_inventory: bool = True,
    ) -> None:
        self.brand = normalize_brand(brand)
        self.brand_upper = self.brand.upper()
        self.db = db or get_database()
        self.top_n = max(5, int(top_n))
        self.include_inventory = include_inventory
        self.excluded = tuple(Config.EXCLUDED_DOCUMENT_CODES)
        self.db_name = Database.validate_sql_identifier(Config.DB_NAME, "database")
        self.table_name = Database.validate_sql_identifier(Config.DB_TABLE, "table")
        self.base = (
            f"[{self.db_name}].[dbo].[{self.table_name}] bd "
            f"LEFT JOIN [{self.db_name}].[dbo].[productos_adicional] pa "
            "ON bd.ArticulosCodigo = pa.producto_codigo"
        )
        self.max_date = self._fetch_max_date()
        if start_date is not None or end_date is not None:
            if start_date is None or end_date is None:
                raise ValueError(
                    "Debe indicar la fecha inicial y la fecha final del rango."
                )
            self.period = resolve_brand_period_range(
                start_date, end_date, max_date=self.max_date
            )
        else:
            report_year = int(year) if year is not None else self.max_date.year
            self.period = resolve_brand_period(
                report_year, as_of, max_date=self.max_date
            )
        self.year = self.period["year"]

    # ------------------------------------------------------------------ SQL
    def _fetch_max_date(self) -> date:
        rows = self.db.execute_query(
            f"SELECT MAX(bd.Fecha) AS max_date FROM {self.base}"
        )
        value = rows[0].get("max_date") if rows else None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if value:
            return date.fromisoformat(str(value)[:10])
        raise ValueError("No hay datos de ventas en banco_datos.")

    def _brand_condition(self, bd: str = "bd", pa: str = "pa") -> Tuple[str, List[Any]]:
        """Brand match: master brand, brand category, or name fallback.

        The name fallback is only used when the product has no master brand and
        the brand is long enough to avoid false positives (e.g. ``ICO``).
        """
        master = f"UPPER(LTRIM(RTRIM({pa}.producto_marca))) = %s"
        category = f"UPPER(LTRIM(RTRIM({bd}.categoria))) IN (%s, %s)"
        parts = [master, category]
        params: List[Any] = [
            self.brand_upper,
            self.brand_upper,
            f"PRODUCTOS {self.brand_upper}",
        ]
        if len(self.brand_upper) >= _NAME_FALLBACK_MIN_LEN:
            parts.append(
                f"(({pa}.producto_codigo IS NULL OR "
                f"NULLIF(LTRIM(RTRIM({pa}.producto_marca)), '') IS NULL) "
                f"AND UPPER({bd}.ArticulosNombre) LIKE %s)"
            )
            params.append(f"%{self.brand_upper}%")
        return " OR ".join(f"({part})" for part in parts), params

    def _doc_condition(self, bd: str = "bd") -> Tuple[str, List[Any]]:
        placeholders = ",".join(["%s"] * len(self.excluded))
        return f"{bd}.DocumentosCodigo NOT IN ({placeholders})", list(self.excluded)

    def _where(
        self, start: date, end: date, *, brand: bool = True
    ) -> Tuple[str, List[Any]]:
        doc_sql, doc_params = self._doc_condition()
        clauses = [f"bd.Fecha BETWEEN %s AND %s", doc_sql]
        params: List[Any] = [start, end] + doc_params
        if brand:
            brand_sql, brand_params = self._brand_condition()
            clauses.append(f"({brand_sql})")
            params.extend(brand_params)
        return " AND ".join(clauses), params

    def _rows(self, sql: str, params: Sequence[Any]) -> List[Dict[str, Any]]:
        return list(self.db.execute_query(sql, tuple(params)))

    # --------------------------------------------------------------- metrics
    def _kpis(self, start: date, end: date, *, brand: bool = True) -> Dict[str, Any]:
        where, params = self._where(start, end, brand=brand)
        sql = f"""
            SELECT
                COUNT(*) AS lines,
                COUNT(DISTINCT bd.ArticulosCodigo) AS skus,
                COUNT(DISTINCT bd.TercerosID) AS customers,
                COUNT(DISTINCT bd.DocumentosCodigo + '|' +
                    CAST(CAST(bd.NumeroDocumento AS bigint) AS VARCHAR(30))) AS invoices,
                SUM(bd.TotalSinIva) AS rev,
                SUM(bd.TotalMasIva) AS rev_iva,
                SUM(bd.ValorCosto) AS cost,
                SUM(bd.Cantidad) AS qty,
                SUM(CASE WHEN bd.TotalSinIva > 0 THEN bd.TotalSinIva ELSE 0 END) AS gross_rev,
                SUM(CASE WHEN bd.DocumentosNombre LIKE 'DEVOLUC%'
                         THEN bd.TotalSinIva ELSE 0 END) AS return_rev,
                COUNT(CASE WHEN bd.DocumentosNombre LIKE 'DEVOLUC%'
                           THEN 1 END) AS return_lines
            FROM {self.base}
            WHERE {where}
        """
        row = self._rows(sql, params)[0]
        result = {key: _to_float(value) for key, value in row.items()}
        for key in ("lines", "skus", "customers", "invoices", "return_lines"):
            result[key] = _to_int(row.get(key))
        result["profit"] = result["rev"] - result["cost"]
        result["margin_pct"] = _safe_div(result["profit"], result["rev"]) * 100
        result["avg_ticket"] = _safe_div(result["rev"], result["invoices"])
        result["price_unit"] = _safe_div(result["rev"], result["qty"])
        result["return_pct"] = (
            _safe_div(abs(result["return_rev"]), result["gross_rev"]) * 100
        )
        return result

    def _annual(self) -> List[Dict[str, Any]]:
        start = date(self.year - 4, 1, 1)
        end = self.period["end"]
        where, params = self._where(start, end, brand=True)
        sql = f"""
            SELECT bd.ano AS year,
                SUM(bd.TotalSinIva) AS rev,
                SUM(bd.ValorCosto) AS cost,
                SUM(bd.Cantidad) AS qty,
                COUNT(DISTINCT bd.TercerosID) AS customers,
                COUNT(DISTINCT bd.DocumentosCodigo + '|' +
                    CAST(CAST(bd.NumeroDocumento AS bigint) AS VARCHAR(30))) AS invoices,
                COUNT(DISTINCT bd.ArticulosCodigo) AS skus
            FROM {self.base}
            WHERE {where}
            GROUP BY bd.ano
            ORDER BY bd.ano
        """
        rows: List[Dict[str, Any]] = []
        for row in self._rows(sql, params):
            rev = _to_float(row.get("rev"))
            cost = _to_float(row.get("cost"))
            rows.append(
                {
                    "year": _to_int(row.get("year")),
                    "rev": rev,
                    "cost": cost,
                    "profit": rev - cost,
                    "margin_pct": _safe_div(rev - cost, rev) * 100,
                    "qty": _to_float(row.get("qty")),
                    "customers": _to_int(row.get("customers")),
                    "invoices": _to_int(row.get("invoices")),
                    "skus": _to_int(row.get("skus")),
                    "partial": _to_int(row.get("year")) == self.year
                    and self.period["end"] < date(self.year, 12, 31),
                }
            )
        return rows

    def _monthly(self) -> List[Dict[str, Any]]:
        start, end = self.period["start"], self.period["end"]
        prior_start, prior_end = self.period["prior_start"], self.period["prior_end"]
        select = """
            bd.ano AS year, bd.mes AS month,
            SUM(bd.TotalSinIva) AS rev, SUM(bd.ValorCosto) AS cost,
            SUM(bd.Cantidad) AS qty,
            COUNT(DISTINCT bd.DocumentosCodigo + '|' +
                CAST(CAST(bd.NumeroDocumento AS bigint) AS VARCHAR(30))) AS invoices
        """
        where_cur, params_cur = self._where(start, end)
        where_prev, params_prev = self._where(prior_start, prior_end)
        cur_rows = self._rows(
            f"SELECT {select} FROM {self.base} WHERE {where_cur} "
            "GROUP BY bd.ano, bd.mes ORDER BY bd.ano, bd.mes",
            params_cur,
        )
        prev_rows = self._rows(
            f"SELECT {select} FROM {self.base} WHERE {where_prev} "
            "GROUP BY bd.ano, bd.mes ORDER BY bd.ano, bd.mes",
            params_prev,
        )
        cur_by_month = {
            (_to_int(r.get("year")), _to_int(r.get("month"))): r for r in cur_rows
        }
        prev_by_month = {
            (_to_int(r.get("year")), _to_int(r.get("month"))): r for r in prev_rows
        }

        months: List[tuple[int, int]] = []
        cursor = date(start.year, start.month, 1)
        while (cursor.year, cursor.month) <= (end.year, end.month):
            months.append((cursor.year, cursor.month))
            if cursor.month == 12:
                cursor = date(cursor.year + 1, 1, 1)
            else:
                cursor = date(cursor.year, cursor.month + 1, 1)

        result: List[Dict[str, Any]] = []
        spans_years = start.year != end.year
        for year, month in months:
            cur = cur_by_month.get((year, month), {})
            prev = prev_by_month.get((year - 1, month), {})
            window_start = max(start, date(year, month, 1))
            window_end = min(end, _month_end(year, month))
            is_partial = window_start != date(
                year, month, 1
            ) or window_end != _month_end(year, month)
            if is_partial:
                p_start = _same_day_prior_year(window_start)
                p_end = _same_day_prior_year(window_end)
                if p_end >= p_start:
                    where_p, params_p = self._where(p_start, p_end)
                    override = self._rows(
                        f"SELECT {select} FROM {self.base} WHERE {where_p} "
                        "GROUP BY bd.ano, bd.mes",
                        params_p,
                    )
                    if override:
                        prev = override[0]
            cur_rev = _to_float(cur.get("rev"))
            prev_rev = _to_float(prev.get("rev"))
            cur_cost = _to_float(cur.get("cost"))
            prev_cost = _to_float(prev.get("cost"))
            label = MONTH_NAMES_ES[month] if month <= 12 else str(month)
            if spans_years:
                label = f"{label} {year}"
            result.append(
                {
                    "year": year,
                    "month": month,
                    "label": label,
                    "current_rev": cur_rev,
                    "prior_rev": prev_rev,
                    "current_cost": cur_cost,
                    "prior_cost": prev_cost,
                    "current_profit": cur_rev - cur_cost,
                    "prior_profit": prev_rev - prev_cost,
                    "current_margin_pct": _safe_div(cur_rev - cur_cost, cur_rev) * 100,
                    "prior_margin_pct": _safe_div(prev_rev - prev_cost, prev_rev) * 100,
                    "current_qty": _to_float(cur.get("qty")),
                    "prior_qty": _to_float(prev.get("qty")),
                    "current_invoices": _to_int(cur.get("invoices")),
                    "delta_pct": _delta_pct(cur_rev, prev_rev),
                    "partial": is_partial,
                }
            )
        return result

    def _breakdown(
        self,
        select: str,
        group_by: str,
        order_by: str,
        start: date,
        end: date,
        *,
        extra_where: str = "",
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        where, params = self._where(start, end)
        if extra_where:
            where = f"{where} AND {extra_where}"
        top = f"TOP {int(limit)} " if limit else ""
        sql = f"""
            SELECT {top}{select}
            FROM {self.base}
            WHERE {where}
            GROUP BY {group_by}
            ORDER BY {order_by}
        """
        return self._rows(sql, params)

    def _warehouses(self) -> Dict[str, List[Dict[str, Any]]]:
        select = """
            bd.AlmacenCodigo AS code,
            SUM(bd.TotalSinIva) AS rev, SUM(bd.ValorCosto) AS cost,
            SUM(bd.Cantidad) AS qty, COUNT(*) AS lines,
            COUNT(DISTINCT bd.TercerosID) AS customers,
            COUNT(DISTINCT bd.DocumentosCodigo + '|' +
                CAST(CAST(bd.NumeroDocumento AS bigint) AS VARCHAR(30))) AS invoices
        """
        cur = self._breakdown(
            select,
            "bd.AlmacenCodigo",
            "SUM(bd.TotalSinIva) DESC",
            self.period["start"],
            self.period["end"],
        )
        prev = self._breakdown(
            select,
            "bd.AlmacenCodigo",
            "SUM(bd.TotalSinIva) DESC",
            self.period["prior_start"],
            self.period["prior_end"],
        )
        return {
            "current": self._finish_breakdown(cur),
            "prior": self._finish_breakdown(prev),
        }

    def _branches(self) -> Dict[str, List[Dict[str, Any]]]:
        select = """
            bd.DocumentosCodigo AS code,
            MAX(bd.DocumentosNombre) AS doc_name,
            SUM(bd.TotalSinIva) AS rev, SUM(bd.ValorCosto) AS cost,
            SUM(bd.Cantidad) AS qty, COUNT(*) AS lines,
            COUNT(DISTINCT bd.TercerosID) AS customers,
            COUNT(DISTINCT bd.DocumentosCodigo + '|' +
                CAST(CAST(bd.NumeroDocumento AS bigint) AS VARCHAR(30))) AS invoices
        """
        cur = self._breakdown(
            select,
            "bd.DocumentosCodigo",
            "SUM(bd.TotalSinIva) DESC",
            self.period["start"],
            self.period["end"],
        )
        prev = self._breakdown(
            select,
            "bd.DocumentosCodigo",
            "SUM(bd.TotalSinIva) DESC",
            self.period["prior_start"],
            self.period["prior_end"],
        )
        return {
            "current": self._finish_breakdown(cur),
            "prior": self._finish_breakdown(prev),
        }

    def _rubros(self) -> Dict[str, List[Dict[str, Any]]]:
        select = """
            COALESCE(NULLIF(LTRIM(RTRIM(pa.producto_rubro)), ''), '(sin rubro)') AS rubro,
            COALESCE(NULLIF(LTRIM(RTRIM(pa.producto_subrubro)), ''), '(sin subrubro)') AS subrubro,
            SUM(bd.TotalSinIva) AS rev, SUM(bd.ValorCosto) AS cost,
            SUM(bd.Cantidad) AS qty, COUNT(*) AS lines
        """
        group = (
            "COALESCE(NULLIF(LTRIM(RTRIM(pa.producto_rubro)), ''), '(sin rubro)'), "
            "COALESCE(NULLIF(LTRIM(RTRIM(pa.producto_subrubro)), ''), '(sin subrubro)')"
        )
        cur = self._breakdown(
            select,
            group,
            "SUM(bd.TotalSinIva) DESC",
            self.period["start"],
            self.period["end"],
        )
        prev = self._breakdown(
            select,
            group,
            "SUM(bd.TotalSinIva) DESC",
            self.period["prior_start"],
            self.period["prior_end"],
        )
        return {
            "current": self._finish_breakdown(cur),
            "prior": self._finish_breakdown(prev),
        }

    def _products(self) -> Dict[str, Any]:
        select = """
            bd.ArticulosCodigo AS sku, MAX(bd.ArticulosNombre) AS name,
            SUM(bd.TotalSinIva) AS rev, SUM(bd.ValorCosto) AS cost,
            SUM(bd.Cantidad) AS qty, COUNT(*) AS lines,
            COUNT(DISTINCT bd.TercerosID) AS customers,
            MAX(CASE WHEN pa.producto_codigo IS NULL OR
                     NULLIF(LTRIM(RTRIM(pa.producto_marca)), '') IS NULL
                     THEN 1 ELSE 0 END) AS missing_master
        """
        cur = self._breakdown(
            select,
            "bd.ArticulosCodigo",
            "SUM(bd.TotalSinIva) DESC",
            self.period["start"],
            self.period["end"],
        )
        prev = self._breakdown(
            select,
            "bd.ArticulosCodigo",
            "SUM(bd.TotalSinIva) DESC",
            self.period["prior_start"],
            self.period["prior_end"],
        )
        return self._finish_products(cur, prev)

    def _customers(self) -> Dict[str, Any]:
        select = """
            bd.TercerosID AS cid, MAX(bd.TercerosNombres) AS name,
            SUM(bd.TotalSinIva) AS rev, SUM(bd.ValorCosto) AS cost,
            SUM(bd.Cantidad) AS qty,
            COUNT(DISTINCT bd.DocumentosCodigo + '|' +
                CAST(CAST(bd.NumeroDocumento AS bigint) AS VARCHAR(30))) AS invoices,
            COUNT(DISTINCT bd.ArticulosCodigo) AS skus
        """
        cur = self._breakdown(
            select,
            "bd.TercerosID",
            "SUM(bd.TotalSinIva) DESC",
            self.period["start"],
            self.period["end"],
        )
        prev = self._breakdown(
            select,
            "bd.TercerosID",
            "SUM(bd.TotalSinIva) DESC",
            self.period["prior_start"],
            self.period["prior_end"],
        )
        return self._finish_customers(cur, prev)

    def _vendors(self) -> List[Dict[str, Any]]:
        select = """
            COALESCE(NULLIF(LTRIM(RTRIM(bd.VendedorAsignado)), ''), '(sin vendedor)') AS vendor,
            SUM(bd.TotalSinIva) AS rev, SUM(bd.ValorCosto) AS cost,
            SUM(bd.Cantidad) AS qty,
            COUNT(DISTINCT bd.TercerosID) AS customers,
            COUNT(DISTINCT bd.DocumentosCodigo + '|' +
                CAST(CAST(bd.NumeroDocumento AS bigint) AS VARCHAR(30))) AS invoices
        """
        group = (
            "COALESCE(NULLIF(LTRIM(RTRIM(bd.VendedorAsignado)), ''), '(sin vendedor)')"
        )
        cur = self._breakdown(
            select,
            group,
            "SUM(bd.TotalSinIva) DESC",
            self.period["start"],
            self.period["end"],
        )
        prev = self._breakdown(
            select,
            group,
            "SUM(bd.TotalSinIva) DESC",
            self.period["prior_start"],
            self.period["prior_end"],
        )
        return self._finish_vendors(cur, prev)

    def _returns(
        self, current: Dict[str, Any], prior: Dict[str, Any]
    ) -> Dict[str, Any]:
        extra = "bd.DocumentosNombre LIKE 'DEVOLUC%'"
        select_docs = """
            bd.DocumentosCodigo AS code, MAX(bd.DocumentosNombre) AS doc_name,
            COUNT(*) AS lines, COUNT(DISTINCT bd.ArticulosCodigo) AS skus,
            SUM(bd.Cantidad) AS qty, SUM(bd.TotalSinIva) AS rev
        """
        cur_docs = self._breakdown(
            select_docs,
            "bd.DocumentosCodigo",
            "SUM(bd.TotalSinIva) ASC",
            self.period["start"],
            self.period["end"],
            extra_where=extra,
        )
        prev_docs = self._breakdown(
            select_docs,
            "bd.DocumentosCodigo",
            "SUM(bd.TotalSinIva) ASC",
            self.period["prior_start"],
            self.period["prior_end"],
            extra_where=extra,
        )
        select_cust = """
            bd.TercerosID AS cid, MAX(bd.TercerosNombres) AS name,
            COUNT(*) AS lines, SUM(bd.TotalSinIva) AS rev
        """
        top_customers = self._breakdown(
            select_cust,
            "bd.TercerosID",
            "SUM(bd.TotalSinIva) ASC",
            self.period["start"],
            self.period["end"],
            extra_where=extra,
            limit=8,
        )
        select_prod = """
            bd.ArticulosCodigo AS sku, MAX(bd.ArticulosNombre) AS name,
            COUNT(*) AS lines, SUM(bd.Cantidad) AS qty, SUM(bd.TotalSinIva) AS rev
        """
        top_products = self._breakdown(
            select_prod,
            "bd.ArticulosCodigo",
            "SUM(bd.TotalSinIva) ASC",
            self.period["start"],
            self.period["end"],
            extra_where=extra,
            limit=10,
        )
        return {
            "current": current,
            "prior": prior,
            "by_doc": {
                "current": self._finish_breakdown(cur_docs),
                "prior": self._finish_breakdown(prev_docs),
            },
            "top_customers": self._finish_breakdown(top_customers),
            "top_products": self._finish_breakdown(top_products),
        }

    def _inventory(self, products: List[Dict[str, Any]], cogs: float) -> Dict[str, Any]:
        if not self.include_inventory:
            return {"available": False, "message": "Inventario no solicitado."}
        conn = None
        inventory_year: Optional[int] = None
        try:
            j3 = self.db.get_j3system_connection()
            conn = j3
            cursor = j3.cursor(as_dict=True)
            j3_db = Database.validate_sql_identifier(
                Config.DB_NAME_J3SYSTEM, "j3 database"
            )
            cursor.execute(
                f"SELECT MAX(Ano) AS max_year FROM [{j3_db}].dbo.InvDetalleExistencias"
            )
            max_row = cursor.fetchone() or {}
            max_year = _to_int(max_row.get("max_year"))
            if max_year <= 0:
                return {
                    "available": False,
                    "message": "Sin años de inventario en J3System.",
                }
            year_value = int(min(self.year, max_year))
            inventory_year = year_value
            wh_in = turnover_warehouse_sql_in_list()
            sku_deny = turnover_sku_denylist_sql_not_like()
            name_filter = ""
            params: List[Any] = [
                year_value,
                year_value - 1,
                year_value,
                year_value - 1,
                self.brand_upper,
            ]
            if len(self.brand_upper) >= _NAME_FALLBACK_MIN_LEN:
                name_filter = (
                    " OR (NULLIF(LTRIM(RTRIM(a.ArticulosMarca)), '') IS NULL "
                    "AND UPPER(a.ArticulosNombre) LIKE %s)"
                )
                params.append(f"%{self.brand_upper}%")
            sql = f"""
                SELECT LTRIM(RTRIM(a.ArticulosCodigo)) AS code,
                    MAX(a.ArticulosNombre) AS name,
                    MAX(COALESCE(a.ArticulosUltmoCosto, a.ArticulosCosto, 0)) AS cost,
                    SUM(CASE WHEN d.Ano = %s THEN d.SaldoActual ELSE 0 END) AS stock_current,
                    SUM(CASE WHEN d.Ano = %s THEN d.SaldoActual ELSE 0 END) AS stock_prior
                FROM [{j3_db}].dbo.AdmArticulos a
                JOIN [{j3_db}].dbo.InvExistencias e ON e.ArticulosID = a.ArticulosID
                JOIN [{j3_db}].dbo.InvDetalleExistencias d
                    ON d.ExistenciasID = e.ExistenciasID AND d.Ano IN (%s, %s)
                JOIN [{j3_db}].dbo.AdmAlmacen al ON al.AlmacenID = d.AlmacenID
                WHERE al.AlmacenCodigo IN ({wh_in})
                  AND NOT ({sku_deny})
                  AND (UPPER(LTRIM(RTRIM(a.ArticulosMarca))) = %s{name_filter})
                GROUP BY LTRIM(RTRIM(a.ArticulosCodigo))
            """
            cursor.execute(sql, tuple(params))
            rows = list(cursor)
            cursor.close()
        except Exception:  # noqa: BLE001 - inventory is optional
            logger.exception("brand report inventory failed brand=%s", self.brand)
            return {
                "available": False,
                "message": "Inventario no disponible para la marca.",
            }
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
        if not rows:
            return {
                "available": False,
                "message": "Sin artículos de la marca en J3System.",
            }

        sales_by_sku = {
            str(row.get("sku")).strip(): _to_float(row.get("qty")) for row in products
        }
        months = max(self.period["days"] / 30.4375, 1 / 30.4375)
        items: List[Dict[str, Any]] = []
        for row in rows:
            code = str(row.get("code") or "").strip()
            stock = _to_float(row.get("stock_current"))
            stock_prior = _to_float(row.get("stock_prior"))
            cost = _to_float(row.get("cost"))
            sold = sales_by_sku.get(code, 0.0)
            value = stock * cost
            coverage = _safe_div(stock, sold / months) if sold > 0 else None
            items.append(
                {
                    "sku": code,
                    "name": row.get("name") or "",
                    "stock": stock,
                    "stock_prior": stock_prior,
                    "cost": cost,
                    "value": value,
                    "value_prior": stock_prior * cost,
                    "sold": sold,
                    "coverage_months": coverage,
                    "dead": stock > 0 and sold <= 0,
                }
            )
        total_value = sum(item["value"] for item in items)
        total_value_prior = sum(item["value_prior"] for item in items)
        total_units = sum(item["stock"] for item in items)
        total_units_prior = sum(item["stock_prior"] for item in items)
        buckets: Dict[str, List[Dict[str, Any]]] = {
            "lt1": [],
            "m1_3": [],
            "m3_6": [],
            "gt6": [],
            "dead": [],
        }
        for item in items:
            if item["stock"] <= 0:
                continue
            if item["dead"]:
                buckets["dead"].append(item)
            elif item["coverage_months"] is not None and item["coverage_months"] < 1:
                buckets["lt1"].append(item)
            elif item["coverage_months"] is not None and item["coverage_months"] <= 3:
                buckets["m1_3"].append(item)
            elif item["coverage_months"] is not None and item["coverage_months"] <= 6:
                buckets["m3_6"].append(item)
            else:
                buckets["gt6"].append(item)

        def bucket_summary(items_: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
            values = list(items_)
            value = sum(item["value"] for item in values)
            return {
                "skus": len(values),
                "value": value,
                "share_pct": _safe_div(value, total_value) * 100,
            }

        overstock = sorted(
            [item for item in items if item["stock"] > 0 and item["coverage_months"]],
            key=lambda item: (item["coverage_months"] or 0, item["value"]),
            reverse=True,
        )[:8]
        dead = sorted(
            [item for item in items if item["dead"]],
            key=lambda item: item["value"],
            reverse=True,
        )[:8]
        avg_inventory = (total_value + total_value_prior) / 2
        days = _safe_div(avg_inventory, _safe_div(cogs, self.period["days"]))
        return {
            "available": True,
            "year": inventory_year,
            "items": items,
            "total_value": total_value,
            "total_value_prior": total_value_prior,
            "total_units": total_units,
            "total_units_prior": total_units_prior,
            "value_delta_pct": _delta_pct(total_value, total_value_prior),
            "units_delta_pct": _delta_pct(total_units, total_units_prior),
            "days": days,
            "turnover": _safe_div(365, days) if days else 0,
            "buckets": {key: bucket_summary(value) for key, value in buckets.items()},
            "overstock": overstock,
            "dead_stock": dead,
            "sku_count": len(items),
            "stocked_sku_count": sum(1 for item in items if item["stock"] > 0),
        }

    # ------------------------------------------------------------- finishing
    @staticmethod
    def _finish_breakdown(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        total_rev = sum(_to_float(row.get("rev")) for row in rows)
        for row in rows:
            rev = _to_float(row.get("rev"))
            cost = _to_float(row.get("cost"))
            item = {key: value for key, value in row.items()}
            item["rev"] = rev
            item["cost"] = cost
            item["profit"] = rev - cost
            item["margin_pct"] = _safe_div(rev - cost, rev) * 100
            item["share_pct"] = _safe_div(rev, total_rev) * 100
            item["qty"] = _to_float(row.get("qty"))
            for key in ("lines", "customers", "invoices", "skus"):
                if key in item:
                    item[key] = _to_int(row.get(key))
            result.append(item)
        return result

    def _finish_products(
        self, current: Sequence[Mapping[str, Any]], prior: Sequence[Mapping[str, Any]]
    ) -> Dict[str, Any]:
        cur = {str(row.get("sku")): row for row in current}
        prev = {str(row.get("sku")): row for row in prior}
        top = self._finish_breakdown(current)[: self.top_n]
        for top_row in top:
            top_row["prior_rev"] = _to_float(
                prev.get(str(top_row.get("sku")), {}).get("rev")
            )
        moves: List[Dict[str, Any]] = []
        for sku, product in cur.items():
            cur_rev = _to_float(product.get("rev"))
            prev_rev = _to_float(prev.get(sku, {}).get("rev"))
            moves.append(
                {
                    "sku": sku,
                    "name": product.get("name") or "",
                    "current": cur_rev,
                    "prior": prev_rev,
                    "delta": cur_rev - prev_rev,
                }
            )
        for sku, product in prev.items():
            if sku in cur:
                continue
            prev_rev = _to_float(product.get("rev"))
            moves.append(
                {
                    "sku": sku,
                    "name": product.get("name") or "",
                    "current": 0.0,
                    "prior": prev_rev,
                    "delta": -prev_rev,
                }
            )
        gains = sorted(moves, key=lambda item: item["delta"], reverse=True)[:8]
        losses = sorted(moves, key=lambda item: item["delta"])[:8]
        promo_rows = [
            row for row in current if "PROMOCION" in str(row.get("name", "")).upper()
        ]
        base_rows = [
            row
            for row in current
            if "PROMOCION" not in str(row.get("name", "")).upper()
        ]
        prior_promo = [
            row for row in prior if "PROMOCION" in str(row.get("name", "")).upper()
        ]
        prior_base = [
            row for row in prior if "PROMOCION" not in str(row.get("name", "")).upper()
        ]

        def set_metrics(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
            rev = sum(_to_float(row.get("rev")) for row in rows)
            cost = sum(_to_float(row.get("cost")) for row in rows)
            return {
                "rev": rev,
                "profit": rev - cost,
                "margin_pct": _safe_div(rev - cost, rev) * 100,
                "skus": len(rows),
            }

        promo_cur = set_metrics(promo_rows)
        promo_prev = set_metrics(prior_promo)
        base_cur = set_metrics(base_rows)
        base_prev = set_metrics(prior_base)
        total_rev = promo_cur["rev"] + base_cur["rev"]
        total_prev_rev = promo_prev["rev"] + base_prev["rev"]
        missing_cur = {
            "skus": sum(1 for row in current if _to_int(row.get("missing_master"))),
            "rev": sum(
                _to_float(row.get("rev"))
                for row in current
                if _to_int(row.get("missing_master"))
            ),
        }
        missing_prev = {
            "skus": sum(1 for row in prior if _to_int(row.get("missing_master"))),
            "rev": sum(
                _to_float(row.get("rev"))
                for row in prior
                if _to_int(row.get("missing_master"))
            ),
        }
        return {
            "top": top,
            "items": self._finish_breakdown(current),
            "gains": gains,
            "losses": losses,
            "promo": {
                "current": promo_cur,
                "prior": promo_prev,
                "base_current": base_cur,
                "base_prior": base_prev,
                "share_pct": _safe_div(promo_cur["rev"], total_rev) * 100,
                "prior_share_pct": _safe_div(promo_prev["rev"], total_prev_rev) * 100,
            },
            "master_gap": {
                "current": missing_cur,
                "prior": missing_prev,
                "share_pct": _safe_div(missing_cur["rev"], total_rev) * 100,
                "prior_share_pct": _safe_div(missing_prev["rev"], total_prev_rev) * 100,
            },
        }

    def _finish_customers(
        self, current: Sequence[Mapping[str, Any]], prior: Sequence[Mapping[str, Any]]
    ) -> Dict[str, Any]:
        cur = {str(row.get("cid")): row for row in current}
        prev = {str(row.get("cid")): row for row in prior}
        top = self._finish_breakdown(current)[: self.top_n]
        for top_row in top:
            top_row["prior_rev"] = _to_float(
                prev.get(str(top_row.get("cid")), {}).get("rev")
            )
        both = set(cur) & set(prev)
        new = set(cur) - set(prev)
        lost = set(prev) - set(cur)
        recurring_cur = sum(_to_float(cur[cid].get("rev")) for cid in both)
        recurring_prev = sum(_to_float(prev[cid].get("rev")) for cid in both)
        new_rows = sorted(
            (cur[cid] for cid in new),
            key=lambda row: _to_float(row.get("rev")),
            reverse=True,
        )
        lost_rows = sorted(
            (prev[cid] for cid in lost),
            key=lambda row: _to_float(row.get("rev")),
            reverse=True,
        )
        total_rev = sum(_to_float(row.get("rev")) for row in current)
        top10 = sorted((_to_float(row.get("rev")) for row in current), reverse=True)[
            :10
        ]
        buckets = {"one": {"customers": 0, "rev": 0.0}}
        buckets.update(
            {
                "two_three": {"customers": 0, "rev": 0.0},
                "four_nine": {"customers": 0, "rev": 0.0},
                "ten_plus": {"customers": 0, "rev": 0.0},
            }
        )
        for customer in current:
            invoices = _to_int(customer.get("invoices"))
            rev = _to_float(customer.get("rev"))
            key = (
                "one"
                if invoices <= 1
                else "two_three"
                if invoices <= 3
                else "four_nine"
                if invoices <= 9
                else "ten_plus"
            )
            buckets[key]["customers"] += 1
            buckets[key]["rev"] += rev
        for value in buckets.values():
            value["share_pct"] = _safe_div(value["rev"], total_rev) * 100
        return {
            "top": top,
            "stats": {
                "customers": len(cur),
                "prior_customers": len(prev),
                "top10_share_pct": _safe_div(sum(top10), total_rev) * 100,
                "recurring": {
                    "customers": len(both),
                    "current_rev": recurring_cur,
                    "prior_rev": recurring_prev,
                    "delta": recurring_cur - recurring_prev,
                    "delta_pct": _delta_pct(recurring_cur, recurring_prev),
                },
                "new": {
                    "customers": len(new),
                    "rev": sum(_to_float(row.get("rev")) for row in new_rows),
                    "top": [
                        {"name": row.get("name"), "rev": _to_float(row.get("rev"))}
                        for row in new_rows[:6]
                    ],
                },
                "lost": {
                    "customers": len(lost),
                    "rev": sum(_to_float(row.get("rev")) for row in lost_rows),
                    "top": [
                        {"name": row.get("name"), "rev": _to_float(row.get("rev"))}
                        for row in lost_rows[:6]
                    ],
                },
                "buckets": buckets,
            },
        }

    def _finish_vendors(
        self, current: Sequence[Mapping[str, Any]], prior: Sequence[Mapping[str, Any]]
    ) -> List[Dict[str, Any]]:
        prev = {str(row.get("vendor")): row for row in prior}
        rows = self._finish_breakdown(current)[: max(self.top_n, 12)]
        for row in rows:
            prior_rev = _to_float(prev.get(str(row.get("vendor")), {}).get("rev"))
            row["prior_rev"] = prior_rev
            row["delta_pct"] = _delta_pct(_to_float(row.get("rev")), prior_rev)
        return rows

    # --------------------------------------------------------------- findings
    def _findings(
        self,
        current: Dict[str, Any],
        prior: Dict[str, Any],
        warehouses: Dict[str, List[Dict[str, Any]]],
        products: Dict[str, Any],
        customers: Dict[str, Any],
        inventory: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []
        cur_wh = {row["code"]: row for row in warehouses["current"]}
        prev_wh = {row["code"]: row for row in warehouses["prior"]}
        new_wh = [
            row
            for code, row in cur_wh.items()
            if _to_float(prev_wh.get(code, {}).get("rev")) <= 0
            and _to_float(row.get("rev")) > 0
        ]
        core_codes = {
            code for code, row in prev_wh.items() if _to_float(row.get("rev")) > 0
        } | {
            code
            for code, row in cur_wh.items()
            if _to_float(prev_wh.get(code, {}).get("rev")) > 0
        }
        core_cur = sum(
            _to_float(cur_wh.get(code, {}).get("rev")) for code in core_codes
        )
        core_prev = sum(
            _to_float(prev_wh.get(code, {}).get("rev")) for code in core_codes
        )
        material_new = [
            row
            for row in new_wh
            if _to_float(row.get("rev")) >= max(20_000_000, current["rev"] * 0.01)
        ]
        new_rev = sum(_to_float(row.get("rev")) for row in material_new)
        if material_new and core_codes and new_rev >= current["rev"] * 0.03:
            names = ", ".join(str(row.get("code")) for row in material_new[:3])
            verb = "aportan" if len(material_new) > 1 else "aporta"
            findings.append(
                {
                    "title": "El crecimiento depende de canales nuevos",
                    "evidence": (
                        f"{names} {verb} {_fmt_money(new_rev)}; los canales existentes "
                        f"cambian {_fmt_delta(core_cur, core_prev)} "
                        f"({_fmt_money(core_cur - core_prev)})"
                    ),
                    "risk": "Si el canal nuevo se estabiliza, la marca puede volver a decrecer.",
                    "priority": "Alta",
                }
            )
        margin_delta = current["margin_pct"] - prior["margin_pct"]
        if prior["rev"] <= 0 and current["rev"] > 0:
            findings.append(
                {
                    "title": "Marca nueva o sin base comparable",
                    "evidence": (
                        f"Ventas actuales {_fmt_money(current['rev'])} sin ventas "
                        "en el mismo rango del año anterior."
                    ),
                    "risk": "El comparativo YoY no es representativo.",
                    "priority": "Media",
                }
            )
        elif abs(margin_delta) >= 0.3:
            findings.append(
                {
                    "title": "El margen bruto se movió",
                    "evidence": (
                        f"{_fmt_pct(current['margin_pct'])} vs. "
                        f"{_fmt_pct(prior['margin_pct'])} ({_bp_delta(current['margin_pct'], prior['margin_pct'])})"
                    ),
                    "risk": "Vigilar mezcla de producto, promociones y costo de compra.",
                    "priority": "Alta" if margin_delta < 0 else "Media",
                }
            )
        promo = products["promo"]
        if promo["share_pct"] > promo["prior_share_pct"] + 5:
            findings.append(
                {
                    "title": "Mayor peso de promociones",
                    "evidence": (
                        f"Promociones: {_fmt_pct(promo['share_pct'], 1)} de las ventas "
                        f"(antes {_fmt_pct(promo['prior_share_pct'], 1)}), margen "
                        f"{_fmt_pct(promo['current']['margin_pct'])} vs. "
                        f"{_fmt_pct(promo['base_current']['margin_pct'])} no promocional"
                    ),
                    "risk": "Dilución de margen y canibalización de referencias base.",
                    "priority": "Alta",
                }
            )
        recurring = customers["stats"]["recurring"]
        if recurring["delta"] < 0:
            findings.append(
                {
                    "title": "La base recurrente se contrae",
                    "evidence": (
                        f"Clientes recurrentes: {_fmt_money(recurring['current_rev'])} vs. "
                        f"{_fmt_money(recurring['prior_rev'])} "
                        f"({_fmt_delta(recurring['current_rev'], recurring['prior_rev'])})"
                    ),
                    "risk": "El crecimiento depende de altas y reactivaciones.",
                    "priority": "Alta",
                }
            )
        return_delta = current["return_pct"] - prior["return_pct"]
        if return_delta > 0.2:
            findings.append(
                {
                    "title": "Devoluciones al alza",
                    "evidence": (
                        f"{_fmt_pct(current['return_pct'])} vs. {_fmt_pct(prior['return_pct'])} "
                        f"({_fmt_money(abs(current['return_rev']))})"
                    ),
                    "risk": "Costo logístico, margen y riesgo de fraude.",
                    "priority": "Alta" if return_delta > 0.5 else "Media",
                }
            )
        inv = inventory
        if inv.get("available"):
            value_delta = inv.get("value_delta_pct") or 0
            rev_delta = _delta_pct(current["rev"], prior["rev"]) or 0
            if value_delta > 0 and value_delta > rev_delta + 5:
                findings.append(
                    {
                        "title": "El inventario crece más que la venta",
                        "evidence": (
                            f"Inventario {_fmt_money(inv['total_value'])} "
                            f"({value_delta:+.1f}%) vs. ventas {rev_delta:+.1f}%; "
                            f"{inv['days']:.0f} días de costo"
                        ),
                        "risk": "Capital de trabajo y obsolescencia.",
                        "priority": "Alta",
                    }
                )
            over = inv["buckets"].get("gt6", {})
            if over.get("share_pct", 0) > 20:
                findings.append(
                    {
                        "title": "Inventario de baja rotación",
                        "evidence": (
                            f"{over['skus']} SKUs con >6 meses de cobertura: "
                            f"{_fmt_money(over['value'])} "
                            f"({_fmt_pct(over['share_pct'], 1)} del inventario)"
                        ),
                        "risk": "Obsolescencia y caja inmovilizada.",
                        "priority": "Media",
                    }
                )
            low = inv["buckets"].get("lt1", {})
            if low.get("skus", 0) >= 5:
                findings.append(
                    {
                        "title": "Riesgo de quiebre en alta rotación",
                        "evidence": (
                            f"{low['skus']} SKUs con <1 mes de cobertura: "
                            f"{_fmt_money(low['value'])}"
                        ),
                        "risk": "Pérdida de venta por falta de stock.",
                        "priority": "Alta" if low.get("skus", 0) >= 20 else "Media",
                    }
                )
        gap = products["master_gap"]
        if gap["share_pct"] >= 5:
            findings.append(
                {
                    "title": "Brecha de datos maestros",
                    "evidence": (
                        f"{gap['current']['skus']} SKUs vendidos sin maestro por "
                        f"{_fmt_money(gap['current']['rev'])} "
                        f"({_fmt_pct(gap['share_pct'], 1)} de las ventas)"
                    ),
                    "risk": "Reportes por rubro/proveedor imprecisos.",
                    "priority": "Media",
                }
            )
        top10 = customers["stats"]["top10_share_pct"]
        if top10 >= 20:
            findings.append(
                {
                    "title": "Concentración de clientes",
                    "evidence": f"Top 10 concentra {_fmt_pct(top10, 1)} de las ventas.",
                    "risk": "Dependencia de pocas cuentas.",
                    "priority": "Media",
                }
            )
        if not findings:
            findings.append(
                {
                    "title": "Sin alertas materiales",
                    "evidence": "Los indicadores principales se mantienen estables.",
                    "risk": "Monitorear la evolución mensual.",
                    "priority": "Baja",
                }
            )
        return findings

    # ------------------------------------------------------------------ build
    def build(self) -> Dict[str, Any]:
        cur = self._kpis(self.period["start"], self.period["end"])
        prev = self._kpis(self.period["prior_start"], self.period["prior_end"])
        company_cur = self._kpis(self.period["start"], self.period["end"], brand=False)
        company_prev = self._kpis(
            self.period["prior_start"], self.period["prior_end"], brand=False
        )
        annual = self._annual()
        monthly = self._monthly()
        warehouses = self._warehouses()
        branches = self._branches()
        rubros = self._rubros()
        products = self._products()
        customers = self._customers()
        vendors = self._vendors()
        returns = self._returns(cur, prev)
        inventory = self._inventory(products["items"], cur["cost"])
        findings = self._findings(cur, prev, warehouses, products, customers, inventory)
        projection = None
        if self.period["full_year"] and self.period["clamped"]:
            prior_full = next(
                (row for row in annual if row["year"] == self.period["prior_year"]),
                None,
            )
            run_rate = _safe_div(cur["rev"], self.period["days"]) * 365
            projection = {
                "run_rate": run_rate,
                "prior_full": _to_float(prior_full["rev"]) if prior_full else 0.0,
                "growth_pct": _delta_pct(
                    run_rate, _to_float(prior_full["rev"]) if prior_full else 0.0
                ),
                "target_end": self.period["requested_end"].isoformat(),
            }
        return {
            "status": "ok",
            "brand": self.brand,
            "brand_label": self.brand.title(),
            "year": self.year,
            "as_of": self.period["as_of"],
            "period": {
                "start": self.period["start"].isoformat(),
                "end": self.period["end"].isoformat(),
                "requested_start": self.period["requested_start"].isoformat(),
                "requested_end": self.period["requested_end"].isoformat(),
                "prior_start": self.period["prior_start"].isoformat(),
                "prior_end": self.period["prior_end"].isoformat(),
                "days": self.period["days"],
                "partial": self.period["partial"],
                "clamped": self.period["clamped"],
                "full_year": self.period["full_year"],
            },
            "kpis": {
                "current": cur,
                "prior": prev,
                "company_current": company_cur,
                "company_prior": company_prev,
            },
            "annual": annual,
            "monthly": monthly,
            "warehouses": warehouses,
            "branches": branches,
            "rubros": rubros,
            "products": products,
            "customers": customers,
            "vendors": vendors,
            "returns": returns,
            "inventory": inventory,
            "findings": findings,
            "projection": projection,
            "excluded_document_codes": list(self.excluded),
        }


def build_brand_report_result(
    *,
    brand: str,
    year: Optional[int] = None,
    as_of: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    fmt: str = "html",
    output_dir: Optional[Path] = None,
    top_n: int = 15,
    db: Optional[Database] = None,
) -> Dict[str, Any]:
    """Build and write a brand report; returns the API/CLI payload."""
    try:
        brand_name = normalize_brand(brand)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}

    fmt_norm = (fmt or "html").strip().lower()
    if fmt_norm not in SUPPORTED_FORMATS:
        return {
            "status": "error",
            "message": f"Formato inválido: {fmt!r} (use html o json).",
        }

    start_obj: Optional[date] = None
    end_obj: Optional[date] = None
    if start_date or end_date:
        if not start_date or not end_date:
            return {
                "status": "error",
                "message": "Indique la fecha inicial y la fecha final del rango.",
            }
        try:
            start_obj = validate_brand_as_of(start_date)
            end_obj = validate_brand_as_of(end_date)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}
        if start_obj > end_obj:
            return {
                "status": "error",
                "message": (
                    f"La fecha inicial ({start_date}) no puede ser posterior "
                    f"a la final ({end_date})."
                ),
            }

    report_year: Optional[int] = None
    if start_obj is None:
        try:
            report_year = int(year) if year is not None else None
        except (TypeError, ValueError):
            return {"status": "error", "message": f"Año inválido: {year!r}"}

    as_of_date: Optional[date] = None
    if as_of and start_obj is None:
        try:
            as_of_date = validate_brand_as_of(as_of)
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}

    try:
        builder = BrandReportBuilder(
            brand=brand_name,
            year=report_year,
            as_of=as_of_date,
            start_date=start_obj,
            end_date=end_obj,
            db=db,
            top_n=top_n,
        )
        report = builder.build()
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception:  # noqa: BLE001 - surface DB/query errors to UI
        logger.exception("brand report build failed brand=%s", brand_name)
        return {
            "status": "error",
            "message": "Error generando informe de marca. Revise los logs.",
        }

    current_kpi = report["kpis"]["current"]
    prior_kpi = report["kpis"]["prior"]
    if not current_kpi["lines"] and not prior_kpi["lines"]:
        return {
            "status": "error",
            "message": (
                f"Sin ventas para la marca {brand_name} en el rango solicitado "
                "ni en el año anterior."
            ),
        }

    period = report["period"]
    out_dir = Path(output_dir) if output_dir else Config.ensure_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / brand_report_basename(
        brand_name, period["requested_start"], period["requested_end"], fmt_norm
    )
    try:
        if fmt_norm == "json":
            path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
        else:
            from business_analyzer.reports.brand_html import render_html

            path.write_text(render_html(report), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "message": f"Error escribiendo informe ({fmt_norm}): {exc}",
        }

    cur = report["kpis"]["current"]
    range_label = f"{period['requested_start']} a {period['requested_end']}"
    data_note = f" (datos al {period['end']})" if period.get("clamped") else ""
    return {
        "status": "success",
        "message": (
            f"Informe de marca {brand_name} {range_label} listo{data_note}: "
            f"{_fmt_money(cur['rev'])}, margen {_fmt_pct(cur['margin_pct'])}."
        ),
        "brand": brand_name,
        "year": report["year"],
        "start_date": period["requested_start"],
        "end_date": period["requested_end"],
        "data_start": period["start"],
        "data_end": period["end"],
        "as_of": period["end"],
        "format": fmt_norm,
        "path": str(path),
        "summary": cur,
        "report": report,
    }


def list_brands(
    *, year: Optional[int] = None, limit: int = 250, db: Optional[Database] = None
) -> Dict[str, Any]:
    """List brands with sales for the brand dropdown, ordered by revenue."""
    cache_key = (year, limit)
    if db is None:
        cached = _BRANDS_CACHE.get(cache_key)
        if cached and time.monotonic() - cached[0] < _BRANDS_CACHE_TTL:
            return cached[1]
    database = db or get_database()
    db_name = Database.validate_sql_identifier(Config.DB_NAME, "database")
    table_name = Database.validate_sql_identifier(Config.DB_TABLE, "table")
    base = (
        f"[{db_name}].[dbo].[{table_name}] bd "
        f"LEFT JOIN [{db_name}].[dbo].[productos_adicional] pa "
        "ON bd.ArticulosCodigo = pa.producto_codigo"
    )
    excluded = tuple(Config.EXCLUDED_DOCUMENT_CODES)
    placeholders = ",".join(["%s"] * len(excluded))
    max_rows = database.execute_query(f"SELECT MAX(bd.Fecha) AS max_date FROM {base}")
    max_value = max_rows[0].get("max_date") if max_rows else None
    if isinstance(max_value, date):
        latest = max_value
    elif max_value:
        latest = date.fromisoformat(str(max_value)[:10])
    else:
        latest = date.today()
    target_year = int(year) if year is not None else latest.year
    sql = f"""
        SELECT LTRIM(RTRIM(pa.producto_marca)) AS brand,
            COUNT(DISTINCT bd.ArticulosCodigo) AS skus,
            SUM(bd.TotalSinIva) AS rev
        FROM {base}
        WHERE bd.ano = %s
          AND bd.DocumentosCodigo NOT IN ({placeholders})
          AND NULLIF(LTRIM(RTRIM(pa.producto_marca)), '') IS NOT NULL
        GROUP BY LTRIM(RTRIM(pa.producto_marca))
        HAVING SUM(bd.TotalSinIva) > 0
        ORDER BY SUM(bd.TotalSinIva) DESC
    """
    rows = database.execute_query(sql, (target_year,) + excluded)
    seen = set()
    brands: List[Dict[str, Any]] = []
    for row in rows:
        value = " ".join(str(row.get("brand") or "").split())
        if not value:
            continue
        key = value.upper()
        if key in seen:
            continue
        seen.add(key)
        brands.append(
            {
                "value": value,
                "label": value.title(),
                "skus": _to_int(row.get("skus")),
                "revenue": _to_float(row.get("rev")),
            }
        )
        if len(brands) >= max(1, int(limit)):
            break
    default = (
        "SIKA"
        if any(item["value"].upper() == "SIKA" for item in brands)
        else (brands[0]["value"] if brands else "SIKA")
    )
    payload = {
        "brands": brands,
        "default_brand": default,
        "year": target_year,
        "max_date": latest.isoformat(),
    }
    if db is None:
        _BRANDS_CACHE[cache_key] = (time.monotonic(), payload)
    return payload


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Informe de marca: período actual vs. mismo período del año anterior."
    )
    parser.add_argument("--brand", required=True, help="Marca (ej. SIKA, PINTUCO)")
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument(
        "--start-date",
        default=None,
        help="Fecha inicial del rango YYYY-MM-DD (ej. 2026-01-01).",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="Fecha final del rango YYYY-MM-DD (ej. 2026-12-31).",
    )
    parser.add_argument(
        "--as-of",
        default=None,
        help="Fecha de corte YYYY-MM-DD (alternativa a --start/--end).",
    )
    parser.add_argument("--format", choices=SUPPORTED_FORMATS, default="html")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--top", type=int, default=15)
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    result = build_brand_report_result(
        brand=args.brand,
        year=args.year,
        as_of=args.as_of,
        start_date=args.start_date,
        end_date=args.end_date,
        fmt=args.format,
        output_dir=Path(args.output_dir) if args.output_dir else None,
        top_n=args.top,
    )
    if result.get("status") == "error":
        print(result.get("message", "Error"), file=sys.stderr)
        return 1
    print(result["message"])
    print(f"Archivo: {result['path']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
