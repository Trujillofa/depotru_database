"""
Engine D — Hierarchical category fallback.

For any SKU that still has < 10 related products, this engine fills gaps by
recommending the top-selling products from the same subcategory, then the
same category.

This is the lowest-confidence engine but provides 100 % coverage.
"""

import logging
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from ...core.database import Database
from . import EXCLUDED_CODES, EXCLUDED_SKUS, EngineResult

logger = logging.getLogger(__name__)

SOURCE = "category_fallback"


def _fetch_category_data(
    db: Database, active_skus: Optional[Set[str]] = None
) -> Dict[str, Dict[str, Any]]:
    """Fetch (sku -> {categoria, subcategoria, sales}) for all active SKUs."""
    excl_doc = ", ".join(f"'{c}'" for c in EXCLUDED_CODES)
    excl_sku = ", ".join(f"'{s}'" for s in EXCLUDED_SKUS)
    rows = db.execute_query(
        f"""
        SELECT
            ArticulosCodigo,
            ArticulosNombre,
            COALESCE(categoria, '') AS categoria,
            COALESCE(subcategoria, '') AS subcategoria,
            COUNT(*) AS total_sales
        FROM [SmartBusiness].[dbo].[banco_datos]
        WHERE DocumentosCodigo NOT IN ({excl_doc})
          AND ArticulosCodigo IS NOT NULL
          AND ArticulosCodigo <> ''
          AND ArticulosCodigo NOT IN ({excl_sku})
        GROUP BY ArticulosCodigo, ArticulosNombre, categoria, subcategoria
        """
    )
    raw: List[Dict[str, Any]] = rows if isinstance(rows, list) else []

    sku_info: Dict[str, Dict[str, Any]] = {}
    for r in raw:
        sku = r["ArticulosCodigo"].strip()
        if active_skus and sku not in active_skus:
            continue
        sku_info[sku] = {
            "name": r.get("ArticulosNombre", sku) or sku,
            "categoria": (r.get("categoria") or "").strip(),
            "subcategoria": (r.get("subcategoria") or "").strip(),
            "sales": r["total_sales"],
        }

    logger.info("  -> fetched %d SKUs with category data", len(sku_info))
    return sku_info


def run(
    db: Database,
    active_skus: Optional[Set[str]] = None,
    top_n: int = 50,
) -> List[EngineResult]:
    """Run category-based fallback engine.

    Returns pairs (sku, related_sku) where related_sku is from the same
    subcategory or category, scored by relative sales rank within that group.
    """
    logger.info("[Engine D] Category/subcategory fallback …")
    t0 = time.time()

    sku_info = _fetch_category_data(db, active_skus)
    if not sku_info:
        return []

    # Build subcategory -> list of (sku, sales) sorted descending
    subcat_skus: Dict[str, List[tuple]] = defaultdict(list)
    cat_skus: Dict[str, List[tuple]] = defaultdict(list)

    for sku, info in sku_info.items():
        subcat = info["subcategoria"]
        if subcat:
            subcat_skus[subcat].append((sku, info["sales"]))
        cat = info["categoria"]
        if cat:
            cat_skus[cat].append((sku, info["sales"]))

    for lst in subcat_skus.values():
        lst.sort(key=lambda x: -x[1])
    for lst in cat_skus.values():
        lst.sort(key=lambda x: -x[1])

    # For each SKU, get top sellers from same subcat, then same cat
    results: List[EngineResult] = []
    for sku, info in sku_info.items():
        seen: Set[str] = {sku}
        candidates: List[tuple] = []  # (related_sku, rank)

        # 1. Same subcategory
        subcat = info["subcategoria"]
        if subcat and subcat in subcat_skus:
            for rel_sku, _ in subcat_skus[subcat]:
                if rel_sku not in seen:
                    candidates.append((rel_sku, 0.8))  # high intra-subcat score
                    seen.add(rel_sku)
                    if len(candidates) >= top_n:
                        break

        # 2. Same category (if still short)
        cat = info["categoria"]
        if len(candidates) < top_n and cat and cat in cat_skus:
            for rel_sku, _ in cat_skus[cat]:
                if rel_sku not in seen:
                    candidates.append((rel_sku, 0.5))  # lower intra-cat score
                    seen.add(rel_sku)
                    if len(candidates) >= top_n:
                        break

        for rel_sku, score in candidates:
            results.append(
                {
                    "sku_a": sku,
                    "sku_b": rel_sku,
                    "name_a": info["name"],
                    "name_b": sku_info[rel_sku]["name"],
                    "score": score,
                    "source": SOURCE,
                }
            )

    elapsed = time.time() - t0
    logger.info("  -> %d pairs generated in %.1f s", len(results), elapsed)
    return results
