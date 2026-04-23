#!/usr/bin/env python3
"""
Generate KPI control board for the last completed week (Mon-Sun).

Typical usage (one command):
  python scripts/utils/run_weekly_kpi_board.py

This script is designed to run every Monday and will always generate
the board for the previous completed week.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.utils.generate_kpi_control_board import generate_kpi_control_board


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate weekly KPI board for the last completed week"
    )
    parser.add_argument(
        "--run-date",
        type=str,
        default=date.today().isoformat(),
        help="Reference date (YYYY-MM-DD). Default: today.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Optional custom output markdown path.",
    )
    parser.add_argument(
        "--print-cron",
        action="store_true",
        help="Print a ready-to-copy cron line for Monday automation.",
    )
    return parser.parse_args()


def get_last_completed_week_window(run_date: date) -> tuple[date, date]:
    current_week_monday = run_date - timedelta(days=run_date.weekday())
    previous_week_sunday = current_week_monday - timedelta(days=1)
    previous_week_monday = previous_week_sunday - timedelta(days=6)
    return previous_week_monday, previous_week_sunday


def cron_line() -> str:
    return (
        "0 7 * * MON "
        f"cd {ROOT_DIR} && "
        "python scripts/utils/run_weekly_kpi_board.py "
        ">> reports/kpi_automation.log 2>&1"
    )


def main() -> None:
    args = parse_args()

    if args.print_cron:
        print("Add this to crontab (runs every Monday at 07:00):")
        print(cron_line())
        return

    run_date = datetime.fromisoformat(args.run_date).date()
    start_date, end_date = get_last_completed_week_window(run_date)

    output_path = generate_kpi_control_board(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        output=args.output,
    )

    print(
        "✅ Weekly KPI board generated "
        f"for {start_date.isoformat()} to {end_date.isoformat()}: {output_path}"
    )


if __name__ == "__main__":
    main()
