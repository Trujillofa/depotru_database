"""Exercise the real shell wrapper and Python entrypoints, with no DB access."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "deploy/run_cross_sell_affinity.sh"


@pytest.mark.parametrize("snapshot_fails", [True, False])
def test_snapshot_exception_cannot_fail_successful_affinity(tmp_path, snapshot_fails):
    inbox = tmp_path / "inbox.env"
    inbox.write_text("DATABASE_URL=postgresql://fixture/test\n")
    j3 = tmp_path / "j3.env"
    j3.write_text("DB_HOST=fixture.invalid\n")
    destination = tmp_path / "category snapshot.json"
    destination.write_text("previous")
    calls = tmp_path / "calls"
    shim = tmp_path / "python-shim"
    shim.write_text(
        f"#!{sys.executable}\n"
        "import sys\n"
        "from unittest.mock import MagicMock\n"
        "from business_analyzer.jobs import cross_sell_affinity as affinity\n"
        "from business_analyzer.jobs import category_snapshot as category\n"
        f"with open({str(calls)!r}, 'a') as log:\n"
        "    log.write(sys.argv[2] + '\\n')\n"
        "store = MagicMock()\n"
        "store.count.return_value = 0\n"
        "store.replace_all.return_value = 0\n"
        "affinity._resolve_store = lambda **kw: store\n"
        "affinity.compute_records = lambda **kw: []\n"
        "def compute(**kw):\n"
        f"    if {snapshot_fails!r}:\n"
        "        raise TimeoutError('fixture_snapshot_timeout')\n"
        "    return {}\n"
        "category.compute_category_snapshot = compute\n"
        "module = affinity if sys.argv[2].endswith('cross_sell_affinity') else category\n"
        "raise SystemExit(module.main(sys.argv[3:]))\n"
    )
    shim.chmod(0o755)
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env={
            **os.environ,
            "AFF_REPO_DIR": str(SCRIPT.parents[1]),
            "AFF_INBOX_ENV": str(inbox),
            "AFF_J3_ENV": str(j3),
            "AFF_ENV_FILE": str(inbox),
            "AFF_PY": str(shim),
            "AFF_ATTEMPTS": "3",
            "AFF_RETRY_SLEEP": "0",
            "CATALOG_CATEGORY_SNAPSHOT": str(destination),
        },
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert " ok (intento 1/3)" in result.stdout
    marker = "category_snapshot fail" if snapshot_fails else "category_snapshot ok"
    assert marker in result.stdout
    assert result.stdout.index(" ok (intento") < result.stdout.index(marker)
    assert calls.read_text().splitlines() == [
        "business_analyzer.jobs.cross_sell_affinity",
        "business_analyzer.jobs.category_snapshot",
    ]
    assert "intento 2/" not in result.stdout
    if snapshot_fails:
        assert "TimeoutError" in result.stderr
        assert destination.read_text() == "previous"
    else:
        assert '"products": {}' in destination.read_text()
