"""ERP vs BI returns reconciliation (InvDevolucionVentas* vs banco_datos).

**ERP source:** ``InvDevolucionVentas`` + ``InvDevolucionVentasDetalle`` (J3System).
**BI source:** ``banco_datos`` return lines — negative ``Cantidad`` and/or document
codes ``DVE``, ``DVD``, ``DDD``, ``DDT``.

Category mapping for ERP lines uses the latest ``categoria`` per ``ArticulosCodigo``
from ``banco_datos`` (same pattern as cross-db inventory).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Mapping, Optional, Sequence, cast

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_sales_warehouse import (
    _validate_period_date,
    qualified_j3_table,
)

DEFAULT_TOP_N_GAPS = 15

EXCLUDED_DOC_CODES: tuple[str, ...] = ("XY", "AS", "TS", "YX", "ISC")
RETURN_DOC_CODES: tuple[str, ...] = ("DVE", "DVD", "DDD", "DDT")


def qualified_sb_table(table: str, sb_database: Optional[str] = None) -> str:
    """Return a validated ``SmartBusiness.dbo.<table>`` reference."""
    db_name = sb_database or os.getenv("DB_NAME", "SmartBusiness")
    validated_db = Database.validate_sql_identifier(db_name, "smartbusiness database")
    validated_table = Database.validate_sql_identifier(table, "table")
    return f"{validated_db}.dbo.{validated_table}"


def _excluded_docs_sql() -> str:
    return ", ".join(f"'{code}'" for code in EXCLUDED_DOC_CODES)


def _return_docs_sql() -> str:
    return ", ".join(f"'{code}'" for code in RETURN_DOC_CODES)


def bi_returns_filter_sql(alias: str = "") -> str:
    """WHERE fragment: BI return lines (negative qty or return doc codes)."""
    prefix = f"{alias}." if alias else ""
    excluded = _excluded_docs_sql()
    returns = _return_docs_sql()
    return (
        f"{prefix}DocumentosCodigo NOT IN ({excluded}) "
        f"AND ({prefix}Cantidad < 0 OR {prefix}DocumentosCodigo IN ({returns}))"
    )


def _categoria_lookup_cte(sb_database: Optional[str] = None) -> str:
    banco = qualified_sb_table("banco_datos", sb_database)
    return f"""
categoria_lookup AS (
    SELECT
        ArticulosCodigo,
        MAX(categoria) AS categoria
    FROM {banco}
    GROUP BY ArticulosCodigo
)""".strip()


def _erp_devoluciones_cte(
    *,
    start_date: str,
    end_date: str,
    j3_database: Optional[str] = None,
    sb_database: Optional[str] = None,
) -> str:
    devolucion = qualified_j3_table("InvDevolucionVentas", j3_database)
    detalle = qualified_j3_table("InvDevolucionVentasDetalle", j3_database)
    adm_docs = qualified_j3_table("AdmDocumentos", j3_database)
    articulos = qualified_j3_table("AdmArticulos", j3_database)
    categoria_lookup = _categoria_lookup_cte(sb_database)
    start = _validate_period_date(start_date, "start_date")
    end = _validate_period_date(end_date, "end_date")
    excluded = _excluded_docs_sql()
    return f"""
{categoria_lookup},
erp_devoluciones AS (
    SELECT
        ISNULL(cl.categoria, 'SIN_CATEGORIA') AS Categoria,
        dc.DocumentosCodigo,
        det.Cantidad AS Unidades,
        det.VentaSinIva AS Valor_Sin_Iva,
        det.VentaSinIva - det.ValorCosto AS Impacto_Margen
    FROM {devolucion} d
    JOIN {detalle} det ON det.DevolucionID = d.DevolucionID
    JOIN {adm_docs} dc ON dc.DocumentosID = d.DocumentosID
    JOIN {articulos} a ON a.ArticulosID = det.ArticulosID
    LEFT JOIN categoria_lookup cl ON cl.ArticulosCodigo = a.ArticulosCodigo
    WHERE d.Fecha BETWEEN '{start}' AND '{end}'
      AND dc.DocumentosCodigo NOT IN ({excluded})
)""".strip()


def _bi_devoluciones_cte(
    *,
    start_date: str,
    end_date: str,
    sb_database: Optional[str] = None,
) -> str:
    banco = qualified_sb_table("banco_datos", sb_database)
    start = _validate_period_date(start_date, "start_date")
    end = _validate_period_date(end_date, "end_date")
    bi_filter = bi_returns_filter_sql()
    return f"""
bi_devoluciones AS (
    SELECT
        ISNULL(categoria, 'SIN_CATEGORIA') AS Categoria,
        DocumentosCodigo,
        ABS(Cantidad) AS Unidades,
        ABS(TotalSinIva) AS Valor_Sin_Iva,
        ABS(TotalSinIva - ValorCosto) AS Impacto_Margen
    FROM {banco}
    WHERE Fecha BETWEEN '{start}' AND '{end}'
      AND {bi_filter}
)""".strip()


def _ventas_brutas_cte(
    *,
    start_date: str,
    end_date: str,
    sb_database: Optional[str] = None,
) -> str:
    banco = qualified_sb_table("banco_datos", sb_database)
    start = _validate_period_date(start_date, "start_date")
    end = _validate_period_date(end_date, "end_date")
    excluded = _excluded_docs_sql()
    return f"""
ventas_brutas AS (
    SELECT
        ISNULL(categoria, 'SIN_CATEGORIA') AS Categoria,
        SUM(Cantidad) AS Unidades_Vendidas
    FROM {banco}
    WHERE Fecha BETWEEN '{start}' AND '{end}'
      AND DocumentosCodigo NOT IN ({excluded})
      AND Cantidad > 0
    GROUP BY ISNULL(categoria, 'SIN_CATEGORIA')
)""".strip()


def build_devoluciones_summary_sql(
    start_date: str,
    end_date: str,
    *,
    j3_database: Optional[str] = None,
    sb_database: Optional[str] = None,
) -> str:
    """Period-level ERP vs BI returns totals and reconciliation gap."""
    erp = _erp_devoluciones_cte(
        start_date=start_date,
        end_date=end_date,
        j3_database=j3_database,
        sb_database=sb_database,
    )
    bi = _bi_devoluciones_cte(
        start_date=start_date, end_date=end_date, sb_database=sb_database
    )
    start = _validate_period_date(start_date, "start_date")
    end = _validate_period_date(end_date, "end_date")
    return f"""
WITH {erp},
{bi}
SELECT
    '{start}' AS Fecha_Inicio,
    '{end}' AS Fecha_Fin,
    (SELECT SUM(Unidades) FROM erp_devoluciones) AS Unidades_ERP,
    (SELECT SUM(Unidades) FROM bi_devoluciones) AS Unidades_BI,
    (SELECT SUM(Unidades) FROM bi_devoluciones)
        - (SELECT SUM(Unidades) FROM erp_devoluciones) AS Diferencia_Unidades,
    CASE
        WHEN (SELECT SUM(Unidades) FROM erp_devoluciones) = 0 THEN
            CASE WHEN (SELECT SUM(Unidades) FROM bi_devoluciones) = 0 THEN 100 ELSE 0 END
        ELSE 100.0 - ABS(
            (SELECT SUM(Unidades) FROM bi_devoluciones)
            - (SELECT SUM(Unidades) FROM erp_devoluciones)
        ) * 100.0 / (SELECT SUM(Unidades) FROM erp_devoluciones)
    END AS Conciliacion_Pct,
    (SELECT SUM(Valor_Sin_Iva) FROM erp_devoluciones) AS Valor_Sin_Iva_ERP,
    (SELECT SUM(Valor_Sin_Iva) FROM bi_devoluciones) AS Valor_Sin_Iva_BI,
    (SELECT SUM(Impacto_Margen) FROM erp_devoluciones) AS Impacto_Margen_ERP,
    (SELECT SUM(Impacto_Margen) FROM bi_devoluciones) AS Impacto_Margen_BI;
""".strip()


def build_devoluciones_by_category_sql(
    start_date: str,
    end_date: str,
    *,
    j3_database: Optional[str] = None,
    sb_database: Optional[str] = None,
) -> str:
    """Category-level reconciliation: ERP vs BI units, gap, validated return rate."""
    erp = _erp_devoluciones_cte(
        start_date=start_date,
        end_date=end_date,
        j3_database=j3_database,
        sb_database=sb_database,
    )
    bi = _bi_devoluciones_cte(
        start_date=start_date, end_date=end_date, sb_database=sb_database
    )
    ventas = _ventas_brutas_cte(
        start_date=start_date, end_date=end_date, sb_database=sb_database
    )
    _validate_period_date(start_date, "start_date")
    _validate_period_date(end_date, "end_date")
    return f"""
WITH {erp},
{bi},
{ventas},
erp_cat AS (
    SELECT
        Categoria,
        SUM(Unidades) AS Unidades_ERP,
        SUM(Valor_Sin_Iva) AS Valor_Sin_Iva_ERP,
        SUM(Impacto_Margen) AS Impacto_Margen_ERP
    FROM erp_devoluciones
    GROUP BY Categoria
),
bi_cat AS (
    SELECT
        Categoria,
        SUM(Unidades) AS Unidades_BI,
        SUM(Valor_Sin_Iva) AS Valor_Sin_Iva_BI,
        SUM(Impacto_Margen) AS Impacto_Margen_BI
    FROM bi_devoluciones
    GROUP BY Categoria
)
SELECT
    COALESCE(e.Categoria, b.Categoria) AS Categoria,
    ISNULL(e.Unidades_ERP, 0) AS Unidades_ERP,
    ISNULL(b.Unidades_BI, 0) AS Unidades_BI,
    ISNULL(b.Unidades_BI, 0) - ISNULL(e.Unidades_ERP, 0) AS Diferencia_Unidades,
    CASE
        WHEN ISNULL(e.Unidades_ERP, 0) = 0 THEN
            CASE WHEN ISNULL(b.Unidades_BI, 0) = 0 THEN 0 ELSE 100 END
        ELSE ABS(ISNULL(b.Unidades_BI, 0) - ISNULL(e.Unidades_ERP, 0))
             * 100.0 / e.Unidades_ERP
    END AS Diferencia_Pct,
    ISNULL(v.Unidades_Vendidas, 0) AS Unidades_Vendidas,
    CASE
        WHEN ISNULL(v.Unidades_Vendidas, 0) = 0 THEN 0
        ELSE ISNULL(e.Unidades_ERP, 0) * 100.0 / v.Unidades_Vendidas
    END AS Tasa_Devolucion_Validada_Pct,
    ISNULL(b.Impacto_Margen_BI, 0) AS Impacto_Margen_BI
FROM erp_cat e
FULL OUTER JOIN bi_cat b ON b.Categoria = e.Categoria
LEFT JOIN ventas_brutas v ON v.Categoria = COALESCE(e.Categoria, b.Categoria)
ORDER BY Diferencia_Unidades DESC, Impacto_Margen_BI DESC;
""".strip()


def build_devoluciones_by_documento_sql(
    start_date: str,
    end_date: str,
    *,
    j3_database: Optional[str] = None,
    sb_database: Optional[str] = None,
) -> str:
    """Reconciliation by return document code (DVE, DVD, etc.)."""
    erp = _erp_devoluciones_cte(
        start_date=start_date,
        end_date=end_date,
        j3_database=j3_database,
        sb_database=sb_database,
    )
    bi = _bi_devoluciones_cte(
        start_date=start_date, end_date=end_date, sb_database=sb_database
    )
    _validate_period_date(start_date, "start_date")
    _validate_period_date(end_date, "end_date")
    return f"""
WITH {erp},
{bi},
erp_doc AS (
    SELECT DocumentosCodigo, SUM(Unidades) AS Unidades_ERP
    FROM erp_devoluciones
    GROUP BY DocumentosCodigo
),
bi_doc AS (
    SELECT DocumentosCodigo, SUM(Unidades) AS Unidades_BI
    FROM bi_devoluciones
    GROUP BY DocumentosCodigo
)
SELECT
    COALESCE(e.DocumentosCodigo, b.DocumentosCodigo) AS DocumentosCodigo,
    ISNULL(e.Unidades_ERP, 0) AS Unidades_ERP,
    ISNULL(b.Unidades_BI, 0) AS Unidades_BI,
    ISNULL(b.Unidades_BI, 0) - ISNULL(e.Unidades_ERP, 0) AS Diferencia_Unidades
FROM erp_doc e
FULL OUTER JOIN bi_doc b ON b.DocumentosCodigo = e.DocumentosCodigo
ORDER BY Diferencia_Unidades DESC, Unidades_ERP DESC;
""".strip()


def validate_devoluciones_sql_period(start_date: str, end_date: str) -> None:
    """Raise if period strings are invalid or reversed."""
    _validate_period_date(start_date, "start_date")
    _validate_period_date(end_date, "end_date")
    if start_date > end_date:
        raise ValueError(f"start_date {start_date!r} is after end_date {end_date!r}")


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


def conciliacion_summary_from_category_rows(
    rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Aggregate category reconciliation rows into period KPIs."""
    erp_total = sum(_as_float(r.get("Unidades_ERP")) for r in rows)
    bi_total = sum(_as_float(r.get("Unidades_BI")) for r in rows)
    diff = bi_total - erp_total
    sold = sum(_as_float(r.get("Unidades_Vendidas")) for r in rows)
    margin_impact = sum(_as_float(r.get("Impacto_Margen_BI")) for r in rows)
    gaps = sum(1 for r in rows if abs(_as_float(r.get("Diferencia_Unidades"))) > 0.001)

    if erp_total == 0:
        conciliacion = 100.0 if bi_total == 0 else 0.0
    else:
        conciliacion = 100.0 - abs(diff) * 100.0 / erp_total

    return {
        "Unidades_ERP": erp_total,
        "Unidades_BI": bi_total,
        "Diferencia_Unidades": diff,
        "Conciliacion_Pct": conciliacion,
        "Categorias_Con_Diferencia": gaps,
        "Tasa_Devolucion_Validada_Pct": ((erp_total * 100.0 / sold) if sold else 0.0),
        "Impacto_Margen_BI": margin_impact,
    }


def top_reconciliation_gaps(
    rows: Sequence[Mapping[str, Any]],
    *,
    n: int = DEFAULT_TOP_N_GAPS,
) -> List[Dict[str, Any]]:
    """Categories with largest absolute unit gap."""
    ranked = sorted(
        rows,
        key=lambda r: abs(_as_float(r.get("Diferencia_Unidades"))),
        reverse=True,
    )
    return [
        dict(row) for row in ranked[:n] if _as_float(row.get("Diferencia_Unidades"))
    ]


def top_margin_erosion_categories(
    rows: Sequence[Mapping[str, Any]],
    *,
    n: int = 5,
) -> List[Dict[str, Any]]:
    """Categories with highest return margin impact (BI)."""
    ranked = sorted(
        rows, key=lambda r: _as_float(r.get("Impacto_Margen_BI")), reverse=True
    )
    return [dict(row) for row in ranked[:n]]


class DevolucionesConciliacionRunner:
    """Execute cross-database returns reconciliation SQL."""

    def __init__(
        self,
        db: Optional[Database] = None,
        *,
        j3_database: Optional[str] = None,
        sb_database: Optional[str] = None,
    ) -> None:
        self.db = db or Database()
        self.j3_database = j3_database
        self.sb_database = sb_database

    def _execute_query(self, sql: str) -> List[Dict[str, Any]]:
        self.db.connect()
        rows = cast(List[Dict[str, Any]], self.db.execute_query(sql))
        return [dict(row) for row in rows]

    def fetch_summary(self, start_date: str, end_date: str) -> Dict[str, Any]:
        validate_devoluciones_sql_period(start_date, end_date)
        sql = build_devoluciones_summary_sql(
            start_date,
            end_date,
            j3_database=self.j3_database,
            sb_database=self.sb_database,
        )
        rows = self._execute_query(sql)
        return dict(rows[0]) if rows else {}

    def fetch_by_category(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        validate_devoluciones_sql_period(start_date, end_date)
        sql = build_devoluciones_by_category_sql(
            start_date,
            end_date,
            j3_database=self.j3_database,
            sb_database=self.sb_database,
        )
        return self._execute_query(sql)

    def fetch_by_documento(
        self, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        validate_devoluciones_sql_period(start_date, end_date)
        sql = build_devoluciones_by_documento_sql(
            start_date,
            end_date,
            j3_database=self.j3_database,
            sb_database=self.sb_database,
        )
        return self._execute_query(sql)

    def build_report(self, start_date: str, end_date: str) -> Dict[str, Any]:
        by_category = self.fetch_by_category(start_date, end_date)
        summary = self.fetch_summary(start_date, end_date)
        if not summary and by_category:
            summary = conciliacion_summary_from_category_rows(by_category)
        return {
            "period": {"start": start_date, "end": end_date},
            "summary": summary,
            "by_category": by_category,
            "by_documento": self.fetch_by_documento(start_date, end_date),
            "top_gaps": top_reconciliation_gaps(by_category),
            "top_margin_erosion": top_margin_erosion_categories(by_category),
        }
