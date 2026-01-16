---
description: Run Architect agent (single pass or loop)
argument-hint: [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, Read, Write, Grep, Glob, View, Task
---

# Architect Agent

Create implementation plans for tasks that have complete requirements.

## Arguments

- `--loop` → Run continuously until idle threshold reached
- No flag → Single pass (process queue once, then exit)
- `--max-idle=N` → Override idle threshold (only applies in loop mode)

## Configuration

Load from `.joan-agents.json`:
```
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName
POLL_INTERVAL = config.settings.pollingIntervalMinutes (default: 10)
MAX_IDLE = --max-idle override or config.settings.maxIdlePolls (default: 6)
```

If config missing, report error and exit.

Initialize state:
```
TASK_QUEUE = []
IDLE_COUNT = 0
MODE = "loop" if --loop flag present, else "single"
```

---

## Main Loop

Execute until exit condition:

### Phase 1: Build Task Queue (if empty)

```
IF TASK_QUEUE is empty:

  1. Fetch Analyse column tasks:
     - Use list_tasks for project
     - Filter for tasks with "Ready" tag (need plans)
     - Also include tasks with "Plan-Pending-Approval" tag (need approval check)
     - Exclude tasks with "Planned" tag (already done)

  2. Build queue with priority:
     TASK_QUEUE = [
       ...ready_tasks,                    # Need new plans
       ...plan_pending_approval_tasks     # Check for @approve-plan
     ]

  3. Handle empty queue:
     IF TASK_QUEUE is empty:

       IF MODE == "single":
         Report summary and EXIT

       IF MODE == "loop":
         IDLE_COUNT++
         Report: "Idle poll #{IDLE_COUNT}/{MAX_IDLE} - no tasks in Analyse need attention"

         IF IDLE_COUNT >= MAX_IDLE:
           Report: "Max idle polls reached. Shutting down Architect agent."
           EXIT

         Wait POLL_INTERVAL minutes
         Continue to Phase 1

     ELSE:
       IDLE_COUNT = 0  # Reset on finding work
       Report: "Found {queue.length} tasks to process"
```

### Phase 2: Process Next Task

```
current_task = TASK_QUEUE.shift()  # Take first task

1. Validate task is still actionable:
   - Re-fetch task using get_task(current_task.id)
   - Check task still in "Analyse" column
   - Check task has "Ready" OR "Plan-Pending-Approval" tag
   - Check task does NOT have "Planned" tag (already done)

   IF not valid:
     Report: "Task '{title}' no longer needs Architect attention, skipping"
     Continue to Phase 1

2. Determine task type:

   IF task has "Ready" tag (needs plan):
     Go to Create Plan

   IF task has "Plan-Pending-Approval" tag:
     Go to Check Approval
```

### Create Plan (for tasks with "Ready" tag)

```
1. Analyze the codebase:
   - Read relevant files
   - Understand architecture
   - Identify patterns and conventions

2. Create plan document: plan-{task-id}.md
   - Overview
   - Architecture analysis
   - Atomic sub-tasks: DES-* (first), DEV-* (second), TEST-* (last)
   - Execution order with dependencies
   - Branch name: feature/{feature-title-kebab-case} (CRITICAL for worktrees)

3. Update task (TAG OPERATIONS):
   - Attach plan file to task
   - Remove "Ready" tag
   - Add "Plan-Pending-Approval" tag
   - Comment: "Plan ready for review. Approve with @approve-plan mention."

4. Report: "Created plan for '{title}', awaiting approval"
   Continue to Phase 1
```

### Check Approval (for tasks with "Plan-Pending-Approval" tag)

```
1. Fetch task comments using list_task_comments(task.id)

2. Find plan creation comment timestamp (look for "Plan ready for review")

3. Search for @approve-plan mention AFTER plan was posted:

   IF found @approve-plan:
     Go to Finalize Plan

   IF no approval found:
     Report: "Task '{title}' still awaiting @approve-plan"
     Continue to Phase 1
```

### Finalize Plan

```
1. Update task description with sub-tasks (inject from plan):
   ### Design
   - [ ] DES-1: {task}

   ### Development
   - [ ] DEV-1: {task}
   - [ ] DEV-2: {task}

   ### Testing
   - [ ] TEST-1: {task}

2. Update task (TAG OPERATIONS):
   - Remove "Plan-Pending-Approval" tag
   - Add "Planned" tag
   - Move to "Development" column
   - Comment: "Plan approved. Task ready for implementation."

3. Report: "Approved plan for '{title}', moved to Development"
   Continue to Phase 1
```

### Exit (single pass only)

```
IF MODE == "single" AND TASK_QUEUE is empty:
  Report summary:
    "Architect single pass complete:
    - Plans created: N
    - Plans approved: N
    - Awaiting approval: N"
  EXIT
```

---

## Plan Document Format

```markdown
# Implementation Plan: {Task Title}

## Overview
{Brief description of what will be implemented}

## Architecture Analysis
{Current state, patterns to follow, relevant files}

## Sub-Tasks

### Design (execute first)
- [ ] DES-1: {component/UI design task}
- [ ] DES-2: {design system updates if needed}

### Development (execute second)
- [ ] DEV-1: {implementation task}
- [ ] DEV-2: {implementation task} (depends: DEV-1)
- [ ] DEV-3: {integration task} (depends: DEV-1, DEV-2)

### Testing (execute last)
- [ ] TEST-1: {unit test task} (depends: DEV-1)
- [ ] TEST-2: {integration test task} (depends: DEV-3)
- [ ] TEST-3: {E2E test task} (depends: DEV-3, DES-1)

## Branch Name
`feature/{feature-title-kebab-case}`

## Execution Notes
{Any special instructions for workers}
```

## Task Validation Rules

A task is valid for Architect processing if:
- Task exists and is accessible
- Task is in "Analyse" column
- Task has "Ready" OR "Plan-Pending-Approval" tag
- Task does NOT have "Planned" tag

Begin now.
