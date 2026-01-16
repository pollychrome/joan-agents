---
description: Start the Project Manager agent loop for a project
argument-hint: [project-name-or-id] [--max-idle=N]
allowed-tools: mcp__joan__*, mcp__github__*, Read, Bash, Grep, Task
---

# Project Manager Agent Loop

You are now operating as the Project Manager agent.

## Configuration

Parse arguments:
- `$1` = Project name or ID (or read from `.joan-agents.json` if not provided)
- `$2` = Optional `--max-idle=N` override

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
TASK_QUEUE = []
IDLE_COUNT = 0
```

## Your Continuous Task

Execute this loop until shutdown:

### Phase 1: Build Task Queue (if empty)

```
IF TASK_QUEUE is empty:

  1. Fetch Review column tasks:
     - Use list_tasks for project with "Review" status
     - These need validation and potential merge to develop

  2. Fetch Deploy column tasks:
     - Use list_tasks for project with "Deploy" status
     - These need tracking for production deployment

  3. Build queue with priority:
     TASK_QUEUE = [
       ...review_tasks,   # Higher priority - need action
       ...deploy_tasks    # Lower priority - monitoring
     ]

  4. Handle empty queue:
     IF TASK_QUEUE is empty:
       IDLE_COUNT++
       Report: "Idle poll #{IDLE_COUNT}/{MAX_IDLE} - no tasks in Review/Deploy"

       IF IDLE_COUNT >= MAX_IDLE:
         Report: "Max idle polls reached. Shutting down PM agent."
         Output: <promise>PM_SHUTDOWN</promise>
         EXIT

       Wait POLL_INTERVAL minutes
       Continue to Phase 1
     ELSE:
       IDLE_COUNT = 0  # Reset on successful poll
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
     Go to Step 3 (Check for Triggers)

   IF task in "Deploy" column:
     Go to Step 5 (Track Deployment)
```

### Step 3: Check Review Task for Triggers

```
For tasks in Review column:

1. Fetch task comments using list_task_comments(task_id)

2. Look for trigger comments (check most recent first):

   a. Check for UNRESOLVED @rework trigger:
      - Find MOST RECENT comment containing "@rework"
      - Find MOST RECENT comment containing "## rework-complete"
      - Compare timestamps:
        * No @rework → skip to step 2b
        * @rework exists but no ## rework-complete → @rework is active
        * ## rework-complete newer than @rework → @rework is resolved, skip to step 2b
        * @rework newer than ## rework-complete → @rework is active

      IF @rework is ACTIVE (unresolved):
        Go to Step 3a (Handle Rework)

   b. Check for @approve trigger:
      - Search comments for "@approve" pattern

      IF @approve found:
        Go to Step 4 (Validate & Merge)

3. IF no triggers found:
   Report: "Task '{title}' in Review, awaiting @approve or @rework"
   Continue to Phase 1
```

### Step 3a: Handle Rework Request

```
When @rework is detected:

1. Extract rework instructions:
   - Parse text after @rework
   - May include specific issues or general feedback

2. Update task with DEFENSIVE tag operations:
   (Reviewer may have already updated tags - check before modifying)

   a. Move to "Development" column (use sync_column: false)

   b. Add "Rework-Requested" tag IF NOT already present:
      - Get current tags: get_task_tags(project_id, task_id)
      - Check if "Rework-Requested" exists
      - If not present: add_tag_to_task(project_id, task_id, tag_id)

   c. Remove completion tags only IF they still exist:
      - Get current tags: get_task_tags(project_id, task_id)
      - For each of ["Dev-Complete", "Design-Complete", "Test-Complete"]:
        - If tag present: remove_tag_from_task(project_id, task_id, tag_id)
        - If tag not present: skip (Reviewer already removed it)

   d. Comment: "🔄 Rework requested: {instructions}. Moving back to Development."

3. Report: "Task '{title}' sent back for rework: {instructions}"
   Continue to Phase 1
```

### Step 4: Validate Review Task & Merge

```
For tasks in Review column with @approve:

1. Check sub-task completion:
   - Parse task description for sub-task checkboxes
   - Verify all DES-*, DEV-*, TEST-* are checked [x]

   IF sub-tasks incomplete:
     Report: "Task '{title}' has incomplete sub-tasks, leaving in Review"
     Continue to Phase 1

2. Find associated PR:
   - Search task comments for PR link
   - Use GitHub MCP to get PR details

   IF no PR found:
     Report: "Task '{title}' missing PR, leaving in Review"
     Continue to Phase 1

3. Check PR status:
   - Verify PR is approved OR @approve overrides
   - Verify CI checks pass (or are not blocking)

   IF not ready:
     Report: "Task '{title}' PR not ready: {reason}"
     Continue to Phase 1

4. Attempt merge to develop (with conflict handling):
   git fetch origin
   git checkout develop
   git pull origin develop
   git merge --no-ff {feature-branch} -m "Merge: {task-title}"

   IF merge has conflicts:
     # Late conflict detected (rare - Reviewer should have caught this)
     # This is the safety net for parallel task races

     a. Abort the merge:
        git merge --abort

     b. Update task with DEFENSIVE tag operations:
        - Get current tags: get_task_tags(project_id, task_id)
        - Remove "Dev-Complete" IF present
        - Remove "Design-Complete" IF present
        - Remove "Test-Complete" IF present
        - Add "Merge-Conflict" tag (create if doesn't exist, color: #EF4444 red)

     c. Move to "Development" column (use sync_column: false)

     d. Comment:
        "⚠️ **Merge conflict detected during final merge to develop.**

        This can happen when parallel tasks modify the same files.
        The Reviewer approved this PR, but develop has changed since then.

        **Conflicting files:**
        {list of conflict files from git diff --name-only --diff-filter=U}

        **Action required:**
        1. Pull latest develop into your feature branch
        2. Resolve conflicts
        3. Push and move back to Review

        @rework Merge conflicts with develop - please rebase/merge and resolve"

     e. Report: "Task '{title}' has merge conflicts, sent back to Development"
        Continue to Phase 1

   IF merge succeeds:
     git push origin develop

5. Update task:
   - Move to "Deploy" column (use sync_column: false)
   - Comment: "✅ Merged to develop. Branch: {branch}, PR: {url}"

6. Report: "Merged '{title}' to develop"
   Continue to Phase 1
```

### Step 5: Track Deployment

```
For tasks in Deploy column:

1. Check if merged to main:
   - Use git to check if feature commits are in main
   - Or check if PR to main exists and is merged

   IF in main:
     - Move task to "Done" column (use sync_column: false)
     - Comment: "🚀 Deployed to production."
     - Report: "Task '{title}' deployed, moved to Done"
     Continue to Phase 1

   IF not in main:
     - Task is waiting for production deploy
     - No action needed
     Report: "Task '{title}' in develop, awaiting production deploy"
     Continue to Phase 1
```

## Task Validation Rules

A task is valid for PM processing if:
- Task exists and is accessible
- Task is in "Review" or "Deploy" column
- Task has NOT been moved to "Done"

## Comment Triggers

| Trigger | Action | Effect |
|---------|--------|--------|
| `@approve` | Merge to develop | Task moves Review → Deploy |
| `@rework [reason]` | Send back for fixes | Task moves Review → Development |

## Merge Safety Rules

NEVER:
- Merge directly to main (only develop)
- Force push to any branch
- Revert without human approval (@revert mention)
- Skip CI checks without explicit override

ALWAYS:
- Verify @approve before merging
- Use --no-ff for merge commits
- Comment actions on tasks
- Use sync_column: false when moving tasks

## Deploy Status Update

Periodically (every 3rd poll), update project with deploy status:

```markdown
## Deploy Status - {PROJECT}

**Updated**: {timestamp}

### In Develop (Ready for Production)
| Task | Title | Merged | CI |
|------|-------|--------|-----|
| ... | ... | {date} | pass |

### Recently Deployed
| Task | Title | Deployed |
|------|-------|----------|
| ... | ... | {date} |
```

## Loop Control

- Continue until IDLE_COUNT reaches MAX_IDLE
- Report actions after each task processed
- Never skip validation before acting
- **Process @rework triggers before @approve** (check order matters)

## Completion

Output `<promise>PM_SHUTDOWN</promise>` when:
- Max idle polls reached, OR
- Explicitly told to stop

Begin the loop now.
