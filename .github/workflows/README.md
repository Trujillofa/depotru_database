# GitHub Actions Workflows

This directory contains CI/CD workflows for automated testing, security scanning, and code review.

## Available Workflows

### 1. CI/CD Pipeline (`python-package-conda.yml`)

**Triggers:**
- Push to `main`, `develop`, `claude/**`, or `copilot/**` branches
- Pull requests to `main` or `develop`
- Manual workflow dispatch

**Jobs:**

- **test**: Runs comprehensive tests across multiple platforms and Python versions
  - Tests on Ubuntu (3.9, 3.10, 3.11, 3.12), Windows (3.10, 3.11, 3.12), macOS (3.10, 3.11, 3.12)
  - Linting (flake8), formatting (black), import sorting (isort), type checking (mypy) - Ubuntu 3.12 only
  - Generates coverage reports (Ubuntu 3.12 only)
  - Uploads to Codecov

- **security**: Security scanning with bandit and safety
  - Checks for security vulnerabilities in code
  - Checks for vulnerable dependencies
  - Uploads security reports

- **package-build**: Validates package can be built
  - Builds Python package using build tools
  - Validates with twine
  - Uploads package artifacts

### 2. Claude Integration (`claude.yml`)

**Triggers:**
- Issue comments, PR review comments, or PR reviews containing `@claude`
- New issues containing `@claude` in title or body

**Purpose:**
- Provides interactive Claude assistance on issues and PRs
- Automatically responds when tagged with `@claude`

### 3. CodeQL Security Analysis (`codeql-analysis.yml`)

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Scheduled: Every Monday at 6:00 AM UTC

**Purpose:**
- Advanced security vulnerability scanning
- Analyzes Python code for security issues
- Uses extended security and quality queries

### 4. Dependency Review (`dependency-review.yml`)

**Triggers:**
- Pull requests to `main` or `develop` branches

**Purpose:**
- Reviews dependency changes in PRs
- Fails on high/critical severity vulnerabilities
- Validates license compatibility

## Viewing Test Results

1. Go to the repository on GitHub
2. Click the **"Actions"** tab
3. Select a workflow run to view details
4. View test output, coverage, security reports, and any failures

## Manual Workflow Trigger

To manually run the CI/CD pipeline:

1. Go to **Actions** tab
2. Select **"CI/CD Pipeline"**
3. Click **"Run workflow"** button
4. Select branch and click **"Run workflow"**

## Understanding Test Status

- ✅ **Success**: All tests passed
- ❌ **Failure**: Tests failed, requires investigation
- 🟡 **Warning**: Some non-blocking checks failed (formatting, type checking)

## Local Testing

To replicate CI environment locally:

```bash
# Create Conda environment
conda env create -f environment.yml
conda activate business-analyzer

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov black flake8 mypy isort

# Run tests
pytest tests/ -v --cov=src

# Run linting
flake8 src/ --count --select=E9,F63,F7,F82
black --check src/ tests/ examples/
isort --check-only src/ tests/ examples/
mypy src/
```

## Environment Variables

The workflows use these environment variables from GitHub Secrets:

- `GROK_API_KEY`: Grok API key for AI testing
- `DB_SERVER`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`: Database credentials

**Note**: These are real secrets stored in GitHub repository settings.

## Coverage Reports

Coverage reports are uploaded to Codecov from Ubuntu with Python 3.12 only.

View coverage at: `https://codecov.io/gh/Trujillofa/depotru_database`

## Security Reports

Security scanning produces:
- Bandit security reports (uploaded as artifacts)
- Safety dependency vulnerability reports
- CodeQL security analysis reports

## Troubleshooting

### Workflow Not Running

- Check that your branch matches the trigger pattern
- Verify workflow triggers are configured correctly

### Tests Failing in CI but Passing Locally

- Check Python version (CI uses 3.9-3.12)
- Ensure dependencies are correctly specified in requirements.txt
- Review workflow logs for missing dependencies or environment issues

### Workflow Permissions

If workflows fail with permission errors:
1. Go to Settings → Actions → General
2. Under "Workflow permissions", select "Read and write permissions"
3. Save changes

## Workflow Optimization

The CI/CD pipeline has been optimized for efficiency:

- **Reduced matrix**: Python 3.9 only tested on Ubuntu
- **Conditional jobs**: Linting/formatting only runs on Ubuntu 3.12
- **Caching**: Conda packages are cached to speed up builds
- **Single coverage upload**: Only Ubuntu 3.12 uploads to Codecov

## Best Practices

- Keep workflows fast (< 10 minutes when possible)
- Use caching for conda/pip packages
- Run expensive checks (linting, coverage) only once
- Use `continue-on-error` for non-blocking checks
- Add workflow_dispatch for manual testing
- Add informative test summaries

## Removed Workflows

The following redundant workflows were removed to simplify maintenance:

- `tests.yml` - Replaced by comprehensive CI/CD pipeline
- `test-vanna-grok.yml` - Tests integrated into main pipeline
- `claude-code-review.yml` - Functionality covered by claude.yml
