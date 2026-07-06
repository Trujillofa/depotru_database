"""
Blending logic for the Hybrid Affinity Pipeline.

Merges results from all engines with a strict priority order:
    1. co_occurrence (highest confidence)
    2. text_similarity
    3. customer_affinity
    4. category_fallback (lowest confidence)

For each SKU, picks the top *top_n* results, preferring higher-priority
sources.  If all engines combined still yield < top_n results, no padding
is added (the SKU simply has fewer related products).
"""

import logging
from collections import OrderedDict
from typing import Any, Dict, List, Set

from .engines import EngineResult

logger = logging.getLogger(__name__)

ENGINE_PRIORITY = {
    "co_occurrence": 0,
    "text_similarity": 1,
    "customer_affinity": 2,
    "category_fallback": 3,
}


def merge(
    engine_results: Dict[str, List[EngineResult]],
    top_n: int = 10,
) -> Dict[str, List[Dict[str, Any]]]:
    """Merge results from multiple engines into one top-N per SKU.

    *engine_results* maps source name -> list of EngineResult dicts.

    Returns a dict::
        { sku: [{"sku": related_sku, "name": ..., "score": ..., "source": ...}, ...] }

    Within each SKU, results are sorted by (engine_priority, score_desc).
    Duplicate (sku_a, sku_b) pairs from different engines keep the
    highest-priority source.
    """
    logger.info(
        "Blending %d engine outputs …",
        len(engine_results),
    )

    # (sku_a, sku_b) -> best result (highest priority wins)
    best: Dict[tuple, EngineResult] = {}

    for source, results in engine_results.items():
        priority = ENGINE_PRIORITY.get(source, 99)
        for r in results:
            sku_a = r["sku_a"]
            sku_b = r["sku_b"]
            # Store canonical order: smaller sku first
            key = (sku_a, sku_b) if sku_a < sku_b else (sku_b, sku_a)

            if key in best:
                existing = best[key]
                existing_prio = ENGINE_PRIORITY.get(existing["source"], 99)
                if priority < existing_prio:
                    # Replace with higher-priority source
                    best[key] = r
                elif priority == existing_prio and r.get("score", 0) > existing.get(
                    "score", 0
                ):
                    # Same priority, keep higher score
                    best[key] = r
            else:
                best[key] = r

    # Build per-SKU lists
    per_sku: Dict[str, List[Dict]] = {}
    for (sku_a, sku_b), r in best.items():
        entry_a = {
            "sku": sku_b,
            "name": r.get("name_b", sku_b),
            "score": r.get("score", 0),
            "source": r.get("source", "unknown"),
        }
        per_sku.setdefault(sku_a, []).append(entry_a)

        entry_b = {
            "sku": sku_a,
            "name": r.get("name_a", sku_a),
            "score": r.get("score", 0),
            "source": r.get("source", "unknown"),
        }
        per_sku.setdefault(sku_b, []).append(entry_b)

    # Sort and trim each SKU's list
    sorted_result: Dict[str, List[Dict]] = {}
    for sku, entries in per_sku.items():
        # Sort by (source priority, score desc)
        entries.sort(
            key=lambda e: (
                ENGINE_PRIORITY.get(e["source"], 99),
                -e["score"],
            )
        )
        # Remove exact duplicate SKUs within the same source
        seen: Set[str] = set()
        deduped: List[Dict] = []
        for e in entries:
            if e["sku"] not in seen:
                seen.add(e["sku"])
                deduped.append(e)
        sorted_result[sku] = deduped[:top_n]

    total_pairs = sum(len(v) for v in sorted_result.values())
    logger.info("  -> %d pairs across %d SKUs", total_pairs, len(sorted_result))

    # Coverage stats
    full = sum(1 for v in sorted_result.values() if len(v) >= top_n)
    partial = sum(1 for v in sorted_result.values() if 0 < len(v) < top_n)
    zero = sum(1 for v in sorted_result.values() if len(v) == 0)
    if total_pairs:
        logger.info(
            "  -> coverage: %d SKUs with %d, %d with < %d, %d with 0",
            full,
            top_n,
            partial,
            top_n,
            zero,
        )

    return sorted_result
