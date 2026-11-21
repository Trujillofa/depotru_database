"""B0 regressions: ``build_quote_search_sql`` dialect guard and integer-COP IVA.

Fake-only: no DB, credentials, or live connection. Exercises the pure SQL
builder and the exact ``Decimal`` IVA arithmetic against the B0 contract.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from business_analyzer.core.j3system_website_stock import build_quote_search_sql
from business_analyzer.core.quote_search_iva import compute_price_with_iva


def test_build_quote_search_sql_rejects_unknown_dialect():
    with pytest.raises(ValueError):
        build_quote_search_sql(dialect="mysql")


def test_build_quote_search_sql_accepts_supported_dialects():
    for dialect in ("tsql", "sqlite"):
        sql = build_quote_search_sql(dialect=dialect)
        assert isinstance(sql, str) and sql.strip()


def test_compute_price_with_iva_uses_full_price_before_cop_rounding():
    # 100.4999 rounds directly to integer COP 100; if it were rounded
    # prematurely to cents (100.50), the result would be 101.
    assert compute_price_with_iva(Decimal("100.4999"), Decimal("0")) == 100
