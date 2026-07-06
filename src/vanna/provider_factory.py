import os
from dataclasses import dataclass
from importlib import import_module
from typing import Any


@dataclass(frozen=True)
class ProviderSettings:
    use_openai: bool
    use_ollama: bool
    use_anthropic: bool
    use_grok: bool
    openai_api_key: str
    ollama_model: str
    anthropic_api_key: str
    grok_api_key: str


def create_vanna_provider(settings: ProviderSettings) -> Any:
    if settings.use_openai:
        openai_module = import_module("vanna.openai")
        vannadb_module = import_module("vanna.vannadb")
        openai_chat_cls = getattr(openai_module, "OpenAI_Chat")
        vector_store_cls = getattr(vannadb_module, "VannaDB_VectorStore")

        openai_vanna_cls = type("OpenAIVanna", (vector_store_cls, openai_chat_cls), {})
        vn = openai_vanna_cls()
        config = {"api_key": settings.openai_api_key, "model": "gpt-4"}
        vector_store_cls.__init__(
            vn,
            vanna_model="smartbusiness-model",
            vanna_api_key=os.getenv("VANNA_API_KEY", ""),
            config=config,
        )
        openai_chat_cls.__init__(vn, config=config)
        return vn

    if settings.use_ollama:
        chromadb_module = import_module("vanna.chromadb")
        ollama_module = import_module("vanna.ollama")
        vector_store_cls = getattr(chromadb_module, "ChromaDB_VectorStore")
        ollama_cls = getattr(ollama_module, "Ollama")

        ollama_vanna_cls = type("OllamaVanna", (vector_store_cls, ollama_cls), {})
        vn = ollama_vanna_cls()
        config = {
            "model": settings.ollama_model,
            "ollama_host": "http://localhost:11434",
        }
        vector_store_cls.__init__(vn, config=config)
        ollama_cls.__init__(vn, config=config)
        return vn

    if settings.use_anthropic:
        anthropic_module = import_module("vanna.anthropic")
        chromadb_module = import_module("vanna.chromadb")
        anthropic_chat_cls = getattr(anthropic_module, "Anthropic_Chat")
        vector_store_cls = getattr(chromadb_module, "ChromaDB_VectorStore")

        anthropic_vanna_cls = type(
            "AnthropicVanna", (vector_store_cls, anthropic_chat_cls), {}
        )
        vn = anthropic_vanna_cls()
        config = {
            "api_key": settings.anthropic_api_key,
            "model": "claude-3-sonnet-20240229",
        }
        vector_store_cls.__init__(vn, config=config)
        anthropic_chat_cls.__init__(vn, config=config)
        return vn

    if settings.use_grok:
        chromadb_module = import_module("vanna.chromadb")
        openai_module = import_module("vanna.openai")
        vector_store_cls = getattr(chromadb_module, "ChromaDB_VectorStore")
        openai_chat_cls = getattr(openai_module, "OpenAI_Chat")

        grok_vanna_cls = type("GrokVanna", (vector_store_cls, openai_chat_cls), {})
        vn = grok_vanna_cls()
        config = {
            "api_key": settings.grok_api_key,
            "model": "grok-beta",
            "base_url": "https://api.x.ai/v1",
        }
        vector_store_cls.__init__(vn, config=config)
        config_with_grok = dict(config)
        config_with_grok["base_url"] = "https://api.x.ai/v1"
        config_with_grok["api_key"] = settings.grok_api_key
        openai_chat_cls.__init__(vn, config=config_with_grok)
        return vn

    raise ValueError(
        "Please enable one of: USE_OPENAI, USE_OLLAMA, USE_ANTHROPIC, or USE_GROK"
    )
