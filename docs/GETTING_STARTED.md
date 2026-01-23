# Getting Started with Joan Agents

This guide walks you through setting up the complete Joan ecosystem from scratch.

---

## Overview

| Component | What it is | Purpose |
|-----------|------------|---------|
| **Joan** | Web app | Project management with Kanban boards |
| **Joan MCP** | Claude integration | Lets Claude read/write Joan data |
| **Joan Agents** | Claude Code plugin | Autonomous agents that work your backlog |

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│    Joan     │◄────│   Joan MCP   │◄────│ Joan Agents  │
│  (web app)  │     │   (bridge)   │     │  (workers)   │
└─────────────┘     └──────────────┘     └──────────────┘
     Tasks              API access         Automation
```

---

## Prerequisites

- [ ] [Claude Code CLI](https://docs.anthropic.com/claude-code) installed
- [ ] Git installed with repository access
- [ ] Terminal access (macOS/Linux)

---

## Step 1: Create a Joan Account

1. Go to [joan.ai](https://joan.ai) and sign up
2. Create a new project for your codebase
3. Note your project name (you'll need it during setup)

---

## Step 2: Install Joan MCP Server

The MCP server lets Claude interact with your Joan projects.

```bash
# Install and configure Joan MCP (one command does everything)
npx @pollychrome/joan-mcp init
```

This will:
1. Open your browser to authenticate with Joan
2. Store credentials securely on your machine
3. Configure Claude Code automatically

**Restart Claude Code** after setup, then verify:

```bash
claude mcp list
```

You should see `joan` in the list of configured servers.

> **Alternative:** Global install with `npm install -g @pollychrome/joan-mcp` then run `joan-mcp init`

---

## Step 3: Install Joan Agents Plugin

```bash
# Add the plugin from GitHub
claude plugin add github:pollychrome/joan-agents
```

This gives you access to all `/agents:*` commands in Claude Code.

---

## Step 4: Install Joan CLI (for monitoring)

The `joan` CLI provides zero-token-cost monitoring of your agents.

```bash
# Navigate to joan-agents and run installer
cd ~/joan-agents
./scripts/install-joan-cli.sh
```

Verify installation:

```bash
joan --help
```

---

## Step 5: Initialize Your Project

Navigate to your codebase and run the setup wizard:

```bash
cd /path/to/your/project
claude
```

In Claude Code:

```
/agents:init
```

The wizard will:
1. List your Joan projects for selection
2. Ask for configuration preferences (model, mode, polling)
3. Create required Kanban columns (To Do → Analyse → Development → Review → Deploy → Done)
4. Create workflow tags (Ready, Planned, Dev-Complete, etc.)
5. Set up bash permissions for autonomous operation
6. Generate `.joan-agents.json` config file
7. Create `.claude/logs/` directory for monitoring

---

## Step 6: Add Tasks to Joan

In the Joan web app, create tasks in the **"To Do"** column:

```
Title: Add user authentication

Description:
- Users can sign up with email/password
- Include password reset flow
- Store sessions in JWT tokens
```

Good tasks have:
- Clear title describing the feature/fix
- Bullet points explaining requirements
- Acceptance criteria (what "done" looks like)

---

## Step 7: Start the Agents

```bash
# In Claude Code
/agents:dispatch --loop
```

You'll see:

```
Starting external scheduler for continuous operation
  Poll interval: 60s
  Max idle polls: 12

═══════════════════════════════════════════════════════════════
  MONITORING
═══════════════════════════════════════════════════════════════
  Live dashboard:  joan status myproject -f
  Tail logs:       joan logs myproject
  Global view:     joan status

  Stop gracefully: touch /tmp/joan-agents-myproject.shutdown
═══════════════════════════════════════════════════════════════
```

---

## Step 8: Monitor Progress

Open a new terminal and run:

```bash
joan status myproject -f
```

This shows a live dashboard with:
- Pipeline status (which stage is active)
- Active workers and what they're doing
- Recent activity log

---

## Workflow Modes

### Standard Mode (default)

Human approval required at two gates:

| Gate | Agent Action | Your Action |
|------|--------------|-------------|
| Plan Approval | Architect creates plan | Add `Plan-Approved` tag in Joan |
| Merge Approval | Reviewer approves code | Add `Ops-Ready` tag in Joan |

Best for: Production systems, learning the workflow

### YOLO Mode

Fully autonomous - no human gates:

```bash
/agents:dispatch --loop --mode=yolo
```

Best for: Internal tools, prototyping, trusted codebases

---

## What the Agents Do

| Agent | Watches | Does |
|-------|---------|------|
| **BA** | To Do | Validates requirements, asks clarifying questions |
| **Architect** | Analyse | Creates implementation plans with subtasks |
| **Dev** | Development | Implements code, creates PRs |
| **Reviewer** | Review | Deep code review, security checks |
| **Ops** | Review (approved) | Merges to develop branch |

Tasks flow: `To Do → Analyse → Development → Review → Deploy → Done`

---

## Common Commands

| Command | Purpose |
|---------|---------|
| `/agents:init` | Initial project setup |
| `/agents:dispatch --loop` | Start continuous operation |
| `/agents:dispatch` | Single pass (testing) |
| `/agents:doctor` | Diagnose stuck tasks |
| `/agents:model` | Change Claude model |

| CLI Command | Purpose |
|-------------|---------|
| `joan status` | Global view of all projects |
| `joan status myproject -f` | Live dashboard |
| `joan logs myproject` | Tail logs |

---

## Stopping Agents

```bash
# Graceful shutdown
touch /tmp/joan-agents-myproject.shutdown

# Or Ctrl+C in the Claude Code terminal
```

Agents also auto-shutdown after 12 consecutive idle polls (configurable).

---

## Troubleshooting

### "MCP server not found"
```bash
claude mcp list  # Verify joan is listed

# If missing, reinstall:
npx @pollychrome/joan-mcp init
```

### "Plugin not found"
```bash
claude plugins  # Verify joan-agents is listed
claude plugin add github:pollychrome/joan-agents
```

### Tasks stuck in a column
```bash
# In Claude Code
/agents:doctor
```

### Scheduler killed prematurely
Check that `schedulerStuckTimeoutSeconds` (default: 3900) is longer than `workerTimeouts.dev` (default: 3600) in `.joan-agents.json`.

---

## Next Steps

- Read the [full documentation](./../.claude/CLAUDE.md) for advanced configuration
- Check [workflow details](../shared/joan-shared-specs/docs/workflow/) for tag conventions
- Join the community for support and feature requests

---

## Quick Reference Card

```
SETUP
  1. joan.ai signup → create project
  2. npx @pollychrome/joan-mcp init → restart Claude Code
  3. claude plugin add github:pollychrome/joan-agents
  4. cd /your/project && claude → /agents:init
  5. Add tasks to Joan "To Do" column
  6. /agents:dispatch --loop

MONITOR (zero tokens)
  joan status myproject -f

STOP
  touch /tmp/joan-agents-myproject.shutdown

HUMAN GATES (standard mode)
  Plan ready    → add Plan-Approved tag
  Code reviewed → add Ops-Ready tag
```
