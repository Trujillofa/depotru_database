# F3 Real Manual QA Evidence

Date: 2026-03-13
Scope: hands-on checks for CLI/public surfaces and one negative-path behavior.

## Manual Checks

1) `python -m src.business_analyzer_combined --help`
- Classification: PASS
- Observed behavior: command exited successfully and printed argparse help with documented options (`--start-date`, `--end-date`, `--limit`, `--ncx-file`, `--generate-report`, `--report-output`, `--skip-analysis`).

2) `python -c "from src.vanna_chat import create_vanna_instance, connect_to_database; print('ok')"`
- Classification: PASS
- Observed behavior: printed `ok`.

3) `python -c "import examples.pandas_approach; print('examples-ok')"`
- Classification: PASS
- Observed behavior: printed `examples-ok`.

4) `python -c "import examples.streamlit_dashboard; print('streamlit-ok')"`
- Classification: EXPECTED-SKIP
- Observed behavior:

```text
ModuleNotFoundError: No module named 'streamlit'
```

- Rationale: Streamlit is an optional runtime dependency for dashboard workflow in local/dev environments; missing package behavior is expected for this manual smoke context.

## Negative-Path Check

5) `python -m src.business_analyzer_combined --definitely-invalid-arg`
- Classification: PASS
- Observed behavior: argparse rejected invalid input and printed deterministic error:

```text
business_analyzer_combined.py: error: unrecognized arguments: --definitely-invalid-arg
```

## Outcome

- Blocking FAIL observed: No
- F3 status: PASS (with one EXPECTED-SKIP for optional Streamlit dependency)
