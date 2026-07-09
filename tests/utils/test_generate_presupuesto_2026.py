"""Unit tests for 2026 presupuesto builder (no DB)."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from business_analyzer.core.presupuesto_2026 import (  # noqa: E402
    DEFAULT_CODE_MERGES,
    apply_code_merge,
    attribute_sale,
    build_name_to_code_map,
    build_presupuesto_2026,
    canonical_active_codes,
    draft_metas_from_base,
    last_complete_month,
    parse_asignado_code,
    redistribute_pool,
    year_month_to_periodo,
)


def test_year_month_to_periodo():
    assert year_month_to_periodo(2026, 6) == 20266
    assert year_month_to_periodo(2026, 10) == 202610


def test_last_complete_month():
    assert last_complete_month(date(2026, 7, 8)) == (2026, 6)
    assert last_complete_month(date(2026, 1, 5)) == (2025, 12)


def test_william_merge():
    assert apply_code_merge("123", DEFAULT_CODE_MERGES) == "162"
    assert apply_code_merge("133", DEFAULT_CODE_MERGES) == "162"
    assert apply_code_merge("162", DEFAULT_CODE_MERGES) == "162"
    assert canonical_active_codes(["095", "123", "133", "162"]) == ["095", "162"]


def test_fef_union_keeps_sika_only_code():
    # 162 only appears via FEF path in raw set
    assert "162" in canonical_active_codes(["035", "162", "123"])


def test_parse_asignado_and_priority():
    assert parse_asignado_code("044-HUBER SANTIAGO ENCISO") == "044"
    assert parse_asignado_code("131-OLGA LUCIA TORRES ") == "131"
    active = ["044", "095", "131", "163", "162"]
    nmap = {"HUBER SANTIAGO ENCISO": "163"}  # wrong majority would say 163
    # Asignado wins over factura map and codigo
    assert (
        attribute_sale(
            code="163",
            name="HUBER SANTIAGO ENCISO",
            asignado="044-HUBER SANTIAGO ENCISO",
            name_to_code=nmap,
            active_codes=active,
        )
        == "044"
    )
    # No Asignado: official Factura owner Huber → 044 (not majority 163)
    assert (
        attribute_sale(
            code=None,
            name="HUBER SANTIAGO ENCISO",
            asignado=None,
            name_to_code=nmap,
            active_codes=active,
        )
        == "044"
    )
    # Olga official 131
    assert (
        attribute_sale(
            code="003",
            name="OLGA LUCIA TORRES",
            asignado=None,
            name_to_code={},
            active_codes=active,
        )
        == "131"
    )
    # Asignado inactive → pool
    assert (
        attribute_sale(
            code="095",
            name="X",
            asignado="126-LEFT",
            name_to_code={},
            active_codes=active,
        )
        == "POOL"
    )


def test_name_map_and_attribution_pool():
    coded = [
        ("095", "DANIEL ENRIQUE CAICEDO", 100.0),
        ("060", "YULI ALEJANDRA HIGUERA", 50.0),
    ]
    active = ["095", "060", "162", "044"]
    nmap = build_name_to_code_map(coded, allowed_codes=active)
    assert nmap["DANIEL ENRIQUE CAICEDO"] == "095"
    assert (
        attribute_sale(
            code=None,
            name="DANIEL ENRIQUE CAICEDO",
            name_to_code=nmap,
            active_codes=active,
        )
        == "095"
    )
    assert (
        attribute_sale(
            code="126",
            name="LEFT PERSON",
            name_to_code=nmap,
            active_codes=active,
        )
        == "POOL"
    )
    assert (
        attribute_sale(
            code=None,
            name="WILLIAM HERNANDO QUINTERO G",
            name_to_code=nmap,
            active_codes=active,
        )
        == "162"
    )


def test_pool_redistribute_and_growth_lock():
    attributed = {
        ("095", 2025, 1): 80.0,
        ("060", 2025, 1): 20.0,
        ("POOL", 2025, 1): 100.0,  # leaver volume
    }
    base = redistribute_pool(attributed, active_codes=["095", "060"])
    # pool 100 split 80/20 → 095 gets 80+80=160, 060 gets 20+20=40
    assert abs(base[("095", 1)] - 160.0) < 1e-6
    assert abs(base[("060", 1)] - 40.0) < 1e-6
    metas = draft_metas_from_base(base, active_codes=["095", "060"], growth=0.25)
    assert abs(sum(metas.values()) - 200.0 * 1.25) < 1e-6


def test_build_end_to_end_small_fixture():
    active_raw = ["095", "060", "123", "162"]
    sales = []
    for m in range(1, 13):
        sales.append(("095", "DANIEL", "095-DANIEL", 2025, m, 100.0))
        sales.append(("060", "YULI", "060-YULI", 2025, m, 50.0))
        sales.append((None, "AMELIA LEFT", None, 2025, m, 10.0))  # pool
    sales.append(("123", "WILLIAM HERNANDO QUINTERO G", "162-WILLIAM", 2026, 6, 5.0))
    coded = [
        ("095", "DANIEL", 1200.0),
        ("060", "YULI", 600.0),
        ("162", "WILLIAM HERNANDO QUINTERO G", 5.0),
    ]
    line_shares = {
        "095": [("001", "017", 1.0)],
        "060": [("001", "017", 1.0)],
        "162": [("001", "017", 1.0)],
        "__COMPANY__": [("001", "017", 1.0)],
    }
    result = build_presupuesto_2026(
        active_raw_codes=active_raw,
        sales_rows=sales,
        coded_name_sales=coded,
        line_shares=line_shares,
        h1_2026_by_code={"095": 600.0, "060": 300.0, "162": 5.0},
        primary_names={"095": "DANIEL", "060": "YULI", "162": "WILLIAM"},
        growth=0.25,
    )
    assert "123" not in result.active_codes
    assert "162" in result.active_codes
    # base = 12*(100+50+10) = 1920; meta = 1920*1.25
    assert abs(result.company_base_2025 - 1920.0) < 1.0
    assert abs(result.company_meta_2026 - 1920.0 * 1.25) < 1.0
    assert result.pool_total_2025 > 0
    assert all(r["vendedor_codigo"] != "123" for r in result.vendor_rows)
    # line recon approx
    by_period_vendor = {}
    for r in result.line_rows:
        k = (r["periodo"], r["vendedor_codigo"])
        by_period_vendor[k] = by_period_vendor.get(k, 0.0) + float(r["valor"])
    for r in result.vendor_rows:
        k = (r["periodo"], r["vendedor_codigo"])
        assert abs(by_period_vendor.get(k, 0.0) - float(r["valor"])) < 0.01
