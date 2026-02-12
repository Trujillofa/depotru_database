"""
Business Analyzer Core Module
=============================
Core functionality for database connections and business logic.
"""

from .database import Database, DatabaseError, ConnectionType

__all__ = ["Database", "DatabaseError", "ConnectionType"]
