---
description: Run Architect agent (single pass or loop)
argument-hint: [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, Read, Write, Grep, Glob, View, Task
---

# Architect Agent

Quick invocation of the Architect agent.

## Mode Selection

Parse arguments:
- `--loop` → Run continuously (use architect-loop behavior)
- No flag → Single pass (process queue once, then exit)
- `--max-idle=N` → Override idle threshold (only for loop mode)

## Configuration

Load from `.joan-agents.json`:
- PROJECT_ID = config.projectId
- PROJECT_NAME = config.projectName

If config missing, report error and exit.

## Single Pass Mode (default)

### Step 1: Fetch Actionable Tasks

Fetch all tasks in Analyse column:
- Tasks with "Ready" tag (need plans)
- Tasks with "Plan-Pending-Approval" tag (check for @approve-plan)

Filter out tasks that already have "Planned" tag.

### Step 2: Process Each Task

For each task, validate it's still actionable, then:

#### If task has "Ready" tag → Create Plan

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
```

#### If task has "Plan-Pending-Approval" tag → Check for Approval

```
1. Fetch task comments using list_task_comments(task.id)

2. Find plan creation comment timestamp (look for "Plan ready for review")

3. Search for @approve-plan mention AFTER plan was posted:
   - If found: Plan is approved → Go to Finalize
   - If not found: Report "Task '{title}' still awaiting @approve-plan", skip
```

#### Finalize Approved Plan

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
```

### Step 3: Report Summary and Exit

```
Architect single pass complete:
- Plans created: N
- Plans approved: N
- Awaiting approval: N
```

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

## Loop Mode (--loop)

Invoke the full architect-loop with configuration from .joan-agents.json.

Begin now.
