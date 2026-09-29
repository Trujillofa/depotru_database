"""CI-safe tests for ops website-stock allowlist sync (no J3 / SSH)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = ROOT / "scripts" / "ops" / "run_website_stock_allowlist_sync.py"


def _load_ops():
    name = "run_website_stock_allowlist_sync"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.unit
def test_dry_run_skips_j3_payload_and_ssh(tmp_path):
    ops = _load_ops()
    log_file = tmp_path / "sync.jsonl"
    with patch.object(ops, "build_excluded_payload") as build, patch.object(
        ops, "apply_payload_via_ssh"
    ) as apply_ssh, patch.object(ops.MagentoSshConfig, "from_env") as from_env:
        rc = ops.main(["--dry-run", "--log-file", str(log_file)])

    assert rc == 0
    build.assert_not_called()
    apply_ssh.assert_not_called()
    from_env.assert_not_called()
    row = json.loads(log_file.read_text(encoding="utf-8").splitlines()[-1])
    assert row["mode"] == "dry-run"
    assert row["ssh"] is False
    assert row["updated_skus"] == 0
    assert row["errors"] == []
    assert "skipped J3" in row["note"]
    assert "no SSH" in row["note"]


@pytest.mark.unit
def test_apply_builds_payload_and_calls_ssh(tmp_path):
    ops = _load_ops()
    log_file = tmp_path / "sync.jsonl"
    payload = [{"sku": "SKU-1", "website_qty": 2, "excluded_qty": 1}]
    cfg = MagicMock()
    apply_result = {
        "mode": "apply",
        "updated_skus": 1,
        "updated_items": 1,
        "errors": [],
    }
    with patch.object(
        ops, "build_excluded_payload", return_value=payload
    ) as build, patch.object(
        ops, "apply_payload_via_ssh", return_value=apply_result
    ) as apply_ssh, patch.object(
        ops.MagentoSshConfig, "from_env", return_value=cfg
    ):
        rc = ops.main(
            [
                "--log-file",
                str(log_file),
                "--top-n",
                "10",
                "--min-excluded",
                "0.5",
                "--batch-size",
                "20",
                "--no-reindex",
            ]
        )

    assert rc == 0
    build.assert_called_once_with(top_n=10, min_excluded=0.5)
    apply_ssh.assert_called_once_with(
        payload,
        cfg=cfg,
        dry_run=False,
        batch_size=20,
        reindex=False,
    )
    row = json.loads(log_file.read_text(encoding="utf-8").splitlines()[-1])
    assert row["mode"] == "apply"
    assert row["payload_skus"] == 1
    assert row["updated_skus"] == 1


@pytest.mark.unit
def test_apply_without_ssh_config_exits_before_payload(tmp_path):
    ops = _load_ops()
    with patch.object(ops, "build_excluded_payload") as build, patch.object(
        ops, "apply_payload_via_ssh"
    ) as apply_ssh, patch.object(ops.MagentoSshConfig, "from_env", return_value=None):
        rc = ops.main(["--log-file", str(tmp_path / "unused.jsonl")])

    assert rc == 2
    build.assert_not_called()
    apply_ssh.assert_not_called()
