"""OpenAI-compatible provider wiring (deepseek, groq, openrouter, commandcode)."""

from unittest.mock import Mock, patch

from business_analyzer.ai.base import SUPPORTED_PROVIDERS, create_ai_client
from business_analyzer.ai.insights import _openai_compatible_model
from business_analyzer.ai.providers.deepseek import DeepSeekProvider

CONFIG = "business_analyzer.core.config.Config"


def test_supported_providers_include_new_backends():
    for provider in ("deepseek", "openrouter", "groq", "commandcode"):
        assert provider in SUPPORTED_PROVIDERS


def test_deepseek_key_validation():
    assert DeepSeekProvider.validate_api_key("sk-abc")
    assert not DeepSeekProvider.validate_api_key("xai-abc")
    assert not DeepSeekProvider.validate_api_key("")


def test_create_ai_client_deepseek():
    fake_client = Mock()
    with patch("business_analyzer.ai.llm.OpenAI", return_value=fake_client) as ctor:
        with patch(CONFIG + ".DEEPSEEK_API_KEY", "sk-test-deepseek"):
            with patch(CONFIG + ".DEEPSEEK_MODEL", "deepseek-chat"):
                client, config, provider_type = create_ai_client("deepseek")
    assert client is fake_client
    assert provider_type == "openai"
    assert config["model"] == "deepseek-chat"
    assert config["base_url"] == "https://api.deepseek.com"
    ctor.assert_called_once_with(
        api_key="sk-test-deepseek",
        base_url="https://api.deepseek.com",
    )


def test_create_ai_client_groq():
    fake_client = Mock()
    with patch("business_analyzer.ai.llm.OpenAI", return_value=fake_client) as ctor:
        with patch(CONFIG + ".GROQ_API_KEY", "gsk_test_key"):
            with patch(CONFIG + ".GROQ_BASE_URL", "https://api.groq.com/openai/v1"):
                with patch(CONFIG + ".GROQ_MODEL", "qwen/qwen3.8-27b"):
                    client, config, provider_type = create_ai_client("groq")
    assert client is fake_client
    assert provider_type == "openai"
    assert config["model"] == "qwen/qwen3.8-27b"
    assert config["base_url"] == "https://api.groq.com/openai/v1"
    ctor.assert_called_once_with(
        api_key="gsk_test_key",
        base_url="https://api.groq.com/openai/v1",
    )


def test_create_ai_client_openrouter():
    fake_client = Mock()
    with patch("business_analyzer.ai.llm.OpenAI", return_value=fake_client) as ctor:
        with patch(CONFIG + ".OPENROUTER_API_KEY", "sk-or-test-key"):
            with patch(CONFIG + ".OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"):
                with patch(
                    CONFIG + ".OPENROUTER_MODEL", "deepseek/deepseek-v4.1-flash"
                ):
                    client, config, provider_type = create_ai_client("openrouter")
    assert client is fake_client
    assert provider_type == "openai"
    assert config["model"] == "deepseek/deepseek-v4.1-flash"
    assert config["base_url"] == "https://openrouter.ai/api/v1"
    ctor.assert_called_once_with(
        api_key="sk-or-test-key",
        base_url="https://openrouter.ai/api/v1",
    )


def test_create_ai_client_commandcode():
    fake_client = Mock()
    with patch(
        "business_analyzer.ai.commandcode_client.CommandCodeClient",
        return_value=fake_client,
    ) as ctor:
        client, config, provider_type = create_ai_client("commandcode")
    assert client is fake_client
    assert provider_type == "openai"
    assert config["model"] == "deepseek/deepseek-v4.1-flash"
    ctor.assert_called_once_with(model="deepseek/deepseek-v4.1-flash")


def test_insights_model_for_deepseek(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    assert _openai_compatible_model("deepseek") == "deepseek-chat"
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    assert _openai_compatible_model("deepseek") == "deepseek-v4-flash"
