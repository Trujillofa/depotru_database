"""Regression coverage for the core package's lazy public exports."""

import os
import subprocess
import sys


def test_lazy_exports_and_config_import_cycle():
    # A fresh interpreter is necessary: other tests may already import database.
    script = """
import sys
import config
import business_analyzer.core as core
assert "business_analyzer.core.database" not in sys.modules
assert core.paths is not None
try:
    core.missing_export
except AttributeError:
    pass
else:
    raise AssertionError("unknown export must raise AttributeError")
from business_analyzer.core import Database, DatabaseError, ConnectionType
from business_analyzer.core import database
assert (Database, DatabaseError, ConnectionType) == (
    database.Database, database.DatabaseError, database.ConnectionType
)
namespace = {}
exec("from business_analyzer.core import *", namespace)
for name in core.__all__:
    assert namespace[name] is getattr(core, name)
"""
    env = {"PATH": os.defpath, "PYTHONPATH": "src", "TESTING": "true"}
    subprocess.run([sys.executable, "-c", script], env=env, check=True)
