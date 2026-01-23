---
description: Initialize Joan agent configuration for this repository
allowed-tools: mcp__joan__*, Read, Write, AskUserQuestion
---

# Initialize Joan Agent Configuration

You are setting up the Joan multi-agent system for this repository.

## Step 1: Check Existing Config

First, check if `.joan-agents.json` already exists in the project root.

```
Read .joan-agents.json
```

If it exists, ask the user if they want to reconfigure or keep existing settings.

## Step 2: Fetch Available Projects

Use Joan MCP to list all available projects:

```
mcp__joan__list_projects()
```

Present the projects to the user and ask them to select one.

## Step 3: Gather Configuration

Ask the user for their preferences using AskUserQuestion:

1. **Model**: Which Claude model should agents use? (default: opus)
   - `opus` - Best instruction-following, most thorough (recommended for complex workflows)
   - `sonnet` - Faster, lower cost, good for simpler tasks
   - `haiku` - Fastest, lowest cost, best for very simple operations

2. **Workflow Mode**: Which mode should agents operate in? (default: standard)

   Use AskUserQuestion with options:

   - `standard` - Human approval required at critical gates **(RECOMMENDED)**
     * Architect creates plan → Human adds Plan-Approved tag → Architect finalizes
     * Reviewer approves → Human adds Ops-Ready tag → Ops merges
     * Best for: Production systems, high-risk changes, learning environments
     * Ensures human oversight at critical decision points

   - `yolo` - Fully autonomous, auto-approve all gates **(EXPERIMENTAL)**
     * Architect creates plan → Auto-approved immediately
     * Reviewer approves → Auto-merge immediately
     * Best for: Internal tools, prototyping, trusted codebases with strong tests
     * ⚠️ **WARNING**: No human review means bad plans get implemented and bad code gets merged

3. **Polling Interval**: How often should agents poll for new work? **(RECOMMENDED: 1 minute)**

   With strict serial pipeline, faster polling = better responsiveness:

   - `1 minute` - Best responsiveness, minimal token overhead (~500-1000 tokens/poll) **(RECOMMENDED)**
   - `3 minutes` - Balanced between responsiveness and cost
   - `5 minutes` - Legacy default, slower but lower token usage
   - `10 minutes` - Very slow, only for low-priority projects

   **Note:** Polling cost is negligible (~1000 tokens/poll). With dev work taking 10-30 minutes, 1-minute polling provides 80-95% better responsiveness.

4. **Max Idle Polls**: How many empty polls before agent shuts down? (default: 12)

   With 1-minute polling: 12 polls = 12 minutes of idle time before shutdown

5. **Enabled Agents**: Which agents should be enabled?

**Note:** Dev count is always 1 (strict serial mode - prevents merge conflicts and stale plans).

## Step 4: Set Up Project Structure

After the user selects a project, configure it for the agentic workflow.

### 4a: Configure Kanban Columns

The workflow requires these columns in order. Automatically create any that are missing.

**Required Columns:**

| Column | Default Status | Color | Position |
|--------|---------------|-------|----------|
| To Do | todo | #6B7280 (gray) | 0 |
| Analyse | analyse | #8B5CF6 (purple) | 1 |
| Development | in_progress | #3B82F6 (blue) | 2 |
| Review | review | #F59E0B (amber) | 3 |
| Deploy | deploy | #10B981 (emerald) | 4 |
| Done | done | #22C55E (green) | 5 |

**Step 1: Fetch existing columns**
```
columns = mcp__joan__list_columns(project_id)
```

**Step 2: Check and create missing columns**

For each required column (in order):
1. Check if it exists (case-insensitive match on name)
2. If missing, create it:
   ```
   mcp__joan__create_column(project_id, name, default_status, color, position)
   ```
3. Track which columns were created vs already existed

**Step 3: Report column configuration**

```
✓ Kanban Columns Configured

Created: Analyse, Deploy
Existing: To Do, Development, Review, Done
Total: 6 workflow columns ready
```

If all columns already existed:
```
✓ Kanban Columns Configured

All 6 workflow columns already exist.
```

### 4b: Create Workflow Tags

The workflow uses tags for agent communication. Create any missing tags:

**Required Tags:**
| Tag | Color | Purpose |
|-----|-------|---------|
| `Ready` | #22C55E (green) | Task requirements complete, ready for planning |
| `Needs-Clarification` | #F59E0B (amber) | Task has unanswered questions |
| `Clarification-Answered` | #10B981 (emerald) | Human answered BA questions (tag-trigger) |
| `Plan-Pending-Approval` | #8B5CF6 (purple) | Plan created, awaiting human approval |
| `Plan-Approved` | #6366F1 (indigo) | Human approved plan (tag-trigger) |
| `Plan-Rejected` | #F43F5E (rose) | Human rejected plan (tag-trigger) |
| `Planned` | #3B82F6 (blue) | Plan approved, available for devs |
| `Dev-Complete` | #22C55E (green) | All DEV sub-tasks done |
| `Design-Complete` | #3B82F6 (blue) | All DES sub-tasks done |
| `Test-Complete` | #8B5CF6 (purple) | All TEST sub-tasks pass |
| `Review-In-Progress` | #F59E0B (amber) | Reviewer is actively reviewing |
| `Review-Approved` | #14B8A6 (teal) | Reviewer approved for merge (tag-trigger) |
| `Ops-Ready` | #06B6D4 (cyan) | Human approved merge to develop (tag-trigger) |
| `Rework-Requested` | #EF4444 (red) | Reviewer found issues, needs fixes |
| `Rework-Complete` | #84CC16 (lime) | Dev finished rework (tag-trigger) |
| `Merge-Conflict` | #F97316 (orange) | Merge conflict detected |
| `Implementation-Failed` | #F43F5E (rose) | Dev couldn't complete (manual recovery) |
| `Branch-Setup-Failed` | #EC4899 (pink) | Branch setup failed (manual recovery) |
| `Claimed-Dev-1` | #0EA5E9 (sky) | Dev worker claim tag (strict serial: only 1) |

First, fetch existing tags:
```
mcp__joan__list_project_tags(project_id)
```

Then create any missing tags using:
```
mcp__joan__create_project_tag(project_id, name, color)
```

Report the tag setup:
```
✓ Project Tags Configured

Created: Ready, Planned, Needs-Clarification, ...
Existing: Dev-Complete, Test-Complete, ...
Total: 16 workflow tags ready
```

## Step 5: Configure Bash Permissions

The agents need permission to run git, npm, and test commands without prompting during the loop.

**Create or update `.claude/settings.local.json`** in the project root:

```
1. Check if .claude/settings.local.json exists
2. If exists, read current permissions
3. Merge required permissions (don't overwrite existing)
4. Write back the file
```

**Required permissions for autonomous operation:**

```json
{
  "permissions": {
    "allow": [
      "Bash(git fetch:*)",
      "Bash(git checkout:*)",
      "Bash(git merge:*)",
      "Bash(git pull:*)",
      "Bash(git push:*)",
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git branch:*)",
      "Bash(git status:*)",
      "Bash(git log:*)",
      "Bash(git diff:*)",
      "Bash(git reset:*)",
      "Bash(npm install:*)",
      "Bash(npm test:*)",
      "Bash(npm run:*)",
      "Bash(pip install:*)",
      "Bash(pytest:*)",
      "Bash(mkdir:*)",
      "Bash(cd:*)",
      "mcp__joan__*",
      "mcp__github__*"
    ]
  }
}
```

**Report the configuration:**

```
✓ Bash Permissions Configured

Added {N} permission rules to .claude/settings.local.json
Agents can now run git, npm, and test commands autonomously.
```

If permissions already existed:
```
✓ Bash Permissions Configured

All required permissions already present.
```

---

## Note: Agent Commands

**If you installed via the Claude Code plugin system** (recommended):
Agent commands are automatically available through the plugin. No additional setup needed.

```bash
# Plugin installation (one time, globally)
claude plugin marketplace add github:pollychrome/joan-agents
claude plugin install agents@alexbenson-joan-agents
```

**If you installed manually via symlinks** (legacy):
Agent commands should be symlinked from `~/joan-agents`. If not already done:

```bash
mkdir -p ~/.claude/commands
ln -sf ~/joan-agents/commands ~/.claude/commands/agents
```

---

## Step 6: Write Configuration

Create `.joan-agents.json` in project root with the user's selections:

```json
{
  "$schema": "./.claude/schemas/joan-agents.schema.json",
  "projectId": "{selected-project-uuid}",
  "projectName": "{selected-project-name}",
  "settings": {
    "model": "{opus|sonnet|haiku}",
    "mode": "{standard|yolo}",
    "pollingIntervalMinutes": {user-choice, default: 1},
    "maxIdlePolls": {user-choice, default: 12},
    "staleClaimMinutes": 120,
    "maxPollCyclesBeforeRestart": 10,
    "stuckStateMinutes": 120,
    "schedulerIntervalSeconds": 60,
    "schedulerStuckTimeoutSeconds": 3900,
    "schedulerMaxConsecutiveFailures": 3,
    "pipeline": {
      "baQueueDraining": true,
      "maxBaTasksPerCycle": 10
    },
    "workerTimeouts": {
      "ba": 10,
      "architect": 20,
      "dev": 60,
      "reviewer": 20,
      "ops": 15
    }
  },
  "agents": {
    "businessAnalyst": { "enabled": {true/false} },
    "architect": { "enabled": {true/false} },
    "reviewer": { "enabled": {true/false} },
    "ops": { "enabled": {true/false} },
    "devs": { "enabled": {true/false}, "count": 1 }
  }
}
```

**Note:** `devs.count` is always 1 to enforce strict serial mode.

## Step 7: Confirm Setup & Offer Tutorial

Report the configuration summary:

```
═══════════════════════════════════════════════════════════════
  Joan Agent Configuration Complete
═══════════════════════════════════════════════════════════════

Project: {name}
Model: {opus|sonnet|haiku}
Polling: Every {N} minutes
Auto-shutdown: After {N} idle polls ({calculated time})

Enabled Agents:
  • Business Analyst: {enabled/disabled}
  • Architect: {enabled/disabled}
  • Code Reviewer: {enabled/disabled}
  • Ops: {enabled/disabled}
  • Dev Worker: {enabled/disabled} (strict serial mode)

Project Structure:
  • Columns: {N} workflow columns configured
  • Tags: {N} workflow tags configured
  • Permissions: {N} bash rules configured for autonomous operation
  • Agent Commands: Available via plugin (or symlinks if legacy install)
═══════════════════════════════════════════════════════════════
```

Then ask if the user wants a workflow tutorial:

```
AskUserQuestion: "Would you like an interactive tutorial explaining how the agent workflow operates?"
Options:
  - "Yes, show me the tutorial"
  - "No, I'm ready to start"
```

If user selects tutorial, proceed to Step 8. Otherwise, show quick start commands and finish.

## Step 8: Interactive Workflow Tutorial (Optional)

Present the tutorial in interactive sections, pausing between each for questions.

### Section 1: The Big Picture

```
╔═══════════════════════════════════════════════════════════════╗
║  JOAN AGENT WORKFLOW - The Big Picture                        ║
╚═══════════════════════════════════════════════════════════════╝

Tasks flow through 6 columns, each managed by a specialized agent:

   To Do  →  Analyse  →  Development  →  Review  →  Deploy  →  Done
     │          │            │             │          │
     BA      Architect      Dev        Reviewer     Ops

Each agent has ONE job:
  • BA: Validates requirements are clear and complete
  • Architect: Creates detailed implementation plans
  • Dev: Implements the plan on feature branches
  • Reviewer: Deep code review, approves or requests changes
  • Ops: Merges approved code, tracks deployments
```

Ask: "Ready to learn about each agent's role? (Continue / Ask a question)"

### Section 2: Agent Roles

```
╔═══════════════════════════════════════════════════════════════╗
║  AGENT ROLES                                                  ║
╚═══════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────┐
│ 🔍 BUSINESS ANALYST (BA)                                     │
├─────────────────────────────────────────────────────────────┤
│ Watches: To Do column                                        │
│ Action:  Evaluates if requirements are complete              │
│ Output:  Adds "Ready" tag when task is clear                 │
│          Adds "Needs-Clarification" if questions remain      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 📐 ARCHITECT                                                 │
├─────────────────────────────────────────────────────────────┤
│ Watches: Analyse column (tasks with "Ready" tag)            │
│ Action:  Analyzes codebase, creates implementation plan      │
│ Output:  Detailed plan with sub-tasks (DES/DEV/TEST)        │
│          Requires YOUR approval via "Plan-Approved" tag      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 💻 DEV                                                       │
├─────────────────────────────────────────────────────────────┤
│ Watches: Development column (tasks with "Planned" tag)       │
│ Action:  Claims task, switches to feature branch, implements │
│ Output:  Pull request with all sub-tasks completed           │
│          Moves task to Review when done                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 🔎 REVIEWER                                                  │
├─────────────────────────────────────────────────────────────┤
│ Watches: Review column                                       │
│ Action:  Deep code review, security check, test validation   │
│ Output:  Adds Review-Approved or Rework-Requested tag        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 🚀 OPS                                                       │
├─────────────────────────────────────────────────────────────┤
│ Watches: Review column (Review-Approved), Deploy column      │
│ Action:  Merges PRs to develop, resolves conflicts           │
│ Output:  Moves task to Deploy, then Done when shipped        │
└─────────────────────────────────────────────────────────────┘
```

Ask: "Ready to learn how to run agents? (Continue / Ask a question)"

### Section 3: Running Agents

```
╔═══════════════════════════════════════════════════════════════╗
║  RUNNING AGENTS (Coordinator Mode)                            ║
╚═══════════════════════════════════════════════════════════════╝

The coordinator polls Joan ONCE per interval and dispatches
single-pass workers as needed. Much more efficient than
running agents independently.

INVOCATION MODES:
─────────────────────────────────────
  /agents:dispatch           Single pass (dispatch once, exit)
  /agents:dispatch --loop    Continuous operation (uses external scheduler)

WHEN TO USE EACH:
─────────────────────────────────────
  Single pass:    Testing, debugging, manual intervention
  --loop mode:    Any run longer than 15 minutes (recommended for production)

  The --loop flag automatically uses an external scheduler that spawns
  FRESH Claude processes each cycle. This prevents context accumulation
  that previously caused failures after 20-30 minutes.

WHAT HAPPENS (Staged Pipeline):
─────────────────────────────────────
  PHASE 1: BA DRAINING
  1. Coordinator polls Joan (one API call)
  2. Processes ALL BA tasks (no code dependencies)

  PHASE 2: SERIAL DEV PIPELINE
  3. Checks pipeline gate (is any task in Architect→Dev→Review→Ops?)
  4. If clear: dispatches ONE task through the pipeline
  5. Workers complete and exit
  6. Coordinator sleeps, then repeats

Auto-shutdown after {maxIdlePolls} empty polls
(configured to {calculated time} with current settings)

STRICT SERIAL MODE:
─────────────────────────────────────
Only ONE task flows through the dev pipeline at a time.
This prevents:
  • Merge conflicts (no parallel PRs to develop)
  • Stale plans (Architect always sees current codebase)
  • Rework cycles (plans never become outdated)
```

Ask: "Ready to see the human touchpoints? (Continue / Ask a question)"

### Section 4: Human Touchpoints

```
╔═══════════════════════════════════════════════════════════════╗
║  YOUR ROLE IN THE WORKFLOW (Tag-Based)                        ║
╚═══════════════════════════════════════════════════════════════╝

All human actions are done via TAGS in Joan UI (not comments):

1. APPROVE PLANS
   When Architect creates a plan (tagged "Plan-Pending-Approval"):
   → Add "Plan-Approved" tag in Joan UI
   The coordinator will finalize the plan automatically.

2. ANSWER CLARIFICATIONS
   When BA asks questions (tagged "Needs-Clarification"):
   → Answer questions in task comments
   → Add "Clarification-Answered" tag
   BA will re-evaluate with your answers.

3. MONITOR PROGRESS
   Check Joan board to see tasks flowing through columns.
   Tags show current state (Ready, Planned, Claimed-Dev-1)

4. HANDLE FAILURES
   Tasks tagged "Implementation-Failed" or "Branch-Setup-Failed"
   need manual intervention. Check the failure comment,
   fix the issue, remove the failure tag, ensure "Planned" exists.

TAG QUICK REFERENCE (your actions):
─────────────────────────────────────
  Plan-Approved         Add to approve architect's plan
  Plan-Rejected         Add to reject architect's plan (revise)
  Clarification-Answered Add after answering BA questions
  Ops-Ready             Add to approve merge to develop

AGENT-MANAGED TAGS (for your awareness):
─────────────────────────────────────
  Ready                 BA validated requirements
  Planned               Plan approved, ready for devs
  Review-Approved       Reviewer approved code
  Rework-Complete       Dev finished rework (→ re-review)
  Rework-Requested      Reviewer found issues

MERGE REQUIRES BOTH (dual-tag gate):
─────────────────────────────────────
  Review-Approved (agent) + Ops-Ready (you) → Ops merges
```

### Section 5: Quick Start

```
╔═══════════════════════════════════════════════════════════════╗
║  QUICK START                                                  ║
╚═══════════════════════════════════════════════════════════════╝

Ready to go! Here's your workflow:

1. Create tasks in Joan's "To Do" column

2. Start agents:
   /agents:dispatch --loop    (recommended for all production runs)

3. Watch tasks flow:
   To Do → BA adds "Ready" tag
   Analyse → Architect creates plan → YOU add "Plan-Approved" tag
   Development → Dev implements in worktree → creates PR
   Review → Reviewer checks code → adds "Review-Approved"
   Review → YOU add "Ops-Ready" tag to approve merge
   Deploy → Ops merges to develop (requires BOTH tags)
   Done!

4. Stop agents:
   Auto-shutdown after {calculated time} of inactivity
   Or manually: touch /tmp/joan-agents-{project-name}.shutdown
   Or: Ctrl+C

Need help later? Run /agents:init again to see this tutorial.
```

End of tutorial.

## Final Output

After tutorial (or if skipped), show:

```
Start agents with:
  /agents:dispatch --loop   - Continuous operation (recommended, uses external scheduler)
  /agents:dispatch          - Single pass (testing/debugging only)

Stop gracefully:
  touch /tmp/joan-agents-{project-name}.shutdown
  Or: Ctrl+C

Change model anytime with: /agents:model

Onboard existing backlog: /agents:clean-project
```

Begin the initialization now.
