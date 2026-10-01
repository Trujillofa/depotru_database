"""KPI SQL pack must exclude the canonical five test document codes."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SQL_PACK = ROOT / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
CANONICAL = ("XY", "AS", "TS", "YX", "ISC")


@pytest.mark.unit
def test_kpi_sql_pack_sales_filters_use_five_codes():
    text = SQL_PACK.read_text(encoding="utf-8")
    assert "NOT IN ('XY', 'AS', 'TS')" not in text
    five = "NOT IN ('XY', 'AS', 'TS', 'YX', 'ISC')"
    assert text.count(five) == 21
    for code in CANONICAL:
        assert f"'{code}'" in text
