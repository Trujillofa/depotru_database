"""
Pytest Configuration and Shared Fixtures
=========================================
This file configures pytest for the Business Data Analyzer test suite.
"""

import pytest
import sys
from pathlib import Path


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
    config.addinivalue_line("markers", "integration: Integration tests requiring database")
    config.addinivalue_line("markers", "slow: Slow running tests")
    config.addinivalue_line("markers", "requires_db: Tests that require database connection")
    config.addinivalue_line("markers", "requires_api: Tests that require API keys")


# =============================================================================
# Skip Conditions
# =============================================================================

# Skip decorators for missing dependencies
requires_pymssql = pytest.mark.skipif(
    not HAS_PYMSSQL,
    reason="pymssql not installed (pip install pymssql)"
)

requires_vanna = pytest.mark.skipif(
    not HAS_VANNA,
    reason="vanna not installed (pip install vanna)"
)

requires_matplotlib = pytest.mark.skipif(
    not HAS_MATPLOTLIB,
    reason="matplotlib not installed (pip install matplotlib)"
)

requires_pandas = pytest.mark.skipif(
    not HAS_PANDAS,
    reason="pandas not installed (pip install pandas)"
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
            "Fecha": datetime(2025, 1, 15)
        },
        {
            "TotalMasIva": 232.0,
            "TotalSinIva": 200.0,
            "ValorCosto": 120.0,
            "Cantidad": 4,
            "TercerosNombres": "Customer A",
            "ArticulosNombre": "Product 2",
            "categoria": "Category 1",
            "Fecha": datetime(2025, 1, 16)
        },
        {
            "TotalMasIva": 174.0,
            "TotalSinIva": 150.0,
            "ValorCosto": 90.0,
            "Cantidad": 3,
            "TercerosNombres": "Customer B",
            "ArticulosNombre": "Product 1",
            "categoria": "Category 2",
            "Fecha": datetime(2025, 1, 17)
        }
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
