"""Canonical sales-document exclusions apply to both imported affinity readers."""

import sqlite3
from datetime import date

from business_analyzer.jobs import cross_sell_affinity as job
from depotru_integrations.j3 import affinity
from depotru_kernel.documents import (
    excluded_document_codes,
    excluded_document_sql_in_list,
)


def test_materialized_affinity_ignores_noncommercial_baskets(tmp_path):
    source = tmp_path / "source.sqlite3"
    target = tmp_path / "target.sqlite3"
    with sqlite3.connect(source) as conn:
        conn.execute(
            "CREATE TABLE banco_datos (DocumentosCodigo TEXT, NumeroDocumento TEXT, Fecha TEXT, ArticulosCodigo TEXT, ArticulosNombre TEXT, Cantidad REAL)"
        )
        rows = []
        for doc in ("F1", *excluded_document_codes()):
            for num in ("1", "2"):
                for sku in ("A", "B" if doc == "F1" else "BAD"):
                    rows.append((doc, num, "2026-06-01", sku, sku, 1))
        conn.executemany("INSERT INTO banco_datos VALUES (?, ?, ?, ?, ?, ?)", rows)
    job.run_job(
        as_of=date(2026, 11, 1),
        min_baskets=2,
        source_sqlite=source,
        target_sqlite=target,
        apply=True,
    )
    with sqlite3.connect(target) as conn:
        pairs = conn.execute(
            "SELECT sku, complement_sku, baskets, confidence FROM advisor_cross_sell_affinity ORDER BY sku"
        ).fetchall()
    assert pairs == [("A", "B", 2, 1.0), ("B", "A", 2, 1.0)]


def test_live_affinity_filters_both_sides_of_basket_join():
    codes = excluded_document_sql_in_list()
    assert f"AND DocumentosCodigo NOT IN ({codes})" in affinity._SQL
    assert f"AND d.DocumentosCodigo NOT IN ({codes})" in affinity._SQL
