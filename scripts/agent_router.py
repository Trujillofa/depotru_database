#!/usr/bin/env python3
"""
Task Router for Multi-Agent System

This script analyzes tasks and routes them to the most appropriate agent(s)
based on their specialties and current workload.

Usage:
    python scripts/agent_router.py "Implement customer API endpoint"
    python scripts/agent_router.py --list-agents
    python scripts/agent_router.py --config .agents/config.yml "Debug database issue"
"""

import argparse
import yaml
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class TaskType(Enum):
    ARCHITECTURE = "architecture"
    IMPLEMENTATION = "implementation"
    DEBUGGING = "debugging"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    RESEARCH = "research"
    REVIEW = "review"
    UNKNOWN = "unknown"


@dataclass
class Agent:
    id: str
    name: str
    role: str
    priority: int
    capabilities: List[str]
    branch_prefix: str
    config_file: Optional[str] = None


@dataclass
class Task:
    description: str
    task_type: TaskType
    required_capabilities: List[str]
    urgency: str = "normal"  # low, normal, high, critical


class AgentRouter:
    """Routes tasks to appropriate agents based on capabilities and routing rules."""

    def __init__(self, config_path: str = ".agents/config.yml"):
        self.config = self._load_config(config_path)
        self.agents = self._init_agents()

    def _load_config(self, config_path: str) -> Dict:
        """Load agent configuration from YAML file."""
        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"⚠️  Config file not found: {config_path}")
            print("Using default configuration...")
            return self._default_config()
        except yaml.YAMLError as e:
            print(f"❌ Error parsing config: {e}")
            sys.exit(1)

    def _default_config(self) -> Dict:
        """Return default configuration if file not found."""
        return {
            "agents": {
                "claude": {
                    "name": "Claude Code",
                    "role": "architect",
                    "priority": 1,
                    "capabilities": [
                        "refactoring",
                        "architecture",
                        "debugging",
                        "security_audit",
                    ],
                    "branch_prefix": "agent/claude",
                },
                "gemini": {
                    "name": "Gemini CLI",
                    "role": "implementer",
                    "priority": 2,
                    "capabilities": [
                        "implementation",
                        "research",
                        "documentation",
                        "testing",
                    ],
                    "branch_prefix": "agent/gemini",
                },
                "opencode": {
                    "name": "OpenCode/Sisyphus",
                    "role": "coordinator",
                    "priority": 0,
                    "capabilities": [
                        "coordination",
                        "task_routing",
                        "conflict_resolution",
                    ],
                    "branch_prefix": "agent/opencode",
                },
            },
            "routing": {
                "architecture": {"agents": ["claude"], "confidence_threshold": 0.8},
                "implementation": {
                    "agents": ["gemini", "claude"],
                    "confidence_threshold": 0.7,
                },
                "debugging": {"agents": ["claude"], "confidence_threshold": 0.8},
                "testing": {
                    "agents": ["gemini", "claude"],
                    "confidence_threshold": 0.6,
                },
                "documentation": {"agents": ["gemini"], "confidence_threshold": 0.6},
                "research": {"agents": ["gemini"], "confidence_threshold": 0.7},
            },
        }

    def _init_agents(self) -> Dict[str, Agent]:
        """Initialize agent objects from configuration."""
        agents = {}
        for agent_id, config in self.config.get("agents", {}).items():
            agents[agent_id] = Agent(
                id=agent_id,
                name=config["name"],
                role=config["role"],
                priority=config.get("priority", 99),
                capabilities=config.get("capabilities", []),
                branch_prefix=config.get("branch_prefix", f"agent/{agent_id}"),
                config_file=config.get("config_file"),
            )
        return agents

    def _classify_task(self, description: str) -> Task:
        """Classify task type based on description keywords."""
        description_lower = description.lower()

        # Architecture keywords
        if any(
            kw in description_lower
            for kw in [
                "refactor",
                "architecture",
                "design",
                "modular",
                "restructure",
                "pattern",
                "interface",
                "abstract",
                "inheritance",
                "composition",
            ]
        ):
            return Task(
                description=description,
                task_type=TaskType.ARCHITECTURE,
                required_capabilities=["refactoring", "architecture"],
            )

        # Debugging keywords
        if any(
            kw in description_lower
            for kw in [
                "fix",
                "bug",
                "error",
                "debug",
                "investigate",
                "issue",
                "broken",
                "fail",
                "crash",
                "exception",
                "traceback",
            ]
        ):
            return Task(
                description=description,
                task_type=TaskType.DEBUGGING,
                required_capabilities=["debugging"],
                urgency="high",
            )

        # Testing keywords
        if any(
            kw in description_lower
            for kw in [
                "test",
                "testing",
                "coverage",
                "pytest",
                "unittest",
                "mock",
                "fixture",
                "assert",
                "spec",
            ]
        ):
            return Task(
                description=description,
                task_type=TaskType.TESTING,
                required_capabilities=["testing"],
            )

        # Documentation keywords
        if any(
            kw in description_lower
            for kw in [
                "doc",
                "documentation",
                "readme",
                "guide",
                "comment",
                "explain",
                "tutorial",
                "example",
                "usage",
            ]
        ):
            return Task(
                description=description,
                task_type=TaskType.DOCUMENTATION,
                required_capabilities=["documentation"],
            )

        # Research keywords
        if any(
            kw in description_lower
            for kw in [
                "research",
                "investigate",
                "analyze",
                "study",
                "explore",
                "compare",
                "evaluate",
                "survey",
                "benchmark",
            ]
        ):
            return Task(
                description=description,
                task_type=TaskType.RESEARCH,
                required_capabilities=["research"],
            )

        # Review keywords
        if any(
            kw in description_lower
            for kw in [
                "review",
                "audit",
                "check",
                "validate",
                "verify",
                "inspect",
                "assess",
                "examine",
            ]
        ):
            return Task(
                description=description,
                task_type=TaskType.REVIEW,
                required_capabilities=["review"],
            )

        # Default to implementation
        return Task(
            description=description,
            task_type=TaskType.IMPLEMENTATION,
            required_capabilities=["implementation"],
        )

    def route_task(self, description: str) -> Dict:
        """Route a task to the most appropriate agent(s)."""
        task = self._classify_task(description)

        # Get routing rules for this task type
        routing_rules = self.config.get("routing", {}).get(task.task_type.value, {})
        preferred_agents = routing_rules.get("agents", [])
        confidence_threshold = routing_rules.get("confidence_threshold", 0.7)

        # Score all agents
        agent_scores = {}
        for agent_id, agent in self.agents.items():
            # Capability match score (0-10)
            matching_caps = set(task.required_capabilities) & set(agent.capabilities)
            cap_score = len(matching_caps) * 5  # 5 points per matching capability

            # Role alignment score
            role_score = 0
            if task.task_type.value in agent.role:
                role_score = 3

            # Priority bonus (lower priority number = higher score)
            priority_score = max(0, 5 - agent.priority)

            # Calculate total score
            total_score = cap_score + role_score + priority_score

            # Boost preferred agents
            if agent_id in preferred_agents:
                total_score *= 1.5

            agent_scores[agent_id] = {
                "agent": agent,
                "score": total_score,
                "matching_capabilities": list(matching_caps),
                "is_preferred": agent_id in preferred_agents,
            }

        # Sort by score
        sorted_agents = sorted(
            agent_scores.items(), key=lambda x: x[1]["score"], reverse=True
        )

        # Select top agent(s)
        primary_agent = sorted_agents[0][1]["agent"] if sorted_agents else None
        secondary_agents = [
            sorted_agents[i][1]["agent"] for i in range(1, min(3, len(sorted_agents)))
        ]

        return {
            "task": task,
            "primary_agent": primary_agent,
            "secondary_agents": secondary_agents,
            "all_scores": sorted_agents,
            "confidence_threshold": confidence_threshold,
        }

    def generate_branch_name(self, agent: Agent, task: Task) -> str:
        """Generate a branch name for the task."""
        import re
        import time

        # Clean task description for branch name
        clean_desc = re.sub(r"[^\w\s-]", "", task.description.lower())
        clean_desc = re.sub(r"[-\s]+", "-", clean_desc)
        clean_desc = clean_desc[:50]  # Limit length

        timestamp = int(time.time())
        return f"{agent.branch_prefix}/{clean_desc}-{timestamp}"

    def list_agents(self) -> None:
        """List all configured agents."""
        print("\n🤖 Configured Agents:\n")
        print(f"{'ID':<15} {'Name':<20} {'Role':<15} {'Priority':<10}")
        print("-" * 65)

        for agent_id, agent in sorted(self.agents.items(), key=lambda x: x[1].priority):
            print(
                f"{agent_id:<15} {agent.name:<20} {agent.role:<15} {agent.priority:<10}"
            )

        print("\n")


def print_routing_result(result: Dict) -> None:
    """Print routing result in a formatted way."""
    task = result["task"]
    primary = result["primary_agent"]
    secondary = result["secondary_agents"]

    print("\n" + "=" * 70)
    print("🎯 TASK ROUTING RESULT")
    print("=" * 70)

    print(f"\n📋 Task: {task.description}")
    print(f"📊 Type: {task.task_type.value.upper()}")
    print(f"⚡ Urgency: {task.urgency}")
    print(f"🔧 Required Capabilities: {', '.join(task.required_capabilities)}")

    print("\n" + "-" * 70)
    print("🥇 PRIMARY AGENT (Recommended)")
    print("-" * 70)
    if primary:
        print(f"   Name: {primary.name}")
        print(f"   ID: {primary.id}")
        print(f"   Role: {primary.role}")
        print(f"   Branch Prefix: {primary.branch_prefix}")
        print(f"   Capabilities: {', '.join(primary.capabilities)}")

    if secondary:
        print("\n" + "-" * 70)
        print("🥈 SECONDARY AGENTS (Alternative/Review)")
        print("-" * 70)
        for i, agent in enumerate(secondary, 1):
            print(f"   {i}. {agent.name} ({agent.id})")

    print("\n" + "-" * 70)
    print("📈 AGENT SCORES")
    print("-" * 70)
    for agent_id, data in result["all_scores"]:
        score_bar = "█" * int(data["score"] / 2)
        preferred = " ⭐" if data["is_preferred"] else ""
        print(f"   {agent_id:<15} {data['score']:>3}/30  {score_bar:<15}{preferred}")

    # Generate suggested branch name
    if primary:
        router = AgentRouter()
        branch_name = router.generate_branch_name(primary, task)
        print("\n" + "-" * 70)
        print("🌿 SUGGESTED BRANCH NAME")
        print("-" * 70)
        print(f"   {branch_name}")

    print("\n" + "=" * 70)
    print("\n💡 Next Steps:")
    print(
        f"   1. Create branch: git checkout -b {branch_name if primary else '<branch-name>'}"
    )
    print(
        f"   2. Start {primary.name if primary else 'agent'}: {primary.id if primary else '<agent>'} code ."
    )
    print("   3. Work on task")
    print("   4. Commit and push")
    print("   5. Create PR for review")
    print("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Route tasks to appropriate AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "Implement customer API"
  %(prog)s "Debug database connection issue"
  %(prog)s --list-agents
  %(prog)s --config custom-config.yml "Refactor authentication"
        """,
    )

    parser.add_argument("task", nargs="?", help="Task description to route")

    parser.add_argument(
        "--config",
        default=".agents/config.yml",
        help="Path to agent configuration file (default: .agents/config.yml)",
    )

    parser.add_argument(
        "--list-agents", action="store_true", help="List all configured agents"
    )

    parser.add_argument(
        "--branch-name",
        action="store_true",
        help="Only output the suggested branch name",
    )

    args = parser.parse_args()

    # Initialize router
    router = AgentRouter(args.config)

    if args.list_agents:
        router.list_agents()
        return

    if not args.task:
        parser.print_help()
        print("\n❌ Error: Task description required (unless using --list-agents)")
        sys.exit(1)

    # Route the task
    result = router.route_task(args.task)

    if args.branch_name:
        # Only output branch name (for scripting)
        if result["primary_agent"]:
            branch = router.generate_branch_name(
                result["primary_agent"], result["task"]
            )
            print(branch)
    else:
        # Print full result
        print_routing_result(result)


if __name__ == "__main__":
    main()
