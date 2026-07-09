#!/usr/bin/env python3
"""
Export Magento-importable related + cross-sell pairs from hybrid affinity CSV.

Grounds recommendations in SmartBusiness sales affinity (co-occurrence first),
optionally merging brand-peer candidates from brand_link_fill. Does not apply
to Magento production — writes import artifacts only.

Usage:
  PYTHONPATH=src python scripts/analysis/export_magento_related_crosssell.py \\
    --affinity ~/business_reports/top_10_related_products_per_sku.csv \\
    --output-dir /tmp/improved_related_crosssell

  # With brand-peer fallbacks + sample SKU filter:
  PYTHONPATH=src python scripts/analysis/export_magento_related_crosssell.py \\
    --affinity ~/business_reports/top_10_related_products_per_sku.csv \\
    --brand-related path/to/brand-related-fill.csv \\
    --brand-crosssell path/to/import-batch-brand-crosssell.csv \\
    --sku 0010180015 --sku 0010240344 \\
    --output-dir ./out
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import sys
import types
from pathlib import Path

# Load pure export module without importing analysis package __init__
# (that package eagerly loads customer/DB modules and can circular-import config).
_REPO = Path(__file__).resolve().parents[2]
_MOD_PATH = (
    _REPO / "src" / "business_analyzer" / "analysis" / "magento_related_export.py"
)


def _load_export_module():
    for pkg_name in ("business_analyzer", "business_analyzer.analysis"):
        if pkg_name not in sys.modules:
            sys.modules[pkg_name] = types.ModuleType(pkg_name)
    name = "business_analyzer.analysis.magento_related_export"
    spec = importlib.util.spec_from_file_location(name, _MOD_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {_MOD_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_export = _load_export_module()
export_from_affinity_file = _export.export_from_affinity_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export Magento related/cross-sell from affinity CSV"
    )
    parser.add_argument(
        "--affinity",
        required=True,
        help="Hybrid affinity CSV (top_N related products per SKU)",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory for Magento import CSVs + audit",
    )
    parser.add_argument(
        "--brand-related",
        default=None,
        help="Optional brand_link_fill related CSV (SKU, Rel_i_SKU)",
    )
    parser.add_argument(
        "--brand-crosssell",
        default=None,
        help="Optional brand cross-sell batch (sku, crosssell_skus)",
    )
    parser.add_argument(
        "--batch-id",
        default="affinity-improved-related-crosssell",
        help="Batch id used in output filenames",
    )
    parser.add_argument(
        "--related-limit",
        type=int,
        default=10,
        help="Max related links per SKU (default 10)",
    )
    parser.add_argument(
        "--cross-limit",
        type=int,
        default=8,
        help="Max cross-sell links per SKU (default 8)",
    )
    parser.add_argument(
        "--sku",
        action="append",
        default=None,
        help="Optional source SKU filter (repeatable)",
    )
    args = parser.parse_args(argv)

    affinity = Path(args.affinity)
    if not affinity.is_file():
        logger.error("Affinity CSV not found: %s", affinity)
        return 1

    stats = export_from_affinity_file(
        affinity,
        Path(args.output_dir),
        brand_related_csv=Path(args.brand_related) if args.brand_related else None,
        brand_crosssell_csv=(
            Path(args.brand_crosssell) if args.brand_crosssell else None
        ),
        batch_id=args.batch_id,
        related_limit=args.related_limit,
        cross_limit=args.cross_limit,
        sku_filter=args.sku,
    )
    print("EXPORT_OK")
    for key, val in stats.items():
        print(f"  {key}: {val}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
