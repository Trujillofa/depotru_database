"""Magento client product URL helpers (no network)."""

import pytest

from depotru_integrations.magento.client import MagentoConfig, MagentoRestClient


@pytest.mark.unit
def test_product_url_for_key():
    cfg = MagentoConfig(
        base_url="https://www.depositotrujillo.co",
        access_token="dummy",
    )
    client = MagentoRestClient(cfg)
    url = client.product_url_for_key("cemento-gris-cemex-50kg")
    assert url == ("https://www.depositotrujillo.co/cemento-gris-cemex-50kg.html")


@pytest.mark.unit
def test_custom_attr_url_key():
    item = {
        "sku": "X",
        "name": "Test",
        "custom_attributes": [
            {"attribute_code": "url_key", "value": "mi-producto"},
            {"attribute_code": "description", "value": "x"},
        ],
    }
    assert MagentoRestClient._custom_attr(item, "url_key") == "mi-producto"
    assert MagentoRestClient._custom_attr(item, "missing") == ""
