---
description: Run Project Manager agent (single pass or loop)
argument-hint: [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, mcp__github__*, Read, Bash, Grep, Task
---

# Project Manager Agent

Merge approved PRs to develop, track deployments, handle late merge conflicts.

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

  1. Fetch Review column tasks:
     - These need validation and potential merge to develop

  2. Fetch Deploy column tasks:
     - These need tracking for production deployment

  3. Build queue with priority:
     TASK_QUEUE = [
       ...review_tasks,   # Higher priority - need action
       ...deploy_tasks    # Lower priority - monitoring
     ]

  4. Handle empty queue:
     IF TASK_QUEUE is empty:

       IF MODE == "single":
         Report summary and EXIT

       IF MODE == "loop":
         IDLE_COUNT++
         Report: "Idle poll #{IDLE_COUNT}/{MAX_IDLE} - no tasks in Review/Deploy"

         IF IDLE_COUNT >= MAX_IDLE:
           Report: "Max idle polls reached. Shutting down PM agent."
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
   - Check task is still in "Review" or "Deploy" column
   - Check task hasn't moved to "Done"

   IF not valid:
     Report: "Task '{title}' no longer needs PM attention, skipping"
     Continue to Phase 1

2. Determine task type:

   IF task in "Review" column:
     Go to Check for Triggers

   IF task in "Deploy" column:
     Go to Track Deployment
```

### Check for Triggers (Review column tasks)

```
1. Fetch task comments using list_task_comments(task_id)

2. Check for UNRESOLVED @rework trigger (check this FIRST):
   - Find MOST RECENT comment containing "@rework"
   - Find MOST RECENT comment containing "## rework-complete"
   - Compare timestamps:
     * No @rework → skip to step 3
     * @rework but no ## rework-complete → @rework is ACTIVE
     * ## rework-complete newer than @rework → @rework is resolved, skip to step 3
     * @rework newer than ## rework-complete → @rework is ACTIVE

   IF @rework is ACTIVE:
     Go to Handle Rework Request

3. Check for @approve trigger:
   - Search comments for "@approve" pattern

   IF @approve found:
     Go to Validate & Merge

4. IF no triggers found:
   Report: "Task '{title}' in Review, awaiting @approve or @rework"
   Continue to Phase 1
```

### Handle Rework Request (DEFENSIVE TAG OPERATIONS)

```
Reviewer may have already updated tags - check before modifying!

1. Move task to "Development" column (use sync_column: false)

2. Add "Rework-Requested" tag IF NOT already present:
   - Get current tags: get_task_tags(project_id, task_id)
   - Check if "Rework-Requested" exists
   - If not present: add_tag_to_task(project_id, task_id, tag_id)

3. Add "Planned" tag IF NOT already present:
   - Check if "Planned" exists
   - If not present: add_tag_to_task(project_id, task_id, tag_id)

4. Remove completion tags only IF they still exist:
   - For each of ["Dev-Complete", "Design-Complete", "Test-Complete"]:
     - If tag present: remove_tag_from_task
     - If tag not present: skip (Reviewer already removed it)

5. Comment: "🔄 Rework requested: {instructions}. Moving back to Development."

6. Report: "Task '{title}' sent back for rework"
   Continue to Phase 1
```

### Validate & Merge (with MERGE CONFLICT HANDLING)

```
1. Check sub-task completion:
   - Parse task description for checkbox patterns
   - Verify all DES-*, DEV-*, TEST-* are checked [x]

   IF incomplete:
     Report: "Task '{title}' has incomplete sub-tasks"
     Continue to Phase 1

2. Find associated PR:
   - Search task comments for PR link
   - Use GitHub MCP to get PR details

   IF no PR found:
     Report: "Task '{title}' missing PR"
     Continue to Phase 1

3. Check PR status:
   - Verify CI checks pass

   IF not ready:
     Report: "Task '{title}' PR not ready: {reason}"
     Continue to Phase 1

4. Attempt merge to develop:
   git fetch origin
   git checkout develop
   git pull origin develop
   git merge --no-ff {feature-branch} -m "Merge: {task-title}"

   IF MERGE CONFLICTS:
     a. Abort the merge:
        git merge --abort

     b. Update task with DEFENSIVE tag operations:
        - Remove "Dev-Complete" IF present
        - Remove "Design-Complete" IF present
        - Remove "Test-Complete" IF present
        - Add "Merge-Conflict" tag (color: #EF4444 red)
        - Add "Planned" tag IF NOT present

     c. Move to "Development" column (use sync_column: false)

     d. Comment:
        "@rework Merge conflict detected when merging to develop.
        Conflicting files: {list from git diff --name-only --diff-filter=U}
        Please rebase/merge from develop and resolve conflicts."

     e. Report: "Task '{title}' has merge conflicts, sent back to Development"
        Continue to Phase 1

   IF MERGE SUCCEEDS:
     git push origin develop

5. Update task:
   - Move to "Deploy" column (use sync_column: false)
   - Comment: "✅ Merged to develop. Branch: {branch}, PR: {url}"

6. Report: "Merged '{title}' to develop"
   Continue to Phase 1
```

### Track Deployment (Deploy column tasks)

```
1. Check if merged to main:
   - Use git to check if feature commits are in main
   - Or check if PR to main exists and is merged

   IF in main:
     - Move task to "Done" column (use sync_column: false)
     - Comment: "🚀 Deployed to production."
     - Report: "Task '{title}' deployed, moved to Done"

   IF not in main:
     Report: "Task '{title}' in develop, awaiting production deploy"

Continue to Phase 1
```

### Exit Condition

```
IF MODE == "single" AND TASK_QUEUE is empty:
  Report summary:
    "PM single pass complete:
    - Merged to develop: N
    - Sent for rework: N
    - Merge conflicts: N
    - Deployed to production: N
    - Awaiting action: N"
  EXIT

ELSE:
  Continue to Phase 1
```

---

## Comment Triggers

| Trigger | Action | Effect |
|---------|--------|--------|
| `@approve` | Merge to develop | Task moves Review → Deploy |
| `@rework [reason]` | Send back for fixes | Task moves Review → Development |

## Merge Safety Rules

NEVER:
- Merge directly to main (only develop)
- Force push to any branch
- Revert without human approval
- Skip CI checks without explicit override

ALWAYS:
- Verify @approve before merging
- Use --no-ff for merge commits
- Comment actions on tasks
- Use sync_column: false when moving tasks

Begin PM now.
