---
description: Single-pass Dev worker dispatched by coordinator
argument-hint: --task=<task-id> --dev=<N> --mode=<implement|rework|conflict>
allowed-tools: mcp__joan__*, mcp__github__*, Read, Write, Edit, Bash, Grep, Glob, Task, View, computer
---

# Dev Worker (Single-Pass)

Implement a single task assigned by the coordinator. The coordinator has already claimed this task with your Claimed-Dev-N tag before dispatching.

## Arguments

- `--task=<ID>` - Task ID to process (REQUIRED)
- `--dev=<N>` - Dev worker number (REQUIRED)
- `--mode=<implement|rework|conflict>` - Processing mode (REQUIRED)
  - `implement`: Fresh implementation of a Planned task
  - `rework`: Address Rework-Requested feedback
  - `conflict`: Resolve Merge-Conflict with develop

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
DEV_ID = value from --dev
MODE = value from --mode
CLAIM_TAG = "Claimed-Dev-{DEV_ID}"
PROJECT_ROOT = pwd
WORKTREE_BASE = "../worktrees"
```

If any argument missing, report error and exit.

---

## Step 1: Fetch and Validate Task

```
1. Fetch task using get_task(TASK_ID)

2. Validate task is claimed by this worker:
   - Task should have CLAIM_TAG

3. Validate task matches expected mode:

   IF MODE == "implement":
     - Task should be in "Development" column
     - Task should have "Planned" tag

   IF MODE == "rework":
     - Task should be in "Development" column
     - Task should have "Rework-Requested" tag
     - Read the latest ALS comment with action "review-rework" for instructions

   IF MODE == "conflict":
     - Task should be in "Development" column
     - Task should have "Merge-Conflict" tag
     - Read the latest ALS comment with action "review-conflict" or "ops-conflict"

4. IF validation fails:
   Report: "Task {TASK_ID} not valid for Dev #{DEV_ID} mode {MODE}"
   - Remove CLAIM_TAG (release task)
   EXIT
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

4. Comment (ALS breadcrumb):
   "ALS/1
   actor: dev
   intent: status
   action: dev-start
   tags.add: []
   tags.remove: []
   summary: Dev #{DEV_ID} started work.
   details:
   - mode: {MODE}
   - branch: {BRANCH}
   - worktree: {WORKTREE}"
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
      - Check off in description: [x] DES-{N}

   b. Development tasks (DEV-*) second:
      - Implement code changes
      - Run linter, fix issues
      - Run type checker, fix issues
      - Commit: "feat({scope}): DEV-{N} - {description}"
      - Check off in description: [x] DEV-{N}

   c. Testing tasks (TEST-*) last:
      - Write test cases
      - Run test suite
      - Fix any failures (up to 3 retries)
      - Commit: "test({scope}): TEST-{N} - {description}"
      - Check off in description: [x] TEST-{N}

3. IF any sub-task fails after 3 retries:
   Go to FAILURE HANDLING
```

### Mode: rework (address reviewer feedback)

```
1. Read the rework instructions from the latest ALS comment:
   - Find action "review-rework"
   - Use the ALS details as the rework checklist

2. Address each piece of feedback:
   - Make targeted changes
   - Don't redo the entire task
   - Check off items as completed

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
     Create new PR via GitHub MCP:
     - Title: {Task Title}
     - Base: develop
     - Body: |
       ## Summary
       {Task description}

       ## Sub-Tasks Completed
       - [x] DES-1: ...
       - [x] DEV-1: ...
       - [x] TEST-1: ...

       ## Testing
       - All tests passing

       Task: #{TASK_ID}

    Attach PR link as task resource (type: link)

   ELSE (rework/conflict):
     PR already exists, just pushed updates

3. Cleanup worktree:
   cd "$PROJECT_ROOT"
   git worktree remove "$WORKTREE" --force
   git worktree prune

4. Update tags:
   - Remove: CLAIM_TAG
   - Remove: "Planned" (if present)
   - Remove: "Rework-Requested" (if present)
   - Remove: "Merge-Conflict" (if present)
   - Add: "Dev-Complete", "Design-Complete", "Test-Complete"
   - Add: "Rework-Complete" (if MODE was rework or conflict)

5. Move task to "Review" column

6. Comment (ALS breadcrumb):
   IF MODE == "implement":
     "ALS/1
     actor: dev
     intent: response
     action: dev-complete
     tags.add: [Dev-Complete, Design-Complete, Test-Complete]
     tags.remove: [Planned, {CLAIM_TAG}]
     summary: Implementation complete; PR ready for review.
     links:
     - pr: {PR_URL}"

   IF MODE == "rework":
     "ALS/1
     actor: dev
     intent: response
     action: rework-complete
     tags.add: [Dev-Complete, Design-Complete, Test-Complete, Rework-Complete]
     tags.remove: [Planned, Rework-Requested, {CLAIM_TAG}]
     summary: Rework complete; ready for re-review.
     details:
     - {summary of changes}
     links:
     - pr: {PR_URL}"

   IF MODE == "conflict":
     "ALS/1
     actor: dev
     intent: response
     action: conflict-resolved
     tags.add: [Dev-Complete, Design-Complete, Test-Complete, Rework-Complete]
     tags.remove: [Planned, Merge-Conflict, Rework-Requested, {CLAIM_TAG}]
     summary: Merge conflicts resolved; ready for re-review.
     links:
     - pr: {PR_URL}"

7. Report: "Dev #{DEV_ID} completed '{title}' (mode: {MODE})"
```

---

## Step 5: Failure Handling

```
IF implementation cannot complete:

1. Keep worktree (for debugging)

2. Update tags:
   - Remove: CLAIM_TAG
   - Add: "Implementation-Failed"

3. Comment (ALS breadcrumb):
   "ALS/1
   actor: dev
   intent: failure
   action: dev-failure
   tags.add: [Implementation-Failed]
   tags.remove: [{CLAIM_TAG}]
   summary: Implementation failed; manual intervention required.
   details:
   - error: {error details}
   - worktree: {WORKTREE}"

4. Report: "Dev #{DEV_ID} FAILED on '{title}': {reason}"

EXIT
```

---

## Constraints

- One task only - process and exit
- Always work in worktree, never main repo
- Always clean up worktree on success
- Never merge PRs (only create/update them)
- Respect sub-task dependencies
- Coordinator claims task before dispatch - verify claim exists

Begin processing task: $TASK_ID as Dev #$DEV_ID with mode: $MODE
