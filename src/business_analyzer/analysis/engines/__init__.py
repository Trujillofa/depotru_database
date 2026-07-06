"""
Engine package for the Hybrid Affinity Pipeline.

Each engine implements a distinct method for relating products:
    - co_occurrence:    Ticket-level co-occurrence (existing, high confidence)
    - text_similarity:  TF-IDF on product names + brand (medium confidence)
    - customer_affinity:Customer-level co-occurrence with time window (medium)
    - category_fallback: Subcategory -> Category hierarchy fallback (low)

All engines share the same output format:
    List[EngineResult] where EngineResult is a dict with keys:
        sku_a, sku_b, score (0.0-1.0), source (engine name tag)
"""

from typing import Any, Dict, List

# Shared type alias: each result row from any engine
EngineResult = Dict[str, Any]
#   { "sku_a": str, "sku_b": str, "name_a": str, "name_b": str,
#     "score": float, "source": str }

# Config shared across engines
EXCLUDED_CODES = ("XY", "AS", "TS", "YX", "ISC")
EXCLUDED_SKUS = ("0010040013", "0120010001")  # Bags/packaging
MATRIX_MIN_SALES = 10  # minimum total sales to include a SKU
