"""
Pytest Configuration and Shared Fixtures
=========================================
This file configures pytest for the Business Data Analyzer test suite.
"""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

# =============================================================================
# Path Setup
# =============================================================================

# Add src to path for imports
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# Mock external dependencies before any imports from business_analyzer
sys.modules["pymssql"] = Mock()
sys.modules["pyodbc"] = Mock()
sys.modules["NavicatCipher"] = Mock()
sys.modules["Crypto"] = Mock()
sys.modules["Crypto.Cipher"] = Mock()
sys.modules["Crypto.Util"] = Mock()
sys.modules["Crypto.Util.Padding"] = Mock()

# Create mock config module
mock_config = Mock()
mock_config.Config = Mock()
mock_config.Config.DB_HOST = "test-host"
mock_config.Config.DB_PORT = 1433
mock_config.Config.DB_USER = "test-user"
mock_config.Config.DB_PASSWORD = "test-password"
mock_config.Config.DB_NAME = "TestDB"
mock_config.Config.DB_TABLE = "test_table"
mock_config.Config.NCX_FILE_PATH = "/test/connections.ncx"
mock_config.Config.DB_LOGIN_TIMEOUT = 10
mock_config.Config.DB_TIMEOUT = 10
mock_config.Config.DB_TDS_VERSION = "7.4"
mock_config.Config.DEFAULT_LIMIT = 1000
mock_config.Config.EXCLUDED_DOCUMENT_CODES = ["XY", "AS"]
mock_config.Config.has_direct_db_config = Mock(return_value=True)
mock_config.Config.ensure_output_dir = Mock(return_value=Path("/tmp"))

# Insert the mock config into sys.modules BEFORE importing business_analyzer
sys.modules["config"] = mock_config

# =============================================================================
# Dependency Checks
# =============================================================================


def check_dependency(module_name):
    """Check if a module is available for import."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


# Check for optional dependencies
HAS_PYMSSQL = check_dependency("pymssql")
HAS_VANNA = check_dependency("vanna")
HAS_MATPLOTLIB = check_dependency("matplotlib")
HAS_PANDAS = check_dependency("pandas")


# =============================================================================
# Pytest Markers
# =============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line(
        "markers", "integration: Integration tests requiring database"
    )
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line(
        "markers", "requires_db: Tests that require database connection"
    )
    config.addinivalue_line("markers", "requires_api: Tests that require API keys")


# =============================================================================
# Skip Conditions
# =============================================================================

# Skip decorators for missing dependencies
requires_pymssql = pytest.mark.skipif(
    not HAS_PYMSSQL, reason="pymssql not installed (pip install pymssql)"
)

requires_vanna = pytest.mark.skipif(
    not HAS_VANNA, reason="vanna not installed (pip install vanna)"
)

requires_matplotlib = pytest.mark.skipif(
    not HAS_MATPLOTLIB, reason="matplotlib not installed (pip install matplotlib)"
)

requires_pandas = pytest.mark.skipif(
    not HAS_PANDAS, reason="pandas not installed (pip install pandas)"
)


# =============================================================================
# Shared Fixtures
# =============================================================================


@pytest.fixture
def sample_transaction_data():
    """Sample transaction data for testing."""
    from datetime import datetime

    return [
        {
            "TotalMasIva": 116.0,
            "TotalSinIva": 100.0,
            "ValorCosto": 60.0,
            "Cantidad": 2,
            "TercerosNombres": "Customer A",
            "ArticulosNombre": "Product 1",
            "categoria": "Category 1",
            "Fecha": datetime(2025, 1, 15),
        },
        {
            "TotalMasIva": 232.0,
            "TotalSinIva": 200.0,
            "ValorCosto": 120.0,
            "Cantidad": 4,
            "TercerosNombres": "Customer A",
            "ArticulosNombre": "Product 2",
            "categoria": "Category 1",
            "Fecha": datetime(2025, 1, 16),
        },
        {
            "TotalMasIva": 174.0,
            "TotalSinIva": 150.0,
            "ValorCosto": 90.0,
            "Cantidad": 3,
            "TercerosNombres": "Customer B",
            "ArticulosNombre": "Product 1",
            "categoria": "Category 2",
            "Fecha": datetime(2025, 1, 17),
        },
    ]


@pytest.fixture
def empty_data():
    """Empty dataset for edge case testing."""
    return []


# =============================================================================
# Session Hooks
# =============================================================================


def pytest_report_header(config):
    """Add custom header to test report."""
    return [
        "Business Data Analyzer Test Suite",
        f"Python: {sys.version}",
        f"pymssql: {'✓' if HAS_PYMSSQL else '✗'}",
        f"pandas: {'✓' if HAS_PANDAS else '✗'}",
        f"matplotlib: {'✓' if HAS_MATPLOTLIB else '✗'}",
        f"vanna: {'✓' if HAS_VANNA else '✗'}",
    ]
