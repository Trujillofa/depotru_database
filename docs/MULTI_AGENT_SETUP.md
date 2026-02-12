# 🤖 Multi-Agent Setup Guide

This guide explains how to set up and use multiple AI agents (Claude Code, Gemini CLI, OpenCode/Sisyphus) for collaborative development on this repository.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture Overview](#architecture-overview)
3. [Agent Roles](#agent-roles)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Workflow Examples](#workflow-examples)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# 1. Install agent tools
chmod +x scripts/install-agents.sh
./scripts/install-agents.sh

# 2. Configure agents
cp .agents/config.template.yml .agents/config.yml
# Edit .agents/config.yml with your preferences

# 3. Start working with multiple agents
# See Workflow Examples section below
```

---

## Architecture Overview

We use a **Hub-and-Spoke** architecture with OpenCode/Sisyphus as the coordinator:

```
                    ┌──────────────────┐
                    │   Coordinator    │
                    │  (OpenCode/      │
                    │   Sisyphus)      │
                    └────────┬─────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ↓                    ↓                    ↓
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Claude Code  │   │ Gemini CLI   │   │  Specialist  │
│ (Architecture)│   │ (Research)   │   │   Agents     │
└──────────────┘   └──────────────┘   └──────────────┘
```

### Why This Architecture?

- **Single point of coordination**: Sisyphus routes tasks and manages conflicts
- **Specialized agents**: Each agent focuses on what it does best
- **Scalable**: Easy to add new agents
- **Conflict resolution**: Coordinator manages disagreements

---

## Agent Roles

### 🤖 Claude Code (Anthropic)

**Role**: Senior Architect & Complex Problem Solver

**Best For**:
- Complex refactoring
- Architecture design
- Debugging tricky issues
- Code review
- Security audits

**Strengths**:
- Deep reasoning
- Context understanding
- Code quality

**Branch Prefix**: `agent/claude/`

**Usage**:
```bash
# Start Claude Code in project directory
claude code .

# Non-interactive mode
claude code . --prompt "Refactor the database module"
```

---

### 🔷 Gemini CLI (Google)

**Role**: Fast Implementer & Researcher

**Best For**:
- Quick feature implementation
- Research and documentation
- Web searches
- Test writing
- Code generation

**Strengths**:
- Speed
- Web grounding
- 1M token context
- Free tier available

**Branch Prefix**: `agent/gemini/`

**Usage**:
```bash
# Start Gemini CLI
gemini

# Include specific directories
gemini --include-directories ../lib,../docs

# Non-interactive mode
gemini -p "Generate tests for customer module" --output-format json
```

---

### 🎯 OpenCode/Sisyphus (Current)

**Role**: Coordinator & Orchestrator

**Best For**:
- Task routing
- Conflict resolution
- Project management
- CI/CD coordination
- Quality assurance

**Strengths**:
- Task decomposition
- Parallel execution
- Git workflow expertise
- Integration with existing tools

**Branch Prefix**: `agent/opencode/`

---

## Installation

### Prerequisites

- Node.js 18+ (for Claude Code and Gemini CLI)
- Python 3.8+ (for Aider and existing tools)
- Git

### Install All Agents

```bash
# Run the installation script
chmod +x scripts/install-agents.sh
./scripts/install-agents.sh
```

### Manual Installation

#### Claude Code
```bash
npm install -g @anthropic-ai/claude-code
claude login
```

#### Gemini CLI
```bash
npm install -g @google/gemini-cli
gemini login
```

#### Aider (Optional - for pair programming)
```bash
pip install aider-chat
```

---

## Configuration

### Agent Configuration File

Create `.agents/config.yml`:

```yaml
# Agent Configuration
# This file defines agent roles, capabilities, and routing rules

agents:
  claude:
    name: "Claude Code"
    provider: "anthropic"
    role: "architect"
    priority: 1
    capabilities:
      - refactoring
      - architecture
      - debugging
      - security_audit
      - code_review
    branch_prefix: "agent/claude"
    config_file: ".agents/claude/CLAUDE.md"
    
  gemini:
    name: "Gemini CLI"
    provider: "google"
    role: "implementer"
    priority: 2
    capabilities:
      - implementation
      - research
      - documentation
      - testing
      - code_generation
    branch_prefix: "agent/gemini"
    config_file: ".agents/gemini/GEMINI.md"
    
  opencode:
    name: "OpenCode/Sisyphus"
    provider: "opencode"
    role: "coordinator"
    priority: 0
    capabilities:
      - coordination
      - task_routing
      - conflict_resolution
      - project_management
    branch_prefix: "agent/opencode"
    config_file: ".agents/opencode/SISYPHUS.md"

# Task Routing Rules
routing:
  architecture:
    agents: [claude]
    confidence_threshold: 0.8
    
  implementation:
    agents: [gemini, claude]
    confidence_threshold: 0.7
    
  debugging:
    agents: [claude]
    confidence_threshold: 0.8
    
  testing:
    agents: [gemini, claude]
    confidence_threshold: 0.6
    
  documentation:
    agents: [gemini]
    confidence_threshold: 0.6
    
  research:
    agents: [gemini]
    confidence_threshold: 0.7

# Consensus Settings
consensus:
  method: "weighted_voting"
  min_agents: 2
  threshold: 0.7
  escalate_to_human: true
  
  weights:
    claude: 0.4
    gemini: 0.3
    opencode: 0.3

# Workflow Settings
workflow:
  require_pr: true
  require_review: true
  min_reviewers: 1
  auto_merge: false
```

### Agent-Specific Instructions

#### Claude Code Instructions (`.agents/claude/CLAUDE.md`)

```markdown
# Claude Code Agent Configuration

## Your Role
You are a Senior Software Architect working on a Business Intelligence 
platform for a Colombian hardware store.

## Specialties
- Complex refactoring and architecture design
- Debugging production issues
- Code review and quality assurance
- Security audits

## Workflow
1. Create feature branches: `agent/claude/<task-description>`
2. Use PR workflow - never push to main directly
3. Write comprehensive commit messages
4. Document architectural decisions in PR descriptions
5. Review other agents' work thoroughly

## Code Style
- Follow existing patterns in the codebase
- Prefer clarity over cleverness
- Add type hints to new functions
- Include docstrings for public APIs

## Communication
- Explain your reasoning in PR comments
- Ask questions when requirements are unclear
- Suggest improvements proactively
- Be respectful to other agents' contributions

## Key Files
- `src/business_analyzer/core/` - Core functionality
- `docs/ARCHITECTURE.md` - Architecture decisions
- `pyproject.toml` - Project configuration

## Testing
- Run tests before committing: `pytest tests/ -v`
- Aim for >80% coverage on new code
- Use existing fixtures and utilities
```

#### Gemini CLI Instructions (`.agents/gemini/GEMINI.md`)

```markdown
# Gemini CLI Agent Configuration

## Your Role
You are a Fast Implementer and Researcher working on a Business Intelligence 
platform for a Colombian hardware store.

## Specialties
- Quick feature implementation
- Research and documentation
- Test writing
- Code generation
- Web searches for solutions

## Workflow
1. Create feature branches: `agent/gemini/<task-description>`
2. Focus on speed + quality balance
3. Follow existing code patterns
4. Always include tests for new features
5. Update documentation when needed

## Speed Guidelines
- Small features: < 30 minutes
- Medium features: < 2 hours
- Research tasks: < 1 hour
- Documentation: < 30 minutes

## Research First
When starting a task:
1. Search for similar implementations in the codebase
2. Check existing patterns and conventions
3. Look up best practices if needed
4. Then implement

## Communication
- Report progress frequently
- Flag blockers immediately
- Celebrate quick wins!
- Ask for help when stuck

## Testing
- Write tests alongside implementation
- Run tests often: `pytest tests/ -v -k <test_name>`
- Mock external dependencies
```

#### OpenCode/Sisyphus Instructions (`.agents/opencode/SISYPHUS.md`)

```markdown
# OpenCode/Sisyphus Agent Configuration

## Your Role
You are the Coordinator and Orchestrator for a multi-agent development team.

## Responsibilities
1. Route tasks to appropriate agents
2. Manage conflicts and disagreements
3. Ensure code quality standards
4. Coordinate PR reviews
5. Maintain project momentum

## Task Routing
Analyze incoming tasks and assign to best agent:

- **Architecture/Design** → Claude
- **Research/Web** → Gemini
- **Quick Implementation** → Gemini
- **Complex Debugging** → Claude
- **Testing** → Both (parallel)
- **Documentation** → Gemini
- **Review** → Either (not original author)

## Conflict Resolution
When agents disagree:
1. Analyze both positions objectively
2. Check against project requirements
3. Consider trade-offs
4. Make decision or escalate to human
5. Document reasoning

## Quality Gates
Before approving PRs:
- [ ] All tests pass
- [ ] Code review completed
- [ ] Documentation updated
- [ ] No merge conflicts
- [ ] Commit history is clean

## Coordination Patterns
- **Sequential**: One agent at a time (for complex tasks)
- **Parallel**: Multiple agents on different files
- **Review Cycle**: Agent A implements, Agent B reviews

## Emergency Procedures
- **Hotfix**: Bypass normal workflow, fix immediately
- **Rollback**: Revert problematic commits
- **Escalation**: Human intervention needed
```

---

## Workflow Examples

### Example 1: Adding a New Feature

**Task**: Add customer segmentation feature

```bash
# Step 1: Coordinator assigns task
# Sisyphus analyzes: "implementation + testing" → Route to Gemini

# Step 2: Gemini creates branch and implements
git checkout -b agent/gemini/customer-segmentation
gemini --prompt "Implement customer segmentation feature in src/business_analyzer/analysis/"

# Step 3: Gemini commits and pushes
git add .
git commit -m "feat: Add customer segmentation feature"
git push -u origin agent/gemini/customer-segmentation

# Step 4: Create PR for review
gh pr create --title "feat: Customer segmentation" \
             --body "Implemented customer segmentation..." \
             --label "agent:gemini"

# Step 5: Claude reviews the PR
claude code . --prompt "Review PR #45 for customer segmentation feature"
gh pr review --approve

# Step 6: Merge
gh pr merge --squash
```

### Example 2: Complex Refactoring

**Task**: Refactor database connection handling

```bash
# Step 1: Coordinator assigns to Claude (architecture task)
git checkout -b agent/claude/refactor-database-connection

# Step 2: Claude works on it
claude code . --prompt "Refactor database connection handling in src/business_analyzer/core/database.py"

# Step 3: Gemini writes tests in parallel
git checkout -b agent/gemini/database-tests
gemini --prompt "Write comprehensive tests for database module"

# Step 4: Both create PRs
# Claude's PR: Implementation
# Gemini's PR: Tests

# Step 5: Cross-review
# Claude reviews test PR
# Gemini reviews implementation PR

# Step 6: Merge implementation first, then tests
gh pr merge 46  # Claude's PR
gh pr merge 47  # Gemini's PR
```

### Example 3: Debugging Production Issue

**Task**: Fix database connection timeout

```bash
# Step 1: Create hotfix branch
git checkout -b hotfix/database-timeout

# Step 2: Claude investigates
claude code . --prompt "Debug database connection timeout issue in production"

# Step 3: Fix and test quickly
git add .
git commit -m "fix: Resolve database connection timeout"

# Step 4: Create PR (even for hotfixes - track the fix)
gh pr create --title "hotfix: Database connection timeout" --label "hotfix"

# Step 5: Fast-track review (another agent)
gh pr review --approve

# Step 6: Merge and deploy
gh pr merge --squash
git checkout main
git pull origin main

# Step 7: Gemini documents the fix
git checkout -b agent/gemini/document-timeout-fix
gemini --prompt "Document the database timeout fix and prevention measures"
```

### Example 4: Research Task

**Task**: Research best practices for SQL query optimization

```bash
# Step 1: Assign to Gemini (research task)
git checkout -b agent/gemini/research-sql-optimization

# Step 2: Gemini researches
# Uses web search, reads documentation, analyzes code
gemini --prompt "Research SQL query optimization best practices for our database schema"

# Step 3: Document findings
git add docs/research/
git commit -m "docs: Research SQL optimization best practices"

# Step 4: Create PR
gh pr create --title "docs: SQL optimization research"

# Step 5: Claude reviews and implements recommendations
git checkout -b agent/claude/implement-sql-optimization
# Based on Gemini's research
claude code . --prompt "Implement SQL optimization recommendations from research"
```

---

## Best Practices

### ✅ DO

1. **Use Feature Branches**
   ```bash
   git checkout -b agent/<name>/<task>
   ```

2. **Create PRs for Everything**
   - Even documentation changes
   - Even small fixes
   - Enables review and tracking

3. **Label PRs by Agent**
   ```bash
   gh pr create --label "agent:claude"
   ```

4. **Cross-Review Work**
   - Agent A implements → Agent B reviews
   - Catches different perspectives
   - Improves code quality

5. **Run Tests Before Committing**
   ```bash
   pytest tests/ -v
   ```

6. **Communicate in PR Comments**
   - Explain reasoning
   - Ask questions
   - Suggest improvements

7. **Keep Agents Focused**
   - Don't overload one agent
   - Parallelize when possible
   - Respect specialties

### ❌ DON'T

1. **Don't Push to Main Directly**
   - Use PR workflow
   - Branch protection prevents this anyway

2. **Don't Have Agents Edit Same File Simultaneously**
   - Causes merge conflicts
   - Coordinate via coordinator

3. **Don't Skip Code Review**
   - Even for "simple" changes
   - Another agent should review

4. **Don't Override Without Discussion**
   - If you disagree with another agent's approach
   - Comment on PR and discuss
   - Don't force push over their work

5. **Don't Create Long-Running Branches**
   - Rebase frequently
   - Keep PRs small and focused
   - Merge quickly

---

## Troubleshooting

### Issue: Merge Conflicts Between Agents

**Solution**:
```bash
# Agent 1's branch
git checkout agent/claude/feature
git fetch origin
git rebase origin/main
# Resolve conflicts
git push --force-with-lease
```

### Issue: Agents Disagree on Approach

**Solution**: Escalate to coordinator (Sisyphus)
- Post on PR with both approaches
- List pros/cons
- Make decision or defer to human

### Issue: Tests Failing on Agent's Branch

**Solution**:
```bash
# Check what's failing
pytest tests/ -v --tb=short

# Fix issues
# Run tests again
pytest tests/ -v

# Commit fixes separately
git add .
git commit -m "fix: Address test failures"
```

### Issue: Agent CLI Not Working

**Solution**:
```bash
# Check installation
which claude
which gemini

# Reinstall if needed
npm install -g @anthropic-ai/claude-code
npm install -g @google/gemini-cli

# Check authentication
claude login
gemini login
```

---

## Advanced Topics

### Adding New Agents

To add a new agent (e.g., Aider, GPT-4):

1. Install the tool
2. Create config in `.agents/<name>/`
3. Add to `.agents/config.yml`
4. Define capabilities and routing rules
5. Test with a small task

### Custom Consensus Rules

Modify `.agents/config.yml`:

```yaml
consensus:
  method: "confidence_weighted"
  threshold: 0.75
  
  special_rules:
    security:
      method: "unanimous"  # All must agree
      min_agents: 2
    
    performance:
      method: "expert_weighted"
      weights:
        claude: 0.6  # More weight for architecture
        gemini: 0.2
```

### Integration with CI/CD

Add to `.github/workflows/multi-agent.yml`:

```yaml
name: Multi-Agent Coordination

on:
  pull_request:
    types: [opened, labeled]

jobs:
  route:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Route to Agent
        run: |
          if [[ "${{ github.event.label.name }}" == "agent:claude" ]]; then
            echo "Routing to Claude Code..."
            # Trigger Claude Code review
          elif [[ "${{ github.event.label.name }}" == "agent:gemini" ]]; then
            echo "Routing to Gemini CLI..."
            # Trigger Gemini CLI tasks
          fi
```

---

## Resources

- [Claude Code Documentation](https://docs.anthropic.com/claude-code)
- [Gemini CLI Documentation](https://github.com/google-gemini/gemini-cli)
- [Aider Documentation](https://aider.chat/)
- [PR Workflow Guide](./PR_WORKFLOW.md)

---

## Summary

Multi-agent development enables:
- ✅ Parallel work on different tasks
- ✅ Specialized expertise for different problems
- ✅ Code review by different AI perspectives
- ✅ Faster development cycles
- ✅ Higher code quality

**Key Success Factors**:
1. Clear agent roles and responsibilities
2. Consistent PR workflow
3. Cross-agent code review
4. Good communication in PRs
5. Respect for each agent's specialty

**Remember**: The coordinator (Sisyphus/OpenCode) is the glue that holds it all together. Trust the process, communicate clearly, and build amazing software together! 🚀
