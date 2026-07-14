"""Assistant chat JSONL logging."""

import json
from pathlib import Path

import pytest

from depotru_kernel.auth import Audience
from depotru_tools.registry import reset_default_registry
from modules.assistant.chat import ChatRequest, format_product_lines, run_assistant_turn
from modules.assistant.logging import log_assistant_turn


@pytest.fixture(autouse=True)
def _fresh_registry():
    reset_default_registry()
    yield
    reset_default_registry()


@pytest.mark.unit
@pytest.mark.module_assistant
def test_log_assistant_turn_writes_jsonl(tmp_path: Path):
    log_file = tmp_path / "chat_log.jsonl"
    ok = log_assistant_turn(
        session_id="sess-1",
        audience="public",
        locale="es_CO",
        message="tengo una gotera",
        reply="Gotera o filtración\n…",
        tools_used=["catalog.search_products"],
        mode="stub_tools",
        guide_id="gotera",
        product_query=None,
        grounded=True,
        log_path=log_file,
    )
    assert ok is True
    assert log_file.is_file()
    line = log_file.read_text(encoding="utf-8").strip()
    rec = json.loads(line)
    assert rec["session_id"] == "sess-1"
    assert rec["guide_id"] == "gotera"
    assert rec["message"] == "tengo una gotera"
    assert "catalog.search_products" in rec["tools_used"]
    assert "ts" in rec


@pytest.mark.unit
@pytest.mark.module_assistant
def test_log_never_raises_on_bad_path():
    # Unwritable path should return False, not raise
    ok = log_assistant_turn(
        session_id="x",
        audience="public",
        locale="es_CO",
        message="hola",
        reply="hi",
        log_path=Path("/proc/does-not-exist-assistant-log/x.jsonl"),
    )
    assert ok is False


@pytest.mark.unit
@pytest.mark.module_assistant
def test_format_product_lines_with_urls():
    text = format_product_lines(
        [
            {
                "name": "CEMENTO GRIS",
                "sku": "002001",
                "product_url": "https://www.depositotrujillo.co/cemento-gris.html",
            },
            {"name": "ARENA", "sku": "99"},
        ],
        limit=5,
    )
    assert "CEMENTO GRIS" in text
    assert "https://www.depositotrujillo.co/cemento-gris.html" in text
    assert "ARENA" in text
    assert "002001" not in text
    assert "SKU" not in text


@pytest.mark.unit
@pytest.mark.module_assistant
def test_chat_response_includes_guide_id():
    resp = run_assistant_turn(
        ChatRequest(message="tengo una gotera en el techo", audience=Audience.PUBLIC)
    )
    assert resp.guide_id == "gotera"
    assert "SKU" not in resp.reply


@pytest.mark.unit
@pytest.mark.module_assistant
def test_product_url_helper():
    from depotru_tools.builtins import storefront_product_url

    url = storefront_product_url("pintura-vinilo-blanco")
    assert url.endswith("pintura-vinilo-blanco.html")
    assert "depositotrujillo" in url or url.startswith("http")


@pytest.mark.unit
@pytest.mark.module_assistant
def test_v1_chat_writes_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from fastapi.testclient import TestClient

    from api import app

    log_file = tmp_path / "api_chat.jsonl"
    monkeypatch.setenv("ASSISTANT_CHAT_LOG", str(log_file))
    # Clear PLATFORM_API_KEYS so TestClient doesn't need a key
    monkeypatch.delenv("PLATFORM_API_KEYS", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)

    client = TestClient(app)
    r = client.post(
        "/v1/assistant/chat",
        json={"message": "cuales son las sedes"},
    )
    assert r.status_code == 200
    assert log_file.is_file()
    rec = json.loads(log_file.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert "sedes" in rec["message"].lower() or "cuales" in rec["message"].lower()
    assert rec["session_id"]
