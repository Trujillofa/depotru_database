# AI Agent Instructions - Business Data Analyzer Project

## 📋 Overview

You are an AI agent working on a **Business Intelligence platform for a Colombian hardware store**. The project combines traditional Python data analysis with AI-powered natural language SQL queries using **Vanna AI + Grok (xAI)**.

**Primary Technologies:**
- Python 3.8-3.11
- MSSQL Server (SmartBusiness database)
- Vanna AI 2.0.1 (legacy, stable)
- Grok API (xAI) for natural language → SQL
- Flask/Waitress web servers
- Pandas for data manipulation
- ChromaDB for vector storage (RAG)

**Your Mission:**
Develop, debug, refactor, and fix code while maintaining production stability, security, and Colombian business context (Spanish language, peso formatting, local conventions).

---

## 🎯 Core Responsibilities

### 1. **Developing New Features**
- Implement features from `docs/ROADMAP.md` (currently on Path A → Path B)
- Maintain backward compatibility with Vanna 2.0.1 legacy APIs
- Ensure all new code works across Python 3.8-3.11
- Add tests for every new feature
- Update documentation immediately

### 2. **Debugging Issues**
- Prioritize security and data correctness bugs
- Reproduce issues locally before fixing
- Add regression tests to prevent recurrence
- Document root cause and fix in commit messages

### 3. **Refactoring Code**
- Improve code quality without changing behavior
- Extract duplicated logic into reusable functions
- Maintain Colombian formatting standards
- Never sacrifice readability for brevity

### 4. **Fixing Bugs**
- Classify severity: P0 (critical), P1 (high), P2 (medium), P3 (low)
- Fix P0 bugs immediately
- Include before/after examples in commits
- Update related tests

---

## 🏗️ Project Architecture

### Directory Structure

```
coding_omarchy/
├── src/                          # Source code (Python modules)
│   ├── vanna_grok.py            # 🔥 MAIN APP - Natural language SQL (multi-provider)
│   ├── business_analyzer_combined.py  # Traditional analytics
│   ├── config.py                # Configuration management
│   └── utils/                   # Utility functions
│
├── tests/                       # Test suite (pytest)
│   ├── test_config.py          # Environment validation
│   ├── test_formatting.py      # Colombian number formatting
│   ├── test_error_handling.py  # Retry logic, security
│   └── test_business_metrics.py # Business calculations
│
├── docs/                        # Documentation
│   ├── START_HERE.md           # Entry point for new users
│   ├── ROADMAP.md              # Development roadmap (4 paths)
│   ├── VANNA_SETUP.md          # Vanna AI configuration
│   ├── ANACONDA_TESTING.md     # Multi-version Python testing
│   └── AI_AGENT_INSTRUCTIONS.md # THIS FILE
│
├── examples/                    # Working examples
│   ├── improvements_p0.py      # P0 fixes demonstration
│   └── streamlit_dashboard.py  # Interactive dashboard
│
├── data/                        # Data files
│   └── sample_data/            # Test data (never commit real data!)
│
├── .github/workflows/          # CI/CD automation
│   ├── python-package-conda.yml  # Multi-version testing
│   ├── codeql-analysis.yml      # Security scanning
│   └── dependency-review.yml    # Vulnerability checks
│
├── .env.example                # Template for environment variables
├── requirements.txt            # Python dependencies
├── environment.yml             # Conda environment spec
├── setup.py                    # Package configuration
└── README.md                   # Project overview
```

### Key Files (Priority Order)

| File | Purpose | Modify Frequency |
|------|---------|-----------------|
| **src/vanna_grok.py** | Main production app | High - Core feature development |
| **tests/*.py** | Test suite | High - Add tests for every change |
| **docs/ROADMAP.md** | Development plan | Medium - Update after milestones |
| **README.md** | User-facing docs | Medium - Update for major features |
| **setup.py** | Package config | Low - Only for new dependencies |
| **.env.example** | Config template | Low - Only for new env vars |

---

## 🔧 Development Workflow

### Step 1: Understand the Task

Before writing any code:

1. **Read related documentation**
   ```bash
   # Start here
   cat docs/START_HERE.md
   cat docs/ROADMAP.md  # Check current phase
   ```

2. **Check for existing implementations**
   ```bash
   # Search codebase
   grep -r "feature_name" src/
   git log --all --grep="related keyword"
   ```

3. **Understand business context**
   - This is a Colombian hardware store (ferretería)
   - Outputs must be in Spanish
   - Numbers use Colombian format: $1.234.567 (pesos), 45,6% (percentages)
   - Database: SmartBusiness MSSQL with `banco_datos` table

### Step 2: Plan the Implementation

1. **Check ROADMAP.md for alignment**
   - Are you working on the current phase?
   - Does this fit the project priorities?

2. **Identify affected files**
   ```bash
   # Example: Adding a new metric
   # Affected: src/vanna_grok.py (training examples)
   #           tests/test_business_metrics.py (tests)
   #           docs/VANNA_BEAUTIFUL_OUTPUT.md (examples)
   ```

3. **Design with these principles**
   - **Security First**: Never hardcode credentials
   - **Colombian Format**: Use existing `format_number()` function
   - **Error Handling**: Use `retry_on_failure` decorator for API calls
   - **Resource Efficiency**: Reuse shared clients (e.g., grok_client)
   - **Testability**: Write pure functions when possible

### Step 3: Implement Changes

#### For New Features

```python
# Template for new feature in vanna_grok.py

from functools import wraps
from typing import Optional, Dict, Any
import pandas as pd

@retry_on_failure(max_attempts=3, delay=2)
def new_feature_function(
    param1: str,
    param2: int,
    grok_client: OpenAI
) -> Optional[Dict[str, Any]]:
    """
    Brief description of what this does.

    Args:
        param1: Description
        param2: Description
        grok_client: Shared Grok client (reuse, don't create new)

    Returns:
        Dict with results or None on failure

    Example:
        >>> result = new_feature_function("test", 42, client)
        >>> print(result['metric'])
        $1.234.567
    """
    try:
        # 1. Validate inputs
        if not param1:
            raise ValueError("param1 required")

        # 2. Process
        result = some_calculation(param1, param2)

        # 3. Format Colombian numbers
        formatted = format_number(result, "TotalMasIva")

        # 4. Return structured data
        return {
            'metric': formatted,
            'raw_value': result,
            'timestamp': pd.Timestamp.now()
        }

    except Exception as e:
        print(f"⚠️ Error in new_feature_function: {e}")
        return None
```

#### For Bug Fixes

```python
# Before (buggy):
def calculate_margin(revenue, cost):
    return (revenue - cost) / revenue  # ZeroDivisionError!

# After (fixed):
def calculate_margin(revenue: float, cost: float) -> float:
    """
    Calculate profit margin as percentage.

    Args:
        revenue: Total revenue (TotalSinIva)
        cost: Total cost (ValorCosto)

    Returns:
        Margin percentage (0-100)

    Example:
        >>> calculate_margin(1000, 600)
        40.0
    """
    if revenue <= 0:
        return 0.0  # Avoid division by zero

    margin = ((revenue - cost) / revenue) * 100
    return max(0.0, margin)  # Never return negative
```

### Step 4: Test Thoroughly

```bash
# 1. Run all tests
pytest tests/ -v

# 2. Run specific test file
pytest tests/test_formatting.py -v

# 3. Run with coverage
pytest tests/ --cov=src --cov-report=html

# 4. Test on multiple Python versions (if major change)
conda create -n test-py310 python=3.10 -y
conda activate test-py310
pip install -r requirements.txt
pytest tests/ -v
```

**Always add tests for new features:**

```python
# tests/test_new_feature.py
import pytest
from src.vanna_grok import new_feature_function
from unittest.mock import Mock

def test_new_feature_success():
    """Test successful execution"""
    mock_client = Mock()
    result = new_feature_function("valid", 42, mock_client)

    assert result is not None
    assert 'metric' in result
    assert 'raw_value' in result

def test_new_feature_handles_empty_input():
    """Test error handling for empty input"""
    mock_client = Mock()
    result = new_feature_function("", 42, mock_client)

    assert result is None  # Should handle gracefully

def test_new_feature_formats_colombian_pesos():
    """Test Colombian number formatting"""
    mock_client = Mock()
    result = new_feature_function("test", 1234567, mock_client)

    assert result['metric'] == "$1.234.567"
```

### Step 5: Update Documentation

**For every feature/fix, update:**

1. **Code comments** (docstrings)
2. **README.md** (if user-facing)
3. **Relevant docs/** files
4. **Commit message** (detailed)

Example commit message:

```
feat: Add profit margin validation to prevent negative values

Problem:
- calculate_margin() could return negative percentages
- Division by zero crash when revenue = 0
- No validation on input values

Solution:
- Add zero-revenue check (return 0.0)
- Use max(0.0, margin) to prevent negatives
- Add type hints and docstring
- Handle edge cases gracefully

Tests:
- test_calculate_margin_zero_revenue()
- test_calculate_margin_negative_cost()
- test_calculate_margin_normal_case()

Related: src/vanna_grok.py:487, tests/test_business_metrics.py:123
```

### Step 6: Commit and Push

```bash
# 1. Stage changes
git add src/vanna_grok.py tests/test_new_feature.py docs/ROADMAP.md

# 2. Check what's staged
git diff --cached

# 3. Commit with descriptive message
git commit -m "feat: Add new feature with tests and docs

- Implement new_feature_function with retry logic
- Add 5 test cases covering edge cases
- Update ROADMAP.md to mark feature complete
- Ensure Colombian number formatting

Tests: ✅ All passing (pytest tests/ -v)
Coverage: 92% → 94%"

# 4. Push to feature branch
git push -u origin claude/feature-name-SessionID
```

---

## 🔐 Security Requirements

### **CRITICAL: Never Commit Secrets**

```bash
# ❌ NEVER DO THIS
DB_PASSWORD = "MySecret123"
api_key = "xai-1234567890"

# ✅ ALWAYS DO THIS
DB_PASSWORD = require_env("DB_PASSWORD")
api_key = require_env("GROK_API_KEY", validation_func=lambda x: x.startswith("xai-"))
```

### Environment Variables Checklist

When adding new configuration:

1. **Add to .env.example** (with dummy value)
   ```bash
   # .env.example
   NEW_FEATURE_API_KEY=your-key-here
   ```

2. **Use require_env() for required values**
   ```python
   class Config:
       NEW_KEY = require_env("NEW_FEATURE_API_KEY")
   ```

3. **Provide defaults for optional values**
   ```python
   class Config:
       FEATURE_ENABLED = os.getenv("FEATURE_ENABLED", "true").lower() == "true"
   ```

4. **Update docs/VANNA_SETUP.md** with setup instructions

### Security Scanning

All code is automatically scanned by:
- **CodeQL** (GitHub Security)
- **Bandit** (Python security linter)
- **Safety** (dependency vulnerabilities)

Fix any issues before merging!

---

## 🇨🇴 Colombian Business Context

### Number Formatting Standards

```python
# ALWAYS use format_number() for display

# Currency (Colombian Pesos)
format_number(1234567.89, "TotalMasIva")  # → "$1.234.568"
format_number(50000, "Precio")            # → "$50.000"

# Percentages (Spanish format: comma for decimal)
format_number(45.6, "Margen_Promedio_Pct")  # → "45,6%"
format_number(100.0, "margin_pct")          # → "100,0%"

# Quantities (thousands separator)
format_number(1234, "Cantidad")  # → "1.234"
format_number(5678, "Units")     # → "5.678"

# Null values
format_number(None, "TotalMasIva")  # → "-"
format_number(pd.NA, "Revenue")     # → "-"
```

### Spanish Language Requirements

All user-facing text must be in Spanish:

```python
# ❌ English
print("Error: Database connection failed")
print("Processing 1000 records...")

# ✅ Spanish (Colombian)
print("❌ Error: Conexión a base de datos falló")
print("📊 Procesando 1.000 registros...")
```

**Common translations:**

| English | Spanish (Colombian) |
|---------|-------------------|
| Revenue | Facturación / Ingresos |
| Profit | Ganancia |
| Margin | Margen |
| Cost | Costo |
| Customer | Cliente |
| Product | Producto / Artículo |
| Category | Categoría |
| Total | Total |
| Error | Error |
| Success | Éxito |
| Loading | Cargando |
| Results | Resultados |

### Database Schema (SmartBusiness)

The `banco_datos` table structure:

```sql
CREATE TABLE banco_datos (
    Fecha DATE,                     -- Transaction date
    TotalMasIva DECIMAL(18,2),      -- Total with tax
    TotalSinIva DECIMAL(18,2),      -- Total without tax
    ValorCosto DECIMAL(18,2),       -- Cost
    Cantidad INT,                   -- Quantity sold
    TercerosNombres NVARCHAR(200),  -- Customer name
    ArticulosNombre NVARCHAR(200),  -- Product name
    ArticulosCodigo NVARCHAR(50),   -- Product code
    DocumentosCodigo NVARCHAR(10),  -- Document type
    categoria NVARCHAR(100),        -- Category
    subcategoria NVARCHAR(100)      -- Subcategory
);
```

**CRITICAL RULE:** Always exclude test documents:
```sql
WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')
```

### Common Business Metrics

```python
# Revenue
revenue = df['TotalMasIva'].sum()

# Net Revenue (without tax)
net_revenue = df['TotalSinIva'].sum()

# Profit
profit = df['TotalSinIva'].sum() - df['ValorCosto'].sum()

# Margin %
margin = ((df['TotalSinIva'] - df['ValorCosto']) / df['TotalSinIva'] * 100).mean()

# Tax (IVA)
tax = df['TotalMasIva'].sum() - df['TotalSinIva'].sum()

# Average ticket
avg_ticket = df.groupby('DocumentosCodigo')['TotalMasIva'].sum().mean()
```

---

## 🐛 Debugging Strategies

### Common Issues and Solutions

#### Issue 1: Database Connection Failed

```python
# Symptom
❌ MSSQL connection failed: Login failed for user 'sa'

# Debug steps:
1. Check .env file exists and has correct credentials
   cat .env | grep DB_

2. Test connection manually
   sqlcmd -S $DB_SERVER -U $DB_USER -P $DB_PASSWORD -d $DB_NAME -Q "SELECT 1"

3. Verify ODBC driver installed
   odbcinst -j

4. Check firewall/network
   telnet $DB_SERVER 1433

# Common fixes:
- Install ODBC driver: sudo apt install msodbcsql17
- Enable TCP/IP in SQL Server Configuration Manager
- Add firewall rule for port 1433
- Use TrustServerCertificate=yes in connection string
```

#### Issue 2: Grok API Errors

```python
# Symptom
⚠️ Intento 1/3 falló: 401 Unauthorized

# Debug steps:
1. Verify API key format
   echo $GROK_API_KEY | grep "^xai-"

2. Test API key manually
   curl -H "Authorization: Bearer $GROK_API_KEY" https://api.x.ai/v1/models

3. Check rate limits
   # Grok has rate limits - wait 1 minute and retry

# Common fixes:
- Regenerate API key at https://console.x.ai/
- Ensure GROK_API_KEY in .env starts with "xai-"
- Add retry_on_failure decorator to API calls
- Implement exponential backoff (already done in vanna_grok.py)
```

#### Issue 3: Number Formatting Issues

```python
# Symptom
Expected: "$1.234.567"
Got: "$1,234,567"

# Debug steps:
1. Check locale settings
   locale | grep LC_

2. Verify format_number() is being used
   grep -n "format_number" src/vanna_grok.py

3. Test formatting directly
   python -c "from src.vanna_grok import format_number; print(format_number(1234567, 'TotalMasIva'))"

# Fix:
- Always use format_number() from vanna_grok.py
- Never use locale.currency() or f"{value:,}" directly
- Add column name to format_number() for correct detection
```

#### Issue 4: Tests Failing in CI but Passing Locally

```python
# Symptom
✅ Local: pytest tests/ -v → All pass
❌ GitHub Actions: tests/test_config.py::test_environment_variables_loaded FAILED

# Debug steps:
1. Check if test depends on .env file
   # CI doesn't have .env, uses environment variables

2. Review workflow file
   cat .github/workflows/python-package-conda.yml | grep -A 10 "env:"

3. Add dummy values to CI
   # In .github/workflows/python-package-conda.yml:
   env:
     DB_SERVER: "test-server"
     GROK_API_KEY: "xai-test-key-for-ci"

# Fix:
- Mock environment variables in tests
- Use @patch.dict(os.environ, {...}) for tests requiring env vars
- Don't commit .env file to git (already in .gitignore)
```

### Debugging Tools

```bash
# Python debugger (pdb)
python -m pdb src/vanna_grok.py

# Print debugging (temporary only!)
print(f"DEBUG: variable={variable}, type={type(variable)}")

# Logging (preferred for production)
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug(f"Processing {len(df)} rows")

# Profile performance
python -m cProfile -s cumtime src/vanna_grok.py > profile.txt

# Memory profiling
pip install memory_profiler
python -m memory_profiler src/vanna_grok.py
```

---

## ♻️ Refactoring Guidelines

### When to Refactor

**DO refactor when:**
- ✅ Duplicated code appears 3+ times
- ✅ Function exceeds 50 lines
- ✅ Cyclomatic complexity > 10
- ✅ Test coverage < 80%
- ✅ Code violates project standards

**DON'T refactor when:**
- ❌ It would break existing functionality
- ❌ No tests exist (write tests first!)
- ❌ You don't understand the code fully
- ❌ It's a minor style preference

### Refactoring Patterns

#### Pattern 1: Extract Function

```python
# Before (duplicated code)
def process_sales():
    df = df[df['DocumentosCodigo'].isin(['XY', 'AS', 'TS']) == False]
    # ... processing

def process_inventory():
    df = df[df['DocumentosCodigo'].isin(['XY', 'AS', 'TS']) == False]
    # ... processing

# After (extracted to reusable function)
def filter_valid_documents(df: pd.DataFrame) -> pd.DataFrame:
    """Remove test/cancelled documents from DataFrame."""
    return df[df['DocumentosCodigo'].isin(['XY', 'AS', 'TS']) == False]

def process_sales():
    df = filter_valid_documents(df)
    # ... processing

def process_inventory():
    df = filter_valid_documents(df)
    # ... processing
```

#### Pattern 2: Extract Configuration

```python
# Before (magic numbers scattered)
def calculate_metrics(df):
    df_preview = df.head(15)  # Magic number
    if len(df) > 100:  # Magic number
        print("Large dataset")

# After (centralized config)
class Config:
    INSIGHTS_MAX_ROWS = 15
    MAX_DISPLAY_ROWS = 100

def calculate_metrics(df):
    df_preview = df.head(Config.INSIGHTS_MAX_ROWS)
    if len(df) > Config.MAX_DISPLAY_ROWS:
        print("Large dataset")
```

#### Pattern 3: Simplify Conditionals

```python
# Before (complex nested ifs)
def validate_revenue(value):
    if value is not None:
        if value > 0:
            if value < 1000000000:
                return True
            else:
                return False
        else:
            return False
    else:
        return False

# After (early returns)
def validate_revenue(value: float) -> bool:
    """Validate revenue is positive and reasonable."""
    if value is None:
        return False

    if value <= 0:
        return False

    if value >= 1_000_000_000:  # 1 billion COP limit
        return False

    return True
```

### Code Style Standards

```python
# Use Black formatter
black src/ tests/ examples/

# Sort imports with isort
isort src/ tests/ examples/

# Check with flake8
flake8 src/ tests/ --max-line-length=127

# Type hints (Python 3.8+)
from typing import Optional, List, Dict, Any

def process_data(
    df: pd.DataFrame,
    columns: List[str],
    config: Optional[Dict[str, Any]] = None
) -> pd.DataFrame:
    """
    Process DataFrame according to config.

    Args:
        df: Input DataFrame
        columns: Columns to process
        config: Optional configuration dict

    Returns:
        Processed DataFrame
    """
    if config is None:
        config = {}

    # ... implementation
    return df
```

---

## 🧪 Testing Requirements

### Test Coverage Goals

| Component | Minimum Coverage | Current |
|-----------|-----------------|---------|
| src/vanna_grok.py | 85% | ~90% |
| src/business_analyzer_combined.py | 80% | ~75% |
| src/config.py | 90% | ~95% |
| Overall | 80% | ~85% |

### Test Organization

```
tests/
├── test_config.py              # Configuration & environment
├── test_formatting.py          # Number formatting
├── test_error_handling.py      # Retry logic, exceptions
├── test_business_metrics.py    # Business calculations
└── test_integration.py         # (Future) End-to-end tests
```

### Writing Good Tests

```python
# Test naming convention: test_<function>_<scenario>_<expected>

def test_format_number_currency_returns_colombian_format():
    """Test that currency values use Colombian peso format."""
    result = format_number(1234567, "TotalMasIva")
    assert result == "$1.234.567"

def test_format_number_null_returns_dash():
    """Test that None values return dash placeholder."""
    result = format_number(None, "TotalMasIva")
    assert result == "-"

def test_retry_decorator_succeeds_after_two_failures():
    """Test retry decorator retries failed calls."""
    call_count = 0

    @retry_on_failure(max_attempts=3, delay=0.1)
    def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Temporary failure")
        return "success"

    result = flaky_function()
    assert result == "success"
    assert call_count == 3  # Verify it retried
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_formatting.py -v

# Run specific test function
pytest tests/test_formatting.py::test_format_number_currency_returns_colombian_format -v

# Run with coverage report
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html

# Run only failed tests from last run
pytest --lf

# Run tests in parallel (faster)
pip install pytest-xdist
pytest tests/ -n auto
```

---

## 📊 Performance Optimization

### Performance Targets

| Operation | Target | Current |
|-----------|--------|---------|
| SQL query generation | < 2s | ~1.5s |
| DataFrame formatting (1000 rows) | < 0.5s | ~0.3s |
| AI insights generation | < 5s | ~3s |
| Page load time | < 3s | ~2s |

### Optimization Checklist

When optimizing code:

1. **Profile first, optimize second**
   ```bash
   python -m cProfile -s cumtime src/vanna_grok.py > profile.txt
   ```

2. **Use vectorized Pandas operations**
   ```python
   # ❌ Slow (row-by-row)
   for idx, row in df.iterrows():
       df.loc[idx, 'margin'] = (row['revenue'] - row['cost']) / row['revenue']

   # ✅ Fast (vectorized)
   df['margin'] = (df['revenue'] - df['cost']) / df['revenue']
   ```

3. **Limit data sent to AI APIs**
   ```python
   # Already implemented in vanna_grok.py
   df_preview = df.head(Config.INSIGHTS_MAX_ROWS)  # Max 15 rows
   ```

4. **Reuse expensive resources**
   ```python
   # ✅ Single shared client (already implemented)
   self.grok_client = OpenAI(api_key=Config.GROK_API_KEY, base_url="https://api.x.ai/v1")

   # ❌ Creating new client each time (wasteful)
   def generate_sql(question):
       client = OpenAI(...)  # Don't do this!
   ```

5. **Cache frequent queries**
   ```python
   from functools import lru_cache

   @lru_cache(maxsize=100)
   def get_product_categories() -> List[str]:
       """Cache product categories (rarely change)."""
       return df['categoria'].unique().tolist()
   ```

---

## 🚀 Git Workflow

### Branch Naming Convention

```bash
# Feature branches
claude/feature-name-SessionID
claude/add-profit-alerts-011CUderi5Zh1AFqSbeCWPt2

# Bug fix branches
claude/fix-margin-calculation-SessionID
claude/fix-zero-division-error-011CUderi5Zh1AFqSbeCWPt2

# Refactoring branches
claude/refactor-formatting-SessionID

# Documentation branches
claude/docs-update-SessionID
```

**CRITICAL:** Branch name MUST start with `claude/` and end with matching session ID, otherwise push will fail with 403 error.

### Commit Message Format

```
<type>: <short summary (50 chars max)>

<detailed description (wrap at 72 chars)>

<optional sections>

Examples:
- feat: Add automatic profit margin alerts
- fix: Handle zero division in margin calculation
- refactor: Extract formatting logic to utils module
- docs: Update ANACONDA_TESTING.md with troubleshooting
- test: Add edge cases for Colombian peso formatting
- chore: Update dependencies in requirements.txt
```

### Commit Best Practices

```bash
# 1. Review changes before committing
git diff

# 2. Stage related changes together
git add src/vanna_grok.py tests/test_formatting.py

# 3. Write descriptive commit message
git commit -m "feat: Add revenue trend visualization

- Implement 30-day revenue trend chart using Plotly
- Add trend_analysis() function with pandas rolling average
- Include Colombian peso formatting on Y-axis
- Add tests for trend calculation edge cases

Tests: ✅ pytest tests/test_visualization.py
Performance: <0.5s for 1000 data points
Related: docs/ROADMAP.md (Path B, item 4)"

# 4. Push with retry on network failure
git push -u origin claude/feature-name-SessionID

# If push fails with network error, retry with exponential backoff:
# Try 1: wait 2s
# Try 2: wait 4s
# Try 3: wait 8s
# Try 4: wait 16s
```

---

## 📚 Documentation Standards

### Code Documentation

Every function must have a docstring:

```python
def calculate_profit_margin(
    revenue: float,
    cost: float,
    include_tax: bool = False
) -> float:
    """
    Calculate profit margin as percentage.

    Formula:
        margin = ((revenue - cost) / revenue) * 100

    Args:
        revenue: Total revenue in COP (Colombian Pesos)
        cost: Total cost in COP
        include_tax: If True, use TotalMasIva; else TotalSinIva

    Returns:
        Profit margin as percentage (0-100)
        Returns 0.0 if revenue is zero or negative

    Examples:
        >>> calculate_profit_margin(1000, 600)
        40.0

        >>> calculate_profit_margin(1000, 1200)  # Loss
        0.0

        >>> calculate_profit_margin(0, 100)  # Zero revenue
        0.0

    Note:
        This function never returns negative values.
        Losses are represented as 0% margin.
    """
    if revenue <= 0:
        return 0.0

    margin = ((revenue - cost) / revenue) * 100
    return max(0.0, margin)
```

### README Updates

Update README.md when adding:
- New installation requirements
- New environment variables
- New console commands
- Major features
- Breaking changes

### Documentation Files to Update

| Change Type | Update Files |
|-------------|-------------|
| New feature | README.md, ROADMAP.md, relevant docs/*.md |
| Bug fix | CHANGELOG.md (if exists), commit message |
| Configuration | .env.example, VANNA_SETUP.md |
| Testing | ANACONDA_TESTING.md, test docstrings |
| API change | All affected documentation |

---

## 🎓 Learning Resources

### Understanding the Codebase

1. **Start here** (in order):
   - `docs/START_HERE.md` - Project overview
   - `docs/ROADMAP.md` - Development plan
   - `src/vanna_grok.py` - Main application
   - `tests/test_*.py` - Test examples

2. **Key concepts to understand**:
   - Vanna AI RAG (Retrieval Augmented Generation)
   - ChromaDB vector storage
   - Grok API for SQL generation
   - Colombian number formatting
   - MSSQL connection via ODBC

3. **External documentation**:
   - [Vanna AI Docs](https://vanna.ai/docs/)
   - [Grok API Reference](https://docs.x.ai/)
   - [Pandas Documentation](https://pandas.pydata.org/docs/)
   - [pytest Documentation](https://docs.pytest.org/)

### Common Patterns in This Codebase

```python
# Pattern 1: Retry with exponential backoff
@retry_on_failure(max_attempts=3, delay=2, backoff=2)
def api_call():
    # Implementation

# Pattern 2: Environment variable validation
config_value = require_env("VAR_NAME", validation_func=lambda x: x.startswith("prefix"))

# Pattern 3: Colombian number formatting
formatted = format_number(value, column_name)

# Pattern 4: Resource reuse
# Use self.grok_client instead of creating new OpenAI() instances

# Pattern 5: DataFrame processing
df = filter_valid_documents(df)  # Remove test docs
df_formatted = format_dataframe(df, max_rows=100)  # Limit + format
```

---

## ✅ Pre-Commit Checklist

Before committing ANY code, verify:

- [ ] Code runs without errors
- [ ] All tests pass: `pytest tests/ -v`
- [ ] Code formatted: `black src/ tests/`
- [ ] Imports sorted: `isort src/ tests/`
- [ ] No flake8 errors: `flake8 src/ tests/`
- [ ] Type hints added for new functions
- [ ] Docstrings added/updated
- [ ] Colombian formatting preserved
- [ ] Spanish language used for user messages
- [ ] No hardcoded credentials
- [ ] Tests added for new features
- [ ] Documentation updated
- [ ] Commit message descriptive
- [ ] `.env` file NOT committed
- [ ] No debugging print() statements (use logging)
- [ ] Performance acceptable (profile if unsure)

---

## 🚨 Emergency Procedures

### Production Hotfix Process

If production is broken:

1. **Assess severity**
   ```bash
   # P0 (Critical): Database down, security breach, data loss
   # P1 (High): Feature broken, major bug affecting users
   # P2 (Medium): Minor bug, performance degradation
   # P3 (Low): Cosmetic issues, minor improvements
   ```

2. **For P0/P1 issues:**
   ```bash
   # Create hotfix branch
   git checkout -b claude/hotfix-issue-description-SessionID

   # Fix the issue (minimal changes only!)
   # Add test to prevent regression

   # Verify fix
   pytest tests/ -v

   # Commit and push immediately
   git commit -m "fix(P0): Brief description of critical fix"
   git push -u origin claude/hotfix-issue-description-SessionID
   ```

3. **Notify team** (if applicable)

### Rollback Procedure

If a deployment causes issues:

```bash
# Find last working commit
git log --oneline | head -10

# Revert to that commit
git revert <commit-hash>

# Or create revert branch
git checkout -b claude/revert-broken-feature-SessionID
git revert <commit-hash>
git push -u origin claude/revert-broken-feature-SessionID
```

---

## 💡 Tips for Success

1. **Read existing code first** - Understand patterns before adding new code
2. **Test early, test often** - Don't wait until code is "done"
3. **Small commits** - Easier to review and revert if needed
4. **Ask for clarification** - Better to ask than assume
5. **Document as you go** - Don't leave it for later
6. **Respect Colombian context** - Spanish language, peso formatting, local business practices
7. **Security first** - Never compromise on credentials or data safety
8. **Performance matters** - Profile before optimizing, but don't ignore slowness
9. **Backward compatibility** - Don't break existing functionality
10. **Have fun!** - You're building something that helps a real business

---

## 📞 Getting Help

### Documentation Hierarchy

1. This file (AI_AGENT_INSTRUCTIONS.md)
2. `docs/START_HERE.md` - Quick orientation
3. `docs/ROADMAP.md` - Development priorities
4. `docs/VANNA_SETUP.md` - Vanna AI specifics
5. `docs/ANACONDA_TESTING.md` - Testing infrastructure
6. Code comments and docstrings

### Debugging Workflow

```
1. Reproduce the issue locally
   ↓
2. Read related documentation
   ↓
3. Search codebase for similar patterns
   ↓
4. Check git history: git log --all --grep="keyword"
   ↓
5. Add debug logging/prints
   ↓
6. Use pdb debugger if needed
   ↓
7. Write failing test first
   ↓
8. Fix the issue
   ↓
9. Verify test passes
   ↓
10. Document the fix
```

---

## 🎯 Success Metrics

You're doing well if:

- ✅ Test coverage stays above 80%
- ✅ All CI/CD checks pass
- ✅ Code follows existing patterns
- ✅ Documentation is up-to-date
- ✅ No security vulnerabilities introduced
- ✅ Colombian formatting preserved
- ✅ Spanish language maintained
- ✅ Performance remains acceptable
- ✅ Commits are descriptive and atomic
- ✅ Backward compatibility maintained

---

**Remember:** This project serves a real business. Your code impacts actual sales decisions, inventory management, and business insights. Write code you'd be proud to show the store owner.

**¡Buena suerte!** (Good luck!)
