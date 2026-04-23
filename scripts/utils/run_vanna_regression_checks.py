#!/usr/bin/env python3
"""
Run repeatable NL→SQL regression checks for Vanna.

This script validates that:
1) SQL generation succeeds for a fixed question suite.
2) Generated SQL contains the critical DocumentosCodigo exclusion filter.
3) SQL execution returns non-empty result sets.

Usage:
    python scripts/utils/run_vanna_regression_checks.py
    python scripts/utils/run_vanna_regression_checks.py --training-file data/autoresearch_vanna_examples.jsonl
    python scripts/utils/run_vanna_regression_checks.py --skip-training
"""

import argparse
import contextlib
import io
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.vanna_grok import EnhancedAIVanna, clean_sql, train_vanna  # noqa: E402

REGRESSION_QUESTIONS = [
    "Top 10 productos más vendidos por facturación este año",
    "Top proveedores por facturación",
    "Margen de ganancia promedio por subcategoría",
    "Clientes más rentables por ganancia",
    "Ventas mensuales por categoría en 2025",
]

DOC_FILTER = "DocumentosCodigo NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--training-file",
        default="data/autoresearch_vanna_examples.jsonl",
        help="Path to external training JSONL file used by full_training.",
    )
    parser.add_argument(
        "--min-rows",
        type=int,
        default=1,
        help="Minimum rows required per query to pass.",
    )
    parser.add_argument(
        "--skip-training",
        action="store_true",
        help="Skip train_vanna() before checks (faster, less deterministic).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    training_file = Path(args.training_file)
    if not training_file.is_absolute():
        training_file = PROJECT_ROOT / training_file

    if training_file.exists():
        os.environ["AUTORESEARCH_TRAINING_FILE"] = str(training_file.resolve())
        print(f"Using external training file: {training_file.resolve()}")
    else:
        print(f"External training file not found: {training_file}")
        print("Continuing with default internal examples only.")

    vn = EnhancedAIVanna()
    vn.connect_to_mssql_odbc()

    if not args.skip_training:
        train_vanna(vn)
    else:
        print("Skipping training step (--skip-training).")

    print("\nQUESTION|FILTER|ROWS|STATUS")
    failures = []

    for question in REGRESSION_QUESTIONS:
        try:
            sink = io.StringIO()
            with contextlib.redirect_stdout(sink):
                raw_sql = vn.generate_sql(question=question, allow_llm_to_see_data=True)

            if not raw_sql:
                status = "GENERATION_FAILED"
                print(f"{question}|NO|0|{status}")
                failures.append((question, status))
                continue

            sql = clean_sql(raw_sql)
            has_filter = DOC_FILTER in sql

            df = vn.run_sql(sql)
            rows = 0 if df is None else len(df)

            if not has_filter:
                status = "MISSING_FILTER"
                failures.append((question, status))
            elif rows < args.min_rows:
                status = "EMPTY"
                failures.append((question, status))
            else:
                status = "OK"

            print(f"{question}|{'YES' if has_filter else 'NO'}|{rows}|{status}")
        except Exception as exc:
            status = f"ERROR:{type(exc).__name__}"
            print(f"{question}|NO|0|{status}")
            failures.append((question, status))

    print("\nSummary")
    print("-" * 80)
    if not failures:
        print("PASS: all regression checks succeeded.")
        return 0

    print(f"FAIL: {len(failures)} checks failed.")
    for question, reason in failures:
        print(f"- {reason}: {question}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
