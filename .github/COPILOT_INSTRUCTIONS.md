# GitHub Copilot Instructions for Business Data Analyzer

This file provides instructions for GitHub Copilot when working with this repository.

## Project Overview

**Business Data Analyzer** is a comprehensive business intelligence platform for hardware store operations with:
- AI-powered natural language SQL queries using Vanna AI
- Support for multiple AI providers (OpenAI GPT-4, Grok/xAI, Anthropic Claude, Ollama)
- Traditional script-based business analytics
- Interactive web dashboards with Streamlit
- Automated report generation and visualizations

**Main Technologies:**
- Python 3.10+
- SQL Server (via pymssql/pyodbc)
- Vanna AI for natural language to SQL
- Flask/Waitress for web serving
- Pandas, Matplotlib, Plotly for data analysis and visualization
- pytest for testing

## Development Setup

### Prerequisites

```bash
# Clone repository
git clone <repo-url>
cd depotru_database

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Environment Configuration

**ALWAYS** use `.env` file for configuration (never commit `.env`):

```bash
# Copy template
cp .env.example .env

# Required environment variables:
# - DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME (database connection)
# - GROK_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY (for AI features)
# - OUTPUT_DIR (default: ~/business_reports)
```

**Security Rules:**
- Never commit credentials, API keys, or `.env` files
- Always use environment variables or `.env` files for sensitive data
- Check `.gitignore` before committing to ensure no secrets are included

## Building and Testing

### Running Tests

```bash
# Quick tests (no dependencies required) - RECOMMENDED FOR CI
python run_tests.py --quick

# All tests (requires dependencies)
python run_tests.py

# With coverage
python run_tests.py --cov

# Using pytest directly
pytest tests/ -v

# Run specific test file
pytest tests/test_basic.py -v
```

**Testing Strategy:**
- Always run `python run_tests.py --quick` before committing
- Use `pytest.mark.skipif` for tests requiring optional dependencies
- Mock external services (databases, APIs) in unit tests
- Use `conftest.py` for shared fixtures and skip conditions

### Linting and Code Quality

```bash
# Format code (before committing)
black src/ tests/ examples/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/

# Sort imports
isort src/ tests/ examples/
```

**Code Style:**
- Follow PEP 8 guidelines
- Maximum line length: 100 characters
- Use type hints for function parameters and return values
- Add docstrings to all functions and classes
- Use meaningful variable names

## Code Conventions

### Database Connections

Always use safe database connection patterns with proper cleanup:

```python
import pymssql

def safe_database_operation():
    """Always use try-finally for database connections."""
    conn = None
    try:
        conn = pymssql.connect(...)
        cursor = conn.cursor(as_dict=True)
        # Do work
        return results
    except Exception as e:
        logging.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()
```

### Configuration Management

Use the centralized `config.py` module:

```python
from src.config import Config

# Access configuration
db_host = Config.DB_HOST
output_dir = Config.OUTPUT_DIR
```

### Error Handling

Always include proper error handling and logging:

```python
import logging

def process_data(data):
    """Process data with proper error handling."""
    try:
        # Validate input
        if not data:
            raise ValueError("Data cannot be empty")
        
        # Process
        result = do_something(data)
        return result
        
    except ValueError as e:
        logging.error(f"Validation error: {e}")
        raise
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        raise
```

### Division Operations

Always use safe division to avoid division by zero errors:

```python
def safe_divide(numerator, denominator, default=0):
    """Safely divide two numbers, returning default if denominator is zero."""
    try:
        return numerator / denominator if denominator != 0 else default
    except (TypeError, ZeroDivisionError):
        return default

# Usage
margin = safe_divide(profit, revenue, 0.0)
```

### Testing Patterns

Use proper pytest fixtures and markers:

```python
import pytest

@pytest.fixture
def sample_data():
    """Fixture for sample test data."""
    return [{"value": 100}, {"value": 200}]

@pytest.mark.unit
def test_calculation(sample_data):
    """Test with proper markers and docstrings."""
    result = calculate_total(sample_data)
    assert result == 300

@pytest.mark.requires_db
@pytest.mark.skipif(not HAS_DATABASE, reason="Database not available")
def test_database_query():
    """Test requiring database connection."""
    # Test implementation
    pass
```

## Workflow and CI/CD

### GitHub Actions Workflows

The repository has multiple workflows:

1. **tests.yml** - Main test suite
   - Runs on push to `main` and `copilot/**` branches
   - Two jobs: basic tests (no dependencies) and full tests (with dependencies)
   - Tests across Python 3.10, 3.11, 3.12
   - Always ensure changes don't break `python run_tests.py --quick`

2. **test-vanna-grok.yml** - Vanna AI tests
   - Specific to `src/vanna_grok.py` changes
   - Requires ODBC drivers and specific dependencies
   - Uses mocked API keys in CI

3. **claude.yml** - Claude Code integration
   - Triggered by `@claude` mentions in issues/PRs

4. **claude-code-review.yml** - Automated code review
   - Runs on PR open/sync

### Branch Strategy

- `main` - Stable production branch
- `copilot/**` - Copilot-generated branches (CI enabled)
- Feature branches - Standard feature development

## Common Tasks

### Adding a New Feature

1. Create a branch: `git checkout -b feature/feature-name`
2. Write code following conventions above
3. Add tests in `tests/` directory
4. Run tests: `python run_tests.py --quick`
5. Format code: `black src/ tests/`
6. Commit with descriptive message (see CONTRIBUTING.md for commit message format)
7. Push and create PR

### Adding New Dependencies

1. Add to `requirements.txt` with version
2. Document in README.md if it's a major dependency
3. Update `.github/workflows/` if new system dependencies are needed
4. Add appropriate `pytest.mark.skipif` for optional dependencies

### Working with Vanna AI

The repository has two Vanna implementations:

1. **vanna_grok.py** - Production-ready, Spanish-optimized, beautiful output
2. **vanna_chat.py** - Multi-provider testing (OpenAI, Grok, Claude, Ollama)

When modifying Vanna code:
- Always mock API calls in tests
- Set test API keys as environment variables
- Test with `pytest tests/test_vanna_grok.py -v`
- Ensure beautiful number formatting for Colombian pesos: `$123.456.789`

### Debugging Tips

```bash
# Test database connection
python test_connection.py

# Run Vanna test
python test_vanna.py

# Check imports
python -c "import sys; sys.path.insert(0, 'src'); from vanna_grok import format_number"

# View logs
tail -f *.log
```

## Documentation

- **README.md** - Main project documentation and quick start
- **docs/START_HERE.md** - Overview and navigation guide
- **docs/CONTRIBUTING.md** - Development workflow and guidelines
- **docs/VANNA_SETUP.md** - AI setup instructions
- **docs/VANNA_COMPARISON.md** - Comparison of Vanna implementations
- **docs/SECURITY.md** - Security best practices

When adding features:
- Update README.md if user-facing
- Add examples to `examples/` directory if applicable
- Update relevant docs in `docs/` directory

## Important Files

- `src/business_analyzer_combined.py` - Main traditional analyzer (1,492 lines, legacy)
- `src/vanna_grok.py` - Production Vanna AI implementation (Spanish, beautiful output)
- `src/vanna_chat.py` - Multi-provider Vanna AI testing
- `src/config.py` - Centralized configuration management
- `tests/conftest.py` - Shared pytest fixtures and configuration
- `run_tests.py` - Test runner script
- `pytest.ini` - Pytest configuration

## Special Considerations

### Performance

- The traditional analyzer can be slow with large datasets
- Consider using `examples/pandas_approach.py` patterns for better performance
- Limit query results appropriately (use `--limit` flag)

### Spanish Language Support

- `vanna_grok.py` is optimized for Colombian business context
- Number formatting: Colombian peso format `$123.456.789`
- Support Spanish queries: "Top 10 productos más vendidos"

### Cross-Platform Support

- Use `Path` from `pathlib` for file paths
- Use `os.path.expanduser()` for home directory paths
- Test on multiple platforms when possible

## Getting Help

- Check existing documentation in `docs/` directory
- Review working examples in `examples/` directory
- Look at test cases in `tests/` for usage patterns
- See `.env.example` for configuration options

## Copilot-Specific Guidelines

When generating code:
1. Always follow the security rules (no credentials in code)
2. Include proper error handling and logging
3. Add type hints to function signatures
4. Write docstrings for all functions
5. Use existing patterns from the codebase
6. Add appropriate pytest markers to tests
7. Consider cross-platform compatibility
8. Update documentation if adding user-facing features
9. Run `python run_tests.py --quick` before suggesting the code is complete
10. Use `black` formatting style

When reviewing code:
1. Check for security issues (credentials, SQL injection, etc.)
2. Verify proper error handling
3. Ensure tests are included
4. Check for division by zero issues
5. Verify database connections are properly closed
6. Ensure documentation is updated

## Quick Reference

```bash
# Setup
cp .env.example .env
pip install -r requirements.txt

# Test
python run_tests.py --quick

# Format
black src/ tests/

# Run traditional analyzer
python src/business_analyzer_combined.py

# Run Vanna AI (Grok)
python src/vanna_grok.py

# Run Streamlit dashboard
streamlit run examples/streamlit_dashboard.py
```

---

**Remember:** Security first, test early, document changes, and follow existing patterns!
