#!/usr/bin/env python3
"""Scheduled / CLI wrapper for the Monday cash pack (draft by default)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from business_analyzer.jobs.monday_cash_pack import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
