import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_vanna_public_surface_imports_all_entrypoints():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from src.vanna_chat import "
                "create_vanna_instance, connect_to_database, "
                "train_vanna_on_schema, main; "
                "assert callable(create_vanna_instance); "
                "assert callable(connect_to_database); "
                "assert callable(train_vanna_on_schema); "
                "assert callable(main); "
                "print('ok')"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("ok")


def test_vanna_grok_direct_launch_imports_external_vanna_package():
    env = os.environ.copy()
    env["TESTING"] = "true"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "sys.path.insert(0, 'src'); "
                "import vanna_grok; "
                "import vanna.legacy.flask; "
                "print('ok')"
            ),
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("ok")
