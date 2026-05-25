import sys
import types

import pytest

import src.vanna_chat as vanna_chat


def _install_fake_vanna_modules(monkeypatch):
    vanna_pkg = types.ModuleType("vanna")
    vanna_pkg.__path__ = []

    openai_module = types.ModuleType("vanna.openai")
    vannadb_module = types.ModuleType("vanna.vannadb")
    chromadb_module = types.ModuleType("vanna.chromadb")
    ollama_module = types.ModuleType("vanna.ollama")
    anthropic_module = types.ModuleType("vanna.anthropic")

    class OpenAI_Chat:
        def __init__(self, config=None):
            self.chat_backend = "openai"
            self.chat_config = config

    class VannaDB_VectorStore:
        def __init__(self, vanna_model=None, vanna_api_key=None, config=None):
            self.vector_store = "vannadb"
            self.vanna_model = vanna_model
            self.vanna_api_key = vanna_api_key
            self.vector_config = config

    class ChromaDB_VectorStore:
        def __init__(self, config=None):
            self.vector_store = "chromadb"
            self.vector_config = config

    class Ollama:
        def __init__(self, config=None):
            self.chat_backend = "ollama"
            self.chat_config = config

    class Anthropic_Chat:
        def __init__(self, config=None):
            self.chat_backend = "anthropic"
            self.chat_config = config

    setattr(openai_module, "OpenAI_Chat", OpenAI_Chat)
    setattr(vannadb_module, "VannaDB_VectorStore", VannaDB_VectorStore)
    setattr(chromadb_module, "ChromaDB_VectorStore", ChromaDB_VectorStore)
    setattr(ollama_module, "Ollama", Ollama)
    setattr(anthropic_module, "Anthropic_Chat", Anthropic_Chat)

    monkeypatch.setitem(sys.modules, "vanna", vanna_pkg)
    monkeypatch.setitem(sys.modules, "vanna.openai", openai_module)
    monkeypatch.setitem(sys.modules, "vanna.vannadb", vannadb_module)
    monkeypatch.setitem(sys.modules, "vanna.chromadb", chromadb_module)
    monkeypatch.setitem(sys.modules, "vanna.ollama", ollama_module)
    monkeypatch.setitem(sys.modules, "vanna.anthropic", anthropic_module)


def _set_provider_flags(
    monkeypatch,
    *,
    use_openai=False,
    use_ollama=False,
    use_anthropic=False,
    use_grok=False,
):
    monkeypatch.setattr(vanna_chat, "USE_OPENAI", use_openai)
    monkeypatch.setattr(vanna_chat, "USE_OLLAMA", use_ollama)
    monkeypatch.setattr(vanna_chat, "USE_ANTHROPIC", use_anthropic)
    monkeypatch.setattr(vanna_chat, "USE_GROK", use_grok)


def test_create_vanna_instance_selects_openai_branch(monkeypatch):
    _install_fake_vanna_modules(monkeypatch)
    _set_provider_flags(monkeypatch, use_openai=True)
    monkeypatch.setattr(vanna_chat, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("VANNA_API_KEY", "vanna-hosted-key")

    vn = vanna_chat.create_vanna_instance()

    assert vn.vector_store == "vannadb"
    assert vn.vanna_model == "smartbusiness-model"
    assert vn.vanna_api_key == "vanna-hosted-key"
    assert vn.chat_backend == "openai"
    assert vn.chat_config == {"api_key": "openai-key", "model": "gpt-4"}


def test_create_vanna_instance_selects_ollama_branch(monkeypatch):
    _install_fake_vanna_modules(monkeypatch)
    _set_provider_flags(monkeypatch, use_ollama=True)
    monkeypatch.setattr(vanna_chat, "OLLAMA_MODEL", "custom-ollama")

    vn = vanna_chat.create_vanna_instance()

    assert vn.vector_store == "chromadb"
    assert vn.chat_backend == "ollama"
    assert vn.chat_config == {
        "model": "custom-ollama",
        "ollama_host": "http://localhost:11434",
    }


def test_create_vanna_instance_selects_anthropic_branch(monkeypatch):
    _install_fake_vanna_modules(monkeypatch)
    _set_provider_flags(monkeypatch, use_anthropic=True)
    monkeypatch.setattr(vanna_chat, "ANTHROPIC_API_KEY", "anthropic-key")

    vn = vanna_chat.create_vanna_instance()

    assert vn.vector_store == "chromadb"
    assert vn.chat_backend == "anthropic"
    assert vn.chat_config == {
        "api_key": "anthropic-key",
        "model": "claude-3-sonnet-20240229",
    }


def test_create_vanna_instance_selects_grok_branch(monkeypatch):
    _install_fake_vanna_modules(monkeypatch)
    _set_provider_flags(monkeypatch, use_grok=True)
    monkeypatch.setattr(vanna_chat, "GROK_API_KEY", "grok-key")

    vn = vanna_chat.create_vanna_instance()

    assert vn.vector_store == "chromadb"
    assert vn.chat_backend == "openai"
    assert vn.chat_config == {
        "api_key": "grok-key",
        "model": "grok-beta",
        "base_url": "https://api.x.ai/v1",
    }


def test_create_vanna_instance_raises_when_no_provider_enabled(monkeypatch):
    _install_fake_vanna_modules(monkeypatch)
    _set_provider_flags(monkeypatch)

    with pytest.raises(ValueError, match="Please enable one of"):
        vanna_chat.create_vanna_instance()
