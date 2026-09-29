"""Local .env values must not leak into the test process environment."""

from __future__ import annotations

import importlib
import os
import sys

from tests.conftest import isolate_dotenv_from_test_environ


def test_isolate_dotenv_drops_keys_that_were_not_in_the_process(monkeypatch):
    leaked_key = "GROK_API_KEY"
    leaked_value = "xai-leaked-from-local-dotenv"
    monkeypatch.setenv(leaked_key, leaked_value)

    isolate_dotenv_from_test_environ()

    assert os.environ.get(leaked_key) != leaked_value


def test_load_dotenv_after_configure_does_not_stick(tmp_path):
    """Direct load_dotenv (what a late src.* import runs) must not leak."""
    leaked = "xai-leaked-from-load-dotenv"
    env_file = tmp_path / ".env"
    env_file.write_text(f"GROK_API_KEY={leaked}\n", encoding="utf-8")
    isolate_dotenv_from_test_environ()

    from dotenv import load_dotenv

    load_dotenv(env_file)
    assert os.environ.get("GROK_API_KEY") != leaked


def test_late_src_config_import_does_not_releak_dotenv(tmp_path, monkeypatch):
    """A fresh ``src.*`` import re-runs load_dotenv after pytest_configure."""
    leaked = "xai-leaked-from-late-src-import"
    env_file = tmp_path / ".env"
    env_file.write_text(f"GROK_API_KEY={leaked}\n", encoding="utf-8")

    import dotenv

    monkeypatch.setattr(dotenv, "find_dotenv", lambda *args, **kwargs: str(env_file))
    monkeypatch.setattr(
        dotenv.main, "find_dotenv", lambda *args, **kwargs: str(env_file)
    )
    isolate_dotenv_from_test_environ()

    for name in list(sys.modules):
        if name == "src.business_analyzer.core.config":
            del sys.modules[name]

    importlib.import_module("src.business_analyzer.core.config")

    assert os.environ.get("GROK_API_KEY") != leaked
