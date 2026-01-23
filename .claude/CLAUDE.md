# Joan Multi-Agent System (v4.6 - Enhanced Anomaly Detection & Recovery)

This system uses **tag-based state transitions** (no comment parsing), a **single coordinator** that dispatches workers, and a **strict serial dev pipeline** to prevent merge conflicts.

## Quick Start

```bash
# 1. Initialize configuration (interactive)
/agents:init

# 2. Check current status
/agents:status             # Dashboard view of queues and workers

# 3. Run coordinator
/agents:dispatch                       # Single pass (testing/debugging)
/agents:dispatch --loop                # Continuous operation (recommended for production)
/agents:dispatch --mode=yolo           # Fully autonomous (YOLO mode)
/agents:dispatch --loop --mode=yolo    # Continuous YOLO mode

# 4. Monitor live activity (from terminal, not Claude)
joan status                # Global view of all running instances
joan status yolo-test      # Detailed view of specific project
joan logs yolo-test        # Tail logs in real-time

# 5. Diagnose and recover invalid task states
/agents:doctor             # Scan all tasks for issues
/agents:doctor --dry-run   # Preview fixes without applying
```

**Important:** For any run longer than 15 minutes, always use `--loop` mode. It uses an external scheduler that prevents context accumulation issues.

## Architecture

```
Staged Pipeline Architecture (Strict Serial Mode)
──────────────────────────────────────────────────────────────────────────

  ┌─────────────────────────────────────────────────────────────────────┐
  │                      PHASE 1: BA DRAINING                           │
  │  Process ALL tasks in To Do → Move to Analyse with Ready tag        │
  │  (Safe to process all - no code dependencies)                       │
  └─────────────────────────────────────────────────────────────────────┘
                                  ↓
  ┌─────────────────────────────────────────────────────────────────────┐
  │                PHASE 2: STRICT SERIAL DEV PIPELINE                  │
  │                                                                     │
  │  ┌──────────┐   ┌─────────┐   ┌────────┐   ┌──────┐   ┌──────────┐ │
  │  │ Architect│ → │   Dev   │ → │ Review │ → │  Ops │ → │  MERGED  │ │
  │  │ (1 task) │   │(1 task) │   │(1 task)│   │merge │   │to develop│ │
  │  └──────────┘   └─────────┘   └────────┘   └──────┘   └──────────┘ │
  │                                                                     │
  │  ONLY AFTER MERGE → Pick next Ready task for Architect              │
  │  This ensures plans always reference current codebase               │
  └─────────────────────────────────────────────────────────────────────┘

  Key Principles:
  • BA tasks drain in parallel (no code dependencies)
  • ONE task at a time in the Architect→Dev→Review→Ops pipeline
  • Pipeline gate blocks new planning until current task merges
  • No merge conflicts - each PR merges to fresh develop state
  • Workers do NOT have MCP access - they return action requests
  • Self-healing: anomaly detection cleans stale tags automatically
```

## What's New in v4.6

**Enhanced Anomaly Detection & Recovery** - The coordinator now handles tasks that were manually moved between columns without proper workflow tags:

**Key Improvements:**
1. **Complete WORKFLOW_TAGS list** - Now includes all workflow tags (`Dev-Complete`, `Design-Complete`, `Test-Complete`, etc.) for proper cleanup
2. **Diagnostic for untagged tasks** - Detects tasks in Review/Deploy columns missing required workflow tags
3. **Auto-recovery for manually-moved tasks:**
   - Tasks in Review with no tags → moved back to Development with `Planned` tag
   - Tasks in Deploy with completion tags → moved back to Review for proper approval flow
4. **Better visibility** - Enhanced diagnostics report tasks that don't match any queue

**Why this matters:** Manual task moves (via Joan UI) bypass the agent workflow and leave tasks in inconsistent states. The enhanced detection now catches and auto-fixes these cases, eliminating stuck tasks from manual operations.

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
    "mode": "standard",
    "pollingIntervalMinutes": 5,
    "maxIdlePolls": 12,
    "staleClaimMinutes": 120,
    "stuckStateMinutes": 120,
    "pipeline": {
      "baQueueDraining": true,
      "maxBaTasksPerCycle": 10
    },
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

Run `/agents:init` to generate this file interactively.

### Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `model` | opus | Claude model for all agents: `opus`, `sonnet`, or `haiku` |
| `mode` | standard | Workflow mode: `standard` (human gates) or `yolo` (autonomous) |
| `pollingIntervalMinutes` | 1 | Minutes between polls (1 min recommended for best responsiveness) |
| `maxIdlePolls` | 12 | Consecutive truly idle polls before auto-shutdown |
| `staleClaimMinutes` | 120 | Minutes before orphaned dev claims are auto-released |
| `stuckStateMinutes` | 120 | Minutes before tasks are flagged as stuck in workflow |

### Context Management

The coordinator relies on Claude's **auto-compact** feature for long-running sessions. Key state (TAG_CACHE, COLUMN_CACHE) is rebuilt every poll cycle from Joan MCP, so context summarization doesn't affect correctness. The loop continues indefinitely until max idle polls is reached.

### Pipeline Settings (Strict Serial Mode)

| Setting | Default | Description |
|---------|---------|-------------|
| `pipeline.baQueueDraining` | true | Process all BA tasks before dev pipeline |
| `pipeline.maxBaTasksPerCycle` | 10 | Maximum BA tasks to drain per dispatch cycle |

### Worker Timeouts

| Setting | Default | Description |
|---------|---------|-------------|
| `workerTimeouts.ba` | 10 | BA worker timeout in minutes |
| `workerTimeouts.architect` | 20 | Architect worker timeout in minutes |
| `workerTimeouts.dev` | 60 | Dev worker timeout in minutes |
| `workerTimeouts.reviewer` | 20 | Reviewer worker timeout in minutes |
| `workerTimeouts.ops` | 15 | Ops worker timeout in minutes |

**IMPORTANT: `devs.count` must be 1 (enforced by schema)**
This ensures strict serial execution and prevents merge conflicts.

**Model Selection:**
- `opus` - Best instruction-following, most thorough (recommended for complex workflows)
- `sonnet` - Faster, lower cost, good for simpler tasks
- `haiku` - Fastest, lowest cost, for very simple operations

Change model anytime with `/agents:model`.

With defaults: agents auto-shutdown after 12 minutes of true inactivity (12 polls × 1 min, only counting polls with no work AND no workers running).

Override per-run with `--max-idle=N`:
```bash
/agents:dispatch --loop --max-idle=24  # Shutdown after 2 hours idle
```

### Workflow Modes

The system supports two operational modes:

#### Standard Mode (default, recommended)

Human approval required at two critical gates:

1. **Plan Approval**: Architect creates plan → Human adds `Plan-Approved` tag → Architect finalizes
2. **Merge Approval**: Reviewer approves → Human adds `Ops-Ready` tag → Ops merges

**Best for:**
- Production systems
- High-risk changes
- Learning environments
- Projects with multiple stakeholders

**Guarantees:** Human oversight at critical decision points

#### YOLO Mode (experimental)

Fully autonomous operation with auto-approval at both gates:

1. **Plan Auto-Approval**: Architect creates plan → Auto-approved immediately → Moves to Development
2. **Merge Auto-Approval**: Reviewer approves → Auto-add Ops-Ready → Ops merges immediately

⚠️ **WARNING**: No human review means bad architectural decisions get implemented and poorly reviewed code gets merged.

**Best for:**
- Internal tools and scripts
- Prototyping in sandboxed environments
- Greenfield projects with comprehensive test coverage
- Trusted codebases with strong CI/CD

**Not recommended for:**
- Production systems
- Critical infrastructure
- Systems with compliance requirements

#### Switching Modes

```bash
# Override mode for a single run
/agents:dispatch --mode=yolo
/agents:dispatch --loop --mode=yolo

# Change default mode (edit .joan-agents.json)
{
  "settings": {
    "mode": "yolo"  # or "standard"
  }
}
```

**Audit trail:** In YOLO mode, all auto-approvals are logged as ALS comments for debugging and compliance tracking.

## Invocation Modes

The coordinator supports two modes:

### Single Pass (default)
```bash
/agents:dispatch
```
- Process all available tasks once
- Exit when queue is empty
- Best for: ad-hoc runs, testing, manual intervention

### Continuous Operation (--loop)
```bash
/agents:dispatch --loop
```
- Uses external scheduler to spawn fresh coordinator processes
- Each poll cycle starts with clean context (prevents context bloat)
- Auto-shutdown after N consecutive idle polls
- Best for: autonomous operation, overnight runs, any session >15 minutes

**How it works:**
```
External Scheduler (bash script)
├── spawn: claude /agents:dispatch → exits with fresh context
├── check heartbeat for stuck detection
├── sleep INTERVAL seconds
├── spawn: claude /agents:dispatch → exits with fresh context
└── ... (each invocation starts clean)
```

**Why external scheduler?**
- Internal loop mode accumulated context causing failures after 20-30 minutes
- Context bloat led to partial action execution and verification skips
- External scheduler ensures consistent behavior indefinitely

**When to use:**

| Scenario | Recommended Command |
|----------|---------------------|
| Quick test / debugging | `/agents:dispatch` (single pass) |
| Any run longer than 15 minutes | `/agents:dispatch --loop` |
| Overnight autonomous operation | `/agents:dispatch --loop` |
| Multi-hour background processing | `/agents:dispatch --loop --max-idle=48` |

**Options:**
```bash
/agents:dispatch --loop                      # Default settings
/agents:dispatch --loop --interval=180       # Custom poll interval (3 min)
/agents:dispatch --loop --max-idle=24        # Extended operation (2 hours)
```

**Scheduler settings** (in `.joan-agents.json`):
| Setting | Default | Description |
|---------|---------|-------------|
| `schedulerIntervalSeconds` | 300 | Seconds between coordinator spawns |
| `schedulerStuckTimeoutSeconds` | 600 | Seconds before killing stuck coordinator |
| `schedulerMaxConsecutiveFailures` | 3 | Max failures before scheduler stops |

**Graceful shutdown:**
```bash
touch /tmp/joan-agents-{project-name}.shutdown
```

Logs are written to `.claude/logs/scheduler.log`.

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

### Serial Pipeline Gate

The coordinator enforces a **strict serial gate** on the Architect→Dev→Review→Ops pipeline:

```
Pipeline Gate Check (runs before dispatching Architect)
─────────────────────────────────────────────────────────
  IF any task in Development OR Review that hasn't merged:
    → BLOCK: Don't plan new tasks
    → BA continues draining (no code deps)
  ELSE:
    → CLEAR: Architect can plan next Ready task
```

**Why strict serial?**

| Aspect | Parallel (Old) | Strict Serial (New) |
|--------|---------------|---------------------|
| Merge conflicts | Frequent | None |
| Plan freshness | Often stale | Always current |
| Throughput | Higher nominal | Lower but reliable |
| Rework cycles | Common | Rare |
| Predictability | Chaotic | Linear, trackable |

The trade-off is worth it: avoiding merge conflicts and stale plans saves more time than parallel execution gains.

## Agent Communication Protocol

All agents communicate through Joan MCP and task comments/tags.

### Context Handoffs (v4.2)

Workers pass structured context between workflow stages using **handoff comments**. This enables each worker to receive relevant context from the previous stage while maintaining stateless architecture.

**Key Design Principles:**
- Context is per-transition (not cumulative) - each handoff contains only what the next stage needs
- Persisted in Joan comments (durable across coordinator restarts)
- Structured with enforced schema (prevents context bloat)
- Optional and backward-compatible (existing tasks continue working)

**Handoff Flow:**
```
BA evaluates → BA→Architect handoff
      ↓
Architect plans → reads BA context, produces Architect→Dev handoff
      ↓
Dev implements → reads Architect context, produces Dev→Reviewer handoff
      ↓
Reviewer reviews → reads Dev context
      ├── APPROVE: Reviewer→Ops handoff → Ops merges → Done
      └── REJECT: Reviewer→Dev (rework) handoff → Dev reworks
```

**Handoff Content by Stage:**

| Transition | Contains |
|------------|----------|
| BA → Architect | Requirements clarifications, user answers, key decisions |
| Architect → Dev | Architecture decisions, files to modify, dependencies |
| Dev → Reviewer | Implementation notes, files changed, warnings |
| Reviewer → Ops | Review summary, approval notes |
| Reviewer → Dev (rework) | Blockers with file:line, warnings, suggestions |

**Schema Constraints:**
- `key_decisions`: Max 5 items, 200 chars each
- `files_of_interest`: Max 10 file paths
- `warnings`: Max 3 items, 100 chars each
- `dependencies`: Max 5 items
- `metadata`: Max 1KB serialized
- **Total**: Max 3KB per handoff

See `shared/joan-shared-specs/docs/workflow/als-spec.md` for the full ALS handoff format.

### Tag Conventions

**State Tags (set by agents):**

| Tag | Meaning | Set By | Removed By |
|-----|---------|--------|------------|
| `Needs-Clarification` | Task has unanswered questions | BA | BA |
| `Ready` | Requirements complete | BA | Architect |
| `Plan-Pending-Approval` | Plan created, awaiting approval | Architect | Architect |
| `Planned` | Plan approved, available for devs | Architect, Reviewer | Dev |
| `Claimed-Dev-1` | Dev is implementing this task (strict serial: always N=1) | Coordinator | Dev |
| `Dev-Complete` | All DEV sub-tasks done | Dev | Reviewer |
| `Design-Complete` | All DES sub-tasks done | Dev | Reviewer |
| `Test-Complete` | All TEST sub-tasks pass | Dev | Reviewer |
| `Review-In-Progress` | Reviewer is actively reviewing | Reviewer | Reviewer |
| `Rework-Requested` | Reviewer found issues, needs fixes | Reviewer, Ops | Dev |
| `Merge-Conflict` | Merge conflict with develop | Ops | Dev |
| `Implementation-Failed` | Dev couldn't complete (manual) | Dev | Human |
| `Branch-Setup-Failed` | Branch setup failed (manual) | Dev | Human |
| `Invoke-Architect` | Task needs Architect consultation | Ops | Architect |
| `Architect-Assist-Complete` | Architect provided guidance | Architect | Ops |

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

Tasks with `Implementation-Failed` or `Branch-Setup-Failed` tags require **manual intervention**:
1. Human reviews failure comment to understand the issue
2. Human resolves the underlying problem
3. Human removes the failure tag
4. Human ensures `Planned` tag is present
5. Task becomes available for devs to claim again

### Automatic Recovery (Self-Healing)

The coordinator automatically recovers from certain failure modes:

**Stale Claim Recovery:**
When the coordinator or workers are killed/crash, `Claimed-Dev-1` tags may remain orphaned on tasks. Each poll cycle, the coordinator:
1. Finds tasks with `Claimed-Dev-1` tag (or `Claimed-Dev-N` if legacy config)
2. Checks if the task's `updated_at` timestamp is older than `staleClaimMinutes` (default: 60)
3. If stale, removes the orphaned claim tag and adds an ALS comment for audit
4. Task becomes available for other dev workers to claim

**Anomaly Detection (Stale Workflow Tags):**
Tasks can end up with stale workflow tags due to partial failures, manual moves, or worker crashes. Each poll cycle, the coordinator:
1. Finds tasks in terminal columns (Deploy, Done) with workflow tags
2. Removes stale tags: `Review-Approved`, `Ops-Ready`, `Planned`, `Ready`, etc.
3. Detects conflicting tag combinations (e.g., both `Review-Approved` AND `Rework-Requested`)
4. Adds ALS comment documenting the cleanup for audit trail

**Stuck State Detection:**
Tasks can get stuck in mid-workflow states due to context bloat or lost worker results. Each poll cycle:
1. Checks tasks against expected workflow state timeouts (e.g., plan finalization: 30 min, plan creation: 60 min)
2. Tasks exceeding their timeout are flagged and force re-queued for processing
3. Logs diagnostic comments for debugging

**State Machine Validation:**
Validates that task tag combinations are valid workflow states:
1. Detects invalid tag combinations (e.g., `Ready` + `Plan-Pending-Approval` + `Plan-Approved`)
2. Auto-remediates by removing stale tags (removes `Ready` when plan exists)
3. Prevents tasks from matching multiple queues or none

**Context Window Management:**
Long-running coordinators can experience context drift:
1. Tracks poll cycles (`maxPollCyclesBeforeRestart`, default: 10)
2. In loop mode, exits with code 100 after N cycles to trigger restart
3. External scheduler spawns fresh processes for each dispatch cycle

This makes the system self-healing - no manual intervention needed when workers crash or the coordinator is restarted.

**What triggers recovery:**
- Coordinator killed mid-dispatch (workers still claimed tasks)
- Worker crashes or times out without cleanup
- Network issues preventing worker completion
- Manual task moves in Joan UI that bypass tag cleanup
- Context bloat causing queue-building logic to fail

**What still requires manual intervention:**
- `Implementation-Failed` tag (dev hit unrecoverable error)
- `Branch-Setup-Failed` tag (git branch setup failed)

### Doctor Agent (Manual Recovery Tool)

For complex recovery scenarios beyond automatic self-healing, use the **Doctor agent**:

```bash
/agents:doctor             # Diagnose and fix all tasks
/agents:doctor --dry-run   # Preview issues without fixing
/agents:doctor --task=ID   # Diagnose specific task
/agents:doctor --verbose   # Show detailed diagnostics
```

**What Doctor diagnoses:**

| Issue Type | Description | Auto-Fix |
|------------|-------------|----------|
| Invalid tag combinations | Conflicting tags like `Ready` + `Planned` | Remove stale tag |
| Column/tag mismatch | Task in wrong column for its tags | Move or add missing tag |
| Stale claims | `Claimed-Dev-1` orphaned for >2 hours | Release claim |
| Pipeline blockers | Approved tasks not progressing | Flag for agent attention |
| Orphaned approvals | `Plan-Approved` without `Plan-Pending-Approval` | Restore paired tags |
| PR state mismatch | PR merged but task not in Deploy | Move to Deploy |

**When to use Doctor:**
- Pipeline stuck with no apparent cause
- Scheduler reports idle despite pending work
- After coordinator crashes or context overflow
- Manual task moves left tasks in limbo
- Tasks have conflicting or missing tags

**Example output:**
```
═══════════════════════════════════════════════════════════════
DIAGNOSTIC REPORT
═══════════════════════════════════════════════════════════════

Issues found: 2
Warnings: 1

──────────────────────────────────────────────────────────────
[HIGH] STUCK_PLAN_FINALIZATION
Task: #6 Add user preferences
Column: Analyse
Tags: Plan-Pending-Approval, Plan-Approved
Problem: Plan approved 3 hours ago but not finalized
Fix: flag_for_architect - Architect needs to finalize and move to Development

──────────────────────────────────────────────────────────────
[HIGH] ORPHANED_IN_ANALYSE
Task: #7 Implement dark mode
Column: Analyse
Tags: Ready
Problem: Task in Analyse with Ready tag for >1 hour
Fix: flag_for_architect - Architect should plan this task
```

Doctor changes are logged as ALS comments for audit trail.

### Comment Convention (ALS Breadcrumbs)

**IMPORTANT:** In v4, comments are WRITE-ONLY breadcrumbs. Agents never parse comments to determine state - they use tags exclusively.

All comments use ALS (Agentic Language Syntax) blocks for auditability.
See `shared/joan-shared-specs/docs/workflow/als-spec.md` for the full format and examples.

### Human Actions (Tag-Based)

**NOTE:** In YOLO mode, `Plan-Approved` and `Ops-Ready` tags are added automatically by the coordinator. Manual addition is not required.

Instead of comment mentions, humans add tags in Joan UI:

| Action | Add This Tag | Result |
|--------|--------------|--------|
| Approve a plan | `Plan-Approved` | Architect finalizes, moves to Development |
| Reject a plan | `Plan-Rejected` | Architect revises plan |
| Answer clarification | `Clarification-Answered` | BA re-evaluates requirements |
| Approve merge | `Ops-Ready` | Ops merges to develop |
| Handle failed task | Remove `Implementation-Failed` | Task becomes claimable again |

**Legacy comment triggers (`@approve-plan`, `@approve`, `@rework`) are no longer parsed.**

### Merge Conflict Handling (AI-Assisted + Invocation)

When Ops detects a merge conflict during final merge to `develop`:

1. **Ops** first attempts AI-assisted conflict resolution:
   - Read each conflicting file with conflict markers
   - Analyze both develop and feature versions
   - Resolve conflicts preserving intent from both branches
   - Run verification tests if available

2. **If AI resolution succeeds**:
   - Ops commits the resolution with a descriptive message
   - Ops pushes to develop, deletes feature branch
   - Ops comments with resolution details
   - Task proceeds to Deploy

3. **If AI resolution fails** (tests fail, complex conflicts):
   - Ops invokes Architect for specialist guidance (adds `Invoke-Architect` tag)
   - Coordinator dispatches Architect in `advisory-conflict` mode
   - Architect analyzes both branches, provides resolution strategy
   - Architect adds `Architect-Assist-Complete` tag
   - Coordinator dispatches Ops in `merge-with-guidance` mode
   - Ops applies Architect guidance to resolve conflicts

4. **If even Architect guidance fails** (rare edge case):
   - Ops adds `Merge-Conflict` + `Rework-Requested` + `Planned` tags
   - Ops moves task back to Development column
   - Dev claims and manually resolves conflicts
   - Dev removes `Merge-Conflict` tag, adds `Rework-Complete` when resolved

See [Agent Invocation](#agent-invocation) for the full invocation flow.

## Agent Invocation

Workers can invoke other agents for specialist help during workflow execution.
This enables cross-agent consultation without breaking the tag-based state machine.

**Current Invocation Flow: Ops → Architect (for merge conflicts)**

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Ops → Architect Invocation Flow                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. Ops attempts merge to develop                                        │
│  2. Conflict detected, AI resolution fails (tests don't pass)            │
│  3. Ops returns: { invoke_agent: { agent_type: "architect", ... } }      │
│  4. Coordinator adds Invoke-Architect tag, stores context as ALS comment │
│  5. Coordinator skips sleep, re-polls immediately                        │
│  6. Architect dispatched in advisory-conflict mode                       │
│  7. Architect analyzes both branches, returns resolution strategy        │
│  8. Architect adds Architect-Assist-Complete, removes Invoke-Architect   │
│  9. Coordinator dispatches Ops in merge-with-guidance mode               │
│  10. Ops applies guidance, completes merge, deletes feature branch       │
│                                                                          │
│  Fallback: If guidance also fails → Dev handles manually                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**How invocation works:**

1. **Worker returns `invoke_agent` field** in WorkerResult JSON
2. **Coordinator processes invocation:**
   - Adds invocation tag (e.g., `Invoke-Architect`)
   - Stores invocation context as ALS comment
   - Sets `INVOCATION_PENDING` flag to skip sleep
3. **Coordinator dispatches invoked agent** on next (immediate) poll
4. **Invoked agent provides guidance** and updates tags
5. **Coordinator resumes original worker** with guidance

**Invocation context includes:**
- `reason`: Why invocation is needed
- `question`: Specific question to answer
- `files_of_interest`: Relevant files
- `conflict_details`: For merge conflicts - what each branch changed
- `resume_as`: How to continue after invocation (agent type + mode)

**Design principles:**
- Tag-based (no comment parsing for state)
- Fast resolution (skip sleep when invocation pending)
- Stateless (context stored in ALS comment, not memory)
- Fallback path (graceful degradation if invocation fails)

See `shared/joan-shared-specs/docs/workflow/worker-result-schema.md` for the full `invoke_agent` schema.

## Branch Management

With strict serial mode (one dev worker), we work directly on feature branches in the main directory.
No worktrees needed - the feature branch stays checked out until Ops merges it.

**Dev workflow:**
```bash
# Fresh implementation (from develop)
git checkout develop
git pull origin develop
git checkout -b feature/{task-name}

# Work happens directly in main directory
# ... implement, commit, push ...
git push origin feature/{task-name} -u

# Branch stays checked out until Ops merges
```

**Ops merge workflow:**
```bash
git checkout develop
git pull origin develop
git merge origin/feature/{task-name}
# Resolve conflicts if needed (AI-assisted + Architect invocation)
git push origin develop

# Cleanup: delete feature branch
git push origin --delete feature/{task-name}
git branch -d feature/{task-name}
```

**Why no worktrees?**
- Strict serial mode means only one task is in-flight at a time
- No parallel development = no need for branch isolation
- Simpler workflow, less git complexity
- Feature branch stays on feature until deliberately merged

**Branch state model:**
```
To Do → Analyse: develop checked out
Analyse → Development: feature branch created and checked out
Development → Review: feature branch still checked out
Review → Deploy: Ops merges to develop, deletes feature branch
```

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

This name is specified in the Architect's plan and used by Devs when creating the branch.

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
5. **Development** (Planned) → Coordinator claims with `Claimed-Dev-1` → dispatches Dev worker
6. **Development** → Dev implements → PR → removes `Claimed-Dev-1` + `Planned`, adds completion tags → moves to Review
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

## Monitoring with `joan` CLI

The `joan` command-line tool provides global monitoring of all running agent instances across all projects.

### Installation

```bash
cd ~/joan-agents
./scripts/install-joan-cli.sh
```

This creates a global `joan` command available from any directory.

### Commands

**Global View** - See all running instances at a glance:
```bash
joan status       # Static snapshot
joan status -f    # Live updating view with recent logs
```

Output (static):
```
                          Joan Agents - Global Status
╭─┬───────────┬──────┬──────┬────────┬───────────┬──────────┬───────────────╮
│#│ Project   │ Cycle│ Idle │ Active │ Completed │ Runtime  │ Status        │
├─┼───────────┼──────┼──────┼────────┼───────────┼──────────┼───────────────┤
│1│ yolo-test │   42 │ 0/12 │   2    │    18     │ 02:15:30 │ 🔄 2 workers  │
│2│ prod-app  │  128 │ 2/12 │   0    │    94     │ 08:42:10 │ 💤 Idle (2/12)│
╰─┴───────────┴──────┴──────┴────────┴───────────┴──────────┴───────────────╯
```

Live view (`-f`) adds:
- Auto-refreshing table (2x per second)
- Recent activity panel showing log events from all projects, interleaved by timestamp
- Current time in header
- Press Ctrl+C to exit

**Project Detail** - Drill into specific project:
```bash
joan status yolo-test       # Static snapshot
joan status yolo-test -f    # Live view with logs
```

Shows:
- Configuration (model, mode, poll interval)
- Runtime statistics (cycle, idle count, tasks completed)
- Active workers with duration
- Log file location
- In live mode (`-f`): recent log lines update in real-time

**Tail Logs** - Live log streaming:
```bash
joan logs yolo-test
```

Streams the scheduler log in real-time (equivalent to `tail -f`).

### Features

- **Auto-discovery**: Finds all running instances by scanning `ps` for scheduler processes
- **Global visibility**: Monitor multiple projects from a single command
- **Zero tokens**: Pure local operation, no Claude API calls
- **Project matching**: Partial name matching (e.g., `joan status yolo` matches `yolo-test`)
- **Rich metrics**: Runtime, cycle count, tasks completed, active workers

### Tips

```bash
# Live dashboard - see everything update in real-time
joan status -f

# Live view of specific project
joan status yolo-test -f

# Quick health check (static)
joan status | grep "🔄"  # Show only projects with active workers

# Monitor all projects in background
joan status -f > /dev/null 2>&1 &
```

**Live Mode Features:**
- Updates 2x per second
- Shows recent activity from ALL projects, sorted by timestamp
- Displays which project each log line came from
- Auto-scrolls to show latest events
- Zero token cost - just reads local log files

## Agent Responsibilities

| Agent | Primary Role | Key Actions |
|-------|-------------|-------------|
| **BA** | Requirements validation | Evaluates tasks, asks clarifying questions, marks Ready |
| **Architect** | Technical planning | Analyzes codebase, creates implementation plans with sub-tasks, provides conflict guidance |
| **Dev** | Implementation | Claims tasks, implements on feature branches, creates PRs, handles rework |
| **Reviewer** | Quality gate | Merges develop into feature, deep code review, approves or rejects |
| **Ops** | Integration & deployment | Merges to develop with AI conflict resolution + Architect invocation, tracks deployment |

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
