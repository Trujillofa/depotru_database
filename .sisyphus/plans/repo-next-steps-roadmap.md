# Repository Next Steps Roadmap

## TL;DR
> **Summary**: Stabilize behavior first, then formalize tooling, then extract the monolith behind stable facades, then move AI/provider logic and examples onto shared modules.
> **Deliverables**:
> - automated baseline guardrails for the three repo workflows
> - formal repo quality config and CI checks
> - extracted analytics/data-access/reporting/provider modules behind compatibility facades
> - updated docs/examples aligned to the new module boundaries
> **Effort**: Large
> **Parallel**: YES - 2 waves
> **Critical Path**: 1. Baseline Guardrails -> 3. Typed Data Contract Layer -> 4. Extract Analytics Core -> 6. Extract Reporting Layer -> 8. Docs and Consumer Alignment

## Context
### Original Request
Plan the next steps for the repository, analyze the recommended path, and include refactoring, improvements, and development priorities after the recent fixes.

### Interview Summary
- Current runtime baseline is healthy: `pytest tests/` passes and the recent security/import fixes are in place.
- The repo has three public workflows that must continue to work during refactor: CLI analyzer, Vanna chat, and Streamlit/example paths.
- The biggest technical risk is `src/business_analyzer_combined.py`, which mixes configuration, data access, analytics, recommendations, reporting, and CLI orchestration.
- Static-analysis noise is high because DB rows are dynamically shaped and optional imports are handled at runtime.
- Existing docs promise modularity, but the implementation still centralizes too much behavior in one file.

### Metis Review (gaps addressed)
- Added explicit non-regression guardrails for all three workflows before any extraction work.
- Added stable-facade requirement so public entry points keep current names and invocation patterns.
- Added concrete scope boundaries to prevent a big-bang rewrite or premature product work.
- Added explicit contract/golden testing tasks so refactors are validated by behavior, not only by imports.
- Applied default test strategy: `tests-after` on legacy code, strict automated checks for all newly extracted modules.

## Work Objectives
### Core Objective
Restructure the repository into maintainable, testable modules without breaking the current CLI analyzer, Vanna chat workflow, or dashboard/example workflows.

### Deliverables
- Repo-level baseline checks for analyzer, Vanna chat, and example/dashboard entry points.
- Formal quality-tool configuration for pytest, black, isort, flake8, and mypy.
- Shared typed/coercion layer for SQL-shaped row data.
- Extracted analytics, data-access, and reporting modules used through backward-compatible facades.
- Provider factory/service structure for `src/vanna_chat.py` that preserves current env-driven behavior.
- Updated docs and examples that point to extracted modules instead of expanding the monolith.

### Definition of Done (verifiable conditions with commands)
- `python -m pytest tests/ -v` exits `0`.
- `python -m src.business_analyzer_combined --help` exits `0`.
- `python -c "from src.vanna_chat import create_vanna_instance, connect_to_database; print('ok')"` prints `ok`.
- `python -c "import examples.pandas_approach, examples.streamlit_dashboard; print('examples-ok')"` prints `examples-ok` or, if `streamlit` import requires runtime secrets, the repo has a dedicated smoke test that exits `0` instead.
- `black --check src tests examples` exits `0`.
- `isort --check-only src tests examples` exits `0`.
- `flake8 src tests examples` exits `0` under the new scoped config.
- `mypy src` exits `0` for extracted modules and agreed legacy exclusions.

### Must Have
- Preserve current public entry points: `src/business_analyzer_combined.py`, `src/vanna_chat.py`, `examples/pandas_approach.py`, `examples/streamlit_dashboard.py`.
- Keep environment-variable names and current configuration semantics intact unless a wrapper preserves backward compatibility.
- Lock behavior with golden/contract tests before moving logic out of the monolith.
- Route all new feature work through extracted modules after they exist.

### Must NOT Have (guardrails, AI slop patterns, scope boundaries)
- No big-bang rewrite of `src/business_analyzer_combined.py`.
- No network-dependent test that requires live DB/API credentials in CI.
- No replacement of the documented toolchain with a different stack; formalize existing tools instead of introducing `ruff` in this roadmap.
- No public CLI flag changes, env var renames, or provider toggle renames.
- No new business features added directly to `src/business_analyzer_combined.py` after extraction tasks begin.

## Verification Strategy
> ZERO HUMAN INTERVENTION - all verification is agent-executed.
- Test decision: `tests-after` for legacy modules, with strict checks on each extracted module and compatibility facade.
- QA policy: Every task includes agent-executed happy-path and failure/edge-case scenarios.
- Evidence: `.sisyphus/evidence/task-{N}-{slug}.{ext}`

## Execution Strategy
### Parallel Execution Waves
> Target: 5-8 tasks per wave. Extract shared dependencies first for max parallelism.

Wave 1: Baseline guardrails, tooling formalization, and shared contract foundation.
Wave 2: Monolith extraction slices, provider abstraction, and consumer/doc alignment.

### Dependency Matrix (full, all tasks)
| Task | Depends On | Why |
|---|---|---|
| 1. Baseline Guardrails | None | Defines behavior lock before code movement |
| 2. Tooling and CI Formalization | 1 | Uses the stabilized command/test baseline |
| 3. Typed Data Contract Layer | 1, 2 | Needs behavior baseline and tool rules first |
| 4. Extract Analytics Core | 3 | Analytics extraction needs shared row/coercion contracts |
| 5. Extract Data Access and Config Boundaries | 3 | Data access split depends on typed connection/row boundaries |
| 6. Extract Reporting Layer | 4, 5 | Reporting depends on stable metrics output and data-access seams |
| 7. Refactor Vanna Provider Layer | 2 | Independent of analytics extraction but must obey new quality gates |
| 8. Docs and Consumer Alignment | 4, 6, 7 | Should point examples/docs to the new module boundaries only after they exist |

### Agent Dispatch Summary (wave -> task count -> categories)
- Wave 1 -> 3 tasks -> `deep`, `unspecified-high`, `writing`
- Wave 2 -> 5 tasks -> `deep`, `unspecified-high`, `writing`

## TODOs
> Implementation + Test = ONE task. Never separate.
> EVERY task MUST have: Agent Profile + Parallelization + QA Scenarios.

- [x] 1. Lock the Current Behavior Baseline

  **What to do**: Add repo-owned smoke/contract tests that lock the current public behavior for the CLI analyzer, Vanna import surface, and example workflows. Create deterministic fixtures for representative metric output so later extraction work can prove behavioral parity. Prefer fixture-driven tests over live DB/API calls; use monkeypatch/mocks for DB and provider boundaries.
  **Must NOT do**: Do not require real database credentials, real Vanna API keys, or live HTTP access in the baseline suite.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: establishes cross-cutting regression guardrails that all later refactors depend on.
  - Skills: [`git-master`] - why needed: keeps baseline additions atomic and reviewable.
  - Omitted: [`playwright`] - why not needed: current baseline can be locked with command/test smoke checks without browser automation.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [2, 3] | Blocked By: []

  **References**:
  - Pattern: `README.md:46` - repo documents the traditional analyzer workflow.
  - Pattern: `README.md:62` - repo documents the Vanna workflow.
  - Pattern: `README.md:80` - repo documents the dashboard/example workflow.
  - API/Type: `src/business_analyzer_combined.py:1399` - CLI entry point that must stay stable.
  - API/Type: `src/vanna_chat.py:62` - Vanna instance creation surface.
  - Test: `tests/test_business_metrics.py:97` - existing pytest style and assertion patterns.
  - Test: `tests/test_metabase_connection.py:11` - existing import/path conventions for repo modules.

  **Acceptance Criteria**:
  - [ ] `python -m pytest tests/ -v` exits `0` with new baseline tests included.
  - [ ] `python -m src.business_analyzer_combined --help` exits `0` in a test subprocess.
  - [ ] `python -c "from src.vanna_chat import create_vanna_instance, connect_to_database; print('ok')"` prints `ok` in a test subprocess.
  - [ ] Example workflow smoke coverage exists for `examples/pandas_approach.py` and the Streamlit dashboard path without requiring live DB access.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path baseline smoke suite
    Tool: Bash
    Steps: Run `python -m pytest tests/ -v` after adding analyzer/provider/example smoke tests.
    Expected: Exit code 0; output includes the new smoke/contract tests and no live-network failures.
    Evidence: .sisyphus/evidence/task-1-baseline-pytest.txt

  Scenario: Failure path with missing credentials
    Tool: Bash
    Steps: Run a dedicated smoke test that clears DB/API env vars and invokes the analyzer/provider import surfaces with mocks only.
    Expected: Tests assert graceful validation or mocked behavior rather than a raw import/runtime crash.
    Evidence: .sisyphus/evidence/task-1-baseline-error.txt
  ```

  **Commit**: YES | Message: `test(baseline): lock analyzer and provider behavior` | Files: [`tests/`, optional `tests/fixtures/`]

- [x] 2. Formalize Quality Tooling and CI

  **What to do**: Add repo-native config for pytest, black, isort, mypy, and flake8. Use `pyproject.toml` for shared tool config, add a dedicated `.flake8` only if needed, and add a GitHub Actions workflow that runs the baseline test suite plus formatting/type checks. Scope legacy mypy coverage to the extracted/new modules first; explicitly exclude noisy legacy sections until extraction lands.
  **Must NOT do**: Do not replace the documented toolchain with `ruff`; do not set CI to require live credentials.

  **Recommended Agent Profile**:
  - Category: `unspecified-high` - Reason: repo-wide tooling/CI wiring spans multiple root files and quality gates.
  - Skills: [`git-master`] - why needed: tooling changes should land in one coherent chore commit.
  - Omitted: [`playwright`] - why not needed: no browser flow is required.

  **Parallelization**: Can Parallel: NO | Wave 1 | Blocks: [3, 7] | Blocked By: [1]

  **References**:
  - Pattern: `requirements.txt:52` - pytest is already a documented dependency.
  - Pattern: `requirements.txt:54` - black is already documented.
  - Pattern: `requirements.txt:55` - flake8 is already documented.
  - Pattern: `requirements.txt:56` - mypy is already documented.
  - Pattern: `requirements.txt:57` - isort is already documented.
  - Pattern: `README.md:302` - existing developer guidance already instructs these checks.
  - Pattern: `docs/ARCHITECTURE.md:30` - architecture docs already claim modular, maintainable structure.

  **Acceptance Criteria**:
  - [ ] `python -m pytest tests/ -v` exits `0` in CI and locally.
  - [ ] `black --check src tests examples` exits `0`.
  - [ ] `isort --check-only src tests examples` exits `0`.
  - [ ] `flake8 src tests examples` exits `0` under the new config.
  - [ ] `mypy src` exits `0` for the allowed scope documented in config.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path quality gate
    Tool: Bash
    Steps: Run `python -m pytest tests/ -v && black --check src tests examples && isort --check-only src tests examples && flake8 src tests examples && mypy src`.
    Expected: All commands exit 0 under the new repo config.
    Evidence: .sisyphus/evidence/task-2-quality-gate.txt

  Scenario: Failure path on intentionally malformed file order
    Tool: Bash
    Steps: Run at least one tool individually against a temporary mismatched file state in test harness or documented negative fixture.
    Expected: The command fails with a deterministic lint/format error, proving the gate is active.
    Evidence: .sisyphus/evidence/task-2-quality-gate-error.txt
  ```

  **Commit**: YES | Message: `chore(tooling): formalize quality checks and ci` | Files: [`pyproject.toml`, optional `.flake8`, `.github/workflows/ci.yml`]

- [x] 3. Introduce a Typed Data Contract and Coercion Layer

  **What to do**: Create a shared module for SQL-row contracts and coercion helpers used by analytics and reporting code. Define typed aliases/`TypedDict` structures for raw DB rows and normalized metric payloads, and move value-extraction/coercion rules out of the monolith so later extraction slices depend on one source of truth.
  **Must NOT do**: Do not attempt to fully type every legacy dict in one pass; type the shared contracts needed for extraction and suppress/bridge the rest.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: this task reduces legacy dynamic-shape ambiguity and unlocks safe refactors.
  - Skills: [`git-master`] - why needed: contract introduction should be isolated from extraction logic.
  - Omitted: [`dev-browser`] - why not needed: repo evidence is enough.

  **Parallelization**: Can Parallel: YES | Wave 1 | Blocks: [4, 5] | Blocked By: [1, 2]

  **References**:
  - Pattern: `src/business_analyzer_combined.py:225` - current row coercion lives inside the monolith.
  - Pattern: `src/business_analyzer_combined.py:245` - financial metrics consume dynamic row values repeatedly.
  - Pattern: `src/business_analyzer_combined.py:733` - DB fetch returns `List[Dict[str, Any]]` today.
  - Pattern: `tests/test_business_metrics.py:61` - decimal/nullable fixture cases to preserve.
  - Pattern: `examples/pandas_approach.py:40` - dataframe path already normalizes field names; use this as naming guidance.

  **Acceptance Criteria**:
  - [ ] Shared row/coercion module exists and is imported by at least one legacy facade plus one new/extracted module.
  - [ ] Decimal, string-number, and `None` handling matches the current behavior validated by tests.
  - [ ] `mypy` passes on the new contract module and its direct consumers.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path coercion parity
    Tool: Bash
    Steps: Run targeted pytest cases covering float, Decimal, numeric-string, and null row values through the new contract/coercion helpers.
    Expected: Outputs match the legacy behavior currently covered by business-metric fixtures.
    Evidence: .sisyphus/evidence/task-3-contract-parity.txt

  Scenario: Failure path with unsupported row payload
    Tool: Bash
    Steps: Run a targeted test that passes a malformed row (missing expected keys or wrong scalar type) into the new contract/coercion layer.
    Expected: The helper raises a deliberate validation error or returns the documented fallback instead of silently corrupting metrics.
    Evidence: .sisyphus/evidence/task-3-contract-parity-error.txt
  ```

  **Commit**: YES | Message: `refactor(types): add shared row contracts and coercion` | Files: [`src/` new contract module, updated tests]

- [x] 4. Extract the Analytics Core Behind a Compatibility Facade

  **What to do**: Move pure metric computation out of `src/business_analyzer_combined.py` into dedicated analytics modules (financial, customers, products, categories, inventory, trends, profitability, risk/efficiency if kept together). Keep `BusinessMetricsCalculator` as a backward-compatible facade that delegates to the new modules without changing caller behavior.
  **Must NOT do**: Do not move DB connection logic, CLI parsing, or matplotlib/reporting code in this task.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: large extraction with heavy dependency on data-shape correctness and regression safety.
  - Skills: [`git-master`] - why needed: this should land as a focused extraction slice.
  - Omitted: [`playwright`] - why not needed: module extraction is verified by tests/subprocess checks.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [6, 8] | Blocked By: [3]

  **References**:
  - Pattern: `src/business_analyzer_combined.py:205` - current facade/class entry point.
  - Pattern: `src/business_analyzer_combined.py:211` - top-level metrics payload shape returned today.
  - Pattern: `src/business_analyzer_combined.py:245` - financial metrics extraction pattern.
  - Pattern: `src/business_analyzer_combined.py:308` - customer analytics branch.
  - Pattern: `src/business_analyzer_combined.py:397` - product analytics branch.
  - Pattern: `src/business_analyzer_combined.py:457` - category analytics branch.
  - Pattern: `tests/test_business_metrics.py:218` - downstream metric expectations.
  - Pattern: `examples/pandas_approach.py:87` - reduced analytics organization for inspiration, not direct copy.

  **Acceptance Criteria**:
  - [ ] `BusinessMetricsCalculator.calculate_all_metrics()` returns the same top-level keys and nested shapes as before.
  - [ ] `python -m pytest tests/test_business_metrics.py -v` exits `0`.
  - [ ] New analytics modules pass `mypy` and are imported by the facade.
  - [ ] No new business logic remains added in the monolith for extracted concerns.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path analytics parity
    Tool: Bash
    Steps: Run the full business metrics test file plus a fixture-based parity test comparing legacy facade output against extracted module output for the same sample dataset.
    Expected: Outputs are identical for financial, customer, product, and category result shapes.
    Evidence: .sisyphus/evidence/task-4-analytics-parity.txt

  Scenario: Failure path with sparse/null-heavy rows
    Tool: Bash
    Steps: Run targeted tests against the extracted analytics modules using the null/decimal fixtures.
    Expected: Modules retain safe default behavior and do not crash on missing values.
    Evidence: .sisyphus/evidence/task-4-analytics-parity-error.txt
  ```

  **Commit**: YES | Message: `refactor(analytics): extract metrics engine behind facade` | Files: [`src/business_analyzer_combined.py`, new `src/analytics/` modules, tests]

- [x] 5. Extract Data Access and Connection Handling Boundaries

  **What to do**: Split connection loading, NCX parsing, and `fetch_banco_datos()` query construction into dedicated modules such as `src/data_access/connections.py` and `src/data_access/banco_datos.py`. Keep `src/business_analyzer_combined.py` calling the new APIs so the CLI entry point stays stable.
  **Must NOT do**: Do not change SQL semantics, excluded document code behavior, env var names, or default table/database names.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: data-access extraction affects config, DB connectivity, and CLI orchestration.
  - Skills: [`git-master`] - why needed: extraction should remain atomic and reversible.
  - Omitted: [`playwright`] - why not needed: no browser testing is needed.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [6, 8] | Blocked By: [3]

  **References**:
  - Pattern: `src/config.py:39` - central config class to preserve.
  - Pattern: `src/config.py:78` - output-dir and validation helpers already live in config.
  - Pattern: `src/business_analyzer_combined.py:693` - NCX connection loading flow.
  - Pattern: `src/business_analyzer_combined.py:733` - current fetch/query implementation.
  - Pattern: `src/business_analyzer_combined.py:1443` - current CLI connection-selection logic.
  - Test: `tests/test_metabase_connection.py:11` - existing connection test/import shape.

  **Acceptance Criteria**:
  - [ ] Analyzer CLI still resolves direct env-based DB config or NCX-based config using the same precedence rules.
  - [ ] Query-building preserves `DocumentosCodigo NOT IN ('XY', 'AS', 'TS')` behavior.
  - [ ] Existing and new tests cover direct-config, NCX-path, and no-config failure behavior.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path connection-resolution smoke
    Tool: Bash
    Steps: Run targeted pytest cases that monkeypatch `Config` and connection-loading helpers for both direct-env and NCX-based branches.
    Expected: The facade returns the same connection-details payload and fetch path chosen today.
    Evidence: .sisyphus/evidence/task-5-data-access-smoke.txt

  Scenario: Failure path with missing config
    Tool: Bash
    Steps: Run a targeted test that clears DB env vars and points NCX loading to a missing path.
    Expected: The code raises a deliberate validation error matching current CLI behavior instead of a raw key/index error.
    Evidence: .sisyphus/evidence/task-5-data-access-smoke-error.txt
  ```

  **Commit**: YES | Message: `refactor(data): extract connection and fetch boundaries` | Files: [`src/business_analyzer_combined.py`, new `src/data_access/` modules, tests]

- [x] 6. Extract Reporting and Visualization into a Dedicated Layer

  **What to do**: Move `generate_visualization_report()` and related formatting/report assembly helpers into a dedicated reporting module. Keep `src/business_analyzer_combined.py` calling the new reporting API. Normalize output path handling and isolate optional matplotlib imports so static analysis and runtime behavior are easier to manage.
  **Must NOT do**: Do not redesign the report layout, KPI labels, or file naming in this task; this is a structural extraction, not a product redesign.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: reporting depends on extracted metrics and current output conventions.
  - Skills: [`git-master`] - why needed: keeps reporting extraction bundled with its regression tests.
  - Omitted: [`frontend-ui-ux`] - why not needed: no visual redesign is in scope.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [8] | Blocked By: [4, 5]

  **References**:
  - Pattern: `src/business_analyzer_combined.py:901` - current reporting entry point.
  - Pattern: `src/business_analyzer_combined.py:918` - expected analysis payload consumed by the report.
  - Pattern: `src/business_analyzer_combined.py:926` - current matplotlib layout bootstrap.
  - Pattern: `src/config.py:66` - output directory handling.
  - Pattern: `examples/streamlit_dashboard.py:91` - dashboard metric shape that should stay conceptually aligned with reporting outputs.

  **Acceptance Criteria**:
  - [ ] Report generation still skips cleanly when matplotlib is unavailable.
  - [ ] Report filenames and output-directory behavior stay compatible with current analyzer expectations.
  - [ ] A fixture-based report smoke test verifies file creation without requiring manual inspection.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path report smoke
    Tool: Bash
    Steps: Run a targeted pytest case that passes a fixture analysis payload into the extracted reporting API and writes to a temp directory.
    Expected: A `.png` file is created at the expected path and the function returns that path.
    Evidence: .sisyphus/evidence/task-6-report-smoke.txt

  Scenario: Failure path without matplotlib
    Tool: Bash
    Steps: Run a targeted test that monkeypatches reporting imports/availability to simulate matplotlib absence.
    Expected: The function returns `None` or the documented skip result without raising.
    Evidence: .sisyphus/evidence/task-6-report-smoke-error.txt
  ```

  **Commit**: YES | Message: `refactor(reporting): extract visualization layer` | Files: [`src/business_analyzer_combined.py`, new `src/reporting/` modules, tests]

- [x] 7. Refactor `vanna_chat.py` into a Provider Factory and Service Layer

  **What to do**: Replace the repeated provider branching in `src/vanna_chat.py` with a provider factory/service layout that preserves the same env vars, provider toggles, and public functions (`create_vanna_instance`, `connect_to_database`, `train_vanna_on_schema`, `main`). Separate provider selection from schema-training and DB-connection code.
  **Must NOT do**: Do not change default provider semantics, base URLs, model names, or current environment variable names.

  **Recommended Agent Profile**:
  - Category: `deep` - Reason: provider abstraction is a second architecture slice with multiple optional-import branches.
  - Skills: [`git-master`] - why needed: keep provider refactor isolated from analytics work.
  - Omitted: [`dev-browser`] - why not needed: repository code and current module behavior are sufficient.

  **Parallelization**: Can Parallel: YES | Wave 2 | Blocks: [8] | Blocked By: [2]

  **References**:
  - Pattern: `src/vanna_chat.py:62` - current provider selection function.
  - Pattern: `src/vanna_chat.py:70` - current OpenAI/VannaDB branch shape.
  - Pattern: `src/vanna_chat.py:82` - current Ollama branch shape.
  - Pattern: `src/vanna_chat.py:97` - current Anthropic branch shape.
  - Pattern: `src/vanna_chat.py:112` - current Grok/OpenAI-compatible branch shape.
  - Pattern: `src/vanna_chat.py:133` - DB-connection handoff that must stay callable.
  - Pattern: `docs/ARCHITECTURE.md:156` - docs already describe provider-driven Vanna architecture.

  **Acceptance Criteria**:
  - [ ] `from src.vanna_chat import create_vanna_instance, connect_to_database, train_vanna_on_schema` still works.
  - [ ] Provider selection remains environment/toggle driven with matching branch behavior.
  - [ ] New provider-factory tests cover OpenAI, Ollama, Anthropic, and Grok branch selection without live API calls.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path provider selection matrix
    Tool: Bash
    Steps: Run targeted pytest cases that monkeypatch provider toggles/imports and assert the factory selects the expected provider class/config for OpenAI, Ollama, Anthropic, and Grok.
    Expected: Each branch returns the expected provider wrapper without network calls.
    Evidence: .sisyphus/evidence/task-7-provider-matrix.txt

  Scenario: Failure path with no provider enabled
    Tool: Bash
    Steps: Run a test that disables all provider toggles and calls the factory.
    Expected: The code raises the current deliberate `ValueError`-style configuration failure.
    Evidence: .sisyphus/evidence/task-7-provider-matrix-error.txt
  ```

  **Commit**: YES | Message: `refactor(vanna): introduce provider factory service` | Files: [`src/vanna_chat.py`, new `src/vanna/` or equivalent modules, tests]

 [x] 8. Align Docs, Examples, and Future Development Rules to the Extracted Architecture

  **What to do**: Update docs and examples so they describe the real post-refactor structure and route future development toward extracted modules. Explicitly document that new analytics logic must go into extracted modules, not `src/business_analyzer_combined.py`. Where practical, update examples/dashboard code to consume shared extracted helpers instead of duplicating metric/query logic.
  **Must NOT do**: Do not rewrite product copy or redesign the dashboard; focus on architectural alignment and consumer reuse.

  **Recommended Agent Profile**:
  - Category: `writing` - Reason: this is documentation/consumer alignment with light code wiring.
  - Skills: [`git-master`] - why needed: doc/example alignment should be committed together after the extraction slices stabilize.
  - Omitted: [`frontend-ui-ux`] - why not needed: no redesign work is required.

  **Parallelization**: Can Parallel: NO | Wave 2 | Blocks: [] | Blocked By: [4, 6, 7]

  **References**:
  - Pattern: `README.md:92` - current project-structure narrative.
  - Pattern: `docs/ARCHITECTURE.md:22` - three-interface architecture promise to preserve.
  - Pattern: `docs/ARCHITECTURE.md:128` - current analyzer section that still points at the monolith.
  - Pattern: `examples/pandas_approach.py:23` - example that already demonstrates a cleaner modular direction.
  - Pattern: `examples/streamlit_dashboard.py:54` - dashboard data loading path that can be aligned to extracted helpers.

  **Acceptance Criteria**:
  - [ ] Docs accurately describe the new module boundaries and stable entry points.
  - [ ] Examples either reuse shared extracted helpers or explicitly document why they remain standalone.
  - [ ] A contributor-facing rule exists stating that new analytics/reporting/provider logic must target extracted modules, not the monolith.

  **QA Scenarios** (MANDATORY - task incomplete without these):
  ```
  Scenario: Happy path doc and consumer alignment
    Tool: Bash
    Steps: Run `python -m pytest tests/ -v` plus any new smoke tests for examples/consumers after docs/example updates.
    Expected: Tests still pass and all referenced commands/files in the updated docs exist.
    Evidence: .sisyphus/evidence/task-8-docs-consumers.txt

  Scenario: Failure path for stale architecture references
    Tool: Bash
    Steps: Run a grep-based or scripted doc check that looks for obsolete instructions pointing new work back into `src/business_analyzer_combined.py` for extracted concerns.
    Expected: The check finds zero stale references for extracted responsibilities.
    Evidence: .sisyphus/evidence/task-8-docs-consumers-error.txt
  ```

  **Commit**: YES | Message: `docs(architecture): align examples and module boundaries` | Files: [`README.md`, `docs/`, `examples/`, optional contributor docs]

## Final Verification Wave
- [x] F1. Plan Compliance Audit - oracle
- [x] F2. Code Quality Review - unspecified-high
- [x] F3. Real Manual QA - unspecified-high (+ playwright if UI)
- [x] F4. Scope Fidelity Check - deep

## Commit Strategy
- Use one atomic commit per task.
- Preserve a backward-compatible facade in the same commit as each extraction.
- Commit message pattern:
  - `test(baseline): lock analyzer and provider behavior`
  - `chore(tooling): formalize quality checks and ci`
  - `refactor(analytics): extract metrics engine behind facade`
  - `refactor(vanna): introduce provider factory service`
  - `docs(architecture): align examples and module boundaries`

## Success Criteria
- The repository still supports the three documented workflows with stable entry points.
- The largest monolith responsibilities are split into modules with contract-backed facades.
- Static-analysis output drops from broad legacy noise to scoped, actionable checks.
- New development paths flow through extracted modules, not through `src/business_analyzer_combined.py`.
- Docs and examples describe the real architecture, not the aspirational one.
