"""Co-occurrence mart table helpers for the affinity pipeline."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Set

from business_analyzer.core.database import Database

logger = logging.getLogger(__name__)

MART_TABLE = os.getenv("AFFINITY_MART_TABLE", "affinity_co_occurrence")


def use_mart_preferred() -> bool:
    return os.getenv("AFFINITY_USE_MART", "0").lower() in {"1", "true", "yes"}


def mart_table_exists(db: Database) -> bool:
    try:
        rows = db.execute_query(
            """
            SELECT 1 AS ok
            FROM sys.tables
            WHERE name = %s AND schema_id = SCHEMA_ID('dbo')
            """,
            (MART_TABLE,),
        )
        return bool(rows)
    except Exception:
        return False


def refresh_co_occurrence_mart(db: Database) -> int:
    """Rebuild the co-occurrence mart from banco_datos. Returns row count."""
    from business_analyzer.analysis.engines.co_occurrence import (
        generate_co_occurrence_sql,
    )

    table = Database.validate_sql_identifier(MART_TABLE, "mart table")
    logger.info("Refreshing mart table dbo.%s …", table)
    t0 = time.time()

    db.execute_query(f"TRUNCATE TABLE dbo.[{table}]", fetch=False)  # nosec B608

    insert_sql = f"""
        INSERT INTO dbo.[{table}] (sku_a, sku_b, name_a, name_b, co_count)
        {generate_co_occurrence_sql().strip()}
    """  # nosec B608
    inserted = db.execute_query(insert_sql, fetch=False)
    row_count = inserted if isinstance(inserted, int) else 0
    elapsed = time.time() - t0
    logger.info("Mart refresh complete: %s rows in %.1f s", row_count, elapsed)
    return row_count


def fetch_co_occurrence_from_mart(db: Database) -> List[Dict[str, Any]]:
    table = Database.validate_sql_identifier(MART_TABLE, "mart table")
    rows = db.execute_query(
        f"""
        SELECT sku_a, name_a, sku_b, name_b, co_count
        FROM dbo.[{table}]
        ORDER BY co_count DESC
        """,  # nosec B608
    )
    return rows if isinstance(rows, list) else []


def rows_to_engine_results(
    rows: List[Dict[str, Any]],
    active_skus: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    if not rows:
        return []
    max_co = max(int(r.get("co_count") or 0) for r in rows)
    results: List[Dict[str, Any]] = []
    for r in rows:
        sku_a = str(r.get("sku_a", "")).strip()
        sku_b = str(r.get("sku_b", "")).strip()
        if not sku_a or not sku_b:
            continue
        if active_skus and (sku_a not in active_skus or sku_b not in active_skus):
            continue
        co = int(r.get("co_count") or 0)
        score = co / max_co if max_co else 0.0
        results.append(
            {
                "sku_a": sku_a,
                "sku_b": sku_b,
                "name_a": r.get("name_a", sku_a) or sku_a,
                "name_b": r.get("name_b", sku_b) or sku_b,
                "score": round(score, 4),
                "source": "co_occurrence",
            }
        )
    return results
