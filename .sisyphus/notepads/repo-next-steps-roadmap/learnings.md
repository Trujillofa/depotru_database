# Learnings

- Added deterministic baseline smoke coverage with subprocess contract checks for `python -m src.business_analyzer_combined --help` and the `src.vanna_chat` public import surface.
- Example workflow baseline is stable offline by stubbing optional dependencies for `examples/pandas_approach.py` and using AST-level contract validation for `examples/streamlit_dashboard.py` to avoid runtime secrets/network requirements.

- Formalized repo-native quality config in `pyproject.toml` for pytest/black/isort/mypy and paired it with `.flake8` because flake8 still reads INI-style config more reliably across versions.
- Quality gate now runs deterministically offline by checking only local source/tests/examples and avoiding any credential-dependent runtime setup.
- Split shared row normalization into `src/contracts/value_coercion.py` so decimal and numeric-string parsing now have a single source of truth reused by `extract_row_value` and analytics helpers.
- Added coercion-focused parity tests that explicitly lock Decimal, grouped numeric-string (`"1,234.56"`), null/missing key fallback, and malformed row payload behavior.
- For callable-typed delegates like `safe_divide`, pass fallback defaults positionally (third arg) to satisfy basedpyright `reportCallIssue` while preserving runtime behavior.
- Extracting DB boundaries is safer when the query string construction is isolated in a pure helper (`build_banco_datos_query`) so filter invariants can be tested without requiring a live database.
- Keeping connection precedence in one resolver (`resolve_connection_details`) preserves CLI behavior while making direct-env vs NCX fallback testable with simple monkeypatching.
- Report-layer extraction works cleanly by moving only `generate_visualization_report` + matplotlib wiring into `src/reporting/visualization.py` and keeping `src/business_analyzer_combined.py` as a thin facade delegating to that module.
- Output-path compatibility is preserved by retaining the default filename contract `business_analysis_report_%Y%m%d_%H%M%S.png` under `Config.OUTPUT_DIR` and keeping `os.path.expanduser` for custom output paths.
- Full-suite stability improved by setting low `Config.REPORT_DPI` inside the new smoke test fixture path, which keeps report-generation coverage while avoiding resource pressure during `pytest tests/ -v`.
- Provider-branch refactors remain behavior-compatible when `src/vanna_chat.py` keeps toggle/env ownership and delegates only branch construction to a `ProviderSettings` + factory function.
- Offline provider matrix tests are reliable by stubbing `sys.modules` entries for `vanna.*` optional imports and asserting config payloads instead of provider internals.
- Architecture docs stay accurate when the module ownership rule is written in multiple contributor touchpoints (`README.md`, `docs/ARCHITECTURE.md`, `docs/CONTRIBUTING.md`) instead of a single file.
- Legacy example docs are less likely to cause monolith regressions when they explicitly frame `examples/` as reference material and direct implementation work to extracted `src/*` modules.
