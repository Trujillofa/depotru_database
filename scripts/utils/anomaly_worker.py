#!/usr/bin/env python3
"""
Anomaly Detection Background Worker.

Compares yesterday's sales vs 30-day moving average.
If drop > threshold_pct, logs alert (no Telegram/WhatsApp bot).

Usage:
  PYTHONPATH=src python scripts/utils/anomaly_worker.py
  PYTHONPATH=src python scripts/utils/anomaly_worker.py --threshold 25
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from business_analyzer.analysis.anomaly import check_sales_anomaly  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check daily sales anomaly")
    parser.add_argument(
        "--days-ago",
        type=int,
        default=1,
        help="How many days back to compare (default: 1 = yesterday)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=20.0,
        help="Alert when drop exceeds this percent (default: 20)",
    )
    args = parser.parse_args(argv)

    result = check_sales_anomaly(days_ago=args.days_ago, threshold_pct=args.threshold)
    y = result["yesterday_sales"]
    avg = result["avg_sales"]
    drop = result["drop_pct"]

    if result["anomaly"]:
        print(
            f"[ANOMALY] {result['target_date']}: "
            f"${y:,.2f} vs avg ${avg:,.2f}, drop {drop:.1f}% > {args.threshold:.1f}%"
        )
        return 1

    if avg == 0:
        print(
            f"[ANOMALY] {result['target_date']}: ${y:,.2f}, 30-day avg: N/A (no data)"
        )
        return 0

    print(
        f"[OK] {result['target_date']}: ${y:,.2f}, "
        f"30-day avg ${avg:,.2f}, drop {drop:.1f}%"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
