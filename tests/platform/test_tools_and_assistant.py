"""Tool registry and assistant stub tests."""

import pytest
from fastapi.testclient import TestClient

from depotru_kernel.auth import Audience
from depotru_tools.registry import (
    ToolContext,
    ToolPermissionError,
    get_default_registry,
    reset_default_registry,
)
from modules.assistant.chat import ChatRequest, run_assistant_turn


@pytest.fixture(autouse=True)
def _fresh_registry():
    reset_default_registry()
    yield
    reset_default_registry()


@pytest.mark.unit
def test_registry_lists_public_tools_only():
    reg = get_default_registry()
    public = reg.list_tools(audience=Audience.PUBLIC)
    names = {t["name"] for t in public}
    assert "platform.health" in names
    assert "info.branches" in names
    assert "catalog.related_for_sku" in names
    assert "inventory.sellable_qty" in names
    assert "attribution.resolve_seller" not in names


@pytest.mark.unit
def test_public_cannot_call_attribution():
    reg = get_default_registry()
    with pytest.raises(ToolPermissionError):
        reg.call(
            "attribution.resolve_seller",
            {"code": "095"},
            context=ToolContext(audience=Audience.PUBLIC),
        )


@pytest.mark.unit
def test_sales_can_resolve_seller():
    reg = get_default_registry()
    out = reg.call(
        "attribution.resolve_seller",
        {"asignado": "163-BETSY", "name": "HUBER SANTIAGO ENCISO", "code": "044"},
        context=ToolContext(audience=Audience.SALES),
    )
    assert out["code"] == "163"


@pytest.mark.unit
@pytest.mark.module_assistant
def test_assistant_branches_turn():
    resp = run_assistant_turn(
        ChatRequest(message="¿dónde están las sedes?", audience=Audience.PUBLIC)
    )
    assert "FED" in resp.reply
    assert "info.branches" in resp.tools_used
    assert resp.grounded is True


@pytest.mark.unit
@pytest.mark.module_assistant
def test_assistant_branches_cuales_son_las_sedes():
    resp = run_assistant_turn(
        ChatRequest(message="cuales son las sedes", audience=Audience.PUBLIC)
    )
    assert "FED" in resp.reply
    assert "info.branches" in resp.tools_used


@pytest.mark.unit
@pytest.mark.module_assistant
def test_assistant_stock_stub():
    resp = run_assistant_turn(
        ChatRequest(
            message="hay stock del SKU 1234567890?",
            audience=Audience.PUBLIC,
        )
    )
    assert "1234567890" in resp.reply
    assert "inventory.sellable_qty" in resp.tools_used


@pytest.mark.unit
@pytest.mark.module_assistant
def test_assistant_product_name_search_routes():
    from modules.assistant.chat import extract_product_query

    assert extract_product_query("tienen cemento?") == "cemento"
    assert extract_product_query("stock de cemento") == "cemento"
    assert extract_product_query("busco varilla 1/2") == "varilla 1/2"

    resp = run_assistant_turn(
        ChatRequest(message="tienen cemento?", audience=Audience.PUBLIC)
    )
    assert "catalog.search_products" in resp.tools_used
    # Either product hits or storefront search URL — never bare generic help
    assert "cemento" in resp.reply.lower()
    assert "modo herramientas" not in resp.reply.lower()


@pytest.mark.unit
def test_v1_api_tools_and_chat():
    from api import app

    client = TestClient(app)
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r2 = client.get("/v1/tools")
    assert r2.status_code == 200
    assert any(t["name"] == "platform.health" for t in r2.json()["tools"])

    r3 = client.post(
        "/v1/assistant/chat",
        json={"message": "ubicacion de las sedes"},
    )
    assert r3.status_code == 200
    body = r3.json()
    assert "FED" in body["reply"] or "sedes" in body["reply"].lower()
    assert body["grounded"] is True

    r4 = client.get("/v1/affinity/contract")
    assert r4.status_code == 200
    assert r4.json()["contract_version"] == "1.0.0"


@pytest.mark.unit
@pytest.mark.module_catalog
def test_affinity_contract_headers():
    from depotru_integrations.affinity.contract import (
        validate_crosssell_csv_header,
        validate_related_csv_header,
    )

    ok, msg = validate_related_csv_header(["SKU", "Rel_1_SKU", "Rel_2_SKU"])
    assert ok, msg
    ok2, msg2 = validate_crosssell_csv_header(["sku", "crosssell_skus"])
    assert ok2, msg2
    bad, _ = validate_crosssell_csv_header(["sku"])
    assert not bad
