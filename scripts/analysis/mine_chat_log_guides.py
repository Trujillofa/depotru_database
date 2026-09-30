#!/usr/bin/env python3
"""CLI wrapper: mine chat_log.jsonl for unmatched assistant problem guides."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from business_analyzer.jobs.chat_log_guides import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
