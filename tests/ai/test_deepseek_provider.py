"""DeepSeek OpenAI-compatible provider wiring."""

from unittest.mock import Mock, patch

from business_analyzer.ai.base import SUPPORTED_PROVIDERS, create_ai_client
from business_analyzer.ai.insights import _openai_compatible_model
from business_analyzer.ai.providers.deepseek import DeepSeekProvider


def test_supported_providers_include_deepseek():
    assert "deepseek" in SUPPORTED_PROVIDERS


def test_deepseek_key_validation():
    assert DeepSeekProvider.validate_api_key("sk-abc")
    assert not DeepSeekProvider.validate_api_key("xai-abc")
    assert not DeepSeekProvider.validate_api_key("")


def test_create_ai_client_deepseek(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-deepseek")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    fake_client = Mock()
    with patch("business_analyzer.ai.base.OpenAI", return_value=fake_client) as ctor:
        with patch(
            "business_analyzer.ai.base.Config.DEEPSEEK_API_KEY",
            "sk-test-deepseek",
        ):
            client, config, provider_type = create_ai_client("deepseek")
    assert client is fake_client
    assert provider_type == "openai"
    assert config["model"] == "deepseek-chat"
    assert config["base_url"] == "https://api.deepseek.com"
    ctor.assert_called_once_with(
        api_key="sk-test-deepseek",
        base_url="https://api.deepseek.com",
    )


def test_insights_model_for_deepseek(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    assert _openai_compatible_model("deepseek") == "deepseek-chat"
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    assert _openai_compatible_model("deepseek") == "deepseek-v4-flash"
