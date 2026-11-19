"""Hybrid quote-search regressions, executing SQL on synthetic SQLite only."""

import sqlite3

import pytest

from business_analyzer.core.j3system_website_stock import build_quote_search_sql
from depotru_tools import builtins


@pytest.fixture
def search(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.create_function("CONCAT", -1, lambda *parts: "".join(parts))
    conn.execute("CREATE TABLE articles (sku TEXT, name TEXT)")
    calls = []

    def rows(sql, params, *, limit):
        calls.append((sql, params))
        # Exercise the actual generated WHERE predicate, not a Python imitation.
        predicate = sql.rsplit("\nWHERE ", 1)[1].split("\nORDER BY", 1)[0]
        predicate = predicate.replace("a.ArticulosNombre", "a.name")
        predicate = predicate.replace("a.ArticulosCodigo", "a.sku")
        predicate = predicate.replace("%s", "?")
        return [
            dict(r)
            for r in conn.execute(
                f"SELECT * FROM articles a WHERE {predicate} LIMIT ?", (*params, limit)
            )
        ]

    monkeypatch.setattr(builtins, "_quote_search_j3_rows", rows, raising=False)

    class FakeDB:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute_query(self, sql, params):
            return [
                dict(r, price=1, iva_rate=0, line_id=1, website_qty=0)
                for r in rows(sql, params, limit=40)
            ]

    monkeypatch.setattr("business_analyzer.core.database.Database", FakeDB)

    def run(query, products, limit=40):
        conn.execute("DELETE FROM articles")
        conn.executemany("INSERT INTO articles VALUES (?, ?)", products)
        return [r["sku"] for r in builtins._quote_search_j3(query, limit=limit)]

    return run, calls


@pytest.mark.parametrize(
    "query,products,expected",
    [
        (
            "precio sikafill 7 x galón",
            [("A", "SIKAFILL 7 POWER BLANCO X GALON")],
            ["A"],
        ),
        (
            "válvula 3/8",
            [("A", "VALVULA 3/8"), ("B", "VALVULA 3/4"), ("38", "VALVULA 1/2")],
            ["A"],
        ),
        (
            "tubo pvc 1/2",
            [
                ("A", "TUBO PVC 1/2"),
                ("B", "TUBO CPVC 1/2"),
                ("C", "TUBO PVC 11/2"),
                ("D", "TUBO PVC 1/256"),
                ("PVC12", "TUBO CPVC 3/4"),
            ],
            ["A"],
        ),
        ("pvc", [("A", "PVC"), ("B", "CPVC")], ["A"]),
        ("tubo 7", [("7", "TUBO 8"), ("A", "TUBO 70"), ("B", "TUBO 7")], ["B"]),
        ("1/2", [("A", "CODO 1/2"), ("B", "CODO 11/2"), ("C", "CODO 1/256")], ["A"]),
        (
            "0020080005",
            [("0020080005", "CEMENTO"), ("X0020080005", "OTRO")],
            ["0020080005"],
        ),
        (
            "ABC-123 cemento",
            [("ABC-123", "CEMENTO GRIS"), ("ABC-1234", "CEMENTO")],
            ["ABC-123"],
        ),
        ("ABC", [("ABC", "CEMENTO"), ("XABC", "OTRO")], ["ABC"]),
        ("sikafill galon", [("A", "SIKAFILL 7 POWER X GALON")], ["A"]),
        ("sikafill/galon", [("A", "SIKAFILL 7 POWER X GALON")], ["A"]),
        (
            "cemento gris 50",
            [
                ("A", "CEMENTO GRIS 50KG"),
                ("B", "CEMENTO GRIS 50 KG"),
                ("C", "CEMENTO GRIS 500KG"),
                ("D", "CEMENTO GRIS 150KG"),
                ("E", "CEMENTO GRIS 50KGBAD"),
                ("F50", "CEMENTO GRIS 25KG"),
            ],
            ["A", "B"],
        ),
        ("50%", [("A", "MEZCLA 50%"), ("B", "MEZCLA 500")], ["A"]),
        ("a_b", [("A", "a_b"), ("B", "axb")], ["A"]),
        ("[abc]", [("A", "[abc]"), ("B", "a")], ["A"]),
        ("precio x", [("A", "CUALQUIERA")], []),
    ],
)
def test_hybrid_search_contract(search, query, products, expected):
    run, _ = search
    assert run(query, products) == expected


def test_phrase_first_is_useful_but_not_a_constraint_bypass(search):
    run, calls = search
    assert run("tubo pvc 1/2", [("A", "TUBO PVC 1/256")]) == []
    calls.clear()
    assert run(
        "sikafill galon", [("A", "SIKAFILL GALON"), ("B", "SIKAFILL POWER GALON")]
    ) == ["A"]
    assert len(calls) == 1


def test_no_token_truncation_or_sql_interpolation(search):
    run, calls = search
    assert run("a b c d e f pvc 1/2", [("A", "a b c d e f CPVC 1/256")]) == []
    assert run("cemento' OR 1=1 --", [("A", "CEMENTO")]) == []
    assert all("cemento'" not in sql for sql, _ in calls)


def test_sqlite_statement_executes_full_price_stock_projection():
    from test_catalog_quote_search import _make_db

    from depotru_tools.catalog_query import quote_search_statement

    conn = _make_db()
    conn.execute(
        "INSERT INTO AdmArticulos VALUES (1, 'A', 'VÁLVULA PVC 3/8', '100', 1, 1)"
    )
    sql, params = quote_search_statement("valvula pvc 3/8", dialect="sqlite")
    rows = conn.execute(sql, params).fetchall()
    assert len(rows) == 1
    assert rows[0]["sku"] == "A"
    assert rows[0]["price"] == "100"
    conn.close()


def test_projection_drift_fails_closed(monkeypatch):
    from depotru_tools.catalog_query import quote_search_statement

    monkeypatch.setattr(
        "business_analyzer.core.j3system_website_stock.build_quote_search_sql",
        lambda **kwargs: "SELECT 1 WHERE changed_predicate",
    )
    with pytest.raises(RuntimeError, match="unrecognized quote-search predicate"):
        quote_search_statement("pvc")


def test_sql_limits_stay_bounded():
    assert "TOP 40" in build_quote_search_sql(limit=999)
    assert "TOP 6" in build_quote_search_sql()
