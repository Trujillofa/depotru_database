# Custom GitHub Copilot Agents

This directory contains custom GitHub Copilot agents for the depotru_database project.

## What are Custom Agents?

Custom agents are specialized AI assistants that understand your project's specific context, conventions, and requirements. They provide more relevant and accurate help than general-purpose AI assistants.

## Available Agents

### @business-data-analyzer

**File:** `business-data-analyzer.agent.md`

A specialized AI agent for working on this Colombian hardware store Business Intelligence platform.

**Expertise:**
- Colombian business formatting (pesos, percentages, Spanish language)
- Vanna AI + Grok API integration for natural language SQL
- MSSQL database schema and business metrics
- Python testing with pytest
- Security and credential management
- Project-specific code patterns and conventions

**Best Used For:**
- Developing new features for the Vanna AI app
- Debugging database connection or API issues
- Writing tests for business logic
- Formatting numbers in Colombian peso format
- Security reviews and credential handling
- Understanding project structure and conventions

## How to Use Custom Agents

### In GitHub Copilot Chat (VS Code, JetBrains)

1. Open Copilot Chat (Ctrl+Shift+I or Cmd+Shift+I)
2. Type `@business-data-analyzer` followed by your request

Example:
```
@business-data-analyzer How do I format currency in Colombian pesos?
@business-data-analyzer Help me write a test for the profit margin calculation
@business-data-analyzer Review this code for security issues
```

### In GitHub.com (PRs, Issues)

Mention the agent in comments:
```
@business-data-analyzer please review this PR for Colombian formatting issues
```

### In GitHub Copilot CLI

```bash
gh copilot suggest -a business-data-analyzer "create a new business metric function"
```

## Agent Discovery

Custom agents are discovered in this order:
1. **Repository-level** (`.github/agents/`) - Highest priority
2. **Organization-level** (`{org}/.github/agents/`)
3. **User-level** (`~/.copilot/agents/`) - Lowest priority

This repository's agents take precedence over organization or personal agents.

## Creating New Agents

To create a new custom agent:

1. Create a new `.agent.md` file in this directory
2. Use YAML frontmatter for metadata (name, description, tools)
3. Write clear instructions about the agent's expertise and boundaries
4. Include code examples and patterns specific to the agent's domain
5. Commit and merge to the main branch

**Template:**

```markdown
---
name: my-custom-agent
description: Brief description of what this agent does
tools: ['read', 'search', 'edit', 'bash']
---

You are an AI agent specialized in...

## Core Responsibilities
...

## Boundaries
...

## Code Patterns
...
```

## Modifying Existing Agents

Agents can be updated as the project evolves. After updating an agent file:

1. Make your changes to the `.agent.md` file
2. Commit and push to a feature branch
3. Create a PR for review
4. After merging, the agent will be updated automatically

## Learn More

- [GitHub Docs: Custom Agents](https://docs.github.com/en/copilot/tutorials/customization-library/custom-agents)
- [GitHub Blog: How to Write Great Agents](https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/)
- [Project AI Instructions](../../docs/AI_AGENT_INSTRUCTIONS.md)

---

**Note:** Custom agents provide guidance but are not deterministic. Always review and test generated code before committing.
