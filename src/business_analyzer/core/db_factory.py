"""Shared database factory for API, MCP, and report entry points."""

from __future__ import annotations

import threading
from typing import Dict, Optional

from business_analyzer.core.database import ConnectionType, Database

try:
    from config import Config
except ImportError:
    import sys
    from pathlib import Path

    src_path = Path(__file__).parent.parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from config import Config

_thread_local = threading.local()


def _thread_cache() -> Dict[str, Database]:
    cache = getattr(_thread_local, "databases", None)
    if cache is None:
        cache = {}
        _thread_local.databases = cache
    return cache


def _cache_key(target_db: Optional[str] = None) -> str:
    return target_db or Config.DB_NAME


def get_database(
    target_db: Optional[str] = None,
    *,
    reuse: bool = True,
    connection_type: ConnectionType = ConnectionType.DIRECT,
    conn_details: Optional[dict] = None,
    ncx_file_path: Optional[str] = None,
) -> Database:
    """Return a connected Database, optionally reusing a per-thread instance."""
    key = _cache_key(target_db)
    if reuse:
        cached = _thread_cache().get(key)
        if cached is not None:
            if cached.is_connected() and cached.ping():
                return cached
            try:
                cached.close()
            except Exception:
                pass
            _thread_cache().pop(key, None)

    resolved_details = conn_details
    if target_db:
        probe = Database(
            connection_type=connection_type,
            conn_details=conn_details,
            ncx_file_path=ncx_file_path,
        )
        base = probe._get_connection_details()
        base["Database"] = target_db
        resolved_details = base

    db = Database(
        connection_type=connection_type,
        conn_details=resolved_details,
        ncx_file_path=ncx_file_path,
    )
    db.connect()
    if reuse:
        _thread_cache()[key] = db
    return db


def release_thread_connections() -> None:
    """Close all Database instances cached on the current thread."""
    cache = getattr(_thread_local, "databases", None)
    if not cache:
        return
    for db in cache.values():
        try:
            db.close()
        except Exception:
            pass
    cache.clear()
