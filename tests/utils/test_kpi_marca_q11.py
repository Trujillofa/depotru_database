"""Tests for Q11 marca real KPI pack block."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.utils.generate_kpi_control_board import load_query_blocks


def test_sql_pack_includes_q11_marca_real_join():
    blocks = load_query_blocks(
        ROOT / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
    )
    assert "Q11" in blocks
    sql = blocks["Q11"].upper()
    assert "PRODUCTOS_ADICIONAL" in sql
    assert "PRODUCTO_MARCA" in sql
    assert "MARCA_REAL" in sql
    assert sql.index("PRODUCTO_MARCA") < sql.index("BD.MARCA")
