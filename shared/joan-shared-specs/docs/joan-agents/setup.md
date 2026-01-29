# Setup Guide

This guide walks you through setting up the Joan Multi-Agent Orchestration System.

> **Quick Start**: For most users, the [README Quick Start](../../../../README.md#-quick-start-5-minutes) is all you need. This guide provides additional details and configuration options.

---

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Claude Code | Latest | Agent runtime ([install guide](https://docs.anthropic.com/claude-code)) |
| Python | 3.9+ | Status dashboard and WebSocket client |
| Git | 2.x+ | Version control and worktree management |
| Node.js | 18+ | If your project uses Node (optional) |
| iTerm2 | 3.x+ | Recommended terminal for macOS (optional) |

### Required Accounts & Access

- [ ] Claude Code subscription (Max recommended for heavy usage)
- [ ] Git repository access (push permissions to your repository)
- [ ] Joan platform account with API access
- [ ] Joan project created (you'll need the project UUID)

### System Requirements

| Dev Workers | RAM | Use Case |
|-------------|-----|----------|
| 2 | 4-6 GB | Light workload |
| 4 | 6-10 GB | Standard (recommended) |
| 6 | 10-14 GB | Heavy workload |

---

## Installation Options

Choose one of these installation methods:

| Method | Best For | Updates |
|--------|----------|---------|
| **Global (Recommended)** | Multiple projects | `git pull` updates all projects |
| **Per-Project** | Single project or isolated setup | Manual copy per project |

---

## Global Installation (Recommended)

### Step 1: Clone the Repository

```bash
# Clone to a permanent location
git clone https://github.com/pollychrome/joan-agents.git ~/joan-agents

# Make scripts executable
chmod +x ~/joan-agents/*.sh

# Install dashboard dependencies (Rich UI + terminal effects)
python3 -m pip install --user --break-system-packages -r ~/joan-agents/scripts/requirements.txt
```

### Step 2: Create Symlinks

```bash
# Create Claude Code directories
mkdir -p ~/.claude/commands

# Remove any existing installations
rm -rf ~/.claude/commands/agents
rm -rf ~/.claude/agents

# Create symlinks
ln -s ~/joan-agents/.claude/commands/agents ~/.claude/commands/agents
ln -s ~/joan-agents/.claude/agents ~/.claude/agents
```

### Step 3: Set Up Global Instructions

Choose one option:

**Option A: Symlink** (recommended if no existing global instructions)
```bash
ln -sf ~/joan-agents/.claude/CLAUDE.md ~/.claude/CLAUDE.md
```

**Option B: Include via reference** (if you have existing instructions)
Add this line to your `~/.claude/CLAUDE.md`:
```markdown
{{~/joan-agents/.claude/CLAUDE.md}}
```

**Option C: Append contents**
```bash
cat ~/joan-agents/.claude/CLAUDE.md >> ~/.claude/CLAUDE.md
```

### Step 4: Configure Joan MCP Server

The agents communicate with Joan via MCP. Configure your Joan MCP server in Claude Code:

```bash
# Open Claude Code settings
claude /settings
```

Or manually edit `~/.claude/mcp.json`:

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

#### Joan MCP Required Methods

Your Joan MCP server must implement these methods (or equivalents):

```typescript
// Task retrieval
joan.getTasks(params: {
  project: string;
  column?: string;
  tags?: string[];
}): Task[]

// Task updates
joan.updateTask(params: {
  id: string;
  title?: string;
  description?: string;
  column?: string;
  priority?: string;
  assignee?: string;
}): Task

// Tag management
joan.addTag(params: { id: string; tag: string }): Task
joan.removeTag(params: { id: string; tag: string }): Task

// Comments
joan.addComment(params: { id: string; text: string }): Comment
joan.getComments(params: { id: string }): Comment[]

// Attachments
joan.attachFile(params: { id: string; filename: string; content: string }): Attachment
joan.getAttachments(params: { id: string }): Attachment[]

// Column operations
joan.moveTask(params: { id: string; column: string }): Task
```

If your MCP uses different method names, update the agent definitions accordingly.

### Step 4: Configure GitHub MCP (Optional but Recommended)

For PR creation and management:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-github"],
      "env": {
        "GITHUB_TOKEN": "your-github-token"
      }
    }
  }
}
```

### Step 5: Initialize Your Project

Navigate to your project and run the initialization wizard:

```bash
cd ~/your-project
claude

# In Claude Code:
> /agents:init
```

**The `/agents:init` wizard will:**

1. **Fetch available Joan projects** - Lists all projects you have access to
2. **Let you select your project** - Choose from the list or enter a project ID
3. **Configure settings** - Model (opus/sonnet/haiku), polling interval, idle threshold
4. **Enable/disable agents** - Choose which agents to activate (BA, Architect, Reviewer, Ops, Devs)
5. **Set dev worker count** - How many parallel development workers (default: 2)
6. **Auto-create Kanban columns** - Creates missing workflow columns in Joan
7. **Auto-create workflow tags** - Creates all required tags for agent communication
8. **Configure bash permissions** - Sets up `.claude/settings.local.json` for autonomous operation
9. **Generate config file** - Writes `.joan-agents.json` to your project root

### Step 6: Ensure `develop` Branch Exists

```bash
git checkout -b develop main
git push -u origin develop
```

### Step 7: Verify Installation

```bash
# In Claude Code:
> /agents:dispatch           # Single pass test
> /agents:dispatch --loop    # Continuous operation (recommended)

# In separate terminal (zero token cost):
$ joan status              # Global view of all projects
$ joan status myproject -f # Live monitoring dashboard
```

You should see:
1. Coordinator announces itself
2. Coordinator polls Joan for tasks
3. Coordinator reports status (even if no tasks found)

---

## Per-Project Installation (Alternative)

If you prefer to copy files instead of symlinking:

```bash
cd /path/to/your/project

# Create .claude directory
mkdir -p .claude

# Copy agent definitions
cp -r ~/joan-agents/.claude/agents .claude/
cp -r ~/joan-agents/.claude/commands .claude/

# Copy system instructions
cp ~/joan-agents/.claude/CLAUDE.md .claude/

# Install dashboard dependencies
python3 -m pip install --user --break-system-packages -r ~/joan-agents/scripts/requirements.txt

# Initialize and run
claude
> /agents:init
> /agents:dispatch --loop
```

---

## Project-Specific Instructions (Optional)

You can add project-specific instructions to `.claude/CLAUDE.md`:

```markdown
# Project: Your Project Name

## Repository
- URL: https://github.com/your-org/your-repo
- Main branch: main
- Development branch: develop

## Design System

### Colors
- Primary: #3B82F6
- Secondary: #10B981

### Typography
- Headings: Inter
- Body: Inter

## Testing
- Framework: Jest / Vitest / Pytest
- Command: npm test
- Coverage target: 80%
```

## Configuration Options

### .joan-agents.json

| Setting | Default | Description |
|---------|---------|-------------|
| `settings.model` | `opus` | Claude model for all agents |
| `settings.pollingIntervalMinutes` | `10` | Minutes between idle polls |
| `settings.maxIdlePolls` | `6` | Idle polls before shutdown |
| `agents.devs.count` | `2` | Parallel dev workers |

### Customizing Poll Interval

Edit `settings.pollingIntervalMinutes` in `.joan-agents.json`.

### Customizing Concurrent Tasks

Edit `agents.devs.count` in `.joan-agents.json`.

---

## What `/agents:init` Creates Automatically

### Kanban Columns

The following columns are created if they don't exist:

| Column | Default Status | Color | Purpose |
|--------|----------------|-------|---------|
| **To Do** | `todo` | Gray (#6B7280) | New tasks awaiting analysis |
| **Analyse** | `analyse` | Purple (#8B5CF6) | Tasks being evaluated/planned |
| **Development** | `in_progress` | Blue (#3B82F6) | Tasks being implemented |
| **Review** | `review` | Amber (#F59E0B) | Automated code review |
| **Deploy** | `deploy` | Emerald (#10B981) | Merged, awaiting production |
| **Done** | `done` | Green (#22C55E) | Deployed to production |

### Workflow Tags

All required tags are created automatically:

| Tag | Color | Purpose |
|-----|-------|---------|
| `Needs-Clarification` | Amber | Task has unanswered questions |
| `Clarification-Answered` | Emerald | Human answered BA questions |
| `Ready` | Green | Requirements complete, ready for Architect |
| `Plan-Pending-Approval` | Purple | Plan awaits human approval |
| `Plan-Approved` | Indigo | Plan approved, ready to finalize |
| `Plan-Rejected` | Red | Plan rejected, revision required |
| `Planned` | Blue | Plan finalized, available for Dev to claim |
| `Claimed-Dev-1` through `Claimed-Dev-N` | Gray | Dev N is implementing this task |
| `Dev-Complete` | Green | All DEV sub-tasks done |
| `Design-Complete` | Blue | All DES sub-tasks done |
| `Test-Complete` | Purple | All TEST sub-tasks pass |
| `Review-In-Progress` | Amber | Reviewer is actively reviewing |
| `Review-Approved` | Green | Review approved, awaiting Ops-Ready |
| `Ops-Ready` | Teal | Human approved merge; Ops may proceed |
| `Rework-Requested` | Red | Reviewer found issues, Dev needs to fix |
| `Rework-Complete` | Lime | Rework done, ready for review |
| `Merge-Conflict` | Orange | Late conflict detected during Ops merge |
| `Implementation-Failed` | Rose | Dev couldn't complete (manual recovery) |
| `Branch-Setup-Failed` | Pink | Branch setup failed (manual recovery) |

> **Note**: The number of `Claimed-Dev-N` tags created matches your configured `devs.count` setting.

### Bash Permissions

The agents need to run git, npm, and test commands without permission prompts. `/agents:init` creates `.claude/settings.local.json` with:

```json
{
  "permissions": {
    "allow": [
      "Bash(git fetch:*)",
      "Bash(git checkout:*)",
      "Bash(git merge:*)",
      "Bash(git pull:*)",
      "Bash(git push:*)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git branch:*)",
      "Bash(git status:*)",
      "Bash(git log:*)",
      "Bash(git diff:*)",
      "Bash(git reset:*)",
      "Bash(git stash:*)",
      "Bash(npm install:*)",
      "Bash(npm test:*)",
      "Bash(npm run:*)",
      "Bash(pip install:*)",
      "Bash(pytest:*)",
      "Bash(mkdir:*)",
      "Bash(cd:*)",
      "Bash(gh pr:*)",
      "Bash(gh issue:*)",
      "Bash(gh api:*)",
      "Bash(python3:*)",
      "mcp__joan__*",
      "mcp__plugin_agents_joan__*",
      "mcp__github__*"
    ]
  }
}
```

This file is git-ignored and local to your machine. Without these permissions, agents would be interrupted by permission prompts during the loop.

---

## Launching the System

### Full Launch (Coordinator)

```bash
# For iTerm2 (recommended)
cd /path/to/your/project
./joan-agents/start-agents-iterm.sh

# For Terminal.app
cd /path/to/your/project
./joan-agents/start-agents.sh
```

### Single Terminal Launch

```bash
cd /path/to/your/project
./joan-agents/start-agent.sh
```

### Verification Checklist

After launching, verify:

- [ ] Coordinator terminal is running without errors
- [ ] Coordinator reports polling and dispatching
- [ ] Worker logs appear when tasks are available
- [ ] No MCP connection errors
- [ ] Tags and comments update in Joan as expected

## Upgrading

To upgrade to a new version:

1. Stop all agents: `./stop-agents.sh`
2. Backup your customizations
3. Extract new package
4. Restore customizations to agent definitions
5. Restart agents

## Uninstallation

```bash
# Stop agents
./joan-agents/stop-agents.sh

# Remove agent files
rm -rf joan-agents/
rm -rf .claude/agents/
rm -rf .claude/commands/agents/
```
