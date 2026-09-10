"""Safety + payload shape for Magento base-price SSH applier."""

from business_analyzer.core.website_price_magento_ssh import (
    APPLY_PHP,
    FETCH_PHP,
    magento_update_rows,
)


def test_apply_php_uses_base_price_storage_and_never_flushes():
    assert "BasePriceStorageInterface" in APPLY_PHP
    assert "cache:flush" not in APPLY_PHP
    assert "view_preprocessed" not in APPLY_PHP
    assert "setStoreId(0)" in APPLY_PHP or "setStoreId(0)" in APPLY_PHP


def test_fetch_php_reads_price_and_special_price():
    assert "attribute_code='price'" in FETCH_PHP
    assert "special_price" in FETCH_PHP
    assert "cache:flush" not in FETCH_PHP
    # Must not cartesian every store-0 decimal row (weight/cost would look like special_price).
    assert "special.attribute_id = sa.attribute_id" in FETCH_PHP
    assert (
        "sa.attribute_code='special_price'" in FETCH_PHP
        or "attribute_code='special_price'" in FETCH_PHP
    )


def test_magento_update_rows_maps_target_to_price():
    rows = magento_update_rows(
        [{"sku": "0010170536", "target": 278460, "delta": 21420}]
    )
    assert rows == [{"sku": "0010170536", "price": 278460, "store_id": 0}]
