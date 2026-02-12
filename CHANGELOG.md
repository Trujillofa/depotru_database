# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[2.0.0]: https://github.com/Trujillofa/coding_omarchy/releases/tag/v2.0.0
[1.0.0]: https://github.com/Trujillofa/coding_omarchy/releases/tag/v1.0.0
