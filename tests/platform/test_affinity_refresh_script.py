"""El wrapper nocturno no corre --apply si el env no carga (hallazgo 7 de la firma).

El script es văritabilizado (AFF_INBOX_ENV / AFF_REPO_DIR / AFF_PY /
AFF_ENV_FILE) para poder probarlo sin tocar el crontab real ni J3: la
llamada al job se reemplaza por un shim que sólo registra su invocación.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "run_cross_sell_affinity.sh"


def _run(tmp_path: Path, env: dict[str, str]) -> tuple[int, int]:
    """Corre el script con el job sustituido por un shim; devuelve (rc, llamadas)."""
    fake_repo = tmp_path / "repo"
    fake_repo.mkdir()
    fake_repo.joinpath("src").mkdir()
    shim_dir = tmp_path / "bin"
    shim_dir.mkdir()
    log = tmp_path / "job.log"
    shim = shim_dir / "shim"
    shim.write_text(
        "#!/usr/bin/env bash\n" f'echo called >> "{log}"\nexit 0\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    import os

    env = {**os.environ, **env}
    env["AFF_REPO_DIR"] = str(fake_repo)
    env["AFF_PY"] = str(shim)
    env["PATH"] = str(shim_dir) + ":" + os.environ.get("PATH", "")
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    calls = len(log.read_text().splitlines()) if log.exists() else 0
    return result.returncode, calls


def test_missing_env_file_never_runs_the_apply(tmp_path, monkeypatch) -> None:
    _probe()
    monkeypatch.setenv("AFF_ATTEMPTS", "1")
    monkeypatch.setenv("AFF_RETRY_SLEEP", "0")
    rc, calls = _run(
        tmp_path,
        env={"AFF_INBOX_ENV": str(tmp_path / "no_existe.env")},
    )
    assert rc == 1
    assert calls == 0  # el --apply jamás corre sin el env cargado


def _probe() -> None:  # pragma: no cover - documentación del riesgo
    """Con el código rojo, la carga falla y el job corre igual: `ADVISOR_DATABASE_URL` vacía
    en el job con --apply. El fix exige el éxito de la carga."""


def test_failing_env_file_never_runs_the_apply(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "bad.env"
    bad.write_text("exit 1\n", encoding="utf-8")
    monkeypatch.setenv("AFF_ATTEMPTS", "1")
    monkeypatch.setenv("AFF_RETRY_SLEEP", "0")
    rc, calls = _run(tmp_path, env={"AFF_INBOX_ENV": str(bad)})
    assert rc == 1
    assert calls == 0


def test_loaded_env_runs_apply_once(tmp_path, monkeypatch) -> None:
    good = tmp_path / "good.env"
    good.write_text("export DATABASE_URL=postgresql://test/neondb\n", encoding="utf-8")
    monkeypatch.setenv("AFF_ATTEMPTS", "1")
    monkeypatch.setenv("AFF_RETRY_SLEEP", "0")
    rc, calls = _run(tmp_path, env={"AFF_INBOX_ENV": str(good)})
    assert rc == 0
    assert calls == 1
