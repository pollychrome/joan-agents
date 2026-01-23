---
description: Slim coordinator router - routes to focused handlers (~100 lines vs 2143)
argument-hint: [--loop] [--max-idle=N] [--mode=standard|yolo] [--handler=ba|architect|dev|reviewer|ops]
allowed-tools: Bash, Read, Task
---

# Coordinator Router (v2 - Optimized)

Lightweight router that delegates to focused micro-handlers.
~100 lines vs original 2143 lines = 95% token reduction.

## Arguments

- `--loop` → Run continuously via external scheduler
- `--max-idle=N` → Max consecutive idle polls before shutdown
- `--mode=standard|yolo` → Workflow mode override
- `--handler=NAME` → Run specific handler only (event-driven mode)
- `--task=UUID` → Process specific task (with --handler)

## Configuration

```
config = JSON.parse(read(".joan-agents.json"))
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName
MODE = config.settings.mode OR "standard"
MODEL = config.settings.model OR "opus"
MAX_IDLE = config.settings.maxIdlePolls OR 12
```

## Execution Branch

```
IF --loop flag present:
  # Delegate to external scheduler (unchanged from original)
  Report: "Starting external scheduler..."
  SCHEDULER_SCRIPT="$HOME/joan-agents/scripts/joan-scheduler.sh"
  Bash: "$SCHEDULER_SCRIPT" . --mode={MODE} (run_in_background: true)
  EXIT

IF --handler flag present:
  # Event-driven: run specific handler
  GOTO SINGLE_HANDLER
ELSE:
  # Polling: run full dispatch cycle
  GOTO FULL_DISPATCH
```

## SINGLE_HANDLER

Event-driven mode - process single handler/task:

```
HANDLER = --handler value
TASK_ID = --task value (optional)

Report: "Router: Running {HANDLER} handler"

IF HANDLER == "ba":
  IF TASK_ID:
    Task agent: handle-ba --task={TASK_ID}
  ELSE:
    Task agent: handle-ba --all
  EXIT

IF HANDLER == "architect":
  IF TASK_ID:
    Task agent: handle-architect --task={TASK_ID}
  ELSE:
    Task agent: handle-architect --all
  EXIT

IF HANDLER == "dev":
  IF TASK_ID:
    Task agent: handle-dev --task={TASK_ID}
  ELSE:
    Task agent: handle-dev --all
  EXIT

IF HANDLER == "reviewer":
  IF TASK_ID:
    Task agent: handle-reviewer --task={TASK_ID}
  ELSE:
    Task agent: handle-reviewer --all
  EXIT

IF HANDLER == "ops":
  IF TASK_ID:
    Task agent: handle-ops --task={TASK_ID}
  ELSE:
    Task agent: handle-ops --all
  EXIT

Report: "Unknown handler: {HANDLER}"
EXIT with error
```

## FULL_DISPATCH

Full polling cycle - build queues and dispatch handlers:

```
Report: "=== COORDINATOR - {PROJECT_NAME} ==="
Report: "Mode: {MODE}, Model: {MODEL}"

# 1. Write heartbeat
PROJECT_SLUG = PROJECT_NAME.toLowerCase().replace(/[^a-z0-9]+/g, '-')
Bash: echo "$(date -Iseconds)" > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat

# 2. Fetch tasks and build lightweight summary
tasks = mcp__joan__list_tasks(project_id: PROJECT_ID)
columns = mcp__joan__list_columns(PROJECT_ID)

# Build column cache
COLUMN_CACHE = {}
FOR col IN columns:
  COLUMN_CACHE[col.name] = col.id

# Build tag index for O(1) lookups
TAG_INDEX = {}
FOR task IN tasks:
  tagSet = Set()
  FOR tag IN task.tags:
    tagSet.add(tag.name)
  TAG_INDEX[task.id] = tagSet

# 3. Count queue sizes (don't build full queues - just counts)
BA_COUNT = 0
ARCHITECT_COUNT = 0
DEV_COUNT = 0
REVIEWER_COUNT = 0
OPS_COUNT = 0

FOR task IN tasks:
  taskId = task.id
  tags = TAG_INDEX[taskId]

  # BA tasks
  IF task.column_id == COLUMN_CACHE["To Do"] AND NOT tags.has("Ready"):
    BA_COUNT += 1
  ELIF task.column_id == COLUMN_CACHE["Analyse"] AND tags.has("Needs-Clarification") AND tags.has("Clarification-Answered"):
    BA_COUNT += 1

  # Architect tasks
  ELIF task.column_id == COLUMN_CACHE["Review"] AND tags.has("Invoke-Architect") AND NOT tags.has("Architect-Assist-Complete"):
    ARCHITECT_COUNT += 1
  ELIF task.column_id == COLUMN_CACHE["Analyse"] AND tags.has("Plan-Pending-Approval") AND tags.has("Plan-Approved"):
    ARCHITECT_COUNT += 1
  ELIF task.column_id == COLUMN_CACHE["Analyse"] AND tags.has("Ready") AND NOT tags.has("Plan-Pending-Approval"):
    ARCHITECT_COUNT += 1

  # Dev tasks
  ELIF task.column_id == COLUMN_CACHE["Development"] AND NOT isClaimedByAnyDev(tags) AND
       (tags.has("Planned") OR tags.has("Rework-Requested") OR tags.has("Merge-Conflict")) AND
       NOT tags.has("Implementation-Failed") AND NOT tags.has("Branch-Setup-Failed"):
    DEV_COUNT += 1

  # Reviewer tasks
  ELIF task.column_id == COLUMN_CACHE["Review"] AND
       (tags.has("Dev-Complete") OR tags.has("Rework-Complete")) AND
       NOT tags.has("Review-In-Progress") AND NOT tags.has("Review-Approved"):
    REVIEWER_COUNT += 1

  # Ops tasks
  ELIF (task.column_id == COLUMN_CACHE["Review"] OR task.column_id == COLUMN_CACHE["Deploy"]) AND
       tags.has("Review-Approved") AND tags.has("Ops-Ready"):
    OPS_COUNT += 1

Report: "Queues: BA={BA_COUNT}, Arch={ARCHITECT_COUNT}, Dev={DEV_COUNT}, Rev={REVIEWER_COUNT}, Ops={OPS_COUNT}"

# 4. Dispatch handlers in priority order (only if work exists)
DISPATCHED = 0

# P0: Invocations (highest priority)
IF ARCHITECT_COUNT > 0 AND hasInvocationPending(tasks, TAG_INDEX, COLUMN_CACHE):
  Report: "Dispatching Architect (invocation priority)"
  Task agent: handle-architect --all
  DISPATCHED += 1

# P1: Ops (finish what's started)
IF OPS_COUNT > 0:
  Report: "Dispatching Ops"
  Task agent: handle-ops --all
  DISPATCHED += 1

# P2: Reviewer
IF REVIEWER_COUNT > 0:
  Report: "Dispatching Reviewer"
  Task agent: handle-reviewer --all
  DISPATCHED += 1

# P3: Dev (strict serial - only if pipeline clear)
IF DEV_COUNT > 0 AND NOT hasPipelineBlocker(tasks, TAG_INDEX, COLUMN_CACHE):
  Report: "Dispatching Dev"
  Task agent: handle-dev --all
  DISPATCHED += 1

# P4: Architect (planning)
IF ARCHITECT_COUNT > 0 AND NOT hasInvocationPending(tasks, TAG_INDEX, COLUMN_CACHE):
  # Check pipeline gate for new plans
  IF NOT hasPipelineBlocker(tasks, TAG_INDEX, COLUMN_CACHE):
    Report: "Dispatching Architect (planning)"
    Task agent: handle-architect --all
    DISPATCHED += 1
  ELSE:
    Report: "Architect blocked by pipeline gate"

# P5: BA (always allowed)
IF BA_COUNT > 0:
  Report: "Dispatching BA"
  Task agent: handle-ba --all --max=10
  DISPATCHED += 1

# 5. Report results
Report: ""
Report: "Dispatched {DISPATCHED} handlers"

IF DISPATCHED == 0:
  Report: "No work to dispatch (idle)"
```

## Helper Functions

```
def isClaimedByAnyDev(tags):
  RETURN tags.has("Claimed-Dev-1")

def hasInvocationPending(tasks, TAG_INDEX, COLUMN_CACHE):
  FOR task IN tasks:
    IF task.column_id == COLUMN_CACHE["Review"] AND
       TAG_INDEX[task.id].has("Invoke-Architect") AND
       NOT TAG_INDEX[task.id].has("Architect-Assist-Complete"):
      RETURN true
  RETURN false

def hasPipelineBlocker(tasks, TAG_INDEX, COLUMN_CACHE):
  # Check if any task is in Development or Review that would block new work
  FOR task IN tasks:
    tags = TAG_INDEX[task.id]

    # Active development blocks new plans
    IF task.column_id == COLUMN_CACHE["Development"]:
      IF tags.has("Claimed-Dev-1") OR tags.has("Planned"):
        RETURN true

    # Pending review blocks new plans
    IF task.column_id == COLUMN_CACHE["Review"]:
      IF NOT (tags.has("Review-Approved") AND tags.has("Ops-Ready")):
        RETURN true

  RETURN false
```

---

## Migration Notes

This router replaces `dispatch.md` with ~100 lines vs 2143 lines.

**What moved to handlers:**
- BA dispatch logic → `handle-ba.md`
- Architect dispatch logic → `handle-architect.md`
- Dev dispatch logic → `handle-dev.md`
- Reviewer dispatch logic → `handle-reviewer.md`
- Ops dispatch logic → `handle-ops.md`
- Self-healing → `self-healing.md` (lazy, on-demand)
- Doctor diagnostics → `doctor.md` (existing, unchanged)

**Token savings:**
- Before: 30KB loaded every spawn
- After: ~2KB router + ~3KB per handler (only loaded when needed)
- Typical cycle: 5-8KB vs 30KB = 75% reduction

**Event-driven usage:**
```bash
# Webhook triggers specific handler with task ID
/dispatch/router --handler=architect --task=abc-123
```

**Polling usage:**
```bash
# Full dispatch cycle (backwards compatible)
/dispatch/router
```
