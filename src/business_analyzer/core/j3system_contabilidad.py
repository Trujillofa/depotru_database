"""J3System accounting (libro mayor) SQL builders.

``ConMovimiento`` + ``ConMovimientoDetalle`` joined to ``AdmCuentasPuc`` (PUC)
and ``AdmSubCentroCosto`` for cost-center expense views.

Signed balance respects ``CuentasPucNaturaleza`` (D/C). Test documents are
excluded via ``AdmDocumentos`` (XY, AS, TS, YX, ISC).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

from business_analyzer.core.database import Database, qualified_sb_table
from business_analyzer.core.j3system_sales_warehouse import (
    _validate_period_date,
    qualified_j3_table,
)

DEFAULT_TOP_N_GASTOS = 15
DEFAULT_TOP_N_CENTROS = 20

EXCLUDED_DOC_CODES: tuple[str, ...] = ("XY", "AS", "TS", "YX", "ISC")
BALANCE_CLASSES: tuple[str, ...] = ("1", "2", "3")
PYG_CLASSES: tuple[str, ...] = ("4", "5", "6")

PUC_CLASE_LABELS: Dict[str, str] = {
    "1": "Activo",
    "2": "Pasivo",
    "3": "Patrimonio",
    "4": "Ingresos",
    "5": "Gastos",
    "6": "Costos",
}

CONTABILIDAD_METRIC_HELP: Dict[str, str] = {
    "balance_intro": (
        "Saldos acumulados al cierre del periodo (movimientos históricos hasta la "
        "fecha fin). Clases 1=Activo, 2=Pasivo, 3=Patrimonio."
    ),
    "pyg_intro": (
        "Movimientos del periodo en cuentas de resultado. Clase 4=Ingresos, "
        "5=Gastos operativos, 6=Costos de ventas."
    ),
    "margen_bruto_contable": (
        "Ingresos operacionales (créditos clase 4) menos costos de ventas "
        "(débitos clase 6), según libro mayor."
    ),
    "margen_contable_pct": "Margen bruto contable ÷ ingresos clase 4 × 100.",
    "conciliacion_ingresos": (
        "Compara créditos del grupo PUC 41 (ingresos operacionales) contra "
        "facturación BI con IVA en banco_datos del mismo periodo."
    ),
    "cuadre": "Suma de débitos = suma de créditos en movimientos del periodo.",
    "ecuacion_contable": (
        "Activo = Pasivo + Patrimonio + resultado acumulado (clases 4–6 sin cierre "
        "a patrimonio). El resultado es ingresos (cl. 4) menos gastos (cl. 5) y "
        "costos (cl. 6) según saldos históricos abiertos en el mayor."
    ),
    "resultado_pyg_acumulado": (
        "Utilidad/pérdida acumulada abierta: saldo clase 4 − clase 5 − clase 6 "
        "sin traslado de cierre a patrimonio. Positivo = utilidad abierta."
    ),
}


def _excluded_docs_sql() -> str:
    return ", ".join(f"'{code}'" for code in EXCLUDED_DOC_CODES)


def puc_signed_balance_sql(
    *,
    naturaleza_col: str = "p.CuentasPucNaturaleza",
    tipo_col: str = "det.MovimientoDetalleTipo",
    valor_col: str = "det.MovimientoDetalleValor",
) -> str:
    """Signed movement amount using PUC account nature (D/C)."""
    return f"""CASE
        WHEN {naturaleza_col} = 'C' THEN
            CASE WHEN {tipo_col} = 'C' THEN {valor_col} ELSE -{valor_col} END
        WHEN {naturaleza_col} = 'D' THEN
            CASE WHEN {tipo_col} = 'D' THEN {valor_col} ELSE -{valor_col} END
        ELSE 0
    END"""


def _movimientos_filtrados_cte(
    *,
    start_date: str,
    end_date: str,
    j3_database: Optional[str] = None,
) -> str:
    movimiento = qualified_j3_table("ConMovimiento", j3_database)
    detalle = qualified_j3_table("ConMovimientoDetalle", j3_database)
    adm_docs = qualified_j3_table("AdmDocumentos", j3_database)
    cuentas = qualified_j3_table("AdmCuentasPuc", j3_database)
    start = _validate_period_date(start_date, "start_date")
    end = _validate_period_date(end_date, "end_date")
    excluded = _excluded_docs_sql()
    signed = puc_signed_balance_sql()
    return f"""
movimientos_filtrados AS (
    SELECT
        m.MovimientoID,
        m.MovimientoFecha,
        dc.DocumentosCodigo,
        p.CuentasPucCodigo,
        p.CuentasPucNombre,
        p.CuentasPucNaturaleza,
        det.MovimientoDetalleTipo,
        det.MovimientoDetalleValor,
        det.SubCentroCostoID,
        {signed} AS Saldo_Firmado
    FROM {movimiento} m
    JOIN {detalle} det ON det.MovimientoID = m.MovimientoID
    JOIN {adm_docs} dc ON dc.DocumentosID = m.DocumentosID
    JOIN {cuentas} p ON p.CuentasPucID = det.CuentasPucID
    WHERE m.MovimientoFecha BETWEEN '{start}' AND '{end}'
      AND dc.DocumentosCodigo NOT IN ({excluded})
)""".strip()


def _movimientos_acumulados_hasta_cte(
    *,
    end_date: str,
    j3_database: Optional[str] = None,
) -> str:
    """Cumulative movements through ``end_date`` (balance sheet position)."""
    movimiento = qualified_j3_table("ConMovimiento", j3_database)
    detalle = qualified_j3_table("ConMovimientoDetalle", j3_database)
    adm_docs = qualified_j3_table("AdmDocumentos", j3_database)
    cuentas = qualified_j3_table("AdmCuentasPuc", j3_database)
    end = _validate_period_date(end_date, "end_date")
    excluded = _excluded_docs_sql()
    signed = puc_signed_balance_sql()
    return f"""
movimientos_acumulados AS (
    SELECT
        p.CuentasPucCodigo,
        p.CuentasPucNombre,
        p.CuentasPucNaturaleza,
        det.MovimientoDetalleTipo,
        det.MovimientoDetalleValor,
        {signed} AS Saldo_Firmado
    FROM {movimiento} m
    JOIN {detalle} det ON det.MovimientoID = m.MovimientoID
    JOIN {adm_docs} dc ON dc.DocumentosID = m.DocumentosID
    JOIN {cuentas} p ON p.CuentasPucID = det.CuentasPucID
    WHERE m.MovimientoFecha <= '{end}'
      AND dc.DocumentosCodigo NOT IN ({excluded})
)""".strip()


def build_contabilidad_balance_clase_sql(
    end_date: str,
    *,
    j3_database: Optional[str] = None,
) -> str:
    """Balance sheet snapshot by PUC class (1=Activo, 2=Pasivo, 3=Patrimonio)."""
    cte = _movimientos_acumulados_hasta_cte(end_date=end_date, j3_database=j3_database)
    classes = ", ".join(f"'{c}'" for c in BALANCE_CLASSES)
    case_lines = "\n        ".join(
        f"WHEN '{code}' THEN '{PUC_CLASE_LABELS[code]}'" for code in BALANCE_CLASSES
    )
    return f"""
WITH {cte}
SELECT
    LEFT(CuentasPucCodigo, 1) AS Clase_Puc,
    CASE LEFT(CuentasPucCodigo, 1)
        {case_lines}
        ELSE 'Otro'
    END AS Tipo_Cuenta,
    SUM(CASE WHEN MovimientoDetalleTipo = 'D' THEN MovimientoDetalleValor ELSE 0 END)
        AS Total_Debitos,
    SUM(CASE WHEN MovimientoDetalleTipo = 'C' THEN MovimientoDetalleValor ELSE 0 END)
        AS Total_Creditos,
    SUM(Saldo_Firmado) AS Saldo_Acumulado
FROM movimientos_acumulados
WHERE LEFT(CuentasPucCodigo, 1) IN ({classes})
GROUP BY LEFT(CuentasPucCodigo, 1)
ORDER BY Clase_Puc;
""".strip()


def build_contabilidad_pyg_acumulado_clase_sql(
    end_date: str,
    *,
    j3_database: Optional[str] = None,
) -> str:
    """Cumulative P&L classes (4–6) through ``end_date`` (open result balances)."""
    cte = _movimientos_acumulados_hasta_cte(end_date=end_date, j3_database=j3_database)
    classes = ", ".join(f"'{c}'" for c in PYG_CLASSES)
    case_lines = "\n        ".join(
        f"WHEN '{code}' THEN '{PUC_CLASE_LABELS[code]}'" for code in PYG_CLASSES
    )
    return f"""
WITH {cte}
SELECT
    LEFT(CuentasPucCodigo, 1) AS Clase_Puc,
    CASE LEFT(CuentasPucCodigo, 1)
        {case_lines}
        ELSE 'Otro'
    END AS Tipo_Cuenta,
    SUM(CASE WHEN MovimientoDetalleTipo = 'D' THEN MovimientoDetalleValor ELSE 0 END)
        AS Total_Debitos,
    SUM(CASE WHEN MovimientoDetalleTipo = 'C' THEN MovimientoDetalleValor ELSE 0 END)
        AS Total_Creditos,
    SUM(Saldo_Firmado) AS Saldo_Acumulado
FROM movimientos_acumulados
WHERE LEFT(CuentasPucCodigo, 1) IN ({classes})
GROUP BY LEFT(CuentasPucCodigo, 1)
ORDER BY Clase_Puc;
""".strip()


def build_contabilidad_summary_sql(
    start_date: str,
    end_date: str,
    *,
    j3_database: Optional[str] = None,
) -> str:
    """Period summary: movement counts and debit/credit cuadre."""
    cte = _movimientos_filtrados_cte(
        start_date=start_date, end_date=end_date, j3_database=j3_database
    )
    return f"""
WITH {cte}
SELECT
    COUNT(DISTINCT MovimientoID) AS Movimientos,
    COUNT(*) AS Lineas,
    SUM(CASE WHEN MovimientoDetalleTipo = 'D' THEN MovimientoDetalleValor ELSE 0 END)
        AS Total_Debitos,
    SUM(CASE WHEN MovimientoDetalleTipo = 'C' THEN MovimientoDetalleValor ELSE 0 END)
        AS Total_Creditos,
    SUM(CASE WHEN MovimientoDetalleTipo = 'D' THEN MovimientoDetalleValor ELSE 0 END)
      - SUM(CASE WHEN MovimientoDetalleTipo = 'C' THEN MovimientoDetalleValor ELSE 0 END)
        AS Diferencia_Cuadre,
    CASE
        WHEN ABS(
            SUM(CASE WHEN MovimientoDetalleTipo = 'D' THEN MovimientoDetalleValor ELSE 0 END)
          - SUM(CASE WHEN MovimientoDetalleTipo = 'C' THEN MovimientoDetalleValor ELSE 0 END)
        ) < 0.01 THEN 1
        ELSE 0
    END AS Cuadre_OK
FROM movimientos_filtrados;
""".strip()


def build_contabilidad_pyg_clase_sql(
    start_date: str,
    end_date: str,
    *,
    j3_database: Optional[str] = None,
) -> str:
    """P&L snapshot by PUC class (4=Ingresos, 5=Gastos, 6=Costos)."""
    cte = _movimientos_filtrados_cte(
        start_date=start_date, end_date=end_date, j3_database=j3_database
    )
    classes = ", ".join(f"'{c}'" for c in PYG_CLASSES)
    return f"""
WITH {cte}
SELECT
    LEFT(CuentasPucCodigo, 1) AS Clase_Puc,
    CASE LEFT(CuentasPucCodigo, 1)
        WHEN '4' THEN '{PUC_CLASE_LABELS["4"]}'
        WHEN '5' THEN '{PUC_CLASE_LABELS["5"]}'
        WHEN '6' THEN '{PUC_CLASE_LABELS["6"]}'
        ELSE 'Otro'
    END AS Tipo_Cuenta,
    SUM(CASE WHEN MovimientoDetalleTipo = 'C' THEN MovimientoDetalleValor ELSE 0 END)
        AS Total_Creditos,
    SUM(CASE WHEN MovimientoDetalleTipo = 'D' THEN MovimientoDetalleValor ELSE 0 END)
        AS Total_Debitos,
    SUM(Saldo_Firmado) AS Saldo_Neto
FROM movimientos_filtrados
WHERE LEFT(CuentasPucCodigo, 1) IN ({classes})
GROUP BY LEFT(CuentasPucCodigo, 1)
ORDER BY Clase_Puc;
""".strip()


def build_contabilidad_gastos_centro_sql(
    start_date: str,
    end_date: str,
    *,
    j3_database: Optional[str] = None,
    top_n: int = DEFAULT_TOP_N_CENTROS,
) -> str:
    """Operating costs (classes 5+6) by cost center."""
    cte = _movimientos_filtrados_cte(
        start_date=start_date, end_date=end_date, j3_database=j3_database
    )
    subcentro = qualified_j3_table("AdmSubCentroCosto", j3_database)
    n = max(1, int(top_n))
    return f"""
WITH {cte}
SELECT TOP {n}
    scc.SubCentroCostoCodigo,
    scc.SubCentroCostoNombre,
    SUM(CASE WHEN LEFT(mf.CuentasPucCodigo, 1) = '5' THEN mf.Saldo_Firmado ELSE 0 END)
        AS Gastos_Neto,
    SUM(CASE WHEN LEFT(mf.CuentasPucCodigo, 1) = '6' THEN mf.Saldo_Firmado ELSE 0 END)
        AS Costos_Neto,
    SUM(mf.Saldo_Firmado) AS Total_Gasto_Costo_Neto
FROM movimientos_filtrados mf
JOIN {subcentro} scc ON scc.SubCentroCostoID = mf.SubCentroCostoID
WHERE LEFT(mf.CuentasPucCodigo, 1) IN ('5', '6')
GROUP BY scc.SubCentroCostoCodigo, scc.SubCentroCostoNombre
ORDER BY ABS(SUM(mf.Saldo_Firmado)) DESC;
""".strip()


def build_contabilidad_top_gastos_sql(
    start_date: str,
    end_date: str,
    *,
    j3_database: Optional[str] = None,
    top_n: int = DEFAULT_TOP_N_GASTOS,
) -> str:
    """Top expense accounts (PUC class 5) by absolute signed balance."""
    cte = _movimientos_filtrados_cte(
        start_date=start_date, end_date=end_date, j3_database=j3_database
    )
    n = max(1, int(top_n))
    return f"""
WITH {cte}
SELECT TOP {n}
    CuentasPucCodigo,
    MAX(CuentasPucNombre) AS CuentasPucNombre,
    SUM(Saldo_Firmado) AS Saldo_Neto,
    SUM(CASE WHEN MovimientoDetalleTipo = 'D' THEN MovimientoDetalleValor ELSE 0 END)
        AS Total_Debitos,
    SUM(CASE WHEN MovimientoDetalleTipo = 'C' THEN MovimientoDetalleValor ELSE 0 END)
        AS Total_Creditos
FROM movimientos_filtrados
WHERE LEFT(CuentasPucCodigo, 1) = '5'
GROUP BY CuentasPucCodigo
ORDER BY ABS(SUM(Saldo_Firmado)) DESC;
""".strip()


def build_contabilidad_conciliacion_ingresos_sql(
    start_date: str,
    end_date: str,
    *,
    j3_database: Optional[str] = None,
    sb_database: Optional[str] = None,
) -> str:
    """Cross-db: grupo 41 credits (contable) vs ``banco_datos`` sales with tax."""
    movimiento = qualified_j3_table("ConMovimiento", j3_database)
    detalle = qualified_j3_table("ConMovimientoDetalle", j3_database)
    adm_docs = qualified_j3_table("AdmDocumentos", j3_database)
    cuentas = qualified_j3_table("AdmCuentasPuc", j3_database)
    banco = qualified_sb_table("banco_datos", sb_database)
    start = _validate_period_date(start_date, "start_date")
    end = _validate_period_date(end_date, "end_date")
    excluded = _excluded_docs_sql()
    return f"""
WITH ingresos_contables AS (
    SELECT
        SUM(CASE WHEN det.MovimientoDetalleTipo = 'C' THEN det.MovimientoDetalleValor ELSE 0 END)
            AS Ingresos_Contables_41
    FROM {movimiento} m
    JOIN {detalle} det ON det.MovimientoID = m.MovimientoID
    JOIN {adm_docs} dc ON dc.DocumentosID = m.DocumentosID
    JOIN {cuentas} p ON p.CuentasPucID = det.CuentasPucID
    WHERE m.MovimientoFecha BETWEEN '{start}' AND '{end}'
      AND dc.DocumentosCodigo NOT IN ({excluded})
      AND LEFT(p.CuentasPucCodigo, 2) = '41'
),
ventas_bi AS (
    SELECT
        SUM(TotalMasIva) AS Ventas_BI_Con_Iva,
        SUM(TotalSinIva) AS Ventas_BI_Sin_Iva
    FROM {banco}
    WHERE Fecha BETWEEN '{start}' AND '{end}'
      AND DocumentosCodigo NOT IN ({excluded})
      AND Cantidad > 0
)
SELECT
    ic.Ingresos_Contables_41,
    vb.Ventas_BI_Con_Iva,
    vb.Ventas_BI_Sin_Iva,
    ic.Ingresos_Contables_41 - vb.Ventas_BI_Con_Iva AS Diferencia_Con_Iva,
    CASE
        WHEN ISNULL(ic.Ingresos_Contables_41, 0) = 0 THEN 0
        ELSE 100.0 - ABS(ic.Ingresos_Contables_41 - vb.Ventas_BI_Con_Iva)
            * 100.0 / ic.Ingresos_Contables_41
    END AS Conciliacion_Ingresos_Pct
FROM ingresos_contables ic
CROSS JOIN ventas_bi vb;
""".strip()


def validate_contabilidad_sql_period(start_date: str, end_date: str) -> None:
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


def balance_summary_from_clase_rows(
    rows: Sequence[Mapping[str, Any]],
    pyg_acumulado_rows: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Aggregate balance sheet metrics from class-level cumulative rows."""
    by_class = {str(r.get("Clase_Puc", "")): r for r in rows}
    activo_signed = _as_float(by_class.get("1", {}).get("Saldo_Acumulado"))
    pasivo_signed = _as_float(by_class.get("2", {}).get("Saldo_Acumulado"))
    patrimonio_signed = _as_float(by_class.get("3", {}).get("Saldo_Acumulado"))
    activo = abs(activo_signed)
    pasivo = abs(pasivo_signed)
    patrimonio = abs(patrimonio_signed)
    pasivo_mas_patrimonio = pasivo + patrimonio
    diferencia_bruta = activo - pasivo_mas_patrimonio
    pyg_by_class = {
        str(r.get("Clase_Puc", "")): _as_float(r.get("Saldo_Acumulado"))
        for r in (pyg_acumulado_rows or [])
    }
    # Economic open result: ingresos − gastos − costos (PUC classes 4–6).
    resultado_pyg_signed = (
        pyg_by_class.get("4", 0.0)
        - pyg_by_class.get("5", 0.0)
        - pyg_by_class.get("6", 0.0)
    )
    # Open PyG explains bruta gap: A − P − E ≈ utilidad acumulada abierta.
    diferencia_ajustada = diferencia_bruta - resultado_pyg_signed
    tolerancia = max(activo * 0.0001, 500_000.0)
    return {
        "Activo_Total": activo,
        "Pasivo_Total": pasivo,
        "Patrimonio_Total": patrimonio,
        "Pasivo_Mas_Patrimonio": pasivo_mas_patrimonio,
        "Resultado_PyG_Acumulado": resultado_pyg_signed,
        "Ecuacion_Diferencia_Bruta": diferencia_bruta,
        "Ecuacion_Diferencia": diferencia_ajustada,
        "Ecuacion_OK": abs(diferencia_ajustada) <= tolerancia,
        "Activo_Signed": activo_signed,
        "Pasivo_Signed": pasivo_signed,
        "Patrimonio_Signed": patrimonio_signed,
    }


def pyg_summary_from_clase_rows(
    rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Aggregate P&L metrics from class-level rows."""
    by_class = {str(r.get("Clase_Puc", "")): r for r in rows}
    ingresos = by_class.get("4", {})
    gastos = by_class.get("5", {})
    costos = by_class.get("6", {})
    ingresos_creditos = _as_float(ingresos.get("Total_Creditos"))
    gastos_debitos = _as_float(gastos.get("Total_Debitos"))
    costos_debitos = _as_float(costos.get("Total_Debitos"))
    margen = ingresos_creditos - costos_debitos
    return {
        "Ingresos_Creditos": ingresos_creditos,
        "Gastos_Debitos": gastos_debitos,
        "Costos_Debitos": costos_debitos,
        "Margen_Bruto_Contable": margen,
        "Margen_Contable_Pct": (margen * 100.0 / ingresos_creditos)
        if ingresos_creditos
        else 0.0,
        "Gastos_Operativos_Neto": abs(_as_float(gastos.get("Saldo_Neto"))),
        "Costos_Neto": abs(_as_float(costos.get("Saldo_Neto"))),
    }


def conciliacion_ingresos_from_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize conciliación ingresos single-row result."""
    return {
        "Ingresos_Contables_41": _as_float(row.get("Ingresos_Contables_41")),
        "Ventas_BI_Con_Iva": _as_float(row.get("Ventas_BI_Con_Iva")),
        "Ventas_BI_Sin_Iva": _as_float(row.get("Ventas_BI_Sin_Iva")),
        "Diferencia_Con_Iva": _as_float(row.get("Diferencia_Con_Iva")),
        "Conciliacion_Ingresos_Pct": _as_float(row.get("Conciliacion_Ingresos_Pct")),
    }


class ContabilidadRunner:
    """Execute J3System accounting SQL and return structured results."""

    def __init__(
        self,
        db: Optional[Database] = None,
        *,
        j3_database: Optional[str] = None,
        sb_database: Optional[str] = None,
        top_n_gastos: int = DEFAULT_TOP_N_GASTOS,
        top_n_centros: int = DEFAULT_TOP_N_CENTROS,
    ) -> None:
        self.db = db or Database()
        self.j3_database = j3_database
        self.sb_database = sb_database
        self.top_n_gastos = top_n_gastos
        self.top_n_centros = top_n_centros

    def _execute_j3_query(self, sql: str) -> List[Dict[str, Any]]:
        conn = self.db.get_j3system_connection()
        try:
            cursor = conn.cursor(as_dict=True)
            cursor.execute(sql)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def fetch_summary(self, start_date: str, end_date: str) -> Dict[str, Any]:
        validate_contabilidad_sql_period(start_date, end_date)
        sql = build_contabilidad_summary_sql(
            start_date, end_date, j3_database=self.j3_database
        )
        rows = self._execute_j3_query(sql)
        return dict(rows[0]) if rows else {}

    def fetch_balance_clase(self, end_date: str) -> List[Dict[str, Any]]:
        end = _validate_period_date(end_date, "end_date")
        sql = build_contabilidad_balance_clase_sql(end, j3_database=self.j3_database)
        return self._execute_j3_query(sql)

    def fetch_pyg_acumulado_clase(self, end_date: str) -> List[Dict[str, Any]]:
        end = _validate_period_date(end_date, "end_date")
        sql = build_contabilidad_pyg_acumulado_clase_sql(
            end, j3_database=self.j3_database
        )
        return self._execute_j3_query(sql)

    def fetch_pyg_clase(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        validate_contabilidad_sql_period(start_date, end_date)
        sql = build_contabilidad_pyg_clase_sql(
            start_date, end_date, j3_database=self.j3_database
        )
        return self._execute_j3_query(sql)

    def fetch_gastos_centro(
        self, start_date: str, end_date: str
    ) -> List[Dict[str, Any]]:
        validate_contabilidad_sql_period(start_date, end_date)
        sql = build_contabilidad_gastos_centro_sql(
            start_date,
            end_date,
            j3_database=self.j3_database,
            top_n=self.top_n_centros,
        )
        return self._execute_j3_query(sql)

    def fetch_top_gastos(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        validate_contabilidad_sql_period(start_date, end_date)
        sql = build_contabilidad_top_gastos_sql(
            start_date,
            end_date,
            j3_database=self.j3_database,
            top_n=self.top_n_gastos,
        )
        return self._execute_j3_query(sql)

    def fetch_conciliacion_ingresos(
        self, start_date: str, end_date: str
    ) -> Dict[str, Any]:
        validate_contabilidad_sql_period(start_date, end_date)
        sql = build_contabilidad_conciliacion_ingresos_sql(
            start_date,
            end_date,
            j3_database=self.j3_database,
            sb_database=self.sb_database,
        )
        rows = self._execute_j3_query(sql)
        return conciliacion_ingresos_from_row(rows[0]) if rows else {}

    def build_report(self, start_date: str, end_date: str) -> Dict[str, Any]:
        summary = self.fetch_summary(start_date, end_date)
        balance_clase = self.fetch_balance_clase(end_date)
        pyg_acumulado_clase = self.fetch_pyg_acumulado_clase(end_date)
        pyg_clase = self.fetch_pyg_clase(start_date, end_date)
        gastos_centro = self.fetch_gastos_centro(start_date, end_date)
        top_gastos = self.fetch_top_gastos(start_date, end_date)
        conciliacion = self.fetch_conciliacion_ingresos(start_date, end_date)
        balance_summary = balance_summary_from_clase_rows(
            balance_clase, pyg_acumulado_clase
        )
        pyg_summary = pyg_summary_from_clase_rows(pyg_clase)
        return {
            "period": {"start": start_date, "end": end_date},
            "summary": summary,
            "balance_clase": balance_clase,
            "pyg_acumulado_clase": pyg_acumulado_clase,
            "balance_summary": balance_summary,
            "pyg_clase": pyg_clase,
            "pyg_summary": pyg_summary,
            "gastos_centro": gastos_centro,
            "top_gastos": top_gastos,
            "conciliacion_ingresos": conciliacion,
            "metric_help": dict(CONTABILIDAD_METRIC_HELP),
        }
