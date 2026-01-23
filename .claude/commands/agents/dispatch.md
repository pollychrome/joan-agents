---
description: Run coordinator (single pass or continuous) - recommended mode
argument-hint: [--loop] [--max-idle=N] [--interval=N] [--mode=standard|yolo]
allowed-tools: Bash, Read
---

# Coordinator (Dispatcher)

The coordinator is the **recommended way** to run the Joan agent system. It:
- Polls Joan once per interval (not N times for N agents)
- Dispatches single-pass workers for available tasks
- Claims dev tasks atomically before dispatching
- Uses tags for all state transitions (no comment parsing)

## Execution Modes

1. **Single Pass** (no `--loop` flag)
   - Runs coordinator once, then exits
   - Best for testing, debugging, manual intervention

2. **Continuous Operation** (`--loop` flag)
   - Uses external scheduler to spawn fresh coordinator processes
   - Prevents context accumulation and degradation
   - Each poll cycle starts with clean context
   - Best for autonomous operation (overnight runs, multi-hour sessions)

**IMPORTANT**: The `--loop` mode uses an external bash scheduler that spawns fresh Claude processes. This eliminates context bloat that causes reliability issues after 20-30 minutes.

## Arguments

- `--loop` → Run continuously using external scheduler (recommended for >15 min runs)
- No flag → Single pass (dispatch once, then exit)
- `--max-idle=N` → Max consecutive idle polls before shutdown (default: 12)
- `--interval=N` → Poll interval in seconds for loop mode (default: 300 = 5 minutes)
- `--mode=standard|yolo` → Override workflow mode (default: read from config)

## Configuration

Load from `.joan-agents.json`:
```
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName
POLL_INTERVAL = config.settings.pollingIntervalMinutes (default: 5)
MAX_IDLE = --max-idle override or config.settings.maxIdlePolls (default: 12)
MODEL = config.settings.model (default: "opus")
MODE = --mode override or config.settings.mode (default: "standard")
DEV_COUNT = config.agents.devs.count (default: 1)  # STRICT SERIAL: Must be 1
STALE_CLAIM_MINUTES = config.settings.staleClaimMinutes (default: 120)
MAX_POLL_CYCLES = config.settings.maxPollCyclesBeforeRestart (default: 10)
STUCK_STATE_MINUTES = config.settings.stuckStateMinutes (default: 120)

# Pipeline settings (strict serial mode)
BA_DRAINING_ENABLED = config.settings.pipeline.baQueueDraining (default: true)
MAX_BA_TASKS_PER_CYCLE = config.settings.pipeline.maxBaTasksPerCycle (default: 10)

# Worker timeout settings (in minutes)
WORKER_TIMEOUT_BA = config.settings.workerTimeouts.ba (default: 10)
WORKER_TIMEOUT_ARCHITECT = config.settings.workerTimeouts.architect (default: 20)
WORKER_TIMEOUT_DEV = config.settings.workerTimeouts.dev (default: 60)
WORKER_TIMEOUT_REVIEWER = config.settings.workerTimeouts.reviewer (default: 20)
WORKER_TIMEOUT_OPS = config.settings.workerTimeouts.ops (default: 15)

# Enabled flags (all default to true)
BA_ENABLED = config.agents.businessAnalyst.enabled
ARCHITECT_ENABLED = config.agents.architect.enabled
REVIEWER_ENABLED = config.agents.reviewer.enabled
OPS_ENABLED = config.agents.ops.enabled
DEVS_ENABLED = config.agents.devs.enabled
```

If config missing, report error and exit.

**IMPORTANT (Strict Serial Mode):**
- `DEV_COUNT` MUST be 1 - the schema enforces this
- This prevents parallel dev work which causes merge conflicts
- Plans always reference the current codebase state

## Execution Branch

Parse arguments:
```
LOOP_MODE = true if --loop flag present, else false
MAX_IDLE_OVERRIDE = --max-idle value if present, else null
INTERVAL_OVERRIDE = --interval value if present, else null
MODE_OVERRIDE = --mode value if present, else null
```

## Parse CLI Parameters

Extract mode override if provided:
- Look for `--mode=standard` or `--mode=yolo` in command arguments
- If found: MODE = cli_value
- Else: MODE = CONFIG.settings.mode || "standard"

Report: "Running in {MODE} mode"

**Branch based on LOOP_MODE:**

### If LOOP_MODE is TRUE (Continuous Operation)

Execute external scheduler to prevent context accumulation:

```
# Get project name for file naming
PROJECT_SLUG = PROJECT_NAME.toLowerCase().replace(/[^a-z0-9]+/g, '-')

# Build scheduler arguments
INTERVAL = INTERVAL_OVERRIDE or config.settings.schedulerIntervalSeconds or 300
STUCK_TIMEOUT = config.settings.schedulerStuckTimeoutSeconds or 600
MAX_IDLE_ARG = MAX_IDLE_OVERRIDE or MAX_IDLE or 12
MAX_FAILURES = config.settings.schedulerMaxConsecutiveFailures or 3

Report: "Starting external scheduler for continuous operation"
Report: "  Poll interval: {INTERVAL}s"
Report: "  Max idle polls: {MAX_IDLE_ARG}"
Report: "  Stuck timeout: {STUCK_TIMEOUT}s"
Report: "  Logs: .claude/logs/scheduler.log"
Report: ""
Report: "To stop gracefully: touch /tmp/joan-agents-{PROJECT_SLUG}.shutdown"
Report: ""

# Execute the external scheduler script
# This script will repeatedly spawn fresh `claude /agents:dispatch` processes
# Expand home directory path for joan-scheduler.sh
SCHEDULER_SCRIPT="$HOME/joan-agents/scripts/joan-scheduler.sh"

IF scheduler script does not exist at $SCHEDULER_SCRIPT:
  Report: "ERROR: Scheduler script not found at {SCHEDULER_SCRIPT}"
  Report: "Expected joan-agents repository at ~/joan-agents"
  Report: ""
  Report: "Installation issue - verify joan-agents is cloned to ~/joan-agents:"
  Report: "  git clone https://github.com/pollychrome/joan-agents.git ~/joan-agents"
  EXIT with error

Bash:
  command: "$HOME/joan-agents/scripts/joan-scheduler.sh" . --interval={INTERVAL} --stuck-timeout={STUCK_TIMEOUT} --max-idle={MAX_IDLE_ARG} --max-failures={MAX_FAILURES}
  description: Run external scheduler for continuous coordinator execution

# The script runs until shutdown signal or max idle reached
EXIT
```

**Why external scheduler?**
- Internal loop mode accumulates context over 20-30 minutes
- Context bloat causes partial action execution and verification skips
- External scheduler spawns fresh Claude processes with clean context
- Each poll cycle maintains consistent behavior indefinitely

### If LOOP_MODE is FALSE (Single Pass)

Continue with single-pass coordinator logic below...

## Configuration Validation

**CRITICAL: Validate config before starting coordinator**

```
ERRORS = []

# Enforce strict serial mode
IF DEV_COUNT !== 1:
  ERRORS.push("devs.count must be 1 for strict serial mode (found: " + DEV_COUNT + "). " +
              "This prevents merge conflicts. Update .joan-agents.json.")

# Validate required settings exist
IF !STUCK_STATE_MINUTES:
  ERRORS.push("Missing settings.stuckStateMinutes - add default 120")

IF !BA_DRAINING_ENABLED OR !MAX_BA_TASKS_PER_CYCLE:
  ERRORS.push("Missing settings.pipeline - add: { baQueueDraining: true, maxBaTasksPerCycle: 10 }")

# Validate worker timeouts exist
REQUIRED_WORKERS = ["ba", "architect", "dev", "reviewer", "ops"]
MISSING_TIMEOUTS = []
FOR worker IN REQUIRED_WORKERS:
  IF !config.settings.workerTimeouts[worker]:
    MISSING_TIMEOUTS.push(worker)

IF MISSING_TIMEOUTS.length > 0:
  ERRORS.push("Missing worker timeouts for: " + MISSING_TIMEOUTS.join(", "))

# Report validation results
IF ERRORS.length > 0:
  Report: "❌ Configuration validation failed:"
  FOR error IN ERRORS:
    Report: "  • " + error
  Report: ""
  Report: "Fix .joan-agents.json and try again, or run /agents:init to regenerate config."
  EXIT with error code

Report: "✓ Configuration validated"
```

## Initialization (Single Pass Only)

```
1. Report: "Coordinator started for {PROJECT_NAME}"
   Report: "Mode: Single pass"
   Report: "Dev workers available: {DEV_COUNT}"
   Report: "Enabled agents: {list enabled agents}"

2. Initialize state:
   TAG_CACHE = {}
   COLUMN_CACHE = {}
   FORCE_REQUEUE = []  # Tasks flagged for priority re-processing
   INVOCATION_PENDING = false  # Set when agent invocation needs fast resolution
```

---

## Single Pass Execution

Execute one coordinator cycle, then exit:

```
Step 1: Cache Tags and Columns
Step 2: Fetch Tasks
Step 2a: Write Heartbeat (for external scheduler monitoring)
Step 2b: Recover Stale Claims (self-healing)
Step 2c: Detect and Clean Anomalies (self-healing)
Step 2d: Detect Stuck Workflow States (self-healing)
Step 2e: State Machine Validation (self-healing)
Step 3: Build Priority Queues
Step 3b: Serial Pipeline Gate Check
Step 4: Dispatch Workers
Step 5: Exit

EXIT (external scheduler will respawn if in loop mode)
```

---

## Step 1: Cache Tags and Columns (once per loop iteration)

```
1. Fetch all project tags:
   tags = mcp__joan__list_project_tags(PROJECT_ID)

2. Build tag name → ID map:
   TAG_CACHE = {
     "Ready": "uuid-1",
     "Planned": "uuid-2",
     "Needs-Clarification": "uuid-3",
     ... (all workflow tags)
   }

3. Fetch all project columns:
   columns = mcp__joan__list_columns(PROJECT_ID)

4. Build column name → ID map:
   COLUMN_CACHE = {
     "To Do": "uuid-a",
     "Analyse": "uuid-b",
     "Development": "uuid-c",
     "Review": "uuid-d",
     "Deploy": "uuid-e",
     "Done": "uuid-f"
   }

5. Helper functions:

   hasTag(task, tagName):
   - Check if task.tags array contains any tag with id === TAG_CACHE[tagName]

   isClaimedByAnyDev(task):
   - For each tagName in TAG_CACHE keys:
       IF tagName starts with "Claimed-Dev-" AND hasTag(task, tagName): RETURN true
   - RETURN false

   inColumn(task, columnName):
   - RETURN task.column_id === COLUMN_CACHE[columnName]

IMPORTANT: Always use inColumn(task, "Column Name") to check columns.
Do NOT compare task.status string - it may be out of sync with column_id.
```

---

## Step 2: Fetch Tasks

```
1. Fetch all tasks for project:
   tasks = mcp__joan__list_tasks(project_id=PROJECT_ID)

2. For each task, note:
   - task.id
   - task.title
   - task.column_id (use this for column checks via inColumn())
   - task.tags[]

NOTE: Do NOT use task.status for column checks - it may be stale.
Always use task.column_id with the inColumn() helper.
```

---

## Step 2a: Write Heartbeat (External Scheduler Support)

Write current timestamp to heartbeat file for external scheduler monitoring.
This allows `/agents:dispatch --loop` to detect stuck coordinators and restart them.

```
# Get project name for heartbeat file naming (sanitize for filesystem)
PROJECT_SLUG = PROJECT_NAME.toLowerCase().replace(/[^a-z0-9]+/g, '-')

Run bash command:
  echo $(date +%s) > /tmp/joan-agents-{PROJECT_SLUG}.heartbeat

# Silent operation - only report if debugging
```

**Why heartbeat?**
- External scheduler (used by `/agents:dispatch --loop`) spawns fresh Claude processes to avoid context overflow
- Scheduler monitors heartbeat file to detect stuck coordinators
- If heartbeat becomes stale (older than stuck_timeout), scheduler kills and restarts
- Even single-pass coordinators write heartbeat - the freshness indicates activity
- This enables self-healing when coordinators freeze due to context bloat

---

## Step 2b: Recover Stale Claims (Self-Healing)

When the coordinator is killed or workers crash, `Claimed-Dev-N` tags may remain orphaned.
This step detects and releases stale claims so tasks can be picked up again.

```
STALE_THRESHOLD_MINUTES = STALE_CLAIM_MINUTES  # From config, default 60

For each task in tasks:
  IF isClaimedByAnyDev(task):

    # Find the claim tag and check when it was CREATED (not task.updated_at)
    # task.updated_at changes on any field update - we need claim creation time
    FOR N in 1..DEV_COUNT:
      claim_tag_name = "Claimed-Dev-{N}"
      IF hasTag(task, claim_tag_name):

        # Find the actual tag object to get its created_at timestamp
        claim_tag = null
        FOR tag IN task.tags:
          IF tag.name == claim_tag_name:
            claim_tag = tag
            BREAK

        IF claim_tag AND claim_tag.created_at:
          claim_age_minutes = (NOW - claim_tag.created_at) in minutes
        ELSE:
          # Fallback to task.updated_at if tag timestamp unavailable
          claim_age_minutes = (NOW - task.updated_at) in minutes

        # A task claimed for longer than STALE_THRESHOLD is likely orphaned
        IF claim_age_minutes > STALE_THRESHOLD_MINUTES:

          Report: "Releasing stale claim on '{task.title}' (Claimed-Dev-{N}, claimed {claim_age_minutes} min ago)"

          # Remove the stale claim tag
          mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE["Claimed-Dev-{N}"])

          # Add comment for audit trail
          mcp__joan__create_task_comment(task.id,
            "ALS/1
            actor: coordinator
            intent: recovery
            action: release-stale-claim
            tags.add: []
            tags.remove: [Claimed-Dev-{N}]
            summary: Released stale claim after {claim_age_minutes} min.
            details:
            - threshold: {STALE_THRESHOLD_MINUTES} min
            - claim_created_at: {claim_tag.created_at}
            - reason: Worker likely crashed or was terminated")

        BREAK  # Only one claim per task

Report: "Stale claim recovery complete"
```

**Why this matters:**
- Without recovery, orphaned claims block tasks indefinitely
- Workers may crash, be killed, or hit timeouts
- This makes the system self-healing without manual intervention

---

## Step 2c: Detect and Clean Anomalies (Self-Healing)

Tasks can end up in inconsistent states due to partial failures, manual moves, or worker crashes.
This step detects and auto-cleans anomalies to prevent stuck states.

```
WORKFLOW_TAGS = ["Review-Approved", "Ops-Ready", "Plan-Approved", "Planned",
                 "Plan-Pending-Approval", "Ready", "Rework-Requested",
                 "Dev-Complete", "Design-Complete", "Test-Complete",
                 "Review-In-Progress", "Rework-Complete", "Claimed-Dev-1",
                 "Clarification-Answered", "Plan-Rejected", "Invoke-Architect",
                 "Architect-Assist-Complete", "Merge-Conflict", "Implementation-Failed",
                 "Branch-Setup-Failed"]
TERMINAL_COLUMNS = ["Deploy", "Done"]

For each task in tasks:

  # Anomaly 1: Completed tasks with stale workflow tags
  IF inColumn(task, "Deploy") OR inColumn(task, "Done"):
    stale_tags = []
    FOR tagName IN WORKFLOW_TAGS:
      IF hasTag(task, tagName):
        stale_tags.push(tagName)

    IF stale_tags.length > 0:
      Report: "ANOMALY: '{task.title}' in {column} has stale tags: {stale_tags}"

      # Auto-clean stale tags
      FOR tagName IN stale_tags:
        mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE[tagName])

      # Audit trail
      mcp__joan__create_task_comment(task.id,
        "ALS/1
        actor: coordinator
        intent: recovery
        action: anomaly-cleanup
        tags.add: []
        tags.remove: {stale_tags}
        summary: Cleaned stale workflow tags from completed task.
        details:
        - column: {task column name}
        - reason: Tasks in terminal columns should not have active workflow tags")

  # Anomaly 2: Conflicting approval/rejection tags
  IF hasTag(task, "Review-Approved") AND hasTag(task, "Rework-Requested"):
    Report: "ANOMALY: '{task.title}' has both Review-Approved AND Rework-Requested"

    # Remove the older state (approval came after rework request would be invalid)
    mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE["Review-Approved"])

    mcp__joan__create_task_comment(task.id,
      "ALS/1
      actor: coordinator
      intent: recovery
      action: anomaly-cleanup
      tags.add: []
      tags.remove: [Review-Approved]
      summary: Removed conflicting Review-Approved tag (Rework-Requested takes precedence).
      details:
      - reason: Cannot be both approved and requesting rework simultaneously")

  # Anomaly 3: Plan-Approved without Plan-Pending-Approval
  IF hasTag(task, "Plan-Approved") AND NOT hasTag(task, "Plan-Pending-Approval"):
    IF NOT inColumn(task, "Development") AND NOT inColumn(task, "Deploy") AND NOT inColumn(task, "Done"):
      Report: "ANOMALY: '{task.title}' has Plan-Approved but no Plan-Pending-Approval"

      # Auto-fix: Add the missing Plan-Pending-Approval tag so architect can finalize
      mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE["Plan-Pending-Approval"])

      mcp__joan__create_task_comment(task.id,
        "ALS/1
        actor: coordinator
        intent: recovery
        action: anomaly-cleanup
        tags.add: [Plan-Pending-Approval]
        tags.remove: []
        summary: Added missing Plan-Pending-Approval tag to enable plan finalization.
        details:
        - reason: Plan-Approved was present but Plan-Pending-Approval was missing (likely worker crash)
        - effect: Task will now be queued for architect finalization")

  # Anomaly 4: Tasks in Review column with no workflow tags
  # These were likely manually moved without proper dev worker completion
  IF inColumn(task, "Review"):
    has_any_workflow_tag = false
    FOR tagName IN WORKFLOW_TAGS:
      IF hasTag(task, tagName):
        has_any_workflow_tag = true
        BREAK

    IF NOT has_any_workflow_tag:
      Report: "ANOMALY: '{task.title}' in Review column has NO workflow tags (likely manually moved)"
      Report: "  This task cannot be processed - moving back to Development with Planned tag"

      # Move back to Development with Planned tag for dev worker to handle
      mcp__joan__update_task(task.id, column_id=COLUMN_CACHE["Development"])
      mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE["Planned"])

      mcp__joan__create_task_comment(task.id,
        "ALS/1
        actor: coordinator
        intent: recovery
        action: anomaly-recovery
        tags.add: [Planned]
        tags.remove: []
        summary: Moved task back to Development (was in Review with no workflow tags).
        details:
        - reason: Task in Review column must have completion tags or rework state
        - likely_cause: Manually moved without dev worker completion
        - action: Dev worker will pick up and properly complete this task
        - next_steps: Task will be implemented, checked off, and moved to Review with proper tags")

  # Anomaly 5: Tasks in Deploy with completion tags (should be in Review awaiting Ops-Ready)
  # These were likely manually moved before review/merge completed
  IF inColumn(task, "Deploy"):
    has_completion_tags = hasTag(task, "Dev-Complete") OR hasTag(task, "Design-Complete") OR hasTag(task, "Test-Complete")

    IF has_completion_tags:
      Report: "ANOMALY: '{task.title}' in Deploy has completion tags (should be in Review)"
      Report: "  Moving back to Review for proper review/approval flow"

      # Move back to Review - let review/ops flow handle properly
      mcp__joan__update_task(task.id, column_id=COLUMN_CACHE["Review"])

      mcp__joan__create_task_comment(task.id,
        "ALS/1
        actor: coordinator
        intent: recovery
        action: anomaly-recovery
        tags.add: []
        tags.remove: []
        summary: Moved task from Deploy back to Review (had completion tags indicating incomplete workflow).
        details:
        - reason: Deploy column is for tasks awaiting production deployment only
        - issue: Task still had Dev-Complete/Design-Complete/Test-Complete tags
        - likely_cause: Manually moved before review/merge completed
        - action: Task will now go through proper review → approval → Ops-Ready → merge flow")

Report: "Anomaly detection complete"
```

**Why this matters:**
- Partial worker failures leave inconsistent tag states
- Manual task moves in Joan UI bypass tag cleanup
- Without detection, tasks get stuck in limbo forever
- Auto-cleanup makes the system self-healing

---

## Step 2d: Detect Stuck Workflow States (Self-Healing)

Tasks can get stuck in mid-workflow states due to context bloat, lost worker results, or coordinator crashes.
This step detects tasks that have been in the same workflow state for too long and flags them for re-processing.

```
STUCK_THRESHOLD_MINUTES = STUCK_STATE_MINUTES  # From config, default 120

# Define expected state transitions and their max durations (minutes)
# Format: [column, required_tags, forbidden_tags, max_minutes, description]
WORKFLOW_STATE_TIMEOUTS = [
  # Architect should finalize approved plans quickly
  ["Analyse", ["Plan-Pending-Approval", "Plan-Approved"], ["Plan-Rejected"], 30, "Plan finalization"],

  # Architect should create plans within 1 hour of Ready
  ["Analyse", ["Ready"], ["Plan-Pending-Approval"], 60, "Plan creation"],

  # Clarification answers should be processed quickly
  ["Analyse", ["Needs-Clarification", "Clarification-Answered"], [], 30, "Clarification processing"],

  # Planned tasks should be claimed within 2 hours
  ["Development", ["Planned"], ["Claimed-Dev-"], 120, "Dev claim"],

  # Rework should be picked up within 2 hours
  ["Development", ["Rework-Requested", "Planned"], ["Claimed-Dev-"], 120, "Rework claim"],

  # Review should start within 2 hours of completion
  ["Review", ["Dev-Complete", "Design-Complete", "Test-Complete"], ["Review-In-Progress", "Review-Approved", "Rework-Requested"], 120, "Review start"],
]

CLEAR FORCE_REQUEUE  # Reset at start of detection

For each task in tasks:
  state_age_minutes = (NOW - task.updated_at) in minutes

  FOR EACH [expected_column, required_tags, forbidden_tags, max_minutes, description] IN WORKFLOW_STATE_TIMEOUTS:

    # Check if task is in this workflow state
    IF NOT inColumn(task, expected_column):
      CONTINUE

    # Check required tags are present
    all_required = true
    FOR tag IN required_tags:
      # Handle wildcard prefix matching (e.g., "Claimed-Dev-")
      IF tag ends with "-":
        # Check if ANY tag with this prefix exists
        prefix_found = false
        FOR actual_tag IN task.tags:
          IF actual_tag.name starts with tag:
            prefix_found = true
            BREAK
        # For forbidden tags with prefix, we want NONE to match
        IF tag IN forbidden_tags AND prefix_found:
          all_required = false
          BREAK
      ELSE:
        IF NOT hasTag(task, tag):
          all_required = false
          BREAK

    IF NOT all_required:
      CONTINUE

    # Check no forbidden tags are present
    has_forbidden = false
    FOR tag IN forbidden_tags:
      IF tag ends with "-":
        # Prefix matching for forbidden tags
        FOR actual_tag IN task.tags:
          IF actual_tag.name starts with tag:
            has_forbidden = true
            BREAK
      ELSE:
        IF hasTag(task, tag):
          has_forbidden = true
          BREAK
    IF has_forbidden:
      CONTINUE

    # Task matches this workflow state - check age
    IF state_age_minutes > max_minutes:
      Report: "STUCK STATE: '{task.title}' in {description} state for {state_age_minutes} min (max: {max_minutes})"

      # Add diagnostic comment
      mcp__joan__create_task_comment(task.id,
        "ALS/1
        actor: coordinator
        intent: diagnostic
        action: stuck-state-detected
        tags.add: []
        tags.remove: []
        summary: Task stuck in workflow state for {state_age_minutes} minutes.
        details:
        - state: {description}
        - expected_tags: {required_tags}
        - column: {expected_column}
        - threshold: {max_minutes} minutes
        - action: Force re-queuing for next dispatch cycle")

      # Mark for priority re-processing
      FORCE_REQUEUE.push({task: task, state: description, required_tags: required_tags})

      BREAK  # Only report each task once

IF FORCE_REQUEUE.length > 0:
  Report: "Detected {FORCE_REQUEUE.length} stuck tasks for re-processing"
ELSE:
  Report: "No stuck states detected"
```

**Why this matters:**
- Context bloat can cause coordinators to skip queue-building logic
- Lost worker results leave tasks in mid-transition states
- Without detection, tasks can remain stuck for hours/days
- Force re-queuing gives stuck tasks priority processing

---

## Step 2e: State Machine Validation (Self-Healing)

Validates that task tag combinations match valid workflow states.
Invalid combinations are auto-remediated to restore consistent state.

```
# Define invalid tag combinations that should never coexist
INVALID_TAG_COMBINATIONS = [
  # Ready should be removed when plan is created
  {
    tags: ["Ready", "Plan-Pending-Approval"],
    remediation: "remove",
    remove_tag: "Ready",
    reason: "Ready tag should be removed when plan is created"
  },

  # Ready should definitely not exist alongside Plan-Approved
  {
    tags: ["Ready", "Plan-Approved"],
    remediation: "remove",
    remove_tag: "Ready",
    reason: "Ready tag is stale - plan has been approved"
  },

  # Cannot be both approved and requesting rework
  {
    tags: ["Review-Approved", "Rework-Requested"],
    remediation: "remove",
    remove_tag: "Review-Approved",
    reason: "Rework-Requested takes precedence over Review-Approved"
  },

  # Plan-Rejected should not coexist with Plan-Approved
  {
    tags: ["Plan-Approved", "Plan-Rejected"],
    remediation: "remove",
    remove_tag: "Plan-Rejected",
    reason: "Plan-Approved takes precedence (latest action)"
  },

  # Claimed tasks should not have Implementation-Failed
  {
    tags_pattern: ["Claimed-Dev-*", "Implementation-Failed"],
    remediation: "remove_pattern",
    remove_pattern: "Claimed-Dev-*",
    reason: "Failed implementations should release claims"
  },

  # Completed tasks should not still be claimed
  {
    tags_pattern: ["Claimed-Dev-*", "Dev-Complete"],
    remediation: "remove_pattern",
    remove_pattern: "Claimed-Dev-*",
    reason: "Completed tasks should release claims"
  },
]

REMEDIATED_COUNT = 0

For each task in tasks:

  FOR EACH invalid IN INVALID_TAG_COMBINATIONS:

    # Check if this invalid combination exists
    IF invalid.tags:
      # Exact tag matching
      all_present = true
      FOR tag IN invalid.tags:
        IF NOT hasTag(task, tag):
          all_present = false
          BREAK
      IF NOT all_present:
        CONTINUE

    ELIF invalid.tags_pattern:
      # Pattern matching (e.g., "Claimed-Dev-*")
      all_present = true
      FOR pattern IN invalid.tags_pattern:
        IF pattern ends with "*":
          prefix = pattern without "*"
          found = false
          FOR actual_tag IN task.tags:
            IF actual_tag.name starts with prefix:
              found = true
              BREAK
          IF NOT found:
            all_present = false
            BREAK
        ELSE:
          IF NOT hasTag(task, pattern):
            all_present = false
            BREAK
      IF NOT all_present:
        CONTINUE

    # Invalid combination found - apply remediation
    Report: "INVALID STATE: '{task.title}' has invalid tag combination"
    Report: "  Tags: {task.tags as names}"
    Report: "  Reason: {invalid.reason}"

    IF invalid.remediation == "remove":
      IF TAG_CACHE[invalid.remove_tag]:
        mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE[invalid.remove_tag])
        Report: "  Remediation: Removed '{invalid.remove_tag}'"

    ELIF invalid.remediation == "remove_pattern":
      prefix = invalid.remove_pattern without "*"
      FOR actual_tag IN task.tags:
        IF actual_tag.name starts with prefix:
          mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, actual_tag.id)
          Report: "  Remediation: Removed '{actual_tag.name}'"

    # Audit trail
    mcp__joan__create_task_comment(task.id,
      "ALS/1
      actor: coordinator
      intent: recovery
      action: invalid-state-remediation
      tags.add: []
      tags.remove: [{removed tag(s)}]
      summary: Auto-fixed invalid tag combination.
      details:
      - reason: {invalid.reason}
      - remediation: {invalid.remediation}")

    REMEDIATED_COUNT++

IF REMEDIATED_COUNT > 0:
  Report: "State machine validation: remediated {REMEDIATED_COUNT} invalid states"
ELSE:
  Report: "State machine validation: all tasks in valid states"
```

**Why this matters:**
- Invalid tag combinations can cause tasks to match multiple queues or none
- Partial worker failures leave inconsistent states
- Auto-remediation restores tasks to processable states
- This catches the exact issue that caused tasks #81/#82 to be stuck

---

## Step 3: Build Priority Queues

Build queues in priority order. Each task goes into AT MOST one queue.

```
BA_QUEUE = []
ARCHITECT_QUEUE = []
DEV_QUEUE = []
REVIEWER_QUEUE = []
OPS_QUEUE = []

For each task in tasks:

  # Priority 0: Invocation responses (HIGHEST PRIORITY - fast resolution)
  # These are handled first to minimize latency in cross-agent consultation

  # 0a: Architect invoked for conflict advisory (needs to provide guidance)
  IF inColumn(task, "Review")
     AND hasTag(task, "Invoke-Architect")
     AND NOT hasTag(task, "Architect-Assist-Complete"):
    ARCHITECT_QUEUE.unshift({task, mode: "advisory-conflict"})  # Insert at front
    CONTINUE

  # 0b: Architect advisory complete, Ops can resume with guidance
  IF inColumn(task, "Review")
     AND hasTag(task, "Architect-Assist-Complete"):
    OPS_QUEUE.unshift({task, mode: "merge-with-guidance"})  # Insert at front
    CONTINUE

  # Priority 1: Dev tasks needing conflict resolution
  IF inColumn(task, "Development")
     AND hasTag(task, "Merge-Conflict")
     AND NOT isClaimedByAnyDev(task):
    DEV_QUEUE.push({task, mode: "conflict"})
    CONTINUE

  # Priority 2: Dev tasks needing rework
  IF inColumn(task, "Development")
     AND hasTag(task, "Rework-Requested")
     AND NOT isClaimedByAnyDev(task)
     AND NOT hasTag(task, "Merge-Conflict"):
    DEV_QUEUE.push({task, mode: "rework"})
    CONTINUE

  # Priority 3: Dev tasks ready for implementation
  IF inColumn(task, "Development")
     AND hasTag(task, "Planned")
     AND NOT isClaimedByAnyDev(task)
     AND NOT hasTag(task, "Rework-Requested")
     AND NOT hasTag(task, "Implementation-Failed")
     AND NOT hasTag(task, "Branch-Setup-Failed"):
    DEV_QUEUE.push({task, mode: "implement"})
    CONTINUE

  # Priority 4: Architect tasks with Plan-Approved (finalize)
  IF inColumn(task, "Analyse")
     AND hasTag(task, "Plan-Pending-Approval")
     AND hasTag(task, "Plan-Approved")
     AND NOT hasTag(task, "Plan-Rejected"):
    ARCHITECT_QUEUE.push({task, mode: "finalize"})
    CONTINUE

  # Priority 4.5: Architect tasks with Plan-Rejected (revise)
  IF inColumn(task, "Analyse")
     AND hasTag(task, "Plan-Pending-Approval")
     AND hasTag(task, "Plan-Rejected"):
    ARCHITECT_QUEUE.push({task, mode: "revise"})
    CONTINUE

  # Priority 5: Architect tasks with Ready (create plan)
  IF inColumn(task, "Analyse")
     AND hasTag(task, "Ready")
     AND NOT hasTag(task, "Plan-Pending-Approval"):
    ARCHITECT_QUEUE.push({task, mode: "plan"})
    CONTINUE

  # Priority 6: BA tasks with Clarification-Answered (reevaluate)
  IF inColumn(task, "Analyse")
     AND hasTag(task, "Needs-Clarification")
     AND hasTag(task, "Clarification-Answered"):
    BA_QUEUE.push({task, mode: "reevaluate"})
    CONTINUE

  # Priority 7: BA tasks in To Do (evaluate)
  IF inColumn(task, "To Do")
     AND NOT hasTag(task, "Ready"):
    BA_QUEUE.push({task, mode: "evaluate"})
    CONTINUE

  # Priority 8: Reviewer tasks ready for review
  IF inColumn(task, "Review")
     AND hasTag(task, "Dev-Complete")
     AND hasTag(task, "Design-Complete")
     AND hasTag(task, "Test-Complete")
     AND NOT hasTag(task, "Review-In-Progress")
     AND NOT hasTag(task, "Review-Approved")
     AND NOT hasTag(task, "Rework-Requested"):
    REVIEWER_QUEUE.push({task})
    CONTINUE

  # Priority 8b: Rework-Complete triggers re-review
  IF inColumn(task, "Review")
     AND hasTag(task, "Rework-Complete")
     AND NOT hasTag(task, "Review-In-Progress")
     AND NOT hasTag(task, "Review-Approved")
     AND NOT hasTag(task, "Rework-Requested"):
    REVIEWER_QUEUE.push({task})
    CONTINUE

  # Priority 9: Ops tasks with Review-Approved AND Ops-Ready
  # NOTE: Check both Review AND Deploy to handle column drift (task moved before Ops processed)
  IF (inColumn(task, "Review") OR inColumn(task, "Deploy"))
     AND hasTag(task, "Review-Approved")
     AND hasTag(task, "Ops-Ready"):
    OPS_QUEUE.push({task, mode: "merge"})
    CONTINUE

  # Priority 10: Ops tasks with Rework-Requested in Review
  IF inColumn(task, "Review")
     AND hasTag(task, "Rework-Requested")
     AND NOT hasTag(task, "Review-Approved"):
    OPS_QUEUE.push({task, mode: "rework"})
    CONTINUE

  # DIAGNOSTIC: Identify tasks with workflow tags that didn't match any queue
  # This catches edge cases and helps diagnose stuck tasks
  workflow_tags_present = []
  FOR tagName IN WORKFLOW_TAGS:
    IF hasTag(task, tagName):
      workflow_tags_present.push(tagName)

  IF workflow_tags_present.length > 0:
    Report: "UNQUEUED: '{task.title}' has tags {workflow_tags_present} in column '{task.column}' but didn't match any queue condition"

  # DIAGNOSTIC: Tasks in workflow columns with no tags or incomplete tags
  # This catches tasks that were manually moved without proper state transitions
  IF inColumn(task, "Review"):
    # Review column tasks should have completion tags OR rework tags
    has_completion_tags = hasTag(task, "Dev-Complete") AND hasTag(task, "Design-Complete") AND hasTag(task, "Test-Complete")
    has_rework_tags = hasTag(task, "Rework-Requested") OR hasTag(task, "Rework-Complete")
    has_approval_tags = hasTag(task, "Review-Approved") OR hasTag(task, "Review-In-Progress")

    IF NOT (has_completion_tags OR has_rework_tags OR has_approval_tags):
      Report: "ANOMALY: '{task.title}' in Review column is missing expected tags (completion, rework, or review state)"
      Report: "  Current tags: {workflow_tags_present or 'NONE'}"
      Report: "  Expected: Dev-Complete+Design-Complete+Test-Complete OR Rework-Requested/Rework-Complete OR Review-Approved"
      Report: "  Action: Task needs manual intervention - add appropriate tags or move to correct column"

  IF inColumn(task, "Deploy"):
    # Deploy column tasks should have NO workflow tags (they're awaiting production deployment)
    IF workflow_tags_present.length > 0:
      Report: "ANOMALY: '{task.title}' in Deploy has stale workflow tags: {workflow_tags_present}"
      Report: "  Action: These will be auto-cleaned by anomaly detection"
    ELSE:
      # Deploy tasks with no tags is normal (awaiting production deployment)
      # But if they have completion tags, they shouldn't be here yet
      pass

Report queue sizes:
"Queues: BA={BA_QUEUE.length}, Architect={ARCHITECT_QUEUE.length}, Dev={DEV_QUEUE.length}, Reviewer={REVIEWER_QUEUE.length}, Ops={OPS_QUEUE.length}"
```

---

## Step 3-Doctor: Doctor Diagnostic Pass (Self-Healing)

When all queues are empty but tasks exist in pipeline columns, run Doctor diagnostics to detect
and fix stuck tasks that didn't match any queue condition. This catches the scenario where tasks
have invalid tag combinations or got stuck due to worker failures.

```
# Check if Doctor pass is needed
ALL_QUEUES_EMPTY = (BA_QUEUE.length == 0 AND ARCHITECT_QUEUE.length == 0 AND
                   DEV_QUEUE.length == 0 AND REVIEWER_QUEUE.length == 0 AND
                   OPS_QUEUE.length == 0)

# Count tasks in pipeline columns (not To Do or Done)
PIPELINE_TASKS = []
For each task in tasks:
  IF inColumn(task, "Analyse") OR inColumn(task, "Development") OR
     inColumn(task, "Review") OR inColumn(task, "Deploy"):
    PIPELINE_TASKS.push(task)

# Doctor triggers when: queues empty BUT pipeline has tasks
DOCTOR_TRIGGERED = ALL_QUEUES_EMPTY AND PIPELINE_TASKS.length > 0

IF DOCTOR_TRIGGERED:
  Report: ""
  Report: "╔══════════════════════════════════════════════════════════════════╗"
  Report: "║  DOCTOR DIAGNOSTIC PASS                                          ║"
  Report: "║  All queues empty but {PIPELINE_TASKS.length} tasks in pipeline - running diagnostics  ║"
  Report: "╚══════════════════════════════════════════════════════════════════╝"
  Report: ""

  DOCTOR_ISSUES = []
  DOCTOR_FIXES = []

  For each task in PIPELINE_TASKS:

    # === Diagnosis 1: Stuck Plan Finalization ===
    IF inColumn(task, "Analyse") AND hasTag(task, "Plan-Pending-Approval") AND hasTag(task, "Plan-Approved"):
      state_age_hours = (NOW - task.updated_at) in hours
      IF state_age_hours > 0.5:  # 30 minutes
        DOCTOR_ISSUES.push({
          task: task,
          type: "STUCK_PLAN_FINALIZATION",
          severity: "HIGH",
          description: "Plan approved but not finalized for {state_age_hours} hours"
        })

        # FIX: Finalize the plan (remove approval tags, add Planned, move to Development)
        mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE["Plan-Pending-Approval"])
        mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE["Plan-Approved"])
        mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE["Planned"])
        mcp__joan__update_task(task.id, column_id=COLUMN_CACHE["Development"])

        mcp__joan__create_task_comment(task.id,
          "ALS/1
          actor: doctor
          intent: recovery
          action: finalize-stuck-plan
          tags.add: [Planned]
          tags.remove: [Plan-Pending-Approval, Plan-Approved]
          column.move: Analyse → Development
          summary: Doctor auto-finalized stuck plan after {state_age_hours} hours.
          details:
          - issue_type: STUCK_PLAN_FINALIZATION
          - trigger: Queue empty but pipeline has tasks
          - root_cause: Worker/coordinator likely failed during finalization")

        DOCTOR_FIXES.push({task: task, fix: "finalize-stuck-plan", workflow_step: "Analyse→Development"})
        Report: "  [HIGH] STUCK_PLAN_FINALIZATION: '{task.title}'"
        Report: "    Fixed: Finalized plan and moved to Development"

    # === Diagnosis 2: Orphaned in Analyse with Ready ===
    IF inColumn(task, "Analyse") AND hasTag(task, "Ready") AND NOT hasTag(task, "Plan-Pending-Approval"):
      state_age_hours = (NOW - task.updated_at) in hours
      IF state_age_hours > 1:  # 1 hour without being planned
        DOCTOR_ISSUES.push({
          task: task,
          type: "READY_NOT_PLANNED",
          severity: "MEDIUM",
          description: "Task Ready for {state_age_hours} hours but not queued for Architect"
        })
        # This indicates the pipeline gate is blocking or Architect is disabled
        # Don't auto-fix - just report (pipeline gate may be intentional)
        Report: "  [MEDIUM] READY_NOT_PLANNED: '{task.title}'"
        Report: "    Note: Pipeline gate may be blocking. Check for tasks in Development/Review."

    # === Diagnosis 3: Orphaned in Development ===
    IF inColumn(task, "Development"):
      has_workflow_tag = hasTag(task, "Planned") OR hasTag(task, "Rework-Requested") OR
                         hasTag(task, "Merge-Conflict") OR isClaimedByAnyDev(task) OR
                         hasTag(task, "Implementation-Failed") OR hasTag(task, "Branch-Setup-Failed")
      IF NOT has_workflow_tag:
        DOCTOR_ISSUES.push({
          task: task,
          type: "ORPHANED_IN_DEVELOPMENT",
          severity: "HIGH",
          description: "Task in Development without any workflow tags"
        })

        # FIX: Check if task has a plan in description
        IF task.description contains "## Implementation Plan" OR task.description contains "### Sub-Tasks":
          mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE["Planned"])
          mcp__joan__create_task_comment(task.id,
            "ALS/1
            actor: doctor
            intent: recovery
            action: restore-planned-tag
            tags.add: [Planned]
            summary: Doctor restored Planned tag (plan found in description).
            details:
            - issue_type: ORPHANED_IN_DEVELOPMENT
            - trigger: Task had no workflow tags")
          DOCTOR_FIXES.push({task: task, fix: "restore-planned-tag", workflow_step: "Development"})
          Report: "  [HIGH] ORPHANED_IN_DEVELOPMENT: '{task.title}'"
          Report: "    Fixed: Added Planned tag (plan exists in description)"
        ELSE:
          # No plan - move back to Analyse with Ready tag
          mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE["Ready"])
          mcp__joan__update_task(task.id, column_id=COLUMN_CACHE["Analyse"])
          mcp__joan__create_task_comment(task.id,
            "ALS/1
            actor: doctor
            intent: recovery
            action: move-to-analyse
            tags.add: [Ready]
            column.move: Development → Analyse
            summary: Doctor moved task to Analyse (no plan found).
            details:
            - issue_type: ORPHANED_IN_DEVELOPMENT
            - trigger: Task had no workflow tags and no plan in description")
          DOCTOR_FIXES.push({task: task, fix: "move-to-analyse", workflow_step: "Development→Analyse"})
          Report: "  [HIGH] ORPHANED_IN_DEVELOPMENT: '{task.title}'"
          Report: "    Fixed: Moved to Analyse with Ready tag (no plan found)"

    # === Diagnosis 4: Orphaned in Review ===
    IF inColumn(task, "Review"):
      has_review_state = hasTag(task, "Dev-Complete") OR hasTag(task, "Review-Approved") OR
                         hasTag(task, "Rework-Requested") OR hasTag(task, "Review-In-Progress") OR
                         hasTag(task, "Rework-Complete")
      IF NOT has_review_state:
        DOCTOR_ISSUES.push({
          task: task,
          type: "ORPHANED_IN_REVIEW",
          severity: "HIGH",
          description: "Task in Review without completion or review tags"
        })
        # Already handled in Step 2c anomaly detection, but log if still present
        Report: "  [HIGH] ORPHANED_IN_REVIEW: '{task.title}'"
        Report: "    Note: Should have been fixed by anomaly detection"

    # === Diagnosis 5: Stuck Ops Merge ===
    IF inColumn(task, "Review") AND hasTag(task, "Review-Approved") AND hasTag(task, "Ops-Ready"):
      state_age_hours = (NOW - task.updated_at) in hours
      IF state_age_hours > 0.5:  # 30 minutes
        DOCTOR_ISSUES.push({
          task: task,
          type: "STUCK_OPS_MERGE",
          severity: "HIGH",
          description: "Task ready for Ops merge for {state_age_hours} hours"
        })
        # Don't auto-fix - Ops should pick this up, just report
        Report: "  [HIGH] STUCK_OPS_MERGE: '{task.title}'"
        Report: "    Note: Task is ready for Ops, should be processed next cycle"

  # === Write Doctor Metrics ===
  IF DOCTOR_ISSUES.length > 0 OR DOCTOR_FIXES.length > 0:
    METRICS_FILE = "{PROJECT_DIR}/.claude/logs/agent-metrics.jsonl"

    # Write metrics entry (JSON Lines format)
    metric_entry = {
      "timestamp": NOW in ISO format,
      "event": "doctor_invocation",
      "project": PROJECT_NAME,
      "trigger": "queues_empty_with_pipeline_tasks",
      "pipeline_tasks_count": PIPELINE_TASKS.length,
      "issues_found": DOCTOR_ISSUES.length,
      "fixes_applied": DOCTOR_FIXES.length,
      "issues": DOCTOR_ISSUES.map(i => ({type: i.type, severity: i.severity, task: i.task.title})),
      "fixes": DOCTOR_FIXES.map(f => ({task: f.task.title, fix: f.fix, workflow_step: f.workflow_step}))
    }

    Run bash command:
      echo '{JSON.stringify(metric_entry)}' >> {METRICS_FILE}

    Report: ""
    Report: "Doctor summary: {DOCTOR_ISSUES.length} issues found, {DOCTOR_FIXES.length} fixes applied"
    Report: "Metrics logged to: {METRICS_FILE}"

    # === Re-build queues after fixes ===
    IF DOCTOR_FIXES.length > 0:
      Report: ""
      Report: "Re-fetching tasks and rebuilding queues after Doctor fixes..."

      # Re-fetch all tasks (they've changed)
      tasks = mcp__joan__list_tasks(project_id=PROJECT_ID)

      # Clear and rebuild all queues
      BA_QUEUE = []
      ARCHITECT_QUEUE = []
      DEV_QUEUE = []
      REVIEWER_QUEUE = []
      OPS_QUEUE = []

      # ... (repeat queue building logic from Step 3)
      # For brevity, this is a conceptual re-run - actual implementation
      # would call a helper function or inline the logic

      Report: "Queues rebuilt: BA={BA_QUEUE.length}, Architect={ARCHITECT_QUEUE.length}, Dev={DEV_QUEUE.length}, Reviewer={REVIEWER_QUEUE.length}, Ops={OPS_QUEUE.length}"

  ELSE:
    Report: "Doctor pass complete: No issues requiring fixes"
```

---

## Step 3a: YOLO Mode Auto-Approval (Pre-Dispatch)

In YOLO mode, auto-approve any pending approvals BEFORE dispatch begins.
This handles both fresh approvals (just added this cycle) and stale approvals (from previous cycles).

```
IF MODE == "yolo":
  Report: "YOLO mode: scanning for pending approvals..."

  auto_approved_count = 0

  # Auto-approve plans
  For each task in tasks:
    IF hasTag(task, "Plan-Pending-Approval") AND inColumn(task, "Analyse"):
      # Check if Plan-Approved already exists
      IF NOT hasTag(task, "Plan-Approved"):
        Report: "  Auto-approving plan for task '{task.title}'"

        # Add Plan-Approved tag
        IF TAG_CACHE["Plan-Approved"]:
          mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE["Plan-Approved"])

          # Add audit comment
          mcp__joan__create_task_comment(task.id,
            "ALS/1
            actor: coordinator
            intent: decision
            action: auto-approve-plan
            tags.add: [Plan-Approved]
            tags.remove: []
            summary: Plan auto-approved (YOLO mode active).
            details:
            - mode: yolo
            - reason: Auto-approval bypasses human review gate
            - next: Architect will finalize on next poll
            - trigger: pre-dispatch scan detected Plan-Pending-Approval tag")

          auto_approved_count++
          Report: "    ✓ Added Plan-Approved tag + audit comment"

  # Auto-approve merges
  For each task in tasks:
    IF hasTag(task, "Review-Approved") AND inColumn(task, "Review"):
      # Check if Ops-Ready already exists
      IF NOT hasTag(task, "Ops-Ready"):
        Report: "  Auto-approving merge for task '{task.title}'"

        # Add Ops-Ready tag
        IF TAG_CACHE["Ops-Ready"]:
          mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE["Ops-Ready"])

          # Add audit comment
          mcp__joan__create_task_comment(task.id,
            "ALS/1
            actor: coordinator
            intent: decision
            action: auto-approve-merge
            tags.add: [Ops-Ready]
            tags.remove: []
            summary: Merge auto-approved (YOLO mode active).
            details:
            - mode: yolo
            - reason: Auto-approval bypasses human merge gate
            - next: Ops will merge on next poll
            - trigger: pre-dispatch scan detected Review-Approved tag")

          auto_approved_count++
          Report: "    ✓ Added Ops-Ready tag + audit comment"

  IF auto_approved_count > 0:
    Report: "YOLO mode: {auto_approved_count} approval(s) auto-added"
  ELSE:
    Report: "YOLO mode: no pending approvals found"
```

**Why this location?**
- Runs after queue building (we know which tasks need attention)
- Runs before pipeline gate (updated tags affect gate logic)
- Runs before dispatch (workers see updated state)
- Handles both fresh AND stale approvals from previous cycles

---

## Step 3b: Serial Pipeline Gate Check

Before dispatching Architect workers, check if the dev pipeline is clear.
**Strict serial mode ensures only ONE task flows through Architect→Dev→Review→Ops at a time.**

This prevents:
- Stale plans (Architect plans reference code that gets modified by other tasks)
- Merge conflicts (multiple PRs trying to merge to develop)
- Rework cycles (plans become invalid before dev even starts)

```
PIPELINE_BLOCKED = false
BLOCKING_TASK = null
BLOCKING_REASON = ""

# Check if any task is currently in the dev pipeline
For each task in tasks:

  # === Check Development column ===
  IF inColumn(task, "Development"):

    # Task is planned and waiting for dev pickup
    IF hasTag(task, "Planned") AND NOT isClaimedByAnyDev(task):
      PIPELINE_BLOCKED = true
      BLOCKING_TASK = task
      BLOCKING_REASON = "Planned task waiting for dev claim"
      Report: "Pipeline BLOCKED: '{task.title}' is Planned in Development"
      BREAK

    # Task is actively being implemented
    IF isClaimedByAnyDev(task):
      PIPELINE_BLOCKED = true
      BLOCKING_TASK = task
      BLOCKING_REASON = "Task being implemented by dev worker"
      Report: "Pipeline BLOCKED: '{task.title}' is claimed by a dev worker"
      BREAK

    # Task needs rework (failed review)
    IF hasTag(task, "Rework-Requested"):
      PIPELINE_BLOCKED = true
      BLOCKING_TASK = task
      BLOCKING_REASON = "Task needs rework after review"
      Report: "Pipeline BLOCKED: '{task.title}' has Rework-Requested"
      BREAK

    # Task has merge conflict
    IF hasTag(task, "Merge-Conflict"):
      PIPELINE_BLOCKED = true
      BLOCKING_TASK = task
      BLOCKING_REASON = "Task has merge conflict to resolve"
      Report: "Pipeline BLOCKED: '{task.title}' has Merge-Conflict"
      BREAK

  # === Check Review column ===
  IF inColumn(task, "Review"):

    # Task awaiting reviewer (has completion tags, not yet reviewed)
    IF hasTag(task, "Dev-Complete") AND NOT hasTag(task, "Review-Approved") AND NOT hasTag(task, "Rework-Requested"):
      PIPELINE_BLOCKED = true
      BLOCKING_TASK = task
      BLOCKING_REASON = "Task awaiting code review"
      Report: "Pipeline BLOCKED: '{task.title}' is in Review awaiting reviewer"
      BREAK

    # Task approved but awaiting human merge approval (Ops-Ready tag)
    IF hasTag(task, "Review-Approved") AND NOT hasTag(task, "Ops-Ready"):
      PIPELINE_BLOCKED = true
      BLOCKING_TASK = task
      BLOCKING_REASON = "Approved task awaiting human Ops-Ready tag"
      Report: "Pipeline BLOCKED: '{task.title}' is Review-Approved, awaiting Ops-Ready"
      BREAK

    # Task ready for Ops to merge
    IF hasTag(task, "Review-Approved") AND hasTag(task, "Ops-Ready"):
      PIPELINE_BLOCKED = true
      BLOCKING_TASK = task
      BLOCKING_REASON = "Task ready for Ops merge to develop"
      Report: "Pipeline BLOCKED: '{task.title}' is ready for Ops merge"
      BREAK

# === Apply gate decision ===
IF PIPELINE_BLOCKED:
  Report: ""
  Report: "╔══════════════════════════════════════════════════════════════════╗"
  Report: "║  SERIAL PIPELINE GATE: BLOCKED                                   ║"
  Report: "╠══════════════════════════════════════════════════════════════════╣"
  Report: "║  Blocking task: '{BLOCKING_TASK.title}'                          ║"
  Report: "║  Reason: {BLOCKING_REASON}                                       ║"
  Report: "╠══════════════════════════════════════════════════════════════════╣"
  Report: "║  Architect will NOT plan new tasks until current task merges.    ║"
  Report: "║  BA evaluation continues (no code dependencies).                 ║"
  Report: "╚══════════════════════════════════════════════════════════════════╝"
  Report: ""

  # Clear architect queue - do NOT plan anything new
  ARCHITECT_QUEUE = []

ELSE:
  Report: ""
  Report: "╔══════════════════════════════════════════════════════════════════╗"
  Report: "║  SERIAL PIPELINE GATE: CLEAR                                     ║"
  Report: "║  No tasks in dev pipeline. Architect can plan next Ready task.   ║"
  Report: "╚══════════════════════════════════════════════════════════════════╝"
  Report: ""
```

---

## Step 4: Dispatch Workers (MCP Proxy Pattern - Staged Pipeline)

**ARCHITECTURE:** Workers do NOT have MCP access. The coordinator:
1. Builds a complete "work package" with all task data
2. Dispatches worker with work package via prompt
3. Receives structured JSON result from worker
4. Executes MCP actions on behalf of worker
5. Verifies post-conditions

This pattern ensures workers are isolated, parallelizable, and fault-tolerant.

```
DISPATCHED = 0
RESULTS = []  # Collect worker results for batch processing

# Helper: Get column name from COLUMN_CACHE
def get_column_name_from_cache(column_id, COLUMN_CACHE):
  FOR column_name, cached_id IN COLUMN_CACHE:
    IF cached_id == column_id:
      RETURN column_name
  RETURN "Unknown"  # Fallback if not found

# Helper: Extract tag names from tag objects
def extract_tag_names(tags):
  tag_names = []
  FOR tag IN tags:
    tag_names.push(tag.name)
  RETURN tag_names

# Helper: Extract stage context from comments
def extract_stage_context_from_comments(comments, expected_from, expected_to):
  """
  Scan comments in reverse chronological order to find the most recent
  context handoff from expected_from stage to expected_to stage.
  Returns the parsed context object or null if not found.
  """
  FOR comment IN reversed(comments):
    content = comment.content

    # Check if this is a context handoff ALS block
    IF "intent: handoff" IN content AND "action: context-handoff" IN content:
      # Extract from_stage and to_stage using simple string matching
      from_stage = null
      to_stage = null

      FOR line IN content.split("\n"):
        IF line starts with "from_stage:":
          from_stage = line after "from_stage:" (trimmed)
        IF line starts with "to_stage:":
          to_stage = line after "to_stage:" (trimmed)

      # Check if this is the handoff we're looking for
      IF from_stage == expected_from AND to_stage == expected_to:
        # Parse the full handoff content
        RETURN parse_handoff_from_comment(content)

  # No matching handoff found (backward compatible)
  RETURN null

# Helper: Parse handoff content
def parse_handoff_from_comment(content):
  """
  Parse an ALS handoff comment into a structured context object.
  Extracts key_decisions, files_of_interest, warnings, dependencies, metadata.
  """
  context = {
    "from_stage": null,
    "to_stage": null,
    "summary": null,
    "key_decisions": [],
    "files_of_interest": [],
    "warnings": [],
    "dependencies": [],
    "metadata": {}
  }

  lines = content.split("\n")
  current_section = null

  FOR line IN lines:
    trimmed = line.trim()

    # Extract scalar fields
    IF trimmed starts with "from_stage:":
      context.from_stage = trimmed after "from_stage:" (trimmed)
    ELIF trimmed starts with "to_stage:":
      context.to_stage = trimmed after "to_stage:" (trimmed)
    ELIF trimmed starts with "summary:":
      context.summary = trimmed after "summary:" (trimmed)

    # Detect section headers (ending with :)
    ELIF trimmed == "key_decisions:":
      current_section = "key_decisions"
    ELIF trimmed == "files_of_interest:":
      current_section = "files_of_interest"
    ELIF trimmed == "warnings:":
      current_section = "warnings"
    ELIF trimmed == "dependencies:":
      current_section = "dependencies"
    ELIF trimmed == "metadata:":
      current_section = "metadata"

    # Parse list items (lines starting with -)
    ELIF trimmed starts with "- " AND current_section IN ["key_decisions", "files_of_interest", "warnings", "dependencies"]:
      item = trimmed after "- " (trimmed)
      context[current_section].push(item)

    # Parse metadata key-value pairs (indented lines with :)
    ELIF current_section == "metadata" AND ":" IN trimmed:
      key = trimmed before ":"
      value = trimmed after ":" (trimmed)
      context.metadata[key] = value

  RETURN context

# Helper: Format Handoff Comment
def format_handoff_comment(context):
  """
  Format a StageContext object as an ALS handoff comment.
  See als-spec.md for the full format.
  """
  lines = [
    "ALS/1",
    f"actor: {context.from_stage}",
    "intent: handoff",
    "action: context-handoff",
    f"from_stage: {context.from_stage}",
    f"to_stage: {context.to_stage}",
    f"summary: {context.summary or 'Context handoff for next stage'}",
  ]

  # Add key_decisions (required)
  IF context.key_decisions AND len(context.key_decisions) > 0:
    lines.append("key_decisions:")
    FOR decision IN context.key_decisions:
      lines.append(f"- {decision}")

  # Add files_of_interest (optional)
  IF context.files_of_interest AND len(context.files_of_interest) > 0:
    lines.append("files_of_interest:")
    FOR file_path IN context.files_of_interest:
      lines.append(f"- {file_path}")

  # Add warnings (optional)
  IF context.warnings AND len(context.warnings) > 0:
    lines.append("warnings:")
    FOR warning IN context.warnings:
      lines.append(f"- {warning}")

  # Add dependencies (optional)
  IF context.dependencies AND len(context.dependencies) > 0:
    lines.append("dependencies:")
    FOR dep IN context.dependencies:
      lines.append(f"- {dep}")

  # Add metadata (optional)
  IF context.metadata AND len(context.metadata) > 0:
    lines.append("metadata:")
    FOR key, value IN context.metadata.items():
      lines.append(f"  {key}: {value}")

  RETURN "\n".join(lines)

# Helper: Format Invocation Comment
def format_invoke_comment(invocation):
  """
  Format an AgentInvocation as an ALS invoke-request comment.
  This stores the invocation context for the invoked agent to read.
  """
  lines = [
    "ALS/1",
    f"actor: {invocation.resume_as.agent_type}",  # Original requester
    "intent: request",
    "action: invoke-request",
    f"tags.add: [Invoke-{invocation.agent_type.capitalize()}]",
    "tags.remove: []",
    f"summary: Invoking {invocation.agent_type} for {invocation.mode}.",
  ]

  # Add context details
  lines.append("details:")
  lines.append(f"- reason: {invocation.context.reason}")
  IF invocation.context.question:
    lines.append(f"- question: {invocation.context.question}")
  IF invocation.context.files_of_interest:
    lines.append("- files_of_interest:")
    FOR file_path IN invocation.context.files_of_interest:
      lines.append(f"  - {file_path}")

  # Add conflict details if present (for Ops → Architect)
  IF invocation.context.conflict_details:
    cd = invocation.context.conflict_details
    lines.append("- conflict_details:")
    lines.append(f"  conflicting_files: {cd.conflicting_files}")
    lines.append(f"  develop_summary: {cd.develop_summary}")
    lines.append(f"  feature_summary: {cd.feature_summary}")

  # Add resume info
  lines.append("invoke_context:")
  lines.append(f"  agent_type: {invocation.agent_type}")
  lines.append(f"  mode: {invocation.mode}")
  lines.append(f"  resume_as: {invocation.resume_as.agent_type}/{invocation.resume_as.mode}")

  RETURN "\n".join(lines)

# 4a: Dispatch BA workers - DRAIN QUEUE (no code dependencies, safe to process all)
#
# BA evaluation is safe to run for ALL pending tasks because:
# - No code modifications (just requirement analysis)
# - No git operations
# - Each task evaluation is independent
#
# Load config for max tasks per cycle
MAX_BA_TASKS_PER_CYCLE = config.settings.pipeline.maxBaTasksPerCycle OR 10
BA_DRAINING_ENABLED = config.settings.pipeline.baQueueDraining OR true

IF BA_ENABLED AND BA_QUEUE.length > 0:
  ba_count = 0
  ba_failures = 0

  IF BA_DRAINING_ENABLED:
    Report: ""
    Report: "╔══════════════════════════════════════════════════════════════════╗"
    Report: "║  PHASE 1: BA QUEUE DRAINING                                      ║"
    Report: "║  Processing up to {MAX_BA_TASKS_PER_CYCLE} of {BA_QUEUE.length} BA tasks  ║"
    Report: "╚══════════════════════════════════════════════════════════════════╝"
    Report: ""

    # Process ALL BA tasks (up to max per cycle)
    WHILE BA_QUEUE.length > 0 AND ba_count < MAX_BA_TASKS_PER_CYCLE:
      item = BA_QUEUE.shift()

      # EXPLICIT WORK PACKAGE BUILDING (not pseudocode - actual MCP calls)
      # Fetch full task details via MCP
      full_task = mcp__joan__get_task(item.task.id)
      task_comments = mcp__joan__list_task_comments(item.task.id)

      # Get column name from COLUMN_CACHE
      task_column_name = get_column_name_from_cache(full_task.column_id, COLUMN_CACHE)

      # Build work package JSON
      work_package = {
        "task_id": full_task.id,
        "task_title": full_task.title,
        "task_description": full_task.description || "",
        "task_tags": extract_tag_names(full_task.tags),
        "task_column": task_column_name,
        "task_comments": task_comments,
        "mode": item.mode,
        "project_id": PROJECT_ID,
        "project_name": PROJECT_NAME,
        "previous_stage_context": null  // BA is first stage
      }

      Report: "BA [{ba_count + 1}/{MAX_BA_TASKS_PER_CYCLE}] Dispatching for '{item.task.title}' (mode: {item.mode})"

      # Dispatch worker with work package in prompt
      result = Task tool call:
        subagent_type: "business-analyst"
        model: MODEL
        prompt: |
          You are a Business Analyst worker. Process this task and return a structured JSON result.

          **IMPORTANT: You do NOT have access to MCP tools. All task data is provided in the work package below.**

          ## Work Package
          ```json
          {JSON.stringify(work_package, null, 2)}
          ```

          ## Instructions
          Follow /agents:ba-worker logic for mode "{item.mode}".
          Analyze the task data provided above and determine if requirements are complete.

          ## Required Output
          Return ONLY a JSON object with this structure (no markdown, no explanation):
          ```json
          {
            "success": true/false,
            "summary": "What you did",
            "joan_actions": {
              "add_tags": ["tag names to add"],
              "remove_tags": ["tag names to remove"],
              "add_comment": "ALS/1 format comment",
              "move_to_column": "column name or null"
            },
            "worker_type": "ba",
            "task_id": "{full_task.id}",
            "needs_human": "reason if blocked, or null"
          }
          ```

      # Check if result indicates failure (we continue anyway, per design)
      IF result indicates failure:
        ba_failures++
        Report: "  WARNING: BA task '{item.task.title}' failed - continuing with others"
        # Record failure but don't stop - we continue processing remaining BA tasks

      RESULTS.push({worker: "ba", task: item.task, result: result})
      ba_count++
      DISPATCHED++

    Report: ""
    Report: "BA draining complete: {ba_count} dispatched, {ba_failures} failures"
    IF BA_QUEUE.length > 0:
      Report: "  {BA_QUEUE.length} BA tasks remaining (will process next cycle)"
    Report: ""

  ELSE:
    # Legacy single-task mode (for debugging or if draining disabled)
    item = BA_QUEUE.shift()

    # EXPLICIT WORK PACKAGE BUILDING
    full_task = mcp__joan__get_task(item.task.id)
    task_comments = mcp__joan__list_task_comments(item.task.id)
    task_column_name = get_column_name_from_cache(full_task.column_id, COLUMN_CACHE)

    work_package = {
      "task_id": full_task.id,
      "task_title": full_task.title,
      "task_description": full_task.description || "",
      "task_tags": extract_tag_names(full_task.tags),
      "task_column": task_column_name,
      "task_comments": task_comments,
      "mode": item.mode,
      "project_id": PROJECT_ID,
      "project_name": PROJECT_NAME,
      "previous_stage_context": null
    }

    Report: "Dispatching BA worker for '{item.task.title}' (mode: {item.mode})"

    result = Task tool call:
      subagent_type: "business-analyst"
      model: MODEL
      prompt: |
        You are a Business Analyst worker. Process this task and return a structured JSON result.

        **IMPORTANT: You do NOT have access to MCP tools. All task data is provided in the work package below.**

        ## Work Package
        ```json
        {JSON.stringify(work_package, null, 2)}
        ```

        ## Instructions
        Follow /agents:ba-worker logic for mode "{item.mode}".

        ## Required Output
        Return ONLY a JSON object with this structure (no markdown, no explanation):
        ```json
        {
          "success": true/false,
          "summary": "What you did",
          "joan_actions": {
            "add_tags": ["tag names to add"],
            "remove_tags": ["tag names to remove"],
            "add_comment": "ALS/1 format comment",
            "move_to_column": "column name or null"
          },
          "worker_type": "ba",
          "task_id": "{full_task.id}",
          "needs_human": "reason if blocked, or null"
        }
        ```

    RESULTS.push({worker: "ba", task: item.task, result: result})
    DISPATCHED++

# 4b: Dispatch Architect worker (ONE TASK ONLY - respects pipeline gate)
#
# NOTE: The pipeline gate in Step 3b clears ARCHITECT_QUEUE if pipeline is blocked.
# If we reach here with tasks in the queue, the pipeline is clear and we can plan.
# Only plan ONE task to maintain strict serialization.
#
IF ARCHITECT_ENABLED AND ARCHITECT_QUEUE.length > 0:
  Report: ""
  Report: "╔══════════════════════════════════════════════════════════════════╗"
  Report: "║  PHASE 2: SERIAL DEV PIPELINE - ARCHITECT                        ║"
  Report: "║  Planning ONE task (pipeline is clear)                           ║"
  Report: "╚══════════════════════════════════════════════════════════════════╝"
  Report: ""

  item = ARCHITECT_QUEUE.shift()  # Take first (oldest) Ready task

  # EXPLICIT WORK PACKAGE BUILDING
  full_task = mcp__joan__get_task(item.task.id)
  task_comments = mcp__joan__list_task_comments(item.task.id)
  task_column_name = get_column_name_from_cache(full_task.column_id, COLUMN_CACHE)

  # Extract previous stage context (BA → Architect handoff)
  previous_stage_context = extract_stage_context_from_comments(task_comments, "ba", "architect")

  work_package = {
    "task_id": full_task.id,
    "task_title": full_task.title,
    "task_description": full_task.description || "",
    "task_tags": extract_tag_names(full_task.tags),
    "task_column": task_column_name,
    "task_comments": task_comments,
    "mode": item.mode,
    "project_id": PROJECT_ID,
    "project_name": PROJECT_NAME,
    "previous_stage_context": previous_stage_context
  }

  Report: "Dispatching Architect worker for '{item.task.title}' (mode: {item.mode})"

  result = Task tool call:
    subagent_type: "architect"
    model: MODEL
    prompt: |
      You are an Architect worker. Process this task and return a structured JSON result.

      **IMPORTANT: You do NOT have access to MCP tools. All task data is provided in the work package below.**

      ## Work Package
      ```json
      {JSON.stringify(work_package, null, 2)}
      ```

      ## Instructions
      Follow /agents:architect-worker logic for mode "{item.mode}".

      ## Required Output
      Return ONLY a JSON object with this structure:
      ```json
      {
        "success": true/false,
        "summary": "What you did",
        "joan_actions": {
          "add_tags": ["tag names"],
          "remove_tags": ["tag names"],
          "add_comment": "ALS/1 format comment",
          "move_to_column": "column name or null",
          "update_description": "new description with plan, or null"
        },
        "worker_type": "architect",
        "task_id": "{full_task.id}",
        "needs_human": "reason if blocked, or null"
      }
      ```

  RESULTS.push({worker: "architect", task: item.task, result: result})
  DISPATCHED++

# 4c: Dispatch Dev worker (ONE TASK - strict serial mode enforces single dev)
#
# STRICT SERIAL MODE: Only one dev worker exists (DEV_COUNT=1).
# This ensures:
# - No parallel development that could cause merge conflicts
# - Plans always reference current codebase state
# - No race conditions for task claiming
#
IF DEVS_ENABLED AND DEV_QUEUE.length > 0:
  Report: ""
  Report: "╔══════════════════════════════════════════════════════════════════╗"
  Report: "║  PHASE 2: SERIAL DEV PIPELINE - DEVELOPMENT                      ║"
  Report: "║  Implementing ONE task (strict serial mode)                      ║"
  Report: "╚══════════════════════════════════════════════════════════════════╝"
  Report: ""

  # In strict serial mode, we only have dev_id = 1
  dev_id = 1
  available_devs = find_available_devs()

  IF dev_id IN available_devs AND DEV_QUEUE.length > 0:
    item = DEV_QUEUE.shift()
    task = item.task

    # ATOMIC CLAIM before dispatch (coordinator does this, not worker)
    mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE["Claimed-Dev-{dev_id}"])
    Wait 1 second
    updated_task = mcp__joan__get_task(task.id)

    IF claim verified (Claimed-Dev-{dev_id} tag present):
      # EXPLICIT WORK PACKAGE BUILDING
      full_task = mcp__joan__get_task(task.id)
      task_comments = mcp__joan__list_task_comments(task.id)
      task_column_name = get_column_name_from_cache(full_task.column_id, COLUMN_CACHE)

      # Extract previous stage context (Architect → Dev or Reviewer → Dev for rework)
      expected_from = (item.mode == "rework" OR item.mode == "conflict") ? "reviewer" : "architect"
      previous_stage_context = extract_stage_context_from_comments(task_comments, expected_from, "dev")

      work_package = {
        "task_id": full_task.id,
        "task_title": full_task.title,
        "task_description": full_task.description || "",
        "task_tags": extract_tag_names(full_task.tags),
        "task_column": task_column_name,
        "task_comments": task_comments,
        "mode": item.mode,
        "project_id": PROJECT_ID,
        "project_name": PROJECT_NAME,
        "dev_id": dev_id,
        "previous_stage_context": previous_stage_context
      }

      Report: "Dispatching Dev worker for '{task.title}' (mode: {item.mode})"

      result = Task tool call:
        subagent_type: "implementation-worker"
        model: MODEL
        prompt: |
          You are the Dev Worker. Implement this task and return a structured JSON result.

          **IMPORTANT: You do NOT have access to MCP tools. All task data is provided in the work package below.**

          ## Work Package
          ```json
          {JSON.stringify(work_package, null, 2)}
          ```

          ## Instructions
          Follow /agents:dev-worker logic for mode "{item.mode}".

          ## Required Output
          Return ONLY a JSON object:
          ```json
          {
            "success": true/false,
            "summary": "What you implemented",
            "joan_actions": {
              "add_tags": ["Dev-Complete", "Design-Complete", "Test-Complete"],
              "remove_tags": ["Claimed-Dev-1", "Planned"],
              "add_comment": "ALS/1 format",
              "move_to_column": "Review"
            },
            "git_actions": {
              "branch_created": "feature/...",
              "files_changed": ["file1.ts", "file2.ts"],
              "commit_made": true,
              "pr_created": {"number": N, "url": "..."}
            },
            "worker_type": "dev",
            "task_id": "{full_task.id}",
            "needs_human": null
          }
          ```

      RESULTS.push({worker: "dev", dev_id: dev_id, task: task, result: result})
      DISPATCHED++

    ELSE:
      # Claim failed - another coordinator got it (unlikely in single-coordinator setup)
      mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE["Claimed-Dev-{dev_id}"])
      Report: "Claim failed for '{task.title}' - will retry next cycle"

  ELSE IF dev_id NOT IN available_devs:
    Report: "Dev worker busy (task already claimed) - skipping dispatch"

# 4d: Dispatch Reviewer worker (ONE TASK - part of serial pipeline)
IF REVIEWER_ENABLED AND REVIEWER_QUEUE.length > 0:
  Report: ""
  Report: "╔══════════════════════════════════════════════════════════════════╗"
  Report: "║  PHASE 2: SERIAL DEV PIPELINE - REVIEW                           ║"
  Report: "║  Reviewing ONE task                                              ║"
  Report: "╚══════════════════════════════════════════════════════════════════╝"
  Report: ""

  item = REVIEWER_QUEUE.shift()

  # EXPLICIT WORK PACKAGE BUILDING
  full_task = mcp__joan__get_task(item.task.id)
  task_comments = mcp__joan__list_task_comments(item.task.id)
  task_column_name = get_column_name_from_cache(full_task.column_id, COLUMN_CACHE)

  # Extract previous stage context (Dev → Reviewer handoff)
  previous_stage_context = extract_stage_context_from_comments(task_comments, "dev", "reviewer")

  work_package = {
    "task_id": full_task.id,
    "task_title": full_task.title,
    "task_description": full_task.description || "",
    "task_tags": extract_tag_names(full_task.tags),
    "task_column": task_column_name,
    "task_comments": task_comments,
    "mode": "review",
    "project_id": PROJECT_ID,
    "project_name": PROJECT_NAME,
    "previous_stage_context": previous_stage_context
  }

  Report: "Dispatching Reviewer worker for '{item.task.title}'"

  result = Task tool call:
    subagent_type: "code-reviewer"
    model: MODEL
    prompt: |
      You are a Code Reviewer worker. Review this task and return a structured JSON result.

      **IMPORTANT: You do NOT have access to MCP tools. All task data is provided in the work package below.**

      ## Work Package
      ```json
      {JSON.stringify(work_package, null, 2)}
      ```

      ## Instructions
      Follow /agents:reviewer-worker logic.

      ## Required Output
      Return ONLY a JSON object:
      ```json
      {
        "success": true/false,
        "summary": "Review findings",
        "joan_actions": {
          "add_tags": ["Review-Approved"] or ["Rework-Requested", "Planned"],
          "remove_tags": ["Review-In-Progress"] or completion tags if rejecting,
          "add_comment": "ALS/1 format with review details",
          "move_to_column": null or "Development" if rework needed
        },
        "worker_type": "reviewer",
        "task_id": "{full_task.id}",
        "needs_human": null
      }
      ```

  RESULTS.push({worker: "reviewer", task: item.task, result: result})
  DISPATCHED++

# 4e: Dispatch Ops worker (ONE TASK - final step in serial pipeline)
#
# Ops merges the task to develop, which UNLOCKS the pipeline for the next task.
# After Ops completes successfully, the pipeline gate will be CLEAR on next poll.
#
IF OPS_ENABLED AND OPS_QUEUE.length > 0:
  Report: ""
  Report: "╔══════════════════════════════════════════════════════════════════╗"
  Report: "║  PHASE 2: SERIAL DEV PIPELINE - OPS (FINAL STEP)                 ║"
  Report: "║  Merging ONE task to develop → UNLOCKS pipeline                  ║"
  Report: "╚══════════════════════════════════════════════════════════════════╝"
  Report: ""

  item = OPS_QUEUE.shift()

  # EXPLICIT WORK PACKAGE BUILDING
  full_task = mcp__joan__get_task(item.task.id)
  task_comments = mcp__joan__list_task_comments(item.task.id)
  task_column_name = get_column_name_from_cache(full_task.column_id, COLUMN_CACHE)

  # Extract previous stage context (Reviewer → Ops handoff)
  previous_stage_context = extract_stage_context_from_comments(task_comments, "reviewer", "ops")

  work_package = {
    "task_id": full_task.id,
    "task_title": full_task.title,
    "task_description": full_task.description || "",
    "task_tags": extract_tag_names(full_task.tags),
    "task_column": task_column_name,
    "task_comments": task_comments,
    "mode": item.mode,
    "project_id": PROJECT_ID,
    "project_name": PROJECT_NAME,
    "previous_stage_context": previous_stage_context
  }

  Report: "Dispatching Ops worker for '{item.task.title}' (mode: {item.mode})"

  result = Task tool call:
    subagent_type: "ops"
    model: MODEL
    prompt: |
      You are an Ops worker. Handle integration operations and return a structured JSON result.

      **IMPORTANT: You do NOT have access to MCP tools. All task data is provided in the work package below.**

      ## Work Package
      ```json
      {JSON.stringify(work_package, null, 2)}
      ```

      ## Instructions
      Follow /agents:ops-worker logic for mode "{item.mode}".

      ## Required Output
      Return ONLY a JSON object:
      ```json
      {
        "success": true/false,
        "summary": "What you did",
        "joan_actions": {
          "add_tags": [],
          "remove_tags": ["Review-Approved", "Ops-Ready"],
          "add_comment": "ALS/1 format",
          "move_to_column": "Deploy" or "Development" if conflict
        },
        "git_actions": {
          "merged_to": "develop",
          "commit_sha": "..."
        },
        "worker_type": "ops",
        "task_id": "{full_task.id}",
        "needs_human": null or "reason"
      }
      ```

  RESULTS.push({worker: "ops", task: item.task, result: result})
  DISPATCHED++

Report: "Dispatched {DISPATCHED} workers"
```

---

## Step 4f: Execute Worker Results (MCP Proxy)

After all workers complete, execute their requested MCP actions.
**Enhanced error handling ensures failures are recorded and claims are released.**

```
PARSE_FAILURES = 0

FOR EACH {worker, task, result, dev_id} IN RESULTS:

  Report: "Processing result from {worker} worker for '{task.title}'"

  # 1. Parse result (handle both JSON and text responses)
  parsed = parse_json_from_result(result)

  IF parsed is null:
    PARSE_FAILURES++
    Report: "ERROR: Unparseable result from {worker} worker for '{task.title}'"

    # Log failure details for debugging
    raw_preview = first 500 chars of result
    Report: "  Raw result preview: {raw_preview}"

    # Record the failure in task comments for audit trail
    mcp__joan__create_task_comment(task.id,
      "ALS/1
      actor: coordinator
      intent: error
      action: result-parse-failure
      tags.add: []
      tags.remove: []
      summary: Worker returned unparseable result.
      details:
      - worker_type: {worker}
      - raw_result_preview: {raw_preview}
      - action: Task will be re-processable on next poll cycle")

    # For dev workers, release the claim so task can be re-processed
    IF worker == "dev" AND dev_id:
      claim_tag = "Claimed-Dev-{dev_id}"
      IF TAG_CACHE[claim_tag]:
        mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE[claim_tag])
        Report: "  Released claim {claim_tag} (task will be retried)"

    CONTINUE

  # 1b. Validate required fields
  required_fields = ["success", "summary", "joan_actions", "worker_type", "task_id"]
  missing_fields = []
  FOR field IN required_fields:
    IF field NOT IN parsed:
      missing_fields.push(field)

  IF missing_fields.length > 0:
    PARSE_FAILURES++
    Report: "ERROR: Missing required fields in {worker} result: {missing_fields}"

    mcp__joan__create_task_comment(task.id,
      "ALS/1
      actor: coordinator
      intent: error
      action: result-validation-failure
      tags.add: []
      tags.remove: []
      summary: Worker result missing required fields.
      details:
      - worker_type: {worker}
      - missing_fields: {missing_fields}
      - action: Task will be re-processable on next poll cycle")

    # Release dev claims
    IF worker == "dev" AND dev_id:
      claim_tag = "Claimed-Dev-{dev_id}"
      IF TAG_CACHE[claim_tag]:
        mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE[claim_tag])
        Report: "  Released claim {claim_tag} (task will be retried)"

    CONTINUE

  # 2. Check success status
  IF NOT parsed.success:
    Report: "Worker reported FAILURE: {parsed.summary}"
    IF parsed.needs_human:
      Report: "Needs human intervention: {parsed.needs_human}"
      # Add failure tag for visibility
      mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE["Implementation-Failed"])

    # Release dev claims on failure (DEPRECATED: workers now handle this via joan_actions)
    IF worker == "dev" AND dev_id:
      claim_tag = "Claimed-Dev-{dev_id}"
      IF TAG_CACHE[claim_tag]:
        mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE[claim_tag])
        Report: "  Released claim {claim_tag}"

  # 3. Execute joan_actions
  actions = parsed.joan_actions

  # 3a. Add tags
  IF actions.add_tags AND actions.add_tags.length > 0:
    FOR tag_name IN actions.add_tags:
      IF TAG_CACHE[tag_name]:
        mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE[tag_name])
        Report: "  Added tag: {tag_name}"
      ELSE:
        Report: "  WARNING: Unknown tag '{tag_name}', skipping"

  # 3b. Remove tags
  IF actions.remove_tags AND actions.remove_tags.length > 0:
    FOR tag_name IN actions.remove_tags:
      IF TAG_CACHE[tag_name]:
        mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE[tag_name])
        Report: "  Removed tag: {tag_name}"

  # 3c. Add comment
  IF actions.add_comment AND actions.add_comment.length > 0:
    mcp__joan__create_task_comment(task.id, actions.add_comment)
    Report: "  Added comment"

  # 3d. Update description (for architect plans)
  IF actions.update_description:
    mcp__joan__update_task(task.id, description=actions.update_description)
    Report: "  Updated task description"

  # 3e. Move to column
  IF actions.move_to_column AND COLUMN_CACHE[actions.move_to_column]:
    mcp__joan__update_task(task.id, column_id=COLUMN_CACHE[actions.move_to_column])
    Report: "  Moved to column: {actions.move_to_column}"

  # 3f. Create context handoff comment (if worker provided stage_context)
  IF parsed.stage_context:
    context = parsed.stage_context

    # Validate size constraint (max 3KB)
    context_json = JSON.stringify(context)
    IF context_json.length > 3072:
      Report: "  WARNING: stage_context exceeds 3KB limit ({context_json.length} bytes), truncating"
      # Truncate key_decisions and files_of_interest to fit
      context.key_decisions = context.key_decisions[:3]
      context.files_of_interest = context.files_of_interest[:5]
      context.warnings = context.warnings[:2]

    # Format as ALS handoff comment
    handoff_comment = format_handoff_comment(context)
    mcp__joan__create_task_comment(task.id, handoff_comment)
    Report: "  Created context handoff: {context.from_stage} → {context.to_stage}"

  # 3g. Auto-Approval Post-Dispatch (YOLO Mode)
  # NOTE: This catches approvals added by workers in THIS cycle.
  # Pre-dispatch approval (Step 3a) catches approvals from PREVIOUS cycles.
  # Both are needed for complete YOLO coverage.
  IF MODE == "yolo":
    Report: "YOLO mode: checking for post-dispatch auto-approval opportunities"

    # Auto-approve plans
    IF worker == "architect" AND actions.add_tags?.includes("Plan-Pending-Approval"):
      Report: "  Auto-approving plan (YOLO mode)"

      # Fetch updated task to check current state
      updated_task = mcp__joan__get_task(task.id)

      # Add Plan-Approved tag if not already present
      IF TAG_CACHE["Plan-Approved"] AND NOT task_has_tag(updated_task, "Plan-Approved"):
        mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE["Plan-Approved"])

        # Add audit comment
        mcp__joan__create_task_comment(task.id,
          "ALS/1
          actor: coordinator
          intent: decision
          action: auto-approve-plan
          tags.add: [Plan-Approved]
          tags.remove: []
          summary: Plan auto-approved (YOLO mode active).
          details:
          - mode: yolo
          - reason: Auto-approval bypasses human review gate
          - next: Architect will finalize on next poll")

        Report: "  ✓ Added Plan-Approved tag"
      ELSE:
        Report: "  Plan-Approved already present, skipping"

    # Auto-approve merges
    IF worker == "reviewer" AND actions.add_tags?.includes("Review-Approved"):
      Report: "  Auto-approving merge (YOLO mode)"

      # Fetch updated task to check current state
      updated_task = mcp__joan__get_task(task.id)

      # Add Ops-Ready tag if not already present
      IF TAG_CACHE["Ops-Ready"] AND NOT task_has_tag(updated_task, "Ops-Ready"):
        mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE["Ops-Ready"])

        # Add audit comment
        mcp__joan__create_task_comment(task.id,
          "ALS/1
          actor: coordinator
          intent: decision
          action: auto-approve-merge
          tags.add: [Ops-Ready]
          tags.remove: []
          summary: Merge auto-approved (YOLO mode active).
          details:
          - mode: yolo
          - reason: Auto-approval bypasses human merge gate
          - next: Ops will merge on next poll")

        Report: "  ✓ Added Ops-Ready tag"
      ELSE:
        Report: "  Ops-Ready already present, skipping"

  # 3g-metrics. Track Reworks and Other Workflow Metrics
  # Log metrics for reworks (Reviewer → Dev), Doctor fixes, and other workflow events
  # These metrics help identify issues with agent prompts and workflow effectiveness

  METRICS_FILE = "{PROJECT_DIR}/.claude/logs/agent-metrics.jsonl"

  # Track rework requests (indicates review failures)
  IF worker == "reviewer" AND actions.add_tags?.includes("Rework-Requested"):
    Report: "  Logging rework metrics"

    # Extract rework reason from the comment (if structured)
    rework_reason = "Code review failed"
    IF parsed.summary:
      rework_reason = parsed.summary

    rework_metric = {
      "timestamp": NOW in ISO format,
      "event": "rework_requested",
      "project": PROJECT_NAME,
      "task_id": task.id,
      "task_title": task.title,
      "workflow_step": "Review→Development",
      "reason": rework_reason,
      "reviewer_summary": parsed.summary,
      "cycle_count": 1  # Would increment if tracking multiple rework cycles
    }

    Run bash command:
      echo '{JSON.stringify(rework_metric)}' >> {METRICS_FILE}

    Report: "  ✓ Rework metric logged"

  # Track successful task completions (for velocity metrics)
  IF worker == "ops" AND actions.move_to_column == "Deploy":
    Report: "  Logging task completion metrics"

    completion_metric = {
      "timestamp": NOW in ISO format,
      "event": "task_completed",
      "project": PROJECT_NAME,
      "task_id": task.id,
      "task_title": task.title,
      "workflow_step": "Review→Deploy",
      "final_status": "merged"
    }

    Run bash command:
      echo '{JSON.stringify(completion_metric)}' >> {METRICS_FILE}

    Report: "  ✓ Completion metric logged"

  # Track implementation failures (indicates dev worker issues)
  IF worker == "dev" AND NOT parsed.success:
    Report: "  Logging implementation failure metrics"

    failure_metric = {
      "timestamp": NOW in ISO format,
      "event": "implementation_failed",
      "project": PROJECT_NAME,
      "task_id": task.id,
      "task_title": task.title,
      "workflow_step": "Development",
      "failure_reason": parsed.needs_human OR parsed.summary OR "Unknown",
      "dev_summary": parsed.summary
    }

    Run bash command:
      echo '{JSON.stringify(failure_metric)}' >> {METRICS_FILE}

    Report: "  ✓ Failure metric logged"

  # 3h. Handle agent invocation (cross-agent consultation)
  IF parsed.invoke_agent:
    invocation = parsed.invoke_agent
    Report: "  Processing agent invocation: {worker} → {invocation.agent_type}"

    # Store invocation context as ALS comment for the invoked agent
    invoke_comment = format_invoke_comment(invocation)
    mcp__joan__create_task_comment(task.id, invoke_comment)
    Report: "  Stored invocation context for {invocation.agent_type}"

    # Set flag to skip sleep and re-poll immediately
    INVOCATION_PENDING = true
    Report: "  INVOCATION_PENDING set - will skip sleep for fast resolution"

  # 4. Verify post-conditions
  updated_task = mcp__joan__get_task(task.id)

  # Verify tags were applied
  FOR tag_name IN (actions.add_tags or []):
    IF TAG_CACHE[tag_name] AND NOT hasTag(updated_task, tag_name):
      Report: "  WARNING: Tag '{tag_name}' not applied, retrying..."
      mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE[tag_name])

  # Verify tags were removed
  FOR tag_name IN (actions.remove_tags or []):
    IF TAG_CACHE[tag_name] AND hasTag(updated_task, tag_name):
      Report: "  WARNING: Tag '{tag_name}' not removed, retrying..."
      mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE[tag_name])

  Report: "Completed processing for '{task.title}': {parsed.summary}"

# Summary
IF PARSE_FAILURES > 0:
  Report: "WARNING: {PARSE_FAILURES} worker results failed to parse (tasks will be retried)"

Report: "All {RESULTS.length} worker results processed ({RESULTS.length - PARSE_FAILURES} successful, {PARSE_FAILURES} failed)"
```

### Helper: parse_json_from_result(result)

```
# Workers return text that should contain JSON
# Extract JSON from the result, handling various formats

1. Try direct JSON.parse(result)
2. If fails, look for ```json ... ``` block and extract
3. If fails, look for { ... } pattern and extract
4. If all fail, return null
```

### Helper: find_available_devs()

```
claimed_devs = []
For each task in all tasks:
  For N in 1..DEV_COUNT:
    IF hasTag("Claimed-Dev-{N}"):
      claimed_devs.push(N)

available = []
For N in 1..DEV_COUNT:
  IF N not in claimed_devs:
    available.push(N)

RETURN available
```

---

## Step 5: Exit

```
# Calculate work summary
PENDING_HUMAN = count tasks with:
  - Plan-Pending-Approval (no Plan-Approved) → waiting for human approval
  - Review-Approved (no Ops-Ready) → waiting for human merge approval
  - Implementation-Failed or Branch-Setup-Failed → waiting for human fix

CLAIMED_TASKS = count tasks with Claimed-Dev-* tags (workers currently running)

# Write status file for scheduler (reliable work detection)
# This file is read by joan-scheduler.sh to determine if work was dispatched
PROJECT_SLUG = PROJECT_NAME.toLowerCase().replace(/[^a-z0-9]+/g, '-')
STATUS_FILE = "/tmp/joan-agents-{PROJECT_SLUG}.status"

Run bash command:
  echo "dispatched={DISPATCHED}" > {STATUS_FILE}
  echo "claimed={CLAIMED_TASKS}" >> {STATUS_FILE}
  echo "pending_human={PENDING_HUMAN}" >> {STATUS_FILE}
  echo "timestamp=$(date +%s)" >> {STATUS_FILE}

Report: ""
Report: "Poll complete: dispatched {DISPATCHED} workers"
IF PENDING_HUMAN > 0:
  Report: "  {PENDING_HUMAN} tasks awaiting human action in Joan UI"

IF DISPATCHED == 0:
  IF CLAIMED_TASKS > 0:
    Report: "No new work dispatched, but {CLAIMED_TASKS} workers still running (not idle)"
  ELSE:
    Report: "No work dispatched (all queues empty or pipeline blocked)"

Report: "Single pass complete. Exiting."
EXIT
```

**Note:** If this coordinator was spawned by the external scheduler (via `--loop` mode), the scheduler will automatically respawn a fresh coordinator process after the configured interval. This ensures continuous operation without context accumulation.

---

## Constraints

**CRITICAL - Autonomous Operation:**
- NEVER ask the user questions or prompt for input
- NEVER offer choices like "Would you like me to..." or "Should I..."
- NEVER pause to wait for user confirmation
- Human interaction happens via TAGS in Joan UI, not via conversation
- In loop mode: poll → dispatch → sleep → repeat (no interruptions)
- Only exit when: (a) single-pass mode completes, or (b) max idle polls reached

**Operational Rules:**
- NEVER parse comments for triggers (tags only)
- ALWAYS claim dev tasks before dispatching
- Dispatch at most ONE worker per type per cycle (except devs)
- Workers are single-pass - they exit after completing their task
- Report all queue sizes and dispatch actions for observability

**CRITICAL - Worker Dispatch Format:**
- ALWAYS use the EXACT command format: `/agents:dev-worker --task=... --dev=... --mode=...`
- NEVER create custom prompts with instructions like "checkout the branch" or task lists
- The worker commands (dev-worker.md) contain ALL the logic including branch setup
- Custom prompts bypass proper branch management and can cause issues
- The "Task Details" section is ONLY contextual reference - do NOT expand it into instructions

---

## Examples

```bash
# Single pass - dispatch workers once, then exit
/agents:dispatch

# Continuous operation - external scheduler with fresh context
/agents:dispatch --loop

# Custom poll interval (every 3 minutes)
/agents:dispatch --loop --interval=180

# Extended idle threshold (2 hours at 5-min intervals)
/agents:dispatch --loop --max-idle=24
```

**Recommended for production:** Use `--loop` mode for any operation lasting longer than 15 minutes. The external scheduler eliminates context bloat issues that occur in long-running sessions.

Begin coordination now.
