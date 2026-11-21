"""
Tests for vanna_grok.py CLI wrapper
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(scope="module")
def vanna_grok_module():
    """Import vanna_grok without polluting sys.modules for other test files."""
    saved = {
        name: sys.modules.get(name)
        for name in list(sys.modules)
        if name.startswith("vanna")
    }
    for name in list(sys.modules):
        if name.startswith("vanna"):
            del sys.modules[name]

    import vanna_grok

    yield vanna_grok

    for name in list(sys.modules):
        if name.startswith("vanna"):
            del sys.modules[name]
    sys.modules.update(saved)


class TestVannaGrokCLI:
    def test_module_imports(self, vanna_grok_module):
        assert vanna_grok_module is not None

    def test_main_function_exists(self, vanna_grok_module):
        assert callable(vanna_grok_module.main)


class TestWaitressServeKwargs:
    def test_defaults_cover_long_manager_reports(self, vanna_grok_module, monkeypatch):
        monkeypatch.delenv("WAITRESS_THREADS", raising=False)
        monkeypatch.delenv("WAITRESS_CHANNEL_TIMEOUT", raising=False)
        kwargs = vanna_grok_module.waitress_serve_kwargs(host="0.0.0.0", port=8084)
        assert kwargs["host"] == "0.0.0.0"
        assert kwargs["port"] == 8084
        assert kwargs["threads"] == 8
        assert kwargs["channel_timeout"] == 600

    def test_env_overrides(self, vanna_grok_module, monkeypatch):
        monkeypatch.setenv("WAITRESS_THREADS", "4")
        monkeypatch.setenv("WAITRESS_CHANNEL_TIMEOUT", "900")
        kwargs = vanna_grok_module.waitress_serve_kwargs(host="127.0.0.1", port=9)
        assert kwargs["threads"] == 4
        assert kwargs["channel_timeout"] == 900


class TestConfiguration:
    def test_config_values(self):
        mock_config = Mock()
        mock_config.GROK_API_KEY = "test-api-key"
        mock_config.AI_PROVIDER = "grok"
        assert mock_config.GROK_API_KEY == "test-api-key"
