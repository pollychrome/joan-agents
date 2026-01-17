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
/agents:ops                # Merge PRs, resolve conflicts, track deploys

# 3. Run agents in loop mode (continuous until idle)
/agents:ba --loop
/agents:architect --loop
/agents:dev 1 --loop
/agents:reviewer --loop
/agents:ops --loop

# 4. Start all agents at once
/agents:start all                # Single pass
/agents:start all --loop         # Continuous loop mode
```

## Configuration

Agents read from `.joan-agents.json` in project root:

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

Run `/agents:init` to generate this file interactively.

### Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `model` | opus | Claude model for all agents: `opus`, `sonnet`, or `haiku` |
| `pollingIntervalMinutes` | 10 | Minutes between polls when queue is empty |
| `maxIdlePolls` | 6 | Consecutive empty polls before auto-shutdown |

**Model Selection:**
- `opus` - Best instruction-following, most thorough (recommended for complex workflows)
- `sonnet` - Faster, lower cost, good for simpler tasks
- `haiku` - Fastest, lowest cost, for very simple operations

Change model anytime with `/agents:model`.

With defaults: agents auto-shutdown after 1 hour of inactivity (6 polls × 10 min).

Override per-run with `--max-idle=N`:
```bash
/agents:dev --loop --max-idle=12  # Shutdown after 2 hours idle
```

## Invocation Modes

All agent commands support both modes via the `--loop` flag:

### Single Pass (default)
```bash
/agents:ba
/agents:architect
/agents:dev [id]
/agents:reviewer
/agents:ops
/agents:start all
```
- Process all available tasks once
- Exit when queue is empty
- Best for: ad-hoc runs, testing, manual intervention

### Loop Mode (--loop)
```bash
/agents:ba --loop
/agents:architect --loop
/agents:dev [id] --loop
/agents:reviewer --loop
/agents:ops --loop
/agents:start all --loop
```
- Poll continuously until max idle reached
- Auto-shutdown after N empty polls
- Best for: autonomous operation, overnight runs

**Note:** Each command is a single unified file supporting both modes. There are no separate `-loop` commands.

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
| `Ready` | Requirements complete | BA | Architect (when creating plan) |
| `Plan-Pending-Approval` | Plan created, awaiting @approve-plan | Architect | Architect (on approval) |
| `Planned` | Plan approved, available for devs | Architect, Reviewer (on reject) | Dev (on completion) |
| `Claimed-Dev-N` | Dev N is implementing this task | Dev | Dev (on completion or failure) |
| `Dev-Complete` | All DEV sub-tasks done | Dev | Reviewer (on reject) |
| `Design-Complete` | All DES sub-tasks done | Dev | Reviewer (on reject) |
| `Test-Complete` | All TEST sub-tasks pass | Dev | Reviewer (on reject) |
| `Review-In-Progress` | Reviewer is actively reviewing | Reviewer | Reviewer |
| `Rework-Requested` | Reviewer found issues, needs fixes | Reviewer | Dev |
| `Merge-Conflict` | Late conflict detected during Ops merge (fallback) | Ops | Dev |
| `Implementation-Failed` | Dev couldn't complete (manual recovery) | Dev | Human |
| `Worktree-Failed` | Worktree creation failed (manual recovery) | Dev | Human |

### Claim Protocol

Devs use atomic tagging to claim tasks:
1. Find task with (`Planned` OR `Rework-Requested`) tag and NO `Claimed-Dev-*` tag
2. Rework tasks get priority over new tasks (finish what's started)
3. Immediately add `Claimed-Dev-{N}` tag
4. Re-fetch and verify claim succeeded (no race condition)
5. On completion: Remove `Claimed-Dev-{N}`, remove `Planned`, add completion tags
6. On failure: Remove `Claimed-Dev-{N}`, add `Implementation-Failed` or `Worktree-Failed`
7. For rework: Remove `Rework-Requested` tag, read `@rework` comment for feedback

### Recovering Failed Tasks

Tasks with `Implementation-Failed` or `Worktree-Failed` tags require **manual intervention**:
1. Human reviews failure comment to understand the issue
2. Human resolves the underlying problem
3. Human removes the failure tag
4. Human ensures `Planned` tag is present
5. Task becomes available for devs to claim again

### Comment Convention

Comments follow an `@` / `##` convention:

| Prefix | Meaning | Usage |
|--------|---------|-------|
| `@` | **Request/Trigger** | Agent or human requesting action |
| `##` | **Response/Completion** | Agent responding that action is complete |

This creates an auditable back-and-forth trail in task comments.

### Comment Triggers (Requests)

| Mention | Created By | Consumed By | Effect |
|---------|------------|-------------|--------|
| `@approve-plan` | Human | Architect | Approves plan |
| `@approve` | Reviewer | Ops | Authorizes Ops to merge |
| `@rework` | Reviewer, Ops | Dev, Ops | Dev reads feedback and fixes; Ops moves task back |
| `@rework-requested` | Reviewer | Dev | Alias for @rework |
| `@business-analyst` | Any | BA | Escalates requirement questions |

### Comment Responses

| Response | Created By | Consumed By | Effect |
|----------|------------|-------------|--------|
| `## rework-complete` | Dev | Reviewer, Ops | Signals rework is done, task ready for re-review |

### Rework Detection Logic

Agents check if `@rework` is "resolved" before acting:

1. Find the MOST RECENT `@rework` comment
2. Find the MOST RECENT `## rework-complete` comment
3. If `## rework-complete` timestamp > `@rework` timestamp → rework is complete

This allows multiple rework cycles while maintaining a clear audit trail.

### Merge Conflict Handling (AI-Assisted)

When Ops detects a merge conflict during final merge to `develop`:

1. **Ops** first attempts AI-assisted conflict resolution:
   - Read each conflicting file with conflict markers
   - Analyze both develop and feature versions
   - Resolve conflicts preserving intent from both branches
   - Run verification tests if available

2. **If AI resolution succeeds**:
   - Ops commits the resolution with a descriptive message
   - Ops pushes to develop
   - Ops comments with resolution details
   - Task proceeds to Deploy

3. **If AI resolution fails** (tests fail, complex conflicts):
   - Ops adds `Merge-Conflict` tag to the task
   - Ops adds `Rework-Requested` tag
   - Ops comments with `@rework` including conflict details
   - Ops moves task back to Development column
   - Dev claims and manually resolves conflicts
   - Dev removes `Merge-Conflict` tag when resolved

The `@rework` trigger is reused for consistency with code quality rework flows.

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
  BA    Architect    Dev      Reviewer   Ops
```

### Detailed Flow

1. **To Do** → BA evaluates requirements, adds `Ready` tag
2. **Analyse** (Ready) → Architect creates plan, removes `Ready`, adds `Plan-Pending-Approval`
3. **Analyse** (Plan-Pending-Approval) → Human approves with `@approve-plan`
4. **Development** (Planned) → Architect removes `Plan-Pending-Approval`, adds `Planned`, moves task
5. **Development** → Dev claims with `Claimed-Dev-N`, implements, commits, creates PR
6. **Review** → Dev removes `Planned` + `Claimed-Dev-N`, adds completion tags, moves task
7. **Review** → Reviewer validates, merges develop into feature (conflict check)
8. **Review** → Reviewer comments `@approve` or `@rework`
9. **Review** (on @approve) → Ops merges to develop (with AI conflict resolution if needed), moves to Deploy
10. **Development** (on @rework) → Reviewer removes completion tags, adds `Rework-Requested` + `Planned`, moves to Development
11. **Done** (when deployed to production) → Task complete

### Quality Gates

- **BA → Architect**: Requirements must be clear and complete
- **Architect → Dev**: Plan must be approved by human
- **Dev → Reviewer**: All sub-tasks must be checked off
- **Reviewer → Ops**: Must pass code review, tests, and merge conflict check
- **Ops → Done**: Must be deployed to production

## Agent Responsibilities

| Agent | Primary Role | Key Actions |
|-------|-------------|-------------|
| **BA** | Requirements validation | Evaluates tasks, asks clarifying questions, marks Ready |
| **Architect** | Technical planning | Analyzes codebase, creates implementation plans with sub-tasks |
| **Dev** | Implementation | Claims tasks, implements in worktrees, creates PRs, handles rework |
| **Reviewer** | Quality gate | Merges develop into feature, deep code review, approves or rejects |
| **Ops** | Integration & deployment | Merges to develop with AI conflict resolution, tracks deployment |

### Reviewer Deep Dive

The Reviewer agent performs comprehensive validation:

1. **Merge develop into feature branch** - Ensures PR is reviewed against current develop state
2. **Functional completeness** - All sub-tasks checked, PR matches requirements
3. **Code quality** - Conventions, logic errors, error handling
4. **Security** - No secrets, input validation, no injection vulnerabilities
5. **Testing** - Tests exist and pass, CI green
6. **Design** - UI matches design system (if applicable)

On **approval**: Comments `@approve`, Ops merges to develop
On **rejection**: Removes completion tags, adds `Rework-Requested` + `Planned`, comments `@rework`, moves to Development
