"""Local .env values must not leak into the test process environment."""

from __future__ import annotations

import os

from tests.conftest import isolate_dotenv_from_test_environ


def test_isolate_dotenv_drops_keys_that_were_not_in_the_process(monkeypatch):
    leaked_key = "GROK_API_KEY"
    leaked_value = "xai-leaked-from-local-dotenv"
    monkeypatch.setenv(leaked_key, leaked_value)

    isolate_dotenv_from_test_environ()

    assert os.environ.get(leaked_key) != leaked_value
