---
description: Single-pass Architect worker dispatched by coordinator
argument-hint: --task=<task-id> --mode=<plan|finalize>
allowed-tools: mcp__joan__*, Read, Write, Grep, Glob, View
---

# Architect Worker (Single-Pass)

Process a single task assigned by the coordinator, then exit.

## Arguments

- `--task=<ID>` - Task ID to process (REQUIRED)
- `--mode=<plan|finalize>` - Processing mode (REQUIRED)
  - `plan`: Task has Ready tag, create implementation plan
  - `finalize`: Task has Plan-Approved tag, inject sub-tasks and move to Development

## Configuration

Load from `.joan-agents.json`:
```
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName
```

If config missing, report error and exit.

Parse arguments:
```
TASK_ID = value from --task
MODE = value from --mode
```

If either argument missing, report error and exit.

---

## Step 1: Fetch Task

```
1. Fetch task using get_task(TASK_ID)

2. Validate task is actionable:

   IF MODE == "plan":
     - Task should be in "Analyse" column
     - Task should have "Ready" tag
     - Task should NOT have "Plan-Pending-Approval" tag

   IF MODE == "finalize":
     - Task should be in "Analyse" column
     - Task should have "Plan-Pending-Approval" tag
     - Task should have "Plan-Approved" tag

3. IF validation fails:
   Report: "Task {TASK_ID} not actionable for mode {MODE}"
   EXIT
```

---

## Step 2: Process Task

### Mode: plan (create implementation plan)

```
1. Analyze the codebase:
   - Read CLAUDE.md for project conventions
   - Explore relevant directories
   - Understand architecture patterns
   - Identify files that will need modification

2. Create plan document with this structure:

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

   ## Branch Name
   `feature/{task-title-kebab-case}`

   ## Execution Notes
   {Special instructions for devs}

3. Attach plan to task:
   - Use upload_attachment with the plan content
   - Filename: plan-{task-id}.md

4. Update tags:
   - Remove "Ready" tag
   - Add "Plan-Pending-Approval" tag

5. Comment (ALS breadcrumb):
   "ALS/1
   actor: architect
   intent: request
   action: plan-ready
   tags.add: [Plan-Pending-Approval]
   tags.remove: [Ready]
   summary: Plan attached; add Plan-Approved to proceed.
   details:
   - Plan includes {N} sub-tasks across Design, Development, and Testing.
   links:
   - plan: plan-{task-id}.md"

6. Report: "Plan created for '{title}', awaiting approval"
```

### Mode: finalize (plan approved, move to Development)

```
1. Retrieve the plan attachment:
   - List attachments for task
   - Find plan-{task-id}.md
   - Download/read the plan content

2. Extract sub-tasks from plan:
   - Parse the Design, Development, and Testing sections
   - Build the sub-task list

3. Update task description:
   - Append sub-tasks to the end of the description:

   ---

   ## Implementation Plan

   ### Design
   - [ ] DES-1: {task}

   ### Development
   - [ ] DEV-1: {task}
   - [ ] DEV-2: {task}

   ### Testing
   - [ ] TEST-1: {task}

   **Branch:** `feature/{branch-name}`

4. Update tags:
   - Remove "Plan-Pending-Approval" tag
   - Remove "Plan-Approved" tag
   - Add "Planned" tag

5. Move task to "Development" column

6. Comment (ALS breadcrumb):
   "ALS/1
   actor: architect
   intent: decision
   action: plan-approved
   tags.add: [Planned]
   tags.remove: [Plan-Pending-Approval, Plan-Approved]
   summary: Plan approved; moved to Development.
   details:
   - Branch: feature/{branch-name}
   - Sub-tasks: {N} total ({DES} design, {DEV} development, {TEST} testing)"

7. Report: "Plan finalized for '{title}', moved to Development"
```

---

## Step 3: Exit

```
Report completion summary:
"Architect Worker complete:
- Task: {title}
- Mode: {MODE}
- Result: {Plan Created | Plan Finalized}"

EXIT
```

---

## Plan Guidelines

When creating plans:
- **Atomic**: Each sub-task should be completable independently
- **Ordered**: Respect dependencies (DES first, then DEV, then TEST)
- **Testable**: Each sub-task should have verifiable completion criteria
- **Scoped**: Don't add features beyond the task requirements

Branch naming:
- Use kebab-case: `feature/add-user-authentication`
- Keep it descriptive but concise
- Must be valid git branch name

## Constraints

- Never implement code (only plan it)
- Always attach plan as file (for reference)
- Always inject sub-tasks into description when finalizing
- Single task only - process and exit

Begin processing task: $TASK_ID with mode: $MODE
