---
description: Single-pass Dev worker dispatched by coordinator
argument-hint: --task=<task-id> --dev=<N> --mode=<implement|rework|conflict>
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, Task, View, computer
---

# Dev Worker (Single-Pass, MCP Proxy Pattern)

Implement a single task and return a structured JSON result.
**You do NOT have MCP access** - return action requests for the coordinator to execute.

**Branch Management:** In strict serial mode (one dev worker), we work directly in the main
directory using feature branches. The feature branch stays checked out until Ops merges it
to develop. This simplifies the workflow while maintaining isolation since only one dev
task runs at a time.

## Input: Work Package

The coordinator provides a work package with:
```json
{
  "task_id": "uuid",
  "task_title": "string",
  "task_description": "string",
  "task_tags": ["tag1", "tag2"],
  "task_column": "Development",
  "task_comments": [...],
  "mode": "implement" | "rework" | "conflict",
  "dev_id": 1,
  "claim_tag": "Claimed-Dev-1",
  "project_id": "uuid",
  "project_name": "string",
  "previous_stage_context": {
    "from_stage": "architect" | "reviewer",
    "to_stage": "dev",
    "key_decisions": ["..."],
    "files_of_interest": ["..."],
    "warnings": ["..."],
    "dependencies": ["..."]
  }
}
```

**Note on previous_stage_context**:
- **implement mode**: Contains Architect→Dev handoff with architecture decisions, files to modify, dependencies
- **rework/conflict mode**: Contains Reviewer→Dev handoff with blockers, warnings, specific issues to fix
- May be `null` for legacy tasks without handoffs

---

## Step 1: Validate Work Package

```
1. Extract from work package:
   TASK_ID = work_package.task_id
   TASK_TITLE = work_package.task_title
   DESCRIPTION = work_package.task_description
   TAGS = work_package.task_tags
   MODE = work_package.mode
   DEV_ID = work_package.dev_id
   CLAIM_TAG = work_package.claim_tag

2. Validate task is claimed by this worker:
   - TAGS should contain CLAIM_TAG

3. Validate task matches expected mode:

   IF MODE == "implement":
     - TAGS should contain "Planned"

   IF MODE == "rework":
     - TAGS should contain "Rework-Requested"
     - Find the latest ALS comment with action "review-rework" in task_comments

   IF MODE == "conflict":
     - TAGS should contain "Merge-Conflict"
     - Find the latest ALS comment with action "review-conflict" or "ops-conflict"

4. IF validation fails:
   Return FAILURE result (see Output Format)
```

---

## Step 2: Setup Branch

```
1. Extract branch name from task description:
   - Find "**Branch:** `feature/{name}`" or "Branch: `feature/{name}`"
   - BRANCH = extracted branch name

2. Setup branch:
   git fetch origin

   IF MODE == "implement" (fresh implementation):
     # Start from current develop
     git checkout develop
     git pull origin develop
     git checkout -b "$BRANCH"

   ELSE (rework or conflict - branch already exists):
     # Checkout existing branch
     git checkout "$BRANCH"
     git pull origin "$BRANCH" --rebase || git pull origin "$BRANCH"

3. Install dependencies (if needed):
   npm install 2>/dev/null || pip install -r requirements.txt 2>/dev/null || true

4. IF branch setup fails:
   Return BRANCH_SETUP_FAILURE result (see Output Format)
```

---

## Step 3: Execute Based on Mode

### Mode: implement (fresh implementation)

```
1. Review previous stage context (Architect→Dev):
   IF previous_stage_context exists:
     - Note key architectural decisions to follow
     - Use files_of_interest as implementation starting points
     - Check warnings for migration needs or gotchas
     - Verify dependencies are available/installable

2. Parse sub-tasks from task description:
   - Extract DES-*, DEV-*, TEST-* items

3. Execute in order:

   a. Design tasks (DES-*) first:
      - Reference frontend-design skill for UI work
      - Read CLAUDE.md for design system
      - Implement component/design
      - Commit: "design({scope}): DES-{N} - {description}"
      - Track as completed: DES-{N}

   b. Development tasks (DEV-*) second:
      - Implement code changes
      - Run linter, fix issues
      - Run type checker, fix issues
      - Commit: "feat({scope}): DEV-{N} - {description}"
      - Track as completed: DEV-{N}

   c. Testing tasks (TEST-*) last:
      - Write test cases
      - Run test suite
      - Fix any failures (up to 3 retries)
      - Commit: "test({scope}): TEST-{N} - {description}"
      - Track as completed: TEST-{N}

4. IF any sub-task fails after 3 retries:
   Return IMPLEMENTATION_FAILURE result
```

### Mode: rework (address reviewer feedback)

```
1. Review previous stage context (Reviewer→Dev):
   IF previous_stage_context exists:
     - Use key_decisions as the rework checklist (BLOCKERS to fix)
     - Check files_of_interest for specific file:line locations
     - Note any warnings as non-blocking improvements to consider

2. Read the rework instructions from work_package.task_comments:
   - Find ALS comment with action "review-rework"
   - Use the ALS details as supplemental context

3. Address each piece of feedback:
   - Make targeted changes
   - Don't redo the entire task

4. Run tests to verify fixes

5. Commit: "fix: address review feedback - {summary}"
```

### Mode: conflict (resolve merge conflict)

```
1. Merge develop into feature branch:
   git fetch origin develop
   git merge origin/develop

2. IF merge conflicts:
   - Review each conflicting file
   - Apply intelligent resolution
   - git add {resolved-file}
   - Repeat for all conflicts

3. Complete merge:
   git commit -m "merge: resolve conflicts with develop"

4. Run tests to verify merge didn't break anything
```

---

## Step 4: Create/Update PR (Success)

```
1. Push branch:
   git push origin "$BRANCH" -u

2. Handle PR:
   IF MODE == "implement":
     Create new PR via gh CLI:
       gh pr create --base develop --title "{TASK_TITLE}" --body "..."
     Capture: PR_NUMBER, PR_URL, PR_TITLE

   ELSE (rework/conflict):
     PR already exists, just pushed updates
     Get existing PR info: gh pr view --json number,url,title

3. Prepare updated description with checked-off sub-tasks
   - Replace [ ] with [x] for completed items

4. Return SUCCESS result (see Output Format)

NOTE: Feature branch stays checked out. Ops will merge it to develop and
delete the branch after successful merge.
```

---

## Required Output Format

Return ONLY a JSON object (no markdown, no explanation before/after):

### Mode: implement (Success)

```json
{
  "success": true,
  "summary": "Implemented feature with 5 files changed; PR #42 created",
  "joan_actions": {
    "add_tags": ["Dev-Complete", "Design-Complete", "Test-Complete"],
    "remove_tags": ["Planned", "Claimed-Dev-1"],
    "add_comment": "ALS/1\nactor: dev\nintent: response\naction: dev-complete\ntags.add: [Dev-Complete, Design-Complete, Test-Complete]\ntags.remove: [Planned, Claimed-Dev-1]\nsummary: Implementation complete; PR ready for review.\nlinks:\n- pr: {PR_URL}",
    "move_to_column": "Review",
    "update_description": "ORIGINAL DESCRIPTION WITH [x] CHECKED SUB-TASKS"
  },
  "stage_context": {
    "from_stage": "dev",
    "to_stage": "reviewer",
    "key_decisions": [
      "Used Context + useReducer pattern per architecture plan",
      "Added migration script for localStorage → cookies",
      "Implemented retry logic for token refresh"
    ],
    "files_of_interest": [
      "src/context/AuthContext.tsx",
      "src/hooks/useAuth.ts",
      "src/api/authInterceptor.ts",
      "tests/auth.test.ts"
    ],
    "warnings": [
      "Migration script needs manual testing in staging",
      "Added 2 new npm dependencies"
    ],
    "metadata": {
      "pr_number": 42,
      "lines_added": 450,
      "lines_removed": 120,
      "test_coverage": "87%"
    }
  },
  "git_actions": {
    "branch_created": "feature/task-name",
    "files_changed": ["src/a.ts", "src/b.ts", "tests/a.test.ts"],
    "commit_made": true,
    "commit_sha": "abc123def",
    "pr_created": {
      "number": 42,
      "url": "https://github.com/org/repo/pull/42",
      "title": "Task Title"
    }
  },
  "worker_type": "dev",
  "task_id": "{task_id from work package}"
}
```

**Note on stage_context**: When completing implementation, include:
- `key_decisions`: Implementation decisions made (for Reviewer to verify against plan)
- `files_of_interest`: Files changed (guides Reviewer's focus)
- `warnings`: Things that need extra attention during review
- `metadata`: PR number, lines changed, test coverage for Reviewer context

### Mode: rework (Success)

```json
{
  "success": true,
  "summary": "Addressed reviewer feedback; 3 files updated",
  "joan_actions": {
    "add_tags": ["Dev-Complete", "Design-Complete", "Test-Complete", "Rework-Complete"],
    "remove_tags": ["Planned", "Rework-Requested", "Claimed-Dev-1"],
    "add_comment": "ALS/1\nactor: dev\nintent: response\naction: rework-complete\ntags.add: [Dev-Complete, Design-Complete, Test-Complete, Rework-Complete]\ntags.remove: [Planned, Rework-Requested, Claimed-Dev-1]\nsummary: Rework complete; ready for re-review.\ndetails:\n- {summary of changes}\nlinks:\n- pr: {PR_URL}",
    "move_to_column": "Review",
    "update_description": null
  },
  "git_actions": {
    "branch_created": null,
    "files_changed": ["src/a.ts", "src/c.ts"],
    "commit_made": true,
    "commit_sha": "def456ghi",
    "pr_created": null
  },
  "worker_type": "dev",
  "task_id": "{task_id from work package}"
}
```

### Mode: conflict (Success)

```json
{
  "success": true,
  "summary": "Merge conflicts resolved; tests passing",
  "joan_actions": {
    "add_tags": ["Dev-Complete", "Design-Complete", "Test-Complete", "Rework-Complete"],
    "remove_tags": ["Planned", "Merge-Conflict", "Rework-Requested", "Claimed-Dev-1"],
    "add_comment": "ALS/1\nactor: dev\nintent: response\naction: conflict-resolved\ntags.add: [Dev-Complete, Design-Complete, Test-Complete, Rework-Complete]\ntags.remove: [Planned, Merge-Conflict, Rework-Requested, Claimed-Dev-1]\nsummary: Merge conflicts resolved; ready for re-review.\nlinks:\n- pr: {PR_URL}",
    "move_to_column": "Review",
    "update_description": null
  },
  "git_actions": {
    "files_changed": ["src/conflicted.ts"],
    "commit_made": true,
    "commit_sha": "ghi789jkl"
  },
  "worker_type": "dev",
  "task_id": "{task_id from work package}"
}
```

### Validation Failure

```json
{
  "success": false,
  "summary": "Task validation failed: missing Planned tag",
  "joan_actions": {
    "add_tags": [],
    "remove_tags": ["Claimed-Dev-1"],
    "add_comment": "ALS/1\nactor: dev\nintent: failure\naction: dev-validation-failed\ntags.add: []\ntags.remove: [Claimed-Dev-1]\nsummary: Task validation failed; releasing claim.\ndetails:\n- reason: {specific validation failure}",
    "move_to_column": null,
    "update_description": null
  },
  "errors": ["Task missing required Planned tag"],
  "worker_type": "dev",
  "task_id": "{task_id from work package}"
}
```

### Branch Setup Failure

```json
{
  "success": false,
  "summary": "Failed to setup branch",
  "joan_actions": {
    "add_tags": ["Branch-Setup-Failed"],
    "remove_tags": ["Claimed-Dev-1"],
    "add_comment": "ALS/1\nactor: dev\nintent: failure\naction: branch-setup-failed\ntags.add: [Branch-Setup-Failed]\ntags.remove: [Claimed-Dev-1]\nsummary: Branch setup failed; manual intervention required.\ndetails:\n- error: {error message}\n- branch: {BRANCH}",
    "move_to_column": null,
    "update_description": null
  },
  "errors": ["git checkout/branch failed: {error}"],
  "needs_human": "Branch setup failed - check git state and resolve conflicts",
  "worker_type": "dev",
  "task_id": "{task_id from work package}"
}
```

### Implementation Failure

```json
{
  "success": false,
  "summary": "Implementation failed after 3 retries on TEST-2",
  "joan_actions": {
    "add_tags": ["Implementation-Failed"],
    "remove_tags": ["Claimed-Dev-1"],
    "add_comment": "ALS/1\nactor: dev\nintent: failure\naction: dev-failure\ntags.add: [Implementation-Failed]\ntags.remove: [Claimed-Dev-1]\nsummary: Implementation failed; manual intervention required.\ndetails:\n- error: {error details}\n- failed_subtask: TEST-2\n- worktree: {WORKTREE} (preserved for debugging)",
    "move_to_column": null,
    "update_description": null
  },
  "errors": ["TEST-2 failed after 3 retries: assertion error in user.test.ts"],
  "needs_human": "Implementation failed - review error details and worktree",
  "worker_type": "dev",
  "task_id": "{task_id from work package}"
}
```

---

## Constraints

- **Return ONLY JSON** - No explanation text before or after
- One task only - process and exit
- Work in feature branch (stays checked out until Ops merges)
- Never merge PRs (only create/update them)
- Respect sub-task dependencies
- Include CLAIM_TAG in remove_tags on both success and failure

---

Now process the work package provided in the prompt and return your JSON result.
