---
description: Start an Implementation Worker loop for parallel feature development
argument-hint: [project-name-or-id] [worker-id] [--max-idle=N]
allowed-tools: mcp__joan__*, mcp__github__*, Read, Write, Edit, Bash, Grep, Glob, Task, View, computer
---

# Implementation Worker Loop

You are an **Implementation Worker** for parallel feature development.

## Configuration

Parse arguments:
- `$1` = Project name or ID (or read from `.joan-agents.json` if not provided)
- `$2` = Worker ID (default: 1)
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
WORKER_ID = $2 or 1
CLAIM_TAG = "Claimed-Worker-{WORKER_ID}"
TASK_QUEUE = []
IDLE_COUNT = 0
PROJECT_ROOT = pwd
WORKTREE_BASE = "../worktrees"
```

Report: "Worker #{WORKER_ID} initialized for project {PROJECT}"

## Your Mission

Continuously claim tasks, implement them in isolated worktrees, and create PRs. This enables true parallel feature development.

## Main Loop

Execute until shutdown:

### Phase 1: Build Task Queue (if empty)

```
IF TASK_QUEUE is empty:

  1. Fetch Development column tasks:
     - Use list_tasks for project with "Development" status
     - Filter for tasks with "Planned" tag
     - Exclude tasks with any "Claimed-Worker-*" tag

  2. Build queue:
     TASK_QUEUE = [available_tasks sorted by priority]

  3. Handle empty queue:
     IF TASK_QUEUE is empty:
       IDLE_COUNT++
       Report: "Worker #{WORKER_ID} idle poll #{IDLE_COUNT}/{MAX_IDLE} - no available tasks"

       IF IDLE_COUNT >= MAX_IDLE:
         Report: "Max idle polls reached. Shutting down Worker #{WORKER_ID}."
         Output: <promise>WORKER_{WORKER_ID}_SHUTDOWN</promise>
         EXIT

       Wait POLL_INTERVAL minutes
       Continue to Phase 1
     ELSE:
       IDLE_COUNT = 0  # Reset on successful poll
       Report: "Worker #{WORKER_ID} found {queue.length} potential tasks"
```

### Phase 2: Claim Next Task

```
current_task = TASK_QUEUE.shift()  # Take first task

1. Validate and attempt claim:
   - Re-fetch task using get_task(current_task.id)

   Validation checks:
   - Task still in "Development" column
   - Task still has "Planned" tag
   - Task has NO "Claimed-Worker-*" tags
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
   - Check no OTHER "Claimed-Worker-*" tags exist

   IF claim failed:
     Report: "Failed to claim '{title}' (another worker got it)"
     Remove your claim tag if present
     Continue to Phase 1

   IF claim succeeded:
     Report: "Worker #{WORKER_ID} claimed: '{title}'"
     Go to Phase 3
```

### Phase 3: Setup Worktree

```
1. Get branch name from plan attachment or task:
   - Read plan file attached to task
   - Extract branch name (format: feature/{title-kebab-case})
   - BRANCH = extracted branch name

2. Create worktree:
   WORKTREE = "{WORKTREE_BASE}/{task-id}"

   mkdir -p "$WORKTREE_BASE"
   git fetch origin
   git worktree add "$WORKTREE" -b "$BRANCH" origin/develop 2>/dev/null || \
   git worktree add "$WORKTREE" "$BRANCH"

3. Enter worktree and install deps:
   cd "$WORKTREE"
   npm install 2>/dev/null || pip install -r requirements.txt 2>/dev/null || true

4. Comment on task: "Worker #{WORKER_ID} started. Branch: {BRANCH}, Worktree: {path}"
```

### Phase 4: Execute Sub-Tasks

```
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

2. Create PR using GitHub MCP:
   - Title: {Task Title}
   - Base: develop
   - Body: List completed sub-tasks, reference task ID

3. Comment on task: "PR created: {PR_URL}"

4. Cleanup worktree:
   cd "$PROJECT_ROOT"
   git worktree remove "$WORKTREE" --force
   git worktree prune

5. Update task:
   - Remove: CLAIM_TAG
   - Add: "Dev-Complete", "Design-Complete", "Test-Complete"
   - Move to: "Review" column
   - Comment: "Implementation complete. PR: {link}"

6. Report: "Worker #{WORKER_ID} completed '{title}'"
   Continue to Phase 1
```

### Phase 6: Handle Failure

```
IF implementation cannot complete:

1. Keep worktree (for debugging)

2. Update task:
   - Remove: CLAIM_TAG
   - Add: "Implementation-Failed"
   - Comment: "Worker #{WORKER_ID} failed: {error details}"

3. Report: "Worker #{WORKER_ID} failed on '{title}': {reason}"
   Continue to Phase 1
```

## Task Validation Rules

A task is valid for Worker claiming if:
- Task is in "Development" column
- Task has "Planned" tag
- Task has NO "Claimed-Worker-*" tags
- Task has NO "Implementation-Failed" tag

## Status Reporting

While working on a task, every 5 minutes comment:
```
Worker #{WORKER_ID} progress on '{title}':
- Current: {TYPE}-{N}
- Completed: X/Y sub-tasks
- Elapsed: {time}
```

## Loop Control

- Continue until IDLE_COUNT reaches MAX_IDLE
- No waiting between tasks when queue has items
- Always validate and claim atomically
- Always cleanup worktrees after completion

## Completion

Output `<promise>WORKER_{WORKER_ID}_SHUTDOWN</promise>` when:
- Max idle polls reached, OR
- Explicitly told to stop

Begin Worker #{WORKER_ID} loop now.
