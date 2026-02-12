# Testing Guide

This document explains how to test the Business Data Analyzer repository.

## Quick Start

### Running Tests

The easiest way to run tests is using the test runner script:

```bash
# Run all tests (default)
python run_tests.py

# Run only basic tests (no dependencies required)
python run_tests.py --quick

# Run all tests including those requiring dependencies
python run_tests.py --all

# Run with coverage report
python run_tests.py --cov
```

### Using pytest directly

```bash
# Install pytest if not already installed
pip install pytest pytest-cov

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_basic.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run only tests that don't require dependencies
pytest tests/test_basic.py -v
```

## Test Structure

```
tests/
├── __init__.py                    # Test package initialization
├── conftest.py                    # Pytest configuration and fixtures
├── test_basic.py                  # Basic tests (no dependencies)
├── test_business_metrics.py       # Business metrics tests (requires pymssql)
├── test_metabase_connection.py    # Database connection diagnostic
└── test_vanna_grok.py             # Vanna Grok integration tests (requires pandas, vanna)
```

## Test Categories

### 1. Basic Tests (`test_basic.py`)
- **No dependencies required**
- Tests repository structure
- Tests basic Python functionality
- Tests utility functions
- Always runs, even without installing dependencies

### 2. Business Metrics Tests (`test_business_metrics.py`)
- **Requires**: `pymssql`, `examples/improvements_p0.py`
- Tests financial calculations
- Tests data validation
- Tests profit margin calculations
- **Skipped** if dependencies not available

### 3. Metabase Connection Tests (`test_metabase_connection.py`)
- **Requires**: `pymssql`, database connection
- Diagnostic tool for database issues
- **Skipped** if dependencies not available

### 4. Vanna Grok Tests (`test_vanna_grok.py`) 🆕
- **Requires**: `pandas`, `vanna`, `openai`
- Tests number formatting (Colombian pesos format)
- Tests AI insights generation (mocked)
- Tests configuration management
- Tests edge cases and error handling
- **Skipped** if dependencies not available
- **Runs in CI/CD** with GitHub Actions workflow

## Installing Test Dependencies

### Minimal (for basic tests only)
```bash
pip install pytest pytest-cov
```

### Full (for all tests)
```bash
# Install from requirements.txt
pip install -r requirements.txt

# Or install individually
pip install pytest pytest-cov pymssql python-dotenv pandas matplotlib
```

## Test Configuration

The repository includes a `pytest.ini` file with sensible defaults:

```ini
[pytest]
testpaths = tests
addopts = -v --tb=short --strict-markers --disable-warnings
```

## Continuous Integration

The repository includes GitHub Actions workflows for automated testing:

### Available Workflows

1. **Basic Tests** (`.github/workflows/tests.yml`)
   - Runs on every push and pull request
   - Tests basic functionality without dependencies
   - Tests with full dependencies (when available)
   - Runs on Python 3.10, 3.11, and 3.12

2. **Vanna Grok Tests** (`.github/workflows/test-vanna-grok.yml`)
   - Specifically tests vanna_grok.py functionality
   - Installs vanna, pandas, and related dependencies
   - Runs on multiple Python versions
   - Generates coverage reports

### GitHub Actions Status

You can view the test status in the Actions tab of the repository:
- ✅ All tests passing: Tests run successfully
- ⏭️ Tests skipped: Dependencies not available (expected)
- ❌ Tests failed: Investigate the failure

### Running Tests Locally Like CI

To replicate CI environment locally:

```bash
# Basic tests (like CI basic job)
pip install pytest pytest-cov
python run_tests.py --quick

# Full tests (like CI with-dependencies job)
pip install -r requirements.txt
pytest tests/ -v --cov=src
```

### Manual Workflow Trigger

You can manually trigger workflows from GitHub:
1. Go to the "Actions" tab
2. Select the workflow (e.g., "Test Vanna Grok")
3. Click "Run workflow"
4. Select the branch and click "Run workflow"

## Writing New Tests

### Test File Naming
- Test files must start with `test_`
- Test functions must start with `test_`
- Test classes must start with `Test`

### Using Fixtures

```python
def test_example(sample_transaction_data):
    """Test using shared fixture from conftest.py"""
    assert len(sample_transaction_data) == 3
```

### Marking Tests

```python
import pytest

@pytest.mark.unit
def test_basic_function():
    """Unit test"""
    assert True

@pytest.mark.integration
@pytest.mark.requires_db
def test_database_function():
    """Integration test requiring database"""
    pass
```

### Skipping Tests

```python
import pytest

@pytest.mark.skipif(not HAS_DEPENDENCY, reason="dependency not installed")
def test_with_dependency():
    """This test requires a specific dependency"""
    pass
```

## Coverage Reports

### Current Coverage Status

**Overall Coverage: ~54%** (Target: ≥80%)

| Module | Coverage | Status |
|--------|----------|--------|
| src/config.py | 98.21% | ✅ |
| src/business_analyzer/analysis/customer.py | 90.77% | ✅ |
| src/business_analyzer/analysis/financial.py | 91.80% | ✅ |
| src/business_analyzer/analysis/inventory.py | 88.89% | ✅ |
| src/business_analyzer/analysis/product.py | 85.96% | ✅ |
| src/business_analyzer/core/database.py | 88.57% | ✅ |
| src/business_analyzer/ai/formatting.py | 82.19% | ✅ |
| src/business_analyzer/ai/providers/grok.py | 71.43% | ⚠️ |
| src/business_analyzer/ai/providers/openai.py | 68.42% | ⚠️ |
| src/business_analyzer/ai/providers/anthropic.py | 59.09% | ⚠️ |
| src/business_analyzer/ai/providers/ollama.py | 55.00% | ⚠️ |
| src/business_analyzer/ai/training.py | 48.39% | ⚠️ |
| src/business_analyzer_combined.py | 43.38% | ❌ |
| src/business_analyzer/ai/insights.py | 20.59% | ❌ |
| src/vanna_grok.py | 6.45% | ❌ |
| src/business_analyzer/ai/base.py | 0.00% | ❌ |

### Running Coverage Reports

Generate HTML coverage reports:

```bash
# Run all tests with coverage
pytest tests/ --cov=src --cov-report=html

# Run with terminal report showing missing lines
pytest tests/ --cov=src --cov-report=term-missing

# Run coverage for specific module
pytest tests/ --cov=src.business_analyzer_combined --cov-report=term-missing
```

View the HTML report by opening `htmlcov/index.html` in your browser.

### Coverage Goals

- **Target**: ≥80% overall coverage
- **Critical modules** (business logic): ≥90%
- **Utility modules**: ≥70%
- **CLI/Wrapper modules**: ≥60%

### Coverage in CI

Coverage reports are automatically generated in GitHub Actions:
- Coverage artifacts uploaded for Python 3.11 runs
- Reports retained for 30 days
- Access via Actions tab → Artifacts

## Troubleshooting

### "No module named 'pymssql'"
This is expected if you haven't installed the full dependencies. Tests requiring pymssql will be automatically skipped.

**Solution**: Either run only basic tests (`python run_tests.py --quick`) or install dependencies (`pip install -r requirements.txt`)

### "No tests collected"
Make sure you're in the repository root directory and pytest can find the `tests/` folder.

**Solution**:
```bash
cd /path/to/depotru_database
pytest tests/ -v
```

### Tests pass locally but fail in CI
Check that your CI environment has the necessary dependencies installed.

## Best Practices

1. **Run tests before committing**
   ```bash
   python run_tests.py
   ```

2. **Write tests for new features**
   - Add tests in the appropriate test file
   - Use existing fixtures when possible
   - Follow the existing test structure

3. **Keep tests fast**
   - Basic tests should run in under 1 second
   - Use mocks for external dependencies
   - Skip slow tests in quick mode

4. **Test edge cases**
   - Empty data
   - Null values
   - Division by zero
   - Invalid inputs

## Example Test Session

```bash
$ python run_tests.py
======================================================================
Running Business Data Analyzer Tests
======================================================================
Command: pytest tests/ -v

========================= test session starts =========================
platform linux -- Python 3.12.3, pytest-9.0.2, pluggy-1.6.0
Business Data Analyzer Test Suite
Python: 3.12.3
pymssql: ✗
pandas: ✗
matplotlib: ✗
vanna: ✗
rootdir: /home/runner/work/depotru_database/depotru_database
configfile: pytest.ini
collected 13 items / 2 skipped

tests/test_basic.py::TestRepositoryStructure::test_readme_exists PASSED
tests/test_basic.py::TestRepositoryStructure::test_requirements_exists PASSED
...

======================== 13 passed, 2 skipped in 0.04s ========================

======================================================================
✅ All tests passed!
======================================================================
```

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Testing Python Applications](https://realpython.com/pytest-python-testing/)
