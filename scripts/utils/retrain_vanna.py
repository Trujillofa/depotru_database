#!/usr/bin/env python3
"""
Refresh Vanna ChromaDB training data (schema + SQL examples).

Run after updating training.py or when cached embeddings are stale:
  PYTHONPATH=src python scripts/utils/retrain_vanna.py
  PYTHONPATH=src python scripts/utils/retrain_vanna.py --reset
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from business_analyzer.ai import AIVanna, full_training  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Retrain Vanna on SmartBusiness schema"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove existing training data before retraining",
    )
    parser.add_argument(
        "--schema",
        default="SmartBusiness",
        help="Database schema name (default: SmartBusiness)",
    )
    args = parser.parse_args(argv)

    vn = AIVanna()
    vn.connect_to_mssql_odbc()

    if args.reset:
        try:
            vn.remove_training_data()
            print("✓ Removed existing training data")
        except Exception as exc:
            print(f"⚠️ Could not remove training data: {exc}")

    full_training(vn, schema_name=args.schema)
    print("✓ Retrain complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
