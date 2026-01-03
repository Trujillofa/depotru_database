# GitHub Actions Workflows

This directory contains CI/CD workflows for automated testing and code quality.

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

### 3. Code Quality & Security

**CodeQL Analysis (`codeql-analysis.yml`)**
- Automated security vulnerability scanning
- Runs on push to main and on PRs

**Dependency Review (`dependency-review.yml`)**
- Scans for vulnerable dependencies in PRs
- Prevents introduction of known security issues

### 4. AI-Assisted Development

**Claude Code (`claude.yml`)**
- Triggered by @claude mentions in issues/PRs
- Provides AI-assisted code review and suggestions

**Claude Code Review (`claude-code-review.yml`)**
- Automated code review on PR open/update
- Reviews for code quality, security, and best practices

## Workflow Organization

The workflows are organized to minimize redundancy:

- **tests.yml**: General test suite for all code changes
- **test-vanna-grok.yml**: Focused testing for Vanna integration (only runs when relevant files change)
- **codeql-analysis.yml** & **dependency-review.yml**: Security and dependency scanning
- **claude.yml** & **claude-code-review.yml**: AI-assisted development tools

## Viewing Workflow Results

1. Go to the repository on GitHub
2. Click the **"Actions"** tab
3. Select a workflow run to view details
4. View test output, coverage, and any failures

## Manual Workflow Trigger

To manually run a workflow:

1. Go to **Actions** tab
2. Select the workflow (e.g., "Tests" or "Test Vanna Grok")
3. Click **"Run workflow"** button
4. Select branch and click **"Run workflow"**

## Understanding Status Badges

- ✅ **Success**: All tests passed
- ⏭️ **Skipped**: Tests skipped due to missing dependencies (expected behavior)
- ❌ **Failure**: Tests failed, requires investigation
- 🟡 **Warning**: Some tests passed, some skipped

## Local Testing

Replicate CI environment locally:

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-mock

# Install optional dependencies for full testing
pip install pandas vanna chromadb openai python-dotenv pymssql

# Run quick tests (no dependencies required)
python scripts/utils/run_tests.py --quick

# Run all tests with coverage
pytest tests/ -v --cov=src --cov-report=term
```

## Required Secrets

The workflows use GitHub repository secrets for sensitive data:

- `GROK_API_KEY`: API key for Grok/xAI service (test value in CI)
- `DB_SERVER`: Database server address (mock value in CI)
- `DB_NAME`: Database name (mock value in CI)
- `DB_USER`: Database username (mock value in CI)
- `DB_PASSWORD`: Database password (mock value in CI)
- `CLAUDE_CODE_OAUTH_TOKEN`: OAuth token for Claude Code integration

**Note**: CI uses mock/test values. Real credentials are never exposed in workflows.

## Coverage Reports

Coverage reports are uploaded to Codecov:
- Overall test coverage (from tests.yml, Python 3.12 only)
- vanna_grok.py specific coverage (from test-vanna-grok.yml, Python 3.12 only)

View coverage at: `https://codecov.io/gh/Trujillofa/depotru_database`

## Troubleshooting

### Workflow Not Running

- Check that file paths in `on.push.paths` match your changes
- Verify branch name matches the trigger pattern (`main` or `copilot/**`)
- Ensure you have push access to the repository

### Tests Failing in CI but Passing Locally

- Check Python version (CI uses 3.10, 3.11, 3.12)
- Ensure all dependencies are correctly specified in requirements.txt
- Review workflow logs for environment differences
- Check if tests depend on local configuration or files

### Permission Errors

If workflows fail with permission errors:
1. Go to Settings → Actions → General
2. Under "Workflow permissions", select "Read and write permissions"
3. Check "Allow GitHub Actions to create and approve pull requests"
4. Save changes

## Best Practices

- Keep workflows fast (target < 5 minutes when possible)
- Use caching for pip packages to speed up builds
- Skip tests gracefully when optional dependencies are unavailable
- Generate coverage reports only once (Python 3.12) to save resources
- Use `workflow_dispatch` for manual testing flexibility
- Add informative test summaries using `$GITHUB_STEP_SUMMARY`
- Use path filters to run workflows only when relevant files change
