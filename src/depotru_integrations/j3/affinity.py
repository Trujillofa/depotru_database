"""Afinidad de canasta: qué se compra junto, medido en las facturas de J3.

No es una tabla escrita a mano ni una relación de merchandising: son las
canastas reales de `SmartBusiness.dbo.banco_datos` (1,7 M líneas de venta).
Canasta = (DocumentosCodigo, NumeroDocumento); no existe columna `Documento`.

Regla de exploración de J3: empezar por las tablas MÁS GRANDES
(sys.tables + sys.partitions). Las de configuración tienen decenas de filas y
nombres que engañan (AdmDocumentos = tipos de documento).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from business_analyzer.core.database import get_db_connection

WINDOW_MONTHS = 12

#: Canastas que contienen el SKU ancla, y qué otros SKU aparecen en ellas.
#: Se excluye el propio SKU y se ordena por canastas compartidas.
_SQL = """
WITH ancla AS (
    SELECT DISTINCT DocumentosCodigo, NumeroDocumento
    FROM SmartBusiness.dbo.banco_datos
    WHERE ArticulosCodigo = %s AND Cantidad > 0
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
      AND d.Fecha >= DATEADD(month, -{months}, GETDATE())
    GROUP BY d.ArticulosCodigo
)
SELECT TOP ({limit}) sku, nombre, canastas
FROM lineas
WHERE canastas >= 20
ORDER BY canastas DESC
"""


def _fetch(sku: str, limit: int) -> list[tuple[str, str, int]]:
    """Consulta J3 (sólo lectura). Aislada para poder sustituirla en pruebas."""
    conn = get_db_connection().get_j3system_connection()
    cur = conn.cursor()
    cur.execute(_SQL.format(months=WINDOW_MONTHS, limit=int(limit)), (sku, sku))
    return [(str(r[0]), str(r[1] or ""), int(str(r[2]))) for r in cur.fetchall()]


@lru_cache(maxsize=1024)
def _cached(sku: str, limit: int) -> tuple[tuple[str, str, int], ...]:
    return tuple(_fetch(sku, limit))


def cross_sell_affinity(sku: str, limit: int = 5) -> dict[str, Any]:
    """Complementos del SKU por afinidad de canasta, sin precios."""
    clean = (sku or "").strip()
    if not clean:
        return {"status": "error", "reason": "missing_sku", "products": []}
    size = max(1, min(int(limit), 10))
    try:
        rows = _cached(clean, size)
    except Exception as exc:  # noqa: BLE001 - la herramienta no miente: informa
        return {
            "status": "error",
            "reason": f"j3_unavailable: {type(exc).__name__}",
            "products": [],
        }
    products = [
        {"sku": row[0], "name": row[1], "baskets": row[2], "relation": "basket"}
        for row in rows
        if row[0] and row[1]
    ]
    return {
        "status": "ok" if products else "empty",
        "source": "j3_baskets",
        "window_months": WINDOW_MONTHS,
        "products": products,
    }
