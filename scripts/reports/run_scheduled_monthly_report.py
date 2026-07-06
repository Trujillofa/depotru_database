#!/usr/bin/env python3
"""
Generate the previous month's manager report and write outputs to OUTPUT_DIR.

Designed for cron/systemd scheduling, e.g.:
  0 6 1 * * cd /path/to/depotru_database && PYTHONPATH=src python scripts/reports/run_scheduled_monthly_report.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from business_analyzer.reports.monthly import main as monthly_main  # noqa: E402


def _previous_month(today: date | None = None) -> tuple[int, int]:
    today = today or date.today()
    if today.month == 1:
        return today.year - 1, 12
    return today.year, today.month - 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run scheduled monthly manager report")
    parser.add_argument(
        "--year", type=int, help="Report year (default: previous month)"
    )
    parser.add_argument(
        "--month", type=int, help="Report month 1-12 (default: previous month)"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "html", "pdf"],
        default="html",
        help="Output format (default: html)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory for report files (default: OUTPUT_DIR env or ~/business_reports)",
    )
    parser.add_argument(
        "--no-ai", action="store_true", help="Skip AI narrative generation"
    )
    parser.add_argument(
        "--no-j3system", action="store_true", help="Skip J3System enrichment"
    )
    args = parser.parse_args(argv)

    year, month = args.year, args.month
    if year is None or month is None:
        default_year, default_month = _previous_month()
        year = year or default_year
        month = month or default_month

    output_dir = Path(args.output_dir).expanduser() if args.output_dir else None
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = f"report_{year:04d}_{month:02d}"
        output = str(
            output_dir / f"{stem}.{args.format if args.format != 'text' else 'json'}"
        )
    else:
        output = None

    cli_args = [
        "--year",
        str(year),
        "--month",
        str(month),
        "--format",
        args.format,
    ]
    if output:
        cli_args.extend(["--output", output])
    if args.no_ai:
        cli_args.append("--no-ai")
    if args.no_j3system:
        cli_args.append("--no-j3system")

    sys.argv = ["depotru-report", *cli_args]
    monthly_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
