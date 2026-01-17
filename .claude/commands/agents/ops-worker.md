---
description: Single-pass Ops worker dispatched by coordinator
argument-hint: --task=<task-id> --mode=<merge|rework>
allowed-tools: mcp__joan__*, mcp__github__*, Read, Bash, Grep, Glob
---

# Ops Worker (Single-Pass)

Handle integration operations for a single task, then exit.

## Arguments

- `--task=<ID>` - Task ID to process (REQUIRED)
- `--mode=<merge|rework>` - Processing mode (REQUIRED)
  - `merge`: Task has Review-Approved, merge PR to develop
  - `rework`: Task has Rework-Requested in Review column, move back to Development

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

## Step 1: Fetch and Validate Task

```
1. Fetch task using get_task(TASK_ID)

2. Validate task matches expected mode:

   IF MODE == "merge":
     - Task should be in "Review" column
     - Task should have "Review-Approved" tag

   IF MODE == "rework":
     - Task should be in "Review" column
     - Task should have "Rework-Requested" tag

3. IF validation fails:
   Report: "Task {TASK_ID} not actionable for mode {MODE}"
   EXIT
```

---

## Step 2: Process Task

### Mode: merge (merge approved PR to develop)

```
1. Extract branch name from task description

2. Find the PR for this branch:
   - Use GitHub MCP to list PRs
   - Find PR with head = BRANCH, base = develop

3. Checkout develop and merge:
   git fetch origin
   git checkout develop
   git pull origin develop
   git merge origin/$BRANCH --no-edit

4. IF merge conflicts:
   Go to AI CONFLICT RESOLUTION

5. IF merge clean:
   git push origin develop
   Continue to SUCCESS

--- AI CONFLICT RESOLUTION ---

5a. IF merge conflicts detected:
    For each conflicting file:
    - Read the file with conflict markers
    - Analyze both versions (develop vs feature)
    - Make intelligent resolution preserving intent from both

5b. After resolving all conflicts:
    git add .
    git commit -m "merge: {BRANCH} into develop - resolve conflicts"

5c. Run verification (if test command available):
    npm test 2>/dev/null || pytest 2>/dev/null || true

5d. IF tests fail:
    - Conflict resolution was incorrect
    - Go to CONFLICT FAILURE

5e. IF tests pass (or no tests):
    git push origin develop
    Continue to SUCCESS

--- CONFLICT FAILURE (AI couldn't resolve) ---

6. Reset the failed merge:
   git merge --abort || git reset --hard origin/develop

7. Add failure tags:
   - Add "Merge-Conflict" tag
   - Add "Rework-Requested" tag
   - Add "Planned" tag

8. Remove approval:
   - Remove "Review-Approved" tag

9. Move task to "Development" column

10. Comment (ALS breadcrumb):
    "ALS/1
    actor: ops
    intent: decision
    action: ops-conflict
    tags.add: [Merge-Conflict, Rework-Requested, Planned]
    tags.remove: [Review-Approved]
    summary: Merge failed; manual conflict resolution required.
    details:
    - conflicting files:
      - {file1}
      - {file2}"

11. Report: "Merge FAILED - conflicts too complex for AI"
    EXIT

--- SUCCESS ---

7. Update tags:
   - Remove "Review-Approved" tag

8. Move task to "Deploy" column

9. Close or merge PR via GitHub MCP (if not auto-closed)

10. Comment (ALS breadcrumb):
    "ALS/1
    actor: ops
    intent: status
    action: ops-merge
    tags.add: []
    tags.remove: [Review-Approved]
    summary: Merged to develop; task moved to Deploy.
    details:
    - {IF conflicts were resolved} AI-assisted conflict resolution applied."

11. Report: "Merged to develop successfully"
```

### Mode: rework (move rejected task back)

```
This handles an edge case where Reviewer rejected but task stayed in Review.

1. Verify tags:
   - Should have "Rework-Requested"
   - Should have "Planned" (if not, add it)

2. Move task to "Development" column

3. Comment (ALS breadcrumb):
   "ALS/1
   actor: ops
   intent: status
   action: ops-rework
   tags.add: [Rework-Requested, Planned]
   tags.remove: []
   summary: Returned to Development for rework."

4. Report: "Task moved back to Development"
```

---

## Step 3: Exit

```
Report completion summary:
"Ops Worker complete:
- Task: {title}
- Mode: {MODE}
- Result: {Merged | Conflict Failed | Moved to Development}"

EXIT
```

---

## AI Conflict Resolution Guidelines

When resolving conflicts:

1. **Preserve Intent**: Both branches had reasons for their changes
2. **Feature Additions**: If feature branch adds code, keep it
3. **Develop Fixes**: If develop has bug fixes, keep them
4. **Schema Changes**: Be careful with migrations, configs - may need both
5. **Test Both**: Always verify resolution doesn't break anything

Conflict markers look like:
```
<<<<<<< HEAD
develop version
=======
feature version
>>>>>>> feature/branch
```

Resolution approaches:
- **Keep Both**: If changes are additive (e.g., new functions)
- **Keep One**: If changes are mutually exclusive
- **Merge Logic**: If changes affect the same code but can be combined

---

## Constraints

- Single task only - process and exit
- Never force push
- Always attempt AI resolution before failing back
- Merge to develop only (never main/master)
- Store conflict details in task description for manual resolution

Begin processing task: $TASK_ID with mode: $MODE
