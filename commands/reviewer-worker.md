---
description: Single-pass Reviewer worker dispatched by coordinator
argument-hint: --task=<task-id>
allowed-tools: Read, Bash, Grep, Glob, Task
---

# Reviewer Worker (Single-Pass, MCP Proxy Pattern)

Review a single task and return a structured JSON result.
**You do NOT have MCP access** - return action requests for the coordinator to execute.

## Input: Work Package

The coordinator provides a work package with:
```json
{
  "task_id": "uuid",
  "task_title": "string",
  "task_description": "string",
  "task_tags": ["tag1", "tag2"],
  "task_column": "Review",
  "task_comments": [...],
  "workflow_mode": "standard" | "yolo",
  "project_id": "uuid",
  "project_name": "string",
  "previous_stage_context": {
    "from_stage": "dev",
    "to_stage": "reviewer",
    "key_decisions": ["..."],
    "files_of_interest": ["..."],
    "warnings": ["..."],
    "metadata": {
      "pr_number": 42,
      "lines_added": 450,
      "test_coverage": "87%"
    }
  }
}
```

**Note on previous_stage_context**: Contains Dev→Reviewer handoff with:
- Implementation decisions made (verify against architecture plan)
- Files changed (focus review on these)
- Warnings (areas needing extra scrutiny)
- PR/change metadata
- May be `null` for legacy tasks without handoffs

---

## Step 1: Validate Work Package

```
1. Extract from work package:
   TASK_ID = work_package.task_id
   TASK_TITLE = work_package.task_title
   DESCRIPTION = work_package.task_description
   TAGS = work_package.task_tags

2. Validate task is reviewable:
   - Task should have ALL completion tags: Dev-Complete, Design-Complete, Test-Complete
   - Task should NOT have Review-In-Progress tag
   - Task should NOT have Review-Approved tag

3. IF task has Rework-Complete tag:
   - This is a re-review after rework
   - Note: REWORK_REVIEW = true

4. IF validation fails:
   Return VALIDATION_FAILURE result
```

---

## Step 2: Merge Develop Into Feature (Conflict Check)

```
1. Extract branch name from task description:
   - Find "**Branch:** `feature/{name}`" or "Branch: `feature/{name}`"
   - BRANCH = extracted branch name

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
   - Return CONFLICT_REJECTION result

5. IF merge clean:
   git push origin "$BRANCH"
   Continue to Step 3
```

---

## Step 3: Deep Code Review

### 3.0 Review Previous Stage Context (if available)
```
IF previous_stage_context exists:
  - Read key_decisions to understand what dev implemented
  - Use files_of_interest to focus the review
  - Check warnings for areas needing extra scrutiny
  - Use metadata (PR number, line counts) for context
```

Perform comprehensive review:

### 3a. Functional Completeness
```
- All sub-tasks checked off in task description
- PR changes match requirements
- No missing functionality
- Implementation matches architecture plan (compare against key_decisions)
```

### 3b. Code Quality
```
- Follows project conventions (check CLAUDE.md)
- No obvious logic errors
- Proper error handling
- No code duplication
- Clean, readable code
```

### 3c. Security
```
- No hardcoded secrets
- Proper input validation
- No injection vulnerabilities (SQL, XSS, etc.)
- Secure authentication/authorization (if applicable)
```

### 3d. Testing
```
- Tests exist for new functionality
- Test coverage is adequate
- Tests are passing (check CI if available)
- Edge cases considered
```

### 3e. Design (if UI changes)
```
- Matches design system
- Responsive/accessible
- Consistent with existing UI
```

Build a list of issues found, categorized by severity:
- CRITICAL: Security vulnerabilities, crashes, data loss (blocks even in YOLO mode)
- BLOCKER: Must fix before merge (standard mode), becomes WARNING in YOLO mode
- WARNING: Should fix, but not blocking
- SUGGESTION: Nice to have

---

## Step 4: Make Decision and Return Result

### YOLO Mode Behavior

**If `workflow_mode == "yolo"`**: Be lenient and prioritize forward progress:
1. **ONLY CRITICAL issues block**: Security vulnerabilities, crash-causing bugs, data loss potential
2. **Demote BLOCKERs to WARNINGs**: Code quality, missing tests, convention violations → approve with warnings
3. **Document all issues**: Include everything in warnings/suggestions for future cleanup
4. **Always note YOLO approval**: Include "YOLO: Approved with X issues documented" in summary

This enables fully autonomous operation where code ships quickly. Issues are documented but don't block.

### Standard Mode Behavior (default)

### IF CRITICAL or BLOCKERS exist → Return REJECT result
### IF no CRITICAL and no BLOCKERS → Return APPROVE result

### Decision Logic

```
CRITICAL_ISSUES = issues WHERE severity == "CRITICAL"
BLOCKER_ISSUES = issues WHERE severity == "BLOCKER"

IF workflow_mode == "yolo":
  # YOLO: Only critical issues block
  IF CRITICAL_ISSUES.length > 0:
    Return REJECT result (critical issues only)
  ELSE:
    # Approve with all blockers demoted to warnings
    Return APPROVE result with blockers listed as warnings
    Include "YOLO: Approved with {N} issues documented" in summary
ELSE:
  # Standard: Critical and blockers both reject
  IF CRITICAL_ISSUES.length > 0 OR BLOCKER_ISSUES.length > 0:
    Return REJECT result
  ELSE:
    Return APPROVE result
```

---

## Required Output Format

Return ONLY a JSON object (no markdown, no explanation before/after):

### Review APPROVED (Standard Mode)

```json
{
  "success": true,
  "summary": "Review approved; ready for merge",
  "joan_actions": {
    "add_tags": ["Review-Approved"],
    "remove_tags": ["Review-In-Progress", "Rework-Complete"],
    "add_comment": "ALS/1\nactor: reviewer\nintent: decision\naction: review-approve\ntags.add: [Review-Approved]\ntags.remove: [Review-In-Progress, Rework-Complete]\nsummary: Review approved; ready for merge.\ndetails:\n- {summary of review}\n- warnings (non-blocking, if any):\n  - {warning 1}",
    "move_to_column": null,
    "update_description": null
  },
  "stage_context": {
    "from_stage": "reviewer",
    "to_stage": "ops",
    "key_decisions": [
      "Code quality meets standards",
      "Tests passing with 87% coverage",
      "Security review passed - no vulnerabilities"
    ],
    "files_of_interest": [
      "src/context/AuthContext.tsx"
    ],
    "warnings": [
      "Consider splitting auth context in future refactor (non-blocking)"
    ],
    "metadata": {
      "review_duration_minutes": 45,
      "blockers_found": 0,
      "warnings_noted": 1
    }
  },
  "review_result": {
    "decision": "APPROVED",
    "blockers": [],
    "warnings": ["Consider adding edge case test"],
    "suggestions": ["Could improve variable naming in utils.ts"]
  },
  "worker_type": "reviewer",
  "task_id": "{task_id from work package}"
}
```

**Note on stage_context (approval)**: For Reviewer→Ops handoff:
- `key_decisions`: Review summary points for Ops awareness
- `files_of_interest`: Critical files that were reviewed
- `warnings`: Non-blocking observations for future reference
- `metadata`: Review metrics

### Review APPROVED (YOLO Mode - With Issues Documented)

In YOLO mode, approve even with non-critical blockers, but document them:

```json
{
  "success": true,
  "summary": "YOLO: Approved with 2 issues documented; proceeding to merge",
  "joan_actions": {
    "add_tags": ["Review-Approved"],
    "remove_tags": ["Review-In-Progress", "Rework-Complete"],
    "add_comment": "ALS/1\nactor: reviewer\nintent: decision\naction: yolo-review-approve\ntags.add: [Review-Approved]\ntags.remove: [Review-In-Progress, Rework-Complete]\nsummary: YOLO mode - approved with issues documented.\ndetails:\n- demoted_blockers (should fix later):\n  - Missing null check in auth.ts line 42\n  - Test coverage below 80%\n- warnings:\n  - Consider refactoring duplicate code\n- mode: yolo - prioritizing forward progress",
    "move_to_column": null,
    "update_description": null
  },
  "stage_context": {
    "from_stage": "reviewer",
    "to_stage": "ops",
    "key_decisions": [
      "YOLO: Approved despite 2 non-critical blockers",
      "Security review passed - no critical vulnerabilities"
    ],
    "files_of_interest": [
      "src/api/auth.ts:42 (needs null check)"
    ],
    "warnings": [
      "DEMOTED BLOCKER: Missing null check in auth.ts line 42",
      "DEMOTED BLOCKER: Test coverage below 80%",
      "Consider refactoring duplicate code"
    ],
    "metadata": {
      "review_mode": "yolo",
      "critical_issues": 0,
      "demoted_blockers": 2,
      "warnings_noted": 1
    }
  },
  "review_result": {
    "decision": "APPROVED",
    "mode": "yolo",
    "critical_issues": [],
    "demoted_blockers": ["Missing null check in auth.ts line 42", "Test coverage below 80%"],
    "warnings": ["Consider refactoring duplicate code"],
    "suggestions": ["Add JSDoc comments"]
  },
  "worker_type": "reviewer",
  "task_id": "{task_id from work package}"
}
```

### Review REJECTED (Blockers Found)

```json
{
  "success": true,
  "summary": "Review rejected; 2 blockers found",
  "joan_actions": {
    "add_tags": ["Rework-Requested", "Planned"],
    "remove_tags": ["Review-In-Progress", "Review-Approved", "Rework-Complete", "Dev-Complete", "Design-Complete", "Test-Complete"],
    "add_comment": "ALS/1\nactor: reviewer\nintent: decision\naction: review-rework\ntags.add: [Rework-Requested, Planned]\ntags.remove: [Review-In-Progress, Review-Approved, Rework-Complete, Dev-Complete, Design-Complete, Test-Complete]\nsummary: Changes requested; see details.\ndetails:\n- blockers:\n  - {issue 1}\n  - {issue 2}\n- warnings:\n  - {warning 1}\n- suggestions:\n  - {suggestion 1}",
    "move_to_column": "Development",
    "update_description": null
  },
  "stage_context": {
    "from_stage": "reviewer",
    "to_stage": "dev",
    "key_decisions": [
      "BLOCKER: Add null check in AuthContext.tsx line 42",
      "BLOCKER: Fix failing test in auth.test.ts line 67",
      "WARNING: Consider memoizing useAuth hook"
    ],
    "files_of_interest": [
      "src/context/AuthContext.tsx:42",
      "tests/auth.test.ts:67"
    ],
    "warnings": [
      "Code quality otherwise acceptable",
      "Security review passed"
    ],
    "metadata": {
      "blockers_count": 2,
      "warnings_count": 1
    }
  },
  "review_result": {
    "decision": "REJECTED",
    "blockers": ["Missing error handling in auth.ts", "Tests failing on CI"],
    "warnings": ["Consider refactoring duplicate code"],
    "suggestions": ["Add JSDoc comments"]
  },
  "worker_type": "reviewer",
  "task_id": "{task_id from work package}"
}
```

**Note on stage_context (rejection)**: For Reviewer→Dev handoff:
- `key_decisions`: BLOCKER and WARNING items as structured list (Dev uses this as rework checklist)
- `files_of_interest`: Specific file:line locations needing attention
- `warnings`: Positive observations to preserve (don't break what's working)
- `metadata`: Counts of blockers/warnings

### Merge Conflict Detected

```json
{
  "success": true,
  "summary": "Review blocked; merge conflicts with develop",
  "joan_actions": {
    "add_tags": ["Merge-Conflict", "Rework-Requested", "Planned"],
    "remove_tags": ["Review-In-Progress", "Review-Approved", "Dev-Complete", "Design-Complete", "Test-Complete"],
    "add_comment": "ALS/1\nactor: reviewer\nintent: decision\naction: review-conflict\ntags.add: [Merge-Conflict, Rework-Requested, Planned]\ntags.remove: [Review-In-Progress, Review-Approved, Dev-Complete, Design-Complete, Test-Complete]\nsummary: Merge conflicts with develop; resolve and rework.\ndetails:\n- conflicting files:\n  - {file1}\n  - {file2}",
    "move_to_column": "Development",
    "update_description": null
  },
  "review_result": {
    "decision": "BLOCKED",
    "conflict_files": ["src/api/auth.ts", "src/utils/helpers.ts"]
  },
  "worker_type": "reviewer",
  "task_id": "{task_id from work package}"
}
```

### Validation Failure

```json
{
  "success": false,
  "summary": "Task validation failed: missing completion tags",
  "joan_actions": {
    "add_tags": [],
    "remove_tags": [],
    "add_comment": "ALS/1\nactor: reviewer\nintent: failure\naction: review-validation-failed\ntags.add: []\ntags.remove: []\nsummary: Task validation failed; cannot review.\ndetails:\n- reason: {specific validation failure}",
    "move_to_column": null,
    "update_description": null
  },
  "errors": ["Task missing required Dev-Complete tag"],
  "worker_type": "reviewer",
  "task_id": "{task_id from work package}"
}
```

---

## Review Checklist Reference

| Category | Check | Severity | YOLO Behavior |
|----------|-------|----------|---------------|
| **Security** | No hardcoded secrets | CRITICAL | Always blocks |
| **Security** | No injection vulnerabilities | CRITICAL | Always blocks |
| **Security** | Secure auth (if applicable) | CRITICAL | Always blocks |
| **Functional** | No crash-causing bugs | CRITICAL | Always blocks |
| **Functional** | No data loss potential | CRITICAL | Always blocks |
| **Functional** | All sub-tasks complete | BLOCKER | → WARNING |
| **Functional** | PR matches requirements | BLOCKER | → WARNING |
| **Code** | No logic errors | BLOCKER | → WARNING |
| **Testing** | Tests passing | BLOCKER | → WARNING |
| **Code** | Follows conventions | WARNING | Pass |
| **Code** | Proper error handling | WARNING | Pass |
| **Testing** | Tests exist | WARNING | Pass |
| **Design** | Matches design system | WARNING | Pass |

**CRITICAL** = Blocks in ALL modes (security, crashes, data loss)
**BLOCKER** = Blocks in standard mode, demoted to WARNING in YOLO mode

---

## Constraints

- **Return ONLY JSON** - No explanation text before or after
- Single task only - review and exit
- Always merge develop first (conflict check)
- Never merge PRs (Ops does that)
- Be thorough but fair - focus on real issues
- Note: Coordinator will add Review-In-Progress tag before dispatching

---

Now process the work package provided in the prompt and return your JSON result.
