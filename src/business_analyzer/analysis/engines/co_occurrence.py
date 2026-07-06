"""
Engine A — Ticket-level co-occurrence (existing logic, high confidence).

Counts how many tickets each pair of SKUs appears in together, using
COUNT(DISTINCT ticket_id) to avoid overcounting duplicate line-item rows.
"""

import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from ...core.database import Database
from ..affinity_mart import (
    fetch_co_occurrence_from_mart,
    mart_table_exists,
    rows_to_engine_results,
    use_mart_preferred,
)
from . import EXCLUDED_CODES, EXCLUDED_SKUS, MATRIX_MIN_SALES, EngineResult

logger = logging.getLogger(__name__)

SOURCE = "co_occurrence"


def generate_co_occurrence_sql(
    excluded_codes: Tuple[str, ...] = EXCLUDED_CODES,
    excluded_skus: Tuple[str, ...] = EXCLUDED_SKUS,
) -> str:
    """SQL: self-join on ticket to count co-occurrence."""
    excl_doc_list = ", ".join(f"'{c}'" for c in excluded_codes)
    excl_sku_list = ", ".join(f"'{s}'" for s in excluded_skus)
    return f"""
    SELECT
        a.ArticulosCodigo  AS sku_a,
        a.ArticulosNombre  AS name_a,
        b.ArticulosCodigo  AS sku_b,
        b.ArticulosNombre  AS name_b,
        COUNT(DISTINCT CAST(a.NumeroDocumento AS VARCHAR(20)) + a.DocumentosCodigo)
                           AS co_count
    FROM [SmartBusiness].[dbo].[banco_datos] a
    JOIN [SmartBusiness].[dbo].[banco_datos] b
        ON  a.DocumentosCodigo  = b.DocumentosCodigo
        AND a.NumeroDocumento   = b.NumeroDocumento
        AND a.ArticulosCodigo   < b.ArticulosCodigo
    WHERE a.DocumentosCodigo NOT IN ({excl_doc_list})
      AND b.DocumentosCodigo NOT IN ({excl_doc_list})
      AND a.ArticulosCodigo IS NOT NULL
      AND b.ArticulosCodigo IS NOT NULL
      AND a.ArticulosCodigo <> ''
      AND b.ArticulosCodigo <> ''
      AND a.ArticulosCodigo NOT IN ({excl_sku_list})
      AND b.ArticulosCodigo NOT IN ({excl_sku_list})
    GROUP BY
        a.ArticulosCodigo,
        a.ArticulosNombre,
        b.ArticulosCodigo,
        b.ArticulosNombre
    HAVING COUNT(DISTINCT CAST(a.NumeroDocumento AS VARCHAR(20)) + a.DocumentosCodigo) >= 2
    ORDER BY
        a.ArticulosCodigo,
        co_count DESC
    """


def run(
    db: Database,
    active_skus: Optional[Set[str]] = None,
    top_n: int = 50,  # grab extra; blender will trim to 10
) -> List[EngineResult]:
    """Run co-occurrence engine and return scored results.

    Scores are normalized to 0-1 by dividing by max co_count in the dataset.
    Only pairs where BOTH SKUs are in *active_skus* (met sales threshold)
    are returned.
    """
    logger.info("[Engine A] Ticket-level co-occurrence …")
    t0 = time.time()

    rows: List[Dict[str, Any]] = []
    if use_mart_preferred() and mart_table_exists(db):
        logger.info("  -> reading pre-aggregated mart table")
        rows = fetch_co_occurrence_from_mart(db)
    else:
        raw = db.execute_query(generate_co_occurrence_sql())
        rows = raw if isinstance(raw, list) else []

    elapsed = time.time() - t0
    logger.info("  -> loaded %d pairs in %.1f s", len(rows), elapsed)

    results = rows_to_engine_results(rows, active_skus)
    logger.info("  -> %d pairs after active-SKU filter", len(results))
    return results
