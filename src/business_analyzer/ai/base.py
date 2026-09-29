"""
Base module for AI package.

Compatibility facade: historical imports keep working. Implementation
lives in llm / sql_routing / sql_runtime / manager_report_routing /
summaries / vanna.
"""

from __future__ import annotations

from business_analyzer.core.config import (  # noqa: F401
    DEFAULT_PROVIDER,
    MAX_STACK_FRAME_DEPTH,
    SUPPORTED_PROVIDERS,
    Config,
    _is_testing_env,
    get_env_or_test_default,
    hydrate_ai_config,
    require_env,
    resolve_database_settings,
)

from .llm import create_ai_client, retry_on_failure
from .vanna import AIVanna

# Preserve historical import-time AI provider validation / key loading.
hydrate_ai_config()

__all__ = [
    "AIVanna",
    "Config",
    "DEFAULT_PROVIDER",
    "MAX_STACK_FRAME_DEPTH",
    "SUPPORTED_PROVIDERS",
    "create_ai_client",
    "get_env_or_test_default",
    "hydrate_ai_config",
    "require_env",
    "resolve_database_settings",
    "retry_on_failure",
    "_is_testing_env",
]
