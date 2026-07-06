#!/usr/bin/env python3
# mypy: ignore-errors
"""
Verification script for chart heuristics (goal verification plan steps 1–4).

Usage:
  PYTHONPATH=src python scripts/verify_chart_heuristics.py

Writes all stdout/stderr to {SCRATCH}/charts_verify.log and
{SCRATCH}/charts_verify_final.log; client-profit evidence to
{SCRATCH}/client_profit_chart.log.
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path(
    os.environ.get("CHART_VERIFY_SCRATCH", "/tmp/grok-goal-0f5d0439d52b/implementer")
)
sys.path.insert(0, str(REPO_ROOT / "src"))

from business_analyzer.ai.charts import (  # noqa: E402
    build_plotly_code,
    build_smart_figure,
)

CLIENT_PROFIT_DF = pd.DataFrame(
    {
        "Cliente": [
            "ONG FUNDACION GESTION SOCIAL DE COLOMBIA",
            "FEDERACION NACIONAL DE CAFETEROS DE COLOMBIA",
            "FERRETERIA MAGRETH S A S",
        ],
        "Ganancia_Total": [794_510_097, 781_206_614, 728_105_320],
        "Facturacion": [7_680_276_777, 3_836_699_510, 13_044_407_165],
        "Margen_Promedio": [15.2, 29.2, 7.0],
    }
)

MONTHLY = pd.DataFrame(
    {
        "Nombre_Mes": ["Enero", "Febrero", "Marzo"],
        "Mes": [1, 2, 3],
        "Ventas_Totales": [200, 10_301_805, 67_201_662],
        "Ganancia": [88, 1_495_360, 10_024_608],
    }
)

CAT = pd.DataFrame(
    {
        "Categoria": ["Herramientas", "Pinturas"],
        "Ventas_Totales": [1_000_000, 2_000_000],
    }
)

IN_SCOPE_FILES = [
    "src/business_analyzer/ai/charts.py",
    "tests/ai/test_charts.py",
    "src/vanna_grok.py",
    "scripts/verify_chart_heuristics.py",
]


class _Tee(io.TextIOBase):
    def __init__(self, *streams: io.TextIOBase) -> None:
        self._streams = streams

    def write(self, data: str) -> int:
        for stream in self._streams:
            stream.write(data)
        return len(data)

    def flush(self) -> None:
        for stream in self._streams:
            stream.flush()


def _summarize_fig(fig) -> dict:
    if fig is None:
        return {"fig": None}
    data = fig.to_dict().get("data", [])
    layout = fig.to_dict().get("layout", {})
    return {
        "trace_count": len(data),
        "trace_types": [t.get("type") for t in data],
        "orientations": [t.get("orientation", "v") for t in data],
        "layout_title": fig.layout.title.text,
        "has_xaxis2": "xaxis2" in layout,
        "layout_repr": repr(fig.layout),
        "layout_dict": layout,
        "data_dict": data,
    }


def _write_scope_manifest() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = SCRATCH / "scope_manifest.txt"
    lines = [
        "IN_SCOPE (chart improvement goal):",
        *[f"  - {path}" for path in IN_SCOPE_FILES],
        "",
        "EXPLICIT_NON_GOALS (unchanged, not part of this goal):",
        "  - src/business_analyzer/reports/charts.py (Matplotlib manager reports)",
        "  - .crew/ .grok/ .omo/ mcp/ data/ html reports (pre-existing untracked)",
    ]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Wrote scope manifest:", manifest)


def step1_spot_checks() -> None:
    print("=== STEP 1: build_smart_figure / build_plotly_code spot checks ===")
    cases = [
        ("mixed_clients", CLIENT_PROFIT_DF, "Clientes más rentables por ganancia"),
        ("monthly_sika", MONTHLY, "Ventas del Sika Center este año"),
        ("category", CAT, "Ventas por categoría"),
    ]
    for name, df, question in cases:
        fig = build_smart_figure(df, question=question)
        code = build_plotly_code(df, question=question)
        print(f"\n--- {name} ---")
        print("summary:", json.dumps(_summarize_fig(fig), default=str))
        print("code_first_line:", (code or "None").split("\n")[0])
        if code:
            print("code_has_update_traces:", "update_traces" in code)
            print("code_has_melt:", "melt" in code)
            assert "melt" not in code

    mixed = build_smart_figure(
        CLIENT_PROFIT_DF, question="Clientes más rentables por ganancia"
    )
    assert mixed is not None
    assert len(mixed.data) == 1
    assert mixed.data[0].orientation == "h"
    print("mixed_assert: single horizontal trace PASSED")

    monthly = build_smart_figure(MONTHLY, question="Ventas del Sika Center este año")
    assert monthly is not None
    assert getattr(monthly.data[0], "orientation", "v") != "h"
    print("monthly_assert: vertical bar PASSED")

    print("\nSTEP 1: PASSED")


def step2_pytest() -> None:
    print("\n=== STEP 2: pytest tests/ai/test_charts.py ===")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/ai/test_charts.py", "-q", "--tb=line"],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    print("STEP 2: PASSED")


def step3_delegation_real_init() -> None:
    print("\n=== STEP 3: EnhancedAIVanna delegation (real __init__, no DB) ===")
    from unittest.mock import patch

    from vanna.legacy.chromadb.chromadb_vector import ChromaDB_VectorStore
    from vanna.legacy.openai import OpenAI_Chat

    from vanna_grok import EnhancedAIVanna

    with patch.object(
        ChromaDB_VectorStore, "__init__", lambda self, config=None: None
    ), patch.object(
        OpenAI_Chat, "__init__", lambda self, client=None, config=None: None
    ), patch(
        "business_analyzer.ai.base.create_ai_client",
        return_value=(object(), {"model": "test"}, "openai"),
    ):
        vn = EnhancedAIVanna()

    assert vn.provider, "provider must be set by real __init__"
    print("provider:", vn.provider)

    vn._last_result_df = CLIENT_PROFIT_DF.copy()
    vn._last_question = "Clientes más rentables por ganancia"

    code = vn.generate_plotly_code(question=vn._last_question)
    fig = vn.get_plotly_figure(code, CLIENT_PROFIT_DF, dark_mode=False)

    print("delegation_code_has_h:", "orientation='h'" in code)
    print("delegation_code_has_update_traces:", "update_traces" in code)
    print("delegation_trace_count:", len(fig.data))
    print("delegation_orientation:", fig.data[0].orientation)

    assert "orientation='h'" in code
    assert len(fig.data) == 1
    assert fig.data[0].orientation == "h"
    print("STEP 3: PASSED")


def step4_client_profit_transcript() -> None:
    print("\n=== STEP 4: client profit chart transcript (full stdout + fig dict) ===")
    fig = build_smart_figure(
        CLIENT_PROFIT_DF, question="Clientes más rentables por ganancia"
    )
    assert fig is not None

    transcript_lines = [
        "=== client_profit_chart invocation transcript ===",
        f"trace_count={len(fig.data)}",
        f"orientation={fig.data[0].orientation}",
        f"layout_title={fig.layout.title.text}",
        f"repr_layout={repr(fig.layout)}",
        "fig_to_dict_full:",
        json.dumps(fig.to_dict(), indent=2, default=str),
    ]
    transcript = "\n".join(transcript_lines) + "\n"

    SCRATCH.mkdir(parents=True, exist_ok=True)
    client_log = SCRATCH / "client_profit_chart.log"
    client_log.write_text(transcript, encoding="utf-8")

    print(transcript)
    print(f"Wrote full transcript ({client_log.stat().st_size} bytes) to {client_log}")
    print("STEP 4: PASSED")


def main() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    charts_log_path = SCRATCH / "charts_verify.log"
    final_log_path = SCRATCH / "charts_verify_final.log"

    buffer = io.StringIO()
    tee_out = _Tee(sys.stdout, buffer)

    exit_code = 0
    try:
        with redirect_stdout(tee_out), redirect_stderr(tee_out):
            _write_scope_manifest()
            step1_spot_checks()
            step2_pytest()
            step3_delegation_real_init()
            step4_client_profit_transcript()
            print("\nALL_VERIFICATION_STEPS_PASSED")
    except Exception:
        with redirect_stdout(tee_out), redirect_stderr(tee_out):
            traceback.print_exc()
        exit_code = 1

    full_output = buffer.getvalue()
    charts_log_path.write_text(full_output, encoding="utf-8")
    final_log_path.write_text(
        "\n".join(
            [
                "charts_verify_final.log",
                f"exit_code={exit_code}",
                f"charts_verify.log_bytes={charts_log_path.stat().st_size}",
                f"client_profit_chart.log_bytes={(SCRATCH / 'client_profit_chart.log').stat().st_size if (SCRATCH / 'client_profit_chart.log').exists() else 0}",
                f"scope_manifest={(SCRATCH / 'scope_manifest.txt').exists()}",
                "",
                "=== tail of charts_verify.log ===",
                full_output[-4000:] if len(full_output) > 4000 else full_output,
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"\nWrote {charts_log_path} ({charts_log_path.stat().st_size} bytes)")
    print(f"Wrote {final_log_path} ({final_log_path.stat().st_size} bytes)")

    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
