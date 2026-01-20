# Joan Multi-Agent System (v4 - Tag-Triggered Orchestration)

This system uses **tag-based state transitions** (no comment parsing), a **single coordinator** that dispatches workers, and git worktrees for parallel development.

## Quick Start

```bash
# 1. Initialize configuration (interactive)
/agents:init

# 2. Check current status
/agents:status             # Dashboard view of queues and workers

# 3. Run coordinator
/agents:start              # Single pass
/agents:start --loop       # Continuous operation (recommended)

# Or equivalently:
/agents:dispatch --loop
```

## Architecture

```
Coordinator + Single-Pass Workers (MCP Proxy Pattern)
──────────────────────────────────────────────────────────────────────────
  Coordinator (has MCP access)
       │
       ├── 1. Poll Joan (once per interval)
       ├── 2. Build work packages with task data
       ├── 3. Dispatch workers with work packages via prompt
       │       │
       │       ├──► BA-worker (task X) ──────► returns JSON result
       │       ├──► Architect-worker (task Y) ─► returns JSON result
       │       ├──► Dev-worker (task Z) ──────► returns JSON result
       │       ├──► Reviewer-worker (task W) ─► returns JSON result
       │       └──► Ops-worker (task V) ──────► returns JSON result
       │
       ├── 4. Execute joan_actions from worker results
       ├── 5. Verify post-conditions (retry if needed)
       └── 6. Sleep → repeat (in loop mode)

  Key Principles:
  • Workers do NOT have MCP access - they return action requests
  • Coordinator executes all MCP operations (tags, comments, moves)
  • Post-condition verification ensures changes are applied
  • Self-healing: anomaly detection cleans stale tags automatically
```

### Why MCP Proxy Pattern?

Subagents spawned via the Task tool cannot access MCP servers (platform limitation).
The solution:

1. **Workers are "pure functions"** - receive work package, return structured result
2. **Coordinator has MCP access** - executes all Joan API operations
3. **Structured results** - workers return `WorkerResult` JSON with `joan_actions`
4. **Post-condition verification** - coordinator re-fetches to confirm changes

See `shared/joan-shared-specs/docs/workflow/worker-result-schema.md` for the full schema.

## Configuration

Agents read from `.joan-agents.json` in project root:

```json
{
  "projectId": "uuid-from-joan",
  "projectName": "My Project",
  "settings": {
    "model": "opus",
    "pollingIntervalMinutes": 10,
    "maxIdlePolls": 6,
    "staleClaimMinutes": 60
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
| `staleClaimMinutes` | 60 | Minutes before orphaned dev claims are auto-released |

**Model Selection:**
- `opus` - Best instruction-following, most thorough (recommended for complex workflows)
- `sonnet` - Faster, lower cost, good for simpler tasks
- `haiku` - Fastest, lowest cost, for very simple operations

Change model anytime with `/agents:model`.

With defaults: agents auto-shutdown after 1 hour of inactivity (6 polls × 10 min).

Override per-run with `--max-idle=N`:
```bash
/agents:start --loop --max-idle=12  # Shutdown after 2 hours idle
```

## Invocation Modes

The coordinator supports two modes via the `--loop` flag:

### Single Pass (default)
```bash
/agents:start
/agents:dispatch
```
- Process all available tasks once
- Exit when queue is empty
- Best for: ad-hoc runs, testing, manual intervention

### Loop Mode (--loop)
```bash
/agents:start --loop
/agents:dispatch --loop
```
- Poll continuously until max idle reached
- Auto-shutdown after N empty polls
- Best for: autonomous operation, overnight runs

## Coordinator Workflow

The coordinator uses a smart polling pattern with MCP Proxy execution:

1. **Poll** - Fetch all tasks from Joan (once per interval)
2. **Recover** - Release stale claims, clean anomalous tags (self-healing)
3. **Queue** - Build priority queues based on tags
4. **Dispatch** - Build work packages, spawn workers with task data via prompt
5. **Claim** - For dev tasks, atomically claim before dispatch
6. **Execute** - Process worker JSON results, execute `joan_actions` via MCP
7. **Verify** - Re-fetch tasks to confirm changes applied (retry if needed)
8. **Sleep** - Wait for poll interval (in loop mode)
9. **Repeat** - Continue until idle threshold reached

This reduces Joan API calls to 1 poll per interval and ensures reliable state transitions.

## Agent Communication Protocol

All agents communicate through Joan MCP and task comments/tags.

### Tag Conventions

**State Tags (set by agents):**

| Tag | Meaning | Set By | Removed By |
|-----|---------|--------|------------|
| `Needs-Clarification` | Task has unanswered questions | BA | BA |
| `Ready` | Requirements complete | BA | Architect |
| `Plan-Pending-Approval` | Plan created, awaiting approval | Architect | Architect |
| `Planned` | Plan approved, available for devs | Architect, Reviewer | Dev |
| `Claimed-Dev-N` | Dev N is implementing this task | Coordinator | Dev |
| `Dev-Complete` | All DEV sub-tasks done | Dev | Reviewer |
| `Design-Complete` | All DES sub-tasks done | Dev | Reviewer |
| `Test-Complete` | All TEST sub-tasks pass | Dev | Reviewer |
| `Review-In-Progress` | Reviewer is actively reviewing | Reviewer | Reviewer |
| `Rework-Requested` | Reviewer found issues, needs fixes | Reviewer, Ops | Dev |
| `Merge-Conflict` | Merge conflict with develop | Ops | Dev |
| `Implementation-Failed` | Dev couldn't complete (manual) | Dev | Human |
| `Worktree-Failed` | Worktree creation failed (manual) | Dev | Human |

**Trigger Tags (set by humans or agents to trigger next action):**

| Tag | Meaning | Set By | Triggers |
|-----|---------|--------|----------|
| `Clarification-Answered` | Human answered BA questions | Human | BA re-evaluates |
| `Plan-Approved` | Human approved the plan | Human | Architect finalizes |
| `Plan-Rejected` | Human rejected the plan | Human | Architect revises |
| `Review-Approved` | Reviewer approved for merge | Reviewer | Ops merges |
| `Ops-Ready` | Human approved merge to develop | Human | Ops merges |
| `Rework-Complete` | Dev finished rework | Dev | Reviewer re-reviews |

### Claim Protocol (Coordinator-Managed)

The **Coordinator** handles task claiming (not individual devs):

1. Coordinator finds task with (`Planned` OR `Rework-Requested` OR `Merge-Conflict`) tag and NO `Claimed-Dev-*` tag
2. Rework/conflict tasks get priority (finish what's started)
3. Coordinator adds `Claimed-Dev-{N}` tag atomically
4. Coordinator verifies claim succeeded (no race condition)
5. Coordinator dispatches Dev worker with task assignment
6. Dev worker processes and on completion: removes `Claimed-Dev-{N}`, removes `Planned`, adds completion tags
7. On failure: Dev removes `Claimed-Dev-{N}`, adds `Implementation-Failed`
8. For rework: Dev reads feedback from ALS review comment (stored by Reviewer)

### Recovering Failed Tasks

Tasks with `Implementation-Failed` or `Worktree-Failed` tags require **manual intervention**:
1. Human reviews failure comment to understand the issue
2. Human resolves the underlying problem
3. Human removes the failure tag
4. Human ensures `Planned` tag is present
5. Task becomes available for devs to claim again

### Automatic Recovery (Self-Healing)

The coordinator automatically recovers from certain failure modes:

**Stale Claim Recovery:**
When the coordinator or workers are killed/crash, `Claimed-Dev-N` tags may remain orphaned on tasks. Each poll cycle, the coordinator:
1. Finds tasks with `Claimed-Dev-N` tags
2. Checks if the task's `updated_at` timestamp is older than `staleClaimMinutes` (default: 60)
3. If stale, removes the orphaned claim tag and adds an ALS comment for audit
4. Task becomes available for other dev workers to claim

**Anomaly Detection (Stale Workflow Tags):**
Tasks can end up with stale workflow tags due to partial failures, manual moves, or worker crashes. Each poll cycle, the coordinator:
1. Finds tasks in terminal columns (Deploy, Done) with workflow tags
2. Removes stale tags: `Review-Approved`, `Ops-Ready`, `Planned`, `Ready`, etc.
3. Detects conflicting tag combinations (e.g., both `Review-Approved` AND `Rework-Requested`)
4. Adds ALS comment documenting the cleanup for audit trail

This makes the system self-healing - no manual intervention needed when workers crash or the coordinator is restarted.

**What triggers recovery:**
- Coordinator killed mid-dispatch (workers still claimed tasks)
- Worker crashes or times out without cleanup
- Network issues preventing worker completion
- Manual task moves in Joan UI that bypass tag cleanup

**What still requires manual intervention:**
- `Implementation-Failed` tag (dev hit unrecoverable error)
- `Worktree-Failed` tag (git worktree creation failed)
- Tasks stuck in unexpected states

### Comment Convention (ALS Breadcrumbs)

**IMPORTANT:** In v4, comments are WRITE-ONLY breadcrumbs. Agents never parse comments to determine state - they use tags exclusively.

All comments use ALS (Agentic Language Syntax) blocks for auditability.
See `shared/joan-shared-specs/docs/workflow/als-spec.md` for the full format and examples.

### Human Actions (Tag-Based)

Instead of comment mentions, humans add tags in Joan UI:

| Action | Add This Tag | Result |
|--------|--------------|--------|
| Approve a plan | `Plan-Approved` | Architect finalizes, moves to Development |
| Reject a plan | `Plan-Rejected` | Architect revises plan |
| Answer clarification | `Clarification-Answered` | BA re-evaluates requirements |
| Approve merge | `Ops-Ready` | Ops merges to develop |
| Handle failed task | Remove `Implementation-Failed` | Task becomes claimable again |

**Legacy comment triggers (`@approve-plan`, `@approve`, `@rework`) are no longer parsed.**

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
   - Ops adds `Planned` tag (makes task claimable)
   - Ops stores conflict details in task description
   - Ops moves task back to Development column
   - Dev claims and manually resolves conflicts
   - Dev removes `Merge-Conflict` tag, adds `Rework-Complete` when resolved

## Worktree Management

**CRITICAL:** Worktrees enable parallel development. Without them, multiple dev workers would conflict by switching branches in the same directory.

Devs create worktrees in `../worktrees/`:

```bash
# Create (done by dev-worker.md Step 2)
git worktree add ../worktrees/{task-id} feature/{branch}

# Work happens here
cd ../worktrees/{task-id}

# Cleanup (done on success)
git worktree remove ../worktrees/{task-id} --force
git worktree prune
```

All worktrees share the same `.git` directory.

**Important:** The dispatcher MUST invoke `/agents:dev-worker` command (not custom prompts) to ensure worktree creation. See dispatch.md Step 4 constraints.

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

### Detailed Flow (Tag-Based)

1. **To Do** → BA evaluates → adds `Ready` tag → moves to Analyse
2. **Analyse** (Ready) → Architect creates plan → removes `Ready`, adds `Plan-Pending-Approval`
3. **Analyse** (Plan-Pending-Approval) → **Human adds `Plan-Approved` tag** OR **Human adds `Plan-Rejected` tag**
4. **Analyse** (Plan-Pending-Approval + Plan-Approved) → Architect finalizes → removes `Plan-Pending-Approval` + `Plan-Approved`, adds `Planned` → moves to Development
4b. **Analyse** (Plan-Rejected) → Architect revises plan → removes `Plan-Rejected`, keeps `Plan-Pending-Approval` → awaits re-approval
5. **Development** (Planned) → Coordinator claims with `Claimed-Dev-N` → dispatches Dev worker
6. **Development** → Dev implements → PR → removes `Claimed-Dev-N` + `Planned`, adds completion tags → moves to Review
7. **Review** → Reviewer validates → merges develop into feature (conflict check)
8. **Review** (approved) → Reviewer adds `Review-Approved` tag
9. **Review** (Review-Approved) → **Human adds `Ops-Ready` tag**
10. **Review** (Review-Approved + Ops-Ready) → Ops merges to develop → removes `Review-Approved` + `Ops-Ready` → moves to Deploy
11. **Development** (rejected) → Reviewer removes completion tags, adds `Rework-Requested` + `Planned`, stores feedback → moves to Development
12. **Development** (Rework-Requested) → Dev addresses feedback → adds `Rework-Complete` → back to Review
13. **Done** (when deployed to production) → Task complete

### Quality Gates

- **BA → Architect**: Requirements must be clear and complete
- **Architect → Dev**: Plan must be approved by human (or revised if rejected)
- **Dev → Reviewer**: All sub-tasks must be checked off
- **Reviewer → Ops**: Must pass code review, tests, and merge conflict check
- **Ops merge gate**: Human must add `Ops-Ready` tag to approve merge
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

On **approval**: Adds `Review-Approved` tag → Ops merges to develop
On **rejection**: Removes completion tags, adds `Rework-Requested` + `Planned`, stores feedback in description → moves to Development
