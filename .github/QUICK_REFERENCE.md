# Quick Reference for AI Agents

## 🚀 Quick Start

```bash
# 1. Setup environment
cp .env.example .env
# Edit .env with real credentials

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run tests
pytest tests/ -v

# 4. Start application
python src/vanna_grok.py
# Visit http://localhost:8084
```

## 📁 Key Files

| File | Purpose |
|------|---------|
| `src/vanna_grok.py` | Main app - Natural language SQL |
| `tests/test_*.py` | Test suite |
| `.github/agents/business-data-analyzer.agent.md` | Custom GitHub Copilot agent |
| `docs/AI_AGENT_INSTRUCTIONS.md` | Full instructions (READ THIS!) |
| `docs/ROADMAP.md` | Development plan |
| `.env.example` | Configuration template |

## 🔧 Common Commands

```bash
# Testing
pytest tests/ -v                          # Run all tests
pytest tests/ --cov=src                   # With coverage
pytest tests/test_formatting.py -v        # Specific file

# Code quality
black src/ tests/                         # Format code
isort src/ tests/                         # Sort imports
flake8 src/ tests/                        # Lint

# Git
git checkout -b claude/feature-name-SessionID
git add <files>
git commit -m "type: description"
git push -u origin claude/branch-SessionID

# Package build
python -m build                           # Build package
twine check dist/*                        # Validate
```

## 🎯 Development Checklist

Before committing:
- [ ] Tests pass: `pytest tests/ -v`
- [ ] Code formatted: `black src/ tests/`
- [ ] No lint errors: `flake8 src/ tests/`
- [ ] Documentation updated
- [ ] No hardcoded credentials
- [ ] Colombian formatting preserved
- [ ] Spanish language for user messages

## 🇨🇴 Colombian Formatting

```python
# Always use format_number()
format_number(1234567, "TotalMasIva")      # → "$1.234.567"
format_number(45.6, "Margen_Promedio_Pct") # → "45,6%"
format_number(1234, "Cantidad")            # → "1.234"
```

## 🔐 Security

```python
# ✅ Use require_env()
API_KEY = require_env("GROK_API_KEY")

# ❌ Never hardcode
API_KEY = "xai-1234567890"  # WRONG!
```

## 🐛 Debugging

```bash
# Database connection
sqlcmd -S $DB_SERVER -U $DB_USER -P $DB_PASSWORD -d $DB_NAME -Q "SELECT 1"

# Test API key
curl -H "Authorization: Bearer $GROK_API_KEY" https://api.x.ai/v1/models

# Python debugger
python -m pdb src/vanna_grok.py
```

## 📊 Current Status

**Phase:** Path A (Quick Wins) - ✅ COMPLETE
**Next:** Path B (Team Enablement)

**Test Coverage:** ~85%
**Python Versions:** 3.8, 3.9, 3.10, 3.11
**CI/CD:** GitHub Actions (auto-runs on push)

## 🚨 Critical Rules

1. **NEVER commit .env file** (has secrets)
2. **ALWAYS use Colombian formatting** for numbers
3. **ALWAYS write in Spanish** for user messages
4. **ALWAYS add tests** for new features
5. **ALWAYS exclude test docs**: `WHERE DocumentosCodigo NOT IN ('XY', 'AS', 'TS')`
6. **Branch names** must start with `claude/` and end with SessionID

## 📚 Full Documentation

For complete instructions, see:
**[docs/AI_AGENT_INSTRUCTIONS.md](../docs/AI_AGENT_INSTRUCTIONS.md)**

## 🤖 Using the Custom GitHub Copilot Agent

This repository has a custom GitHub Copilot agent called `@business-data-analyzer` that is specialized for this project. The agent is automatically available when using GitHub Copilot in:

- **GitHub.com** (PR comments, issue discussions)
- **VS Code** (with GitHub Copilot extension)
- **JetBrains IDEs** (with GitHub Copilot plugin)
- **GitHub Copilot CLI** (command line)

### How to Use the Agent

In GitHub Copilot chat or comments, mention the agent:

```
@business-data-analyzer help me fix this margin calculation bug
@business-data-analyzer add tests for the Colombian peso formatting
@business-data-analyzer review this PR for security issues
```

The agent has context about:
- Colombian business formatting (pesos, percentages)
- Vanna AI and Grok API integration
- Spanish language requirements
- Database schema and business metrics
- Project structure and conventions
- Testing and security requirements

### Agent Location

The agent definition is in: `.github/agents/business-data-analyzer.agent.md`

This file is version-controlled and can be updated as the project evolves.

---

**Need help?** Read AI_AGENT_INSTRUCTIONS.md first, then check other docs/ files.
