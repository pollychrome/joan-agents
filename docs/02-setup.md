# Setup Guide

This guide walks you through setting up the Joan Multi-Agent Orchestration System.

## Prerequisites

### Required Software

| Software | Version | Purpose |
|----------|---------|---------|
| Claude Code | Latest | Agent runtime |
| Git | 2.x+ | Version control |
| Node.js | 18+ | If your project uses Node |
| iTerm2 | 3.x+ | Recommended terminal (macOS) |

### Required Accounts & Access

- [ ] Claude Code subscription (Max recommended for heavy usage)
- [ ] Git repository access (push permissions)
- [ ] Joan platform account with API access

## Installation Steps

### Step 1: Extract the Package

```bash
# Navigate to your project root
cd /path/to/your/project

# Extract joan-agents
unzip joan-agents.zip

# Verify structure
ls -la joan-agents/
```

You should see:
```
joan-agents/
├── .claude/
│   ├── agents/
│   └── commands/
├── docs/
├── start-agents.sh
├── start-agents-iterm.sh
├── start-agent.sh
├── stop-agents.sh
└── README.md
```

### Step 2: Make Scripts Executable

```bash
chmod +x joan-agents/*.sh
```

### Step 3: Configure Joan MCP Server

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

### Step 5: Set Up Project Structure

Ensure your project has:

```bash
# Create .claude directory if it doesn't exist
mkdir -p .claude

# Copy agent definitions to your project
cp -r joan-agents/.claude/agents .claude/
cp -r joan-agents/.claude/commands .claude/

# Copy CLAUDE.md
cp joan-agents/.claude/CLAUDE.md .claude/
```

### Step 6: Configure Your Project's CLAUDE.md

Edit `.claude/CLAUDE.md` to include your project-specific configuration:

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
- Background: #F9FAFB
- Text: #111827

### Typography
- Headings: Inter
- Body: Inter
- Monospace: JetBrains Mono

### Spacing
- Base unit: 4px
- Scale: 4, 8, 12, 16, 24, 32, 48, 64

## Testing
- Framework: Jest / Vitest / Pytest
- Command: npm test
- Coverage target: 80%

## Joan Configuration
- Project ID: your-project-id
- Board columns: To Do, Analyse, Development, Review, Deploy, Done
```

### Step 7: Verify Installation

Run the coordinator in this terminal to test:

```bash
cd /path/to/your/project
./joan-agents/start-agent.sh
```

You should see:
1. Claude Code starts
2. Coordinator announces itself
3. Coordinator polls Joan for tasks
4. Coordinator reports status (even if no tasks found)

Press `Ctrl+C` to stop the test.

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

## Post-Installation

### Create Joan Board Columns

Ensure your Joan project has these columns:

1. **To Do** - New tasks awaiting analysis
2. **Analyse** - Tasks being evaluated/planned
3. **Development** - Tasks being implemented
4. **Review** - Tasks undergoing automated code review (Reviewer agent)
5. **Deploy** - Tasks merged to develop, awaiting production deployment
6. **Done** - Completed tasks (deployed to production)

### Create Joan Tags

Create these tags in your Joan project:

| Tag | Color | Purpose |
|-----|-------|---------|
| `Needs-Clarification` | Amber | Task has unanswered questions |
| `Clarification-Answered` | Emerald | Human answered BA questions |
| `Ready` | Green | Requirements complete, ready for Architect |
| `Plan-Pending-Approval` | Purple | Plan awaits human approval |
| `Plan-Approved` | Indigo | Plan approved, ready to finalize |
| `Planned` | Blue | Plan finalized, available for Dev to claim |
| `Claimed-Dev-1` through `Claimed-Dev-N` | Gray | Dev N is implementing this task |
| `Dev-Complete` | Green | All DEV sub-tasks done |
| `Design-Complete` | Blue | All DES sub-tasks done |
| `Test-Complete` | Purple | All TEST sub-tasks pass |
| `Review-In-Progress` | Amber | Reviewer is actively reviewing |
| `Review-Approved` | Teal | Review approved, ready for Ops |
| `Rework-Requested` | Red | Reviewer found issues, Dev needs to fix |
| `Rework-Complete` | Lime | Rework done, ready for review |
| `Merge-Conflict` | Orange | Late conflict detected during Ops merge |
| `Implementation-Failed` | Rose | Dev couldn't complete (needs manual recovery) |
| `Worktree-Failed` | Pink | Worktree creation failed (needs manual recovery) |

### Set Up Git Branches

```bash
# Ensure develop branch exists
git checkout -b develop main
git push -u origin develop
```

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
