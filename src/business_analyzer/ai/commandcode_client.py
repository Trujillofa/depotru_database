"""OpenAI-compatible shim that answers through the local Command Code CLI.

Vanna expects ``client.chat.completions.create(...)`` returning an object with
``choices[0].message.content``. This adapter keeps the subscription-based
Command Code backend usable from the legacy OpenAI chat wrapper.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content
        self.role = "assistant"


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Message(content)
        self.finish_reason = "stop"

    def __contains__(self, key: str) -> bool:
        return False


class _Response:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]
        self.usage = None


class _Completions:
    def __init__(self, owner: "CommandCodeClient") -> None:
        self._owner = owner

    def create(self, **kwargs: Any) -> _Response:
        messages = kwargs.get("messages") or []
        prompt = self._owner.flatten_messages(messages)
        model = kwargs.get("model") or self._owner.model
        return _Response(self._owner.complete(prompt, model=model))


class _Chat:
    def __init__(self, owner: "CommandCodeClient") -> None:
        self.completions = _Completions(owner)


class CommandCodeClient:
    """Minimal OpenAI client surface backed by ``commandcode -p``."""

    def __init__(
        self,
        *,
        model: Optional[str] = None,
        binary: Optional[str] = None,
        timeout: Optional[int] = None,
        max_turns: int = 3,
    ) -> None:
        self.model = model or os.getenv(
            "COMMANDCODE_MODEL", "deepseek/deepseek-v4.1-flash"
        )
        self.binary = (
            binary or os.getenv("COMMANDCODE_BIN") or shutil.which("commandcode")
        )
        self.timeout = timeout or int(os.getenv("COMMANDCODE_TIMEOUT", "420"))
        self.max_turns = max_turns
        self.chat = _Chat(self)

    @staticmethod
    def flatten_messages(messages: Any) -> str:
        parts: List[str] = []
        for item in messages or []:
            if isinstance(item, dict):
                content = item.get("content")
                role = item.get("role", "user")
            else:
                content = getattr(item, "content", None)
                role = getattr(item, "role", "user")
            if content:
                parts.append(f"[{role}]\n{content}")
        return "\n\n".join(parts)

    def complete(self, prompt: str, *, model: Optional[str] = None) -> str:
        if not self.binary:
            raise RuntimeError(
                "commandcode CLI no está instalado (use COMMANDCODE_BIN)"
            )
        cmd = [
            self.binary,
            "-p",
            prompt,
            "--no-session",
            "--output-format",
            "text",
            "--max-turns",
            str(self.max_turns),
            "-m",
            model or self.model,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip()[-500:]
            raise RuntimeError(f"Command Code falló ({proc.returncode}): {detail}")
        text = proc.stdout.strip()
        if not text:
            raise RuntimeError("Command Code no devolvió texto")
        return text
