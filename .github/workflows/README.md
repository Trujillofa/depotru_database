# GitHub Actions Workflows

This directory contains CI/CD workflows for automated testing.

## Available Workflows

### 1. General Tests (`tests.yml`)

**Triggers:**
- Push to `main` or `copilot/**` branches
- Pull requests to `main`
- Manual workflow dispatch

**Jobs:**
- **test-basic**: Runs basic tests without dependencies
- **test-with-dependencies**: Runs all tests with optional dependencies installed
  - Tests on Python 3.10, 3.11, 3.12
  - Installs pandas, vanna, matplotlib, pymssql (when possible)
  - Generates coverage reports

### 2. Vanna Grok Tests (`test-vanna-grok.yml`)

**Triggers:**
- Push/PR when `src/vanna_grok.py` or `tests/test_vanna_grok.py` changes
- Manual workflow dispatch

**Jobs:**
- **test-vanna-grok**: Specifically tests vanna_grok.py
  - Tests on Python 3.10, 3.11, 3.12
  - Installs pandas, vanna, openai, chromadb
  - Tests number formatting, AI insights, configuration
  - Generates coverage reports for vanna_grok.py

## Viewing Test Results

1. Go to the repository on GitHub
2. Click the **"Actions"** tab
3. Select a workflow run to view details
4. View test output, coverage, and any failures

## Manual Workflow Trigger

To manually run a workflow:

1. Go to **Actions** tab
2. Select the workflow (e.g., "Test Vanna Grok")
3. Click **"Run workflow"** button
4. Select branch and click **"Run workflow"**

## Understanding Test Status

- ✅ **Success**: All tests passed
- ⏭️ **Skipped**: Tests skipped due to missing dependencies (expected)
- ❌ **Failure**: Tests failed, requires investigation
- 🟡 **Warning**: Some tests passed, some skipped

## Local Testing

To replicate CI environment locally:

```bash
# Install dependencies like CI does
pip install pytest pytest-cov pytest-mock
pip install pandas vanna chromadb openai python-dotenv

# Run tests like CI
pytest tests/ -v --cov=src
```

## Environment Variables

The workflows use these environment variables for testing:

- `GROK_API_KEY`: Set to `xai-test-key-for-ci` (mock value)
- `DB_SERVER`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`: Mock database credentials

**Note**: These are NOT real credentials. Real API keys and database connections are never exposed in CI.

## Coverage Reports

Coverage reports are uploaded to Codecov for:
- Overall test coverage (Python 3.12 only)
- vanna_grok.py specific coverage

View coverage at: `https://codecov.io/gh/Trujillofa/depotru_database`

## Troubleshooting

### Workflow Not Running

- Check that the file paths in `on.push.paths` match your changes
- Verify branch name matches the trigger pattern

### Tests Failing in CI but Passing Locally

- Check Python version (CI uses 3.10, 3.11, 3.12)
- Ensure dependencies are correctly specified
- Review workflow logs for missing dependencies

### Workflow Permissions

If workflows fail with permission errors:
1. Go to Settings → Actions → General
2. Under "Workflow permissions", select "Read and write permissions"
3. Save changes

## Adding New Workflows

To add a new workflow:

1. Create a new `.yml` file in `.github/workflows/`
2. Define triggers, jobs, and steps
3. Test locally with `act` (if available) or push to a test branch
4. Monitor the Actions tab for results

## Best Practices

- Keep workflows fast (< 5 minutes when possible)
- Use caching for pip packages
- Skip tests gracefully when dependencies unavailable
- Generate coverage reports only once (Python 3.12)
- Use workflow_dispatch for manual testing
- Add informative test summaries
