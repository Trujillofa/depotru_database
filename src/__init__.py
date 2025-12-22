"""
Business Data Analyzer - Source Package
========================================
Main application source code for business intelligence and analytics.

Modules:
- business_analyzer_combined: Main business analyzer with comprehensive metrics
- vanna_chat: Natural language SQL interface using Vanna AI
- config: Configuration management and environment variables
- utils: Utility functions and helpers
"""

__version__ = "2.0.0"
__author__ = "Business Data Analyzer Team"

# Make key classes and functions available at package level
from .config import (
    Config,
    CustomerSegmentation,
    InventoryConfig,
    ProfitabilityConfig,
)

__all__ = [
    "Config",
    "CustomerSegmentation",
    "InventoryConfig",
    "ProfitabilityConfig",
]
