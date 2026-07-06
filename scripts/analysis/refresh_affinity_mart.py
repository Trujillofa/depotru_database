#!/usr/bin/env python3
"""
Refresh the affinity co-occurrence mart table.

Prerequisites:
  1. Apply data/sql/affinity_indexes_and_mart.sql on SmartBusiness
  2. Configure DB_* or NCX_FILE_PATH in .env

Usage:
  PYTHONPATH=src python scripts/analysis/refresh_affinity_mart.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from business_analyzer.analysis.affinity_mart import (  # noqa: E402
    mart_table_exists,
    refresh_co_occurrence_mart,
)
from business_analyzer.core.database import Database  # noqa: E402


def main() -> int:
    with Database() as db:
        if not mart_table_exists(db):
            print(
                "Mart table not found. Run data/sql/affinity_indexes_and_mart.sql first.",
                file=sys.stderr,
            )
            return 1
        count = refresh_co_occurrence_mart(db)
    print(f"✓ Refreshed affinity_co_occurrence ({count} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
