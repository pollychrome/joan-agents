---
description: Single-pass Dev worker dispatched by coordinator
argument-hint: --task=<task-id> --dev=<N> --mode=<implement|rework|conflict>
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, Task, View, computer
---

# Dev Worker (Single-Pass, MCP Proxy Pattern)

Implement a single task and return a structured JSON result.
**You do NOT have MCP access** - return action requests for the coordinator to execute.

**CRITICAL: This command MUST be invoked by the dispatcher - not bypassed with custom prompts.**
This command creates a WORKTREE for isolated development. Without worktrees, multiple dev workers
will conflict by switching branches in the same directory.

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
  "project_root": "/path/to/project",
  "worktree_base": "../worktrees"
}
```

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
   PROJECT_ROOT = work_package.project_root
   WORKTREE_BASE = work_package.worktree_base

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

## Step 2: Setup Worktree

```
1. Extract branch name from task description:
   - Find "**Branch:** `feature/{name}`" or "Branch: `feature/{name}`"
   - BRANCH = extracted branch name

2. Setup worktree:
   WORKTREE = "{WORKTREE_BASE}/{TASK_ID}"

   IF worktree already exists (rework/conflict case):
     cd "$WORKTREE"
     git fetch origin
     git checkout "$BRANCH"
     git pull origin "$BRANCH" --rebase || git pull origin "$BRANCH"

   ELSE (fresh implementation):
     mkdir -p "$WORKTREE_BASE"
     git fetch origin
     git worktree add "$WORKTREE" -b "$BRANCH" origin/develop 2>/dev/null || \
     git worktree add "$WORKTREE" "$BRANCH"

3. Enter worktree and install deps:
   cd "$WORKTREE"
   npm install 2>/dev/null || pip install -r requirements.txt 2>/dev/null || true

4. IF worktree creation fails:
   Return WORKTREE_FAILURE result (see Output Format)
```

---

## Step 3: Execute Based on Mode

### Mode: implement (fresh implementation)

```
1. Parse sub-tasks from task description:
   - Extract DES-*, DEV-*, TEST-* items

2. Execute in order:

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

3. IF any sub-task fails after 3 retries:
   Return IMPLEMENTATION_FAILURE result
```

### Mode: rework (address reviewer feedback)

```
1. Read the rework instructions from work_package.task_comments:
   - Find ALS comment with action "review-rework"
   - Use the ALS details as the rework checklist

2. Address each piece of feedback:
   - Make targeted changes
   - Don't redo the entire task

3. Run tests to verify fixes

4. Commit: "fix: address review feedback - {summary}"
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

## Step 4: Create/Update PR and Cleanup (Success)

```
1. Push branch:
   git push origin "$BRANCH"

2. Handle PR:
   IF MODE == "implement":
     Create new PR via gh CLI:
       gh pr create --base develop --title "{TASK_TITLE}" --body "..."
     Capture: PR_NUMBER, PR_URL, PR_TITLE

   ELSE (rework/conflict):
     PR already exists, just pushed updates
     Get existing PR info: gh pr view --json number,url,title

3. Cleanup worktree:
   cd "$PROJECT_ROOT"
   git worktree remove "$WORKTREE" --force
   git worktree prune

4. Prepare updated description with checked-off sub-tasks
   - Replace [ ] with [x] for completed items

5. Return SUCCESS result (see Output Format)
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

### Worktree Failure

```json
{
  "success": false,
  "summary": "Failed to create worktree",
  "joan_actions": {
    "add_tags": ["Worktree-Failed"],
    "remove_tags": ["Claimed-Dev-1"],
    "add_comment": "ALS/1\nactor: dev\nintent: failure\naction: worktree-failed\ntags.add: [Worktree-Failed]\ntags.remove: [Claimed-Dev-1]\nsummary: Worktree creation failed; manual intervention required.\ndetails:\n- error: {error message}\n- branch: {BRANCH}",
    "move_to_column": null,
    "update_description": null
  },
  "errors": ["git worktree add failed: {error}"],
  "needs_human": "Worktree creation failed - check git state and disk space",
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
- Always work in worktree, never main repo
- Always clean up worktree on success (keep on failure)
- Never merge PRs (only create/update them)
- Respect sub-task dependencies
- Include CLAIM_TAG in remove_tags on both success and failure

---

Now process the work package provided in the prompt and return your JSON result.
