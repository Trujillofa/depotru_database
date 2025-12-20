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
└── test_metabase_connection.py    # Database connection diagnostic
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

Tests are designed to work in CI environments where dependencies might not be available. Tests that require external dependencies will be automatically skipped.

### Example GitHub Actions workflow

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install pytest pytest-cov
      - name: Run basic tests
        run: pytest tests/test_basic.py -v
```

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

Generate HTML coverage reports:

```bash
pytest tests/ --cov=src --cov-report=html
```

View the report by opening `htmlcov/index.html` in your browser.

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
