# Multi-Version Python Testing with Anaconda

This guide explains how to test the Business Data Analyzer package across multiple Python versions using Anaconda/Miniconda for package management.

## Overview

The project supports Python 3.8, 3.9, 3.10, and 3.11. We use Conda environments to ensure consistent, reproducible builds across all versions.

## Quick Start

### 1. Install Miniconda (if not already installed)

**Linux/macOS:**
```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
# Follow prompts, then restart shell
```

**Windows:**
Download from https://docs.conda.io/en/latest/miniconda.html

### 2. Create Environment from YAML

```bash
# Create environment from environment.yml
conda env create -f environment.yml

# Activate the environment
conda activate business-analyzer
```

### 3. Verify Installation

```bash
# Check Python version
python --version

# Check installed packages
conda list

# Run tests
pytest tests/ -v
```

## Testing Across Multiple Python Versions

### Manual Testing

Test on each Python version manually:

```bash
# Python 3.8
conda create -n test-py38 python=3.8 -y
conda activate test-py38
pip install -r requirements.txt
pytest tests/ -v
conda deactivate

# Python 3.9
conda create -n test-py39 python=3.9 -y
conda activate test-py39
pip install -r requirements.txt
pytest tests/ -v
conda deactivate

# Python 3.10
conda create -n test-py310 python=3.10 -y
conda activate test-py310
pip install -r requirements.txt
pytest tests/ -v
conda deactivate

# Python 3.11
conda create -n test-py311 python=3.11 -y
conda activate test-py311
pip install -r requirements.txt
pytest tests/ -v
conda deactivate
```

### Automated Testing (Script)

Create `test_all_versions.sh`:

```bash
#!/bin/bash

VERSIONS=("3.8" "3.9" "3.10" "3.11")
PASSED=0
FAILED=0

for VERSION in "${VERSIONS[@]}"; do
    ENV_NAME="test-py${VERSION//.}"
    echo "========================================="
    echo "Testing Python $VERSION"
    echo "========================================="

    # Create environment
    conda create -n "$ENV_NAME" python="$VERSION" -y
    conda activate "$ENV_NAME"

    # Install dependencies
    pip install -r requirements.txt
    pip install pytest pytest-cov

    # Run tests
    if pytest tests/ -v --cov=src; then
        echo "✅ Python $VERSION: PASSED"
        ((PASSED++))
    else
        echo "❌ Python $VERSION: FAILED"
        ((FAILED++))
    fi

    # Cleanup
    conda deactivate
    conda env remove -n "$ENV_NAME" -y
done

echo ""
echo "========================================="
echo "SUMMARY"
echo "========================================="
echo "Passed: $PASSED/${#VERSIONS[@]}"
echo "Failed: $FAILED/${#VERSIONS[@]}"
```

Run it:
```bash
chmod +x test_all_versions.sh
./test_all_versions.sh
```

## GitHub Actions CI/CD

The project includes automated testing via GitHub Actions. See `.github/workflows/tests.yml` and `.github/workflows/test-vanna-grok.yml`.

### Workflow Features

✅ **Multi-version testing** (Python 3.10, 3.11, 3.12)
✅ **Dependency management** (with and without optional dependencies)
✅ **Coverage reporting** (Codecov)
✅ **Security scanning** (CodeQL, dependency review)

### Triggering Workflows

Workflows run automatically on:
- Push to `main` or `copilot/**` branches
- Pull requests to `main`
- Manual trigger via GitHub UI
- Weekly security scans (CodeQL)

### Viewing Results

1. Go to your GitHub repository
2. Click **Actions** tab
3. Select a workflow run to see results

## Local Package Building

### Build Source and Wheel Distributions

```bash
# Install build tools
pip install build wheel setuptools

# Build package
python -m build

# Output: dist/business-data-analyzer-2.0.0.tar.gz
#         dist/business_data_analyzer-2.0.0-py3-none-any.whl
```

### Test Installation

```bash
# Install locally
pip install dist/business_data_analyzer-2.0.0-py3-none-any.whl

# Test console scripts
business-analyzer --help
vanna-grok --help
vanna-chat --help
```

## Conda Environment Management

### Common Commands

```bash
# List all environments
conda env list

# Create environment
conda create -n myenv python=3.10

# Activate environment
conda activate myenv

# Deactivate environment
conda deactivate

# Remove environment
conda env remove -n myenv

# Export environment (for sharing)
conda env export > environment.yml

# Update environment from YAML
conda env update -f environment.yml --prune
```

### Best Practices

1. **Use environment.yml for reproducibility**
   ```bash
   conda env create -f environment.yml
   ```

2. **Pin versions in production**
   ```yaml
   dependencies:
     - python=3.10.8
     - pip
     - pip:
       - pandas==1.5.3
   ```

3. **Separate dev/prod environments**
   ```bash
   # Development
   conda activate business-analyzer-dev

   # Production
   conda activate business-analyzer-prod
   ```

## Troubleshooting

### Issue: Conda command not found

**Solution:**
```bash
# Add conda to PATH (Linux/macOS)
export PATH="$HOME/miniconda3/bin:$PATH"

# Or initialize conda
~/miniconda3/bin/conda init bash
source ~/.bashrc
```

### Issue: Environment conflicts

**Solution:**
```bash
# Remove and recreate environment
conda env remove -n business-analyzer
conda env create -f environment.yml
```

### Issue: Package installation fails

**Solution:**
```bash
# Update conda
conda update conda

# Clear cache
conda clean --all

# Try installing with pip in conda env
conda activate business-analyzer
pip install --upgrade pip
pip install -r requirements.txt
```

### Issue: Tests fail on specific Python version

**Solution:**
```bash
# Check Python version compatibility
python -c "import sys; print(sys.version)"

# Check package versions
pip list

# Compare with requirements.txt
pip check
```

## Development Workflow

### 1. Setup Development Environment

```bash
# Clone repository
git clone https://github.com/Trujillofa/coding_omarchy.git
cd coding_omarchy

# Create Conda environment
conda env create -f environment.yml
conda activate business-analyzer

# Install development dependencies
pip install pytest pytest-cov black flake8 mypy isort
```

### 2. Make Changes

```bash
# Create feature branch
git checkout -b feature/my-improvement

# Make your changes
vim src/vanna_grok.py

# Format code
black src/ tests/
isort src/ tests/
```

### 3. Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# View coverage report
open htmlcov/index.html
```

### 4. Validate Code Quality

```bash
# Lint
flake8 src/ tests/

# Type check
mypy src/

# Security check
bandit -r src/
```

### 5. Test on Multiple Versions

```bash
# Quick test (3.8, 3.11 only)
for version in 3.8 3.11; do
    conda create -n test-py${version//.} python=$version -y
    conda activate test-py${version//.}
    pip install -r requirements.txt
    pytest tests/ -v
    conda deactivate
done
```

### 6. Commit and Push

```bash
git add .
git commit -m "feat: Add awesome feature"
git push origin feature/my-improvement
```

## CI/CD Pipeline Details

### Workflow Stages

1. **Checkout** - Get latest code
2. **Setup Conda** - Install Miniconda and create environment
3. **Install Dependencies** - Install package + dev tools
4. **Lint** - flake8 syntax checking
5. **Format Check** - black, isort validation
6. **Type Check** - mypy static analysis
7. **Test** - pytest with coverage
8. **Security Scan** - bandit, safety, CodeQL
9. **Build Package** - Verify setup.py works
10. **Upload Artifacts** - Coverage + build artifacts

### Environment Variables for CI

Tests run with mock credentials:
```bash
DB_SERVER=test-server
DB_NAME=TestDB
DB_USER=test_user
DB_PASSWORD=test_password
GROK_API_KEY=xai-test-key-for-ci
```

**Important:** Real credentials are never committed to git!

## Performance Comparison

| Method | Setup Time | Test Time | Isolation |
|--------|-----------|-----------|-----------|
| **Conda (recommended)** | 30s | Fast | Excellent |
| **venv** | 10s | Fast | Good |
| **Docker** | 2min | Medium | Excellent |
| **Global pip** | 5s | Fast | None (risky) |

## References

- [Conda Documentation](https://docs.conda.io/)
- [GitHub Actions + Conda](https://github.com/conda-incubator/setup-miniconda)
- [Python Packaging Guide](https://packaging.python.org/)
- [pytest Documentation](https://docs.pytest.org/)

## Next Steps

After setting up multi-version testing:

1. ✅ Run tests locally on all Python versions
2. ✅ Push to GitHub and verify CI passes
3. ✅ Review coverage report
4. ✅ Fix any version-specific issues
5. 📦 Build package for distribution
6. 🚀 Deploy to PyPI (optional)

---

**Questions?** See [docs/CONTRIBUTING.md](CONTRIBUTING.md) or open an issue.
