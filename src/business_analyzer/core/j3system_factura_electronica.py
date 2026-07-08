"""J3System electronic invoice (DIAN) compliance SQL builders.

``InvEstadoFacturaElectronica`` tracks e-invoice submission status per document.

**Accepted:** ``Codigo = '200'`` AND ``Enviado = 1`` AND non-empty ``Cufe``.
**Rejected:** anything else in the filtered period.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from business_analyzer.core.database import Database
from business_analyzer.core.j3system_sales_warehouse import (
    _validate_period_date,
    qualified_j3_table,
)

DEFAULT_TOP_N_REJECTIONS = 15

EXCLUDED_DOC_CODES: tuple[str, ...] = ("XY", "AS", "TS", "YX", "ISC")
SUCCESS_CODIGO = "200"


def _excluded_docs_sql() -> str:
    return ", ".join(f"'{code}'" for code in EXCLUDED_DOC_CODES)


def is_factura_aceptada_sql(
    *,
    codigo_col: str = "fe.Codigo",
    enviado_col: str = "fe.Enviado",
    cufe_col: str = "fe.Cufe",
) -> str:
    """SQL CASE expression: 1 when DIAN accepted the e-invoice."""
    return f"""CASE
        WHEN {codigo_col} = '{SUCCESS_CODIGO}'
         AND {enviado_col} = 1
         AND LEN(ISNULL({cufe_col}, '')) > 0
        THEN 1
        ELSE 0
    END"""


def _fe_filtrada_cte(
    *,
    start_date: str,
    end_date: str,
    j3_database: Optional[str] = None,
) -> str:
    estado = qualified_j3_table("InvEstadoFacturaElectronica", j3_database)
    adm_docs = qualified_j3_table("AdmDocumentos", j3_database)
    start = _validate_period_date(start_date, "start_date")
    end = _validate_period_date(end_date, "end_date")
    excluded = _excluded_docs_sql()
    aceptada = is_factura_aceptada_sql()
    return f"""
fe_filtrada AS (
    SELECT
        dc.DocumentosCodigo,
        fe.Codigo,
        fe.Enviado,
        fe.Cufe,
        fe.Total,
        fe.Documento,
        fe.FechaFactura,
        {aceptada} AS Es_Aceptada
    FROM {estado} fe
    JOIN {adm_docs} dc ON dc.DocumentosID = fe.DocumentosID
    WHERE fe.FechaFactura BETWEEN '{start}' AND '{end}'
      AND dc.DocumentosCodigo NOT IN ({excluded})
)""".strip()


def build_factura_electronica_summary_sql(
    start_date: str,
    end_date: str,
    *,
    j3_database: Optional[str] = None,
) -> str:
    """Single-row period summary: emitidas, aceptadas, rechazadas, rates."""
    cte = _fe_filtrada_cte(
        start_date=start_date, end_date=end_date, j3_database=j3_database
    )
    return f"""
WITH {cte}
SELECT
    COUNT(*) AS Emitidas,
    SUM(Es_Aceptada) AS Aceptadas,
    COUNT(*) - SUM(Es_Aceptada) AS Rechazadas,
    CASE
        WHEN COUNT(*) = 0 THEN 0
        ELSE SUM(Es_Aceptada) * 100.0 / COUNT(*)
    END AS Tasa_Aceptacion_Pct,
    CASE
        WHEN COUNT(*) = 0 THEN 0
        ELSE (COUNT(*) - SUM(Es_Aceptada)) * 100.0 / COUNT(*)
    END AS Tasa_Rechazo_Pct,
    SUM(Total) AS Valor_Total
FROM fe_filtrada;
""".strip()


def build_factura_electronica_by_documento_sql(
    start_date: str,
    end_date: str,
    *,
    j3_database: Optional[str] = None,
) -> str:
    """Acceptance metrics grouped by ``DocumentosCodigo``."""
    cte = _fe_filtrada_cte(
        start_date=start_date, end_date=end_date, j3_database=j3_database
    )
    return f"""
WITH {cte}
SELECT
    DocumentosCodigo,
    COUNT(*) AS Emitidas,
    SUM(Es_Aceptada) AS Aceptadas,
    COUNT(*) - SUM(Es_Aceptada) AS Rechazadas,
    CASE
        WHEN COUNT(*) = 0 THEN 0
        ELSE SUM(Es_Aceptada) * 100.0 / COUNT(*)
    END AS Tasa_Aceptacion_Pct,
    CASE
        WHEN COUNT(*) = 0 THEN 0
        ELSE (COUNT(*) - SUM(Es_Aceptada)) * 100.0 / COUNT(*)
    END AS Tasa_Rechazo_Pct,
    SUM(Total) AS Valor_Total
FROM fe_filtrada
GROUP BY DocumentosCodigo
ORDER BY Rechazadas DESC, Emitidas DESC;
""".strip()


def build_factura_electronica_rechazos_sql(
    start_date: str,
    end_date: str,
    *,
    top_n: int = DEFAULT_TOP_N_REJECTIONS,
    j3_database: Optional[str] = None,
) -> str:
    """Recent rejected e-invoices for operational follow-up."""
    cte = _fe_filtrada_cte(
        start_date=start_date, end_date=end_date, j3_database=j3_database
    )
    n = max(1, int(top_n))
    return f"""
WITH {cte}
SELECT TOP {n}
    Documento,
    DocumentosCodigo,
    FechaFactura,
    Codigo,
    Enviado,
    Total
FROM fe_filtrada
WHERE Es_Aceptada = 0
ORDER BY FechaFactura DESC, Total DESC;
""".strip()


def validate_factura_electronica_sql_period(start_date: str, end_date: str) -> None:
    """Raise ``ValueError`` when the period is invalid."""
    start = _validate_period_date(start_date, "start_date")
    end = _validate_period_date(end_date, "end_date")
    if start > end:
        raise ValueError("start_date must be on or before end_date")


def _as_int(value: Any) -> int:
    if value is None:
        return 0
    return int(value)


def _as_float(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def factura_electronica_summary_from_documento_rows(
    rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Weighted acceptance aggregate from document-type rows."""
    emitidas = sum(_as_int(r.get("Emitidas")) for r in rows)
    aceptadas = sum(_as_int(r.get("Aceptadas")) for r in rows)
    rechazadas = sum(_as_int(r.get("Rechazadas")) for r in rows)
    valor_total = sum(_as_float(r.get("Valor_Total")) for r in rows)
    return {
        "Emitidas": emitidas,
        "Aceptadas": aceptadas,
        "Rechazadas": rechazadas,
        "Tasa_Aceptacion_Pct": (aceptadas * 100.0 / emitidas) if emitidas else 0.0,
        "Tasa_Rechazo_Pct": (rechazadas * 100.0 / emitidas) if emitidas else 0.0,
        "Valor_Total": valor_total,
    }


def worst_rejection_document_types(
    rows: Sequence[Mapping[str, Any]],
    *,
    n: int = 5,
) -> List[Dict[str, Any]]:
    """Document types with most rejections."""
    ranked = sorted(
        rows,
        key=lambda r: (
            _as_int(r.get("Rechazadas")),
            _as_float(r.get("Tasa_Rechazo_Pct")),
        ),
        reverse=True,
    )
    return [dict(row) for row in ranked[:n] if _as_int(row.get("Rechazadas")) > 0]


class FacturaElectronicaRunner:
    """Execute J3System e-invoice compliance SQL and return structured results."""

    def __init__(
        self,
        db: Optional[Database] = None,
        *,
        j3_database: Optional[str] = None,
        top_n_rejections: int = DEFAULT_TOP_N_REJECTIONS,
    ) -> None:
        self.db = db or Database()
        self.j3_database = j3_database
        self.top_n_rejections = top_n_rejections

    def _execute_j3_query(self, sql: str) -> List[Dict[str, Any]]:
        conn = self.db.get_j3system_connection()
        try:
            cursor = conn.cursor(as_dict=True)
            cursor.execute(sql)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def fetch_summary(self, start_date: str, end_date: str) -> Dict[str, Any]:
        validate_factura_electronica_sql_period(start_date, end_date)
        sql = build_factura_electronica_summary_sql(
            start_date, end_date, j3_database=self.j3_database
        )
        rows = self._execute_j3_query(sql)
        return dict(rows[0]) if rows else {}

    def fetch_by_documento(
        self, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        validate_factura_electronica_sql_period(start_date, end_date)
        sql = build_factura_electronica_by_documento_sql(
            start_date, end_date, j3_database=self.j3_database
        )
        return self._execute_j3_query(sql)

    def fetch_rechazos(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        validate_factura_electronica_sql_period(start_date, end_date)
        sql = build_factura_electronica_rechazos_sql(
            start_date,
            end_date,
            top_n=self.top_n_rejections,
            j3_database=self.j3_database,
        )
        return self._execute_j3_query(sql)

    def build_report(self, start_date: str, end_date: str) -> Dict[str, Any]:
        summary = self.fetch_summary(start_date, end_date)
        by_documento = self.fetch_by_documento(start_date, end_date)
        rechazos = self.fetch_rechazos(start_date, end_date)
        if not summary and by_documento:
            summary = factura_electronica_summary_from_documento_rows(by_documento)
        return {
            "period": {"start": start_date, "end": end_date},
            "summary": summary,
            "by_documento": by_documento,
            "rechazos": rechazos,
            "worst_document_types": worst_rejection_document_types(by_documento),
        }
