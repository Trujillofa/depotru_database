"""Backward-compatible re-export of the unified settings module."""

from business_analyzer.core.config import (  # noqa: F401
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
