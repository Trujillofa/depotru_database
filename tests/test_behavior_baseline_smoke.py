import ast
import runpy
import subprocess
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_analyzer_cli_help_surface():
    result = subprocess.run(
        [sys.executable, "-m", "src.business_analyzer_combined", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
    assert "--start-date" in result.stdout
    assert "--end-date" in result.stdout


def test_vanna_public_import_surface():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from src.vanna_chat import create_vanna_instance, connect_to_database; "
                "assert callable(create_vanna_instance); "
                "assert callable(connect_to_database); "
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


def test_pandas_example_smoke_with_stubbed_optional_deps(monkeypatch, capsys):
    pandas_module = types.ModuleType("pandas")

    class DataFrame:
        pass

    class ExcelWriter:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    pandas_module.DataFrame = DataFrame
    pandas_module.ExcelWriter = ExcelWriter
    pandas_module.read_sql = lambda *_args, **_kwargs: DataFrame()
    pandas_module.to_datetime = lambda value: value
    pandas_module.to_numeric = lambda value, errors=None: value

    numpy_module = types.ModuleType("numpy")
    numpy_module.inf = float("inf")

    sqlalchemy_module = types.ModuleType("sqlalchemy")
    sqlalchemy_module.create_engine = lambda *_args, **_kwargs: object()

    plotly_module = types.ModuleType("plotly")
    plotly_express_module = types.ModuleType("plotly.express")
    plotly_graph_objects_module = types.ModuleType("plotly.graph_objects")

    class Figure:
        pass

    plotly_graph_objects_module.Figure = Figure

    plotly_subplots_module = types.ModuleType("plotly.subplots")
    plotly_subplots_module.make_subplots = lambda *_args, **_kwargs: Figure()

    monkeypatch.setitem(sys.modules, "pandas", pandas_module)
    monkeypatch.setitem(sys.modules, "numpy", numpy_module)
    monkeypatch.setitem(sys.modules, "sqlalchemy", sqlalchemy_module)
    monkeypatch.setitem(sys.modules, "plotly", plotly_module)
    monkeypatch.setitem(sys.modules, "plotly.express", plotly_express_module)
    monkeypatch.setitem(
        sys.modules, "plotly.graph_objects", plotly_graph_objects_module
    )
    monkeypatch.setitem(sys.modules, "plotly.subplots", plotly_subplots_module)

    runpy.run_path(str(ROOT / "examples" / "pandas_approach.py"), run_name="__main__")

    captured = capsys.readouterr()
    assert "Pandas-Based Business Analyzer Demo" in captured.out
    assert "Reduction: 87%" in captured.out


def test_streamlit_example_path_contract_without_import_runtime():
    streamlit_path = ROOT / "examples" / "streamlit_dashboard.py"
    source = streamlit_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    function_names = {
        node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
    }

    assert streamlit_path.exists()
    assert "load_data" in function_names
    assert "calculate_metrics" in function_names
    assert "st.set_page_config" in source
    assert "st.cache_data" in source
