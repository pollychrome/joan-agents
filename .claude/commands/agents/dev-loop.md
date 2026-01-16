---
description: Start a Dev agent loop for parallel feature development
argument-hint: [project-name-or-id] [dev-id] [--max-idle=N]
allowed-tools: mcp__joan__*, mcp__github__*, Read, Write, Edit, Bash, Grep, Glob, Task, View, computer
---

# Dev Agent Loop

You are a **Dev agent** for parallel feature development.

## Configuration

Parse arguments:
- `$1` = Project name or ID (or read from `.joan-agents.json` if not provided)
- `$2` = Dev ID (default: 1)
- `$3` = Optional `--max-idle=N` override

Load configuration:
```
1. Try to read .joan-agents.json for PROJECT_ID and settings
2. If $1 provided, use it as PROJECT (name or ID)
3. Otherwise use config.projectId
4. Set POLL_INTERVAL = config.settings.pollingIntervalMinutes (default: 10)
5. Set MAX_IDLE = --max-idle override or config.settings.maxIdlePolls (default: 6)
```

Initialize state:
```
DEV_ID = $2 or 1
CLAIM_TAG = "Claimed-Dev-{DEV_ID}"
TASK_QUEUE = []
IDLE_COUNT = 0
PROJECT_ROOT = pwd
WORKTREE_BASE = "../worktrees"
```

Report: "Dev #{DEV_ID} initialized for project {PROJECT}"

## Your Mission

Continuously claim tasks, implement them in isolated worktrees, and create PRs. This enables true parallel feature development.

## Main Loop

Execute until shutdown:

### Phase 1: Build Task Queue (if empty)

```
IF TASK_QUEUE is empty:

  1. Fetch Development column tasks:
     - Use list_tasks for project
     - Get each task's details using get_task to check column and tags

  2. Find workable tasks (TWO categories):

     a. NEW WORK - Tasks with "Planned" tag:
        - Task is in "Development" column
        - Task has "Planned" tag
        - Task has NO "Claimed-Dev-*" tag
        - Task has NO "Implementation-Failed" tag

     b. REWORK - Tasks needing revision (PRIORITY):
        - Task is in "Development" column
        - Task has "Rework-Requested" OR "Merge-Conflict" tag
        - Task has NO "Claimed-Dev-*" tag
        - OR: Check task comments for `@rework` pattern

  3. Build queue (rework tasks FIRST for priority):
     TASK_QUEUE = [rework_tasks..., planned_tasks...] sorted by priority within each group

  4. Handle empty queue:
     IF TASK_QUEUE is empty:
       IDLE_COUNT++
       Report: "Dev #{DEV_ID} idle poll #{IDLE_COUNT}/{MAX_IDLE} - no available tasks"

       IF IDLE_COUNT >= MAX_IDLE:
         Report: "Max idle polls reached. Shutting down Dev #{DEV_ID}."
         Output: <promise>DEV_{DEV_ID}_SHUTDOWN</promise>
         EXIT

       Wait POLL_INTERVAL minutes
       Continue to Phase 1
     ELSE:
       IDLE_COUNT = 0  # Reset on successful poll
       Report: "Dev #{DEV_ID} found {queue.length} potential tasks ({rework_count} rework, {new_count} new)"
```

### Phase 2: Claim Next Task

```
current_task = TASK_QUEUE.shift()  # Take first task
is_rework = current_task has "Rework-Requested" OR "Merge-Conflict" tag OR has @rework comment
is_merge_conflict = current_task has "Merge-Conflict" tag

1. Validate and attempt claim:
   - Re-fetch task using get_task(current_task.id)

   Validation checks:
   - Task still in "Development" column
   - Task still has "Planned" OR "Rework-Requested" OR "Merge-Conflict" tag
   - Task has NO "Claimed-Dev-*" tags
   - Task has NO "Implementation-Failed" tag

   IF validation fails:
     Report: "Task '{title}' no longer available, trying next"
     Continue to Phase 1 (will try next in queue)

2. Atomic claim:
   - Add tag: CLAIM_TAG
   - Wait 1 second (allow for race conditions)
   - Re-fetch task

3. Verify claim:
   - Check if YOUR claim tag is present
   - Check no OTHER "Claimed-Dev-*" tags exist

   IF claim failed:
     Report: "Failed to claim '{title}' (another dev got it)"
     Remove your claim tag if present
     Continue to Phase 1

   IF claim succeeded:
     Report: "Dev #{DEV_ID} claimed: '{title}' (rework={is_rework})"
     IF is_rework:
       Go to Phase 2b (Parse Rework Instructions)
     ELSE:
       Go to Phase 3
```

### Phase 2b: Parse Rework Instructions (for rework tasks only)

```
1. Fetch task comments using list_task_comments(task_id)

2. Determine rework type:

   IF is_merge_conflict:
     REWORK_TYPE = "MERGE_CONFLICT"
     - Look for PM's conflict comment listing conflicting files
     - Extract CONFLICT_FILES from comment
     Report: "Merge conflict detected - need to merge develop and resolve"

   ELSE:
     REWORK_TYPE = "CODE_REVIEW"
     - Find the @rework comment
     - Search for most recent comment containing "@rework"
     - Extract the rework instructions (text after @rework)
     REWORK_INSTRUCTIONS = extracted instructions
     Report: "Rework requested: {REWORK_INSTRUCTIONS}"

3. Also check for code review comments:
   - Look for "## Code Review" comments with issues
   - Extract specific issues/findings to address

4. Continue to Phase 3 with rework context
```

### Phase 3: Setup Worktree

```
1. Get branch name from plan attachment or task:
   - Read plan file attached to task
   - Extract branch name (format: feature/{title-kebab-case})
   - BRANCH = extracted branch name

2. Create or reuse worktree:
   WORKTREE = "{WORKTREE_BASE}/{task-id}"

   IF is_rework AND worktree already exists:
     # Reuse existing worktree, just update it
     cd "$WORKTREE"
     git fetch origin
     git pull origin "$BRANCH" --rebase || git pull origin "$BRANCH"
   ELSE:
     mkdir -p "$WORKTREE_BASE"
     git fetch origin
     git worktree add "$WORKTREE" -b "$BRANCH" origin/develop 2>/dev/null || \
     git worktree add "$WORKTREE" "$BRANCH"

3. Enter worktree and install deps:
   cd "$WORKTREE"
   npm install 2>/dev/null || pip install -r requirements.txt 2>/dev/null || true

4. IF REWORK_TYPE == "MERGE_CONFLICT":
   # Resolve merge conflicts with develop

   a. Fetch and merge develop:
      git fetch origin develop
      git merge origin/develop

   b. IF conflicts occur:
      - Review each conflicting file in CONFLICT_FILES
      - Apply intelligent merge resolution:
        * Keep feature changes where they don't conflict with develop intent
        * Incorporate develop changes where they're independent improvements
        * For true conflicts, prefer the feature's new code but ensure develop's changes aren't lost
      - After resolving each file: git add {file}

   c. Complete the merge:
      git commit -m "Merge develop into {BRANCH} - resolve conflicts"

   d. Run tests to verify merge didn't break anything:
      npm test 2>/dev/null || pytest 2>/dev/null || true

      IF tests fail:
        Report: "Merge succeeded but tests failing - investigating"
        # Continue to Phase 4 to fix the issues

   e. Report: "Merge conflicts resolved"

5. Comment on task:
   IF is_merge_conflict:
     "Dev #{DEV_ID} resolving merge conflicts with develop."
   ELSE IF is_rework:
     "Dev #{DEV_ID} starting rework. Instructions: {REWORK_INSTRUCTIONS}"
   ELSE:
     "Dev #{DEV_ID} started. Branch: {BRANCH}, Worktree: {path}"
```

### Phase 4: Execute Sub-Tasks

```
IF is_rework:
  # Focus only on the rework instructions
  1. Analyze REWORK_INSTRUCTIONS to understand what needs fixing
  2. Make targeted changes to address the issues
  3. Run tests to verify fixes
  4. Commit with message: "fix: address rework feedback - {summary}"

ELSE:
  # Normal implementation flow
  Read the plan and execute in order:

  1. DES-* tasks first (Design):
     - Reference frontend-design skill if UI work
     - Read design system from CLAUDE.md
     - Implement components/designs
     - Commit after each: "DES-N: {description}"
     - Check off in task description: [x] DES-N: ...

  2. DEV-* tasks second (Development):
     - Implement code changes
     - Run linter and type checker
     - Commit after each: "DEV-N: {description}"
     - Check off in task description: [x] DEV-N: ...

  3. TEST-* tasks last (Testing):
     - Write unit/integration tests
     - Run test suite
     - For E2E: use Chrome via computer tool
     - Commit after each: "TEST-N: {description}"
     - Check off in task description: [x] TEST-N: ...

After each sub-task:
- Update task description checkboxes
- Comment progress if significant milestone

Handle failures:
- If a sub-task fails after 3 retries, go to Phase 6 (Failure)
```

### Phase 5: Create PR and Cleanup (Success)

```
1. Push branch:
   git push origin "$BRANCH"

2. Handle PR:
   IF is_rework:
     # PR already exists, just push updates
     # No comment here - the final comment uses canonical format
   ELSE:
     # Create new PR using GitHub MCP
     - Title: {Task Title}
     - Base: develop
     - Body: List completed sub-tasks, reference task ID
     Comment on task: "PR created: {PR_URL}"

3. Cleanup worktree:
   cd "$PROJECT_ROOT"
   git worktree remove "$WORKTREE" --force
   git worktree prune

4. Update task:
   - Remove: CLAIM_TAG
   - Remove: "Planned" (signals task no longer available for claiming)
   - Remove: "Rework-Requested" (if present)
   - Remove: "Merge-Conflict" (if present)
   - Add: "Dev-Complete", "Design-Complete", "Test-Complete"
   - Move to: "Review" column (use sync_column: false)
   - Comment (use canonical ## format for rework):
     IF is_merge_conflict:
       "## rework-complete\n\nMerge conflicts resolved."
     ELSE IF is_rework:
       "## rework-complete\n\nAddressed reviewer feedback:\n- {summary of changes}\n\nReady for re-review."
     ELSE:
       "Implementation complete. PR: {link}"

5. Report: "Dev #{DEV_ID} completed '{title}'"
   Continue to Phase 1
```

### Phase 6: Handle Failure

```
IF implementation cannot complete:

1. Keep worktree (for debugging)

2. Update task:
   - Remove: CLAIM_TAG
   - Add: "Implementation-Failed"
   - Comment: "Dev #{DEV_ID} failed: {error details}"

3. Report: "Dev #{DEV_ID} failed on '{title}': {reason}"
   Continue to Phase 1
```

## Task Validation Rules

A task is valid for Dev claiming if:
- Task is in "Development" column
- Task has "Planned" OR "Rework-Requested" tag
- Task has NO "Claimed-Dev-*" tags
- Task has NO "Implementation-Failed" tag

**Rework tasks take priority over new work.**

## Detecting @rework Comments

When scanning for rework tasks:
1. Get task comments using `list_task_comments`
2. Look for comments containing `@rework` pattern
3. Extract instructions following `@rework`
4. Common patterns:
   - `@rework Please fix the validation logic`
   - `@rework [reason]: Need to update tests`
   - Just `@rework` with issues listed below

## Status Reporting

While working on a task, every 5 minutes comment:
```
Dev #{DEV_ID} progress on '{title}':
- Type: {NEW_WORK | REWORK}
- Current: {TYPE}-{N} or "Addressing rework feedback"
- Completed: X/Y sub-tasks
- Elapsed: {time}
```

## Loop Control

- Continue until IDLE_COUNT reaches MAX_IDLE
- No waiting between tasks when queue has items
- Always validate and claim atomically
- Always cleanup worktrees after completion
- **Rework tasks are processed before new work**

## Completion

Output `<promise>DEV_{DEV_ID}_SHUTDOWN</promise>` when:
- Max idle polls reached, OR
- Explicitly told to stop

Begin Dev #{DEV_ID} loop now.
