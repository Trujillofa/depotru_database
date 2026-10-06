"""Unit tests for website warehouse allowlist (#182 / storefront #395)."""

import pytest

from business_analyzer.core.j3system_website_stock import (
    build_website_stock_by_sku_sql,
    build_website_stock_impact_summary_sql,
)
from business_analyzer.core.website_stock_magento_ssh import local_dry_run_result
from business_analyzer.core.website_warehouse_policy import (
    ALL_J3_WAREHOUSE_CODES,
    WEBSITE_WAREHOUSE_DENYLIST,
    is_website_warehouse,
    policy_summary,
    sql_in_list,
    website_warehouse_allowlist,
)

# Storefront parity: Trujillofa/depositotrujillo.co#395
EXPECTED_WEBSITE_WAREHOUSE_DENYLIST = frozenset(
    {"BDT", "CEN", "EXH", "EXD", "MDL", "TRA", "CON"}
)


@pytest.mark.unit
def test_denylist_contains_ops_codes():
    assert WEBSITE_WAREHOUSE_DENYLIST == EXPECTED_WEBSITE_WAREHOUSE_DENYLIST
    assert "CON" in WEBSITE_WAREHOUSE_DENYLIST


@pytest.mark.unit
def test_allowlist_excludes_denylist():
    allow = website_warehouse_allowlist()
    for code in WEBSITE_WAREHOUSE_DENYLIST:
        assert code not in allow
    assert "ALM" in allow
    assert "SUR" in allow
    assert "B.ROT" in allow
    assert "CON" not in allow
    assert len(allow) == len(ALL_J3_WAREHOUSE_CODES) - len(WEBSITE_WAREHOUSE_DENYLIST)


@pytest.mark.unit
def test_is_website_warehouse():
    assert is_website_warehouse("ALM") is True
    assert is_website_warehouse("cen") is False
    assert is_website_warehouse("MDL") is False
    assert is_website_warehouse("CON") is False
    assert is_website_warehouse("con") is False
    assert is_website_warehouse("") is False


@pytest.mark.unit
def test_con_only_stock_is_not_website_sellable():
    """Accounting/service SKUs with stock only in CON must not look in-stock online.

    CON holds 0130010001–0130010006 (contabilidad / servicio). Storefront #395
    denies the warehouse so those balances cannot become Magento website qty.
    """
    warehouse_balances = {"CON": 204057.0}  # 0130010006-style: qty only in CON
    website_qty = sum(
        float(qty)
        for code, qty in warehouse_balances.items()
        if is_website_warehouse(code)
    )
    assert website_qty == 0

    mixed = {"ALM": 5.0, "CON": 100.0}
    mixed_qty = sum(
        float(qty) for code, qty in mixed.items() if is_website_warehouse(code)
    )
    assert mixed_qty == 5.0

    preview = local_dry_run_result(
        [
            {
                "sku": "0130010006",
                "website_qty": website_qty,
                "excluded_qty": 204057.0,
                "all_warehouses_qty": 204057.0,
                "name": ".",
            }
        ]
    )
    assert preview["would_zero_skus"] == 1


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
    assert set(s["denylist"]) == EXPECTED_WEBSITE_WAREHOUSE_DENYLIST
    assert "CON" in s["denylist_labels"]
    assert "default" in s["magento_msi_sources"]
    assert "182" in s["issue"]
    assert "395" in s["storefront_policy_issue"]


@pytest.mark.unit
def test_website_stock_sql_filters_denylist():
    sql = build_website_stock_by_sku_sql(top_n=10)
    lower = sql.lower()
    assert "invdetalleexistencias" in lower
    assert "admalmacen" in lower
    assert "'CEN'" in sql or "'cen'" in sql.lower()
    assert "'CON'" in sql
    allow_sql = sql_in_list(website_warehouse_allowlist())
    deny_sql = sql_in_list(sorted(WEBSITE_WAREHOUSE_DENYLIST))
    assert "'CON'" in deny_sql
    assert "'CON'" not in allow_sql
    assert "website_qty" in lower
    assert "excluded_qty" in lower
    assert "TOP 10" in sql


@pytest.mark.unit
def test_impact_summary_sql():
    sql = build_website_stock_impact_summary_sql()
    assert "website_qty_sum" in sql
    assert "excluded_qty_sum" in sql
