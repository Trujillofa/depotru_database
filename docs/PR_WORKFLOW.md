# AI Agent Pull Request Workflow

This document outlines the recommended workflow when multiple AI agents are collaborating on this repository.

## Why Use Pull Requests?

- **Code Review**: Each agent can review changes made by others
- **Quality Control**: Tests must pass before merging
- **Coordination**: Prevents conflicts when multiple agents work simultaneously
- **Rollback Safety**: Easy to revert if issues are found
- **Documentation**: PRs preserve context and decision history

## Branch Naming Convention

Use the following prefixes for branch names:

| Prefix | Purpose | Example |
|--------|---------|---------|
| `feature/` | New features | `feature/add-customer-api` |
| `fix/` | Bug fixes | `fix/database-connection` |
| `docs/` | Documentation | `docs/update-readme` |
| `test/` | Test additions | `test/add-unit-tests` |
| `refactor/` | Code refactoring | `refactor/extract-utils` |
| `chore/` | Maintenance tasks | `chore/update-dependencies` |
| `agent/` | Agent-specific work | `agent/claude-analysis` |

## Workflow Steps

### 1. Create a Feature Branch

```bash
# Ensure you're on main and it's up to date
git checkout main
git pull origin main

# Create and switch to feature branch
git checkout -b feature/your-feature-name
```

### 2. Make Changes

```bash
# Make your changes
git add .
git commit -m "feat: descriptive commit message"
```

### 3. Push Branch

```bash
# First time pushing a new branch
git push -u origin feature/your-feature-name
```

### 4. Create Pull Request

```bash
# Using GitHub CLI
gh pr create --title "feat: brief description" \
             --body "Detailed description of changes" \
             --base main
```

Or use the GitHub web interface.

### 5. Review Process

Before merging, ensure:
- [ ] All tests pass (304 tests)
- [ ] Code review completed by at least one other agent
- [ ] No merge conflicts
- [ ] Documentation updated if needed
- [ ] Commit messages follow semantic convention

### 6. Merge

```bash
# Using GitHub CLI
gh pr merge --squash

# Or merge via GitHub web interface
```

## PR Template

When creating a PR, use this template:

```markdown
## Summary
Brief description of what this PR does.

## Changes
- List of specific changes made
- New features added
- Bugs fixed
- Tests added

## Testing
- [ ] All tests pass (`pytest tests/ -v`)
- [ ] New tests added for new features
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Documentation updated
- [ ] No breaking changes (or clearly documented)
- [ ] Commit messages are clear and descriptive

## Related
- Links to related issues or PRs
- References to documentation
```

## Multi-Agent Coordination

### When Multiple Agents Work Together:

1. **Communication**: Leave comments on PRs explaining reasoning
2. **Small PRs**: Keep changes focused and reviewable (< 500 lines)
3. **Fast Feedback**: Review PRs within 24 hours when possible
4. **Resolve Conflicts**: Rebase feature branches when main changes

### Example Multi-Agent Scenario:

```
Agent 1: Creates PR #10 (database changes)
         ↓
Agent 2: Reviews PR #10, requests changes
         ↓
Agent 1: Updates PR #10
         ↓
Agent 2: Approves and merges PR #10
         ↓
Agent 3: Creates PR #11 (analysis features, based on updated main)
         ↓
Agent 1 & 2: Review PR #11
         ↓
Agent 3: Merges PR #11
```

## Branch Protection Rules (Recommended)

The following rules should be enabled on the `main` branch:

1. **Require pull request reviews** (1 reviewer minimum)
2. **Require status checks to pass** (CI tests)
3. **Require linear history** (no merge commits)
4. **Include administrators** (rules apply to everyone)
5. **Restrict pushes** (no direct pushes to main)

## Emergency Procedures

### If You Accidentally Push to Main:

```bash
# Don't panic! Create a revert PR
git checkout main
git revert HEAD  # Creates a new commit that undoes the last commit
git push origin main

# Then create a proper feature branch with your changes
git checkout -b feature/your-changes
git cherry-pick <commit-hash>  # Apply your original changes
git push -u origin feature/your-changes
gh pr create
```

### Hotfix Process:

For critical production fixes that need immediate attention:

```bash
# Create hotfix branch from main
git checkout main
git pull origin main
git checkout -b hotfix/critical-fix

# Make minimal fix
git add .
git commit -m "fix: critical production issue"
git push -u origin hotfix/critical-fix

# Create PR with "hotfix" label
gh pr create --title "hotfix: critical issue" --label "hotfix"

# Fast-track review and merge
```

## Useful Commands

```bash
# Check branch status
git status

# See commits not on main
git log main..HEAD --oneline

# See files changed
git diff main --stat

# Update feature branch with main changes
git checkout main
git pull origin main
git checkout feature/your-branch
git rebase main

# List open PRs
gh pr list

# Check PR status
gh pr view

# Review a PR
gh pr checkout <pr-number>
# Review code, then:
gh pr review --approve
# or
gh pr review --request-changes --body "Please fix..."
```

## Questions?

If you're unsure about the workflow:
1. Check this document first
2. Look at existing PRs for examples
3. Ask in PR comments
4. When in doubt, create a PR for review rather than pushing directly

---

**Remember**: PRs are about collaboration and quality. They may take a few extra minutes but save hours of debugging later!
