"""Afinidad de canasta: qué se compra junto, medido en las facturas de J3.

No es una tabla escrita a mano ni una relación de merchandising: son las
canastas reales de `SmartBusiness.dbo.banco_datos` (1,7 M líneas de venta).
Canasta = (DocumentosCodigo, NumeroDocumento); no existe columna `Documento`.

Regla de exploración de J3: empezar por las tablas MÁS GRANDES
(sys.tables + sys.partitions). Las de configuración tienen decenas de filas y
nombres que engañan (AdmDocumentos = tipos de documento).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from business_analyzer.core.database import get_db_connection
from depotru_integrations.affinity.store import TABLE as AFFINITY_TABLE
from depotru_integrations.affinity.store import AffinityRecord, configured_store
from depotru_kernel.documents import excluded_document_sql_in_list

WINDOW_MONTHS = 12

#: Canastas que contienen el SKU ancla, y qué otros SKU aparecen en ellas.
#: Se excluye el propio SKU y se ordena por canastas compartidas.
_SQL = """
WITH ancla AS (
    SELECT DISTINCT DocumentosCodigo, NumeroDocumento
    FROM SmartBusiness.dbo.banco_datos
    WHERE ArticulosCodigo = %s AND Cantidad > 0
      AND DocumentosCodigo NOT IN (__EXCLUDED_DOCS__)
      AND Fecha >= DATEADD(month, -{months}, GETDATE())
),
lineas AS (
    SELECT d.ArticulosCodigo AS sku, MAX(d.ArticulosNombre) AS nombre,
           COUNT(DISTINCT CONVERT(varchar(20), d.DocumentosCodigo) + '-' +
                   CONVERT(varchar(30), d.NumeroDocumento)) AS canastas
    FROM SmartBusiness.dbo.banco_datos d
    JOIN ancla a
      ON a.DocumentosCodigo = d.DocumentosCodigo
     AND a.NumeroDocumento = d.NumeroDocumento
    WHERE d.Cantidad > 0 AND d.ArticulosCodigo <> %s
      AND d.DocumentosCodigo NOT IN (__EXCLUDED_DOCS__)
      AND d.Fecha >= DATEADD(month, -{months}, GETDATE())
    GROUP BY d.ArticulosCodigo
)
SELECT TOP ({limit}) sku, nombre, canastas
FROM lineas
WHERE canastas >= 20
ORDER BY canastas DESC
""".replace(
    "__EXCLUDED_DOCS__", excluded_document_sql_in_list()
)


def _fetch(sku: str, limit: int) -> list[tuple[str, str, int]]:
    """Consulta J3 (sólo lectura). Aislada para poder sustituirla en pruebas."""
    database = get_db_connection()
    connection = None
    try:
        connection = database.get_j3system_connection()
        cur = connection.cursor()
        cur.execute(_SQL.format(months=WINDOW_MONTHS, limit=int(limit)), (sku, sku))
        return [(str(r[0]), str(r[1] or ""), int(str(r[2]))) for r in cur.fetchall()]
    finally:
        if connection is not None:
            connection.close()
        database.close()


@lru_cache(maxsize=1024)
def _cached(sku: str, limit: int) -> tuple[tuple[str, str, int], ...]:
    return tuple(_fetch(sku, limit))


MIN_BASKETS = 20
# El job corre a diario a las 02:30; el sello de la tabla no puede llevar
# más de 5 noches perdidas sin caer al J3 en vivo. (Era 35: del 5 al 18 nov
# 2026 el job falló 13 noches seguidas y el lector siguió publicando.)
MAX_TABLE_AGE_DAYS = 5


def _staleness_floor() -> str:
    now = datetime.now(timezone.utc) - timedelta(days=MAX_TABLE_AGE_DAYS)
    return now.date().isoformat()


def _in_contract(record: AffinityRecord) -> bool:
    """El contrato que el SQL en vivo anuncia: complemento distinto del
    ancla, >= 20 canastas, ventana de 12 meses y sello de escritura
    reciente. La tabla materializada se escribe con SU propia
    configuración; si trae filas fuera del contrato (stale,
    re-configurada, ventana absurda o congelada), el lector no las
    publica."""
    if not record.complement_sku or record.complement_sku == record.sku:
        return False
    if (record.baskets or 0) < MIN_BASKETS:
        return False
    window = record.window_months
    if window is None or window < 1 or window > WINDOW_MONTHS:
        return False
    if (record.stored_at or "")[:10] < _staleness_floor():
        return False
    return True


def _from_table(sku: str, limit: int) -> tuple[list[AffinityRecord] | None, str | None]:
    """Lee la tabla precalculada; ``(None, motivo)`` si no se puede usar."""
    try:
        store = configured_store()
    except Exception as exc:  # noqa: BLE001 - la tabla es opcional, no el único camino
        return None, f"table_unavailable: {type(exc).__name__}"
    if store is None:
        return None, None
    try:
        records = store.top_for_sku(sku, limit)
    except Exception as exc:  # noqa: BLE001 - cae a la consulta en vivo
        return None, f"table_unavailable: {type(exc).__name__}"
    if not records:
        return None, "table_empty"
    in_contract = [record for record in records if _in_contract(record)]
    if not in_contract:
        # Todo lo que la tabla trae está fuera del contrato que el SQL
        # anuncia: la tabla está stale/mal sembrada. Cae a J3 en vivo; se
        # informa el motivo, no se publica la basura (hallazgo 6 firma).
        return None, "table_out_of_contract"
    return in_contract, None


def cross_sell_affinity(sku: str, limit: int = 5) -> dict[str, Any]:
    """Complementos del SKU: tabla precalculada primero, J3 en vivo después."""
    clean = (sku or "").strip()
    if not clean:
        return {"status": "error", "reason": "missing_sku", "products": []}
    size = max(1, min(int(limit), 10))

    records, table_reason = _from_table(clean, size)
    if records:
        products = [
            {
                "sku": record.complement_sku,
                "name": record.complement_name or record.complement_sku,
                "baskets": record.baskets,
                "relation": "basket",
            }
            for record in records
            if record.complement_sku
        ]
        if products:
            return {
                "status": "ok",
                "source": "precomputed",
                "source_table": AFFINITY_TABLE,
                "window_months": records[0].window_months,
                "products": products,
            }

    try:
        rows = _cached(clean, size)
    except Exception as exc:  # noqa: BLE001 - la herramienta no miente: informa
        error_result: dict[str, Any] = {
            "status": "error",
            "reason": f"j3_unavailable: {type(exc).__name__}",
            "products": [],
        }
        if table_reason:
            error_result["table_status"] = table_reason
        return error_result
    products = [
        {"sku": row[0], "name": row[1], "baskets": row[2], "relation": "basket"}
        for row in rows
        if row[0] and row[1]
    ]
    result: dict[str, Any] = {
        "status": "ok" if products else "empty",
        "source": "j3_baskets",
        "window_months": WINDOW_MONTHS,
        "products": products,
    }
    if table_reason:
        # Visible para operación: la tabla no respondió o no tenía el SKU y se
        # pagó la consulta en vivo. No se esconde el motivo.
        result["table_status"] = table_reason
    return result
