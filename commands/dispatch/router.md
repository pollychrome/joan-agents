---
description: Run coordinator (single pass or continuous WebSocket client)
argument-hint: [--loop] [--mode=standard|yolo] [--handler=ba|architect|dev|reviewer|ops] [--task=UUID]
allowed-tools: Bash, Read, Task
---

# Coordinator Router (v3 - Production)

Lightweight router that delegates to focused micro-handlers.
~370 lines vs original 2,283-line monolith = 84% token reduction.

## Arguments

**CRITICAL: If no `--loop` flag is passed, you MUST run in single-pass mode. Do NOT start the WebSocket client.**

- `--loop` → Start WebSocket client for real-time event-driven dispatch
- No flag → **DEFAULT: Single pass** (process all queues once, then exit)
- `--mode=standard|yolo` → Workflow mode override
- `--handler=NAME` → Run specific handler only (event-driven mode)
- `--task=UUID` → Process specific task (with --handler)

**Argument Detection Rule:**
Look for the LITERAL string `--loop` in the command arguments. If it is NOT present, you are in single-pass mode.

## Configuration

```
config = JSON.parse(read(".joan-agents.json"))
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName
MODE = config.settings.mode OR "standard"
MODEL = config.settings.model OR "opus"
DEV_COUNT = config.agents.devs.count OR 1
STALE_CLAIM_MINUTES = config.settings.staleClaimMinutes OR 120
API_URL = "https://joan-api.alexbbenson.workers.dev"
MODELS = config.settings.models OR {}
METRICS_FILE = ".claude/logs/agent-metrics.jsonl"

# Agent enabled flags (all default to true)
BA_ENABLED = config.agents.businessAnalyst.enabled OR true
ARCHITECT_ENABLED = config.agents.architect.enabled OR true
REVIEWER_ENABLED = config.agents.reviewer.enabled OR true
OPS_ENABLED = config.agents.ops.enabled OR true
DEVS_ENABLED = config.agents.devs.enabled OR true
```

Parse CLI overrides:
1. Look for `--mode=standard` or `--mode=yolo` in command arguments → MODE = cli_value
2. Check environment variable `JOAN_WORKFLOW_MODE` → MODE = env_value
3. Fallback to config value above

## Configuration Validation

```
ERRORS = []

IF NOT PROJECT_ID:
  ERRORS.push("projectId is required in .joan-agents.json. Run /agents:init")

IF NOT PROJECT_NAME:
  ERRORS.push("projectName is required in .joan-agents.json. Run /agents:init")

IF DEV_COUNT !== 1:
  ERRORS.push("devs.count must be 1 for strict serial mode (found: " + DEV_COUNT + "). " +
              "This prevents merge conflicts. Update .joan-agents.json.")

IF ERRORS.length > 0:
  Report: "Configuration validation failed:"
  FOR error IN ERRORS:
    Report: "  - " + error
  EXIT with error
```

## Execution Branch

```
IF --loop flag present:
  GOTO LOOP_MODE

IF --handler flag present:
  GOTO SINGLE_HANDLER
ELSE:
  GOTO FULL_DISPATCH
```

## LOOP_MODE

Start the WebSocket client for real-time event-driven dispatch.

```
PROJECT_SLUG = PROJECT_NAME.toLowerCase().replace(/[^a-z0-9]+/g, '-')

Report: "Starting WebSocket client for real-time event-driven dispatch"
Report: "  Mode: {MODE}"
Report: "  Startup: state-driven (actionable-tasks API)"
Report: ""
Report: "NOTE: If you have existing tasks, run '/agents:clean-project --apply' first"
Report: "      to integrate them into the workflow."
Report: ""
Report: "========================================"
Report: "  MONITORING"
Report: "========================================"
Report: "  Live dashboard:  joan status {PROJECT_SLUG} -f"
Report: "  Tail logs:       joan logs {PROJECT_SLUG}"
Report: "  Global view:     joan status"
Report: ""
Report: "  Stop gracefully: Ctrl+C or kill the process"
Report: "========================================"
Report: ""

# Execute the WebSocket client script
WS_CLIENT_SCRIPT="$HOME/joan-agents/scripts/ws-client.py"

IF WebSocket client script does not exist at $WS_CLIENT_SCRIPT:
  Report: "ERROR: WebSocket client not found at {WS_CLIENT_SCRIPT}"
  Report: "Expected joan-agents repository at ~/joan-agents"
  Report: ""
  Report: "Installation issue - verify joan-agents is cloned to ~/joan-agents:"
  Report: "  git clone https://github.com/pollychrome/joan-agents.git ~/joan-agents"
  EXIT with error

# Auth is handled by ws-client.py which resolves tokens from:
# 1. JOAN_AUTH_TOKEN environment variable
# 2. ~/.joan-mcp/credentials.json (shared with joan-mcp, auto-decrypted)

Bash:
  command: python3 "$HOME/joan-agents/scripts/ws-client.py" --project-dir . --mode {MODE}
  description: Start WebSocket client for real-time event-driven dispatch
  # NOT run_in_background - we want to keep this session alive for monitoring

# Client exited (user stopped it)
Report: ""
Report: "WebSocket client stopped."
EXIT
```

## SINGLE_HANDLER

Event-driven mode - process single handler/task:

```
HANDLER = --handler value
TASK_ID = --task value (optional)
DISPATCH_START = Date.now()

Report: "Router: Running {HANDLER} handler"

IF HANDLER == "ba":
  IF TASK_ID:
    Task agent: handle-ba --task={TASK_ID}
  ELSE:
    Task agent: handle-ba --all

ELIF HANDLER == "architect":
  IF TASK_ID:
    Task agent: handle-architect --task={TASK_ID}
  ELSE:
    Task agent: handle-architect --all

ELIF HANDLER == "dev":
  IF TASK_ID:
    Task agent: handle-dev --task={TASK_ID}
  ELSE:
    Task agent: handle-dev --all

ELIF HANDLER == "reviewer":
  IF TASK_ID:
    Task agent: handle-reviewer --task={TASK_ID}
  ELSE:
    Task agent: handle-reviewer --all

ELIF HANDLER == "ops":
  IF TASK_ID:
    Task agent: handle-ops --task={TASK_ID}
  ELSE:
    Task agent: handle-ops --all

ELSE:
  Report: "Unknown handler: {HANDLER}"
  EXIT with error

# Record session metric for dashboard throughput & cost tracking
recordWorkerSession(HANDLER, TASK_ID, null, DISPATCH_START)
EXIT
```

## FULL_DISPATCH

Full single-pass cycle — build queues and dispatch handlers:

```
Report: "=== COORDINATOR - {PROJECT_NAME} ==="
Report: "Mode: {MODE}, Model: {MODEL}"

# 1. Write heartbeat
PROJECT_SLUG = PROJECT_NAME.toLowerCase().replace(/[^a-z0-9]+/g, '-')
Bash: echo "$(date +%s)" > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat

# 2. Try API-first queue building, fall back to MCP
API_SUCCESS = false
BA_QUEUE = []
ARCHITECT_QUEUE = []
DEV_QUEUE = []
REVIEWER_QUEUE = []
OPS_QUEUE = []
PIPELINE_BLOCKED = false
```

### API-First Queue Building

```
# Try the actionable-tasks API (pre-computed queues, includes recovery info)
Bash:
  command: curl -sf -H "Authorization: Bearer $JOAN_AUTH_TOKEN" \
    "{API_URL}/api/v1/projects/{PROJECT_ID}/actionable-tasks?mode={MODE}&include_payloads=true&include_recovery=true&stale_claim_minutes={STALE_CLAIM_MINUTES}" \
    -o /tmp/joan-dispatch-response.json
  timeout: 15000

IF curl succeeded (exit code 0):
  response = JSON.parse(read("/tmp/joan-dispatch-response.json"))
  API_SUCCESS = true

  # Extract queue counts
  queues = response.queues OR {}
  BA_QUEUE = queues.ba OR []
  ARCHITECT_QUEUE = queues.architect OR []
  DEV_QUEUE = queues.dev OR []
  REVIEWER_QUEUE = queues.reviewer OR []
  OPS_QUEUE = queues.ops OR []

  # Pipeline status
  pipeline = response.pipeline OR {}
  PIPELINE_BLOCKED = pipeline.blocked OR false

  # Log summary
  summary = response.summary OR {}
  Report: "API: {summary.total_actionable} actionable, {summary.total_recovery_issues} recovery, {summary.pending_human_action} pending human"

  IF PIPELINE_BLOCKED:
    Report: "Pipeline BLOCKED: '{pipeline.blocking_task_title}' - {pipeline.blocking_reason}"

  # Log recovery issues (informational — doctor/API handle remediation)
  recovery = response.recovery OR {}
  FOR stale IN (recovery.stale_claims OR []):
    Report: "  STALE CLAIM: '{stale.task_title}' ({stale.claim_age_minutes}m)"
  FOR anomaly IN (recovery.anomalies OR []):
    Report: "  ANOMALY: '{anomaly.task_title}' [{anomaly.type}]"

ELSE:
  Report: "API unavailable, falling back to MCP queue building"

# Refresh heartbeat (milestone: API phase complete)
Bash: echo "$(date +%s)" > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat
```

### MCP Fallback Queue Building

```
IF NOT API_SUCCESS:
  # Fetch tasks and columns via MCP
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

  # Count queue sizes
  BA_COUNT = 0
  ARCHITECT_COUNT = 0
  DEV_COUNT_Q = 0
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
      DEV_COUNT_Q += 1

    # Reviewer tasks
    ELIF task.column_id == COLUMN_CACHE["Review"] AND
         (tags.has("Dev-Complete") OR tags.has("Rework-Complete")) AND
         NOT tags.has("Review-In-Progress") AND NOT tags.has("Review-Approved"):
      REVIEWER_COUNT += 1

    # Ops tasks
    ELIF (task.column_id == COLUMN_CACHE["Review"] OR task.column_id == COLUMN_CACHE["Deploy"]) AND
         tags.has("Review-Approved") AND tags.has("Ops-Ready"):
      OPS_COUNT += 1

  # Check pipeline blocker (MCP path)
  PIPELINE_BLOCKED = hasPipelineBlocker(tasks, TAG_INDEX, COLUMN_CACHE)

Report: "Queues: BA={len(BA_QUEUE) or BA_COUNT}, Arch={len(ARCHITECT_QUEUE) or ARCHITECT_COUNT}, Dev={len(DEV_QUEUE) or DEV_COUNT_Q}, Rev={len(REVIEWER_QUEUE) or REVIEWER_COUNT}, Ops={len(OPS_QUEUE) or OPS_COUNT}"

# Refresh heartbeat (milestone: queue building complete)
Bash: echo "$(date +%s)" > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat
```

### Cache Project Tags (for Dev Claiming)

```
# Cache project tags for claiming (needed in both API and MCP paths)
project_tags = mcp__joan__list_project_tags(PROJECT_ID)
TAG_CACHE = {}
FOR tag IN project_tags:
  TAG_CACHE[tag.name] = tag.id

# Refresh heartbeat (milestone: tag cache built, entering dispatch)
Bash: echo "$(date +%s)" > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat
```

### Dispatch in Priority Order

```
DISPATCHED = 0

# P0: Invocations (highest priority)
IF API_SUCCESS:
  # API path: check if any architect queue item has mode "advisory-conflict"
  HAS_INVOCATION = any(item.mode == "advisory-conflict" FOR item IN ARCHITECT_QUEUE)
ELSE:
  HAS_INVOCATION = hasInvocationPending(tasks, TAG_INDEX, COLUMN_CACHE)

IF HAS_INVOCATION AND ARCHITECT_ENABLED:
  Report: "Dispatching Architect (invocation priority)"
  Bash: echo "$(date +%s)" > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat
  DISPATCH_START = Date.now()
  Task agent: handle-architect --all
  recordWorkerSession("architect", null, null, DISPATCH_START)
  DISPATCHED += 1

# P1: Ops (finish what's started)
IF (len(OPS_QUEUE) > 0 OR OPS_COUNT > 0) AND OPS_ENABLED:
  Report: "Dispatching Ops"
  Bash: echo "$(date +%s)" > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat
  DISPATCH_START = Date.now()
  Task agent: handle-ops --all
  recordWorkerSession("ops", null, null, DISPATCH_START)
  DISPATCHED += 1

# P2: Reviewer
IF (len(REVIEWER_QUEUE) > 0 OR REVIEWER_COUNT > 0) AND REVIEWER_ENABLED:
  Report: "Dispatching Reviewer"
  Bash: echo "$(date +%s)" > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat
  DISPATCH_START = Date.now()
  Task agent: handle-reviewer --all
  recordWorkerSession("reviewer", null, null, DISPATCH_START)
  DISPATCHED += 1

# P3: Dev (strict serial — only if pipeline clear)
IF (len(DEV_QUEUE) > 0 OR DEV_COUNT_Q > 0) AND DEVS_ENABLED AND NOT PIPELINE_BLOCKED:
  # === DEV CLAIMING PROTOCOL ===
  # Pick first dev task from queue
  IF API_SUCCESS:
    DEV_TASK_ID = DEV_QUEUE[0].task_id
  ELSE:
    # Find first claimable dev task from MCP data
    DEV_TASK_ID = first task in tasks WHERE:
      task.column_id == COLUMN_CACHE["Development"] AND
      NOT isClaimedByAnyDev(TAG_INDEX[task.id]) AND
      (TAG_INDEX[task.id].has("Planned") OR TAG_INDEX[task.id].has("Rework-Requested") OR TAG_INDEX[task.id].has("Merge-Conflict")) AND
      NOT TAG_INDEX[task.id].has("Implementation-Failed") AND NOT TAG_INDEX[task.id].has("Branch-Setup-Failed")

  IF DEV_TASK_ID AND TAG_CACHE["Claimed-Dev-1"]:
    # Add claim tag
    mcp__joan__add_tag_to_task(PROJECT_ID, DEV_TASK_ID, TAG_CACHE["Claimed-Dev-1"])

    # Verify claim (wait 1 second, re-fetch, check tag present)
    Bash: sleep 1
    verify_task = mcp__joan__get_task(DEV_TASK_ID)
    verify_tags = Set(tag.name FOR tag IN verify_task.tags)

    IF verify_tags.has("Claimed-Dev-1"):
      DEV_TASK_TITLE = DEV_QUEUE[0].task_title IF API_SUCCESS ELSE null
      Report: "Dispatching Dev (claimed task {DEV_TASK_ID})"
      Bash: echo "$(date +%s)" > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat
      DISPATCH_START = Date.now()
      Task agent: handle-dev --task={DEV_TASK_ID}
      recordWorkerSession("dev", DEV_TASK_ID, DEV_TASK_TITLE, DISPATCH_START)
      DISPATCHED += 1
    ELSE:
      # Claim failed — release and skip
      Report: "WARN: Dev claim verification failed for {DEV_TASK_ID}, skipping"
      mcp__joan__remove_tag_from_task(PROJECT_ID, DEV_TASK_ID, TAG_CACHE["Claimed-Dev-1"])
  ELSE:
    Report: "Dev queue has work but claiming prerequisites not met"

# P4: Architect (planning — skip if invocation already dispatched above)
IF (len(ARCHITECT_QUEUE) > 0 OR ARCHITECT_COUNT > 0) AND ARCHITECT_ENABLED AND NOT HAS_INVOCATION:
  IF NOT PIPELINE_BLOCKED:
    Report: "Dispatching Architect (planning)"
    Bash: echo "$(date +%s)" > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat
    DISPATCH_START = Date.now()
    Task agent: handle-architect --all
    recordWorkerSession("architect", null, null, DISPATCH_START)
    DISPATCHED += 1
  ELSE:
    Report: "Architect blocked by pipeline gate"

# P5: BA (always allowed)
IF (len(BA_QUEUE) > 0 OR BA_COUNT > 0) AND BA_ENABLED:
  Report: "Dispatching BA"
  Bash: echo "$(date +%s)" > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat
  DISPATCH_START = Date.now()
  Task agent: handle-ba --all --max=10
  recordWorkerSession("ba", null, null, DISPATCH_START)
  DISPATCHED += 1
```

### Re-poll for Downstream Work

After handlers complete, their state changes may create new actionable tasks
(e.g., Reviewer approves → Ops queue populated). Re-poll to chain pipeline
stages within one cycle instead of paying cold-start + sleep per transition.

```
TOTAL_DISPATCHED = DISPATCHED
MAX_REPOLL = 3
REPOLL = 0

WHILE DISPATCHED > 0 AND REPOLL < MAX_REPOLL:
  REPOLL += 1

  # Wait for tag propagation in Joan backend
  Bash: sleep 5

  Report: ""
  Report: "=== RE-POLL {REPOLL}/{MAX_REPOLL} (checking downstream work) ==="

  # Re-query API for fresh queues
  Bash:
    command: curl -sf -H "Authorization: Bearer $JOAN_AUTH_TOKEN" \
      "{API_URL}/api/v1/projects/{PROJECT_ID}/actionable-tasks?mode={MODE}&include_payloads=true&include_recovery=true&stale_claim_minutes={STALE_CLAIM_MINUTES}" \
      -o /tmp/joan-dispatch-response.json
    timeout: 15000

  IF curl failed:
    Report: "Re-poll API failed, ending dispatch loop"
    BREAK

  response = JSON.parse(read("/tmp/joan-dispatch-response.json"))
  queues = response.queues OR {}
  pipeline = response.pipeline OR {}

  OPS_QUEUE = queues.ops OR []
  REVIEWER_QUEUE = queues.reviewer OR []
  DEV_QUEUE = queues.dev OR []
  ARCHITECT_QUEUE = queues.architect OR []
  BA_QUEUE = queues.ba OR []
  PIPELINE_BLOCKED = pipeline.blocked OR false

  Report: "Re-poll queues: Ops={len(OPS_QUEUE)}, Rev={len(REVIEWER_QUEUE)}, Dev={len(DEV_QUEUE)}, Arch={len(ARCHITECT_QUEUE)}, BA={len(BA_QUEUE)}"

  DISPATCHED = 0

  # Dispatch any new work using same priority order

  # P1: Ops
  IF len(OPS_QUEUE) > 0 AND OPS_ENABLED:
    Report: "Dispatching Ops (downstream)"
    Bash: echo "$(date +%s)" > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat
    DISPATCH_START = Date.now()
    Task agent: handle-ops --all
    recordWorkerSession("ops", null, null, DISPATCH_START)
    DISPATCHED += 1

  # P2: Reviewer
  IF len(REVIEWER_QUEUE) > 0 AND REVIEWER_ENABLED:
    Report: "Dispatching Reviewer (downstream)"
    Bash: echo "$(date +%s)" > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat
    DISPATCH_START = Date.now()
    Task agent: handle-reviewer --all
    recordWorkerSession("reviewer", null, null, DISPATCH_START)
    DISPATCHED += 1

  # P3: Dev (if pipeline cleared)
  IF len(DEV_QUEUE) > 0 AND DEVS_ENABLED AND NOT PIPELINE_BLOCKED:
    DEV_TASK_ID = DEV_QUEUE[0].task_id
    IF DEV_TASK_ID AND TAG_CACHE["Claimed-Dev-1"]:
      mcp__joan__add_tag_to_task(PROJECT_ID, DEV_TASK_ID, TAG_CACHE["Claimed-Dev-1"])
      Bash: sleep 1
      verify_task = mcp__joan__get_task(DEV_TASK_ID)
      verify_tags = Set(tag.name FOR tag IN verify_task.tags)
      IF verify_tags.has("Claimed-Dev-1"):
        DEV_TASK_TITLE = DEV_QUEUE[0].task_title IF len(DEV_QUEUE) > 0 ELSE null
        Report: "Dispatching Dev (downstream, claimed {DEV_TASK_ID})"
        Bash: echo "$(date +%s)" > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat
        DISPATCH_START = Date.now()
        Task agent: handle-dev --task={DEV_TASK_ID}
        recordWorkerSession("dev", DEV_TASK_ID, DEV_TASK_TITLE, DISPATCH_START)
        DISPATCHED += 1
      ELSE:
        Report: "WARN: Dev claim verification failed for {DEV_TASK_ID}, skipping"
        mcp__joan__remove_tag_from_task(PROJECT_ID, DEV_TASK_ID, TAG_CACHE["Claimed-Dev-1"])

  # P4: Architect (if pipeline cleared)
  IF len(ARCHITECT_QUEUE) > 0 AND ARCHITECT_ENABLED AND NOT PIPELINE_BLOCKED:
    Report: "Dispatching Architect (downstream)"
    Bash: echo "$(date +%s)" > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat
    DISPATCH_START = Date.now()
    Task agent: handle-architect --all
    recordWorkerSession("architect", null, null, DISPATCH_START)
    DISPATCHED += 1

  # P5: BA
  IF len(BA_QUEUE) > 0 AND BA_ENABLED:
    Report: "Dispatching BA (downstream)"
    Bash: echo "$(date +%s)" > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat
    DISPATCH_START = Date.now()
    Task agent: handle-ba --all --max=10
    recordWorkerSession("ba", null, null, DISPATCH_START)
    DISPATCHED += 1

  TOTAL_DISPATCHED += DISPATCHED

  IF DISPATCHED == 0:
    Report: "No new downstream work, ending dispatch loop"

DISPATCHED = TOTAL_DISPATCHED
```

### Status Report and Exit

```
Report: ""
Report: "Dispatched {DISPATCHED} handlers total"

IF DISPATCHED == 0:
  Report: "No work to dispatch (idle)"

# Write status file for monitoring
Bash: echo '{"dispatched":'$DISPATCHED',"timestamp":"'$(date -Iseconds)'","mode":"{MODE}"}' > /tmp/joan-agents-{PROJECT_SLUG}.status

EXIT
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

def recordWorkerSession(worker_name, task_id, task_title, dispatch_start):
  duration_seconds = Math.round((Date.now() - dispatch_start) / 1000)
  worker_model = MODELS[worker_name] OR MODEL

  Bash: echo '{"timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","event":"worker_session","project":"{PROJECT_NAME}","worker":"{worker_name}","model":"{worker_model}","task_id":"{task_id}","task_title":"{task_title}","success":true,"duration_seconds":{duration_seconds}}' >> {METRICS_FILE}

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

## Architecture Notes

This router (`v3`) replaces the original 2,283-line monolith with a modular design.

**What's in this router:**
- Configuration loading + validation
- WebSocket client launch (`--loop` mode)
- API-first queue building with MCP fallback
- Dev claiming protocol (coordinator-managed)
- Priority-based handler dispatch
- Session recording (worker_session events → agent-metrics.jsonl)
- Status file for monitoring

**What moved to handlers:**
- BA dispatch logic → `handle-ba.md`
- Architect dispatch logic → `handle-architect.md`
- Dev dispatch logic → `handle-dev.md`
- Reviewer dispatch logic → `handle-reviewer.md`
- Ops dispatch logic → `handle-ops.md`

**What moved to API/backend:**
- Self-healing → actionable-tasks API + `/agents:doctor`
- YOLO auto-approvals → Joan backend workflow rules
- Queue computation → actionable-tasks API (MCP fallback retained)

**Token savings:**
- Before: ~20K tokens loaded every spawn (2,283 lines)
- After: ~4K tokens router + ~3K per handler (only loaded when needed)
- Typical single-pass: ~4K vs ~20K = 80% reduction

**Event-driven usage (via ws-client.py):**
```bash
/agents:dispatch --loop
```

**Single-pass usage:**
```bash
/agents:dispatch
/agents:dispatch --mode=yolo
```
