# Joan Multi-Agent Orchestration System (v4.7)

A multi-agent system that automates software development workflows using Claude Code. Agents handle requirements analysis, architecture planning, implementation, code review, and deployment—all orchestrated through your Joan project board.

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Claude Code** | Latest version ([install guide](https://docs.anthropic.com/claude-code)) |
| **Git** | 2.x+ with push access to your repository |
| **Joan Account** | With a project created and Joan MCP server configured |

> **Joan MCP**: The agents communicate with Joan via MCP. Ensure your Joan MCP server is configured in `~/.claude/mcp.json` before proceeding.

### Step 1: Install the Plugin

```bash
# Add joan-agents as a marketplace
claude plugin marketplace add github:pollychrome/joan-agents

# Install the agents plugin (available to all your projects)
claude plugin install agents@alexbenson-joan-agents
```

This installs all agent commands (`/agents:dispatch`, `/agents:init`, etc.) globally.

### Step 2: Initialize Your Project

```bash
cd ~/your-project
claude

# In Claude Code:
> /agents:init
```

The initialization wizard will:
- ✅ Connect to your Joan project
- ✅ Configure agent settings (model, polling interval, dev count)
- ✅ Auto-create required Kanban columns
- ✅ Auto-create all workflow tags
- ✅ **Configure bash permissions** for autonomous operation
- ✅ Generate `.joan-agents.json` in your project

### Step 3: Ensure `develop` Branch Exists

```bash
git checkout -b develop main
git push -u origin develop
```

### Step 4: Launch Agents

```bash
# In Claude Code:
> /agents:dispatch --loop    # Continuous operation (recommended)

# In a separate terminal (zero token cost):
$ joan status myproject -f   # Live monitoring dashboard
```

**That's it!** Your agents are now monitoring your Joan board.

> **Note:** The `--loop` flag uses an external scheduler that prevents context bloat. Always use `--loop` for runs longer than 15 minutes.

---

## 📋 Setup Checklist

```
☐ Claude Code installed
☐ Git installed with push access
☐ Joan account with project created
☐ Joan MCP server configured in ~/.claude/mcp.json

☐ Plugin installed (claude plugin install agents@alexbenson-joan-agents)
☐ /agents:init completed for your project
☐ develop branch exists and pushed
☐ /agents:dispatch --loop running
```

---

## 📖 Detailed Setup Guide

For comprehensive setup instructions, see:
- **[Full Setup Guide](shared/joan-shared-specs/docs/joan-agents/setup.md)** - All configuration options
- **[Troubleshooting](shared/joan-shared-specs/docs/joan-agents/troubleshooting.md)** - Common issues

### Alternative: Manual Installation (Legacy)

If the plugin approach doesn't work, you can install manually:

```bash
# Clone the repository
git clone https://github.com/pollychrome/joan-agents.git ~/joan-agents

# Create symlinks to your user's Claude config
mkdir -p ~/.claude/commands
ln -sf ~/joan-agents/commands ~/.claude/commands/agents
ln -sf ~/joan-agents/agents ~/.claude/agents

# Initialize and run
cd /path/to/your/project
claude
> /agents:init
> /agents:dispatch --loop
```

### Joan MCP Configuration

Add to `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "joan": {
      "command": "node",
      "args": ["/path/to/joan-mcp-server/index.js"],
      "env": {
        "JOAN_API_URL": "https://your-joan-instance.com/api",
        "JOAN_API_KEY": "your-api-key"
      }
    }
  }
}
```

### Configuration File: `.joan-agents.json`

Created by `/agents:init`, this file controls agent behavior:

```json
{
  "projectId": "uuid-from-joan",
  "projectName": "My Project",
  "settings": {
    "model": "opus",
    "pollingIntervalMinutes": 10,
    "maxIdlePolls": 6
  },
  "agents": {
    "businessAnalyst": { "enabled": true },
    "architect": { "enabled": true },
    "reviewer": { "enabled": true },
    "ops": { "enabled": true },
    "devs": { "enabled": true, "count": 2 }
  }
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| `model` | `opus` | Claude model: `opus`, `sonnet`, or `haiku` |
| `pollingIntervalMinutes` | `10` | Minutes between polls when idle |
| `maxIdlePolls` | `6` | Idle polls before auto-shutdown (~1 hour) |
| `devs.count` | `1` | Number of dev workers (strict serial mode) |

### Bash Permissions (Auto-Configured)

`/agents:init` creates `.claude/settings.local.json` with permissions for autonomous operation:

```json
{
  "permissions": {
    "allow": [
      "Bash(git fetch:*)",
      "Bash(git checkout:*)",
      "Bash(git merge:*)",
      "Bash(git push:*)",
      "Bash(npm install:*)",
      "Bash(npm test:*)",
      "mcp__joan__*",
      "mcp__github__*"
    ]
  }
}
```

This prevents permission prompts from interrupting the agent loop. The file is git-ignored and local to your machine.

---

## 🔧 Commands

```bash
# Initialize project configuration
/agents:init

# Onboard existing backlog & fix broken states (comprehensive cure-all)
/agents:clean-project         # Dry run - preview changes
/agents:clean-project --apply # Apply all fixes

# Run coordinator (single pass - testing/debugging)
/agents:dispatch

# Run coordinator (continuous - recommended for production)
/agents:dispatch --loop

# Extended idle threshold (e.g., 2 hours at 5-min intervals)
/agents:dispatch --loop --max-idle=24

# Note: /agents:start is deprecated (use /agents:dispatch instead, kept for backward compatibility)

# Monitor agents (in separate terminal, zero token cost)
joan status              # Global view of all projects
joan status myproject -f # Live dashboard for specific project
joan logs myproject      # Tail logs in real-time

# Change model for all agents
/agents:model
```

### Project Cleanup & Recovery

The `/agents:clean-project` command is a comprehensive tool that handles:

✅ **Fresh backlog onboarding** - Integrates new tasks into workflow
✅ **Broken state recovery** - Fixes incorrectly tagged tasks
✅ **Column drift correction** - Moves misplaced tasks to correct columns
✅ **Tag inconsistency cleanup** - Removes stale workflow tags

**When to use:**
- Initial project setup after `/agents:init`
- After manual changes in Joan UI
- Recovery from tagging errors
- Periodic maintenance to prevent drift

**Example workflow:**
```bash
# 1. See what will be fixed
/agents:clean-project

# 2. Review the output, then apply
/agents:clean-project --apply

# 3. Start agents
/agents:dispatch --loop
```

### Shell Scripts (macOS) - Legacy

> **Note:** These shell scripts are legacy and kept for backward compatibility. The recommended approach is to use `/agents:dispatch --loop` directly in Claude Code.

```bash
chmod +x ~/joan-agents/*.sh

# iTerm2 (opens tabs) - DEPRECATED
~/joan-agents/start-agents-iterm.sh [--max-idle=N]

# Terminal.app - DEPRECATED
~/joan-agents/start-agents.sh [--max-idle=N]

# Stop agents
~/joan-agents/stop-agents.sh
```

These scripts now call `/agents:dispatch --loop` internally.

---

## 🏗️ Architecture

### Tag-Driven Orchestration

v4 uses **tag-based state transitions** instead of comment parsing. A single coordinator polls Joan once per interval and dispatches single-pass workers.

```
Coordinator ────► poll Joan ────► dispatch workers ────► sleep ────► repeat
     │
     ├──► spawn BA-worker (task X)
     ├──► spawn Architect-worker (task Y)
     ├──► spawn Dev-worker (task Z)
     ├──► spawn Reviewer-worker (task W)
     └──► spawn Ops-worker (task V)
```

### Agents

| Agent | Role |
|-------|------|
| **Business Analyst** | Evaluates requirements, asks clarifying questions |
| **Architect** | Creates implementation plans with sub-tasks |
| **Dev** (×1) | Claims tasks, implements on feature branches, creates PRs |
| **Reviewer** | Code review, quality gate, approves or requests rework |
| **Ops** | Merges to develop, tracks deployments |

### Strict Serial Pipeline with Context Handoffs

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      STRICT SERIAL PIPELINE (v4.2)                      │
│                                                                         │
│  ┌──────────┐   ┌─────────┐   ┌────────┐   ┌──────┐   ┌──────────┐    │
│  │ Architect│ → │   Dev   │ → │ Review │ → │  Ops │ → │  MERGED  │    │
│  │ (1 task) │   │(1 task) │   │(1 task)│   │merge │   │to develop│    │
│  └──────────┘   └─────────┘   └────────┘   └──────┘   └──────────┘    │
│       │               │             │           │                      │
│       └───────────────┴─────────────┴───────────┘                      │
│                    Context Handoffs                                     │
│                                                                         │
│  ONE task at a time → No merge conflicts → Plans always fresh          │
└─────────────────────────────────────────────────────────────────────────┘
```

In strict serial mode, only ONE task moves through the Architect→Dev→Review→Ops pipeline at a time. Devs work directly on feature branches (no worktrees needed). This prevents merge conflicts and ensures plans reference the current codebase state.

---

## 📊 Workflow

Tasks flow through these columns (auto-created by `/agents:init`):

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

### Quality Gates

- **BA → Architect**: Requirements must be clear
- **Architect → Dev**: Plan must be approved by human
- **Dev → Reviewer**: All sub-tasks checked off
- **Reviewer → Ops**: Code review passed, tests green
- **Ops → Done**: Deployed to production

---

## 📁 Directory Structure

```
~/.claude/
├── CLAUDE.md                    # Global instructions
├── agents/ → ~/joan-agents/.claude/agents/
└── commands/
    └── agents/ → ~/joan-agents/.claude/commands/agents/

~/joan-agents/                   # Source repository
├── .claude/
│   ├── agents/                  # Agent definitions
│   ├── commands/agents/         # Slash commands
│   └── CLAUDE.md                # System documentation
├── shared/
│   └── joan-shared-specs/       # Shared specifications
└── README.md

~/your-project/                  # Any project using agents
├── .joan-agents.json            # Project config (created by /agents:init)
└── ...
```

Note: Devs work directly on feature branches in the main directory (no worktrees needed in strict serial mode).

---

## 💾 Resource Recommendations

| Dev Workers | RAM | Use Case |
|-------------|-----|----------|
| 2 | 4-6 GB | Light workload |
| 4 | 6-10 GB | Standard (recommended) |
| 6 | 10-14 GB | Heavy workload |

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [Setup Guide](shared/joan-shared-specs/docs/joan-agents/setup.md) | Full installation walkthrough |
| [Global Installation](shared/joan-shared-specs/docs/joan-agents/global-installation.md) | Symlink-based setup |
| [Troubleshooting](shared/joan-shared-specs/docs/joan-agents/troubleshooting.md) | Common issues and fixes |
| [Prevention Strategies](docs/PREVENTION_STRATEGIES.md) | How to prevent common workflow failures |
| [Best Practices](shared/joan-shared-specs/docs/joan-agents/best-practices.md) | Workflow optimization tips |
| [Architecture](shared/joan-shared-specs/docs/joan-agents/architecture.md) | System design details |
| [Agentic Workflow](shared/joan-shared-specs/docs/workflow/agentic-workflow.md) | Task lifecycle spec |
| [ALS Syntax](shared/joan-shared-specs/docs/workflow/als-spec.md) | Comment format for agents |
| [Worker Result Schema](shared/joan-shared-specs/docs/workflow/worker-result-schema.md) | Worker output format and context handoffs |
| [Human Inbox](shared/joan-shared-specs/docs/human-interface/human-inbox.md) | Human interaction patterns |

---

## ✨ Key Benefits

- **Tag-Based Orchestration** - Deterministic state machine, no comment parsing
- **10x Lower Overhead** - Single coordinator vs N independent polling agents
- **Strict Serial Pipeline** - One task at a time prevents merge conflicts
- **Context Handoffs** - Structured context passed between workflow stages
- **Single-Pass Workers** - Stateless workers, easy to retry on failure
- **Quality Gate** - Automated code review before merge
- **Self-Healing** - Auto-recovery from stale claims, anomaly detection
- **External Scheduler** - Context-safe long-running operations

---

## 🔄 Updating

```bash
cd ~/joan-agents
git pull
```

Changes are immediately available in all projects via symlinks.

---

## What's New in v4.5

| Feature | v4.2 | v4.5 |
|---------|------|------|
| Backlog onboarding | Manual tag application | Comprehensive `/agents:clean-project` cure-all |
| State recovery | Manual intervention | Auto-detects and fixes broken states |
| Evidence validation | Not checked | Validates completion evidence (PRs, commits) |
| Column drift | No detection | Auto-corrects misplaced tasks |
| Context management | Internal loop only | External scheduler for long-running ops |

### Comprehensive Project Cleanup

The new `/agents:clean-project` command replaces manual backlog setup with an intelligent cure-all that:
- Detects tasks with incorrect end-stage tags (Review-Approved/Ops-Ready) but no completion evidence
- Auto-corrects column misplacement (e.g., completed tasks in wrong columns)
- Validates workflow state consistency
- Provides detailed dry-run preview before making changes

This eliminates common setup errors and enables self-service recovery from broken states.

---

## What's New in v4.2

| Feature | v4 | v4.2 |
|---------|-----|------|
| Dev pipeline | Parallel (N workers) | Strict serial (1 worker, no merge conflicts) |
| Context passing | Manual via comments | Structured handoffs between stages |
| Session management | Internal loop | External scheduler (context-safe) |
| Self-healing | Basic claim recovery | Anomaly detection, stuck state recovery |

### Context Handoffs

Workers now pass **structured context** between workflow stages:
- BA → Architect: Requirements clarifications and user decisions
- Architect → Dev: Architecture decisions, files to modify, dependencies
- Dev → Reviewer: Implementation notes, files changed, warnings
- Reviewer → Dev (rework): Blockers with file:line, suggestions

Context is persisted in Joan comments (not in-memory), making it durable across coordinator restarts.

See [Worker Result Schema](shared/joan-shared-specs/docs/workflow/worker-result-schema.md) for details.

## What's New in v4

| Feature | v3 | v4 |
|---------|-----|-----|
| Orchestration | N agents poll independently | Single coordinator dispatches workers |
| State triggers | Comment parsing (@approve-plan) | Tag-based (Plan-Approved tag) |
| Human workflow | Add comments | Add tags in Joan UI |
| Polling overhead | N polls per interval | 1 poll per interval |
| Worker lifetime | Continuous loops | Single-pass (exit after task) |
