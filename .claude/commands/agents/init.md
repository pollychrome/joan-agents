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
2. **Polling Interval**: How often should agents poll when idle? (default: 10 minutes)
3. **Max Idle Polls**: How many empty polls before agent shuts down? (default: 6, meaning 1 hour at 10-min intervals)
4. **Enabled Agents**: Which agents should be enabled?
5. **Dev Count**: If devs enabled, how many parallel dev workers? (default: 2)

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
| `Planned` | #3B82F6 (blue) | Plan approved, available for devs |
| `Dev-Complete` | #22C55E (green) | All DEV sub-tasks done |
| `Design-Complete` | #3B82F6 (blue) | All DES sub-tasks done |
| `Test-Complete` | #8B5CF6 (purple) | All TEST sub-tasks pass |
| `Review-In-Progress` | #F59E0B (amber) | Reviewer is actively reviewing |
| `Review-Approved` | #14B8A6 (teal) | Reviewer approved for merge (tag-trigger) |
| `Rework-Requested` | #EF4444 (red) | Reviewer found issues, needs fixes |
| `Rework-Complete` | #84CC16 (lime) | Dev finished rework (tag-trigger) |
| `Merge-Conflict` | #F97316 (orange) | Merge conflict detected |
| `Implementation-Failed` | #F43F5E (rose) | Dev couldn't complete (manual recovery) |
| `Worktree-Failed` | #EC4899 (pink) | Worktree creation failed (manual recovery) |

Additionally, create `Claimed-Dev-N` tags based on dev count:
- `Claimed-Dev-1` (#0EA5E9 sky)
- `Claimed-Dev-2` (#38BDF8 sky-400)
- etc.

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

## Step 5: Write Configuration

Create `.joan-agents.json` in project root with the user's selections:

```json
{
  "$schema": "./.claude/schemas/joan-agents.schema.json",
  "projectId": "{selected-project-uuid}",
  "projectName": "{selected-project-name}",
  "settings": {
    "model": "{opus|sonnet|haiku}",
    "pollingIntervalMinutes": {user-choice},
    "maxIdlePolls": {user-choice}
  },
  "agents": {
    "businessAnalyst": { "enabled": {true/false} },
    "architect": { "enabled": {true/false} },
    "reviewer": { "enabled": {true/false} },
    "ops": { "enabled": {true/false} },
    "devs": { "enabled": {true/false}, "count": {user-choice} }
  }
}
```

## Step 6: Confirm Setup & Offer Tutorial

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
  • Devs: {enabled/disabled} (x{count})

Project Structure:
  • Columns: {status - all present or list missing}
  • Tags: {N} workflow tags configured
═══════════════════════════════════════════════════════════════
```

Then ask if the user wants a workflow tutorial:

```
AskUserQuestion: "Would you like an interactive tutorial explaining how the agent workflow operates?"
Options:
  - "Yes, show me the tutorial"
  - "No, I'm ready to start"
```

If user selects tutorial, proceed to Step 7. Otherwise, show quick start commands and finish.

## Step 7: Interactive Workflow Tutorial (Optional)

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
  • Dev: Implements the plan in isolated worktrees
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
│ Action:  Claims task, creates worktree, implements plan      │
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
║  RUNNING AGENTS                                               ║
╚═══════════════════════════════════════════════════════════════╝

SINGLE PASS (process once, then exit):
─────────────────────────────────────
  /agents:ba              Run BA once
  /agents:architect       Run Architect once
  /agents:dev             Run Dev #1 once
  /agents:dev 2           Run Dev #2 once
  /agents:reviewer        Run Reviewer once
  /agents:ops             Run Ops once
  /agents:start all       Run all agents once

LOOP MODE (continuous until idle):
─────────────────────────────────────
  /agents:ba --loop       BA polls continuously
  /agents:dev 1 --loop    Dev #1 polls continuously
  /agents:start all --loop  All agents poll continuously

Loop mode auto-shuts down after {maxIdlePolls} empty polls
(configured to {calculated time} with current settings)

PARALLEL DEVELOPMENT:
─────────────────────────────────────
Run multiple dev agents in separate terminals:

  Terminal 1: /agents:dev 1 --loop
  Terminal 2: /agents:dev 2 --loop

Each dev works in isolated git worktrees - no conflicts!
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
   Tags show current state (Ready, Planned, Claimed-Dev-1...)

4. HANDLE FAILURES
   Tasks tagged "Implementation-Failed" or "Worktree-Failed"
   need manual intervention. Check the failure comment,
   fix the issue, remove the failure tag, ensure "Planned" exists.

TAG QUICK REFERENCE (your actions):
─────────────────────────────────────
  Plan-Approved         Add to approve architect's plan
  Clarification-Answered Add after answering BA questions

AGENT-MANAGED TAGS (for your awareness):
─────────────────────────────────────
  Ready                 BA validated requirements
  Planned               Plan approved, ready for devs
  Review-Approved       Reviewer approved code (→ Ops merges)
  Rework-Complete       Dev finished rework (→ re-review)
  Rework-Requested      Reviewer found issues
```

### Section 5: Quick Start

```
╔═══════════════════════════════════════════════════════════════╗
║  QUICK START                                                  ║
╚═══════════════════════════════════════════════════════════════╝

Ready to go! Here's your workflow:

1. Create tasks in Joan's "To Do" column

2. Start agents:
   /agents:start all --loop    (or run individually)

3. Watch tasks flow:
   To Do → BA adds "Ready" tag
   Analyse → Architect creates plan → YOU add "Plan-Approved" tag
   Development → Dev implements in worktree → creates PR
   Review → Reviewer checks code → adds Review-Approved or Rework-Requested
   Deploy → Ops merges to develop
   Done!

4. Stop agents:
   They auto-shutdown after {calculated time} of inactivity
   Or press Ctrl+C to stop manually

Need help later? Run /agents:init again to see this tutorial.
```

End of tutorial.

## Final Output

After tutorial (or if skipped), show:

```
Start agents with:
  /agents:ba              - Business Analyst
  /agents:architect       - Architect
  /agents:dev [N]         - Dev worker N
  /agents:reviewer        - Code Reviewer
  /agents:ops             - Ops
  /agents:start all       - All enabled agents

Add --loop for continuous operation.

Change model anytime with: /agents:model
```

Begin the initialization now.
