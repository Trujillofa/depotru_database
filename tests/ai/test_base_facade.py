"""Compat facade for the Phase 2b ai/base.py split.

Proves old import paths resolve to the same objects as the new modules
and that the new modules do not import each other in a cycle.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest

pytest.importorskip("vanna")

from business_analyzer.core import config as config_mod
from business_analyzer.core.config import Config, hydrate_ai_config, require_env

AI_DIR = Path(__file__).resolve().parents[2] / "src" / "business_analyzer" / "ai"

SPLIT_MODULES = (
    "business_analyzer.ai.llm",
    "business_analyzer.ai.sql_routing",
    "business_analyzer.ai.sql_runtime",
    "business_analyzer.ai.manager_report_routing",
    "business_analyzer.ai.summaries",
    "business_analyzer.ai.vanna",
    "business_analyzer.ai.base",
)

FACADE_EXPORTS = (
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
)


def test_split_modules_are_importable():
    for name in SPLIT_MODULES:
        module = importlib.import_module(name)
        assert module is not None


def test_facade_reexports_are_identical_objects():
    from business_analyzer.ai import base as facade
    from business_analyzer.ai import llm, sql_runtime, summaries, vanna
    from business_analyzer.ai.base import (
        DEFAULT_PROVIDER,
        MAX_STACK_FRAME_DEPTH,
        SUPPORTED_PROVIDERS,
        AIVanna,
    )
    from business_analyzer.ai.base import Config as AIConfig
    from business_analyzer.ai.base import (
        _is_testing_env,
        create_ai_client,
        get_env_or_test_default,
    )
    from business_analyzer.ai.base import hydrate_ai_config as hydrate_from_base
    from business_analyzer.ai.base import require_env as require_from_base
    from business_analyzer.ai.base import resolve_database_settings, retry_on_failure

    assert facade.AIVanna is vanna.AIVanna is AIVanna
    assert facade.create_ai_client is llm.create_ai_client is create_ai_client
    assert facade.retry_on_failure is llm.retry_on_failure is retry_on_failure
    assert facade.Config is Config is AIConfig
    assert facade.require_env is require_env is require_from_base
    assert facade.hydrate_ai_config is hydrate_ai_config is hydrate_from_base
    assert facade._is_testing_env is config_mod._is_testing_env is _is_testing_env
    assert facade.get_env_or_test_default is config_mod.get_env_or_test_default
    assert facade.get_env_or_test_default is get_env_or_test_default
    assert facade.resolve_database_settings is config_mod.resolve_database_settings
    assert facade.resolve_database_settings is resolve_database_settings
    assert facade.DEFAULT_PROVIDER is config_mod.DEFAULT_PROVIDER is DEFAULT_PROVIDER
    assert facade.SUPPORTED_PROVIDERS is config_mod.SUPPORTED_PROVIDERS
    assert facade.SUPPORTED_PROVIDERS is SUPPORTED_PROVIDERS
    assert facade.MAX_STACK_FRAME_DEPTH is config_mod.MAX_STACK_FRAME_DEPTH
    assert facade.MAX_STACK_FRAME_DEPTH is MAX_STACK_FRAME_DEPTH
    assert AIVanna.generate_sql is vanna.AIVanna.generate_sql
    assert AIVanna.generate_sql is sql_runtime.SqlRuntimeMixin.generate_sql
    assert AIVanna.generate_summary is summaries.SummaryMixin.generate_summary


def test_facade_all_lists_historical_public_names():
    from business_analyzer.ai import base as facade

    for name in FACADE_EXPORTS:
        assert name in facade.__all__
        assert hasattr(facade, name)


def test_vanna_grok_reexports_retry_and_require_env():
    from business_analyzer.ai.base import require_env as base_require
    from business_analyzer.ai.base import retry_on_failure as base_retry
    from src.vanna_grok import require_env as vg_require
    from src.vanna_grok import retry_on_failure as vg_retry

    assert vg_require is base_require is require_env
    assert vg_retry is base_retry


def test_base_still_calls_hydrate_ai_config_on_import():
    source = inspect.getsource(importlib.import_module("business_analyzer.ai.base"))
    assert "hydrate_ai_config()" in source


def test_create_ai_client_patch_target_remains_on_base():
    from business_analyzer.ai import base as facade
    from business_analyzer.ai import llm

    assert facade.create_ai_client is llm.create_ai_client
    assert "create_ai_client" in facade.__all__


_SPLIT_NAMES = {
    "llm",
    "sql_routing",
    "sql_runtime",
    "manager_report_routing",
    "summaries",
    "vanna",
    "base",
}


def _imported_split_name(module_name: str | None) -> str | None:
    if not module_name:
        return None
    if module_name in _SPLIT_NAMES:
        return module_name
    if module_name.startswith("business_analyzer.ai."):
        tail = module_name.split(".")[-1]
        if tail in _SPLIT_NAMES:
            return tail
    return None


def _relative_ai_imports(path: Path):
    """Module-level imports only — function-body imports are not cycles."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            name = _imported_split_name(node.module)
            if name:
                imported.add(name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                name = _imported_split_name(alias.name)
                if name:
                    imported.add(name)
    return imported


def test_split_modules_have_no_import_cycles():
    graph = {
        "llm": _relative_ai_imports(AI_DIR / "llm.py"),
        "sql_routing": _relative_ai_imports(AI_DIR / "sql_routing.py"),
        "sql_runtime": _relative_ai_imports(AI_DIR / "sql_runtime.py"),
        "manager_report_routing": _relative_ai_imports(
            AI_DIR / "manager_report_routing.py"
        ),
        "summaries": _relative_ai_imports(AI_DIR / "summaries.py"),
        "vanna": _relative_ai_imports(AI_DIR / "vanna.py"),
        "base": _relative_ai_imports(AI_DIR / "base.py"),
    }

    visiting = set()
    seen = set()

    def visit(node: str) -> None:
        if node in seen:
            return
        if node in visiting:
            raise AssertionError("import cycle involving %s: %s" % (node, graph))
        visiting.add(node)
        for nxt in sorted(graph.get(node, ())):
            if nxt in graph:
                visit(nxt)
        visiting.remove(node)
        seen.add(node)

    for name in graph:
        visit(name)

    # Facade may import leaves; leaves must not import the facade or each other
    # in a way that forms a cycle. Explicitly forbid sibling cycles.
    assert "base" not in graph["llm"]
    assert "base" not in graph["sql_routing"]
    assert "base" not in graph["sql_runtime"]
    assert "base" not in graph["manager_report_routing"]
    assert "base" not in graph["summaries"]
    assert "vanna" not in graph["sql_routing"]
    assert "vanna" not in graph["llm"]
