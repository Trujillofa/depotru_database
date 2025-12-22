# Contributing to Business Data Analyzer

Thank you for considering contributing! This document outlines the process and guidelines.

## 🚀 Getting Started

1. **Fork the repository**
2. **Clone your fork**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/coding_omarchy.git
   cd coding_omarchy
   ```
3. **Set up your environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

## 📋 Development Workflow

### 1. Create a Branch

```bash
# Create and switch to a new branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/bug-description
```

### 2. Make Your Changes

- Write clean, readable code
- Follow PEP 8 style guidelines
- Add docstrings to functions and classes
- Update documentation if needed

### 3. Test Your Changes

```bash
# Format code
black *.py

# Check for style issues
flake8 *.py

# Run tests (if available)
pytest
```

### 4. Commit Your Changes

```bash
git add .
git commit -m "type: description

Detailed explanation of changes (if needed)"
```

**Commit message types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

### 5. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

## 🎯 Contribution Guidelines

### Code Style

- Follow PEP 8
- Use type hints for function parameters and return values
- Maximum line length: 100 characters
- Use meaningful variable names
- Add comments for complex logic

**Example:**
```python
def calculate_metrics(data: List[Dict[str, Any]]) -> Dict[str, float]:
    """Calculate business metrics from data.

    Args:
        data: List of dictionaries containing business data

    Returns:
        Dictionary with calculated metrics
    """
    # Implementation
    pass
```

### Documentation

- Update README.md if adding new features
- Add docstrings to all functions and classes
- Update type hints
- Include usage examples for new functionality

### Testing

- Add tests for new features
- Ensure existing tests pass
- Test edge cases
- Test error handling

### Security

- Never commit credentials or secrets
- Use environment variables for sensitive data
- Follow guidelines in SECURITY.md
- Report security issues privately

## 🐛 Reporting Bugs

**Before submitting:**
1. Check if the bug was already reported
2. Ensure you're using the latest version
3. Check documentation for known issues

**When submitting:**
- Clear, descriptive title
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, etc.)
- Error messages and logs
- Screenshots if applicable

**Template:**
```markdown
### Description
[Clear description of the bug]

### Steps to Reproduce
1. Step 1
2. Step 2
3. Step 3

### Expected Behavior
[What should happen]

### Actual Behavior
[What actually happens]

### Environment
- OS: [e.g., Ubuntu 22.04]
- Python version: [e.g., 3.9.5]
- Package versions: [from pip list]

### Additional Context
[Any other relevant information]
```

## 💡 Suggesting Features

**Good feature requests include:**
- Clear use case and benefit
- Detailed description
- Examples of how it would work
- Consideration of alternatives
- Willingness to contribute implementation

## 📝 Pull Request Process

1. **Update documentation** for any new features
2. **Add tests** for new functionality
3. **Ensure all tests pass**
4. **Update CHANGELOG.md** if applicable
5. **One feature per PR** - keep changes focused
6. **Reference related issues** in the PR description

### PR Checklist

- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] All tests passing
- [ ] No new warnings introduced
- [ ] Commit messages are clear

## 🔍 Code Review Process

1. Maintainers will review your PR
2. Address any feedback or requested changes
3. Once approved, your PR will be merged
4. Your contribution will be credited

## 📜 Code of Conduct

### Our Standards

**Positive behaviors:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what's best for the community
- Showing empathy towards others

**Unacceptable behaviors:**
- Harassment or discriminatory comments
- Trolling or insulting comments
- Personal or political attacks
- Publishing others' private information
- Other unprofessional conduct

## 🏆 Recognition

Contributors will be:
- Added to AUTHORS.md
- Mentioned in release notes
- Credited in relevant documentation

## 📞 Questions?

- Open a discussion on GitHub
- Check existing documentation
- Ask in pull request comments

## 📄 License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing! 🎉
