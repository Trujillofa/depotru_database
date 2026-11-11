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
def test_search_products_includes_effective_price(monkeypatch):
    cfg = MagentoConfig(
        base_url="https://www.depositotrujillo.co",
        access_token="dummy",
    )
    client = MagentoRestClient(cfg)

    def fake_request(method, path, body=None):
        assert method == "GET"
        return {
            "items": [
                {
                    "sku": "0020080005",
                    "name": "Cemento Argos",
                    "price": 36428,
                    "status": 1,
                    "type_id": "simple",
                    "custom_attributes": [
                        {"attribute_code": "url_key", "value": "cemento-argos"},
                        {"attribute_code": "special_price", "value": "29900"},
                    ],
                }
            ]
        }

    monkeypatch.setattr(client, "_request", fake_request)
    out = client.search_products("cemento")
    assert out[0]["price"] == 29900.0
    assert out[0]["list_price"] == 36428.0
    assert out[0]["product_url"].endswith("/cemento-argos.html")


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
