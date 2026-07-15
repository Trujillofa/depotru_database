"""Hybrid stub-first LLM assistant tests (mocked LLM, no network)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, List
from unittest.mock import MagicMock

import pytest

from depotru_kernel.auth import Audience
from depotru_tools.registry import reset_default_registry
from modules.assistant import llm_router
from modules.assistant.chat import ChatRequest, run_assistant_turn, run_stub_turn


@pytest.fixture(autouse=True)
def _fresh_registry():
    reset_default_registry()
    yield
    reset_default_registry()


@pytest.mark.unit
@pytest.mark.module_assistant
def test_llm_disabled_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ASSISTANT_LLM", raising=False)
    monkeypatch.setenv("GROK_API_KEY", "xai-test-key")
    assert llm_router.llm_enabled() is False


@pytest.mark.unit
@pytest.mark.module_assistant
def test_llm_enabled_requires_flag_and_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ASSISTANT_LLM", "1")
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert llm_router.llm_enabled() is False

    monkeypatch.setenv("GROK_API_KEY", "xai-test-key")
    assert llm_router.llm_enabled() is True


@pytest.mark.unit
@pytest.mark.module_assistant
def test_stub_confident_paths_do_not_call_llm(monkeypatch: pytest.MonkeyPatch):
    """Greetings / guides / sedes never hit the LLM."""
    monkeypatch.setenv("ASSISTANT_LLM", "1")
    monkeypatch.setenv("GROK_API_KEY", "xai-test-key")

    called: List[str] = []

    def boom(**_kwargs: Any):
        called.append("llm")
        raise AssertionError("LLM must not run for confident stub")

    monkeypatch.setattr(llm_router, "run_llm_turn", boom)

    for msg in (
        "Hola",
        "tengo una gotera en el techo",
        "¿dónde están las sedes?",
        "tienen cemento?",
        "Necesito pagar por internet lo que tengo en el carro",
    ):
        resp = run_assistant_turn(ChatRequest(message=msg, audience=Audience.PUBLIC))
        assert resp.mode == "stub_tools", msg
        assert resp.llm_eligible is False, msg

    assert called == []


# Free-form intent that must not match a curated guide (→ LLM-eligible help)
_FREEFORM = "quiero armar un closet empotrado económico con puertas corredizas"


@pytest.mark.unit
@pytest.mark.module_assistant
def test_stub_fallback_llm_eligible_when_disabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ASSISTANT_LLM", raising=False)
    # Free-form intent → generic help when LLM off
    stub = run_stub_turn(ChatRequest(message=_FREEFORM, audience=Audience.PUBLIC))
    assert stub.llm_eligible is True
    assert stub.mode == "stub_tools"
    assert stub.guide_id is None

    resp = run_assistant_turn(ChatRequest(message=_FREEFORM, audience=Audience.PUBLIC))
    assert resp.mode == "stub_tools"
    assert "asistente" in resp.reply.lower() or "depósito" in resp.reply.lower()


@pytest.mark.unit
@pytest.mark.module_assistant
def test_hybrid_uses_llm_on_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ASSISTANT_LLM", "1")
    monkeypatch.setenv("GROK_API_KEY", "xai-test-key")

    def fake_llm(**_kwargs: Any):
        return (
            "Para un closet empotrado te conviene listones, tornillos y correderas.",
            ["catalog.search_products"],
            [{"tool": "catalog.search_products", "result": {"products": []}}],
        )

    monkeypatch.setattr(llm_router, "run_llm_turn", fake_llm)

    resp = run_assistant_turn(ChatRequest(message=_FREEFORM, audience=Audience.PUBLIC))
    assert resp.mode == "llm_tools"
    assert "closet" in resp.reply.lower() or "listones" in resp.reply.lower()
    assert "catalog.search_products" in resp.tools_used
    assert "SKU" not in resp.reply


@pytest.mark.unit
@pytest.mark.module_assistant
def test_llm_failure_falls_back_to_stub_help(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ASSISTANT_LLM", "1")
    monkeypatch.setenv("GROK_API_KEY", "xai-test-key")
    monkeypatch.setattr(llm_router, "run_llm_turn", lambda **_k: None)

    resp = run_assistant_turn(ChatRequest(message=_FREEFORM, audience=Audience.PUBLIC))
    assert resp.mode == "stub_tools"
    assert resp.llm_eligible is True  # stub help still marked; API does not care


@pytest.mark.unit
@pytest.mark.module_assistant
def test_tools_for_llm_allowlist_only():
    from depotru_tools.registry import get_default_registry

    tools = llm_router.tools_for_llm(get_default_registry(), Audience.PUBLIC)
    names = {t["function"]["name"] for t in tools}
    assert "info.branches" in names
    assert "catalog.search_products" in names
    assert "platform.health" not in names
    assert "catalog.related_for_sku" not in names
    assert "inventory.sellable_qty" not in names
    assert "attribution.resolve_seller" not in names


@pytest.mark.unit
@pytest.mark.module_assistant
def test_execute_blocks_non_allowlisted_tool():
    from depotru_tools.registry import ToolContext, get_default_registry

    reg = get_default_registry()
    ctx = ToolContext(audience=Audience.PUBLIC)
    result, err = llm_router._execute_tool(
        reg, ctx, "attribution.resolve_seller", {"code": "095"}
    )
    assert result is None
    assert err is not None
    assert "not allowed" in err.lower()


@pytest.mark.unit
@pytest.mark.module_assistant
def test_sanitize_strips_sku_lines():
    text = "Te recomiendo:\n• Pintura vinilo\nSKU: 002001\n• Rodillo"
    out = llm_router.sanitize_customer_reply(text)
    assert "002001" not in out
    assert "Pintura" in out


@pytest.mark.unit
@pytest.mark.module_assistant
def test_run_llm_turn_mocked_openai(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ASSISTANT_LLM", "1")
    monkeypatch.setenv("GROK_API_KEY", "xai-test-key")

    # Message with no tool_calls → direct text
    mock_msg = SimpleNamespace(
        content="Hola, soy el asistente de la tienda.", tool_calls=None
    )
    mock_choice = SimpleNamespace(message=mock_msg)
    mock_resp = SimpleNamespace(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    mock_openai_cls = MagicMock(return_value=mock_client)
    mock_mod = MagicMock()
    mock_mod.OpenAI = mock_openai_cls
    monkeypatch.setitem(__import__("sys").modules, "openai", mock_mod)

    from depotru_tools.registry import get_default_registry

    out = llm_router.run_llm_turn(
        message="ayuda genérica sin match",
        session_id="s1",
        audience=Audience.PUBLIC,
        registry=get_default_registry(),
    )
    assert out is not None
    reply, tools_used, _ = out
    assert "asistente" in reply.lower()
    assert tools_used == []
    mock_client.chat.completions.create.assert_called()
