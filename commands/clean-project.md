---
description: Onboard backlog AND fix broken states (comprehensive cure-all)
argument-hint: [--apply] [--dry-run]
allowed-tools: mcp__joan__*, Read, Bash
---

# Project Cleanup & Recovery (Comprehensive)

This command is a **single comprehensive solution** that handles:
1. **Fresh backlog onboarding** - Integrates new tasks into the workflow
2. **Broken state recovery** - Fixes incorrectly tagged tasks
3. **Column drift correction** - Moves misplaced tasks to correct columns
4. **Tag inconsistency cleanup** - Removes stale or incorrect workflow tags

All categorization is based on **actual state** (evidence in descriptions, column placement), not assumptions.

## Key Principles

1. **Evidence-based** - Inspect task descriptions for PR links, commits, implementation plans
2. **Detect anomalies** - Identify incorrect tags, misplaced columns, broken states
3. **Auto-correct** - Fix recoverable issues (wrong tags, wrong columns)
4. **Fail-safe** - Never skip workflow stages, never assume completion without evidence
5. **Audit trail** - Add ALS comments documenting all changes

## Recovery Capabilities

This command detects and fixes:

✅ **Incorrect completion tags** - Tasks with Review-Approved/Ops-Ready but no evidence
✅ **Column drift** - Tasks in wrong column for their workflow state
✅ **Missing workflow tags** - Tasks that should be in workflow but aren't tagged
✅ **Stale tags** - Leftover tags from failed operations or manual moves

**What it WON'T fix** (requires manual review):
⚠️ Tasks with unclear state that could be interpreted multiple ways
⚠️ Tasks with conflicting evidence (e.g., plan says done, no PR exists)

## Mode

- `--apply` → Make changes to Joan
- `--dry-run` or no flag → Report only, no changes

## Logic Flow

```
Step 1: Load Configuration
Step 2: Verify Workflow Tags Exist
Step 3: Fetch All Tasks
Step 4: Categorize Tasks by State
Step 5: Apply Tags (if --apply)
Step 6: Report Summary
```

---

## Step 1: Load Configuration

```bash
CONFIG_FILE=".joan-agents.json"

IF NOT exists(CONFIG_FILE):
  Report: "ERROR: .joan-agents.json not found. Run /agents:init first."
  EXIT

config = read_json(CONFIG_FILE)
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName

Report: "Project: {PROJECT_NAME}"
Report: "Project ID: {PROJECT_ID}"
```

---

## Step 2: Verify Workflow Tags Exist

```typescript
tags = mcp__joan__list_project_tags(PROJECT_ID)

TAG_CACHE = {}
FOR tag IN tags:
  TAG_CACHE[tag.name] = tag.id

REQUIRED_TAGS = [
  "Ready", "Needs-Clarification", "Clarification-Answered",
  "Plan-Pending-Approval", "Plan-Approved", "Plan-Rejected", "Planned",
  "Dev-Complete", "Design-Complete", "Test-Complete",
  "Review-In-Progress", "Review-Approved", "Rework-Requested", "Ops-Ready"
]

missing_tags = []
FOR tag_name IN REQUIRED_TAGS:
  IF tag_name NOT IN TAG_CACHE:
    missing_tags.push(tag_name)

IF missing_tags.length > 0:
  Report: "ERROR: Missing required tags: {missing_tags}"
  Report: "Run /agents:init to create workflow tags."
  EXIT

Report: "All workflow tags present"
```

---

## Step 3: Fetch All Tasks

```typescript
columns = mcp__joan__list_columns(PROJECT_ID)

COLUMN_CACHE = {}
FOR col IN columns:
  COLUMN_CACHE[col.name] = col.id

tasks = mcp__joan__list_tasks(project_id=PROJECT_ID)

Report: "Fetched {tasks.length} tasks"
```

---

## Step 4: Categorize Tasks by State

```typescript
# Categorization results
TO_SKIP = []                  # Already in workflow, Done, or terminal
TO_TAG = []                   # Need workflow tags applied
MISPLACED = []                # In wrong column for their state
INCORRECT_COMPLETION_TAGS = [] # Have end-stage tags without evidence (recovery)
NEEDS_MANUAL = []             # Require human decision

# Helper: Check if task has any workflow tags
hasWorkflowTags(task):
  WORKFLOW_TAGS = [
    "Ready", "Needs-Clarification", "Plan-Pending-Approval", "Plan-Approved",
    "Planned", "Dev-Complete", "Design-Complete", "Test-Complete",
    "Review-Approved", "Rework-Requested", "Ops-Ready"
  ]
  FOR tag IN task.tags:
    IF tag.name IN WORKFLOW_TAGS:
      RETURN true
  RETURN false

# Helper: Check if task has implementation plan
hasImplementationPlan(description):
  # Look for structured plan markers
  markers = [
    "## Implementation Plan",
    "### Sub-Tasks",
    "### Development (@developer)",
    "### Testing (@tester)",
    "**Branch**:"
  ]
  FOR marker IN markers:
    IF marker IN description:
      RETURN true
  RETURN false

# Helper: Check if task has evidence of completion
hasCompletionEvidence(task):
  # Check description for PR links, commit references
  desc = task.description or ""

  # Patterns indicating completion
  patterns = [
    /PR #\d+/,
    /pull\/\d+/,
    /Commit: [a-f0-9]{7}/,
    /merged/i,
    /deployed/i
  ]

  FOR pattern IN patterns:
    IF desc.matches(pattern):
      RETURN true

  # Check for completion tags already present
  IF hasTag(task, "Dev-Complete") OR hasTag(task, "Design-Complete"):
    RETURN true

  RETURN false

# Process each task
FOR task IN tasks:
  full_task = mcp__joan__get_task(task.id)

  # === SKIP CRITERIA ===

  # Skip 1: Tasks in Done column
  IF inColumn(task, "Done"):
    TO_SKIP.push({task, reason: "In Done column"})
    CONTINUE

  # Skip 2: Tasks already in workflow (have workflow tags)
  IF hasWorkflowTags(task):
    TO_SKIP.push({task, reason: "Already has workflow tags"})
    CONTINUE

  # Skip 3: Tasks in To Do (waiting for BA)
  IF inColumn(task, "To Do"):
    TO_SKIP.push({task, reason: "In To Do, waiting for BA evaluation"})
    CONTINUE

  # === RECOVERY: DETECT INCORRECT COMPLETION TAGS ===

  # This catches tasks that were incorrectly tagged with end-stage tags
  # (Review-Approved, Ops-Ready) but have no evidence of completion.
  # Common scenario: backlog onboarding error, manual mis-tagging

  has_review_approved = hasTag(task, "Review-Approved")
  has_ops_ready = hasTag(task, "Ops-Ready")
  has_completion_evidence = hasCompletionEvidence(task)

  IF (has_review_approved OR has_ops_ready) AND NOT has_completion_evidence:
    # Task has end-stage tags but no PR/commit evidence - INCORRECT

    tags_to_remove = []
    IF has_review_approved:
      tags_to_remove.push("Review-Approved")
    IF has_ops_ready:
      tags_to_remove.push("Ops-Ready")

    # Also remove any stale workflow tags
    IF hasTag(task, "Rework-Requested"):
      tags_to_remove.push("Rework-Requested")
    IF hasTag(task, "Rework-Complete"):
      tags_to_remove.push("Rework-Complete")

    INCORRECT_COMPLETION_TAGS.push({
      task,
      action: "remove_incorrect_completion_tags",
      tags_add: ["Planned"],
      tags_remove: tags_to_remove,
      move_to: "Development",
      reason: "Has end-stage tags (Review-Approved/Ops-Ready) but no completion evidence"
    })
    CONTINUE

  # === CATEGORIZATION ===

  # Category 1: Tasks in Analyse with implementation plan (Architect created plan)
  IF inColumn(task, "Analyse") AND hasImplementationPlan(full_task.description):
    # Architect created plan, but Plan-Pending-Approval tag is missing
    TO_TAG.push({
      task,
      action: "add_plan_pending",
      tags_add: ["Plan-Pending-Approval"],
      tags_remove: [],
      move_to: null,
      reason: "Has implementation plan, needs Plan-Pending-Approval tag"
    })
    CONTINUE

  # Category 2: Tasks in Development with implementation plan but no Planned tag
  IF inColumn(task, "Development") AND hasImplementationPlan(full_task.description):
    # Should have Planned tag to be claimable by dev
    TO_TAG.push({
      task,
      action: "add_planned",
      tags_add: ["Planned"],
      tags_remove: [],
      move_to: null,
      reason: "In Development with plan, needs Planned tag"
    })
    CONTINUE

  # Category 3: Tasks in Review or Deploy with completion evidence
  IF (inColumn(task, "Review") OR inColumn(task, "Deploy")) AND hasCompletionEvidence(task):
    # Check if already has completion tags
    has_completion_tags = (
      hasTag(task, "Dev-Complete") AND
      hasTag(task, "Design-Complete") AND
      hasTag(task, "Test-Complete")
    )

    IF has_completion_tags:
      # Has completion tags, check column placement
      IF inColumn(task, "Deploy"):
        # Should be in Review, not Deploy (Reviewer hasn't processed yet)
        MISPLACED.push({
          task,
          current_column: "Deploy",
          should_be: "Review",
          reason: "Has completion tags but not yet reviewed"
        })
      ELSE:
        # Correctly in Review with completion tags
        TO_SKIP.push({task, reason: "In Review with completion tags (correct state)"})
      CONTINUE

    # Needs completion tags added
    TO_TAG.push({
      task,
      action: "add_completion_tags",
      tags_add: ["Dev-Complete", "Design-Complete", "Test-Complete"],
      tags_remove: [],
      move_to: "Review",  # Ensure in Review column
      reason: "Has completion evidence, needs completion tags"
    })
    CONTINUE

  # Category 4: Tasks in Deploy without completion tags (manually created with plans)
  IF inColumn(task, "Deploy") AND hasImplementationPlan(full_task.description) AND NOT hasCompletionEvidence(task):
    # These were manually created in Deploy with plans but NOT implemented
    # Should move to Development with Planned tag
    TO_TAG.push({
      task,
      action: "move_to_development",
      tags_add: ["Planned"],
      tags_remove: [],
      move_to: "Development",
      reason: "Has plan but no evidence of implementation - moving to Development"
    })
    CONTINUE

  # Category 5: Tasks in Analyse without plan (no workflow tags, no plan)
  IF inColumn(task, "Analyse"):
    # Waiting for Architect to create plan
    # Should have Ready tag to trigger Architect
    TO_TAG.push({
      task,
      action: "add_ready",
      tags_add: ["Ready"],
      tags_remove: [],
      move_to: null,
      reason: "In Analyse without plan, needs Ready tag for Architect"
    })
    CONTINUE

  # Default: Requires manual review
  NEEDS_MANUAL.push({
    task,
    column: get_column_name(task.column_id),
    has_plan: hasImplementationPlan(full_task.description),
    has_evidence: hasCompletionEvidence(task),
    reason: "Unclear state - requires manual review"
  })
```

---

## Step 5: Report Categories

```typescript
Report: ""
Report: "═══════════════════════════════════════════════════════════════"
Report: "  Project Cleanup & Recovery Analysis"
Report: "═══════════════════════════════════════════════════════════════"
Report: ""
Report: "Project: {PROJECT_NAME}"
Report: "Total tasks: {tasks.length}"
Report: ""
Report: "───────────────────────────────────────────────────────────────"
Report: "  Category Summary"
Report: "───────────────────────────────────────────────────────────────"
Report: ""
Report: "To Skip:                {TO_SKIP.length} tasks"
Report: "To Tag:                 {TO_TAG.length} tasks"
Report: "Misplaced:              {MISPLACED.length} tasks"
Report: "Incorrect Completion:   {INCORRECT_COMPLETION_TAGS.length} tasks (recovery)"
Report: "Needs Manual:           {NEEDS_MANUAL.length} tasks"
Report: ""

# Detail: Tasks to skip
IF TO_SKIP.length > 0:
  Report: "───────────────────────────────────────────────────────────────"
  Report: "  Tasks to Skip ({TO_SKIP.length})"
  Report: "───────────────────────────────────────────────────────────────"
  FOR item IN TO_SKIP:
    Report: "  #{item.task.task_number}: {item.task.title}"
    Report: "    Reason: {item.reason}"
  Report: ""

# Detail: Tasks to tag
IF TO_TAG.length > 0:
  Report: "───────────────────────────────────────────────────────────────"
  Report: "  Tasks to Tag ({TO_TAG.length})"
  Report: "───────────────────────────────────────────────────────────────"
  FOR item IN TO_TAG:
    Report: "  #{item.task.task_number}: {item.task.title}"
    Report: "    Action: {item.action}"
    Report: "    Tags to add: {item.tags_add}"
    IF item.move_to:
      Report: "    Move to: {item.move_to}"
    Report: "    Reason: {item.reason}"
  Report: ""

# Detail: Misplaced tasks
IF MISPLACED.length > 0:
  Report: "───────────────────────────────────────────────────────────────"
  Report: "  Misplaced Tasks ({MISPLACED.length})"
  Report: "───────────────────────────────────────────────────────────────"
  FOR item IN MISPLACED:
    Report: "  #{item.task.task_number}: {item.task.title}"
    Report: "    Current column: {item.current_column}"
    Report: "    Should be in: {item.should_be}"
    Report: "    Reason: {item.reason}"
  Report: ""

# Detail: Incorrect completion tags (recovery)
IF INCORRECT_COMPLETION_TAGS.length > 0:
  Report: "───────────────────────────────────────────────────────────────"
  Report: "  Incorrect Completion Tags ({INCORRECT_COMPLETION_TAGS.length}) - RECOVERY"
  Report: "───────────────────────────────────────────────────────────────"
  Report: ""
  Report: "These tasks have end-stage tags but no evidence of completion."
  Report: "They will be reverted to Development with Planned tag."
  Report: ""
  FOR item IN INCORRECT_COMPLETION_TAGS:
    Report: "  #{item.task.task_number}: {item.task.title}"
    Report: "    Tags to remove: {item.tags_remove.join(', ')}"
    Report: "    Tags to add: {item.tags_add.join(', ')}"
    Report: "    Move to: {item.move_to}"
    Report: "    Reason: {item.reason}"
  Report: ""

# Detail: Needs manual review
IF NEEDS_MANUAL.length > 0:
  Report: "───────────────────────────────────────────────────────────────"
  Report: "  Needs Manual Review ({NEEDS_MANUAL.length})"
  Report: "───────────────────────────────────────────────────────────────"
  FOR item IN NEEDS_MANUAL:
    Report: "  #{item.task.task_number}: {item.task.title}"
    Report: "    Column: {item.column}"
    Report: "    Has plan: {item.has_plan}"
    Report: "    Has completion: {item.has_evidence}"
    Report: "    Reason: {item.reason}"
  Report: ""
```

---

## Step 6: Apply Changes (if --apply)

```typescript
IF "--apply" NOT IN args:
  Report: "───────────────────────────────────────────────────────────────"
  Report: "  DRY RUN - No changes made"
  Report: "───────────────────────────────────────────────────────────────"
  Report: ""
  Report: "Run with --apply flag to make these changes."
  EXIT

Report: "───────────────────────────────────────────────────────────────"
Report: "  Applying Changes"
Report: "───────────────────────────────────────────────────────────────"
Report: ""

success_count = 0
failure_count = 0

# Priority 1: Fix incorrect completion tags (recovery)
FOR item IN INCORRECT_COMPLETION_TAGS:
  task = item.task
  Report: "RECOVERY: #{task.task_number}: {task.title}"

  TRY:
    # Remove incorrect tags
    FOR tag_name IN item.tags_remove:
      IF TAG_CACHE[tag_name]:
        mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE[tag_name])
        Report: "  ✓ Removed tag: {tag_name}"

    # Add correct tags
    FOR tag_name IN item.tags_add:
      IF TAG_CACHE[tag_name]:
        mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE[tag_name])
        Report: "  ✓ Added tag: {tag_name}"

    # Move to correct column
    IF item.move_to AND COLUMN_CACHE[item.move_to]:
      mcp__joan__update_task(task.id, column_id=COLUMN_CACHE[item.move_to])
      Report: "  ✓ Moved to: {item.move_to}"

    # Add audit comment
    comment = "ALS/1
actor: coordinator
intent: recovery
action: revert-incorrect-tagging
tags.add: {item.tags_add}
tags.remove: {item.tags_remove}
summary: Reverted incorrect end-stage tagging.
details:
- issue: Task had end-stage tags (Review-Approved/Ops-Ready) but no completion evidence
- correction: Moved to Development with Planned tag
- next_step: Dev worker will claim and implement this task"

    mcp__joan__create_task_comment(task.id, comment)
    Report: "  ✓ Added audit comment"

    success_count++

  CATCH error:
    Report: "  ✗ Failed: {error.message}"
    failure_count++

Report: ""

# Priority 2: Apply tags to tasks needing workflow integration
FOR item IN TO_TAG:
  task = item.task
  Report: "Processing #{task.task_number}: {task.title}"

  TRY:
    # Add tags
    FOR tag_name IN item.tags_add:
      IF TAG_CACHE[tag_name]:
        mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_CACHE[tag_name])
        Report: "  ✓ Added tag: {tag_name}"

    # Remove tags
    FOR tag_name IN item.tags_remove:
      IF TAG_CACHE[tag_name]:
        mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_CACHE[tag_name])
        Report: "  ✓ Removed tag: {tag_name}"

    # Move to column
    IF item.move_to AND COLUMN_CACHE[item.move_to]:
      mcp__joan__update_task(task.id, column_id=COLUMN_CACHE[item.move_to])
      Report: "  ✓ Moved to: {item.move_to}"

    # Add audit comment
    comment = "ALS/1
actor: coordinator
intent: onboarding
action: backlog-onboarding
tags.add: {item.tags_add}
tags.remove: {item.tags_remove}
summary: Onboarded task to agentic workflow.
details:
- action: {item.action}
- reason: {item.reason}"

    mcp__joan__create_task_comment(task.id, comment)
    Report: "  ✓ Added audit comment"

    success_count++

  CATCH error:
    Report: "  ✗ Failed: {error.message}"
    failure_count++

# Priority 3: Fix misplaced tasks
FOR item IN MISPLACED:
  task = item.task
  Report: "Moving #{task.task_number}: {task.title}"

  TRY:
    mcp__joan__update_task(task.id, column_id=COLUMN_CACHE[item.should_be])
    Report: "  ✓ Moved from {item.current_column} to {item.should_be}"

    # Add audit comment
    comment = "ALS/1
actor: coordinator
intent: recovery
action: column-correction
tags.add: []
tags.remove: []
summary: Corrected column placement.
details:
- from: {item.current_column}
- to: {item.should_be}
- reason: {item.reason}"

    mcp__joan__create_task_comment(task.id, comment)
    success_count++

  CATCH error:
    Report: "  ✗ Failed: {error.message}"
    failure_count++

Report: ""
Report: "───────────────────────────────────────────────────────────────"
Report: "  Summary"
Report: "───────────────────────────────────────────────────────────────"
Report: ""
Report: "Success: {success_count} tasks"
Report: "Failed:  {failure_count} tasks"
Report: "Skipped: {TO_SKIP.length} tasks"
Report: "Needs manual review: {NEEDS_MANUAL.length} tasks"
Report: ""
Report: "═══════════════════════════════════════════════════════════════"
```

---

## Usage

```bash
# Dry run (recommended first)
/agents:clean-project

# Apply changes
/agents:clean-project --apply
```

## When to Use This Command

✅ **Initial setup** - Onboarding existing backlog into agent workflow
✅ **After manual changes** - Fix tasks that were manually moved or tagged in Joan UI
✅ **Recovery from errors** - Fix broken state from previous mistakes
✅ **Periodic maintenance** - Clean up drift that accumulates over time

This is the **primary cleanup command** - use it whenever tasks aren't being processed correctly.
