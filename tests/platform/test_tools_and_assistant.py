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
    assert "Bodega del Sur" in resp.reply
    assert "Bodega Mangueras" in resp.reply
    assert "Bodega 6" in resp.reply
    assert "Distribuciones" in resp.reply or "Calle 5" in resp.reply
    assert "Dirección:" in resp.reply
    assert "Calle 24" in resp.reply or "Carrera 20" in resp.reply
    assert "depositotrujillo.co/bodegas" in resp.reply
    assert "info.branches" in resp.tools_used
    assert resp.grounded is True
    # No internal ERP branch codes for customers
    assert "FED" not in resp.reply
    assert "FEF" not in resp.reply
    assert "FET" not in resp.reply


@pytest.mark.unit
@pytest.mark.module_assistant
def test_assistant_branches_cuales_son_las_sedes():
    resp = run_assistant_turn(
        ChatRequest(message="cuales son las sedes", audience=Audience.PUBLIC)
    )
    assert "Bodega" in resp.reply or "sedes" in resp.reply.lower()
    assert "Dirección:" in resp.reply
    assert "info.branches" in resp.tools_used


@pytest.mark.unit
@pytest.mark.module_assistant
def test_assistant_bodegas_keyword_routes():
    resp = run_assistant_turn(
        ChatRequest(message="dónde quedan las bodegas", audience=Audience.PUBLIC)
    )
    assert "info.branches" in resp.tools_used
    assert "Bodega del Sur" in resp.reply
    assert "Horario:" in resp.reply


@pytest.mark.unit
@pytest.mark.module_assistant
def test_assistant_ignores_sku_customer_language():
    """Customers don't use SKUs — assistant must not push SKU workflows."""
    resp = run_assistant_turn(
        ChatRequest(
            message="hay stock del SKU 1234567890?",
            audience=Audience.PUBLIC,
        )
    )
    # No inventory-by-SKU path for storefront; guide them to problem/name language
    assert "inventory.sellable_qty" not in resp.tools_used
    assert "sku" not in resp.reply.lower()


@pytest.mark.unit
@pytest.mark.module_assistant
def test_assistant_product_name_search_routes():
    from modules.assistant.chat import extract_product_query

    assert extract_product_query("tienen cemento?") == "cemento"
    assert extract_product_query("stock de cemento") == "cemento"
    assert extract_product_query("busco varilla 1/2") == "varilla 1/2"
    assert extract_product_query("cotizar un tanque ajover") is not None
    assert (
        "rodillo"
        in (
            extract_product_query('HOLA ANDO BUSCANDO 15 RODILLOS PROFESIONAL DE 4"')
            or ""
        ).lower()
    )

    resp = run_assistant_turn(
        ChatRequest(message="tienen cemento?", audience=Audience.PUBLIC)
    )
    assert "catalog.search_products" in resp.tools_used
    # Either product hits or storefront search URL — never bare generic help
    assert "cemento" in resp.reply.lower()
    assert "modo herramientas" not in resp.reply.lower()
    # Never list SKU codes to customers
    assert not any(
        line.strip().startswith("- ") and ":" in line and any(c.isdigit() for c in line)
        for line in resp.reply.splitlines()
        if "SKU" in line.upper()
    )
    assert "SKU" not in resp.reply


@pytest.mark.unit
@pytest.mark.module_assistant
def test_assistant_greeting_no_platform_health():
    """Chat-log: greetings must not call platform.health."""
    for msg in (
        "Hola",
        "buenas noches",
        "buen día",
        "hola buenos dias",
        "hello mister",
    ):
        resp = run_assistant_turn(ChatRequest(message=msg, audience=Audience.PUBLIC))
        assert "platform.health" not in resp.tools_used, msg
        assert "asistente" in resp.reply.lower() or "depósito" in resp.reply.lower()


@pytest.mark.unit
@pytest.mark.module_assistant
def test_assistant_chat_log_product_and_guide_routes():
    """Routes derived from production chat_log.jsonl unmatched turns."""
    # Cotizar tanque → guide or catalog, never health
    resp = run_assistant_turn(
        ChatRequest(message="cotizar un tanque ajover", audience=Audience.PUBLIC)
    )
    assert "platform.health" not in resp.tools_used
    assert (
        resp.guide_id == "tanque_agua" or "catalog.search_products" in resp.tools_used
    )
    assert "tanque" in resp.reply.lower()

    # Greeting + product search
    resp = run_assistant_turn(
        ChatRequest(
            message='HOLA ANDO BUSCANDO 15 RODILLOS PROFESIONAL DE 4"',
            audience=Audience.PUBLIC,
        )
    )
    assert "platform.health" not in resp.tools_used
    assert "catalog.search_products" in resp.tools_used
    assert "rodillo" in resp.reply.lower() or "rodillos" in resp.reply.lower()

    # Bare product / typo anticorrosivo → metal paint guide or catalog
    resp = run_assistant_turn(
        ChatRequest(message="SDS anticorrisvo negro", audience=Audience.PUBLIC)
    )
    assert "platform.health" not in resp.tools_used
    assert (
        resp.guide_id == "pintura_metal" or "catalog.search_products" in resp.tools_used
    )

    # Lámina galvanizada
    resp = run_assistant_turn(
        ChatRequest(
            message="necesito un lamina galvanizada calibre 12",
            audience=Audience.PUBLIC,
        )
    )
    assert "platform.health" not in resp.tools_used
    assert resp.guide_id == "teja_zinc" or "catalog.search_products" in resp.tools_used
    assert (
        "lám" in resp.reply.lower()
        or "lamina" in resp.reply.lower()
        or "zinc" in resp.reply.lower()
        or "catálogo" in resp.reply.lower()
        or "productos" in resp.reply.lower()
    )


@pytest.mark.unit
@pytest.mark.module_assistant
def test_assistant_cart_pay_not_product_search():
    resp = run_assistant_turn(
        ChatRequest(
            message="Necesito pagar por internet lo que tengo en el carro me ayudas",
            audience=Audience.PUBLIC,
        )
    )
    assert "catalog.search_products" not in resp.tools_used
    assert "platform.health" not in resp.tools_used
    assert "carrito" in resp.reply.lower() or "checkout" in resp.reply.lower()
    assert "pagar" in resp.reply.lower() or "tienda" in resp.reply.lower()


@pytest.mark.unit
@pytest.mark.module_assistant
def test_assistant_sede_quede_principal():
    resp = run_assistant_turn(
        ChatRequest(message="Dónde quede la sede principal", audience=Audience.PUBLIC)
    )
    assert "info.branches" in resp.tools_used
    assert "Dirección:" in resp.reply
    assert "Bodega" in resp.reply or "Distribuciones" in resp.reply


@pytest.mark.unit
@pytest.mark.module_assistant
def test_assistant_problem_gotera_guide():
    resp = run_assistant_turn(
        ChatRequest(message="tengo una gotera en el techo", audience=Audience.PUBLIC)
    )
    assert "gotera" in resp.reply.lower() or "filtración" in resp.reply.lower()
    assert "impermeabilizante" in resp.reply.lower() or "sellador" in resp.reply.lower()
    assert "SKU" not in resp.reply
    assert "catalog.search_products" in resp.tools_used


@pytest.mark.unit
@pytest.mark.module_assistant
def test_assistant_problem_pintar_habitacion():
    from modules.assistant.problem_guides import match_guide

    assert match_guide("qué necesito para pintar una habitación") is not None
    resp = run_assistant_turn(
        ChatRequest(
            message="qué necesito para pintar una habitación?",
            audience=Audience.PUBLIC,
        )
    )
    assert "pint" in resp.reply.lower()
    assert "rodillo" in resp.reply.lower() or "brocha" in resp.reply.lower()
    assert "SKU" not in resp.reply


@pytest.mark.unit
@pytest.mark.module_assistant
def test_problem_guides_expanded_coverage():
    """New guides should match common storefront job phrases."""
    from modules.assistant.problem_guides import GUIDES, match_guide

    assert len(GUIDES) >= 30
    cases = {
        "quiero instalar un tanque de agua": "tanque_agua",
        "necesito drywall para un cielorraso": "drywall",
        "se me tapó el desagüe del baño": "destape_desague",
        "cómo impermeabilizar la terraza": "impermeabilizar_terraza",
        "materiales para un portón": "porton",
        "pintar el hierro con óxido": "pintura_metal",
        "kit de herramientas para la casa": "herramientas_basicas",
        "instalar un inodoro": "inodoro_sanitario",
        "malla angeo para zancudos": "mosquitero",
        "bomba de agua con poca presión": "bomba_agua",
    }
    for phrase, expected_id in cases.items():
        guide = match_guide(phrase)
        assert guide is not None, phrase
        assert guide.id == expected_id, f"{phrase} → {guide.id} (want {expected_id})"


@pytest.mark.unit
@pytest.mark.module_assistant
def test_assistant_problem_tanque_reply_no_sku():
    resp = run_assistant_turn(
        ChatRequest(
            message="qué necesito para instalar un tanque de agua?",
            audience=Audience.PUBLIC,
        )
    )
    assert "tanque" in resp.reply.lower()
    assert "SKU" not in resp.reply
    assert "catalog.search_products" in resp.tools_used


@pytest.mark.unit
def test_v1_api_tools_and_chat(monkeypatch: pytest.MonkeyPatch):
    from api import app

    # Sourced deploy/bff/env.bff must not force 401 in unit tests
    monkeypatch.delenv("PLATFORM_API_KEYS", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)

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
    assert "Bodega" in body["reply"] or "sedes" in body["reply"].lower()
    assert "Dirección:" in body["reply"] or "bodegas" in body["reply"].lower()
    assert body["grounded"] is True
    assert "FED" not in body["reply"]
    # Response schema includes optional routing diagnostics
    assert "guide_id" in body
    assert "product_query" in body

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
