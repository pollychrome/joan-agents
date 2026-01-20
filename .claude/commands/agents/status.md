---
description: Show current status of Joan agents, queues, and active workers
allowed-tools: mcp__joan__*, Read, Bash
---

# Agents Status Dashboard

Display a comprehensive status view of the Joan multi-agent system.

## Configuration

Load from `.joan-agents.json`:
```
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName
DEV_COUNT = config.agents.devs.count
```

If config missing, report error and exit.

## Step 1: Gather Data

```
1. Fetch all tasks for project:
   tasks = list_tasks(project_id=PROJECT_ID)

2. Fetch all project tags:
   tags = list_project_tags(PROJECT_ID)
   Build TAG_MAP: tag_id -> tag_name

3. For each task, resolve tag names from IDs

4. Check scheduler/coordinator status:
   PROJECT_SLUG = PROJECT_NAME.toLowerCase().replace(/[^a-z0-9]+/g, '-')
   HEARTBEAT_FILE = /tmp/joan-agents-{PROJECT_SLUG}.heartbeat
   PID_FILE = /tmp/joan-agents-{PROJECT_SLUG}.pid
   SHUTDOWN_FILE = /tmp/joan-agents-{PROJECT_SLUG}.shutdown

   Check if HEARTBEAT_FILE exists:
     - If exists, read timestamp and calculate age
     - If age < 60 seconds: SCHEDULER_STATUS = "Active (heartbeat {age}s ago)"
     - If age < 600 seconds: SCHEDULER_STATUS = "Running (heartbeat {age}s ago)"
     - If age >= 600 seconds: SCHEDULER_STATUS = "Possibly stuck (heartbeat {age}s ago)"
   - If not exists: SCHEDULER_STATUS = "Not running"

   Check if SHUTDOWN_FILE exists:
     - If exists: SHUTDOWN_PENDING = true
```

## Step 2: Categorize Tasks

Build counts and lists by column and state:

```
TO_DO = tasks in "To Do" column
ANALYSE = tasks in "Analyse" column
  - needs_clarification: has Needs-Clarification tag
  - clarification_answered: has Clarification-Answered tag
  - ready: has Ready tag
  - plan_pending: has Plan-Pending-Approval tag
  - plan_approved: has Plan-Approved tag
  - plan_rejected: has Plan-Rejected tag

DEVELOPMENT = tasks in "Development" column
  - planned: has Planned, no Claimed-Dev-*
  - claimed: has Claimed-Dev-* tag (note which dev)
  - rework: has Rework-Requested tag
  - conflict: has Merge-Conflict tag
  - failed: has Implementation-Failed or Worktree-Failed

REVIEW = tasks in "Review" column
  - awaiting_review: has completion tags, no Review-In-Progress
  - in_progress: has Review-In-Progress tag
  - approved: has Review-Approved tag
  - ops_ready: has Review-Approved AND Ops-Ready tags

DEPLOY = tasks in "Deploy" column

DONE = tasks in "Done" column (count only, last 5)
```

## Step 3: Identify Active Workers

From task tags, infer active workers:

```
ACTIVE_WORKERS = []

For each task:
  IF has "Claimed-Dev-N" tag:
    ACTIVE_WORKERS.push({type: "Dev", id: N, task: title, column: "Development"})

  IF has "Review-In-Progress" tag:
    ACTIVE_WORKERS.push({type: "Reviewer", task: title, column: "Review"})
```

## Step 4: Identify Blocked/Waiting Items

```
WAITING_HUMAN = []

For each task:
  IF has Plan-Pending-Approval AND NOT Plan-Approved:
    WAITING_HUMAN.push({task: title, waiting: "Plan approval"})

  IF has Review-Approved AND NOT Ops-Ready:
    WAITING_HUMAN.push({task: title, waiting: "Merge approval (Ops-Ready tag)"})

  IF has Needs-Clarification AND NOT Clarification-Answered:
    WAITING_HUMAN.push({task: title, waiting: "Clarification"})

  IF has Implementation-Failed OR Worktree-Failed:
    WAITING_HUMAN.push({task: title, waiting: "Manual intervention"})
```

## Step 5: Render Dashboard

Output the following format:

```
═══════════════════════════════════════════════════════════════
  JOAN AGENTS STATUS - {PROJECT_NAME}
═══════════════════════════════════════════════════════════════

  SCHEDULER STATUS
  ─────────────────────────────────────────────────────────────
  {SCHEDULER_STATUS}
  {IF SHUTDOWN_PENDING}  ⚠ Shutdown pending (will stop after current cycle){END IF}
  ─────────────────────────────────────────────────────────────

  PIPELINE OVERVIEW
  ─────────────────────────────────────────────────────────────
  To Do        [{TO_DO.length}] ████░░░░░░
  Analyse      [{ANALYSE.length}] ██████░░░░  ({ready} ready, {plan_pending} pending)
  Development  [{DEVELOPMENT.length}] ████████░░  ({claimed} active, {planned} queued)
  Review       [{REVIEW.length}] ██░░░░░░░░  ({approved} approved)
  Deploy       [{DEPLOY.length}] ░░░░░░░░░░
  Done         [{DONE.length}]
  ─────────────────────────────────────────────────────────────

  ACTIVE WORKERS
  ─────────────────────────────────────────────────────────────
  {IF ACTIVE_WORKERS.length > 0}
    {FOR worker IN ACTIVE_WORKERS}
      [{worker.type}] {worker.task}
    {END FOR}
  {ELSE}
    No workers currently active
  {END IF}
  ─────────────────────────────────────────────────────────────

  WORK QUEUES
  ─────────────────────────────────────────────────────────────
  BA Queue:        {TO_DO.length + clarification_answered count} tasks
  Architect Queue: {ready count + plan_approved count + plan_rejected count} tasks
  Dev Queue:       {planned count + rework count + conflict count} tasks
  Reviewer Queue:  {awaiting_review count} tasks
  Ops Queue:       {ops_ready count} tasks
  ─────────────────────────────────────────────────────────────

  AWAITING HUMAN ACTION
  ─────────────────────────────────────────────────────────────
  {IF WAITING_HUMAN.length > 0}
    {FOR item IN WAITING_HUMAN}
      ! {item.task}
        -> {item.waiting}
    {END FOR}
  {ELSE}
    No tasks waiting for human action
  {END IF}
  ─────────────────────────────────────────────────────────────

  DEVELOPMENT DETAILS
  ─────────────────────────────────────────────────────────────
  {FOR task IN DEVELOPMENT}
    [{task.state}] {task.title}
      {IF claimed} Claimed by Dev-{N} {END IF}
      {IF rework} Needs rework {END IF}
      {IF conflict} Has merge conflict {END IF}
      {IF failed} FAILED - needs manual fix {END IF}
  {END FOR}
  ─────────────────────────────────────────────────────────────

  RECENTLY COMPLETED (last 5)
  ─────────────────────────────────────────────────────────────
  {FOR task IN DONE.slice(0,5)}
    - {task.title}
  {END FOR}
  ─────────────────────────────────────────────────────────────

═══════════════════════════════════════════════════════════════
  /agents:scheduler (long-running) | /agents:dispatch --loop (interactive)
  /agents:status to refresh
═══════════════════════════════════════════════════════════════
```

## Output Guidelines

- Use box-drawing characters for visual structure
- Keep task titles truncated to ~40 chars if needed
- Show counts prominently
- Highlight items needing human action with `!` prefix
- Use clear state labels: [Planned], [Claimed], [Rework], [Failed]

## Constraints

- Read-only: never modify tasks
- Fast: minimize API calls
- Clear: prioritize actionable information
