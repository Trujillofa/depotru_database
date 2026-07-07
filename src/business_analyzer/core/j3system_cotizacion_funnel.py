"""J3System quote-to-invoice funnel SQL builders.

Linkage rule (do **not** join ``InvCotizaCab`` to ``InvVentas`` on ``VentaID`` alone —
that ID is reused across document types). The authoritative bridge is::

    InvVentasTotales.NumeroCotiza = 'CT-' + CAST(InvCotizaCab.NumeroDocumento AS VARCHAR)

Invoice matches must satisfy ``v.Fecha >= c.Fecha`` and fall within
``@max_conversion_days`` (default 180) to ignore stale cross-year collisions.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_sales_warehouse import (
    _validate_period_date,
    qualified_j3_table,
)

DEFAULT_MAX_CONVERSION_DAYS = 180

EXCLUDED_INVOICE_DOC_CODES: Tuple[str, ...] = ("XY", "AS", "TS", "YX", "ISC")

COTIZACION_DOC_CODE = "CT"


def numero_cotiza_from_documento_sql(cotiza_alias: str = "c") -> str:
    """SQL expression: ``CT-{NumeroDocumento}`` for ``InvVentasTotales`` join."""
    return (
        f"'CT-' + CAST(CAST({cotiza_alias}.NumeroDocumento AS BIGINT) AS VARCHAR(20))"
    )


def _excluded_invoice_docs_sql() -> str:
    codes = ", ".join(f"'{code}'" for code in EXCLUDED_INVOICE_DOC_CODES)
    return codes


def _cotizaciones_cte(
    *,
    start_date: str,
    end_date: str,
    j3_database: Optional[str] = None,
) -> str:
    inv_cotiza = qualified_j3_table("InvCotizaCab", j3_database)
    adm_docs = qualified_j3_table("AdmDocumentos", j3_database)
    start = _validate_period_date(start_date, "start_date")
    end = _validate_period_date(end_date, "end_date")
    return f"""
cotizaciones AS (
    SELECT
        c.VentaID,
        c.NumeroDocumento,
        c.Fecha,
        c.TercerosID,
        c.VendedorID
    FROM {inv_cotiza} c
    JOIN {adm_docs} dc
      ON dc.DocumentosID = c.DocumentosID
     AND dc.DocumentosCodigo = '{COTIZACION_DOC_CODE}'
    WHERE c.Fecha BETWEEN '{start}' AND '{end}'
)""".strip()


def _conversiones_cte(
    *,
    max_conversion_days: int = DEFAULT_MAX_CONVERSION_DAYS,
    j3_database: Optional[str] = None,
) -> str:
    inv_totales = qualified_j3_table("InvVentasTotales", j3_database)
    inv_ventas = qualified_j3_table("InvVentas", j3_database)
    adm_docs = qualified_j3_table("AdmDocumentos", j3_database)
    max_days = int(max_conversion_days)
    if max_days <= 0:
        raise ValueError("max_conversion_days must be positive")
    numero_cotiza = numero_cotiza_from_documento_sql("c")
    excluded = _excluded_invoice_docs_sql()
    return f"""
conversiones AS (
    SELECT
        c.VentaID,
        MIN(v.Fecha) AS primera_factura_fecha,
        COUNT(DISTINCT v.VentaID) AS num_facturas
    FROM cotizaciones c
    JOIN {inv_totales} t ON t.NumeroCotiza = {numero_cotiza}
    JOIN {inv_ventas} v ON v.VentaID = t.VentaID
    JOIN {adm_docs} dv ON dv.DocumentosID = v.DocumentosID
    WHERE dv.DocumentosCodigo NOT IN ({excluded})
      AND v.Fecha >= c.Fecha
      AND DATEDIFF(DAY, c.Fecha, v.Fecha) <= {max_days}
    GROUP BY c.VentaID
)""".strip()


def build_cotizacion_funnel_summary_sql(
    start_date: str,
    end_date: str,
    *,
    max_conversion_days: int = DEFAULT_MAX_CONVERSION_DAYS,
    j3_database: Optional[str] = None,
) -> str:
    """Period-level funnel KPIs: quotes, conversions, rate, avg days."""
    cotizaciones = _cotizaciones_cte(
        start_date=start_date, end_date=end_date, j3_database=j3_database
    )
    conversiones = _conversiones_cte(
        max_conversion_days=max_conversion_days, j3_database=j3_database
    )
    start = _validate_period_date(start_date, "start_date")
    end = _validate_period_date(end_date, "end_date")
    return f"""
WITH {cotizaciones},
{conversiones}
SELECT
    '{start}' AS Fecha_Inicio,
    '{end}' AS Fecha_Fin,
    COUNT(*) AS Cotizaciones,
    SUM(CASE WHEN cv.VentaID IS NOT NULL THEN 1 ELSE 0 END) AS Convertidas,
    SUM(CASE WHEN cv.VentaID IS NULL THEN 1 ELSE 0 END) AS Perdidas,
    CASE
        WHEN COUNT(*) = 0 THEN 0
        ELSE SUM(CASE WHEN cv.VentaID IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
    END AS Tasa_Conversion_Pct,
    CASE
        WHEN SUM(CASE WHEN cv.VentaID IS NOT NULL THEN 1 ELSE 0 END) = 0 THEN 0
        ELSE AVG(
            CASE
                WHEN cv.VentaID IS NOT NULL
                THEN CAST(DATEDIFF(DAY, c.Fecha, cv.primera_factura_fecha) AS FLOAT)
            END
        )
    END AS Dias_Promedio_Conversion,
    SUM(CASE WHEN cv.num_facturas > 1 THEN 1 ELSE 0 END) AS Cotizaciones_Multifactura
FROM cotizaciones c
LEFT JOIN conversiones cv ON cv.VentaID = c.VentaID
""".strip()


def build_cotizacion_funnel_by_vendor_sql(
    start_date: str,
    end_date: str,
    *,
    max_conversion_days: int = DEFAULT_MAX_CONVERSION_DAYS,
    j3_database: Optional[str] = None,
) -> str:
    """Funnel metrics grouped by salesperson (vendedor)."""
    cotizaciones = _cotizaciones_cte(
        start_date=start_date, end_date=end_date, j3_database=j3_database
    )
    conversiones = _conversiones_cte(
        max_conversion_days=max_conversion_days, j3_database=j3_database
    )
    adm_vendedor = qualified_j3_table("AdmVendedor", j3_database)
    return f"""
WITH {cotizaciones},
{conversiones}
SELECT
    ISNULL(v.VendedorCodigo, CAST(c.VendedorID AS VARCHAR(20))) AS Vendedor_Codigo,
    ISNULL(NULLIF(LTRIM(RTRIM(v.VendedorNombre)), ''), 'SIN_NOMBRE') AS Vendedor_Nombre,
    COUNT(*) AS Cotizaciones,
    SUM(CASE WHEN cv.VentaID IS NOT NULL THEN 1 ELSE 0 END) AS Convertidas,
    SUM(CASE WHEN cv.VentaID IS NULL THEN 1 ELSE 0 END) AS Perdidas,
    CASE
        WHEN COUNT(*) = 0 THEN 0
        ELSE SUM(CASE WHEN cv.VentaID IS NOT NULL THEN 1 ELSE 0 END) * 100.0 / COUNT(*)
    END AS Tasa_Conversion_Pct,
    CASE
        WHEN SUM(CASE WHEN cv.VentaID IS NOT NULL THEN 1 ELSE 0 END) = 0 THEN 0
        ELSE AVG(
            CASE
                WHEN cv.VentaID IS NOT NULL
                THEN CAST(DATEDIFF(DAY, c.Fecha, cv.primera_factura_fecha) AS FLOAT)
            END
        )
    END AS Dias_Promedio_Conversion
FROM cotizaciones c
LEFT JOIN conversiones cv ON cv.VentaID = c.VentaID
LEFT JOIN {adm_vendedor} v ON v.VendedorID = c.VendedorID
GROUP BY
    ISNULL(v.VendedorCodigo, CAST(c.VendedorID AS VARCHAR(20))),
    ISNULL(NULLIF(LTRIM(RTRIM(v.VendedorNombre)), ''), 'SIN_NOMBRE')
ORDER BY Cotizaciones DESC
""".strip()


def build_cotizacion_funnel_kpi_pack_sql(
    start_date: str,
    end_date: str,
    *,
    max_conversion_days: int = DEFAULT_MAX_CONVERSION_DAYS,
    j3_database: Optional[str] = None,
) -> str:
    """KPI pack Q12: vendor funnel using cross-database ``J3System.dbo`` refs."""
    return build_cotizacion_funnel_by_vendor_sql(
        start_date,
        end_date,
        max_conversion_days=max_conversion_days,
        j3_database=j3_database,
    )


def validate_funnel_sql_period(start_date: str, end_date: str) -> None:
    """Raise if period strings are not YYYY-MM-DD."""
    _validate_period_date(start_date, "start_date")
    _validate_period_date(end_date, "end_date")
    if start_date > end_date:
        raise ValueError(f"start_date {start_date!r} is after end_date {end_date!r}")


def parse_numero_cotiza(value: object) -> Optional[int]:
    """Parse ``CT-12345`` or bare document number to int."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.upper().startswith("CT-"):
        text = text[3:]
    if re.fullmatch(r"\d+", text):
        return int(text)
    return None


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def funnel_summary_from_vendor_rows(
    rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Aggregate vendor-level funnel rows into period summary KPIs."""
    total_cot = sum(_as_int(r.get("Cotizaciones")) for r in rows)
    total_conv = sum(_as_int(r.get("Convertidas")) for r in rows)
    total_lost = sum(_as_int(r.get("Perdidas")) for r in rows)

    weighted_days = 0.0
    for row in rows:
        conv = _as_int(row.get("Convertidas"))
        if conv:
            weighted_days += _as_float(row.get("Dias_Promedio_Conversion")) * conv

    return {
        "Cotizaciones": total_cot,
        "Convertidas": total_conv,
        "Perdidas": total_lost,
        "Tasa_Conversion_Pct": (total_conv * 100.0 / total_cot) if total_cot else 0.0,
        "Dias_Promedio_Conversion": (weighted_days / total_conv) if total_conv else 0.0,
    }


def top_lost_vendors(
    rows: Sequence[Mapping[str, Any]],
    *,
    n: int = 5,
) -> List[Dict[str, Any]]:
    """Vendors with most lost (unconverted) quotes in the period."""
    ranked = sorted(rows, key=lambda r: _as_int(r.get("Perdidas")), reverse=True)
    return [dict(row) for row in ranked[:n]]


def low_conversion_vendors(
    rows: Sequence[Mapping[str, Any]],
    *,
    min_quotes: int = 10,
    max_rate_pct: float = 20.0,
    n: int = 5,
) -> List[Dict[str, Any]]:
    """Vendors below conversion threshold with enough quote volume."""
    filtered = [
        row
        for row in rows
        if _as_int(row.get("Cotizaciones")) >= min_quotes
        and _as_float(row.get("Tasa_Conversion_Pct")) < max_rate_pct
    ]
    ranked = sorted(filtered, key=lambda r: _as_float(r.get("Tasa_Conversion_Pct")))
    return [dict(row) for row in ranked[:n]]


class CotizacionFunnelRunner:
    """Execute J3System funnel SQL and return structured results."""

    def __init__(
        self,
        db: Optional[Database] = None,
        *,
        j3_database: Optional[str] = None,
        max_conversion_days: int = DEFAULT_MAX_CONVERSION_DAYS,
    ) -> None:
        self.db = db or Database()
        self.j3_database = j3_database
        self.max_conversion_days = max_conversion_days

    def _execute_j3_query(self, sql: str) -> List[Dict[str, Any]]:
        conn = self.db.get_j3system_connection()
        try:
            cursor = conn.cursor(as_dict=True)
            cursor.execute(sql)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def fetch_summary(
        self,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        validate_funnel_sql_period(start_date, end_date)
        sql = build_cotizacion_funnel_summary_sql(
            start_date,
            end_date,
            max_conversion_days=self.max_conversion_days,
            j3_database=self.j3_database,
        )
        rows = self._execute_j3_query(sql)
        return dict(rows[0]) if rows else {}

    def fetch_by_vendor(
        self,
        start_date: str,
        end_date: str,
    ) -> List[Dict[str, Any]]:
        validate_funnel_sql_period(start_date, end_date)
        sql = build_cotizacion_funnel_by_vendor_sql(
            start_date,
            end_date,
            max_conversion_days=self.max_conversion_days,
            j3_database=self.j3_database,
        )
        return self._execute_j3_query(sql)

    def build_report(
        self,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        vendor_rows = self.fetch_by_vendor(start_date, end_date)
        summary = self.fetch_summary(start_date, end_date)
        if not summary and vendor_rows:
            summary = funnel_summary_from_vendor_rows(vendor_rows)
        return {
            "period": {"start": start_date, "end": end_date},
            "summary": summary,
            "by_vendor": vendor_rows,
            "top_lost_vendors": top_lost_vendors(vendor_rows),
            "low_conversion_vendors": low_conversion_vendors(vendor_rows),
        }
