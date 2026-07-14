"""Unit tests for website warehouse allowlist (#182)."""

import pytest

from business_analyzer.core.j3system_website_stock import (
    build_website_stock_by_sku_sql,
    build_website_stock_impact_summary_sql,
)
from business_analyzer.core.website_warehouse_policy import (
    ALL_J3_WAREHOUSE_CODES,
    WEBSITE_WAREHOUSE_DENYLIST,
    is_website_warehouse,
    policy_summary,
    sql_in_list,
    website_warehouse_allowlist,
)


@pytest.mark.unit
def test_denylist_contains_ops_codes():
    assert WEBSITE_WAREHOUSE_DENYLIST == frozenset(
        {"CEN", "EXH", "EXD", "BDT", "MDL", "TRA"}
    )


@pytest.mark.unit
def test_allowlist_excludes_denylist():
    allow = website_warehouse_allowlist()
    for code in WEBSITE_WAREHOUSE_DENYLIST:
        assert code not in allow
    assert "ALM" in allow
    assert "SUR" in allow
    assert "B.ROT" in allow
    assert len(allow) == len(ALL_J3_WAREHOUSE_CODES) - len(WEBSITE_WAREHOUSE_DENYLIST)


@pytest.mark.unit
def test_is_website_warehouse():
    assert is_website_warehouse("ALM") is True
    assert is_website_warehouse("cen") is False
    assert is_website_warehouse("MDL") is False
    assert is_website_warehouse("") is False


@pytest.mark.unit
def test_sql_in_list_safe():
    assert sql_in_list(["ALM", "SUR"]) == "'ALM', 'SUR'"
    with pytest.raises(ValueError):
        sql_in_list(["ALM'; DROP"])
    with pytest.raises(ValueError):
        sql_in_list([])


@pytest.mark.unit
def test_policy_summary_shape():
    s = policy_summary()
    assert "denylist" in s and "allowlist" in s
    assert "default" in s["magento_msi_sources"]
    assert "182" in s["issue"]


@pytest.mark.unit
def test_website_stock_sql_filters_denylist():
    sql = build_website_stock_by_sku_sql(top_n=10)
    lower = sql.lower()
    assert "invdetalleexistencias" in lower
    assert "admalmacen" in lower
    assert "'CEN'" in sql or "'cen'" in sql.lower()
    assert "website_qty" in lower
    assert "excluded_qty" in lower
    assert "TOP 10" in sql


@pytest.mark.unit
def test_impact_summary_sql():
    sql = build_website_stock_impact_summary_sql()
    assert "website_qty_sum" in sql
    assert "excluded_qty_sum" in sql
