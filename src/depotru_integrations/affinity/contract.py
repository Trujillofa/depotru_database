"""Versioned CSV contract between depotru_database and depositotrujillo.co.

Producer: ``business_analyzer.analysis.magento_related_export``
Consumer: ``scripts/catalog/apply_crosssell_merge_bulk.py`` and
          ``scripts/one-off/import_related_products.py`` (Magento ops repo)

Contract version bumps when column sets or semantics change.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

# Bump when Magento import scripts must change.
AFFINITY_CONTRACT_VERSION = "1.0.0"

# Related products CSV (import_related_products.py style)
# Header: SKU, Rel_1_SKU, Rel_2_SKU, ... Rel_N_SKU
RELATED_CSV_COLUMNS_PREFIX = "SKU"
RELATED_REL_TEMPLATE = "Rel_{i}_SKU"
RELATED_DEFAULT_N = 10

# Cross-sell batch CSV (apply_crosssell_merge_bulk.py)
# Header: sku,crosssell_skus[,upsell_skus]
CROSSSELL_CSV_COLUMNS: Tuple[str, ...] = ("sku", "crosssell_skus")
CROSSSELL_OPTIONAL_COLUMNS: Tuple[str, ...] = ("upsell_skus",)

# Policies documented for both sides
RELATED_POLICY = "fill_empty_only"
CROSSSELL_POLICY = "merge"

MANIFEST_SCHEMA = {
    "contract_version": AFFINITY_CONTRACT_VERSION,
    "related_policy": RELATED_POLICY,
    "crosssell_policy": CROSSSELL_POLICY,
    "producer": "depotru_database.magento_related_export",
    "consumer_hint": "depositotrujillo.co/scripts/catalog/apply_crosssell_merge_bulk.py",
}


def related_csv_columns(n: int = RELATED_DEFAULT_N) -> List[str]:
    cols = [RELATED_CSV_COLUMNS_PREFIX]
    for i in range(1, n + 1):
        cols.append(RELATED_REL_TEMPLATE.format(i=i))
    return cols


# Back-compat name used in __init__
RELATED_CSV_COLUMNS = related_csv_columns()


def validate_related_csv_header(
    header: Sequence[str],
    *,
    min_rel: int = 1,
) -> Tuple[bool, str]:
    if not header:
        return False, "empty header"
    normalized = [h.strip() for h in header]
    if normalized[0].upper() != "SKU":
        return False, f"first column must be SKU, got {normalized[0]!r}"
    rel_cols = [c for c in normalized[1:] if c.upper().startswith("REL_")]
    if len(rel_cols) < min_rel:
        return False, f"need at least {min_rel} Rel_N_SKU columns"
    return True, "ok"


def validate_crosssell_csv_header(header: Sequence[str]) -> Tuple[bool, str]:
    if not header:
        return False, "empty header"
    lower = {h.strip().lower() for h in header}
    if "sku" not in lower:
        return False, "missing sku column"
    if "crosssell_skus" not in lower:
        return False, "missing crosssell_skus column"
    return True, "ok"


def build_manifest(**extra: object) -> dict:
    """JSON manifest sidecar for affinity export batches."""
    out: dict = {str(k): v for k, v in MANIFEST_SCHEMA.items()}
    for key, value in extra.items():
        out[str(key)] = value
    return out


def assert_crosssell_rows(rows: Iterable[dict]) -> int:
    """Validate row dicts have sku + crosssell_skus; return count."""
    count = 0
    for row in rows:
        if not (row.get("sku") or row.get("SKU")):
            raise ValueError(f"row missing sku: {row!r}")
        if "crosssell_skus" not in row and "CROSSSELL_SKUS" not in row:
            raise ValueError(f"row missing crosssell_skus: {row!r}")
        count += 1
    return count
