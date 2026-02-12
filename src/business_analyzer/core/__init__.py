"""
Business Analyzer Core Module
=============================
Core functionality for database connections and business logic.
"""

from .database import ConnectionType, Database, DatabaseError

__all__ = ["Database", "DatabaseError", "ConnectionType"]
