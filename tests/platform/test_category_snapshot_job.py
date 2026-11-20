"""Nightly category snapshot: SELECT-only J3 and atomic local publication."""

import json
import sqlite3
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from business_analyzer.jobs import category_snapshot as job
from business_analyzer.jobs import cross_sell_affinity as affinity
from depotru_integrations.affinity import category_snapshot as snapshot


def test_distinct_invoice_tuples_sales_only_including_solo_lines():
    # Only an in-memory fixture, never a configured database.
    with sqlite3.connect(":memory:") as conn:
        conn.execute(
            "CREATE TABLE banco_datos (ArticulosCodigo TEXT, DocumentosCodigo TEXT, "
            "NumeroDocumento TEXT, Fecha TEXT, Cantidad INTEGER)"
        )
        rows = [
            ("A", "FED", "1", "2026-10-01", 1),
            ("A", "FED", "1", "2026-10-01", 2),  # duplicate line, one invoice
            ("A", "FEF", "1", "2026-10-01", 1),  # same number, another document
            ("B", "FET", "solo", "2026-10-01", 1),  # no other SKU
            ("A", "FED", "old", "2024-10-01", 1),
            ("A", "FED", "future", "2027-10-01", 1),
            ("A", "FED", "zero", "2026-10-01", 0),
            ("A", "FED", "negative", "2026-10-01", -1),
            ("A", "FED", None, "2026-10-01", 1),
        ]
        for code in (
            "XY",
            "AS",
            "TS",
            "YX",
            "ISC",
            "NC",
            "DEV",
            "ND",
            "F1",
            "DVE",
            "DVD",
            "DDD",
            "DDT",
        ):
            rows.append(("A", code, "x", "2026-10-01", 1))
        conn.executemany("INSERT INTO banco_datos VALUES (?, ?, ?, ?, ?)", rows)
        counts = dict(
            conn.execute(
                job.invoice_counts_sql(table="banco_datos", p="?"),
                ("2025-11-01", "2026-11-02"),
            ).fetchall()
        )
    assert counts == {"A": 2, "B": 1}
    assert job.SALE_DOCUMENT_CODES == ("FED", "FEF", "FET")


def test_compute_snapshot_reuses_public_iva_without_stock(monkeypatch):
    db = MagicMock()
    db.execute_query.side_effect = [
        [{"sku": "A", "invoice_count": 3}],
        [
            {
                "sku": "A",
                "name": "Aditivo",
                "price": Decimal("100.50"),
                "iva_rate": Decimal(19),
                "line_id": 1,
            },
            {
                "sku": "B",
                "name": "Sin linea",
                "price": Decimal(200),
                "iva_rate": None,
                "line_id": None,
            },
        ],
    ]
    factory = MagicMock()
    factory.return_value.__enter__.return_value = db
    monkeypatch.setattr(job, "Database", factory)
    products = job.compute_category_snapshot(as_of=date(2026, 11, 20))
    assert products["A"]["invoice_count"] == 3
    assert products["A"]["price_with_iva"] == 120
    assert products["B"]["invoice_count"] == 0
    assert products["B"]["price_with_iva_reason"] == "line_not_found"
    for call in db.execute_query.call_args_list:
        sql = call.args[0].lower()
        assert sql.lstrip().startswith(("with", "select"))
        assert all(
            word not in sql
            for word in ("insert ", "update ", "delete ", "stock", "costo")
        )
    start, end = db.execute_query.call_args_list[0].args[1]
    assert start.date() == date(2025, 11, 20)
    assert end.date() == date(2026, 11, 21)
    assert all(not snapshot.STOCK_FIELDS.intersection(p) for p in products.values())


@pytest.mark.parametrize("apply", [False, True])
def test_independent_snapshot_cli_apply_gate(monkeypatch, tmp_path, apply):
    products = {"A": {"sku": "A", "invoice_count": 2}}
    monkeypatch.setattr(affinity, "compute_records", lambda **kw: [])
    monkeypatch.setattr(job, "compute_category_snapshot", lambda **kw: products)
    store = MagicMock()
    store.count.return_value = 0
    monkeypatch.setattr(affinity, "_resolve_store", lambda **kw: store)
    path = tmp_path / "snapshot.json"
    args = ["--category-snapshot", str(path)] + (["--apply"] if apply else [])
    assert job.main(args) == 0
    assert path.exists() is apply
    if apply:
        assert json.loads(path.read_text())["products"] == products
    store.replace_all.assert_not_called()


def test_failed_snapshot_cli_does_not_publish_or_write_affinity(monkeypatch, tmp_path):
    store = MagicMock()
    monkeypatch.setattr(affinity, "compute_records", lambda **kw: [])
    monkeypatch.setattr(affinity, "_resolve_store", lambda **kw: store)

    def broken(**kwargs):
        raise RuntimeError("category_snapshot_unavailable")

    monkeypatch.setattr(job, "compute_category_snapshot", broken)
    path = tmp_path / "snapshot.json"
    assert job.main(["--category-snapshot", str(path), "--apply"]) == 1
    store.replace_all.assert_not_called()
    assert not path.exists()


def test_snapshot_publish_is_atomic_preserves_old_file_on_failure(
    monkeypatch, tmp_path
):
    path = tmp_path / "snapshot.json"
    path.write_text("previous")

    def broken(*args):
        raise OSError("fixture")

    monkeypatch.setattr(snapshot.os, "replace", broken)
    with pytest.raises(OSError):
        snapshot.write_snapshot({}, path)
    assert path.read_text() == "previous"
    assert list(tmp_path.iterdir()) == [path]


def test_cli_accepts_explicit_snapshot_path():
    assert (
        job.parse_args(["--category-snapshot", "/fixture.json"]).category_snapshot
        == "/fixture.json"
    )


def test_affinity_refresh_never_computes_snapshot(monkeypatch):
    compute = MagicMock(side_effect=TimeoutError("must not be called"))
    monkeypatch.setattr(job, "compute_category_snapshot", compute)
    monkeypatch.setattr(affinity, "compute_records", lambda **kw: [])
    store = MagicMock()
    store.count.return_value = 0
    store.replace_all.return_value = 0
    monkeypatch.setattr(affinity, "_resolve_store", lambda **kw: store)
    result = affinity.run_job(apply=True)
    assert result["applied"] is True
    store.replace_all.assert_called_once()
    compute.assert_not_called()


def test_snapshot_cli_publish_failure_returns_own_error(monkeypatch, tmp_path, capsys):
    path = tmp_path / "snapshot.json"
    path.write_text("previous")
    monkeypatch.setattr(job, "compute_category_snapshot", lambda **kw: {})
    publish = MagicMock(side_effect=OSError("private connection detail"))
    monkeypatch.setattr(job, "write_snapshot", publish)
    assert job.main(["--category-snapshot", str(path), "--apply"]) == 1
    assert capsys.readouterr().err == "category_snapshot error: OSError\n"
    assert path.read_text() == "previous"


@pytest.mark.parametrize("count_sku", ["A", "A "])
@pytest.mark.parametrize("article_sku", ["A", "A "])
def test_snapshot_uses_consistent_trimmed_sku(monkeypatch, count_sku, article_sku):
    db = MagicMock()
    db.execute_query.side_effect = [
        [{"sku": count_sku, "invoice_count": 7}],
        [
            {
                "sku": article_sku,
                "name": "Aditivo",
                "price": Decimal(100),
                "iva_rate": Decimal(19),
                "line_id": 1,
            }
        ],
    ]
    factory = MagicMock()
    factory.return_value.__enter__.return_value = db
    monkeypatch.setattr(job, "Database", factory)
    products = job.compute_category_snapshot()
    assert products["A"]["sku"] == "A"
    assert products["A"]["invoice_count"] == 7
    assert snapshot._valid_product("A", products["A"])
