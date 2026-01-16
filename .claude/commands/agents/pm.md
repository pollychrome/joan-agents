---
description: Run Project Manager agent (single pass or loop)
argument-hint: [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, mcp__github__*, Read, Bash, Grep, Task
---

# Project Manager Agent

Quick invocation of the Project Manager agent.

## Mode Selection

Parse arguments:
- `--loop` → Run continuously (use pm-loop behavior)
- No flag → Single pass (process queue once, then exit)
- `--max-idle=N` → Override idle threshold (only for loop mode)

## Configuration

Load from `.joan-agents.json`:
- PROJECT_ID = config.projectId
- PROJECT_NAME = config.projectName

If config missing, report error and exit.

## Single Pass Mode (default)

### Step 1: Fetch Actionable Tasks

Fetch tasks from two columns:
- **Review column**: Check for @approve or unresolved @rework triggers
- **Deploy column**: Check if deployed to production

### Step 2: Process Each Task

For each task, validate it's still actionable, then:

#### If task in "Review" column → Check for Triggers

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
     Go to "Handle Rework Request"

3. Check for @approve trigger:
   - Search comments for "@approve" pattern

   IF @approve found:
     Go to "Validate & Merge"

4. If no triggers: Report "Task awaiting @approve or @rework", skip
```

#### Handle Rework Request (DEFENSIVE TAG OPERATIONS)

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
   - Get current tags
   - For each of ["Dev-Complete", "Design-Complete", "Test-Complete"]:
     - If tag present: remove_tag_from_task
     - If tag not present: skip (Reviewer already removed it)

5. Comment: "🔄 Rework requested: {instructions}. Moving back to Development."

6. Report: "Task '{title}' sent back for rework"
```

#### Validate & Merge (with MERGE CONFLICT HANDLING)

```
1. Check sub-task completion:
   - Parse task description for checkbox patterns
   - Verify all DES-*, DEV-*, TEST-* are checked [x]
   - If incomplete: Report and skip

2. Find PR:
   - Search task comments for PR link
   - If no PR: Report and skip

3. Check PR status:
   - Verify CI checks pass
   - If not ready: Report and skip

4. Attempt merge to develop:
   git fetch origin
   git checkout develop
   git pull origin develop
   git merge --no-ff {feature-branch} -m "Merge: {task-title}"

   IF MERGE CONFLICTS:
     a. Abort the merge:
        git merge --abort

     b. Update task with DEFENSIVE tag operations:
        - Get current tags
        - Remove "Dev-Complete" IF present
        - Remove "Design-Complete" IF present
        - Remove "Test-Complete" IF present
        - Add "Merge-Conflict" tag (color: #EF4444 red)
        - Add "Planned" tag IF NOT present

     c. Move to "Development" column (use sync_column: false)

     d. Comment:
        "⚠️ **Merge conflict detected during final merge to develop.**

        This can happen when parallel tasks modify the same files.

        **Conflicting files:**
        {list from git diff --name-only --diff-filter=U}

        **Action required:**
        1. Pull latest develop into your feature branch
        2. Resolve conflicts
        3. Push and move back to Review

        @rework Merge conflicts with develop - please rebase/merge and resolve"

     e. Report: "Task '{title}' has merge conflicts, sent back to Development"
        Continue to next task

   IF MERGE SUCCEEDS:
     git push origin develop

5. Update task:
   - Move to "Deploy" column (use sync_column: false)
   - Comment: "✅ Merged to develop. Branch: {branch}, PR: {url}"

6. Report: "Merged '{title}' to develop"
```

#### If task in "Deploy" column → Track Deployment

```
1. Check if commits are in main:
   - Use git to check if feature commits exist in main
   - Or check if PR to main is merged

   IF in main:
     - Move task to "Done" column (use sync_column: false)
     - Comment: "🚀 Deployed to production."
     - Report: "Task '{title}' deployed, moved to Done"

   IF not in main:
     - Report: "Task '{title}' in develop, awaiting production deploy"
```

### Step 3: Report Summary and Exit

```
PM single pass complete:
- Merged to develop: N
- Sent for rework: N
- Merge conflicts: N
- Deployed to production: N
- Awaiting action: N
```

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

## Loop Mode (--loop)

Invoke the full pm-loop with configuration from .joan-agents.json.

Begin now.
