"""catalog.quote_skus: batch exact-SKU J3 quote + short TTL cache (fake-only).

RED profile measured by the owner (post #121): one ``catalog.quote_search`` by
SKU = ~3 s because the LIKE/REPLACE predicate forces a full-inventory hash
aggregate (SHOWPLAN: ~320k-row clustered index scan of
``InvDetalleExistencias`` per call); 6 parallel = 12 s, 12 parallel = 21 s.
The exact-code ``IN (...)`` predicate gets predicate pushdown (index seeks per
SKU, subtree cost 0.50 vs 16.55), so N SKUs resolve in ONE query.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from decimal import Decimal, InvalidOperation

import pytest

from business_analyzer.core.j3system_website_stock import (  # noqa: F401
    build_quote_search_sql,
)
from depotru_kernel.auth import Audience
from depotru_tools.catalog_query import quote_skus_statement  # noqa: F401
from depotru_tools.registry import (
    ToolContext,
    get_default_registry,
    reset_default_registry,
)


@pytest.fixture(autouse=True)
def _fresh_registry():
    reset_default_registry()
    from depotru_tools.quote_cache import reset_quote_sku_cache

    reset_quote_sku_cache()
    yield
    reset_default_registry()
    reset_quote_sku_cache()


@pytest.fixture(autouse=True)
def _no_magento(monkeypatch: pytest.MonkeyPatch):
    """Never touch env credentials or Magento in fake-only tests."""
    from depotru_integrations.magento.client import MagentoConfig

    monkeypatch.setattr(MagentoConfig, "from_env", classmethod(lambda cls: None))


def _j3_row(sku: str, name: str | None = None, price: str = "100.0000") -> dict:
    return {
        "sku": sku,
        "name": name or f"PRODUCTO {sku}",
        "price": Decimal(price),
        "iva_rate": Decimal("19.000"),
        "line_id": 1,
        "website_qty": Decimal("5.0000"),
    }


class _FakeDB:
    """Counting fake: returns one row per requested SKU after a latency."""

    calls: list[tuple[str, tuple]] = []

    def __init__(self, suppress_error_details=False, latency: float = 0.0):
        self.latency = latency

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute_query(self, sql, params):
        type(self).calls.append((sql, tuple(params)))
        if self.latency:
            time.sleep(self.latency)
        return [_j3_row(str(p)) for p in params]


@pytest.fixture
def _fake_db(monkeypatch: pytest.MonkeyPatch):
    _FakeDB.calls = []
    monkeypatch.setattr("business_analyzer.core.database.Database", _FakeDB)
    return _FakeDB


SKUS = [
    "0020090002",
    "0020090003",
    "0020090004",
    "0020090005",
    "0020090006",
    "0020090007",
]


@pytest.mark.unit
def test_quote_skus_tool_is_public():
    names = {
        t["name"] for t in get_default_registry().list_tools(audience=Audience.PUBLIC)
    }
    assert "catalog.quote_skus" in names


@pytest.mark.unit
def test_quote_skus_resolves_n_skus_in_one_query(_fake_db):
    from depotru_tools.builtins import _tool_quote_skus

    out = _tool_quote_skus(ToolContext(audience=Audience.PUBLIC), {"skus": SKUS})
    assert out["status"] == "ok"
    assert out["count"] == len(SKUS)
    assert len(_FakeDB.calls) == 1  # N SKUs, ONE query — the whole point
    sql, params = _FakeDB.calls[0]
    lowered = [s.lower() for s in SKUS]
    assert tuple(params) == tuple(lowered)
    assert sql.count("LOWER(a.ArticulosCodigo) IN (") == 1
    assert "ArticulosCosto" not in sql
    # products follow input order with the closed quote contract
    assert [p["sku"] for p in out["products"]] == [str(s) for s in lowered]
    p = out["products"][0]
    assert p["price"] == "100.0000"
    assert p["price_basis"] == "J3"
    assert p["price_with_iva"] == 119
    assert out["found"] == [str(s) for s in lowered]
    assert out["missing"] == []
    assert out["source"] == "j3"
    assert set(out.keys()) == {
        "skus",
        "products",
        "count",
        "found",
        "missing",
        "status",
        "source",
    }


@pytest.mark.unit
def test_quote_skus_reports_missing(_fake_db, monkeypatch: pytest.MonkeyPatch):
    from depotru_tools.builtins import _tool_quote_skus

    def _partial(sql, params):
        return [_j3_row(str(p)) for p in params[:1]]

    monkeypatch.setattr(_FakeDB, "execute_query", staticmethod(_partial))
    out = _tool_quote_skus(ToolContext(audience=Audience.PUBLIC), {"skus": SKUS[:2]})
    assert out["status"] == "ok"
    assert out["count"] == 1
    assert out["found"] == [SKUS[0].lower()]
    assert out["missing"] == [SKUS[1].lower()]


@pytest.mark.unit
def test_quote_skus_empty_result(_fake_db, monkeypatch: pytest.MonkeyPatch):
    from depotru_tools.builtins import _tool_quote_skus

    monkeypatch.setattr(_FakeDB, "execute_query", staticmethod(lambda sql, params: []))
    out = _tool_quote_skus(ToolContext(audience=Audience.PUBLIC), {"skus": ["X1"]})
    assert out["status"] == "empty"
    assert out["products"] == []
    assert out["missing"] == ["x1"]
    assert out["source"] == "none"


@pytest.mark.unit
def test_quote_skus_input_validation(_fake_db):
    from depotru_tools.builtins import _tool_quote_skus

    ctx = ToolContext(audience=Audience.PUBLIC)
    for bad in (None, "0020090002", 123, [], [""], ["   "]):
        out = _tool_quote_skus(ctx, {"skus": bad})
        assert out["status"] == "error"
        assert out["reason"] == "skus_required"
        assert out["products"] == []
    for bad in ([123], ["ok", 5], SKUS + [f"00{i}" for i in range(20)]):
        out = _tool_quote_skus(ctx, {"skus": bad})
        assert out["status"] == "error"
        assert out["reason"] == "skus_invalid"
    assert not _FakeDB.calls  # never reaches the DB


@pytest.mark.unit
def test_quote_skus_dedupes_case_insensitive(_fake_db):
    from depotru_tools.builtins import _tool_quote_skus

    out = _tool_quote_skus(
        ToolContext(audience=Audience.PUBLIC), {"skus": ["0020090002", " 0020090002 "]}
    )
    assert out["count"] == 1
    assert len(_FakeDB.calls) == 1
    assert len(_FakeDB.calls[0][1]) == 1


@pytest.mark.unit
def test_quote_skus_catalog_unavailable(_fake_db, monkeypatch: pytest.MonkeyPatch):
    from depotru_tools.builtins import _tool_quote_skus

    class FailDB:
        def __init__(self, suppress_error_details=False):
            pass

        def __enter__(self):
            raise ConnectionError("boom: SQLSTATE 08S01 host=secret-dsn")

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("business_analyzer.core.database.Database", FailDB)
    out = _tool_quote_skus(ToolContext(audience=Audience.PUBLIC), {"skus": ["X1"]})
    assert out["status"] == "error"
    assert out["reason"] == "catalog_unavailable"
    assert out["products"] == []
    import json

    text = json.dumps(out)
    assert "08S01" not in text
    assert "secret" not in text
    assert "boom" not in text


@pytest.mark.unit
def test_quote_skus_malformed_row_fails_closed(
    _fake_db, monkeypatch: pytest.MonkeyPatch
):
    from depotru_tools.builtins import _tool_quote_skus

    monkeypatch.setattr(
        _FakeDB,
        "execute_query",
        staticmethod(lambda sql, params: [{"sku": "X1", "name": "N"}]),
    )
    out = _tool_quote_skus(ToolContext(audience=Audience.PUBLIC), {"skus": ["X1"]})
    assert out["status"] == "error"
    assert out["reason"] == "catalog_unavailable"


@pytest.mark.unit
def test_quote_skus_short_ttl_cache(_fake_db, monkeypatch: pytest.MonkeyPatch):
    from depotru_tools.builtins import _tool_quote_skus

    monkeypatch.setenv("QUOTE_SKU_CACHE_TTL_SECONDS", "0.05")
    ctx = ToolContext(audience=Audience.PUBLIC)
    out1 = _tool_quote_skus(ctx, {"skus": ["0020090002"]})
    out2 = _tool_quote_skus(ctx, {"skus": ["0020090002"]})
    assert out2["status"] == "ok"
    assert len(_FakeDB.calls) == 1  # warm hit inside the TTL window
    time.sleep(0.08)  # TTL expires
    _tool_quote_skus(ctx, {"skus": ["0020090002"]})
    assert len(_FakeDB.calls) == 2  # cold again


@pytest.mark.unit
def test_quote_skus_ttl_zero_disables_cache(_fake_db, monkeypatch: pytest.MonkeyPatch):
    from depotru_tools.builtins import _tool_quote_skus

    monkeypatch.setenv("QUOTE_SKU_CACHE_TTL_SECONDS", "0")
    ctx = ToolContext(audience=Audience.PUBLIC)
    _tool_quote_skus(ctx, {"skus": ["0020090002"]})
    _tool_quote_skus(ctx, {"skus": ["0020090002"]})
    assert len(_FakeDB.calls) == 2


@pytest.mark.unit
def test_quote_cache_resolve_error_then_retry_succeeds():
    """A failed compute must not poison the key: the next resolve retries.

    Regression for the permanent ``_inflight`` leak: the exception path used
    to leave the dead flight registered, so every later ``resolve`` re-raised
    the stale error without ever calling compute again.
    """
    from depotru_tools.quote_cache import QuoteSkuCache

    cache = QuoteSkuCache(ttl_seconds=60)
    calls = {"n": 0}

    def _fail_once(_key: str) -> list[dict]:
        calls["n"] += 1
        raise ConnectionError("transient J3 failure")

    with pytest.raises(ConnectionError):
        cache.resolve("a1", _fail_once)
    assert calls["n"] == 1

    def _healthy(_key: str) -> list[dict]:
        calls["n"] += 1
        return [{"sku": "a1"}]

    rows = cache.resolve("a1", _healthy)  # must NOT re-raise the stale error
    assert rows == [{"sku": "a1"}]
    assert calls["n"] == 2  # compute was retried, not replayed from the corpse

    assert cache.resolve("a1", _healthy) == [{"sku": "a1"}]
    assert calls["n"] == 2  # now served from the cache
    assert cache.hits == 1


@pytest.mark.unit
def test_quote_skus_j3_failure_does_not_poison_retry(_fake_db, monkeypatch):
    """One transient J3 blip must not return catalog_unavailable forever."""
    from depotru_tools.builtins import _tool_quote_skus

    class FailDB:
        def __init__(self, suppress_error_details=False):
            pass

        def __enter__(self):
            raise ConnectionError("transient J3 blip")

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("business_analyzer.core.database.Database", FailDB)
    ctx = ToolContext(audience=Audience.PUBLIC)
    out1 = _tool_quote_skus(ctx, {"skus": ["X1"]})
    assert out1["status"] == "error"
    assert out1["reason"] == "catalog_unavailable"

    monkeypatch.setattr("business_analyzer.core.database.Database", _FakeDB)
    out2 = _tool_quote_skus(ctx, {"skus": ["X1"]})
    assert out2["status"] == "ok"
    assert out2["count"] == 1
    out3 = _tool_quote_skus(ctx, {"skus": ["X1"]})
    assert out3["status"] == "ok"


@pytest.mark.unit
def test_quote_skus_ttl_zero_one_query_for_n_skus(_fake_db, monkeypatch):
    """TTL=0 disables the cache, NOT the batch: N SKUs in ONE query.

    Documented in ``.env.example`` ("0 disables caching (batch still
    resolves N SKUs in one query)") — this pins the query count.
    """
    from depotru_tools.builtins import _tool_quote_skus

    monkeypatch.setenv("QUOTE_SKU_CACHE_TTL_SECONDS", "0")
    _FakeDB.calls = []
    out = _tool_quote_skus(ToolContext(audience=Audience.PUBLIC), {"skus": SKUS[:3]})
    assert out["status"] == "ok"
    assert out["count"] == 3
    assert len(_FakeDB.calls) == 1
    assert tuple(_FakeDB.calls[0][1]) == tuple(s.lower() for s in SKUS[:3])


@pytest.mark.unit
def test_quote_skus_single_flight_under_concurrency(monkeypatch: pytest.MonkeyPatch):
    """12 parallel identical SKU lookups cause ONE J3 query, not a stampede."""
    from depotru_tools.builtins import _tool_quote_skus

    monkeypatch.setattr(
        "business_analyzer.core.database.Database",
        lambda suppress_error_details=False: _FakeDB(
            suppress_error_details, latency=0.2
        ),
    )
    _FakeDB.calls = []
    results: list[dict] = []
    lock = threading.Lock()

    def _call():
        out = _tool_quote_skus(
            ToolContext(audience=Audience.PUBLIC), {"skus": ["0020090002"]}
        )
        with lock:
            results.append(out)

    threads = [threading.Thread(target=_call) for _ in range(12)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - t0

    assert len(_FakeDB.calls) == 1  # single-flight: one DB round trip
    assert all(r["status"] == "ok" for r in results)
    assert all(r["count"] == 1 for r in results)
    # 12 serialized 0.2 s queries would take >= 2.4 s on one connection.
    assert elapsed < 1.0


@pytest.mark.unit
def test_quote_skus_batch_beats_per_sku_profile(monkeypatch: pytest.MonkeyPatch):
    """RED profile: 6 SKU lookups as N queries vs the batch IN(...) fix.

    Today's shape is one ``catalog.quote_search`` per SKU (~3 s each live).
    With a fake per-query latency of 0.2 s the per-SKU shape needs >= 1.2 s;
    the batch tool must resolve the same 6 SKUs in one query (< 0.6 s here).
    """
    from business_analyzer.core.database import Database  # noqa: F401
    from depotru_tools.builtins import _tool_quote_skus

    latency = 0.2
    monkeypatch.setattr(
        "business_analyzer.core.database.Database",
        lambda suppress_error_details=False: _FakeDB(
            suppress_error_details, latency=latency
        ),
    )
    _FakeDB.calls = []

    # Per-SKU shape (today): one query per SKU, sequential.
    t0 = time.perf_counter()
    with _FakeDB(latency=latency) as db:
        for sku in SKUS:
            sql, params = quote_skus_statement([sku])
            db.execute_query(sql, params)
    per_sku_elapsed = time.perf_counter() - t0
    assert per_sku_elapsed >= 6 * latency  # sanity: the slow profile is real

    # Batch shape (the fix): one query for all six.
    _FakeDB.calls = []
    t0 = time.perf_counter()
    sql, params = quote_skus_statement(SKUS)
    with _FakeDB() as db:
        rows = db.execute_query(sql, params)
    batch_elapsed = time.perf_counter() - t0
    assert len(rows) == len(SKUS)
    assert len(_FakeDB.calls) == 1
    assert batch_elapsed < 3 * latency  # amortized: one round trip


# --- SQLite statement-level check (same fixture style as quote_search) ---


class _DecimalSum:
    def __init__(self) -> None:
        self.total = Decimal("0")

    def step(self, value) -> None:
        if value is None:
            return
        try:
            self.total += Decimal(str(value))
        except (InvalidOperation, ValueError):
            pass

    def finalize(self) -> str:
        return format(self.total, "f")


def _sqlite_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE AdmArticulos (ArticulosID INTEGER PRIMARY KEY, "
        "ArticulosCodigo TEXT, ArticulosNombre TEXT, ArticulosVenta TEXT, "
        "LineasID INTEGER, ArticulosEstado INTEGER)"
    )
    conn.execute(
        "CREATE TABLE AdmLineas (LineasID INTEGER PRIMARY KEY, LineasPorcentaje TEXT)"
    )
    conn.execute(
        "CREATE TABLE InvDetalleExistencias (ExistenciasID INTEGER, "
        "AlmacenID INTEGER, SaldoActual TEXT, Ano INTEGER)"
    )
    conn.execute(
        "CREATE TABLE InvExistencias (ExistenciasID INTEGER, ArticulosID INTEGER)"
    )
    conn.execute(
        "CREATE TABLE AdmAlmacen (AlmacenID INTEGER PRIMARY KEY, AlmacenCodigo TEXT)"
    )
    conn.create_aggregate("decimal_sum", 1, _DecimalSum)

    def _decimal_ge(value, threshold) -> int:
        try:
            return 1 if Decimal(str(value)) >= Decimal(str(threshold)) else 0
        except (InvalidOperation, ValueError):
            return 0

    conn.create_function("decimal_ge", 2, _decimal_ge)

    def _decimal_gt(value, threshold) -> int:
        try:
            return 1 if Decimal(str(value)) > Decimal(str(threshold)) else 0
        except (InvalidOperation, ValueError):
            return 0

    conn.create_function("decimal_gt", 2, _decimal_gt)
    conn.row_factory = sqlite3.Row
    conn.execute("INSERT INTO AdmLineas VALUES (1, '19.000')")
    conn.executemany(
        "INSERT INTO AdmArticulos VALUES (?, ?, ?, ?, 1, 1)",
        [
            (1, "A1", "PRODUCTO A1", "100.0000"),
            (2, "A2", "PRODUCTO A2", "200.0000"),
            (3, "B1", "PRODUCTO B1", "300.0000"),
        ],
    )
    conn.execute("INSERT INTO AdmAlmacen VALUES (10, 'ALM')")
    conn.execute("INSERT INTO InvExistencias VALUES (100, 1)")
    conn.execute("INSERT INTO InvDetalleExistencias VALUES (100, 10, '4.0000', 2026)")
    return conn


@pytest.mark.unit
def test_quote_skus_statement_sqlite():
    from depotru_tools.catalog_query import quote_skus_statement

    conn = _sqlite_conn()
    sql, params = quote_skus_statement(["a1", "b1"], dialect="sqlite")
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    assert sorted(r["sku"] for r in rows) == ["A1", "B1"]
    assert "LOWER(a.ArticulosCodigo) IN (?" in sql
    # missing SKU resolves to no row (caller reports it as missing)
    sql2, params2 = quote_skus_statement(["ZZZ"], dialect="sqlite")
    assert [dict(r) for r in conn.execute(sql2, params2).fetchall()] == []


@pytest.mark.unit
def test_quote_skus_statement_tsql_shape():
    from depotru_tools.catalog_query import quote_skus_statement

    sql, params = quote_skus_statement(SKUS)
    assert sql.count("LOWER(a.ArticulosCodigo) IN (") == 1
    assert sql.count("%s") == len(SKUS)
    assert "TOP %d" % len(SKUS) in sql
    assert "ArticulosCosto" not in sql
    assert "ArticulosEstado" not in sql
    assert tuple(params) == tuple(s.lower() for s in SKUS)
