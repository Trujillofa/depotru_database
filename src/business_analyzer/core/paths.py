"""Filesystem path helpers for environment-backed configuration."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_OUTPUT_DIR = "~/business_reports"


def resolve_env_path(
    env_name: str,
    default: str = DEFAULT_OUTPUT_DIR,
) -> Path:
    """
    Resolve a directory path from an environment variable.

    Expands ``~`` and ``$HOME``, then returns an absolute path. Relative paths
    without ``~`` are resolved against the current working directory.
    """
    raw = (os.getenv(env_name) or default).strip()
    if not raw:
        raw = default
    return Path(raw).expanduser().resolve()


def resolve_output_dir() -> Path:
    """Return the configured report output directory."""
    return resolve_env_path("OUTPUT_DIR", DEFAULT_OUTPUT_DIR)
