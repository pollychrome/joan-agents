---
description: Run Code Reviewer agent (single pass or loop)
argument-hint: [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, mcp__github__*, Read, Bash, Grep, Glob, Task
---

# Code Reviewer Agent

Quick invocation of the Code Reviewer agent - the quality gate between implementation and deployment.

## Mode Selection

Parse arguments:
- `--loop` → Run continuously (use reviewer-loop behavior)
- No flag → Single pass (process queue once, then exit)
- `--max-idle=N` → Override idle threshold (only for loop mode)

## Configuration

Load from `.joan-agents.json`:
- PROJECT_ID = config.projectId
- PROJECT_NAME = config.projectName

If config missing, report error and exit.

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

## Single Pass Mode (default)

### Step 1: Fetch Reviewable Tasks

Fetch tasks in "Review" column that meet ALL criteria:
- Has ALL THREE completion tags: Dev-Complete, Design-Complete, Test-Complete
- Does NOT have "Review-In-Progress" tag
- Does NOT have @approve comment
- Does NOT have unresolved @rework (see Rework Detection below)

### Rework Detection Logic

```
1. Fetch all comments using list_task_comments(task_id)
2. Find the MOST RECENT comment containing "@rework"
3. Find the MOST RECENT comment containing "## rework-complete"
4. Compare timestamps:
   - If no @rework exists → task is reviewable (fresh review)
   - If @rework exists but no ## rework-complete → NOT reviewable (dev still working)
   - If ## rework-complete timestamp > @rework timestamp → reviewable (rework done)
   - If @rework timestamp > ## rework-complete timestamp → NOT reviewable (new rework)
```

### Step 2: Process Each Task

For each reviewable task:

#### 2a. Claim for Review
```
1. Add "Review-In-Progress" tag (claim for review)
2. Verify tag was added
3. Comment: "🔍 Starting code review..."
```

#### 2b. Gather Context
```
1. Find PR link in task comments (pattern: github.com/.../pull/N)
2. If no PR found: Add BLOCKER, go to Rejection
3. Fetch PR details via GitHub MCP
```

#### 2c. Merge Develop Into Feature Branch
```
git fetch origin
git checkout {feature-branch}
git pull origin {feature-branch}
git fetch origin develop
git merge origin/develop --no-ff -m "Merge develop into {feature-branch} for review"

IF merge conflicts:
  CONFLICT_FILES = $(git diff --name-only --diff-filter=U)
  Add BLOCKER: "Merge conflicts with develop in: {CONFLICT_FILES}"
  git merge --abort
  Go to Rejection

IF merge succeeds:
  git push origin {feature-branch}
```

#### 2d. Deep Code Review
```
For EACH file changed in PR, check:
- Functional: All sub-tasks checked off, PR matches requirements
- Code Quality: Follows conventions, no logic errors, proper error handling
- Security: No secrets, input validated, no injection vulnerabilities
- Testing: Tests exist and pass, CI green
- Design: UI matches design system (if applicable)

Record findings as:
- BLOCKER: Critical issue, MUST fix
- SHOULD_FIX: Important, strongly recommended
- CONSIDER: Suggestion, not blocking
```

### Step 3: Render Verdict

#### On Rejection (BLOCKERS exist) - TAG OPERATIONS MUST HAPPEN BEFORE COMMENT

```
1. Remove "Review-In-Progress" tag
2. Remove completion tags:
   - Remove "Dev-Complete"
   - Remove "Design-Complete"
   - Remove "Test-Complete"
3. Add "Rework-Requested" tag
4. Add "Planned" tag (CRITICAL - enables dev agent to pick up rework)
5. NOW comment with review and @rework trigger:

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

---
@rework {concise 1-line summary of required changes}
```

#### On Approval (no BLOCKERS) - TAG OPERATIONS MUST HAPPEN BEFORE COMMENT

```
1. Remove "Review-In-Progress" tag
2. DO NOT remove completion tags (they stay as evidence)
3. NOW comment with review and @approve trigger:

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

---
@approve
```

### Step 4: Report Summary and Exit

```
Reviewer single pass complete:
- Approved: N
- Sent for rework: N
- Merge conflicts: N
- Awaiting review: N
```

## Loop Mode (--loop)

Invoke the full reviewer-loop with configuration from .joan-agents.json.

Begin now.
