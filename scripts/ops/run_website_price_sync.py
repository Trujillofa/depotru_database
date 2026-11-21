#!/usr/bin/env python3
"""Sync Magento list prices from J3 ArticulosVenta × 1.19 IVA.

Default is dry-run (no Magento writes). Pass --apply to write via
BasePriceStorageInterface over SSH. Never cache:flush.

Usage:
  PYTHONPATH=src python scripts/ops/run_website_price_sync.py
  PYTHONPATH=src python scripts/ops/run_website_price_sync.py --apply
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from business_analyzer.core.website_price_magento_ssh import (  # noqa: E402
    apply_price_payload_via_ssh,
    build_drift_payload,
)
from business_analyzer.core.website_price_policy import payload_stats  # noqa: E402
from business_analyzer.core.website_stock_magento_ssh import (  # noqa: E402
    MagentoSshConfig,
)

LOG_DIR = Path.home() / "business_reports"
DEFAULT_LOG = LOG_DIR / "website_price_sync.log"
DEFAULT_CSV = LOG_DIR / "website_price_sync_dryrun.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync Magento prices from J3 ArticulosVenta × 1.19 (dry-run default)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write Magento base prices (default: dry-run only)",
    )
    parser.add_argument(
        "--sku",
        action="append",
        default=[],
        help="Limit to SKU (repeatable)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=0,
        help="Cap payload size after sort-by-|delta| (0 = all drifted)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=80,
        help="Magento apply batch size",
    )
    parser.add_argument(
        "--no-reindex",
        action="store_true",
        help="Skip catalog_product_price reindex after apply",
    )
    parser.add_argument(
        "--csv",
        default=str(DEFAULT_CSV),
        help=f"Write drift CSV (default {DEFAULT_CSV})",
    )
    parser.add_argument(
        "--log-file",
        default=str(DEFAULT_LOG),
        help=f"Append JSONL result (default {DEFAULT_LOG})",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    log = logging.getLogger("website_price_sync")
    dry_run = not args.apply

    cfg = MagentoSshConfig.from_env()
    if not cfg and args.apply:
        log.error("Magento SSH not configured (MAGENTO_SSH_* or MAGENTO_ENV_PHP)")
        return 2

    log.info("Building J3 vs Magento price payload (dry_run=%s)", dry_run)
    payload = build_drift_payload(cfg=cfg)
    if args.sku:
        wanted = {s.strip() for s in args.sku if s.strip()}
        payload = [row for row in payload if row.get("sku") in wanted]
    if args.top_n and args.top_n > 0:
        payload = payload[: int(args.top_n)]

    stats = payload_stats(payload)
    log.info(
        "payload_skus=%s min_abs_delta=%s max_abs_delta=%s median_abs_delta=%s",
        stats["payload_skus"],
        stats["min_abs_delta"],
        stats["max_abs_delta"],
        stats["median_abs_delta"],
    )

    csv_path = Path(args.csv).expanduser()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["sku", "j3_venta", "magento_price", "target", "delta"],
        )
        writer.writeheader()
        for row in payload:
            writer.writerow(
                {
                    "sku": row.get("sku"),
                    "j3_venta": row.get("j3_venta"),
                    "magento_price": row.get("magento_price"),
                    "target": row.get("target"),
                    "delta": row.get("delta"),
                }
            )
    log.info("wrote %s rows=%s", csv_path, len(payload))

    result = apply_price_payload_via_ssh(
        payload,
        cfg=cfg,
        dry_run=dry_run,
        batch_size=args.batch_size,
        reindex=not args.no_reindex and not dry_run,
    )
    result["ts"] = datetime.now(timezone.utc).isoformat()
    result["csv"] = str(csv_path)
    result["formula"] = "round(AdmArticulos.ArticulosVenta * 1.19)"
    result["payload_skus"] = len(payload)
    if payload:
        result["sample"] = [
            {
                "sku": r["sku"],
                "j3_venta": str(r.get("j3_venta")),
                "magento_price": str(r.get("magento_price")),
                "target": r.get("target"),
                "delta": r.get("delta"),
            }
            for r in payload[:8]
        ]

    log.info(
        "done mode=%s updated_skus=%s errors=%s",
        result.get("mode"),
        result.get("updated_skus"),
        len(result.get("errors") or []),
    )

    log_path = Path(args.log_file).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, default=str, ensure_ascii=False) + "\n")
    log.info("appended %s", log_path)

    errors = result.get("errors") or []
    if args.apply and errors and result.get("updated_skus", 0) == 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
