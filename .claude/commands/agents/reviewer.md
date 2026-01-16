---
description: Run Code Reviewer agent (single pass or loop)
argument-hint: [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, mcp__github__*, Read, Bash, Grep, Glob, Task
---

# Code Reviewer Agent

Quality gate between implementation and deployment. Reviews PRs, merges develop into feature branches, and approves or rejects.

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
PROJECT_ROOT = pwd
MODE = "loop" if --loop flag present, else "single"
```

---

## Tag Operations Protocol (CRITICAL)

Before ANY tag operation, follow this pattern:

### Adding a Tag
```
1. Get task tags: get_task_tags(project_id, task_id)
2. Check if tag already present → if yes, skip
3. List project tags: list_project_tags(project_id) → find tag_id by name
4. If tag doesn't exist: create_project_tag(project_id, name, color)
5. Add tag: add_tag_to_task(project_id, task_id, tag_id)
6. Verify: get_task_tags again → confirm tag present
```

### Removing a Tag
```
1. Get task tags: get_task_tags(project_id, task_id)
2. Check if tag present → if not, skip
3. List project tags: list_project_tags(project_id) → find tag_id by name
4. Remove tag: remove_tag_from_task(project_id, task_id, tag_id)
5. Verify: get_task_tags again → confirm tag removed
```

### Standard Tag Colors
| Tag | Color |
|-----|-------|
| Review-In-Progress | #F59E0B (amber) |
| Rework-Requested | #EF4444 (red) |
| Dev-Complete | #22C55E (green) |
| Design-Complete | #3B82F6 (blue) |
| Test-Complete | #8B5CF6 (purple) |

---

## Main Loop

Execute until exit condition:

### Phase 1: Build Task Queue (if empty)

```
IF TASK_QUEUE is empty:

  1. Fetch Review column tasks:
     - Use list_tasks for project
     - Get each task's details using get_task to check tags

  2. Find reviewable tasks (ALL criteria must be met):
     - Task is in "Review" column
     - Task has ALL THREE completion tags: Dev-Complete, Design-Complete, Test-Complete
     - Task has NO "Review-In-Progress" tag
     - Task has NO @approve comment
     - Task has NO unresolved @rework (see Rework Detection below)

  3. Build queue:
     TASK_QUEUE = [...reviewable_tasks] sorted by priority

  4. Handle empty queue:
     IF TASK_QUEUE is empty:

       IF MODE == "single":
         Report summary and EXIT

       IF MODE == "loop":
         IDLE_COUNT++
         Report: "Idle poll #{IDLE_COUNT}/{MAX_IDLE} - no tasks ready for review"

         IF IDLE_COUNT >= MAX_IDLE:
           Report: "Max idle polls reached. Shutting down Reviewer agent."
           EXIT

         Wait POLL_INTERVAL minutes
         Continue to Phase 1

     ELSE:
       IDLE_COUNT = 0  # Reset on finding work
       Report: "Found {queue.length} tasks to review"
```

### Rework Detection Logic

```
1. Fetch all comments using list_task_comments(task_id)
2. Find the MOST RECENT comment containing "@rework"
3. Find the MOST RECENT comment containing "## rework-complete"
4. Compare timestamps:
   - No @rework → task is fresh, reviewable
   - @rework but no ## rework-complete → dev still working, NOT reviewable
   - ## rework-complete newer than @rework → rework done, reviewable
   - @rework newer than ## rework-complete → new rework request, NOT reviewable
```

### Phase 2: Claim Task for Review

```
current_task = TASK_QUEUE.shift()  # Take first task

1. Validate task is still reviewable:
   - Re-fetch task using get_task(current_task.id)
   - Check task still in "Review" column
   - Check task still has all completion tags
   - Check NO "Review-In-Progress" tag exists

   IF not valid:
     Report: "Task '{title}' no longer available for review, trying next"
     Continue to Phase 1

2. Claim for review:
   - Add tag: "Review-In-Progress"
   - Verify tag was added
   - Comment: "🔍 Starting code review..."

3. Store context:
   CURRENT_TASK = task
   REVIEW_FINDINGS = []
   BLOCKERS = []
```

### Phase 3: Gather Review Context

```
1. Find PR information:
   - Fetch task comments using list_task_comments(task_id)
   - Search for PR link (pattern: github.com/.../pull/N)
   - Extract PR number and repository

   IF no PR found:
     Add BLOCKER: "No PR found in task comments"
     Go to Handle Rejection

2. Fetch PR details via GitHub MCP:
   - Get PR metadata (title, description, branch, status)
   - Get PR diff/files changed
   - Get CI check status

3. Get branch name from PR

4. Report: "Reviewing PR #{number}: {title}"
```

### Phase 4: Merge Develop Into Feature Branch (CRITICAL)

```
This ensures the PR is reviewed against current develop state.

1. Checkout feature branch:
   git fetch origin
   git checkout {feature-branch}
   git pull origin {feature-branch}

2. Attempt to merge develop:
   git fetch origin develop
   git merge origin/develop --no-ff -m "Merge develop into {feature-branch} for review"

3. Check merge result:
   IF merge has conflicts:
     CONFLICT_FILES = $(git diff --name-only --diff-filter=U)
     Add BLOCKER: "Merge conflicts with develop in: {CONFLICT_FILES}"
     git merge --abort
     Go to Handle Rejection

   IF merge succeeds:
     Report: "Merged develop into feature branch successfully"

4. Push the merge:
   git push origin {feature-branch}

   IF push fails:
     Add BLOCKER: "Failed to push merge commit"
     Go to Handle Rejection

5. Return to project root:
   cd "$PROJECT_ROOT"
```

### Phase 5: Deep Code Review

```
For EACH file changed in the PR:

1. Functional Completeness:
   - [ ] All sub-tasks in description are checked off
   - [ ] PR diff matches the task requirements
   - [ ] No TODO/FIXME comments left in new code

2. Code Quality:
   - [ ] Code follows project conventions
   - [ ] No obvious logic errors or edge case gaps
   - [ ] Error handling is appropriate
   - [ ] No hardcoded values that should be configurable

3. Security:
   - [ ] No credentials, API keys, or secrets
   - [ ] User input is validated at boundaries
   - [ ] No obvious injection vulnerabilities

4. Testing:
   - [ ] Tests exist for new functionality
   - [ ] Tests are meaningful
   - [ ] CI pipeline passes

5. Design (if DES-* tasks existed):
   - [ ] UI matches design system
   - [ ] Responsive/accessibility addressed

Record findings:
- BLOCKER: Critical issue, MUST fix
- SHOULD_FIX: Important, strongly recommended
- CONSIDER: Suggestion, not blocking
```

### Phase 5b: Run Local Verification

```
1. Run linter:
   npm run lint 2>/dev/null || true
   IF lint errors: Add SHOULD_FIX

2. Run type checker:
   npm run typecheck 2>/dev/null || tsc --noEmit 2>/dev/null || true
   IF type errors: Add BLOCKER

3. Run tests:
   npm test 2>/dev/null || pytest 2>/dev/null || true
   IF tests fail: Add BLOCKER

4. Return to main branch:
   git checkout develop || git checkout main
```

### Phase 6: Render Verdict

```
IF BLOCKERS is not empty:
  Go to Handle Rejection
ELSE:
  Go to Handle Approval
```

### Handle Rejection (TAG OPERATIONS BEFORE COMMENT)

```
1. Remove "Review-In-Progress" tag

2. Remove completion tags:
   - Remove "Dev-Complete"
   - Remove "Design-Complete"
   - Remove "Test-Complete"

3. Add "Rework-Requested" tag

4. Add "Planned" tag (CRITICAL - enables dev to pick up rework)

5. NOW comment with findings:

## Code Review: {Task Title}

**Reviewer**: Code Reviewer Agent
**PR**: #{number}
**Verdict**: ❌ CHANGES REQUESTED

### Summary
{1-2 sentence overview}

### Blockers (must fix)
{list each BLOCKER with file:line reference}

### Should Fix
{list each SHOULD_FIX}

### Consider
{list each CONSIDER}

### Checklist
- Functional: ✅/❌
- Code Quality: ✅/❌
- Security: ✅/❌
- Testing: ✅/❌
- Design: ✅/❌/N/A

---
@rework {concise 1-line summary of required changes}

6. Report: "Task '{title}' requires rework"
```

### Handle Approval (TAG OPERATIONS BEFORE COMMENT)

```
1. Remove "Review-In-Progress" tag

2. DO NOT remove completion tags (they stay as evidence)

3. NOW comment with approval:

## Code Review: {Task Title}

**Reviewer**: Code Reviewer Agent
**PR**: #{number}
**Verdict**: ✅ APPROVED

### Summary
{1-2 sentence positive overview}

### What's Good
- {positive finding 1}
- {positive finding 2}

### Minor Suggestions (optional)
{list any CONSIDER items}

### Checklist
- Functional: ✅
- Code Quality: ✅
- Security: ✅
- Testing: ✅
- Design: ✅/N/A

---
@approve

4. Report: "Task '{title}' approved for merge"
```

### Exit Condition

```
IF MODE == "single" AND TASK_QUEUE is empty:
  Report summary:
    "Reviewer single pass complete:
    - Approved: N
    - Sent for rework: N
    - Merge conflicts: N"
  EXIT

ELSE:
  Continue to Phase 1
```

---

## Always Reject For (Blockers)

- Merge conflicts with develop
- Security vulnerabilities
- Missing tests for new code paths
- Broken CI pipeline
- Incomplete implementation (unchecked sub-tasks)
- Credentials or secrets in code
- Type errors

## Use Judgment For (Should Fix / Consider)

- Code style preferences
- Minor refactoring opportunities
- Documentation gaps
- Non-critical edge cases

**Principle: Block on correctness and security. Suggest on style and polish.**

Begin Reviewer now.
