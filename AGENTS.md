# AGENTS.md — Business Data Analyzer

> Compact instruction file for OpenCode sessions. Every line answers: "Would an agent likely miss this without help?"

---

## Project Essence

**Business Intelligence platform for Colombian hardware store operations.**
- AI natural language → SQL (Vanna AI with Grok/OpenAI/Claude/Ollama)
- Colombian number formatting: `$1.234.567,89` and `45,6%`
- Database: SmartBusiness MSSQL (`banco_datos` table)
- **CRITICAL**: Always exclude test docs in SQL: `WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')`

---

## Quick Commands

```bash
# Install (development mode)
pip install -e ".[dev]"

# Run AI chat interface
python src/vanna_grok.py        # → http://localhost:8084

# Run tests
pytest tests/ -v                # All tests
pytest tests/test_basic.py -v   # Quick tests (no deps required)
pytest -m "not requires_db and not requires_api"  # CI-safe tests

# Code quality
black src/ tests/               # Format (88 char line length)
isort src/ tests/               # Sort imports
flake8 src/ tests/              # Lint
mypy src/                       # Type check (ignore_errors on many modules)
pre-commit run --all-files      # Run all hooks
```

---

## Project Structure

```
src/
├── vanna_grok.py               # Main AI chat entry point (Flask + Waitress)
├── api.py                      # REST API endpoints
├── business_analyzer/            # Modular package (preferred)
│   ├── core/                   # config.py, database.py, validation.py
│   ├── analysis/               # customer.py, financial.py, product.py, inventory.py, unified.py
│   └── ai/                     # base.py, formatting.py, providers/{grok,openai,anthropic,ollama}.py
├── business_analyzer_combined.py  # LEGACY monolithic analyzer (deprecated, don't extend)
└── config.py                   # LEGACY config (deprecated)
```

**Rule**: Use `business_analyzer/` modular package for new code. Legacy files are frozen.

---

## Environment & Configuration

```bash
# Copy template, fill in real values
cp .env.example .env            # NEVER commit .env
```

**Required env vars:**
- `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` (or use `NCX_FILE_PATH` for Navicat)
- One AI provider key: `GROK_API_KEY`, `OPENAI_API_KEY`, or `ANTHROPIC_API_KEY`

**Key config patterns:**
```python
# Use require_env() for required values
from business_analyzer.core.config import require_env
API_KEY = require_env("GROK_API_KEY")  # Raises if missing

# Use os.getenv() with defaults for optional
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "~/business_reports")
```

---

## Code Quality Standards

| Tool | Config | Notes |
|------|--------|-------|
| **black** | 88 char line | `target-version = ['py39', 'py310', 'py311']` |
| **isort** | black profile | `known_first_party = ["src"]` |
| **flake8** | 88 char, via pyproject | Excludes: `E203, W503` (conflict with black) |
| **mypy** | python 3.9 | Many modules have `ignore_errors = true` (legacy) |
| **pytest** | pythonpath=src | Markers: `unit`, `integration`, `slow`, `requires_db`, `requires_api` |

**Pre-commit hooks** (configured in `.pre-commit-config.yaml`):
```bash
pre-commit install              # One-time setup
pre-commit run --all-files      # Manual run
```

---

## Testing Strategy

**Test markers:**
- `unit` — Fast, no external deps
- `integration` — Requires database
- `requires_db` — Needs real SQL Server connection
- `requires_api` — Needs AI provider API key
- `slow` — Long-running tests

**CI runs:**
```bash
pytest -m "not requires_db and not requires_api"  # Safe for CI
```

**Coverage targets:**
- `vanna_grok.py`: 85%
- `business_analyzer_combined.py`: 80%
- Overall: 80%

---

## CI/CD Pipeline

GitHub Actions (`.github/workflows/ci.yml`):
1. **test** — Python 3.9, 3.10, 3.11 (excludes DB/API tests)
2. **lint** — black, isort, flake8 (some files excluded)
3. **type-check** — mypy on subset of files
4. **security-scan** — bandit (fails on HIGH severity)
5. **build** — Package build + twine check

**Note**: Some files are excluded from strict linting in CI:
- `src/business_analyzer/ai/training.py`
- `src/business_analyzer/analysis/customer_optimized.py`
- `tests/ai/test_stability.py`, `tests/test_metabase_connection.py`

---

## Critical Business Rules

### 1. Always Exclude Test Documents
```sql
-- NEVER forget this WHERE clause
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
```

### 2. Use Colombian Number Formatting
```python
from business_analyzer.ai.formatting import format_number

# Currency: $1.234.567,89
format_number(1234567.89, "TotalMasIva")  # → "$1.234.568"

# Percentage: 45,6%
format_number(45.6, "Margen")             # → "45,6%"
```

### 3. Language Convention
- **Code/docs**: English
- **User-facing text**: Spanish (Colombian)
- **Database content**: Spanish field names (`TercerosNombres`, `ArticulosNombre`)

---

## Database Schema (banco_datos)

```sql
CREATE TABLE banco_datos (
    Fecha DATE,                     -- Transaction date
    TotalMasIva DECIMAL(18,2),      -- Revenue WITH tax (IVA)
    TotalSinIva DECIMAL(18,2),      -- Revenue WITHOUT tax
    ValorCosto DECIMAL(18,2),       -- Cost
    Cantidad INT,                   -- Quantity sold
    TercerosNombres NVARCHAR(200),  -- Customer name
    ArticulosNombre NVARCHAR(200),  -- Product name
    categoria NVARCHAR(100),        -- Category
    subcategoria NVARCHAR(100),    -- Subcategory
    DocumentosCodigo NVARCHAR(10)   -- Document type (exclude XY, AS, TS)
);
```

---

## Common Translations (Colombian Spanish)

| English | Spanish |
|---------|---------|
| Revenue | Facturación / Ingresos |
| Profit | Ganancia |
| Margin | Margen |
| Cost | Costo |
| Customer | Cliente |
| Product | Producto / Artículo |
| Category | Categoría |

---

## AI Provider Configuration

```bash
# Choose provider (default: grok)
export AI_PROVIDER=grok           # or: openai, anthropic, ollama

# Set corresponding API key
export GROK_API_KEY=xai-your-key
export OPENAI_API_KEY=sk-your-key
export ANTHROPIC_API_KEY=sk-ant-your-key
```

---

## Security Rules

1. **NEVER hardcode credentials** — Use `require_env()` or `os.getenv()`
2. **NEVER commit `.env`** — Already in `.gitignore`
3. **Bandit exclusions**: `B608` (hardcoded passwords), `B314` (XML parsing)
4. Always use parameterized queries (pymssql/pyodbc)

---

## Existing Instruction Files

- `.agents/claude/CLAUDE.md` — Agent-specific guidelines
- `docs/CONTRIBUTING.md` — Full developer guide
- `docs/ARCHITECTURE.md` — System design
- `docs/AI_AGENT_INSTRUCTIONS.md` — AI development guide
- `docs/SECURITY.md` — Security guidelines
- `docs/TESTING.md` — Testing guide

---

## Quick Reference

```python
# Retry decorator for API calls
from business_analyzer.ai.base import retry_on_failure

# Safe division (avoid ZeroDivisionError)
def safe_divide(n, d, default=0.0):
    return n / d if d != 0 else default

# Run the app
if __name__ == "__main__":
    python src/vanna_grok.py    # Development
    # Production uses Waitress automatically
```

---

**Last updated**: Generated from repository analysis (CI config, pyproject.toml, CONTRIBUTING.md, ARCHITECTURE.md)
