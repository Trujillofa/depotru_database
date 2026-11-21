"""J3 open-AR reads for the read-only cartera display.

Source: ``VCarCarteraCliente`` (verified live: exposes TercerosID,
identificacion, names, cupo and doc-level ``SaldoCartera``). Everything
here is read-only SELECT over the live ERP (R15/R18): nothing is written,
nothing is persisted in Magento, and the response contains no phone,
cost, or margin column — NIT/name are display fields for the member's
own account or the platform-admin view, never log payload.
"""

from __future__ import annotations


def build_cartera_header_sql() -> str:
    """One tercero's identity/cupo header (any open doc row carries it)."""
    view = _view()
    return f"""
SELECT TOP 1
    v.TercerosID AS terceros_id,
    v.TercerosIdentificacion AS identificacion,
    v.TercerosDv AS identificacion_dv,
    v.TercerosNombres AS nombres,
    v.CiudadNombre AS ciudad,
    v.TercerosCupoCredito AS cupo
FROM {view} v
WHERE v.TercerosID = %s
""".strip()


def build_cartera_docs_sql() -> str:
    """Open documents for ONE tercero, oldest due date first."""
    view = _view()
    return f"""
SELECT
    v.DocumentosCodigo AS documentos_codigo,
    v.NumeroFactura AS numero_factura,
    v.Fecha AS fecha,
    v.FechaVence AS fecha_vence,
    CAST(v.ValorCartera AS DECIMAL(18, 2)) AS valor,
    CAST(v.SaldoCartera AS DECIMAL(18, 2)) AS saldo
FROM {view} v
WHERE v.TercerosID = %s
  AND v.SaldoCartera > 0
ORDER BY v.FechaVence, v.Fecha, v.NumeroDocto
""".strip()


def build_cartera_summary_sql(max_rows: int) -> str:
    """Client-grain open-AR summary across ALL tercero, biggest debt first.

    ``max_rows`` must already be a validated positive int (TOP literal,
    never a bound string). Buckets mirror ``banco_cartera``: corriente
    (not yet due), then 30/60/90/120/360 and >360 days overdue, computed
    against GETDATE() so the summary is live (no SB snapshot lag).
    """
    view = _view()
    top = int(max_rows)
    return f"""
SELECT TOP {top}
    v.TercerosID AS terceros_id,
    v.TercerosIdentificacion AS identificacion,
    MIN(v.TercerosNombres) AS nombres,
    MAX(v.TercerosCupoCredito) AS cupo,
    COUNT(*) AS documents,
    SUM(CAST(v.SaldoCartera AS DECIMAL(18, 2))) AS open_total,
    SUM(CASE WHEN DATEDIFF(DAY, v.FechaVence, GETDATE()) <= 0
             THEN CAST(v.SaldoCartera AS DECIMAL(18, 2)) ELSE 0 END) AS corriente,
    SUM(CASE WHEN DATEDIFF(DAY, v.FechaVence, GETDATE()) BETWEEN 1 AND 30
             THEN CAST(v.SaldoCartera AS DECIMAL(18, 2)) ELSE 0 END) AS vencido_30,
    SUM(CASE WHEN DATEDIFF(DAY, v.FechaVence, GETDATE()) BETWEEN 31 AND 60
             THEN CAST(v.SaldoCartera AS DECIMAL(18, 2)) ELSE 0 END) AS vencido_60,
    SUM(CASE WHEN DATEDIFF(DAY, v.FechaVence, GETDATE()) BETWEEN 61 AND 90
             THEN CAST(v.SaldoCartera AS DECIMAL(18, 2)) ELSE 0 END) AS vencido_90,
    SUM(CASE WHEN DATEDIFF(DAY, v.FechaVence, GETDATE()) BETWEEN 91 AND 120
             THEN CAST(v.SaldoCartera AS DECIMAL(18, 2)) ELSE 0 END) AS vencido_120,
    SUM(CASE WHEN DATEDIFF(DAY, v.FechaVence, GETDATE()) BETWEEN 121 AND 360
             THEN CAST(v.SaldoCartera AS DECIMAL(18, 2)) ELSE 0 END) AS vencido_360,
    SUM(CASE WHEN DATEDIFF(DAY, v.FechaVence, GETDATE()) > 360
             THEN CAST(v.SaldoCartera AS DECIMAL(18, 2)) ELSE 0 END) AS vencido_superior
FROM {view} v
WHERE v.SaldoCartera > 0
GROUP BY v.TercerosID, v.TercerosIdentificacion
ORDER BY open_total DESC
""".strip()


def _view() -> str:
    from business_analyzer.core.j3system_sales_warehouse import qualified_j3_table

    view: str = qualified_j3_table("VCarCarteraCliente")
    return view
