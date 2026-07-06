"""
Product Affinity — Hybrid Pipeline CLI
========================================

Orchestrates multiple product-relationship engines, blends them by priority,
and produces CSV output.

Usage:
    DB_TIMEOUT=300 python -m src.business_analyzer.analysis.affinity
"""

import csv
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Ensure src/ is on the path
_src = str(Path(__file__).resolve().parent.parent.parent)
if _src not in sys.path:
    sys.path.insert(0, _src)

from business_analyzer.analysis.blender import merge
from business_analyzer.analysis.engines import (
    EXCLUDED_CODES,
    EXCLUDED_SKUS,
    MATRIX_MIN_SALES,
)
from business_analyzer.analysis.engines.category_fallback import (
    run as run_category_fallback,
)

# ── Engine imports ────────────────────────────────────────────────────────
from business_analyzer.analysis.engines.co_occurrence import run as run_co_occurrence
from business_analyzer.analysis.engines.customer_affinity import (
    run as run_customer_affinity,
)
from business_analyzer.analysis.engines.text_similarity import (
    run as run_text_similarity,
)
from business_analyzer.core.database import ConnectionType, Database
from business_analyzer.core.paths import resolve_output_dir

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────
OUTPUT_DIR = resolve_output_dir()
TOP_N = 10
MATRIX_MIN_SALES = int(os.getenv("MATRIX_MIN_SALES", "10"))
LONG_TAIL_MODE = os.getenv("LONG_TAIL_MODE", "").lower() in ("1", "true", "yes")


def run_all_engines(
    db: Database,
    active_skus: set,
    sku_names: dict,
    long_tail: bool = False,
) -> Dict[str, List[Dict]]:
    """Run all affinity engines and return results keyed by source name.

    When *long_tail* is True, skips engines that depend on co-occurrence
    (A and C) and runs only metadata-based engines (B and D) so that SKUs
    with very few sales still get related products.
    """
    results: Dict[str, List[Dict]] = {}

    if not long_tail:
        # Engine A — ticket-level co-occurrence (needs sales data)
        try:
            results["co_occurrence"] = run_co_occurrence(db, active_skus=active_skus)
        except Exception as e:
            logger.error("[Engine A] Failed: %s", e)
    else:
        logger.info("Long-tail mode: skipping Engine A (co-occurrence)")

    # Engine B — TF-IDF text similarity (works on metadata, no sales needed)
    try:
        results["text_similarity"] = run_text_similarity(db, active_skus=active_skus)
    except Exception as e:
        logger.error("[Engine B] Failed: %s", e)

    if not long_tail:
        # Engine C — customer-level co-occurrence (needs sales data)
        try:
            results["customer_affinity"] = run_customer_affinity(
                db, active_skus=active_skus, window_days=30
            )
        except Exception as e:
            logger.error("[Engine C] Failed: %s", e)
    else:
        logger.info("Long-tail mode: skipping Engine C (customer affinity)")

    # Engine D — category/subcategory fallback (works on metadata)
    try:
        results["category_fallback"] = run_category_fallback(
            db, active_skus=active_skus
        )
    except Exception as e:
        logger.error("[Engine D] Failed: %s", e)

    return results


def save_top_related_csv(
    top_related: Dict[str, List[Dict]],
    sku_sales: Dict[str, int],
    sku_names: Dict[str, str],
    output_path: Path,
    top_n: int = TOP_N,
):
    """Save top-N per SKU with Source column."""
    logger.info("Writing top-%d per SKU to %s …", top_n, output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sorted_skus = sorted(
        top_related.keys(),
        key=lambda s: -sku_sales.get(s, 0),
    )

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = ["SKU", "Nombre_Producto", "Ventas_Totales"]
        for i in range(1, top_n + 1):
            header += [
                f"Rel_{i}_SKU",
                f"Rel_{i}_Nombre",
                f"Rel_{i}_Score",
                f"Rel_{i}_Source",
            ]
        writer.writerow(header)

        for sku in sorted_skus:
            row = [sku, sku_names.get(sku, ""), sku_sales.get(sku, 0)]
            for rel in top_related.get(sku, []):
                row += [rel["sku"], rel["name"], rel["score"], rel["source"]]
            remaining = top_n - len(top_related.get(sku, []))
            for _ in range(remaining):
                row += ["", "", "", ""]
            writer.writerow(row)

    file_size = output_path.stat().st_size
    logger.info("  -> %.1f MB written", file_size / (1024 * 1024))


def generate_sku_sales_sql() -> str:
    """Count total sales per SKU."""
    excl_doc = ", ".join(f"'{c}'" for c in EXCLUDED_CODES)
    excl_sku = ", ".join(f"'{s}'" for s in EXCLUDED_SKUS)
    return f"""
    SELECT
        ArticulosCodigo  AS sku,
        ArticulosNombre  AS name,
        COUNT(*)         AS total_sales
    FROM [SmartBusiness].[dbo].[banco_datos]
    WHERE DocumentosCodigo NOT IN ({excl_doc})
      AND ArticulosCodigo IS NOT NULL
      AND ArticulosCodigo <> ''
      AND ArticulosCodigo NOT IN ({excl_sku})
    GROUP BY ArticulosCodigo, ArticulosNombre
    ORDER BY total_sales DESC
    """


def fetch_sku_metadata(db: Database) -> tuple:
    """Fetch sku_sales and sku_names dicts."""
    raw = db.execute_query(generate_sku_sales_sql())
    rows: List[Dict] = raw if isinstance(raw, list) else []
    sku_sales: Dict[str, int] = {}
    sku_names: Dict[str, str] = {}
    for r in rows:
        sku = r["sku"].strip()
        sku_sales[sku] = r["total_sales"]
        sku_names[sku] = r["name"]
    return sku_sales, sku_names


def print_summary(
    top_related: Dict[str, List[Dict]],
    sku_sales: Dict[str, int],
    sku_names: Dict[str, str],
    top_n: int = 5,
):
    """Print human-readable summary for the top-20 best-selling SKUs."""
    sorted_skus = sorted(
        top_related.keys(),
        key=lambda s: -sku_sales.get(s, 0),
    )[:20]

    print("\n" + "=" * 90)
    print("  TOP SELLING SKUs — Top 5 Related Products (blended)")
    print("=" * 90)
    for sku in sorted_skus:
        name = sku_names.get(sku, "")
        sales = sku_sales.get(sku, 0)
        print(f"\n  {sku} — {name}  ({sales:,} ventas)")
        for i, rel in enumerate(top_related.get(sku, [])[:5], 1):
            print(
                f"    {i}. {rel['sku']} — {rel['name']}  "
                f"(score={rel['score']}, source={rel['source']})"
            )
        if not top_related.get(sku):
            print("    (sin relaciones)")


def main():
    t_start = time.time()

    logger.info("=" * 60)
    logger.info("HYBRID PRODUCT AFFINITY PIPELINE")
    logger.info("=" * 60)

    output_dir = resolve_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Connect
    db = Database(connection_type=ConnectionType.DIRECT)
    try:
        db.connect()
    except Exception as e:
        logger.error("Database connection failed: %s", e)
        sys.exit(1)

    # Fetch SKU metadata
    sku_sales, sku_names = fetch_sku_metadata(db)
    active_count = sum(1 for s in sku_sales.values() if s >= MATRIX_MIN_SALES)
    logger.info(
        "SKU metadata: %d total, %d with >= %d sales",
        len(sku_sales),
        active_count,
        MATRIX_MIN_SALES,
    )

    effective_min_sales = 0 if LONG_TAIL_MODE else MATRIX_MIN_SALES
    active_set = {s for s, c in sku_sales.items() if c >= effective_min_sales}
    if LONG_TAIL_MODE:
        logger.info(
            "Long-tail mode: processing ALL %d SKUs (B + D only)",
            len(active_set),
        )
    else:
        logger.info("Active SKUs (>= %d sales): %d", MATRIX_MIN_SALES, len(active_set))

    # Run all engines
    engine_results = run_all_engines(
        db, active_skus=active_set, sku_names=sku_names, long_tail=LONG_TAIL_MODE
    )

    db.close()

    # Blender: merge by priority
    top_related = merge(engine_results, top_n=TOP_N)

    # Coverage stats
    full = sum(1 for v in top_related.values() if len(v) >= TOP_N)
    partial = sum(1 for v in top_related.values() if 0 < len(v) < TOP_N)
    zero = sum(1 for v in top_related.values() if len(v) == 0)
    logger.info(
        "COVERAGE: %d SKUs with %d related, %d with < %d, %d with 0",
        full,
        TOP_N,
        partial,
        TOP_N,
        zero,
    )

    # Save output
    csv_name = (
        "top_10_related_products_all_skus.csv"
        if LONG_TAIL_MODE
        else "top_10_related_products_per_sku.csv"
    )
    top_path = output_dir / csv_name
    save_top_related_csv(top_related, sku_sales, sku_names, top_path, top_n=TOP_N)

    # Save per-source stats
    for source, results in engine_results.items():
        n_skus = len(
            set(r["sku_a"] for r in results) | set(r.get("sku_b", "") for r in results)
        )
        logger.info("  Engine %s: %d pairs, ~%d SKUs", source, len(results), n_skus)

    # Summary
    print_summary(top_related, sku_sales, sku_names)

    total_time = time.time() - t_start
    logger.info("=" * 60)
    logger.info("DONE in %.1f s", total_time)
    logger.info("Output: %s", top_path)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
