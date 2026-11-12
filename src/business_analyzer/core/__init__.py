"""
Business Analyzer Core Module
=============================
Core functionality for database connections and business logic.
"""

from . import paths

__all__ = ["Database", "DatabaseError", "ConnectionType", "paths"]


def __getattr__(name):
    # Lazy import: ``config`` imports ``business_analyzer.core.paths`` while
    # loading, and eagerly importing ``database`` here would circle back to a
    # partially initialized ``config`` module.
    if name in ("Database", "DatabaseError", "ConnectionType"):
        from . import database

        return getattr(database, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
