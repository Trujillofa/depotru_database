"""
Engine C — Customer-level co-occurrence (basket expansion).

Broadens the association window from *ticket* to *customer over time*.
Instead of counting how often two SKUs appear in the same invoice, this
engine counts how often they were bought by the same customer within a
configurable time window (default 30 days).

Conceptual SQL:
    SELECT a.ArticulosCodigo AS sku_a, b.ArticulosCodigo AS sku_b,
           COUNT(DISTINCT a.TercerosID) AS co_count
    FROM banco_datos a
    JOIN banco_datos b
        ON a.TercerosID = b.TercerosID
       AND a.ArticulosCodigo < b.ArticulosCodigo
       AND ABS(DATEDIFF(day, a.Fecha, b.Fecha)) <= :window_days
    WHERE ...

Because the table is a heap without indexes, the time-filtered self-join is
prohibitively slow.  Instead we fetch (TercerosID, ArticulosCodigo, Fecha)
and compute co-occurrence in Python using a sliding-window approach per
customer, which is practical for ~1.5M rows.
"""

import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from ...core.database import Database
from . import EXCLUDED_CODES, EXCLUDED_SKUS, EngineResult

logger = logging.getLogger(__name__)

SOURCE = "customer_affinity"


def run(
    db: Database,
    active_skus: Optional[Set[str]] = None,
    top_n: int = 50,
    window_days: int = 30,
) -> List[EngineResult]:
    """Run customer-level co-occurrence engine.

    For each customer, sorts purchases by date and counts how many times
    each pair of SKUs appears within a *window_days* sliding window.
    """
    logger.info(
        "[Engine C] Customer-level co-occurrence (%d-day window) …",
        window_days,
    )
    t0 = time.time()

    excl_doc = ", ".join(f"'{c}'" for c in EXCLUDED_CODES)
    excl_sku = ", ".join(f"'{s}'" for s in EXCLUDED_SKUS)

    rows = db.execute_query(
        f"""
        SELECT
            TercerosID,
            ArticulosCodigo,
            ArticulosNombre,
            Fecha
        FROM [SmartBusiness].[dbo].[banco_datos]
        WHERE DocumentosCodigo NOT IN ({excl_doc})
          AND TercerosID IS NOT NULL
          AND ArticulosCodigo IS NOT NULL
          AND ArticulosCodigo <> ''
          AND ArticulosCodigo NOT IN ({excl_sku})
          AND Fecha IS NOT NULL
        ORDER BY TercerosID, Fecha
        """
    )
    raw: List[Dict[str, Any]] = rows if isinstance(rows, list) else []
    fetch_elapsed = time.time() - t0
    logger.info("  -> fetched %d rows in %.1f s", len(raw), fetch_elapsed)

    if not raw:
        return []

    # Build SKU name lookup before we discard the full dataset
    sku_names: Dict[str, str] = {}
    # Group purchases by customer, deduplicate (customer, sku, date)
    # Convert dates to ordinal integers for fast delta calculation
    customer_purchases: Dict[int, List[tuple]] = defaultdict(list)
    seen: Set[tuple] = set()
    for r in raw:
        cid = r["TercerosID"]
        sku = r["ArticulosCodigo"].strip()
        if active_skus and sku not in active_skus:
            continue
        raw_date = r["Fecha"]
        date_ord = raw_date.toordinal() if hasattr(raw_date, "toordinal") else 0
        key = (cid, sku, date_ord)
        if key not in seen:
            seen.add(key)
            customer_purchases[cid].append((sku, date_ord))

    del seen, raw
    logger.info("  -> %d customers with purchases", len(customer_purchases))

    # For each customer, use a sliding window to count co-occurrences
    sku_names: Dict[str, str] = {}
    pair_counts: Dict[tuple, int] = defaultdict(int)

    processed = 0
    for cid, purchases in customer_purchases.items():
        # Purchases are already sorted by Fecha (ORDER BY in SQL)
        # deduplicate to (sku, date) pairs, same SKU can repeat on diff dates
        n = len(purchases)
        for i in range(n):
            sku_a, date_a = purchases[i]
            # Slide forward within window
            j = i + 1
            while j < n:
                sku_b, date_b = purchases[j]
                delta = date_b - date_a
                if delta > window_days:
                    break
                if sku_a < sku_b:
                    pair_counts[(sku_a, sku_b)] += 1
                elif sku_b < sku_a:
                    pair_counts[(sku_b, sku_a)] += 1
                j += 1

        processed += 1
        if processed % 1000 == 0:
            logger.debug("  -> processed %d customers", processed)

    elapsed = time.time() - t0
    logger.info(
        "  -> %d customer-level pairs in %.1f s",
        len(pair_counts),
        elapsed,
    )

    if not pair_counts:
        return []

    max_co = max(pair_counts.values())
    results: List[EngineResult] = []
    for (sku_a, sku_b), co in pair_counts.items():
        results.append(
            {
                "sku_a": sku_a,
                "sku_b": sku_b,
                "name_a": sku_names.get(sku_a, sku_a),
                "name_b": sku_names.get(sku_b, sku_b),
                "score": round(co / max_co, 4) if max_co else 0.0,
                "source": SOURCE,
            }
        )

    logger.info("  -> %d final pairs", len(results))
    return results
