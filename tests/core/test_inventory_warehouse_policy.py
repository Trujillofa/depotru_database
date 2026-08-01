"""Tests for commercial turnover warehouse policy."""

import pytest

from business_analyzer.core.inventory_warehouse_policy import (
    TURNOVER_WAREHOUSE_ALLOWLIST,
    is_turnover_warehouse,
    turnover_policy_summary,
    turnover_warehouse_allowlist,
    turnover_warehouse_sql_in_list,
)


def test_allowlist_is_commercial_only():
    allow = set(turnover_warehouse_allowlist())
    assert allow == {"ALM", "SUR", "BD6", "DIS", "FLO"}
    for noise in ("CON", "B.ROT", "BDT", "CEN", "EXH", "BOD", "MDL", "TRA"):
        assert noise not in allow


def test_is_turnover_warehouse_case_insensitive():
    assert is_turnover_warehouse("alm")
    assert is_turnover_warehouse("DIS")
    assert not is_turnover_warehouse("CON")
    assert not is_turnover_warehouse("")


def test_sql_in_list_quotes_codes():
    sql = turnover_warehouse_sql_in_list()
    for code in TURNOVER_WAREHOUSE_ALLOWLIST:
        assert f"'{code}'" in sql
    assert "CON" not in sql


def test_sql_in_list_rejects_injection():
    with pytest.raises(ValueError):
        turnover_warehouse_sql_in_list(["ALM", "bad;drop"])


def test_policy_summary_keys():
    s = turnover_policy_summary()
    assert "allowlist" in s
    assert "denylist" in s
    assert "ALM" in s["allowlist"]
    assert "B.ROT" in s["denylist"]
