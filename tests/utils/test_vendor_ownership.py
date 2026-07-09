"""Unit tests for vendor ownership card and purity analysis (no DB)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from business_analyzer.core.presupuesto_2026 import (  # noqa: E402
    OFFICIAL_FACTURA_OWNERS,
    attribute_sale,
    official_owner_for_factura,
)
from business_analyzer.core.vendor_ownership import (  # noqa: E402
    ACTIVE_META_CODES_2026,
    OWNER_CARD,
    SalesSlice,
    analyze_purity,
    is_huber_to_betsy_handoff,
    render_purity_markdown,
)


def test_owner_card_has_eighteen_codes():
    assert len(OWNER_CARD) == 18
    assert len(ACTIVE_META_CODES_2026) == 18
    assert OWNER_CARD["044"].owner == "HUBER SANTIAGO ENCISO"
    assert OWNER_CARD["131"].owner == "OLGA LUCIA TORRES"
    assert OWNER_CARD["163"].owner == "BETSY GUZMAN"
    assert "no_multi_name" in OWNER_CARD["044"].flags
    assert "credit_handoff_from_huber" in OWNER_CARD["163"].flags


def test_factura_owners_exported_via_presupuesto():
    assert official_owner_for_factura("HUBER SANTIAGO ENCISO") == "044"
    assert official_owner_for_factura("OLGA LUCIA TORRES") == "131"
    assert official_owner_for_factura("DANIEL ENRIQUE CAICEDO") == "095"
    assert OFFICIAL_FACTURA_OWNERS["BETSY GUZMAN"] == "163"


def test_handoff_detection():
    assert is_huber_to_betsy_handoff(
        factura_name="HUBER SANTIAGO ENCISO",
        asignado="163-BETSY GUZMAN",
    )
    assert not is_huber_to_betsy_handoff(
        factura_name="HUBER SANTIAGO ENCISO",
        asignado="044-HUBER SANTIAGO ENCISO",
    )
    assert not is_huber_to_betsy_handoff(
        factura_name="BETSY GUZMAN",
        asignado="163-BETSY GUZMAN",
    )


def test_handoff_not_purity_error():
    """Asignado 163 + Factura Huber must not flag multi-name on 044."""
    slices = [
        SalesSlice(
            code="044",
            factura_name="HUBER SANTIAGO ENCISO",
            asignado="044-HUBER",
            sede="FED",
            sales=50_000_000,
        ),
        # Handoff book — should count as 163, not multi-name on 044
        SalesSlice(
            code="163",
            factura_name="HUBER SANTIAGO ENCISO",
            asignado="163-BETSY GUZMAN",
            sede="FED",
            sales=80_000_000,
        ),
        SalesSlice(
            code="163",
            factura_name="BETSY GUZMAN",
            asignado="163-BETSY GUZMAN",
            sede="FED",
            sales=20_000_000,
        ),
    ]
    report = analyze_purity(slices, period_label="test", material_threshold=1_000_000)
    assert report.handoff_ok_sales == 80_000_000
    multi = [f for f in report.findings if f.check == "multi_name" and f.code == "044"]
    assert multi == []
    # 163 allows Huber Factura as lag
    multi163 = [
        f for f in report.findings if f.check == "multi_name" and f.code == "163"
    ]
    assert multi163 == []
    handoff_info = [f for f in report.findings if f.check == "handoff_ok"]
    assert len(handoff_info) == 1


def test_multi_name_on_044_flags_daniel():
    slices = [
        SalesSlice(
            code="044",
            factura_name="HUBER SANTIAGO ENCISO",
            asignado="044-HUBER",
            sede="FED",
            sales=50_000_000,
        ),
        SalesSlice(
            code="044",
            factura_name="DANIEL ENRIQUE CAICEDO",
            asignado="044-DANIEL",
            sede="FED",
            sales=30_000_000,
        ),
    ]
    report = analyze_purity(slices, period_label="test", material_threshold=1_000_000)
    errors = [f for f in report.errors if f.check in ("multi_name", "wrong_home")]
    assert any(f.check == "multi_name" and f.code == "044" for f in errors)
    assert any(f.check == "wrong_home" and "DANIEL" in f.message for f in errors)


def test_wrong_home_carlos_on_131():
    slices = [
        SalesSlice(
            code="131",
            factura_name="OLGA LUCIA TORRES",
            asignado="131-OLGA",
            sede="FET",
            sales=10_000_000,
        ),
        SalesSlice(
            code="131",
            factura_name="CARLOS EFREY PASCUAS",
            asignado="131-CARLOS",
            sede="FED",
            sales=40_000_000,
        ),
    ]
    report = analyze_purity(slices, period_label="test", material_threshold=1_000_000)
    assert any(f.check == "wrong_home" and f.code == "131" for f in report.errors)
    assert any(f.check == "multi_name" and f.code == "131" for f in report.errors)


def test_merge_orphan_warns():
    slices = [
        SalesSlice(
            code="123",
            factura_name="WILLIAM HERNANDO QUINTERO G",
            asignado=None,
            sede="FEF",
            sales=5_000_000,
        ),
    ]
    report = analyze_purity(slices, period_label="test", material_threshold=1_000_000)
    assert any(f.check == "merge_orphan" and f.code == "123" for f in report.warns)


def test_asignado_still_wins_budget_for_handoff():
    active = ["044", "163", "095"]
    assert (
        attribute_sale(
            code="044",
            name="HUBER SANTIAGO ENCISO",
            asignado="163-BETSY GUZMAN",
            name_to_code={},
            active_codes=active,
        )
        == "163"
    )


def test_render_markdown_includes_one_pager():
    report = analyze_purity([], period_label="empty")
    md = render_purity_markdown(
        report,
        enero_smoke={
            "code_count": 18,
            "expected": 18,
            "total_meta": 1e9,
            "status": "OK",
            "missing_codes": [],
            "extra_codes": [],
        },
    )
    assert "Field one-pager" in md
    assert "044" in md
    assert "Enero 2026" in md
    assert "OK" in md
