# Joan Multi-Agent System (v3 - Task Queue Edition)

This system uses git worktrees for true parallel feature development, with intelligent task queuing and automatic idle shutdown.

## Quick Start

```bash
# 1. Initialize configuration (interactive)
/agents:init

# 2. Start agents
/agents:start ba           # Start Business Analyst
/agents:start architect    # Start Architect
/agents:start pm           # Start Project Manager
/agents:start worker 1     # Start Worker #1
/agents:start all          # Start all enabled agents
```

## Configuration

Agents read from `.joan-agents.json` in project root:

```json
{
  "projectId": "uuid-from-joan",
  "projectName": "My Project",
  "settings": {
    "pollingIntervalMinutes": 10,
    "maxIdlePolls": 6
  },
  "agents": {
    "businessAnalyst": { "enabled": true },
    "architect": { "enabled": true },
    "projectManager": { "enabled": true },
    "workers": { "enabled": true, "count": 2 }
  }
}
```

Run `/agents:init` to generate this file interactively.

### Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `pollingIntervalMinutes` | 10 | Minutes between polls when queue is empty |
| `maxIdlePolls` | 6 | Consecutive empty polls before auto-shutdown |

With defaults: agents auto-shutdown after 1 hour of inactivity (6 polls × 10 min).

Override per-run with `--max-idle=N`:
```bash
/agents:start ba --max-idle=12  # Shutdown after 2 hours idle
```

## Task Queue Pattern

Agents use a smart polling pattern:

1. **Poll** - Fetch all available tasks from Joan
2. **Queue** - Build local queue of tasks to process
3. **Validate** - Before each task, verify it's still available
4. **Process** - Work on valid tasks without waiting
5. **Repeat** - Only poll again when queue is empty

This reduces Joan API calls while ensuring no tasks are missed or duplicated.

## Agent Communication Protocol

All agents communicate through Joan MCP and task comments/tags.

### Tag Conventions

| Tag | Meaning | Set By |
|-----|---------|--------|
| `Needs-Clarification` | Task has unanswered questions | BA |
| `Ready` | Requirements complete | BA |
| `Plan-Pending-Approval` | Plan created, awaiting @architect | Architect |
| `Planned` | Plan approved, available for workers | Architect |
| `Claimed-Worker-N` | Worker N is implementing this task | Worker |
| `Dev-Complete` | All DEV sub-tasks done | Worker |
| `Design-Complete` | All DES sub-tasks done | Worker |
| `Test-Complete` | All TEST sub-tasks pass | Worker |
| `Implementation-Failed` | Worker couldn't complete | Worker |

### Claim Protocol

Workers use atomic tagging to claim tasks:
1. Find task with `Planned` tag and NO `Claimed-Worker-*` tag
2. Immediately add `Claimed-Worker-{N}` tag
3. Re-fetch and verify claim succeeded (no race condition)
4. Remove claim tag when done (success or failure)

### Comment Triggers

| Mention | Effect |
|---------|--------|
| `@architect` | Approves plan |
| `@approve` | Authorizes PM to merge |
| `@business-analyst` | Escalates requirement questions |

## Worktree Management

Workers create worktrees in `../worktrees/`:

```bash
# Create
git worktree add ../worktrees/{task-id} feature/{branch}

# Work happens here
cd ../worktrees/{task-id}

# Cleanup
git worktree remove ../worktrees/{task-id} --force
git worktree prune
```

All worktrees share the same `.git` directory.

## Sub-Task Format

Plans define sub-tasks executed in order:

```markdown
### Design (first)
- [ ] DES-1: Description

### Development (second)
- [ ] DEV-1: Description
- [ ] DEV-2: Description (depends: DEV-1)

### Testing (last)
- [ ] TEST-1: Description (depends: DEV-1, DES-1)
```

Workers check off tasks as completed:
- [x] DEV-1: Description

## Branch Naming

Feature branches: `feature/{task-title-kebab-case}`

This name is specified in the Architect's plan and used by Workers to create worktrees.

## Auto-Shutdown Behavior

Agents track consecutive empty polls:
- Each time a poll returns no actionable tasks, `idle_count++`
- When `idle_count >= maxIdlePolls`, agent shuts down gracefully
- Finding tasks resets `idle_count = 0`

This ensures agents don't run indefinitely when there's no work, while staying active during productive periods.
