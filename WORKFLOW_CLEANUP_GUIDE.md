# GitHub Actions Workflow Cleanup Guide

## Summary
This guide provides step-by-step instructions to clean up and optimize your GitHub Actions workflows.

## Current State
You have **7 workflows** with significant redundancy and overlap.

## Recommended Final State
**4 optimized workflows** that cover all your needs without redundancy.

## Step-by-Step Cleanup Instructions

### Step 1: Delete Redundant Workflows

Delete these workflow files:

```bash
rm .github/workflows/claude-code-review.yml
rm .github/workflows/test-vanna-grok.yml
```

**Reason**:
- `claude-code-review.yml` duplicates functionality in `claude.yml`
- `test-vanna-grok.yml` tests are now included in the consolidated test workflow

### Step 2: Replace Testing Workflows

1. **Delete old test workflows:**
   ```bash
   rm .github/workflows/python-package-conda.yml
   rm .github/workflows/tests.yml
   ```

2. **Copy the new consolidated workflow:**
   ```bash
   cp proposed-test-workflow.yml .github/workflows/tests.yml
   ```

3. **Review and adjust** the new `tests.yml` if needed (check Python versions, dependencies, etc.)

### Step 3: Keep Security Workflows As-Is

These workflows are already optimized:
- ✅ `.github/workflows/codeql-analysis.yml`
- ✅ `.github/workflows/dependency-review.yml`
- ✅ `.github/workflows/claude.yml`

No changes needed for these files.

### Step 4: Commit Changes

```bash
git add .github/workflows/
git add proposed-test-workflow.yml WORKFLOW_CLEANUP_GUIDE.md
git commit -m "chore: cleanup and consolidate GitHub Actions workflows

- Remove redundant claude-code-review.yml (duplicate of claude.yml)
- Remove test-vanna-grok.yml (consolidated into main tests)
- Consolidate python-package-conda.yml and tests.yml into single optimized workflow
- Reduce test matrix from 12 jobs to 2 jobs (ubuntu-latest, Python 3.10 & 3.12)
- Update codecov action to v4 with token support
- Update safety check command to use --json flag
- Add proposed consolidated workflow and cleanup guide

Resolves #25"
git push origin claude/issue-25-20260102-2146
```

## Benefits of This Cleanup

### Resource Savings
- **Before**: 12+ parallel CI jobs per push (from python-package-conda.yml alone)
- **After**: 2 parallel CI jobs per push
- **Savings**: ~83% reduction in CI minutes

### Maintainability
- **Before**: 7 workflows to maintain
- **After**: 4 workflows to maintain
- **Benefit**: Easier to update and debug

### Clarity
- No more duplicate/overlapping workflows
- Clear separation of concerns:
  - `tests.yml` → Testing
  - `codeql-analysis.yml` → Security scanning
  - `dependency-review.yml` → Dependency security
  - `claude.yml` → AI assistance

## What Changed in the Consolidated Workflow

### Optimizations
1. **Reduced matrix**: Only ubuntu-latest (removed Windows/macOS)
2. **Reduced Python versions**: 3.10 and 3.12 only (removed 3.9, 3.11)
3. **Merged all tests**: Includes vanna_grok tests, basic tests, and full tests
4. **Updated dependencies**: Codecov v4, safety with --json flag
5. **Better caching**: Pip cache for faster runs

### Kept Features
- ✅ Conda environment support
- ✅ All linting (flake8, black, isort, mypy)
- ✅ Full test coverage with pytest
- ✅ Security scanning (bandit, safety)
- ✅ Package building and validation
- ✅ Coverage upload to Codecov
- ✅ Microsoft ODBC driver installation

## If You Need Platform-Specific Testing

If you later determine you need Windows or macOS testing:

```yaml
# In .github/workflows/tests.yml, update the matrix:
strategy:
  fail-fast: false
  matrix:
    os: [ubuntu-latest, windows-latest, macos-latest]
    python-version: ['3.10', '3.12']
runs-on: ${{ matrix.os }}
```

But based on your codebase (database utilities), Ubuntu-only testing should be sufficient.

## Codecov Token Setup

If you use Codecov, make sure to add the token to your repository secrets:

1. Go to https://codecov.io and get your repository token
2. Add it to GitHub: Settings → Secrets and variables → Actions → New repository secret
3. Name: `CODECOV_TOKEN`
4. Value: Your Codecov token

If you don't use Codecov, you can remove the "Upload coverage to Codecov" step.

## Questions?

If you have any questions about these changes, feel free to ask in issue #25.
