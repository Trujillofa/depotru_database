"""Tests for environment-backed path resolution."""

import os

from business_analyzer.core.paths import resolve_env_path, resolve_output_dir


def test_resolve_env_path_expands_tilde(monkeypatch, tmp_path):
    monkeypatch.delenv("OUTPUT_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    path = resolve_env_path("OUTPUT_DIR", "~/business_reports")
    assert path == (tmp_path / "business_reports").resolve()


def test_resolve_output_dir_honors_env_tilde(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OUTPUT_DIR", "~/business_reports")
    path = resolve_output_dir()
    assert path == (tmp_path / "business_reports").resolve()
    assert "~" not in str(path)


def test_resolve_env_path_resolves_relative_paths(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CUSTOM_DIR", raising=False)
    path = resolve_env_path("CUSTOM_DIR", "reports/output")
    assert path == (tmp_path / "reports" / "output").resolve()
