---
description: Onboard existing project backlogs to the agentic workflow
argument-hint: [--apply]
allowed-tools: mcp__joan__*, Read
---

# Onboard Existing Backlog to Agent Workflow

This command prepares existing tasks for the Joan multi-agent system by adding appropriate workflow tags based on their current column position.

## Prerequisites

**Step 1: Check for configuration**

Read `.joan-agents.json` from the project root:

```
Read .joan-agents.json
```

If the file does not exist, exit with:
```
Error: No Joan agent configuration found.

Run /agents:init first to configure your project for the agent workflow.
```

Extract `projectId` from the configuration.

**Step 2: Verify workflow tags exist**

```
tags = mcp__joan__list_project_tags(project_id)
```

Check that the required workflow tags exist. If any are missing, exit with:
```
Error: Missing workflow tags in project.

Run /agents:init to create the required workflow tags.
```

## Mode Detection

Check if `--apply` flag is present in the arguments:
- **Without `--apply`**: Preview mode (default) - show what would change without making changes
- **With `--apply`**: Apply mode - actually make the changes

## Workflow Tags (Skip Detection)

Tasks that already have ANY of these tags should be **skipped** (already in workflow):

```
Ready, Needs-Clarification, Clarification-Answered, Plan-Pending-Approval,
Plan-Approved, Plan-Rejected, Planned, Dev-Complete, Design-Complete,
Test-Complete, Review-In-Progress, Review-Approved, Rework-Requested,
Rework-Complete, Merge-Conflict, Implementation-Failed, Worktree-Failed,
Ops-Ready
```

Also skip any task with a `Claimed-Dev-*` tag pattern (e.g., Claimed-Dev-1, Claimed-Dev-2).

## Tagging Logic by Column

| Column | Action | Tags to Add | Column Move |
|--------|--------|-------------|-------------|
| **To Do** | Skip | None | None |
| **Analyse** | Add tag | Ready | None |
| **Development** | Move + tag | Ready | Move to Analyse |
| **Review** | Add tags | Dev-Complete, Design-Complete, Test-Complete | None |
| **Deploy** | Add tags | Review-Approved, Ops-Ready | None |
| **Done** | Skip | None | None |

## Processing Steps

**Step 1: Build tag ID cache**

Create a map of tag names to tag IDs from the project tags list:
```
tagCache = {
  "Ready": "uuid-for-ready",
  "Dev-Complete": "uuid-for-dev-complete",
  ...
}
```

**Step 2: Fetch columns and tasks**

```
columns = mcp__joan__list_columns(project_id)
tasks = mcp__joan__list_tasks(project_id)
```

Build a map of column IDs to column names for easy lookup.

**Step 3: Process each task**

For each task:
1. Get the task's current column name
2. Get the task's current tags
3. Check if task has any workflow tags → if yes, skip
4. Determine required action based on column
5. In preview mode: record the planned change
6. In apply mode: execute the change

**Step 4: Execute changes (apply mode only)**

For tasks needing tags:
```
mcp__joan__add_tag_to_task(project_id, task_id, tag_id)
```

For tasks needing column move (Development → Analyse):
```
# First get the Analyse column ID
analyse_column_id = columns.find(c => c.name == "Analyse").id

# Move the task
mcp__joan__update_task(task_id, { column_id: analyse_column_id })

# Then add the Ready tag
mcp__joan__add_tag_to_task(project_id, task_id, tagCache["Ready"])
```

## Output Format

### Preview Mode (default)

```
═══════════════════════════════════════════════════════════════
  Backlog Onboarding Preview
═══════════════════════════════════════════════════════════════

Project: {project_name}
Mode: DRY RUN (no changes will be made)

Tasks to Update:
───────────────────────────────────────────────────────────────
  Analyse (2 tasks):
    • "Task Title 1" → Add: Ready
    • "Task Title 2" → Add: Ready

  Development (3 tasks):
    • "Task Title 3" → Move to Analyse, Add: Ready
    • "Task Title 4" → Move to Analyse, Add: Ready
    • "Task Title 5" → Move to Analyse, Add: Ready

  Review (1 task):
    • "Task Title 6" → Add: Dev-Complete, Design-Complete, Test-Complete

  Deploy (1 task):
    • "Task Title 7" → Add: Review-Approved, Ops-Ready

Skipped (already in workflow): 4 tasks
Skipped (To Do / Done): 2 tasks

───────────────────────────────────────────────────────────────
Summary: 7 tasks would be updated

To apply these changes, run:
  /agents:clean-project --apply
═══════════════════════════════════════════════════════════════
```

### Apply Mode

```
═══════════════════════════════════════════════════════════════
  Backlog Onboarding Complete
═══════════════════════════════════════════════════════════════

Project: {project_name}

Results:
───────────────────────────────────────────────────────────────
  Updated: 7 tasks
    Analyse: 2 (added Ready)
    Development → Analyse: 3 (moved + added Ready)
    Review: 1 (added completion tags)
    Deploy: 1 (added Review-Approved, Ops-Ready)

  Skipped: 6 tasks
    Already in workflow: 4
    In To Do / Done: 2

  Failed: 0 tasks
───────────────────────────────────────────────────────────────

Your backlog is now ready for the agent workflow.
Start agents with: /agents:start --loop
═══════════════════════════════════════════════════════════════
```

### No Changes Needed

```
═══════════════════════════════════════════════════════════════
  Backlog Onboarding Check
═══════════════════════════════════════════════════════════════

Project: {project_name}

No changes needed - all tasks are already in the workflow
or in To Do / Done columns.

Total tasks: 15
  In workflow: 10
  To Do: 3
  Done: 2
═══════════════════════════════════════════════════════════════
```

## Error Handling

If any task update fails in apply mode:
1. Continue processing remaining tasks
2. Track failed task IDs and error messages
3. Report failures in the final summary:

```
Failed: 2 tasks
  • "Task Title" - Error: Could not add tag (permission denied)
  • "Other Task" - Error: Task not found
```

## Idempotency

This command is idempotent - running it multiple times produces the same result:
- Tasks already tagged are skipped
- Tasks already moved stay in place
- Running after apply shows "No changes needed"

Begin processing now.
