#!/usr/bin/env python3
"""CLI: fill the TSOL-GENERAL ventas + inventario workbook."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from business_analyzer.reports.tsol_export import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
