#!/usr/bin/env python3
"""
Cron-friendly wrapper for the sales anomaly worker.

Example cron (daily at 7:00):
  0 7 * * * cd /path/to/depotru_database && PYTHONPATH=src python scripts/utils/run_scheduled_anomaly_check.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts" / "utils"))

from anomaly_worker import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
