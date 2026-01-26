# Joan Multi-Agent System (v5.3 - Token Optimized Architecture)

This system uses **tag-based state transitions**, **WebSocket-driven dispatch** for real-time response, and a **strict serial dev pipeline** to prevent merge conflicts.

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

# 4. Monitor live activity (from terminal, zero token cost)
joan status                # Global view of all running instances
joan status myproject -f   # Live dashboard for specific project
joan logs myproject        # Tail logs in real-time

# 5. Diagnose and recover invalid task states (run periodically or on-demand)
/agents:doctor             # Scan all tasks for issues
/agents:doctor --dry-run   # Preview fixes without applying
```

**Why WebSockets?** Real-time response to events with state-aware resilience. The `--loop` mode starts a WebSocket client that:
- Connects outbound to Joan (works through any firewall)
- Receives events instantly via persistent WebSocket connection
- Scans Joan state periodically to catch any missed events (safety net)
- Processes existing backlog on startup

This means you can **safely restart the client at any time** without losing work.

## Architecture

```
WebSocket Real-Time Event Architecture
──────────────────────────────────────────────────────────────────────────

  ┌─────────────────────────────────────────────────────────────────────┐
  │                    Joan Backend (Cloudflare Worker)                  │
  │  ┌───────────────────────────────────────────────────────────────┐  │
  │  │  Routes                       Durable Object                   │  │
  │  │  ┌─────────────┐             ┌─────────────────────┐          │  │
  │  │  │ /tasks      │──event────► │ ProjectEventsDO     │          │  │
  │  │  │ /tags       │             │ - WebSocket conns   │          │  │
  │  │  │ /comments   │             │ - Event broadcast   │          │  │
  │  │  └─────────────┘             └──────────┬──────────┘          │  │
  │  │                                         │                      │  │
  │  │  GET /projects/:id/events/ws ───────────┘                      │  │
  │  │  (WebSocket upgrade)                    │ Push events          │  │
  │  └─────────────────────────────────────────│──────────────────────┘  │
  └────────────────────────────────────────────│──────────────────────────┘
                                               │
                                               ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                       joan-agents (Local)                           │
  │  ┌───────────────────────────────────────────────────────────────┐  │
  │  │  ws-client.py                                                  │  │
  │  │  ┌─────────────────┐    ┌─────────────────┐                    │  │
  │  │  │ WebSocket Conn  │───►│ dispatch_handler│───► claude /agents │  │
  │  │  │  (outbound)     │    │   (same logic)  │                    │  │
  │  │  └─────────────────┘    └─────────────────┘                    │  │
  │  │                                                                │  │
  │  │  Fallback: Catchup scan every 5 min (safety net)               │  │
  │  └────────────────────────────────────────────────────────────────┘  │
  └─────────────────────────────────────────────────────────────────────┘

  Event → Handler Mapping:
  ─────────────────────────────────────────────────────────────────────
  task_created              → handle-ba (evaluate new task)
  tag_added: Ready          → handle-architect --mode=plan
  tag_added: Plan-Approved  → handle-architect --mode=finalize
  tag_added: Planned        → handle-dev
  tag_added: Dev-Complete   → handle-reviewer
  tag_added: Ops-Ready      → handle-ops

  Key Principles:
  • Outbound connection: Works through any firewall (no inbound ports needed)
  • Real-time: Events pushed instantly via WebSocket
  • State-aware: Periodic catchup scans ensure nothing gets stuck
  • Focused handlers: Each invocation processes ONE task
  • Stateless: Handlers check Joan state on each invocation
  • Self-healing: Run /agents:doctor periodically or on-demand
```

## What's New in v5.1

**WebSocket Event Architecture** - Real-time events via outbound WebSocket connections:

**Key Improvements:**
1. **Zero idle cost** - No tokens consumed when waiting for work
2. **Instant response** - Events pushed via WebSocket (<100ms latency)
3. **Works through firewalls** - Outbound WebSocket connection (no inbound ports needed)
4. **Simpler architecture** - Each handler processes one task, stateless design
5. **Better scalability** - No coordinator bottleneck, handlers run independently

**Breaking Changes from v5.0:**
- `webhook-receiver.sh` replaced by `ws-client.py` (WebSocket client)
- HTTP webhook configuration (`webhook.port`, `webhook.secret`) no longer used
- Requires `JOAN_AUTH_TOKEN` environment variable for authentication
- Catchup interval increased from 60s to 300s (5 min) - WebSocket provides real-time events

**Migration:** Same command interface (`/agents:dispatch --loop --mode=yolo`), but now uses WebSocket internally.

## What's New in v5.2 (Hybrid Architecture)

**Server-Side Workflow Rules** - Deterministic state transitions with zero token cost:

Phase 1 of the hybrid architecture moves mechanical operations from Claude to Joan backend, reducing token consumption by ~40-60% for routine workflow transitions.

### Three-Tier Architecture

```
Tier 1: Joan Backend (Zero Tokens)
├── Deterministic state transitions
├── Tag conflict validation
├── Column auto-movement
├── YOLO mode auto-approvals
└── ALS comment generation from structured_comment (v5.3)

Tier 2: Smart Events (Pre-Validated)
├── Semantic event types (task_ready_for_dev vs tag_added)
├── Pre-fetched task payloads
├── Eliminates Claude re-fetching task data
└── Differential payload filtering per handler (v5.3)

Tier 3: Claude Workers (Intelligence Only)
├── BA: Requirements evaluation
├── Architect: Technical planning
├── Dev: Implementation
├── Reviewer: Code review
└── Ops: Conflict resolution
```

### Server-Side Workflow Rules

The Joan backend now executes workflow rules automatically when tags are added:

| Trigger | Conditions | Actions | Smart Event |
|---------|------------|---------|-------------|
| `Plan-Approved` | + `Plan-Pending-Approval` | Remove both tags, add `Planned`, move to Development | `task_ready_for_dev` |
| `Plan-Approved` | YOLO mode + `Plan-Pending-Approval` | Auto-add on plan creation | - |
| `Review-Approved` | YOLO mode | Auto-add `Ops-Ready` | `task_ready_for_merge` |
| `Dev-Complete` + `Test-Complete` | All completion tags present | Move to Review | `task_ready_for_review` |
| `Rework-Requested` | - | Move to Development | `task_needs_rework` |
| `Ready` | Task in To Do/Analyse | - | `task_needs_plan` |

**Validation Rules** (tag conflicts prevented server-side):

| Rule | Prevents |
|------|----------|
| `Ready` conflicts with `Plan-Pending-Approval`, `Planned` | Invalid state progression |
| `Plan-Approved` requires `Plan-Pending-Approval` | Orphaned approval |
| `Planned` conflicts with `Ready`, `Plan-Pending-Approval` | Multiple queue matching |

### Smart Event Types

Smart events replace generic `tag_added` events with semantic, action-oriented events:

| Smart Event | Meaning | Handler |
|-------------|---------|---------|
| `task_needs_ba` | New task needs evaluation | `handle-ba` |
| `task_needs_ba_reevaluation` | Clarification answered | `handle-ba` |
| `task_needs_plan` | Task ready for planning | `handle-architect --mode=plan` |
| `task_ready_for_dev` | Plan approved, ready for implementation | `handle-dev` |
| `task_needs_rework` | Rework requested | `handle-dev` |
| `task_ready_for_review` | All completion tags present | `handle-reviewer` |
| `task_ready_for_merge` | Review approved, ready for ops | `handle-ops` |

Smart events include pre-fetched payloads with task data, tags, and project settings, eliminating the need for handlers to re-fetch.

### Enabling Workflow Rules

Workflow rules are enabled per-project via the `workflow_mode` column:

```sql
-- Enable workflow rules for a project
UPDATE projects SET workflow_mode = 'yolo' WHERE id = 'project-uuid';

-- Standard mode still uses workflow rules but requires human gates
UPDATE projects SET workflow_mode = 'standard' WHERE id = 'project-uuid';
```

| Mode | Server-Side Behavior |
|------|---------------------|
| `standard` | Workflow rules execute, human gates required |
| `yolo` | Workflow rules execute + auto-approval rules active |

### Token Savings

**Before (v5.1):** Each state transition required Claude to:
1. Receive event
2. Fetch task details
3. Validate tag state
4. Determine actions
5. Execute tag/column changes

**After (v5.2):** Joan backend handles steps 2-5 for deterministic transitions:
- ~40-60% reduction in tokens per task lifecycle
- 2-3x faster for mechanical operations
- Claude only invoked for intelligent decisions

### How WebSocket Dispatch Works

The client is **state-aware**, not just event-reactive:

1. **On startup**: Scans Joan state for any actionable work (catches missed events while down)
2. **On WebSocket event**: Dispatches handler for the specific event immediately
3. **Periodically**: Scans Joan state every 5 minutes (safety net for any edge cases)

**Handler dispatch flow:**
1. Client connects to Joan via outbound WebSocket
2. Joan backend pushes events through the connection in real-time
3. Client parses event type and tag changes
4. Handler dispatched via `claude /agents:dispatch/handle-*` with task ID
5. Handler executes focused work on single task

Each handler is stateless and checks Joan state on invocation, ensuring correct behavior regardless of execution order.

**Why state-aware?** WebSockets can disconnect temporarily. The periodic state scan ensures **nothing gets stuck** during brief connection interruptions. The state (tags + columns) is always the source of truth.

## What's New in v5.3 (Token Optimization)

**Differential Payloads, Shared Templates, Structured Comments** - Reduces token consumption by ~35-45% across the agent pipeline through three complementary optimizations.

### Differential Payloads

The WebSocket client now filters smart payloads per-handler, stripping fields each handler doesn't use. Previously all 5 handlers received identical payloads (~3-8KB). Each handler now receives only the fields it actually needs.

| Field | BA | Architect | Dev | Reviewer | Ops |
|-------|-----|-----------|-----|----------|-----|
| `task.description` | 2000 chars | Full | Full | 1000 chars | 200 chars |
| `recent_comments` | Last 3 | Last 5 | 0 (uses handoff) | Last 3 | 0 |
| `subtasks` | No | Yes | Yes | Yes | No |
| `rework_feedback` | No | No | Yes | No | No |
| `columns` | No | Yes | No | No | No |

Enable debug logging to see payload reduction per handler:
```bash
JOAN_WEBSOCKET_DEBUG=1 /agents:dispatch --loop
# Output: "Payload filtered: 4200 -> 2100 bytes (-50%) (handle-ba)"
```

### Shared Handler Templates

Handler command files (`handle-ba.md`, `handle-dev.md`, etc.) now reference shared functions in `helpers.md` instead of duplicating code. This removes ~170 lines of duplication across the 5 handlers.

**Shared functions in `helpers.md`:**
- `extractSmartPayload(TASK_ID, PROJECT_ID)` - Smart payload check + MCP fallback
- `fetchTaskViaMCP(TASK_ID, PROJECT_ID)` - MCP fallback path
- `buildTagSet(tags)` - Tag extraction from both string arrays and `{name, id}` objects
- `extractTagNames(tags)` - Extract tag name strings from MCP objects
- `submitWorkerResult(WORKER_NAME, WORKER_RESULT, WORK_PACKAGE, PROJECT_ID)` - Result submission with structured comment support

### Structured Comments (Server-Side ALS Generation)

Workers now return a compact `structured_comment` JSON object instead of formatting raw ALS/1 strings. The Joan backend generates the ALS format, reducing worker prompt size and improving reliability.

**Before (raw ALS in worker output):**
```
"comment": "ALS/1\nactor: ba\nintent: handoff\naction: context-handoff\nfrom_stage: ba\nto_stage: architect\nsummary: Requirements complete\nkey_decisions:\n- Decision 1"
```

**After (structured JSON, server generates ALS):**
```json
"structured_comment": {
  "actor": "ba", "intent": "handoff", "action": "context-handoff",
  "from_stage": "ba", "to_stage": "architect",
  "summary": "Requirements complete",
  "key_decisions": ["Decision 1"]
}
```

The raw `comment` field still works as a fallback for backward compatibility.

**Backend changes:** `result-processor.ts` includes `StructuredComment` interface and `generateALSComment()` function. The `submit-result.py` client supports `--structured-comment` for JSON submission.

### Token Savings Summary

| Optimization | Reduction |
|-------------|-----------|
| Differential payloads | ~30-40% of payload tokens |
| Shared handler templates | ~170 lines removed from handler system prompts |
| Server-side ALS generation | ~40-80 tokens per handler + reliability improvement |
| **Combined per-task lifecycle** | **~35-45% total reduction** |

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
| `model` | opus | Legacy: Claude model for all agents (fallback if `models` not set) |
| `models` | (see below) | Per-worker model selection (recommended) |
| `mode` | standard | Workflow mode: `standard` (human gates) or `yolo` (autonomous) |
| `staleClaimMinutes` | 120 | Minutes before orphaned dev claims are auto-released (used by doctor) |
| `websocket.catchupIntervalSeconds` | 300 | Seconds between periodic state scans (safety net) |

**Environment variable overrides:**
| Variable | Default | Description |
|----------|---------|-------------|
| `JOAN_AUTH_TOKEN` | (required) | JWT token for WebSocket authentication |
| `JOAN_CATCHUP_INTERVAL` | 300 | Seconds between state scans (set to 0 to disable periodic scans) |
| `JOAN_WEBSOCKET_DEBUG` | (none) | Set to "1" to enable debug logging |

### Model Configuration

Per-worker model selection reduces token costs by ~25-30% while maintaining quality where it matters.

**Resolution Order:** `settings.models.{worker}` → `settings.model` → built-in default

| Worker | Default | Rationale |
|--------|---------|-----------|
| BA | haiku | Simple evaluation, auto-escalates for complex tasks |
| Architect | opus | Complex planning requires full capability |
| Dev | opus | Implementation quality critical |
| Reviewer | opus | Quality gate, no compromise |
| Ops | haiku | Mechanical merge operations |

**Configuration Options:**

```json
// Option 1: Per-worker (recommended, ~25-30% cost savings)
"settings": {
  "models": {
    "ba": "haiku",
    "architect": "opus",
    "dev": "opus",
    "reviewer": "opus",
    "ops": "haiku"
  }
}

// Option 2: Uniform (all workers same model)
"settings": {
  "model": "opus"
}

// Option 3: No config (uses built-in defaults)
"settings": {}
```

**BA Auto-Escalation:**

When BA uses haiku, it automatically escalates to sonnet for complex tasks:
- Long descriptions (>2000 characters)
- Integration keywords: `integration`, `api`, `third-party`, `external`, `oauth`, `webhook`, `database migration`
- Many acceptance criteria (>5 bullets)

Change model configuration anytime with `/agents:model`.

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

#### YOLO Mode (fully autonomous)

Fully autonomous operation with NO human gates:

| Stage | Standard Mode | YOLO Mode |
|-------|--------------|-----------|
| **BA** | Asks clarifying questions | Makes autonomous decisions, documents assumptions |
| **Architect** | Waits for `Plan-Approved` tag | Auto-approves plan immediately |
| **Dev** | Fails on errors | Intelligent recovery: retry, reduce scope, proceed |
| **Reviewer** | Rejects on blockers | Only rejects CRITICAL issues (security, crashes) |
| **Ops** | Waits for `Ops-Ready` tag | Auto-merges after approval |

**YOLO Mode Behaviors:**

1. **BA - Autonomous Requirements**
   - Instead of adding `Needs-Clarification`, makes creative decisions
   - Documents assumptions in stage context
   - Always marks task Ready

2. **Architect - Auto-Approve Plans**
   - Creates plan and immediately adds `Plan-Approved` tag
   - No human review of architectural decisions
   - Proceeds directly to Development

3. **Dev - Intelligent Failure Recovery**
   - On failure, attempts auto-debug and fix
   - If fix fails, reduces scope (implement core only)
   - Documents what was implemented vs. skipped
   - Only truly unrecoverable errors block

4. **Reviewer - Lenient Review**
   - **CRITICAL** issues block (security vulnerabilities, crashes, data loss)
   - **BLOCKER** issues → demoted to warnings, documented but approved
   - Approves with detailed warnings for future cleanup

5. **Ops - Auto-Merge**
   - After Reviewer approval, auto-adds `Ops-Ready` tag
   - Merges to develop automatically

⚠️ **WARNING**: YOLO mode prioritizes forward progress over quality gates.

**Risks:**
- Bad architectural decisions get implemented
- Non-critical bugs ship to develop
- Incomplete features may be merged
- Technical debt accumulates faster

**Mitigations (automatic):**
- All decisions logged as ALS comments for audit trail
- Warnings and skipped items documented in handoffs
- CRITICAL issues (security, crashes) still block
- Recovery attempts documented

**Best for:**
- Internal tools and scripts
- Prototyping in sandboxed environments
- Greenfield projects with comprehensive test coverage
- Trusted codebases with strong CI/CD
- Time-sensitive experiments

**Not recommended for:**
- Production systems
- Critical infrastructure
- Systems with compliance requirements
- Multi-stakeholder projects

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

## WebSocket Client

The WebSocket client is a **state-aware** Python application that connects to Joan and receives real-time events via WebSocket.

### Key Features

- **Outbound connection**: Works through any firewall (no inbound ports needed)
- **Startup scan**: Catches any work missed while client was down
- **Periodic scan**: Every 5 minutes (configurable via `JOAN_CATCHUP_INTERVAL`)
- **Real-time events**: WebSocket pushes events instantly
- **Auto-reconnect**: Exponential backoff on connection loss
- **Graceful restart**: Safe to restart at any time without losing work

### Starting the Client

```bash
# Start via dispatch command (recommended)
/agents:dispatch --loop

# Or run directly
export JOAN_AUTH_TOKEN='your-jwt-token'
python3 ~/joan-agents/scripts/ws-client.py --project-dir .

# With custom catchup interval (default 300 seconds / 5 min)
JOAN_CATCHUP_INTERVAL=600 python3 ~/joan-agents/scripts/ws-client.py --project-dir .

# Enable debug logging
JOAN_WEBSOCKET_DEBUG=1 python3 ~/joan-agents/scripts/ws-client.py --project-dir .
```

### Authentication

The WebSocket client requires a JWT token for authentication:

1. Log in to Joan web app
2. Go to Profile → API Token (or copy from browser dev tools)
3. Set the `JOAN_AUTH_TOKEN` environment variable

### Event → Handler Mapping

**Smart Events (v5.2 - recommended):**

| Smart Event | Handler Dispatched | Pre-fetched Payload |
|-------------|-------------------|---------------------|
| `task_needs_ba` | `handle-ba --task=ID` | ✓ task, tags |
| `task_needs_ba_reevaluation` | `handle-ba --task=ID` | ✓ task, tags |
| `task_needs_plan` | `handle-architect --task=ID --mode=plan` | ✓ task, tags, settings |
| `task_ready_for_dev` | `handle-dev --task=ID` | ✓ task, tags, settings |
| `task_needs_rework` | `handle-dev --task=ID` | ✓ task, tags |
| `task_ready_for_review` | `handle-reviewer --task=ID` | ✓ task, tags |
| `task_ready_for_merge` | `handle-ops --task=ID` | ✓ task, tags |

**Legacy Events (backward compatible):**

| Event | Tag/Condition | Handler Dispatched |
|-------|---------------|-------------------|
| `task_created` | New task in To Do | `handle-ba --task=ID` |
| `tag_added` | `Ready` | `handle-architect --task=ID --mode=plan` |
| `tag_added` | `Plan-Approved` | `handle-architect --task=ID --mode=finalize` |
| `tag_added` | `Plan-Rejected` | `handle-architect --task=ID --mode=revise` |
| `tag_added` | `Planned` | `handle-dev --task=ID` |
| `tag_added` | `Rework-Requested` | `handle-dev --task=ID` |
| `tag_added` | `Merge-Conflict` | `handle-dev --task=ID` |
| `tag_added` | `Dev-Complete` | `handle-reviewer --task=ID` |
| `tag_added` | `Rework-Complete` | `handle-reviewer --task=ID` |
| `tag_added` | `Ops-Ready` | `handle-ops --task=ID` |
| `tag_added` | `Clarification-Answered` | `handle-ba --task=ID` |

**Note:** When workflow rules are enabled, smart events replace many legacy events. The client handles both event types for backward compatibility.

### Graceful Shutdown

```bash
# Send SIGINT or SIGTERM
kill -INT $(pgrep -f ws-client.py)

# Or press Ctrl+C in terminal
```

Logs are written to `.claude/logs/websocket-client.log`.

### State-Aware Resilience

The client automatically catches missed events via periodic state scans. This means:

- **Connection lost?** Auto-reconnect with exponential backoff (1s → 60s max)
- **Events during reconnect?** Caught within 5 minutes by periodic scan
- **Client crashed?** On restart, startup scan catches pending work immediately

For deeper anomaly detection (stale claims, invalid tag combinations), use the doctor:

```bash
/agents:doctor             # Diagnose and fix
/agents:doctor --dry-run   # Preview only
```

### Serial Pipeline Gate

Handlers enforce strict serial execution by checking Joan state before acting:

```
Handler Pipeline Gate Check
─────────────────────────────────────────────────────────
  handle-architect checks:
    IF any task in Development OR Review columns:
      → SKIP: Log "pipeline busy" and exit
    ELSE:
      → PROCEED: Plan this task
```

Each handler is stateless - it queries Joan for current state on every invocation. This ensures correct behavior even if events arrive out of order.

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
2. Checks when the **claim tag was created** (using `tag.created_at`, not `task.updated_at`)
3. If the claim is older than `staleClaimMinutes` (default: 120), removes the orphaned claim tag
4. Adds an ALS comment for audit trail
5. Task becomes available for other dev workers to claim

**Note:** The claim age is calculated from when the tag was added, not when the task was last modified. This ensures claims are properly detected as stale even if the task description or other fields were edited.

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

**IMPORTANT:** Comments are WRITE-ONLY breadcrumbs. Agents never parse comments to determine state - they use tags exclusively.

All comments use ALS (Agentic Language Syntax) blocks for auditability.
See `shared/joan-shared-specs/docs/workflow/als-spec.md` for the full format and examples.

**v5.3:** Workers return `structured_comment` JSON objects instead of formatting raw ALS strings. The Joan backend generates ALS/1 format via `generateALSComment()` in `result-processor.ts`. The raw `comment` field is still supported as a fallback.

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

## Project Planning

The `/agents:project-planner` command creates tasks and milestones from a plan file or interactively.

### Usage

```bash
# Import from plan file
/agents:project-planner --file=plan.md

# Preview before creating
/agents:project-planner --file=plan.md --preview

# Interactive mode (guided questions)
/agents:project-planner --interactive

# Default (interactive)
/agents:project-planner
```

### Supported Plan File Formats

**Format 1: Milestone-hierarchy**
```markdown
## Milestone: MVP Launch
Target: 2024-03-15

### Task: User Authentication
Priority: high
Description: Implement login flow
- Acceptance criteria here
```

**Format 2: Simple task list**
```markdown
## User Authentication
Priority: high
- Requirement bullets
```

**Format 3: Bullet list (quick)**
```markdown
- [ ] User Authentication (high)
- [ ] Dashboard UI (medium)
```

### Task Quality for BA Evaluation

Tasks created by project-planner go to the "To Do" column where the BA agent evaluates them. Good tasks have:
- Clear, specific title (verb + noun)
- Description explaining the goal
- Acceptance criteria as bullet points
- Appropriate priority set

The planner will detect and prompt for clarification on:
- Missing descriptions
- Vague titles ("fix stuff", "update things")
- Missing acceptance criteria
- Unprioritized large-scope tasks

---

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

### Batched Validation (Performance Optimization)

Dev workers use **batched validation** to save ~2-3 minutes per task:

1. **Implement all DES-* tasks** (no commit yet)
2. **Implement all DEV-* tasks** (no commit yet)
3. **Run lint + typecheck ONCE** → commit all implementation
4. **Write all TEST-* test cases** (no commit yet)
5. **Run test suite ONCE** → commit all tests

This produces 2 commits (implementation + tests) instead of N commits per sub-task.
Validation runs once instead of per-task, avoiding redundant lint/typecheck/test runs.

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
╭─┬───────────┬──────┬────────┬────────┬──────┬────┬────┬──────────┬──────────────────╮
│#│ Project   │ Mode │ Events │ Active │ Done │ 🩺 │ ↩️  │ Runtime  │ Status           │
├─┼───────────┼──────┼────────┼────────┼──────┼────┼────┼──────────┼──────────────────┤
│1│ yolo-test │  ⚡  │   42   │   1    │  18  │  0 │  1 │ 02:15:30 │ 📡 Active (5s)   │
│2│ prod-app  │  ⚡  │  128   │   0    │  94  │  2 │  3 │ 08:42:10 │ 📡 Listening (2m)│
╰─┴───────────┴──────┴────────┴────────┴──────┴────┴────┴──────────┴──────────────────╯
```

Mode icons:
- ⚡ = WebSocket mode (real-time events, recommended)
- 🔄 = Polling mode (legacy)

Status indicators (WebSocket mode):
- 📡 Active (Xs ago) - Recent event processed
- 📡 Connected (Xm) - Waiting for events
- 📡 Reconnecting - Connection lost, attempting to reconnect
- 🔄 N workers - Handler(s) currently running

Live view (`-f`) adds:
- Auto-refreshing table (2x per second)
- Recent activity panel showing log events from all projects
- Current time in header
- Press Ctrl+C to exit

**Project Detail** - Drill into specific project:
```bash
joan status yolo-test       # Static snapshot
joan status yolo-test -f    # Live view with logs
```

Shows:
- Configuration (model, workflow mode, dispatch mode)
- Runtime statistics (events received, handlers dispatched, tasks completed)
- Handler breakdown by type (BA, Architect, Dev, Reviewer, Ops)
- Active workers with duration
- Log file location

**Tail Logs** - Live log streaming:
```bash
joan logs yolo-test
```

Streams the WebSocket client log in real-time (equivalent to `tail -f`).

### Features

- **Auto-discovery**: Finds running WebSocket clients and legacy schedulers
- **Mode-aware**: Shows appropriate metrics for WebSocket vs polling mode
- **Global visibility**: Monitor multiple projects from a single command
- **Zero tokens**: Pure local operation, no Claude API calls
- **Project matching**: Partial name matching (e.g., `joan status yolo` matches `yolo-test`)

### Tips

```bash
# Live dashboard - see everything update in real-time
joan status -f

# Live view of specific project
joan status yolo-test -f

# Quick health check - show only WebSocket clients
joan status | grep "⚡"

# Show only projects with active workers
joan status | grep "🔄"
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
