"""Website Magento list price = J3 ArticulosVenta × IVA."""

from decimal import Decimal

from business_analyzer.core.website_price_policy import (
    IVA_RATE,
    build_j3_venta_sql,
    build_price_payload,
    parse_magento_price_tsv,
    should_update,
    target_price,
)


def test_iva_rate_is_colombian_nineteen_percent():
    assert IVA_RATE == Decimal("1.19")


def test_target_price_matches_live_pdp_for_old_j3_venta():
    # Magento PDP 2026-09-10: SKU 0010170536 showed 257040 = 216000 × 1.19
    assert target_price(216000) == 257040


def test_target_price_for_updated_j3_venta():
    assert target_price(234000) == 278460


def test_target_price_rounds_to_whole_cop():
    assert target_price(21554) == 25649  # 21554 * 1.19 = 25649.26 → 25649


def test_target_price_skips_non_positive_venta():
    assert target_price(0) is None
    assert target_price(-10) is None
    assert target_price(None) is None


def test_should_update_when_magento_differs_by_one_cop_or_more():
    assert should_update(257040, 278460) is True
    assert should_update(278460, 278460) is False
    assert should_update(278460.4, 278460) is False
    assert should_update(278459, 278460) is True


def test_build_payload_skips_missing_j3_zero_venta_and_special_price():
    j3 = [
        {"sku": "A", "venta": 234000},
        {"sku": "B", "venta": 0},
        {"sku": "C", "venta": 1000},
        {"sku": "D", "venta": 5000},
    ]
    magento = [
        {"sku": "A", "price": 257040, "special_price": None},
        {"sku": "C", "price": 1190, "special_price": None},
        {"sku": "D", "price": 9000, "special_price": 8000},
        {"sku": "E", "price": 100, "special_price": None},
    ]
    payload = build_price_payload(j3_rows=j3, magento_rows=magento)
    assert [row["sku"] for row in payload] == ["A"]
    assert payload[0]["j3_venta"] == 234000
    assert payload[0]["magento_price"] == 257040
    assert payload[0]["target"] == 278460
    assert payload[0]["delta"] == 21420


def test_j3_venta_sql_reads_articulos_venta():
    sql = build_j3_venta_sql()
    assert "AdmArticulos" in sql
    assert "ArticulosVenta" in sql
    assert "ArticulosCodigo" in sql
    assert "cache:flush" not in sql.lower()


def test_parse_magento_price_tsv_maps_special_price():
    text = "0010170536\t257040.000000\tNULL\nD\t9000\t8000\n"
    rows = parse_magento_price_tsv(text)
    assert rows[0]["sku"] == "0010170536"
    assert rows[0]["price"] == "257040.000000"
    assert rows[0]["special_price"] is None
    assert rows[1]["special_price"] == "8000"
