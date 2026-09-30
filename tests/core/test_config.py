"""Tests for the unified pydantic-settings configuration.

No live database or AI provider calls. Secrets use placeholders only.
"""

from __future__ import annotations

import os

import pytest

from business_analyzer.core import config as config_mod
from business_analyzer.core.config import (
    Config,
    CustomerSegmentation,
    InventoryConfig,
    ProfitabilityConfig,
    Settings,
    get_env_or_test_default,
    hydrate_ai_config,
    require_env,
    resolve_database_settings,
)

_MISSING = object()

CONFIG_ENV_KEYS = (
    "NCX_FILE_PATH",
    "DB_HOST",
    "DB_PORT",
    "DB_USER",
    "DB_PASSWORD",
    "DB_NAME",
    "DB_NAME_J3SYSTEM",
    "DB_TABLE",
    "DB_LOGIN_TIMEOUT",
    "DB_TIMEOUT",
    "DB_TDS_VERSION",
    "OUTPUT_DIR",
    "REPORT_DPI",
    "DEFAULT_LIMIT",
    "LOG_LEVEL",
    "AI_PROVIDER",
    "GROK_API_KEY",
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "ANTHROPIC_API_KEY",
    "OLLAMA_HOST",
    "OLLAMA_MODEL",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
    "PORT",
    "HOST",
    "ENABLE_AI_INSIGHTS",
    "INSIGHTS_MAX_ROWS",
    "MAX_DISPLAY_ROWS",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASSWORD",
    "SMTP_USE_TLS",
    "MAIL_FROM",
    "MAIL_TO",
    "AKZONOBEL_CORE_LINES_CONFIG",
    "ASSISTANT_CHAT_LOG",
)


@pytest.fixture(autouse=True)
def restore_config_class_state():
    """Snapshot/restore Config attrs so reload() cannot leak across tests."""
    names = list(config_mod._SETTINGS_FIELD_NAMES) + ["OUTPUT_DIR", "_DB_SETTINGS"]
    snapshot = {name: getattr(Config, name, _MISSING) for name in names}
    yield
    for name, value in snapshot.items():
        if value is _MISSING:
            if hasattr(Config, name):
                delattr(Config, name)
        else:
            setattr(Config, name, value)


@pytest.fixture
def isolated_config_env(monkeypatch):
    """Drop known config env vars so documented defaults apply."""
    for key in CONFIG_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch


def test_settings_defaults_without_env(isolated_config_env):
    settings = Settings()
    assert settings.DB_HOST is None
    assert settings.DB_USER is None
    assert settings.DB_PASSWORD is None
    assert settings.DB_PORT == 1433
    assert settings.DB_NAME == "SmartBusiness"
    assert settings.DB_NAME_J3SYSTEM == "J3System"
    assert settings.DB_TABLE == "banco_datos"
    assert settings.DB_LOGIN_TIMEOUT == 30
    assert settings.DB_TIMEOUT == 180
    assert settings.DB_TDS_VERSION == "7.4"
    assert settings.REPORT_DPI == 300
    assert settings.DEFAULT_LIMIT == 1000
    assert settings.LOG_LEVEL == "INFO"
    assert settings.AI_PROVIDER == "grok"
    assert settings.GROK_API_KEY is None
    assert settings.OPENAI_API_KEY is None
    assert settings.DEEPSEEK_API_KEY is None
    assert settings.ANTHROPIC_API_KEY is None
    assert settings.OLLAMA_HOST == "http://localhost:11434"
    assert settings.OLLAMA_MODEL == "mistral"
    assert settings.DEEPSEEK_BASE_URL == "https://api.deepseek.com"
    assert settings.DEEPSEEK_MODEL == "deepseek-v4-flash"
    assert settings.PORT == 8084
    assert settings.HOST == "0.0.0.0"
    assert settings.ENABLE_AI_INSIGHTS is True
    assert settings.INSIGHTS_MAX_ROWS == 15
    assert settings.MAX_DISPLAY_ROWS == 100
    assert settings.SMTP_HOST is None
    assert settings.SMTP_PORT == 587
    assert settings.SMTP_USER is None
    assert settings.SMTP_PASSWORD is None
    assert settings.SMTP_USE_TLS is True
    assert settings.MAIL_FROM is None
    assert settings.MAIL_TO is None
    assert settings.AKZONOBEL_CORE_LINES_CONFIG is None
    assert settings.ASSISTANT_CHAT_LOG is None
    assert settings.NCX_FILE_PATH == os.path.expanduser(
        "~/Coding_OMARCHY/python_files/connections.ncx"
    )


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("FALSE", False),
        ("0", False),
        ("no", False),
        ("off", False),
        ("", True),
        ("   ", True),
        ("maybe", True),
    ],
)
def test_settings_smtp_use_tls_boolean_tokens(isolated_config_env, raw, expected):
    isolated_config_env.setenv("SMTP_USE_TLS", raw)
    assert Settings().SMTP_USE_TLS is expected


def test_settings_smtp_use_tls_defaults_on(isolated_config_env):
    isolated_config_env.delenv("SMTP_USE_TLS", raising=False)
    assert Settings().SMTP_USE_TLS is True


def test_settings_smtp_optional_overrides(isolated_config_env):
    isolated_config_env.setenv("SMTP_HOST", "smtp.example.test")
    isolated_config_env.setenv("SMTP_PORT", "465")
    isolated_config_env.setenv("SMTP_USE_TLS", "false")
    isolated_config_env.setenv("MAIL_FROM", "from@example.test")
    isolated_config_env.setenv("MAIL_TO", "to@example.test")
    settings = Settings()
    assert settings.SMTP_HOST == "smtp.example.test"
    assert settings.SMTP_PORT == 465
    assert settings.SMTP_USE_TLS is False
    assert settings.MAIL_FROM == "from@example.test"
    assert settings.MAIL_TO == "to@example.test"


def test_settings_akzonobel_config_path_override(isolated_config_env):
    isolated_config_env.setenv(
        "AKZONOBEL_CORE_LINES_CONFIG", "/tmp/akzo-demo-core-lines.yaml"
    )
    settings = Settings()
    assert settings.AKZONOBEL_CORE_LINES_CONFIG == "/tmp/akzo-demo-core-lines.yaml"


def test_settings_assistant_chat_log_path_override(isolated_config_env):
    isolated_config_env.setenv(
        "ASSISTANT_CHAT_LOG", "/tmp/synthetic-assistant-chat-log.jsonl"
    )
    settings = Settings()
    assert settings.ASSISTANT_CHAT_LOG == "/tmp/synthetic-assistant-chat-log.jsonl"


def test_settings_env_overrides(isolated_config_env):
    isolated_config_env.setenv("DB_HOST", "db.example.test")
    isolated_config_env.setenv("DB_PORT", "1444")
    isolated_config_env.setenv("DB_USER", "placeholder_user")
    isolated_config_env.setenv("DB_PASSWORD", "placeholder_password")
    isolated_config_env.setenv("DB_NAME", "OtherBusiness")
    isolated_config_env.setenv("AI_PROVIDER", "OpenAI")
    isolated_config_env.setenv("GROK_API_KEY", "xai-placeholder-key")
    isolated_config_env.setenv("ENABLE_AI_INSIGHTS", "false")
    isolated_config_env.setenv("PORT", "9090")
    isolated_config_env.setenv("LOG_LEVEL", "DEBUG")

    settings = Settings()
    assert settings.DB_HOST == "db.example.test"
    assert settings.DB_PORT == 1444
    assert settings.DB_USER == "placeholder_user"
    assert settings.DB_PASSWORD == "placeholder_password"
    assert settings.DB_NAME == "OtherBusiness"
    assert settings.AI_PROVIDER == "openai"
    assert settings.GROK_API_KEY == "xai-placeholder-key"
    assert settings.ENABLE_AI_INSIGHTS is False
    assert settings.PORT == 9090
    assert settings.LOG_LEVEL == "DEBUG"


def test_blank_db_strings_use_legacy_defaults(isolated_config_env):
    isolated_config_env.setenv("DB_HOST", "   ")
    isolated_config_env.setenv("DB_USER", "")
    isolated_config_env.setenv("DB_PASSWORD", " \t")
    isolated_config_env.setenv("DB_NAME", "  ")
    isolated_config_env.setenv("DB_PORT", " ")

    settings = Settings()
    assert settings.DB_HOST is None
    assert settings.DB_USER is None
    assert settings.DB_PASSWORD is None
    assert settings.DB_NAME == "SmartBusiness"
    assert settings.DB_PORT == 1433


def test_enable_ai_insights_only_true_is_truthy(isolated_config_env):
    isolated_config_env.setenv("ENABLE_AI_INSIGHTS", "yes")
    assert Settings().ENABLE_AI_INSIGHTS is False
    isolated_config_env.setenv("ENABLE_AI_INSIGHTS", "TRUE")
    assert Settings().ENABLE_AI_INSIGHTS is True


def test_settings_tolerates_invalid_port_and_row_limits(isolated_config_env):
    isolated_config_env.setenv("PORT", "not-a-port")
    isolated_config_env.setenv("INSIGHTS_MAX_ROWS", "abc")
    isolated_config_env.setenv("MAX_DISPLAY_ROWS", "")
    isolated_config_env.setenv("SMTP_PORT", "nope")

    settings = Settings()
    assert settings.PORT == 8084
    assert settings.INSIGHTS_MAX_ROWS == 15
    assert settings.MAX_DISPLAY_ROWS == 100
    assert settings.SMTP_PORT == 587


def test_config_reload_applies_settings_and_thresholds(isolated_config_env):
    Config.reload()
    assert Config.DB_NAME == "SmartBusiness"
    assert Config.EXCLUDED_DOCUMENT_CODES == ["XY", "AS", "TS", "YX", "ISC"]
    assert Config.REPORT_FIGURE_SIZE == (20, 24)
    assert Config.has_direct_db_config() is False
    assert CustomerSegmentation.VIP_REVENUE_THRESHOLD == 500000
    assert CustomerSegmentation.VIP_ORDERS_THRESHOLD == 5
    assert CustomerSegmentation.HIGH_VALUE_THRESHOLD == 200000
    assert CustomerSegmentation.FREQUENT_ORDERS_THRESHOLD == 10
    assert CustomerSegmentation.REGULAR_REVENUE_THRESHOLD == 50000
    assert InventoryConfig.FAST_MOVER_THRESHOLD == 5
    assert InventoryConfig.SLOW_MOVER_THRESHOLD == 2
    assert ProfitabilityConfig.LOW_MARGIN_THRESHOLD == 10
    assert ProfitabilityConfig.STAR_PRODUCT_MARGIN == 30
    assert ProfitabilityConfig.CRITICAL_MARGIN == 0


def test_validate_missing_required_db_and_ncx(isolated_config_env, tmp_path):
    Config.reload()
    Config.NCX_FILE_PATH = str(tmp_path / "missing-connections.ncx")
    with pytest.raises(ValueError, match="No valid database configuration"):
        Config.validate()


def test_validate_accepts_direct_db_config(isolated_config_env, caplog):
    isolated_config_env.setenv("DB_HOST", "db.example.test")
    isolated_config_env.setenv("DB_USER", "placeholder_user")
    isolated_config_env.setenv("DB_PASSWORD", "placeholder_password")

    Config.reload()
    assert Config.has_direct_db_config() is True
    with caplog.at_level("WARNING"):
        assert Config.validate() is True
    assert "direct database credentials" in caplog.text


def test_require_env_missing_exits(isolated_config_env):
    with pytest.raises(SystemExit) as excinfo:
        require_env("GROK_API_KEY")
    assert excinfo.value.code == 1


def test_require_env_invalid_value_exits(isolated_config_env):
    isolated_config_env.setenv("GROK_API_KEY", "not-an-xai-key")

    with pytest.raises(SystemExit) as excinfo:
        require_env(
            "GROK_API_KEY",
            validation_func=lambda value: value.startswith("xai-"),
            error_msg="La clave de Grok debe comenzar con 'xai-'",
        )
    assert excinfo.value.code == 1


def test_require_env_invalid_value_does_not_echo_value(isolated_config_env, capsys):
    leaked = "not-an-xai-key"
    isolated_config_env.setenv("GROK_API_KEY", leaked)

    with pytest.raises(SystemExit) as excinfo:
        require_env(
            "GROK_API_KEY",
            validation_func=lambda value: value.startswith("xai-"),
            error_msg="La clave de Grok debe comenzar con 'xai-'",
        )
    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert leaked not in captured.out
    assert leaked not in captured.err
    assert "GROK_API_KEY" in captured.out
    assert "inválido" in captured.out


def test_require_env_returns_valid_placeholder(isolated_config_env):
    isolated_config_env.setenv("GROK_API_KEY", "xai-placeholder-key")
    assert require_env("GROK_API_KEY") == "xai-placeholder-key"


def test_get_env_or_test_default_uses_placeholder_under_pytest(isolated_config_env):
    value = get_env_or_test_default(
        "GROK_API_KEY",
        test_default="xai-test-key-for-ci-only",
        warn_on_test_default=False,
    )
    assert value == "xai-test-key-for-ci-only"


def test_get_env_or_test_default_missing_in_production_exits(
    isolated_config_env, monkeypatch
):
    monkeypatch.setattr(config_mod, "_is_testing_env", lambda: False)
    with pytest.raises(SystemExit):
        config_mod.get_env_or_test_default(
            "GROK_API_KEY",
            test_default="xai-test-key-for-ci-only",
        )


def test_hydrate_ai_invalid_provider_exits(isolated_config_env):
    isolated_config_env.setenv("AI_PROVIDER", "not-a-provider")

    with pytest.raises(SystemExit) as excinfo:
        hydrate_ai_config()
    assert excinfo.value.code == 1


def test_hydrate_ai_missing_db_host_fails_fast_in_production(
    isolated_config_env, monkeypatch, capsys
):
    isolated_config_env.setenv("AI_PROVIDER", "grok")
    isolated_config_env.setenv("GROK_API_KEY", "xai-placeholder-key")
    Config.reload()
    before_host = Config.DB_HOST
    monkeypatch.setattr(config_mod, "_is_testing_env", lambda: False)

    with pytest.raises(SystemExit) as excinfo:
        hydrate_ai_config()
    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert "Variable de entorno requerida faltante: DB_HOST" in captured.out
    assert Config.DB_HOST is before_host


def test_hydrate_ai_stores_db_settings_off_config_db_attrs(isolated_config_env):
    isolated_config_env.setenv("AI_PROVIDER", "grok")
    isolated_config_env.setenv("GROK_API_KEY", "xai-placeholder-key")
    Config.reload()
    assert Config.DB_HOST is None

    hydrate_ai_config()
    assert Config._DB_SETTINGS["host"] == "test-host"
    assert Config._DB_SETTINGS["name"] == "TestDB"
    assert Config.DB_HOST is None
    assert Config.DB_USER is None
    assert Config.DB_PASSWORD is None
    assert Config.DB_NAME == "SmartBusiness"


def test_resolve_database_settings_test_defaults(isolated_config_env):
    settings = resolve_database_settings()
    assert settings["host"] == "test-host"
    assert settings["port"] == 1433
    assert settings["name"] == "TestDB"
    assert settings["user"] == "test_user"
    assert settings["password"] == "test_password"


def test_ensure_output_dir_creates_path(isolated_config_env, tmp_path):
    isolated_config_env.setenv("OUTPUT_DIR", str(tmp_path / "business_reports"))
    Config.reload()
    path = Config.ensure_output_dir()
    assert path == (tmp_path / "business_reports").resolve()
    assert path.is_dir()
    assert Config.OUTPUT_DIR == path


def test_src_config_shim_reexports_canonical_config():
    from src.config import Config as ShimConfig
    from src.config import CustomerSegmentation as ShimSegments

    assert ShimConfig is Config
    assert ShimSegments is CustomerSegmentation


def test_ai_base_shim_reexports_canonical_config():
    pytest.importorskip("vanna")
    from business_analyzer.ai import base as ai_base
    from business_analyzer.ai.base import Config as AIConfig
    from business_analyzer.ai.base import _is_testing_env as ai_is_testing
    from business_analyzer.ai.base import require_env as ai_require_env

    assert "Config" in ai_base.__all__
    assert "_is_testing_env" in ai_base.__all__
    assert AIConfig is Config
    assert ai_require_env is require_env
    assert ai_is_testing is config_mod._is_testing_env
