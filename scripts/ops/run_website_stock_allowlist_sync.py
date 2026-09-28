#!/usr/bin/env python3
"""Scheduled job: re-apply J3 website warehouse allowlist to Magento MSI.

Counteracts b2c.smart-business re-push of denylist warehouses until B2C is
configured. Safe to run repeatedly (idempotent target qty from J3).

Usage:
  PYTHONPATH=src python scripts/ops/run_website_stock_allowlist_sync.py
  PYTHONPATH=src python scripts/ops/run_website_stock_allowlist_sync.py --dry-run

``--dry-run`` skips the J3 payload query and never SSH/writes Magento.
To inspect a payload locally, call ``build_excluded_payload`` /
``apply_payload_via_ssh(..., dry_run=True)`` instead.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Repo root on path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from business_analyzer.core.website_stock_magento_ssh import (  # noqa: E402
    MagentoSshConfig,
    apply_payload_via_ssh,
    build_excluded_payload,
)
from business_analyzer.core.website_warehouse_policy import policy_summary  # noqa: E402

LOG_DIR = Path.home() / "business_reports"
DEFAULT_LOG = LOG_DIR / "website_stock_allowlist_sync.log"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync Magento MSI to J3 website allowlist stock (#182)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip J3 payload build and Magento SSH/writes (local only)",
    )
    parser.add_argument(
        "--min-excluded",
        type=float,
        default=0.01,
        help="Min denylist qty to include SKU (default 0.01)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=5000,
        help="Max SKUs to process (default 5000)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=40,
        help="Magento apply batch size",
    )
    parser.add_argument(
        "--no-reindex",
        action="store_true",
        help="Skip inventory reindex after apply",
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
    log = logging.getLogger("website_stock_sync")

    # --dry-run is a local no-op: skip the expensive J3 query and never SSH.
    if args.dry_run:
        log.info("Dry-run: skipping J3 payload build and Magento SSH")
        result = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "mode": "dry-run",
            "ssh": False,
            "updated_skus": 0,
            "updated_items": 0,
            "errors": [],
            "note": "dry-run: skipped J3 payload build; no SSH and no Magento writes",
            "policy": policy_summary(),
        }
    else:
        cfg = MagentoSshConfig.from_env()
        if not cfg:
            log.error("Magento SSH not configured (MAGENTO_SSH_* or MAGENTO_ENV_PHP)")
            return 2

        log.info("Building J3 payload (denylist-affected SKUs)...")
        payload = build_excluded_payload(
            top_n=args.top_n, min_excluded=args.min_excluded
        )
        log.info(
            "payload_skus=%s only_denylist=%s",
            len(payload),
            sum(1 for p in payload if float(p.get("website_qty") or 0) <= 0),
        )

        if not payload:
            log.info("Nothing to apply")
            result = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "updated_skus": 0,
                "note": "empty payload",
                "policy": policy_summary(),
            }
        else:
            result = apply_payload_via_ssh(
                payload,
                cfg=cfg,
                dry_run=False,
                batch_size=args.batch_size,
                reindex=not args.no_reindex,
            )
            result["ts"] = datetime.now(timezone.utc).isoformat()
            result["policy_denylist"] = policy_summary()["denylist"]
            result["payload_skus"] = len(payload)

    log.info(
        "done mode=%s updated_skus=%s updated_items=%s errors=%s",
        result.get("mode"),
        result.get("updated_skus"),
        result.get("updated_items"),
        len(result.get("errors") or []),
    )

    log_path = Path(args.log_file).expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, default=str, ensure_ascii=False) + "\n")
    log.info("appended %s", log_path)

    # Non-zero if hard failures
    errors = result.get("errors") or []
    if errors and result.get("updated_skus", 0) == 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
