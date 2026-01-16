# Joan Multi-Agent System (v3 - Task Queue Edition)

This system uses git worktrees for true parallel feature development, with intelligent task queuing and automatic idle shutdown.

## Quick Start

```bash
# 1. Initialize configuration (interactive)
/agents:init

# 2. Run agents (single pass - process once and exit)
/agents:ba                 # Process To Do → Analyse
/agents:architect          # Create/approve plans
/agents:dev                # Implement one task
/agents:dev 2              # Dev #2
/agents:reviewer           # Code review completed tasks
/agents:pm                 # Merge PRs, track deploys

# 3. Run agents in loop mode (continuous until idle)
/agents:ba --loop
/agents:architect --loop
/agents:dev 1 --loop
/agents:reviewer --loop
/agents:pm --loop

# 4. Start all agents at once
/agents:start all
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
    "reviewer": { "enabled": true },
    "projectManager": { "enabled": true },
    "devs": { "enabled": true, "count": 2 }
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
/agents:dev --loop --max-idle=12  # Shutdown after 2 hours idle
```

## Invocation Modes

### Single Pass (default)
```bash
/agents:ba
/agents:architect
/agents:dev [id]
/agents:reviewer
/agents:pm
```
- Process all available tasks once
- Exit when queue is empty
- Best for: ad-hoc runs, testing, manual intervention

### Loop Mode
```bash
/agents:ba --loop
/agents:architect --loop
/agents:dev [id] --loop
/agents:reviewer --loop
/agents:pm --loop
```
- Poll continuously until max idle reached
- Auto-shutdown after N empty polls
- Best for: autonomous operation, overnight runs

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

| Tag | Meaning | Set By | Removed By |
|-----|---------|--------|------------|
| `Needs-Clarification` | Task has unanswered questions | BA | BA |
| `Ready` | Requirements complete | BA | Architect |
| `Plan-Pending-Approval` | Plan created, awaiting @architect | Architect | Architect |
| `Planned` | Plan approved, available for devs | Architect, Reviewer (on reject) | Dev |
| `Claimed-Dev-N` | Dev N is implementing this task | Dev | Dev |
| `Dev-Complete` | All DEV sub-tasks done | Dev | Reviewer (on reject) |
| `Design-Complete` | All DES sub-tasks done | Dev | Reviewer (on reject) |
| `Test-Complete` | All TEST sub-tasks pass | Dev | Reviewer (on reject) |
| `Review-In-Progress` | Reviewer is actively reviewing | Reviewer | Reviewer |
| `Rework-Requested` | Reviewer found issues, needs fixes | Reviewer | Dev |
| `Merge-Conflict` | Late conflict detected during PM merge | PM | Dev |
| `Implementation-Failed` | Dev couldn't complete | Dev | - |

### Claim Protocol

Devs use atomic tagging to claim tasks:
1. Find task with (`Planned` OR `Rework-Requested`) tag and NO `Claimed-Dev-*` tag
2. Rework tasks get priority over new tasks (finish what's started)
3. Immediately add `Claimed-Dev-{N}` tag
4. Re-fetch and verify claim succeeded (no race condition)
5. Remove claim tag when done (success or failure)
6. For rework: Remove `Rework-Requested` tag, read `@rework` comment for feedback

### Comment Triggers

| Mention | Created By | Consumed By | Effect |
|---------|------------|-------------|--------|
| `@architect` | Human | Architect | Approves plan |
| `@approve` | Reviewer | PM | Authorizes PM to merge |
| `@rework` | Reviewer | Dev, PM | Dev reads feedback and fixes; PM moves task back |
| `@rework-requested` | Reviewer | Dev | Alias for @rework - Dev reads feedback and fixes |
| `@business-analyst` | Any | BA | Escalates requirement questions |

## Worktree Management

Devs create worktrees in `../worktrees/`:

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

Devs check off tasks as completed:
- [x] DEV-1: Description

## Branch Naming

Feature branches: `feature/{task-title-kebab-case}`

This name is specified in the Architect's plan and used by Devs to create worktrees.

## Auto-Shutdown Behavior

Agents track consecutive empty polls:
- Each time a poll returns no actionable tasks, `idle_count++`
- When `idle_count >= maxIdlePolls`, agent shuts down gracefully
- Finding tasks resets `idle_count = 0`

This ensures agents don't run indefinitely when there's no work, while staying active during productive periods.

## Complete Task Lifecycle

```
To Do → Analyse → Development → Review → Deploy → Done
  │        │          │           │        │
  BA    Architect    Dev      Reviewer    PM
```

### Detailed Flow

1. **To Do** → BA evaluates requirements
2. **Analyse** (Ready) → Architect creates plan
3. **Analyse** (Plan-Pending-Approval) → Human approves with `@architect`
4. **Development** (Planned) → Dev claims with `Claimed-Dev-N`
5. **Development** → Dev implements, commits, creates PR
6. **Review** (Dev-Complete, Design-Complete, Test-Complete) → Reviewer validates
7. **Review** → Reviewer merges develop into feature branch (conflict check)
8. **Review** → Reviewer comments `@approve` or `@rework`
9. **Deploy** (on @approve) → PM merges to develop, tracks deployment
10. **Development** (on @rework) → Dev addresses feedback, back to step 6
11. **Done** (when deployed) → Task complete

### Quality Gates

- **BA → Architect**: Requirements must be clear and complete
- **Architect → Dev**: Plan must be approved by human
- **Dev → Reviewer**: All sub-tasks must be checked off
- **Reviewer → PM**: Must pass code review, tests, and merge conflict check
- **PM → Done**: Must be deployed to production

## Agent Responsibilities

| Agent | Primary Role | Key Actions |
|-------|-------------|-------------|
| **BA** | Requirements validation | Evaluates tasks, asks clarifying questions, marks Ready |
| **Architect** | Technical planning | Analyzes codebase, creates implementation plans with sub-tasks |
| **Dev** | Implementation | Claims tasks, implements in worktrees, creates PRs, handles rework |
| **Reviewer** | Quality gate | Merges develop into feature, deep code review, approves or rejects |
| **PM** | Integration & deployment | Merges to develop, tracks deployment, handles late conflicts |

### Reviewer Deep Dive

The Reviewer agent performs comprehensive validation:

1. **Merge develop into feature branch** - Ensures PR is reviewed against current develop state
2. **Functional completeness** - All sub-tasks checked, PR matches requirements
3. **Code quality** - Conventions, logic errors, error handling
4. **Security** - No secrets, input validation, no injection vulnerabilities
5. **Testing** - Tests exist and pass, CI green
6. **Design** - UI matches design system (if applicable)

On **approval**: Comments `@approve`, PM merges to develop
On **rejection**: Removes completion tags, adds `Rework-Requested` + `Planned`, comments `@rework`
