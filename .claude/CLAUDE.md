# Joan Multi-Agent System (v5.3)

Tag-based state transitions, WebSocket-driven dispatch, strict serial dev pipeline.

## Quick Start

```bash
# 1. Initialize configuration (interactive)
/agents:init

# 2. Add tasks to your project (choose one)
/agents:project-planner --file=plan.md    # Import from plan file
/agents:project-planner --interactive     # Guided task creation
# Or add tasks manually in Joan web app

# 3. Start the coordinator
/agents:dispatch --loop                   # WebSocket client (real-time events, recommended)
/agents:dispatch --loop --mode=yolo       # Fully autonomous mode
/agents:dispatch                          # Single pass (testing/debugging)

# 4. Monitor live activity (zero token cost)
joan status                # Global view of all running instances
joan status myproject -f   # Live dashboard for specific project
joan logs myproject        # Tail logs in real-time

# 5. Diagnose and recover invalid task states
/agents:doctor             # Scan all tasks for issues
/agents:doctor --dry-run   # Preview fixes without applying
```

## Architecture

```
Event → Handler Mapping:
─────────────────────────────────────────────────────────────────────
task_created              → handle-ba (evaluate new task)
tag_added: Ready          → handle-architect --mode=plan
tag_added: Plan-Approved  → handle-architect --mode=finalize
tag_added: Planned        → handle-dev
tag_added: Dev-Complete   → handle-reviewer
tag_added: Ops-Ready      → handle-ops

Key Principles:
• Outbound WebSocket connection (works through any firewall)
• Real-time events pushed instantly; periodic catchup scans (5 min) as safety net
• Each handler invocation processes ONE task, stateless
• Safe to restart client at any time without losing work
• Run /agents:doctor for anomaly detection
```

### Three-Tier Processing

- **Tier 1 - Joan Backend (zero tokens):** Deterministic state transitions, tag conflict validation, column auto-movement, YOLO auto-approvals, ALS comment generation from structured_comment
- **Tier 2 - Smart Events (pre-validated):** Semantic event types with pre-fetched task payloads, differential payload filtering per handler
- **Tier 3 - Claude Workers (intelligence only):** BA evaluates requirements, Architect plans, Dev implements, Reviewer reviews, Ops resolves conflicts

### Server-Side Workflow Rules

The Joan backend executes workflow rules automatically when tags are added:

| Trigger | Conditions | Actions | Smart Event |
|---------|------------|---------|-------------|
| `Plan-Approved` | + `Plan-Pending-Approval` | Remove both tags, add `Planned`, move to Development | `task_ready_for_dev` |
| `Plan-Approved` | YOLO mode + `Plan-Pending-Approval` | Auto-add on plan creation | - |
| `Review-Approved` | YOLO mode | Auto-add `Ops-Ready` | `task_ready_for_merge` |
| `Dev-Complete` + `Test-Complete` | All completion tags present | Move to Review | `task_ready_for_review` |
| `Rework-Requested` | - | Move to Development | `task_needs_rework` |
| `Ready` | Task in To Do/Analyse | - | `task_needs_plan` |

**Tag conflict validation (server-side):**

| Rule | Prevents |
|------|----------|
| `Ready` conflicts with `Plan-Pending-Approval`, `Planned` | Invalid state progression |
| `Plan-Approved` requires `Plan-Pending-Approval` | Orphaned approval |
| `Planned` conflicts with `Ready`, `Plan-Pending-Approval` | Multiple queue matching |

### Smart Event Types

| Smart Event | Meaning | Handler |
|-------------|---------|---------|
| `task_needs_ba` | New task needs evaluation | `handle-ba` |
| `task_needs_ba_reevaluation` | Clarification answered | `handle-ba` |
| `task_needs_plan` | Task ready for planning | `handle-architect --mode=plan` |
| `task_ready_for_dev` | Plan approved, ready for implementation | `handle-dev` |
| `task_needs_rework` | Rework requested | `handle-dev` |
| `task_ready_for_review` | All completion tags present | `handle-reviewer` |
| `task_ready_for_merge` | Review approved, ready for ops | `handle-ops` |

Smart events include pre-fetched payloads with task data, tags, and project settings.

### Differential Payloads

Each handler receives only the fields it needs (not the full payload):

| Field | BA | Architect | Dev | Reviewer | Ops |
|-------|-----|-----------|-----|----------|-----|
| `task.description` | 2000 chars | Full | Full | 1000 chars | 200 chars |
| `recent_comments` | Last 3 | Last 5 | 0 (uses handoff) | Last 3 | 0 |
| `subtasks` | No | Yes | Yes | Yes | No |
| `rework_feedback` | No | No | Yes | No | No |
| `columns` | No | Yes | No | No | No |

### Shared Handler Templates

Handler command files reference shared functions in `helpers.md`:
- `extractSmartPayload(TASK_ID, PROJECT_ID)` - Smart payload check + MCP fallback
- `fetchTaskViaMCP(TASK_ID, PROJECT_ID)` - MCP fallback path
- `buildTagSet(tags)` - Tag extraction from both string arrays and `{name, id}` objects
- `extractTagNames(tags)` - Extract tag name strings from MCP objects
- `submitWorkerResult(WORKER_NAME, WORKER_RESULT, WORK_PACKAGE, PROJECT_ID)` - Result submission with structured comment support

### Structured Comments

Workers return a compact `structured_comment` JSON object instead of formatting raw ALS/1 strings. The Joan backend generates the ALS format via `generateALSComment()` in `result-processor.ts`.

```json
"structured_comment": {
  "actor": "ba", "intent": "handoff", "action": "context-handoff",
  "from_stage": "ba", "to_stage": "architect",
  "summary": "Requirements complete",
  "key_decisions": ["Decision 1"]
}
```

The raw `comment` field still works as a fallback.

## Configuration

Agents read from `.joan-agents.json` in project root:

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
    "websocket": {
      "catchupIntervalSeconds": 300
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
| `models` | (see below) | Per-worker model selection (recommended) |
| `model` | opus | Fallback if `models` not set |
| `mode` | standard | `standard` (human gates) or `yolo` (autonomous) |
| `staleClaimMinutes` | 120 | Minutes before orphaned dev claims are auto-released |
| `websocket.catchupIntervalSeconds` | 300 | Seconds between periodic state scans |

**Environment variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `JOAN_AUTH_TOKEN` | (required) | JWT token for WebSocket authentication |
| `JOAN_CATCHUP_INTERVAL` | 300 | Seconds between state scans (0 to disable) |
| `JOAN_WEBSOCKET_DEBUG` | (none) | Set to "1" for debug logging |

### Model Configuration

**Resolution Order:** `settings.models.{worker}` → `settings.model` → built-in default

| Worker | Default | Rationale |
|--------|---------|-----------|
| BA | haiku | Simple evaluation, auto-escalates for complex tasks |
| Architect | opus | Complex planning requires full capability |
| Dev | opus | Implementation quality critical |
| Reviewer | opus | Quality gate, no compromise |
| Ops | haiku | Mechanical merge operations |

**BA Auto-Escalation** to sonnet for: long descriptions (>2000 chars), integration keywords (`integration`, `api`, `third-party`, `external`, `oauth`, `webhook`, `database migration`), many acceptance criteria (>5 bullets).

Change model configuration anytime with `/agents:model`.

### Worker Timeouts

| Setting | Default | Description |
|---------|---------|-------------|
| `workerTimeouts.ba` | 10 | BA worker timeout in minutes |
| `workerTimeouts.architect` | 20 | Architect worker timeout in minutes |
| `workerTimeouts.dev` | 60 | Dev worker timeout in minutes |
| `workerTimeouts.reviewer` | 20 | Reviewer worker timeout in minutes |
| `workerTimeouts.ops` | 15 | Ops worker timeout in minutes |

**IMPORTANT: `devs.count` must be 1 (enforced by schema)** — strict serial execution prevents merge conflicts.

## Workflow Modes

### Standard Mode (default)

Human approval required at two gates:

1. **Plan Approval**: Architect creates plan → Human adds `Plan-Approved` tag → Architect finalizes
2. **Merge Approval**: Reviewer approves → Human adds `Ops-Ready` tag → Ops merges

### YOLO Mode (fully autonomous)

| Stage | Standard Mode | YOLO Mode |
|-------|--------------|-----------|
| **BA** | Asks clarifying questions | Makes autonomous decisions, documents assumptions |
| **Architect** | Waits for `Plan-Approved` tag | Auto-approves plan immediately |
| **Dev** | Fails on errors | Intelligent recovery: retry, reduce scope, proceed |
| **Reviewer** | Rejects on blockers | Only rejects CRITICAL issues (security, crashes) |
| **Ops** | Waits for `Ops-Ready` tag | Auto-merges after approval |

YOLO mode prioritizes forward progress. All decisions are logged as ALS comments for audit trail. CRITICAL issues (security, crashes, data loss) still block.

```bash
# Override mode for a single run
/agents:dispatch --mode=yolo
/agents:dispatch --loop --mode=yolo
```

## WebSocket Client

The client is **state-aware**: startup scan catches missed work, WebSocket pushes events in real-time, periodic scan (5 min) acts as safety net.

**Starting:**
```bash
/agents:dispatch --loop                    # Recommended
JOAN_WEBSOCKET_DEBUG=1 /agents:dispatch --loop  # With debug logging
```

**Authentication:** Set `JOAN_AUTH_TOKEN` env var (JWT from Joan web app Profile → API Token).

**Resilience:** Auto-reconnect with exponential backoff. Safe to restart at any time. Logs at `.claude/logs/websocket-client.log`.

### Serial Pipeline Gate

Handlers enforce strict serial execution:
```
handle-architect checks:
  IF any task in Development OR Review columns → SKIP (pipeline busy)
  ELSE → PROCEED
```

Each handler is stateless — queries Joan for current state on every invocation.

## Agent Communication Protocol

All agents communicate through Joan MCP and task comments/tags.

### Context Handoffs

Workers pass structured context between workflow stages using handoff comments. Context is per-transition (not cumulative).

**Handoff Flow:**
```
BA → Architect → Dev → Reviewer
                         ├── APPROVE → Ops → Done
                         └── REJECT → Dev (rework)
```

| Transition | Contains |
|------------|----------|
| BA → Architect | Requirements clarifications, user answers, key decisions |
| Architect → Dev | Architecture decisions, files to modify, dependencies |
| Dev → Reviewer | Implementation notes, files changed, warnings |
| Reviewer → Ops | Review summary, approval notes |
| Reviewer → Dev (rework) | Blockers with file:line, warnings, suggestions |

**Schema Constraints:** `key_decisions` max 5 (200 chars each), `files_of_interest` max 10, `warnings` max 3 (100 chars each), `dependencies` max 5, total max 3KB per handoff.

See `shared/joan-shared-specs/docs/workflow/als-spec.md` for the full ALS handoff format.

### Tag Conventions

**State Tags (set by agents):**

| Tag | Meaning | Set By | Removed By |
|-----|---------|--------|------------|
| `Needs-Clarification` | Task has unanswered questions | BA | BA |
| `Ready` | Requirements complete | BA | Architect |
| `Plan-Pending-Approval` | Plan created, awaiting approval | Architect | Architect |
| `Planned` | Plan approved, available for devs | Architect, Reviewer | Dev |
| `Claimed-Dev-1` | Dev is implementing (strict serial: always N=1) | Coordinator | Dev |
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

**Trigger Tags (set by humans or agents):**

| Tag | Meaning | Set By | Triggers |
|-----|---------|--------|----------|
| `Clarification-Answered` | Human answered BA questions | Human | BA re-evaluates |
| `Plan-Approved` | Human approved the plan | Human | Architect finalizes |
| `Plan-Rejected` | Human rejected the plan | Human | Architect revises |
| `Review-Approved` | Reviewer approved for merge | Reviewer | Ops merges |
| `Ops-Ready` | Human approved merge to develop | Human | Ops merges |
| `Rework-Complete` | Dev finished rework | Dev | Reviewer re-reviews |

### Claim Protocol (Coordinator-Managed)

1. Coordinator finds task with (`Planned` OR `Rework-Requested` OR `Merge-Conflict`) tag and NO `Claimed-Dev-*` tag
2. Rework/conflict tasks get priority (finish what's started)
3. Coordinator adds `Claimed-Dev-{N}` tag atomically and verifies
4. Coordinator dispatches Dev worker
5. On completion: Dev removes `Claimed-Dev-{N}` + `Planned`, adds completion tags
6. On failure: Dev removes `Claimed-Dev-{N}`, adds `Implementation-Failed`
7. For rework: Dev reads feedback from ALS review comment

### Recovering Failed Tasks

Tasks with `Implementation-Failed` or `Branch-Setup-Failed` require **manual intervention**:
1. Human reviews failure comment
2. Human resolves the underlying problem
3. Human removes the failure tag and ensures `Planned` tag is present
4. Task becomes claimable again

### Automatic Recovery (Self-Healing)

The coordinator automatically recovers from certain failure modes each poll cycle:

- **Stale claims:** Finds `Claimed-Dev-1` tags older than `staleClaimMinutes` (checked via `tag.created_at`), removes orphaned claims
- **Stale workflow tags:** Removes workflow tags from tasks in terminal columns (Deploy, Done), detects conflicting tag combinations
- **Stuck states:** Checks tasks against expected workflow state timeouts, force re-queues stuck tasks
- **State machine validation:** Detects invalid tag combinations, auto-remediates by removing stale tags

All recovery actions are logged as ALS comments for audit trail.

### Doctor Agent

For complex recovery beyond automatic self-healing:

```bash
/agents:doctor             # Diagnose and fix all tasks
/agents:doctor --dry-run   # Preview issues without fixing
/agents:doctor --task=ID   # Diagnose specific task
```

Diagnoses: invalid tag combinations, column/tag mismatches, stale claims, pipeline blockers, orphaned approvals, PR state mismatches.

### Comment Convention (ALS Breadcrumbs)

**IMPORTANT:** Comments are WRITE-ONLY breadcrumbs. Agents never parse comments to determine state — they use tags exclusively.

All comments use ALS (Agentic Language Syntax) blocks for auditability. See `shared/joan-shared-specs/docs/workflow/als-spec.md` for the full format.

### Human Actions (Tag-Based)

**NOTE:** In YOLO mode, `Plan-Approved` and `Ops-Ready` tags are added automatically.

| Action | Add This Tag | Result |
|--------|--------------|--------|
| Approve a plan | `Plan-Approved` | Architect finalizes, moves to Development |
| Reject a plan | `Plan-Rejected` | Architect revises plan |
| Answer clarification | `Clarification-Answered` | BA re-evaluates requirements |
| Approve merge | `Ops-Ready` | Ops merges to develop |
| Handle failed task | Remove `Implementation-Failed` | Task becomes claimable again |

### Merge Conflict Handling (AI-Assisted + Invocation)

When Ops detects a merge conflict during final merge to `develop`:

1. **Ops attempts AI-assisted resolution:** Read conflicting files, analyze both versions, resolve preserving intent, run verification tests
2. **If AI resolution succeeds:** Commit, push to develop, delete feature branch, proceed to Deploy
3. **If AI resolution fails:** Invoke Architect (`Invoke-Architect` tag) for specialist guidance. Architect analyzes, provides strategy (`Architect-Assist-Complete` tag). Ops applies guidance.
4. **If Architect guidance also fails:** Add `Merge-Conflict` + `Rework-Requested` + `Planned` tags, move back to Development for manual resolution by Dev.

### Agent Invocation

Workers can invoke other agents for specialist help. Currently: Ops → Architect (merge conflicts).

**Flow:** Worker returns `invoke_agent` in WorkerResult JSON → Coordinator adds invocation tag + stores context as ALS comment → Invoked agent provides guidance and updates tags → Coordinator resumes original worker.

**Invocation context includes:** `reason`, `question`, `files_of_interest`, `conflict_details`, `resume_as`.

See `shared/joan-shared-specs/docs/workflow/worker-result-schema.md` for the full schema.

## Branch Management

Strict serial mode: one dev worker, direct feature branches in main directory, no worktrees.

**Dev workflow:**
```bash
git checkout develop && git pull origin develop
git checkout -b feature/{task-name}
# ... implement, commit, push ...
git push origin feature/{task-name} -u
```

**Ops merge workflow:**
```bash
git checkout develop && git pull origin develop
git merge origin/feature/{task-name}
git push origin develop
git push origin --delete feature/{task-name}
git branch -d feature/{task-name}
```

**Branch state model:**
```
To Do → Analyse: develop checked out
Analyse → Development: feature branch created
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

Devs check off tasks as completed: `- [x] DEV-1: Description`

### Batched Validation

Dev workers batch validation to avoid redundant runs:
1. Implement all DES-* and DEV-* tasks (no commit yet)
2. Run lint + typecheck ONCE → commit all implementation
3. Write all TEST-* test cases (no commit yet)
4. Run test suite ONCE → commit all tests

Produces 2 commits (implementation + tests) instead of N commits per sub-task.

## Branch Naming

Feature branches: `feature/{task-title-kebab-case}`

Specified in the Architect's plan and used by Devs when creating the branch.

## Complete Task Lifecycle

```
To Do → Analyse → Development → Review → Deploy → Done
  │        │          │           │        │
  BA    Architect    Dev      Reviewer   Ops
```

### Detailed Flow

1. **To Do** → BA evaluates → adds `Ready` → moves to Analyse
2. **Analyse** (Ready) → Architect creates plan → removes `Ready`, adds `Plan-Pending-Approval`
3. **Analyse** → Human adds `Plan-Approved` OR `Plan-Rejected`
4. **Analyse** (Plan-Approved) → Architect finalizes → adds `Planned` → moves to Development
4b. **Analyse** (Plan-Rejected) → Architect revises → awaits re-approval
5. **Development** (Planned) → Coordinator claims → dispatches Dev
6. **Development** → Dev implements → PR → adds completion tags → moves to Review
7. **Review** → Reviewer validates → merges develop into feature
8. **Review** (approved) → Reviewer adds `Review-Approved`
9. **Review** → Human adds `Ops-Ready`
10. **Review** (Ops-Ready) → Ops merges to develop → moves to Deploy
11. **Review** (rejected) → Reviewer adds `Rework-Requested` + `Planned` → moves to Development
12. **Development** (Rework) → Dev addresses feedback → adds `Rework-Complete` → back to Review

### Quality Gates

- **BA → Architect**: Requirements must be clear and complete
- **Architect → Dev**: Plan must be approved by human (or revised if rejected)
- **Dev → Reviewer**: All sub-tasks must be checked off
- **Reviewer → Ops**: Must pass code review, tests, and merge conflict check
- **Ops merge gate**: Human must add `Ops-Ready` tag
- **Ops → Done**: Must be deployed to production

## Agent Responsibilities

| Agent | Primary Role | Key Actions |
|-------|-------------|-------------|
| **BA** | Requirements validation | Evaluates tasks, asks clarifying questions, marks Ready |
| **Architect** | Technical planning | Analyzes codebase, creates implementation plans with sub-tasks, provides conflict guidance |
| **Dev** | Implementation | Claims tasks, implements on feature branches, creates PRs, handles rework |
| **Reviewer** | Quality gate | Merges develop into feature, deep code review, approves or rejects |
| **Ops** | Integration & deployment | Merges to develop with AI conflict resolution + Architect invocation, tracks deployment |

### Reviewer Deep Dive

1. **Merge develop into feature branch** - Ensures PR reviewed against current develop
2. **Functional completeness** - All sub-tasks checked, PR matches requirements
3. **Code quality** - Conventions, logic errors, error handling
4. **Security** - No secrets, input validation, no injection vulnerabilities
5. **Testing** - Tests exist and pass, CI green
6. **Design** - UI matches design system (if applicable)

On **approval**: Adds `Review-Approved` tag
On **rejection**: Removes completion tags, adds `Rework-Requested` + `Planned`, stores feedback → moves to Development
