# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Vanna web UI**: minimalist shell with one accent color and display font
  scale (sidebar, header, suggestion chips, composer pinned to the viewport
  bottom). The recommended-reports panel is now grouped (Gerencial, Sedes,
  Operación, TSOL) and collapsible per report, with compact period controls
  and a per-card status line. Report payloads use structured fields only
  (no duplicated natural-language question), surface HTTP failures, and no
  longer auto-open downloads (the "Abrir informe" link is kept). The panel
  CSS/JS now ships as cached `/assets/informes.{css,js}` files; vendor CSS is
  served in a lower cascade layer so overrides work without `!important`.
  Dark mode also follows `prefers-color-scheme`; Plotly loads with `defer`.
  Vanna's English chrome is localized ("Preguntas sugeridas", "Consola",
  "Menú"). Catalog entries expose a `group` field, and the January default
  now falls back to December of the previous year.

### Fixed

- **Vanna debug console / unknown API paths**: `SmartVannaFlaskApp` now defaults
  to `debug=False` because Waitress cannot serve the `/api/v0/log` WebSocket
  (the console failed on every page load). Unmatched `/api/v0/*` paths now
  return `404` with a JSON error instead of Vanna's blanket `200` stub.

- **Manager report rendering (HTML)**: AI narrative now renders Markdown
  instead of literal `**`/`---`; narrative token budget raised so reports are
  not cut mid-sentence; removed duplicate `$` in executive summary/opportunities;
  Colombian comma decimals in vendor/marca/mix/ABC percentages and
  `Prom./Mes`; full customer/product names (no mid-word cuts); empty
  per-customer order groups dropped; `Stock` column hidden when J3 stock is
  unavailable; singular/plural labels; KPI grid is 3x2 with fluid values so
  consolidated amounts are no longer clipped.
- **Manager report charts**: axis ticks no longer collapse to duplicate
  `$2M`/`$4M` labels; vendor value+margin labels combined to stop overlap;
  pie aggregates small categories into `Otros` with a legend; category bar
  labels deduplicated; scatter annotations staggered and weighted average
  margin; weekend shading uses real calendar dates; pie groups the long tail
  as `Resto (N cat.)` and sorts slices/legend consistently.
- **Cartera / Rotación / KPI / TSOL reports**:
  - shared `reports/text.py` helpers (`decimal_es`, `percent_es`,
    `money_compact`, `shorten`, `strip_markdown`) replace duplicated
    formatters in HTML/PDF renderers, charts and the monthly CLI
  - full client/product/seller names in HTML tables (word-boundary `…` only
    where a column truly needs it); insight prose keeps full names
  - KPI Control Board numbers localized (decimal comma, dotted thousands)
  - manager PDF strips Markdown from the AI narrative and reuses compact
    currency labels
  - CLI text report: Spanish ABC labels, singular/plural (`1 proveedor`,
    `1 unidad`), no `N/A` stock noise, localized record counts
- **AI providers / SQL chat**: added `groq`, `openrouter` and `commandcode`
  providers. `commandcode` wraps the local CLI as an OpenAI client, so Vanna
  SQL works on the active subscription without token limits (verified: NL→SQL
  in ~9 s). `AI_PROVIDER` is now `commandcode`; report narratives use the same
  CLI with a configurable chain (`REPORT_AI_FALLBACK_PROVIDERS`) and a
  content-addressed cache (`REPORT_AI_CACHE_DIR`).
- **Health endpoint**: `/api/v0/health` reports SQL provider, report provider
  and fallbacks, CLI path, keys present, cache state and output dir.
- **TSOL quality gate**: `--strict` returns exit 2 when high-severity issues
  exist (placeholder NIT, blank channel/seller, negative stock) and every run
  writes a sibling `.calidad.json` with `issues`. Quality JSON now includes
  `placeholder_nit` and `generic_customer`.
- **KPI board guards**: missing budget and negative inventory coverage render
  `—` with an explicit warning instead of `0,00%` / `-50,8 días`.
- **Ticket KPI**: `Ticket Promedio` is now labelled **con IVA** and each report
  shows the **sin IVA** value (HTML sub-label, PDF second line, CLI, prompt).
- **PDF narrative**: keeps bold emphasis from Markdown instead of stripping it;
  `_strip_html` moved to `reports/text.py`.
- **Tests**: HTML contract test (no `**`, no `$$`, comma decimals, hidden empty
  stock column, dual ticket) + text helper, fallback/cache and TSOL strict tests.
- **Artifacts**: generated cartera/turnover HTML is now ignored under `reports/`.
- **Vanna Waitress timeout**: `channel_timeout` default 600s (was Waitress 120s)
  so sede manager reports can finish without the UI dropping the connection.
  Override with `WAITRESS_CHANNEL_TIMEOUT`.
- **Vanna systemd memory**: `MemoryHigh=2G` / `MemoryMax=3G` (was 768M / 1G)
  so report generation is not forced into swap.

### Changed

- **AI provider DeepSeek**: set `AI_PROVIDER=deepseek` + `DEEPSEEK_API_KEY`
  for Vanna SQL and manager-report narratives (OpenAI-compatible
  `https://api.deepseek.com`, default model `deepseek-chat`).
- **Contabilidad ERP — Balance y PyG (PUC)** is only in the consolidated
  gerencial report. Sede reports (Calle 5 / Sika Center / Almacén Principal)
  skip the J3 `ConMovimiento*` query and omit the HTML/PDF section.

### Added

- **Report narratives via Command Code CLI** (`REPORT_AI_PROVIDER=commandcode`
  or `--ai-provider commandcode`): uses the locally authenticated
  `commandcode` subscription (`COMMANDCODE_MODEL`, default
  `deepseek/deepseek-v4.1-flash`) for manager-report AI analysis, independent
  of `AI_PROVIDER` used by Vanna SQL. The prompt forbids follow-up questions,
  file-save offers and invented findings; agent chatter is stripped from the
  output, and prompt currency values no longer duplicate the `$` sign. Reports also clarify that
  `Ticket Promedio` is **con IVA** (it is `TotalMasIva / transacciones`).
- **TSOL-GENERAL sell-out export** (`depotru-tsol-export`):
  - Fills the manufacturer template (Ventas + Inventario) from `banco_datos`
    plus J3 masters (`AdmTerceros`, `AdmCiudad`, `AdmVendedor`, stock)
  - Brands: `sika` (default), `pintuco`, `all`; previous calendar month
  - Dates as DDMMYYYY text; municipality as DIVIPOLA; NIT with DV
  - CLI: `python scripts/analysis/run_tsol_export.py --brand sika --year 2026 --month 7`
  - Pintuco grain vs J3 dump: SKU `009%`, electronic credit notes as
    signed rows, **all bodegas** (txt `Ventas` is ALM-only; Excel is not)
  - Date range / `--ytd` for 2026-to-date plantilla fills
  - Vanna Informes recomendados: **TSOL Sika** and **TSOL Pintuco** (Excel)

- **Hybrid stub-first LLM assistant** (`ASSISTANT_LLM=1`):
  - Confident stub paths (greetings, sedes, cart, guides, product search) skip LLM
  - Generic-help fallthrough uses Grok tool loop (`info.branches`, `catalog.search_products`)
  - `mode=llm_tools` when LLM answers; fail-soft back to stub help
  - Module: `modules.assistant.llm_router`
- **Assistant routing quality (production chat log)**:
  - Greeting-only turns return help without `platform.health`
  - Product extract: `cotizar`, `ando buscando`, strip leading greeting/qty
  - Bare product-name fallthrough → `catalog.search_products`
  - Cart/checkout/pay intent → Spanish storefront ops reply (no product misroute)
  - Branch phrasing: `dónde quede`, `sede principal`
  - Guide patterns: tanque ajover/cotizar, lámina galvanizada, anticorr typos, sikagrout/grouting
- **Website J3 warehouse allowlist** (depositotrujillo.co#182):
  - SSOT: `website_warehouse_policy` denylist CEN/EXH/EXD/BDT/MDL/TRA
  - SQL: website vs excluded stock from `InvDetalleExistencias`
  - CLI: `depotru-website-stock` (impact report, Magento compare, gated MSI write)
  - Magento client: optional `post_source_items`
  - Docs: `docs/reference/website-warehouse-allowlist.md`
  - **Scheduled MSI re-apply** via SSH: `scripts/ops/run_website_stock_allowlist_sync.py` +
    systemd timer `depotru-website-stock-allowlist` (until B2C denylist is configured)
- **Platform Phase 0 skeleton** for multi-module scale (Magento assistant, CRM, WMS, catalog):
  - `depotru_kernel` — document exclusions, COP formatting, unified attribution wrapper, audience/scopes
  - `depotru_tools` — capability registry + builtins (`platform.health`, `info.branches`, `attribution.resolve_seller`, `catalog.related_for_sku`, `inventory.sellable_qty`)
  - `depotru_integrations` — Magento REST client (MSI sellable qty + SafetyStock policy), affinity CSV contract **v1.0.0**
  - `modules/{bi,assistant,crm,wms,catalog}` scaffolds; assistant BFF tool-routing stub
  - FastAPI **`/v1`** routes: health, tools list/call, assistant chat, affinity contract
  - Docs: `docs/PLATFORM.md`, rewritten `docs/ROADMAP.md`
  - Auth: `PLATFORM_API_KEYS=key:audience` map + `X-Audience` header

## [2.1.0] - 2026-07-09

### Added

- **Mediano-plazo KPIs Q12–Q17** in the weekly KPI SQL pack and control board:
  - Q12 cotización → factura funnel (J3System)
  - Q13 critical inventory / coverage
  - Q14 OTIF and delivery lead time
  - Q15 devoluciones ERP vs BI reconciliation
  - Q16 factura electrónica DIAN acceptance
  - Q17 contabilidad PyG from `ConMovimiento*` (PUC classes)
- **Contabilidad** in monthly manager report: PUC 1–3 balance sheet labels, economic PyG (cl.4 − cl.5 − cl.6)
- **Vanna Informes recomendados**: catalog API, sidebar panel, period/format/branch pickers
- **Weekly KPI Control Board** generation from the chat UI (`/api/v0/generate_kpi_board`) plus `make kpi-weekly` automation
- **J3System warehouse-per-sale** routing in manager report queries
- Sample KPI snapshots (e.g. `reports/KPI_CONTROL_BOARD_2026_W27.md`) and Dec/May 2024 manager/contabilidad reports

### Fixed

- Contabilidad equation gap explained via open PyG balances; economic result formula
- Explicit format honored on catalog report clicks
- Sika / brand warehouse SQL routing (document branch vs warehouse)
- Flask/Vanna display fixes (duplicate SQL blocks, row limits, chart labels)
- CI compatibility for MCP and DB/API-excluded tests

### Changed

- Recommended reports catalog is template-based (user chooses month/year/format or ISO week)
- KPI scorecard: Q1 uses a 4-week lookback for north-star baselines when the board window is a single week; snapshot KPIs show baseline `—` (delta vs target) instead of faking baseline = current
- KPI diagnostics: computable WoW margin drop (prior week Q2) and estimated returns margin impact

## [2.0.0] - 2026-02-12

### Added

#### Modular Architecture
- **business_analyzer package** - Complete modularization of monolithic codebase
  - `core/` module with database connection management, configuration, and validation
  - `analysis/` module with 4 specialized analyzers (customer, product, financial, inventory)
  - `ai/` package with multi-provider AI support
  - `utils/` module with encoding, math, and Navicat utilities
  - Reduced average file size from 1,690 lines to ~84 lines per module

#### AI Package with Multi-Provider Support
- **New `business_analyzer/ai/` package** supporting 4 AI providers:
  - xAI Grok (default) - Production-ready with Spanish optimization
  - OpenAI GPT-4 - Best accuracy for complex queries
  - Anthropic Claude - Advanced reasoning capabilities
  - Ollama (local) - Privacy-focused, no API costs
- Provider selection via `AI_PROVIDER` environment variable
- Factory pattern for provider-specific initialization
- Preserved all production features: Colombian formatting, AI insights, error handling

#### Analysis Modules
- **customer.py** - Customer segmentation and analytics
  - VIP, High Value, Frequent, Regular customer classification
  - Top customers identification
  - Customer concentration analysis
- **product.py** - Product performance and profitability
  - Top selling products identification
  - Star products (>30% margin) and underperformers (<10% margin)
  - Category profitability analysis
- **financial.py** - Financial metrics and KPIs
  - Revenue analysis (with/without IVA)
  - Profit margin calculations
  - Average order value tracking
- **inventory.py** - Inventory velocity and optimization
  - Fast movers (>5 transactions) and slow movers (<2 transactions)
  - Inventory turnover analysis
  - Stock optimization recommendations

#### Database Module
- **business_analyzer/core/database.py** - Comprehensive database management
  - `Database` class with connection pooling support
  - Multiple connection types: DIRECT, SSH_TUNNEL, NAVICAT
  - Navicat NCX file parsing with automatic password decryption
  - SQL injection prevention via `validate_sql_identifier()`
  - Context manager support (`with Database() as db:`)
  - Parameterized query execution for security

#### Comprehensive Test Suite
- **200+ tests** across all modules
- Test coverage increased from ~17% to ~54%
- New test files:
  - `tests/test_business_analyzer_combined.py` (37 tests)
  - `tests/test_config_full.py` (10 tests)
  - `tests/analysis/test_*.py` (64 tests for 4 analyzers)
  - `tests/ai/test_*.py` (58 tests for AI package)
  - `tests/core/test_database.py` (46 tests)
- pytest markers for test categorization: `unit`, `integration`, `slow`, `requires_db`, `requires_api`

#### CI/CD Pipeline with GitHub Actions
- **Unified CI workflow** (`.github/workflows/ci.yml`) with 5 jobs:
  - **Test Job**: Matrix testing across Python 3.8, 3.9, 3.10, 3.11
  - **Lint Job**: Black, isort, flake8 code quality checks
  - **Type Check Job**: mypy static analysis
  - **Build Job**: Package building with wheel validation
  - **CI Summary Job**: Aggregated results with GitHub Step Summary
- Automated artifact uploads (coverage reports, build artifacts)
- pip caching for faster builds
- System dependency installation for database drivers

#### Pre-commit Hooks for Code Quality
- **`.pre-commit-config.yaml`** with 10 hooks:
  - Built-in: trailing-whitespace, end-of-file-fixer, check-yaml, check-added-large-files, check-merge-conflict, debug-statements
  - Code quality: Black, isort, flake8, mypy
- Automatic code formatting on commit
- Integration with pyproject.toml configuration

#### Performance Benchmarks
- **benchmarks/performance_benchmark.py** - Comprehensive benchmark suite
- Baseline metrics established for all analyzers
- Linear O(n) scaling verified across 100-5,000 row datasets
- Performance documentation in `docs/PERFORMANCE.md`
- Optimization attempts documented with lessons learned

#### Security Audit with Bandit
- **Comprehensive security scan** using Bandit
- All 20 identified issues reviewed and addressed
- Security patterns validated:
  - SQL injection prevention via identifier validation
  - Parameterized queries for all dynamic values
  - No hardcoded credentials
  - Environment-based credential management
- Security scanning integrated into CI pipeline
- Detailed security documentation in `docs/SECURITY.md`

### Changed

#### Documentation Consolidation
- **23 documentation files → 3 core documents + archive**
- **Core documents:**
  - `README.md` - User-facing quick start and features
  - `docs/ARCHITECTURE.md` - Technical design and system overview
  - `docs/CONTRIBUTING.md` - Developer guide and workflow
- **Preserved:** ROADMAP.md, SECURITY.md, TESTING.md, AI_AGENT_INSTRUCTIONS.md
- **Archived:** 13 historical/analysis documents moved to `docs/archive/`
- All internal links verified and updated
- No information lost - all valuable content preserved

#### Migrated to pyproject.toml
- **Modern Python packaging** following PEP 621 standard
- Consolidated configuration from setup.py, pytest.ini, requirements.txt
- 29 core dependencies + 7 dev dependencies + 3 jupyter dependencies
- Tool configurations for pytest, black, isort, mypy, flake8, coverage
- CLI entry points: `business-analyzer`, `vanna-grok`, `vanna-chat`
- Optional dependency groups: `[dev]`, `[jupyter]`, `[all]`

#### Refactored AI Implementation
- **Consolidated vanna_chat.py into vanna_grok.py**
- Eliminated 60% code duplication between AI implementations
- Renamed `GrokVanna` class to `AIVanna` (provider-agnostic)
- Enhanced with multi-provider support while preserving production features
- All unique features from vanna_chat.py merged into vanna_grok.py
- Updated entry points in pyproject.toml and setup.py

### Removed

#### Deprecated Files
- **`src/vanna_chat.py`** - Consolidated into vanna_grok.py
  - 396 lines of redundant code removed
  - All functionality preserved in enhanced vanna_grok.py
  - Entry points updated to use vanna_grok.py

#### Duplicate Documentation
- **13 documentation files archived** (not deleted):
  - START_HERE.md → merged into README.md
  - VANNA_SETUP.md → merged into README.md/ARCHITECTURE.md
  - VANNA_COMPARISON.md → merged into README.md/ARCHITECTURE.md
  - VANNA_BEAUTIFUL_OUTPUT.md → merged into README.md
  - ANALYSIS_SUMMARY.md → historical analysis
  - IMPROVEMENT_ANALYSIS.md → historical analysis
  - QUICK_START_IMPROVEMENTS.md → merged into README.md
  - P0_FIXES_APPLIED.md → historical fixes documentation
  - REORGANIZATION_SUMMARY.md → historical reorganization notes
  - METABASE_TROUBLESHOOTING.md → merged into README.md
  - ANACONDA_TESTING.md → merged into CONTRIBUTING.md
  - GITHUB_ACTIONS_SETUP.md → merged into CONTRIBUTING.md
  - setup_instructions.md → merged into README.md

### Security

#### SQL Injection Prevention
- **`validate_sql_identifier()`** function for safe SQL identifier validation
- All table/column names validated before use in queries
- Parameterized queries for all dynamic values
- Comprehensive tests in `tests/test_sql_injection_prevention.py`

#### Security Scanning in CI
- **Bandit security scanner** integrated into GitHub Actions
- Scans all Python files on every push and PR
- Configured to catch hardcoded credentials, SQL injection, unsafe eval
- Security audit report added to `docs/SECURITY.md`

#### Credential Handling Improvements
- **No hardcoded credentials** in any source files
- Environment variable-based configuration via `.env` files
- Secure credential management for database connections
- Navicat password decryption for local NCX files only
- Credential masking in CI logs

### Migration Notes

#### For Users
1. Update your `.env` file to use new configuration format (optional - backward compatible)
2. Install with new command: `pip install -e ".[dev]"`
3. AI provider selection: Set `AI_PROVIDER=grok|openai|anthropic|ollama`

#### For Developers
1. Pre-commit hooks: `pip install pre-commit && pre-commit install`
2. Run tests: `pytest tests/ -v`
3. Code quality: `black src/ tests/ && isort src/ tests/ && flake8 src/ tests/`

### Statistics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Python Files | 35 | 43 | +8 |
| Test Files | 10 | 18 | +8 |
| Documentation Files | 23 | 7 active + 13 archived | -3 |
| Test Coverage | ~17% | ~54% | +37% |
| Lines of Code | 9,354 | ~11,000 | +1,646 |
| Average Module Size | 1,690 lines | ~84 lines | -95% |
| CI Jobs | 0 | 5 | +5 |
| Security Issues | 20 | 0 | -20 |

### Contributors

This release represents the work of the Business Data Analyzer Team with contributions from:
- Claude (AI Assistant) - Architecture design, modularization, testing
- GitHub Copilot - Code review, security fixes, workflow improvements

---

## [1.0.0] - 2025-01-XX

### Added
- Initial release of Business Data Analyzer
- AI-powered natural language SQL queries via Vanna
- Business metrics calculation (financial, customer, product)
- Visualization reports with matplotlib
- Streamlit dashboard interface
- Database connectivity via pymssql and pyodbc
- Basic test suite
- Initial documentation

[2.1.0]: https://github.com/Trujillofa/depotru_database/releases/tag/v2.1.0
[2.0.0]: https://github.com/Trujillofa/coding_omarchy/releases/tag/v2.0.0
[1.0.0]: https://github.com/Trujillofa/coding_omarchy/releases/tag/v1.0.0
