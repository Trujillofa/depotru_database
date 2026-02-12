# GitHub Release Notes Template

Use this template when creating a new GitHub Release.

---

## Release Title Format
```
v{VERSION} - {SHORT_DESCRIPTION}
```

Example: `v2.0.0 - Modular Architecture & Multi-Provider AI`

---

## Release Notes Template

```markdown
## 🎉 What's New

### Major Features
- **Modular Architecture**: Complete refactoring from monolithic 1,690-line file to 21 focused modules (~84 lines each)
- **Multi-Provider AI Support**: Choose from Grok (xAI), OpenAI GPT-4, Anthropic Claude, or Ollama (local)
- **Comprehensive Test Suite**: 200+ tests with ~54% coverage (up from ~17%)
- **CI/CD Pipeline**: Automated testing, linting, type checking, and building via GitHub Actions
- **Security Hardening**: Bandit security scanning, SQL injection prevention, credential management

### New Modules
- `business_analyzer/core/` - Database, config, validation
- `business_analyzer/analysis/` - Customer, product, financial, inventory analyzers
- `business_analyzer/ai/` - Multi-provider AI package with 4 provider backends
- `business_analyzer/utils/` - Encoding, math, Navicat utilities

### Improvements
- Documentation consolidated from 23 files to 3 core documents
- Modern pyproject.toml packaging (PEP 621)
- Pre-commit hooks for code quality
- Performance benchmarks established
- Colombian number formatting preserved

### Breaking Changes
None - fully backward compatible

### Migration Notes
- Update `.env` to optionally use `AI_PROVIDER` variable
- Install with: `pip install -e ".[dev]"`
- All existing scripts continue to work

## 📊 Statistics

| Metric | Value |
|--------|-------|
| Test Coverage | ~54% |
| Tests Passing | 256/282 |
| Python Files | 43 |
| Documentation | 7 active + 13 archived |
| CI Jobs | 5 |
| Security Issues | 0 |

## 🙏 Contributors

- Business Data Analyzer Team
- Claude (AI Assistant) - Architecture & implementation
- GitHub Copilot - Code review & security

## 📦 Installation

```bash
# From PyPI (when published)
pip install business-data-analyzer

# From source
git clone https://github.com/Trujillofa/coding_omarchy.git
cd coding_omarchy
pip install -e ".[dev]"
```

## 🔗 Links

- [Full Changelog](CHANGELOG.md)
- [Documentation](docs/START_HERE.md)
- [Contributing Guide](docs/CONTRIBUTING.md)
- [Security Policy](docs/SECURITY.md)
```

---

## Checklist for Release

- [ ] Version bumped in `pyproject.toml`
- [ ] `CHANGELOG.md` updated with all changes
- [ ] All tests passing (or known failures documented)
- [ ] Distribution packages built (`python -m build`)
- [ ] Git tag created: `git tag -a v2.0.0 -m "Release v2.0.0"`
- [ ] Tag pushed: `git push origin v2.0.0`
- [ ] GitHub Release created using this template
- [ ] Release notes include migration guide
- [ ] Assets attached (sdist and wheel)

---

## Tag Creation Commands

```bash
# Create annotated tag
git tag -a v2.0.0 -m "Release v2.0.0 - Modular Architecture & Multi-Provider AI"

# Push tag (triggers release workflow if configured)
git push origin v2.0.0

# Push branch
git push origin main
```

---

## Asset Upload

Attach these files to the GitHub Release:
1. `dist/business_data_analyzer-2.0.0.tar.gz` (sdist)
2. `dist/business_data_analyzer-2.0.0-py3-none-any.whl` (wheel, if built)

---

## Pre-Release vs Stable

- **Pre-release**: Check "This is a pre-release" box for RC/beta versions
- **Stable**: Uncheck for official releases
- **Latest**: GitHub automatically marks the newest non-pre-release as "Latest"

---

## Notes

- GitHub Releases can be created via web UI or API
- Release notes support Markdown formatting
- Assets can be dragged & dropped into the release form
- Tags can be created before or during release creation
