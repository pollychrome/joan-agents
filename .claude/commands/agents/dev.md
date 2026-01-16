---
description: Run Dev agent (single task or loop)
argument-hint: [dev-id] [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, mcp__github__*, Read, Write, Edit, Bash, Grep, Glob, Task, View, computer
---

# Dev Agent

Quick invocation of a Dev agent for feature implementation.

## Arguments

- `$1` = Dev ID (default: 1)
- `--loop` → Run continuously (use dev-loop behavior)
- No flag → Single task (claim one task, complete it, exit)
- `--max-idle=N` → Override idle threshold (only for loop mode)

## Configuration

Load from `.joan-agents.json`:
- PROJECT_ID = config.projectId
- PROJECT_NAME = config.projectName
- DEV_ID = $1 or 1
- CLAIM_TAG = "Claimed-Dev-{DEV_ID}"

If config missing, report error and exit.

## Single Task Mode (default)

### Step 1: Find Available Task

Find one available task (priority order):
1. **Rework tasks** (Priority 1): Has "Rework-Requested" OR "Merge-Conflict" tag
2. **New tasks** (Priority 2): Has "Planned" tag, no "Claimed-Dev-*" tags

Filter out tasks with "Implementation-Failed" or "Worktree-Failed" tags.

If no tasks available:
```
Dev #{DEV_ID}: No tasks available.
```
Exit.

### Step 2: Claim Task (Atomic)

```
1. Add tag: CLAIM_TAG ("Claimed-Dev-{DEV_ID}")
2. Wait 1 second (allow for race conditions)
3. Re-fetch task and verify:
   - YOUR claim tag is present
   - NO OTHER "Claimed-Dev-*" tags exist
4. If claim failed: remove your tag, exit with "Another dev claimed this task"
```

### Step 3: Parse Rework Instructions (if rework task)

If task has "Rework-Requested" or "Merge-Conflict" tag:
```
1. Fetch task comments using list_task_comments(task_id)
2. Find most recent @rework comment
3. Extract rework instructions
4. If "Merge-Conflict" tag: focus on resolving conflicts with develop
```

### Step 4: Setup Worktree & Implement

```
1. Get branch name from plan (format: feature/{title-kebab-case})
2. Create worktree: git worktree add "../worktrees/{task-id}" "{branch}"
3. Enter worktree and install dependencies
4. If rework: address specific feedback only
   If new task: execute sub-tasks in order (DES-*, DEV-*, TEST-*)
5. Commit changes with appropriate messages
```

### Step 5: Create PR & Cleanup (CRITICAL TAG OPERATIONS)

```
1. Push branch:
   git push origin "$BRANCH"

2. Handle PR:
   - If rework: PR exists, just push updates
   - If new: Create PR via GitHub MCP

3. Cleanup worktree:
   cd "$PROJECT_ROOT"
   git worktree remove "../worktrees/{task-id}" --force
   git worktree prune

4. Update task tags (MUST DO ALL):
   - Remove: CLAIM_TAG ("Claimed-Dev-{DEV_ID}")
   - Remove: "Planned"
   - Remove: "Rework-Requested" (if present)
   - Remove: "Merge-Conflict" (if present)
   - Add: "Dev-Complete"
   - Add: "Design-Complete"
   - Add: "Test-Complete"

5. Move task to "Review" column (use sync_column: false)

6. Comment on task:
   - If was merge conflict:
     "## rework-complete\n\nMerge conflicts resolved."
   - If was rework:
     "## rework-complete\n\nAddressed reviewer feedback:\n- {summary}\n\nReady for re-review."
   - If new task:
     "Implementation complete. PR: {link}"
```

**Note**: The `## rework-complete` header is REQUIRED for rework tasks - it signals the Reviewer that this task is ready for another review cycle.

### Step 6: Report and Exit

```
Dev #{DEV_ID} completed: '{task title}'
- Type: {NEW | REWORK | MERGE_CONFLICT}
- PR: {url}
```

## Loop Mode (--loop)

Invoke the full dev-loop with configuration from .joan-agents.json.

Begin Dev #{DEV_ID} now.
