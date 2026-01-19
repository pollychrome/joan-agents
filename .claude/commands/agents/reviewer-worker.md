---
description: Single-pass Reviewer worker dispatched by coordinator
argument-hint: --task=<task-id>
allowed-tools: mcp__joan__*, mcp__github__*, Read, Bash, Grep, Glob, Task
---

# Reviewer Worker (Single-Pass)

Review a single task assigned by the coordinator, then exit.

## Arguments

- `--task=<ID>` - Task ID to review (REQUIRED)

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
```

If argument missing, report error and exit.

---

## Step 1: Fetch and Validate Task

```
1. Fetch task using get_task(TASK_ID)

2. Validate task is reviewable:
   - Task is in "Review" column
   - Task has ALL completion tags: Dev-Complete, Design-Complete, Test-Complete
   - Task does NOT have Review-In-Progress tag
   - Task does NOT have Review-Approved tag

3. IF task has Rework-Complete tag:
   - This is a re-review after rework
   - Note: REWORK_REVIEW = true

4. IF validation fails:
   Report: "Task {TASK_ID} not ready for review"
   EXIT
```

---

## Step 2: Claim Review

```
1. Add "Review-In-Progress" tag

2. Comment (ALS breadcrumb):
   "ALS/1
   actor: reviewer
   intent: status
   action: review-start
   tags.add: [Review-In-Progress]
   tags.remove: []
   summary: Review started."
```

---

## Step 3: Merge Develop Into Feature (Conflict Check)

```
1. Extract branch name from task description

2. Checkout the feature branch locally:
   git fetch origin
   git checkout "$BRANCH"
   git pull origin "$BRANCH"

3. Merge develop into feature:
   git fetch origin develop
   git merge origin/develop --no-edit

4. IF merge conflicts:
   - This is a blocking issue
   - Cannot review code with unresolved conflicts
   - Go to CONFLICT REJECTION

5. IF merge clean:
   git push origin "$BRANCH"
   Continue to Step 4
```

---

## Step 4: Deep Code Review

Perform comprehensive review:

### 4a. Functional Completeness
```
- All sub-tasks checked off in task description
- PR changes match requirements
- No missing functionality
```

### 4b. Code Quality
```
- Follows project conventions (check CLAUDE.md)
- No obvious logic errors
- Proper error handling
- No code duplication
- Clean, readable code
```

### 4c. Security
```
- No hardcoded secrets
- Proper input validation
- No injection vulnerabilities (SQL, XSS, etc.)
- Secure authentication/authorization (if applicable)
```

### 4d. Testing
```
- Tests exist for new functionality
- Test coverage is adequate
- Tests are passing (check CI if available)
- Edge cases considered
```

### 4e. Design (if UI changes)
```
- Matches design system
- Responsive/accessible
- Consistent with existing UI
```

Build a list of issues found, categorized by severity:
- BLOCKER: Must fix before merge
- WARNING: Should fix, but not blocking
- SUGGESTION: Nice to have

---

## Step 5: Make Decision

### IF BLOCKERS exist → REJECT

```
1. Remove completion tags:
   - Remove "Dev-Complete"
   - Remove "Design-Complete"
   - Remove "Test-Complete"
   - Remove "Rework-Complete" (if present)

2. Remove "Review-In-Progress" tag

3. Add tags:
   - Add "Rework-Requested"
   - Add "Planned" (makes task claimable again)

4. Move task to "Development" column

5. Comment (ALS breadcrumb):
   "ALS/1
   actor: reviewer
   intent: decision
   action: review-rework
   tags.add: [Rework-Requested, Planned]
   tags.remove: [Review-In-Progress, Review-Approved, Rework-Complete, Dev-Complete, Design-Complete, Test-Complete]
   summary: Changes requested; see details.
   details:
   - blockers:
     - {issue 1}
     - {issue 2}
   - warnings:
     - {warning 1}
   - suggestions:
     - {suggestion 1}"

6. Report: "Review REJECTED - {N} blockers found"
```

### IF no BLOCKERS → APPROVE

```
1. Remove "Review-In-Progress" tag
2. Remove "Rework-Complete" tag (if present)

3. Add "Review-Approved" tag

4. Comment (ALS breadcrumb):
   "ALS/1
   actor: reviewer
   intent: decision
   action: review-approve
   tags.add: [Review-Approved]
   tags.remove: [Review-In-Progress, Rework-Complete]
   summary: Review approved; ready for merge.
   details:
   - {summary of review}
   - warnings (non-blocking, if any):
     - {warning 1}"

5. Report: "Review APPROVED"
```

---

## Conflict Rejection

```
IF merge conflicts detected:

1. Do NOT proceed with review (can't review conflicted code)

2. Remove "Review-In-Progress" tag

3. Remove completion tags:
   - Remove "Dev-Complete"
   - Remove "Design-Complete"
   - Remove "Test-Complete"

4. Add tags:
   - Add "Merge-Conflict"
   - Add "Rework-Requested"
   - Add "Planned"

5. Move task to "Development" column

6. Comment (ALS breadcrumb):
   "ALS/1
   actor: reviewer
   intent: decision
   action: review-conflict
   tags.add: [Merge-Conflict, Rework-Requested, Planned]
   tags.remove: [Review-In-Progress, Review-Approved, Dev-Complete, Design-Complete, Test-Complete]
   summary: Merge conflicts with develop; resolve and rework.
   details:
   - conflicting files:
     - {file1}
     - {file2}"

7. Report: "Review BLOCKED - merge conflicts"
```

---

## Step 6: Exit

```
Report completion summary:
"Reviewer Worker complete:
- Task: {title}
- Result: {APPROVED | REJECTED | BLOCKED}
- Issues: {N blockers, N warnings, N suggestions}"

EXIT
```

---

## Review Checklist Reference

| Category | Check | Severity |
|----------|-------|----------|
| **Functional** | All sub-tasks complete | BLOCKER |
| **Functional** | PR matches requirements | BLOCKER |
| **Code** | Follows conventions | WARNING |
| **Code** | No logic errors | BLOCKER |
| **Code** | Proper error handling | WARNING |
| **Security** | No hardcoded secrets | BLOCKER |
| **Security** | Input validation | BLOCKER |
| **Security** | No injection vulnerabilities | BLOCKER |
| **Testing** | Tests exist | WARNING |
| **Testing** | Tests passing | BLOCKER |
| **Design** | Matches design system | WARNING |

## Constraints

- Single task only - review and exit
- Always merge develop first (conflict check)
- Store feedback in task description (not just comments)
- Never merge PRs (Ops does that)
- Be thorough but fair - focus on real issues

Begin reviewing task: $TASK_ID
