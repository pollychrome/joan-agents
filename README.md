# Joan Multi-Agent Orchestration System

A multi-agent system that automates software development workflows using Claude Code. Agents handle requirements analysis, architecture planning, implementation, code review, and deployment—all orchestrated through your Joan project board.

---

## Why Joan Agents?

Claude Code is excellent at implementing tasks when you sit with it, describe what you want, and iterate interactively. Joan Agents solves a different problem: **what if you want Claude to autonomously process a backlog of work without you in the loop?**

### The Problem

With vanilla Claude Code, you are the orchestrator. You decide what to work on next, you review the output, you tell it to move on. This works well for single tasks but breaks down when you have 10, 20, or 50 tasks on a board and want them executed with consistent quality while you do something else.

Running multiple Claude Code sessions in parallel creates its own problems: merge conflicts, stale plans built against code another session already changed, no shared understanding of what's in flight, and no structured handoffs between phases of work.

### What Joan Agents Adds

| Concern | Claude Code alone | With Joan Agents |
|---------|------------------|------------------|
| **Task selection** | You pick what to work on | Agents pull from your Kanban board automatically |
| **Quality pipeline** | You review everything | BA validates requirements → Architect plans → Dev implements → Reviewer gates → Ops merges |
| **Merge safety** | You manage branches | Strict serial pipeline: one task through Dev→Review→Merge at a time, zero conflicts |
| **Context between phases** | Lost between sessions | Structured handoffs carry decisions, files, and warnings between agents |
| **Progress visibility** | You watch the terminal | Joan board updates in real-time; `joan status` dashboard costs zero tokens |
| **Failure recovery** | You restart manually | Self-healing: stale claims released, stuck states detected, doctor agent for diagnostics |
| **Human gates** | Always required | Standard mode: approve plans + merges. YOLO mode: fully autonomous |
| **Cost control** | Tokens consumed while idle | WebSocket events: zero tokens when no work; per-worker model selection (haiku for simple tasks) |

### When to Use Joan Agents

**Good fit:**
- You have a backlog of well-defined tasks and want them executed autonomously
- You want structured code review and quality gates without manual oversight
- You're building a product incrementally and want a predictable pipeline
- You want to prototype rapidly in YOLO mode, then tighten controls for production

**Not the right tool:**
- You're doing one-off exploratory work (just use Claude Code directly)
- You want real-time pair programming (Claude Code is better for that)
- Your tasks are highly interdependent and can't be serialized
- You don't have a Joan project board set up

### Tradeoffs

**What you gain:** Autonomous execution, consistent quality pipeline, merge safety, audit trail, structured handoffs, cost optimization, failure recovery.

**What you trade:** Setup overhead (init, board config, tags), serial throughput (one task at a time through dev→review→merge), token cost for the pipeline stages themselves, less direct control over implementation decisions (though YOLO vs standard mode lets you tune this).

The system is opinionated about workflow: tasks go through BA → Architect → Dev → Reviewer → Ops in order. If your workflow is fundamentally different, the agent pipeline may not fit.

---

## Quick Start

### Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Claude Code** | Latest version ([install guide](https://docs.anthropic.com/claude-code)) |
| **Git** | 2.x+ with push access to your repository |
| **Joan Account** | With a project created and Joan MCP server configured |

> **Joan MCP**: Agents communicate with Joan via MCP. Ensure your Joan MCP server is configured in `~/.claude/mcp.json` before proceeding.

### Step 1: Install the Plugin

```bash
# Add joan-agents as a marketplace
claude plugin marketplace add pollychrome/joan-agents

# Install the agents plugin (available to all your projects)
claude plugin install agents@joan-agents
```

### Step 2: Initialize Your Project

```bash
cd ~/your-project
claude

# In Claude Code:
> /agents:init
```

The initialization wizard will:
- Connect to your Joan project
- Configure agent settings (models, workflow mode, timeouts)
- Auto-create required Kanban columns and workflow tags
- Configure bash permissions for autonomous operation
- Generate `.joan-agents.json` in your project

### Step 3: Ensure `develop` Branch Exists

```bash
git checkout -b develop main
git push -u origin develop
```

### Step 4: Launch Agents

```bash
# In Claude Code:
> /agents:dispatch --loop    # WebSocket client, real-time events (recommended)

# In a separate terminal (zero token cost):
$ joan status myproject -f   # Live monitoring dashboard
```

**That's it.** Agents are now monitoring your Joan board via WebSocket, processing tasks as they appear.

---

## Setup Checklist

```
[ ] Claude Code installed
[ ] Git installed with push access
[ ] Joan account with project created
[ ] Joan MCP server configured in ~/.claude/mcp.json
[ ] Plugin installed (claude plugin install agents@alexbenson-joan-agents)
[ ] /agents:init completed for your project
[ ] develop branch exists and pushed
[ ] /agents:dispatch --loop running
```

---

## Commands

```bash
# Initialize project configuration
/agents:init

# Run coordinator
/agents:dispatch                          # Single pass (testing/debugging)
/agents:dispatch --loop                   # WebSocket client (recommended)
/agents:dispatch --loop --mode=yolo       # Fully autonomous

# Project maintenance
/agents:clean-project                     # Preview fixes (dry run)
/agents:clean-project --apply             # Apply all fixes
/agents:doctor                            # Diagnose and fix task states
/agents:doctor --dry-run                  # Preview only

# Model configuration
/agents:model                             # Change per-worker model selection

# Task planning
/agents:project-planner --file=plan.md    # Import tasks from plan file
/agents:project-planner --interactive     # Guided task creation

# Monitoring (separate terminal, zero token cost)
joan status                               # Global view of all projects
joan status myproject -f                  # Live dashboard
joan logs myproject                       # Tail logs
```

---

## Configuration

Created by `/agents:init` at `.joan-agents.json`:

```json
{
  "projectId": "uuid-from-joan",
  "projectName": "My Project",
  "settings": {
    "models": {
      "ba": "haiku",
      "architect": "opus",
      "dev": "opus",
      "reviewer": "opus",
      "ops": "haiku"
    },
    "mode": "standard",
    "staleClaimMinutes": 120,
    "workerTimeouts": {
      "ba": 10,
      "architect": 20,
      "dev": 60,
      "reviewer": 20,
      "ops": 15
    }
  },
  "agents": {
    "businessAnalyst": { "enabled": true },
    "architect": { "enabled": true },
    "reviewer": { "enabled": true },
    "ops": { "enabled": true },
    "devs": { "enabled": true, "count": 1 }
  }
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| `models` | per-worker | Per-worker model selection (haiku for BA/Ops, opus for rest) |
| `mode` | `standard` | `standard` (human gates) or `yolo` (fully autonomous) |
| `staleClaimMinutes` | `120` | Minutes before orphaned dev claims are auto-released |
| `devs.count` | `1` | Must be 1 (strict serial mode, enforced by schema) |

---

## Architecture

### WebSocket Event-Driven Dispatch

The system uses real-time WebSocket events instead of polling. The coordinator connects outbound to Joan, receives events instantly, and dispatches focused single-pass handlers.

```
                              ┌── Startup: actionable-tasks API → dispatch existing work
ws-client.py ─────────────────┤
                              └── Runtime: WebSocket events → dispatch new work
```

Each handler processes ONE task, is stateless, and checks Joan state on invocation.

### Three-Tier Processing

- **Tier 1 - Joan Backend (zero tokens):** Deterministic state transitions, tag validation, column auto-movement, YOLO auto-approvals
- **Tier 2 - Smart Events:** Semantic event types with pre-fetched payloads, filtered per handler
- **Tier 3 - Claude Workers:** BA, Architect, Dev, Reviewer, Ops — intelligence only

### Agents

| Agent | Role |
|-------|------|
| **Business Analyst** | Evaluates requirements, asks clarifying questions, marks Ready |
| **Architect** | Analyzes codebase, creates implementation plans with sub-tasks |
| **Dev** (×1, serial) | Implements on feature branches, creates PRs, handles rework |
| **Reviewer** | Merges develop into feature, deep code review, approves or rejects |
| **Ops** | Merges to develop with AI conflict resolution, tracks deployment |

### Strict Serial Pipeline

One task moves through Architect → Dev → Review → Ops at a time. No merge conflicts, plans always reference current codebase state.

---

## Workflow

Tasks flow through Kanban columns (auto-created by `/agents:init`):

```
To Do → Analyse → Development → Review → Deploy → Done
  │        │          │           │        │
  BA    Architect    Dev      Reviewer   Ops
```

### Human Actions (Tag-Based)

| When | Add This Tag |
|------|--------------|
| Approve a plan | `Plan-Approved` |
| Reject a plan | `Plan-Rejected` |
| Answer BA questions | `Clarification-Answered` |
| Approve merge to develop | `Ops-Ready` |
| Recover failed task | Remove `Implementation-Failed`, ensure `Planned` exists |

> In YOLO mode, `Plan-Approved` and `Ops-Ready` are added automatically.

### Workflow Modes

**Standard mode** (default): Human approval required for plan approval and merge approval.

**YOLO mode**: Fully autonomous. BA makes assumptions, Architect auto-approves plans, Dev retries on failure, Reviewer only blocks critical issues, Ops auto-merges. All decisions logged for audit trail.

```bash
/agents:dispatch --loop --mode=yolo
```

---

## Directory Structure

```
~/joan-agents/                   # This repository
├── .claude/
│   ├── agents/                  # Agent definitions
│   ├── commands/agents/         # Slash commands
│   └── CLAUDE.md                # System documentation
├── scripts/
│   ├── ws-client.py             # WebSocket client
│   ├── joan                     # CLI monitoring tool
│   └── install-joan-cli.sh      # CLI installer
├── shared/
│   └── joan-shared-specs/       # Shared specifications
└── README.md

~/your-project/                  # Any project using agents
├── .joan-agents.json            # Project config (created by /agents:init)
└── ...
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Setup Guide](shared/joan-shared-specs/docs/joan-agents/setup.md) | Full installation walkthrough |
| [Troubleshooting](shared/joan-shared-specs/docs/joan-agents/troubleshooting.md) | Common issues and fixes |
| [Architecture](shared/joan-shared-specs/docs/joan-agents/architecture.md) | System design details |
| [Agentic Workflow](shared/joan-shared-specs/docs/workflow/agentic-workflow.md) | Task lifecycle spec |
| [ALS Syntax](shared/joan-shared-specs/docs/workflow/als-spec.md) | Comment format for agents |
| [Worker Result Schema](shared/joan-shared-specs/docs/workflow/worker-result-schema.md) | Worker output format and context handoffs |

---

## Updating

```bash
cd ~/joan-agents
git pull
```

Changes are immediately available in all projects via the plugin system.
