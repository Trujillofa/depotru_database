"""Structural + unit tests for the live DB table decision summary deliverable.

Drives real shipped helpers in ``scripts.utils.introspect_table_sizes`` and
asserts the decision-making report under ``reports/`` covers every known
SmartBusiness table and documents the live J3 inventory shape.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

from scripts.utils.introspect_table_sizes import (
    fetch_column_summary,
    fetch_table_sizes,
    introspect_database,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SUMMARY_PATH = REPO_ROOT / "reports" / "DATABASE_TABLE_DECISION_SUMMARY.md"

# Canonical SmartBusiness user tables (live inventory 2026-07-29: 8 tables)
SMARTBUSINESS_TABLES = (
    "banco_datos",
    "productos_adicional",
    "banco_cartera",
    "presupuesto_lineas",
    "presupuesto_lineas_copy1",
    "presupuesto_lineas_copy2",
    "presupuesto_vendedores",
    "presupuesto_vendedores_copy1",
)

# Decision-critical J3 tables that must appear with purpose notes
J3_DECISION_TABLES = (
    "InvVentas",
    "InvVentasDetalle",
    "InvCotizaCab",
    "InvCotizaDetalle",
    "InvHistoricoEntregas",
    "InvDetalleExistencias",
    "InvDevolucionVentas",
    "InvEstadoFacturaElectronica",
    "CarCarteraCliente",
    "ConMovimientoDetalle",
    "AdmTerceros",
    "AdmAlmacen",
    "AdmArticulos",
)


def _summary_text() -> str:
    assert SUMMARY_PATH.is_file(), f"Missing decision summary: {SUMMARY_PATH}"
    return SUMMARY_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Shipped introspect helpers (real functions, mocked DB cursor)
# ---------------------------------------------------------------------------


def test_fetch_table_sizes_executes_catalog_sql_and_returns_rows():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    expected = [
        {
            "schema_name": "dbo",
            "table_name": "banco_datos",
            "row_count": 1_582_580,
            "total_space_kb": 1_061_256,
            "used_space_kb": 1_061_088,
        }
    ]
    cursor.__iter__ = MagicMock(return_value=iter(expected))

    rows = fetch_table_sizes(conn)

    conn.cursor.assert_called_once_with(as_dict=True)
    cursor.execute.assert_called_once()
    sql = cursor.execute.call_args[0][0]
    assert "sys.tables" in sql
    assert "total_space_kb" in sql
    assert rows == expected
    cursor.close.assert_called_once()


def test_fetch_column_summary_parameterizes_schema_and_table():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    expected = [
        {
            "column_name": "Fecha",
            "data_type": "date",
            "max_length": None,
            "is_nullable": "NO",
        }
    ]
    cursor.__iter__ = MagicMock(return_value=iter(expected))

    rows = fetch_column_summary(conn, "dbo", "banco_datos")

    cursor.execute.assert_called_once()
    args = cursor.execute.call_args[0]
    assert "INFORMATION_SCHEMA.COLUMNS" in args[0]
    assert args[1] == ("dbo", "banco_datos")
    assert rows == expected


def test_introspect_database_schema_limit_none_describes_all_tables(monkeypatch):
    """schema_limit=None must describe every size row (SmartBusiness path)."""
    sizes = [
        {
            "schema_name": "dbo",
            "table_name": "banco_datos",
            "row_count": 10,
            "total_space_kb": 100,
            "used_space_kb": 90,
        },
        {
            "schema_name": "dbo",
            "table_name": "banco_cartera",
            "row_count": 5,
            "total_space_kb": 20,
            "used_space_kb": 10,
        },
    ]
    described: list[tuple[str, str]] = []

    def fake_sizes(_conn):
        return list(sizes)

    def fake_cols(_conn, schema, table):
        described.append((schema, table))
        return [
            {
                "column_name": "id",
                "data_type": "int",
                "max_length": None,
                "is_nullable": "NO",
            }
        ]

    monkeypatch.setattr(
        "scripts.utils.introspect_table_sizes.fetch_table_sizes", fake_sizes
    )
    monkeypatch.setattr(
        "scripts.utils.introspect_table_sizes.fetch_column_summary", fake_cols
    )

    db = MagicMock()
    # Return a name that is not SmartBusiness so the non-J3 connect path is used
    # when database_name is SmartBusiness (compare uses validated J3 name).
    db.validate_sql_identifier.return_value = "J3System"
    db._connection = MagicMock()
    payload = introspect_database(db, "SmartBusiness", schema_limit=None)

    assert payload["table_count"] == 2
    assert payload["schema_table_count"] == 2
    assert set(payload["top_10_schema"]) == {
        "dbo.banco_datos",
        "dbo.banco_cartera",
    }
    assert described == [("dbo", "banco_datos"), ("dbo", "banco_cartera")]
    db.connect.assert_called_once()


def test_introspect_database_schema_limit_caps_describes(monkeypatch):
    sizes = [
        {
            "schema_name": "dbo",
            "table_name": f"t{i}",
            "row_count": 100 - i,
            "total_space_kb": 1000 - i,
            "used_space_kb": 900 - i,
        }
        for i in range(5)
    ]
    described: list[str] = []

    monkeypatch.setattr(
        "scripts.utils.introspect_table_sizes.fetch_table_sizes",
        lambda _c: list(sizes),
    )
    monkeypatch.setattr(
        "scripts.utils.introspect_table_sizes.fetch_column_summary",
        lambda _c, _s, t: described.append(t) or [],
    )

    db = MagicMock()
    db.validate_sql_identifier.return_value = "J3System"
    db._connection = MagicMock()
    payload = introspect_database(db, "SmartBusiness", schema_limit=2)

    assert payload["table_count"] == 5
    assert payload["schema_table_count"] == 2
    assert described == ["t0", "t1"]


# ---------------------------------------------------------------------------
# Decision summary deliverable (static/structural on shipped markdown)
# ---------------------------------------------------------------------------


def test_decision_summary_exists_with_executive_framing():
    text = _summary_text()
    assert "Executive framing" in text or "decision makers" in text.lower()
    assert "SmartBusiness" in text
    assert "J3System" in text
    assert "DocumentosCodigo" in text


def test_decision_summary_explains_every_smartbusiness_table():
    text = _summary_text()
    for name in SMARTBUSINESS_TABLES:
        assert f"`{name}`" in text, f"Missing SmartBusiness table {name}"
        # Each table has a dedicated subsection with decision language
        assert re.search(
            rf"### `{re.escape(name)}`", text
        ), f"Missing decision subsection for {name}"
        # Purpose / decisions fields present near the heading
        idx = text.index(f"### `{name}`")
        chunk = text[idx : idx + 1200]
        assert "How it helps decisions" in chunk or "decisions" in chunk.lower()
        assert "Rows / size" in chunk or "rows" in chunk.lower()


def test_decision_summary_embeds_live_smartbusiness_row_counts():
    """Partition-correct live numbers (2026-07-29 re-run after allocation_units fix)."""
    text = _summary_text()
    # banco_datos (no LOB inflation historically; still ~1.58M)
    assert "1,582,580" in text or "1582580" in text
    # productos_adicional must be partition truth (7,133), NOT allocation-inflated 14,266
    assert "7,133" in text or "7133" in text
    assert "14,266" not in text and "14266" not in text
    assert "banco_cartera" in text
    assert re.search(r"\*\*8\*\*.*tables|table_count this run: \*\*8\*\*", text)


def test_decision_summary_covers_j3_inventory_and_decision_tables():
    text = _summary_text()
    assert re.search(r"\*\*968\*\*|table_count this run: \*\*968\*\*", text)
    assert "InvVentas" in text
    # Partition-correct InvVentas rows (563,106) — NOT allocation-inflated 1,689,318
    assert "563,106" in text or "563106" in text
    assert "1,689,318" not in text and "1689318" not in text
    # AdmTerceros partition truth (60,997) — NOT 182,991
    assert "60,997" in text or "60997" in text
    assert "182,991" not in text and "182991" not in text
    for name in J3_DECISION_TABLES:
        assert f"`{name}`" in text, f"Missing decision-critical J3 table {name}"
    assert "Complete J3System table appendix" in text
    assert "domain" in text.lower()
    assert "partition" in text.lower() or "allocation" in text.lower()


def test_decision_summary_is_not_only_stale_recommendations_copy():
    """New summary must be distinct from the 2026-07-07 recommendations doc."""
    text = _summary_text()
    stale = (
        REPO_ROOT / "reports" / "DATABASE_TABLE_ANALYSIS_RECOMMENDATIONS.md"
    ).read_text(encoding="utf-8")
    assert text != stale
    assert "2026-07-29" in text or "Live inventory date" in text
    # Stale report said 1,558,240 for banco_datos — new must prefer live figure
    assert "1,558,240" not in text or "1,582,580" in text


def test_decision_summary_mentions_decision_gaps():
    text = _summary_text().lower()
    assert "cartera" in text
    assert "presupuesto" in text
    assert "gap" in text or "underused" in text
    assert "cotiza" in text or "quotation" in text or "quote" in text
