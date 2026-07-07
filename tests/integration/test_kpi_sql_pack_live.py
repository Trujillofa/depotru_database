"""Live execution of KPI pack queries Q9–Q12 (requires MSSQL)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.utils.generate_kpi_control_board import (  # noqa: E402
    execute_query,
    get_connection,
    load_query_blocks,
    render_query,
)

SQL_PACK = ROOT / "scripts" / "analysis" / "kpi_sql_pack.sql.template"
START_DATE = "2024-12-01"
END_DATE = "2024-12-31"


@pytest.fixture(scope="module")
def db_conn():
    conn = get_connection()
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def query_blocks():
    return load_query_blocks(SQL_PACK)


@pytest.mark.requires_db
@pytest.mark.integration
def test_q9_cartera_dso_returns_snapshot(db_conn, query_blocks):
    sql = render_query(query_blocks["Q9"], START_DATE, END_DATE)
    rows = execute_query(db_conn, sql)
    assert len(rows) == 1
    assert rows[0]["DSO_Dias"] is not None
    assert float(rows[0]["DSO_Dias"]) >= 0


@pytest.mark.requires_db
@pytest.mark.integration
def test_q10_presupuesto_vs_real_columns(db_conn, query_blocks):
    sql = render_query(query_blocks["Q10"], START_DATE, END_DATE)
    rows = execute_query(db_conn, sql)
    if rows:
        row = rows[0]
        assert "Meta_Prorrateada" in row
        assert "Ventas_MTD" in row
        assert "Cumplimiento_Prorrateado_Pct" in row


@pytest.mark.requires_db
@pytest.mark.integration
def test_q11_marca_real_returns_rows(db_conn, query_blocks):
    sql = render_query(query_blocks["Q11"], START_DATE, END_DATE)
    rows = execute_query(db_conn, sql)
    assert rows
    assert "Marca" in rows[0]
    assert "Ganancia_Bruta" in rows[0]


@pytest.mark.requires_db
@pytest.mark.integration
def test_q12_cotizacion_funnel_vendor_metrics(db_conn, query_blocks):
    sql = render_query(query_blocks["Q12"], START_DATE, END_DATE)
    rows = execute_query(db_conn, sql)
    assert rows
    row = rows[0]
    assert "Cotizaciones" in row
    assert "Convertidas" in row
    assert "Tasa_Conversion_Pct" in row
    rate = float(row["Tasa_Conversion_Pct"])
    assert 0 <= rate <= 100
