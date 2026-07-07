"""Integration tests need real pymssql/config (not root conftest mocks).

Run:
    pytest tests/integration/ -m requires_db --noconftest -v
"""

from __future__ import annotations

import sys
from unittest.mock import Mock

import pytest


@pytest.fixture(scope="session", autouse=True)
def _skip_when_db_modules_mocked():
    if isinstance(sys.modules.get("pymssql"), Mock):
        pytest.skip(
            "Integration tests require real DB drivers. "
            "Run: pytest tests/integration/ -m requires_db --noconftest -v"
        )
    if isinstance(sys.modules.get("config"), Mock):
        pytest.skip(
            "Integration tests require real config. "
            "Run: pytest tests/integration/ -m requires_db --noconftest -v"
        )
