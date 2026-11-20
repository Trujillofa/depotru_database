"""El wrapper nocturno no corre --apply si el env no carga (hallazgo 7 de la firma).

El script es văritabilizado (AFF_INBOX_ENV / AFF_REPO_DIR / AFF_PY /
AFF_ENV_FILE) para poder probarlo sin tocar el crontab real ni J3: la
llamada al job se reemplaza por un shim que sólo registra su invocación.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "run_cross_sell_affinity.sh"


def _run(
    tmp_path: Path, env: dict[str, str], shim_path: Path | None = None
) -> tuple[int, int]:
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

    j3 = tmp_path / "j3.env"
    j3.write_text("DB_HOST=j3.test\n", encoding="utf-8")
    env = {**os.environ, "AFF_J3_ENV": str(j3), **env}
    env["AFF_REPO_DIR"] = str(fake_repo)
    env["AFF_PY"] = str(shim_path or shim)
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


# 5-18 nov 2026: sin las credenciales J3 el job fallaba cada noche con
# j3_unavailable. Ahora el wrapper exige el env J3 antes de correr.
@pytest.mark.parametrize("j3_content", [None, "OTRA=1\n"])
def test_missing_j3_env_never_runs_the_apply(tmp_path, monkeypatch, j3_content) -> None:
    good = tmp_path / "good.env"
    good.write_text("export DATABASE_URL=postgresql://test/neondb\n", encoding="utf-8")
    j3 = tmp_path / "j3_override.env"
    if j3_content is not None:
        j3.write_text(j3_content, encoding="utf-8")
    monkeypatch.setenv("AFF_ATTEMPTS", "1")
    monkeypatch.setenv("AFF_RETRY_SLEEP", "0")
    monkeypatch.delenv("DB_HOST", raising=False)
    rc, calls = _run(
        tmp_path,
        env={"AFF_INBOX_ENV": str(good), "AFF_J3_ENV": str(j3)},
    )
    assert rc == 1
    assert calls == 0


def test_inherited_db_host_does_not_satisfy_the_j3_guard(tmp_path, monkeypatch) -> None:
    """Revisión adversarial: un DB_HOST heredado del entorno del cron no
    puede pasar por las credenciales J3 que el archivo no trae."""
    good = tmp_path / "good.env"
    good.write_text("export DATABASE_URL=postgresql://test/neondb\n", encoding="utf-8")
    j3 = tmp_path / "sin_host.env"
    j3.write_text("DB_USER=x\n", encoding="utf-8")
    monkeypatch.setenv("AFF_ATTEMPTS", "1")
    monkeypatch.setenv("AFF_RETRY_SLEEP", "0")
    monkeypatch.setenv("DB_HOST", "heredado.example")
    rc, calls = _run(
        tmp_path,
        env={"AFF_INBOX_ENV": str(good), "AFF_J3_ENV": str(j3)},
    )
    assert rc == 1
    assert calls == 0


def test_j3_env_wins_over_db_vars_in_the_inbox_env(tmp_path, monkeypatch) -> None:
    good = tmp_path / "good.env"
    good.write_text(
        "export DATABASE_URL=postgresql://test/neondb\nDB_HOST=del-inbox\n",
        encoding="utf-8",
    )
    j3 = tmp_path / "j3_ok.env"
    j3.write_text("DB_HOST=j3.real\n", encoding="utf-8")
    seen = tmp_path / "seen"
    monkeypatch.setenv("AFF_ATTEMPTS", "1")
    monkeypatch.setenv("AFF_RETRY_SLEEP", "0")
    monkeypatch.delenv("DB_HOST", raising=False)
    shim = tmp_path / "shim_host"
    shim.write_text(
        f'#!/usr/bin/env bash\necho "$DB_HOST" > "{seen}"\n', encoding="utf-8"
    )
    shim.chmod(0o755)
    rc, _ = _run(
        tmp_path,
        env={"AFF_INBOX_ENV": str(good), "AFF_J3_ENV": str(j3)},
        shim_path=shim,
    )
    assert rc == 0
    assert seen.read_text().strip() == "j3.real"


def test_wrapper_passes_additive_category_snapshot_path(tmp_path, monkeypatch):
    good = tmp_path / "good.env"
    good.write_text("DATABASE_URL=postgresql://test/neondb\n", encoding="utf-8")
    seen = tmp_path / "args"
    shim = tmp_path / "shim_args"
    shim.write_text(
        f'#!/usr/bin/env bash\nprintf "%s\\n" "$@" > "{seen}"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    monkeypatch.setenv("AFF_ATTEMPTS", "1")
    path = str(tmp_path / "category snapshot.json")
    rc, _ = _run(
        tmp_path,
        env={"AFF_INBOX_ENV": str(good), "CATALOG_CATEGORY_SNAPSHOT": path},
        shim_path=shim,
    )
    assert rc == 0
    args = seen.read_text().splitlines()
    assert args[args.index("--category-snapshot") + 1] == path
    assert "--apply" in args
