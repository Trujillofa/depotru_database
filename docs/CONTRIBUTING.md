# Contributing to Business Data Analyzer

> **Development guide for contributors, maintainers, and AI agents.**

Thank you for considering contributing! This document covers setup, workflow, coding standards, and best practices.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Workflow](#development-workflow)
3. [Code Style](#code-style)
4. [Testing](#testing)
5. [Security](#security)
6. [Git Workflow](#git-workflow)
7. [Documentation](#documentation)
8. [AI Agent Guidelines](#ai-agent-guidelines)
9. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- ODBC driver for SQL Server (for database features)

### Setup

```bash
# 1. Fork and clone the repository
git clone https://github.com/YOUR_USERNAME/depotru_database.git
cd depotru_database

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install development dependencies
pip install black flake8 mypy isort pytest pytest-cov

# 5. Install pre-commit hooks (optional but recommended)
pip install pre-commit
pre-commit install

# 6. Configure environment
cp .env.example .env
# Edit .env with your credentials (never commit this file)

# 7. Verify setup
python run_tests.py --quick
```

---

## Development Workflow

### 1. Create a Branch

```bash
# Create and switch to a new branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/bug-description
```

**Branch naming conventions:**
- `feature/description` — New features
- `fix/description` — Bug fixes
- `docs/description` — Documentation updates
- `refactor/description` — Code refactoring

### 2. Make Your Changes

- Write clean, readable code
- Follow [code style guidelines](#code-style)
- Add docstrings to functions and classes
- Update documentation if needed

### 3. Test Your Changes

```bash
# Run tests
python run_tests.py

# Run with coverage
python run_tests.py --cov

# Format code
black src/ tests/ examples/

# Check style
flake8 src/ tests/

# Type check
mypy src/
```

### 4. Run Pre-commit Hooks (Optional)

If you installed pre-commit hooks, they will run automatically on commit. To run them manually:

```bash
# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black

# Skip hooks for a specific commit (not recommended)
git commit -m "message" --no-verify
```

**Pre-commit hooks include:**
- **Trailing whitespace** - Removes trailing whitespace
- **End of file fixer** - Ensures files end with a newline
- **Black** - Code formatting
- **isort** - Import sorting
- **flake8** - Linting
- **mypy** - Type checking

### 5. Commit Your Changes

```bash
git add .
git commit -m "type: description

Detailed explanation of changes"
```

**Commit message types:**
- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation changes
- `style:` — Code style changes (formatting)
- `refactor:` — Code refactoring
- `test:` — Adding or updating tests
- `chore:` — Maintenance tasks

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub with:
- Clear description of changes
- Reference to related issues
- Test results

---

## Code Style

### Python Style Guide

We follow PEP 8 with these specifics:

- **Line length**: 88 characters (Black default)
- **Quotes**: Double quotes for strings
- **Imports**: Sorted with isort (standard library, third-party, local)
- **Type hints**: Required for function parameters and return values

### Code Formatting

```bash
# Format all code
black src/ tests/ examples/

# Sort imports
isort src/ tests/ examples/

# Check style
flake8 src/ tests/ --max-line-length=88
```

### Type Hints

```python
from typing import Optional, List, Dict, Any

def calculate_metrics(
    data: List[Dict[str, Any]],
    limit: Optional[int] = None
) -> Dict[str, float]:
    """Calculate business metrics from data.

    Args:
        data: List of dictionaries containing business data
        limit: Optional limit on number of records to process

    Returns:
        Dictionary with calculated metrics
    """
    # Implementation
    pass
```

### Docstrings

All functions must have docstrings:

```python
def format_number(value: float, column_name: str) -> str:
    """Format number with Colombian formatting.

    Args:
        value: Number to format
        column_name: Name of column (used to determine format type)

    Returns:
        Formatted string (e.g., "$1.234.567" or "45,6%")

    Examples:
        >>> format_number(1234567, "TotalMasIva")
        '$1.234.567'

        >>> format_number(45.6, "Margen")
        '45,6%'
    """
    # Implementation
    pass
```

---

## Testing

### Running Tests

```bash
# Run all tests
python run_tests.py

# Run quick tests (no dependencies required)
python run_tests.py --quick

# Run with coverage
python run_tests.py --cov

# Using pytest directly
pytest tests/ -v

# Run specific test file
pytest tests/test_formatting.py -v

# Run specific test
pytest tests/test_formatting.py::test_format_number_currency -v
```

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── test_basic.py            # Basic tests (no dependencies)
├── test_business_metrics.py # Business logic tests
├── test_formatting.py       # Number formatting tests
└── test_metabase_connection.py  # Database tests
```

### Writing Tests

```python
import pytest

def test_format_number_currency_returns_colombian_format():
    """Test that currency values use Colombian peso format."""
    result = format_number(1234567, "TotalMasIva")
    assert result == "$1.234.567"

def test_format_number_null_returns_dash():
    """Test that None values return dash placeholder."""
    result = format_number(None, "TotalMasIva")
    assert result == "-"

@pytest.mark.skipif(not HAS_PYMSSQL, reason="pymssql not installed")
def test_database_connection():
    """Test database connection (skipped if pymssql unavailable)."""
    # Test implementation
    pass
```

### Test Coverage Goals

| Component | Minimum Coverage |
|-----------|-----------------|
| src/vanna_grok.py | 85% |
| src/business_analyzer_combined.py | 80% |
| src/config.py | 90% |
| **Overall** | **80%** |

---

## Security

### Never Commit Credentials

```python
# ❌ NEVER DO THIS
DB_PASSWORD = "MySecret123"
API_KEY = "xai-1234567890"

# ✅ ALWAYS DO THIS
DB_PASSWORD = os.getenv("DB_PASSWORD")
API_KEY = require_env("GROK_API_KEY")
```

### Environment Variables

When adding new configuration:

1. **Add to `.env.example`** (with dummy value):
   ```bash
   NEW_FEATURE_API_KEY=your-key-here
   ```

2. **Use `require_env()` for required values**:
   ```python
   class Config:
       NEW_KEY = require_env("NEW_FEATURE_API_KEY")
   ```

3. **Provide defaults for optional values**:
   ```python
   class Config:
       FEATURE_ENABLED = os.getenv("FEATURE_ENABLED", "true").lower() == "true"
   ```

### Security Scanning

All code is automatically scanned by:
- **CodeQL** (GitHub Security)
- **Bandit** (Python security linter)
- **Safety** (dependency vulnerabilities)

Fix any issues before merging!

---

## Git Workflow

### Commit Message Format

```
<type>: <short summary (50 chars max)>

<detailed description (wrap at 72 chars)>

<optional: reference issues, breaking changes, etc.>
```

**Examples:**
```
feat: Add automatic profit margin alerts

- Implement threshold-based alerting system
- Add email notification support
- Include tests for alert triggers

Closes #123
```

```
fix: Handle zero division in margin calculation

- Add safe_divide() wrapper function
- Return 0.0 when revenue is zero
- Add test cases for edge cases

Fixes #456
```

### Pre-Commit Checklist

Before committing:

- [ ] Code runs without errors
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Code formatted: `black src/ tests/` (or use pre-commit)
- [ ] No flake8 errors: `flake8 src/ tests/` (or use pre-commit)
- [ ] Type hints added for new functions
- [ ] Docstrings added/updated
- [ ] No hardcoded credentials
- [ ] Tests added for new features
- [ ] Documentation updated
- [ ] `.env` file NOT committed
- [ ] Pre-commit hooks pass: `pre-commit run --all-files` (if installed)

---

## Documentation

### When to Update Documentation

Update these files when making changes:

| Change Type | Update Files |
|-------------|-------------|
| New feature | README.md, ARCHITECTURE.md, ROADMAP.md |
| Bug fix | Commit message, CHANGELOG.md (if exists) |
| Configuration | .env.example, ARCHITECTURE.md |
| API change | All affected documentation |
| New dependency | requirements.txt, pyproject.toml, README.md |

### Documentation Standards

- Use clear, concise language
- Include code examples
- Keep examples runnable
- Use proper Markdown formatting

---

## AI Agent Guidelines

This section is for AI agents working on the project.

### Project Context

- **Business**: Colombian hardware store (ferretería)
- **Language**: Spanish for user messages, English for code/docs
- **Database**: SmartBusiness MSSQL with `banco_datos` table
- **Formatting**: Colombian pesos ($1.234.567), percentages (45,6%)

### Key Patterns

```python
# Pattern 1: Retry with exponential backoff
@retry_on_failure(max_attempts=3, delay=2)
def api_call():
    # Implementation

# Pattern 2: Environment variable validation
config_value = require_env("VAR_NAME")

# Pattern 3: Colombian number formatting
formatted = format_number(value, column_name)

# Pattern 4: Safe division
def safe_divide(numerator, denominator, default=0.0):
    return numerator / denominator if denominator != 0 else default
```

### Critical Rules

1. **Security First**: Never hardcode credentials
2. **Colombian Format**: Use `format_number()` for all display values
3. **Spanish Language**: All user-facing text in Spanish
4. **Error Handling**: Use `retry_on_failure` for API calls
5. **Testing**: Add tests for every new feature
6. **Documentation**: Update docs with every change

### Database Schema

```sql
CREATE TABLE banco_datos (
    Fecha DATE,                     -- Transaction date
    TotalMasIva DECIMAL(18,2),      -- Total with tax
    TotalSinIva DECIMAL(18,2),      -- Total without tax
    ValorCosto DECIMAL(18,2),       -- Cost
    Cantidad INT,                   -- Quantity sold
    TercerosNombres NVARCHAR(200),  -- Customer name
    ArticulosNombre NVARCHAR(200),  -- Product name
    categoria NVARCHAR(100),        -- Category
    subcategoria NVARCHAR(100)      -- Subcategory
);
```

**CRITICAL RULE**: Always exclude test documents:
```sql
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
```

### Common Translations

| English | Spanish (Colombian) |
|---------|-------------------|
| Revenue | Facturación / Ingresos |
| Profit | Ganancia |
| Margin | Margen |
| Cost | Costo |
| Customer | Cliente |
| Product | Producto / Artículo |
| Category | Categoría |
| Error | Error |
| Success | Éxito |
| Loading | Cargando |
| Results | Resultados |

---

## Troubleshooting

### Common Issues

#### "No module named 'pymssql'"

Tests requiring pymssql will be automatically skipped. To run all tests:

```bash
pip install pymssql
# Or install all dependencies:
pip install -r requirements.txt
```

#### Tests pass locally but fail in CI

CI doesn't have `.env` file. Tests should mock environment variables:

```python
import os
from unittest.mock import patch

@patch.dict(os.environ, {"DB_SERVER": "test-server"})
def test_with_env():
    # Test implementation
    pass
```

#### Database connection failed

```bash
# Check ODBC driver
odbcinst -j

# Install if missing (Ubuntu/Debian)
sudo apt install unixodbc-dev msodbcsql17

# Test connection
python tests/test_metabase_connection.py
```

#### Code formatting issues

```bash
# Auto-format all code
black src/ tests/ examples/
isort src/ tests/ examples/
```

#### Pre-commit hook failures

If pre-commit hooks fail during commit:

```bash
# Run hooks manually to see detailed errors
pre-commit run --all-files

# Fix specific hook
pre-commit run black
pre-commit run flake8

# Skip hooks temporarily (not recommended for production)
git commit -m "message" --no-verify

# Update hooks to latest versions
pre-commit autoupdate
```

**Common pre-commit issues:**
- **Black formatting**: Run `black src/ tests/` to auto-fix
- **isort imports**: Run `isort src/ tests/` to auto-fix
- **flake8 errors**: Fix manually or adjust line length
- **mypy type errors**: Add type hints or ignore with `# type: ignore`

---

## Resources

- [Python Best Practices](https://docs.python-guide.org/)
- [Vanna AI Documentation](https://vanna.ai/docs/)
- [pytest Documentation](https://docs.pytest.org/)
- [Black Code Style](https://black.readthedocs.io/)

---

## Questions?

- Open a discussion on GitHub
- Check existing documentation
- Ask in pull request comments

---

**Thank you for contributing!** 🎉
