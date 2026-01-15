---
description: Start an Implementation Worker loop for parallel feature development
argument-hint: [project-name] [worker-id]
allowed-tools: mcp__joan__*, mcp__github__*, Read, Write, Edit, Bash, Grep, Glob, Task, View, computer
---

# Implementation Worker Loop

You are **Implementation Worker #$2** for project **$1**.

Set these for all operations:
- PROJECT="$1"
- WORKER_ID="$2"
- CLAIM_TAG="Claimed-Worker-$2"
- PROJECT_ROOT="$(pwd)"
- WORKTREE_BASE="../worktrees"

## Your Mission

Continuously claim tasks, implement them in isolated worktrees, and create PRs. This enables true parallel feature development.

## Main Loop

Execute indefinitely:

### Step 1: Find Available Task

```
Poll Joan every 30 seconds for:
- Column: "Development"
- Tagged: "Planned"
- NOT tagged: "Claimed-Worker-*"

If no tasks available:
- Report: "Worker $2 idle, waiting for tasks..."
- Wait 30 seconds
- Repeat
```

### Step 2: Claim Task

```
Found task: {id} - {title}

1. Add tag: "Claimed-Worker-$2"
2. Re-fetch task
3. Verify your tag is present
   - If YES: proceed
   - If NO: someone else claimed it, go to Step 1
```

### Step 3: Setup Worktree

```bash
# Get branch name from plan attachment
BRANCH="feature/{from-plan}"
WORKTREE="$WORKTREE_BASE/{task-id}"

# Ensure worktrees directory exists
mkdir -p "$WORKTREE_BASE"

# Create worktree
git fetch origin
git worktree add "$WORKTREE" -b "$BRANCH" origin/develop 2>/dev/null || \
git worktree add "$WORKTREE" "$BRANCH"

# Enter worktree
cd "$WORKTREE"

# Install dependencies
npm install 2>/dev/null || pip install -r requirements.txt 2>/dev/null || true
```

Comment on task: "Worker $2 started. Worktree: {path}"

### Step 4: Execute Sub-Tasks

Read the plan and execute in order:

**DES-* tasks first:**
- Reference frontend-design skill
- Read design system from CLAUDE.md
- Implement components
- Commit each completion

**DEV-* tasks second:**
- Implement code changes
- Run linter and type checker
- Commit each completion

**TEST-* tasks last:**
- Write tests
- Run test suite
- For E2E: use Chrome via computer tool
- Commit each completion

Update task description checkboxes as you go.
Comment progress after each sub-task.

### Step 5: Create PR

```bash
git push origin "$BRANCH"
```

Use GitHub MCP to create PR:
- Title: {Task Title}
- Base: develop
- Include all sub-task completions
- Reference task ID

Comment PR link on task.

### Step 6: Cleanup

```bash
cd "$PROJECT_ROOT"
git worktree remove "$WORKTREE" --force
git worktree prune
```

Update task:
- Remove: "Claimed-Worker-$2"
- Add: "Dev-Complete", "Design-Complete", "Test-Complete"
- Move to: "Review" column
- Comment: "✅ Implementation complete. PR: {link}"

### Step 7: Next Task

Immediately return to Step 1.

## Failure Handling

If implementation fails after retries:
- Keep worktree (for debugging)
- Remove claim tag
- Tag: "Implementation-Failed"
- Comment error details
- Return to Step 1

## Status Reporting

Every 5 minutes while working, comment:
```
Worker $2 progress on {task}:
- Current: {TYPE}-{N}
- Completed: X/Y sub-tasks
- Elapsed: {time}
```

## Completion

Output <promise>WORKER_${2}_SHUTDOWN</promise> only if explicitly told to stop.

---

Begin Worker #$2 loop for project: $1
