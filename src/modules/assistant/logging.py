"""Append-only JSONL logging for storefront assistant turns.

Never raises into the chat path. Path via ASSISTANT_CHAT_LOG or default
data/assistant/chat_log.jsonl under the project root.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def default_log_path() -> Path:
    env = (os.getenv("ASSISTANT_CHAT_LOG") or "").strip()
    if env:
        return Path(env).expanduser()
    # Prefer repo-relative data/ when CWD is project root; else /tmp fallback
    candidate = Path("data/assistant/chat_log.jsonl")
    return candidate


def log_assistant_turn(
    *,
    session_id: str,
    audience: str,
    locale: str,
    message: str,
    reply: str,
    tools_used: Optional[List[str]] = None,
    mode: str = "stub_tools",
    guide_id: Optional[str] = None,
    product_query: Optional[str] = None,
    grounded: bool = True,
    log_path: Optional[Path] = None,
) -> bool:
    """Append one JSON line. Returns True if written, False on skip/error."""
    try:
        path = Path(log_path) if log_path is not None else default_log_path()
        path = path.expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)

        msg = (message or "").strip()
        if len(msg) > 500:
            msg = msg[:500] + "…"
        preview = (reply or "").strip()
        if len(preview) > 200:
            preview = preview[:200] + "…"

        record: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "audience": audience,
            "locale": locale,
            "message": msg,
            "reply_preview": preview,
            "tools_used": list(tools_used or []),
            "mode": mode,
            "guide_id": guide_id,
            "product_query": product_query,
            "grounded": grounded,
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except Exception:  # noqa: BLE001 — logging must never break chat
        return False
