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

1. **Model Configuration**: How should agent models be configured?

   Use AskUserQuestion with options:

   - `optimized` - Cost-optimized per-worker defaults **(RECOMMENDED)**
     * BA: haiku (simple evaluation, auto-escalates for complex tasks)
     * Architect: opus (complex planning requires full capability)
     * Dev: opus (implementation quality critical)
     * Reviewer: opus (quality gate, no compromise)
     * Ops: haiku (mechanical merge operations)
     * **Saves ~25-30% on token costs while maintaining quality**

   - `uniform` - Same model for all workers
     * Follow-up question: opus, sonnet, or haiku?
     * Simpler configuration, consistent behavior

   - `custom` - Configure each worker individually
     * Choose model for each: BA, Architect, Dev, Reviewer, Ops

   **If "uniform" selected**, ask follow-up:
   - `opus` - Best instruction-following, most thorough (recommended for complex workflows)
   - `sonnet` - Faster, lower cost, good for simpler tasks
   - `haiku` - Fastest, lowest cost, best for very simple operations

   **If "custom" selected**, ask for each worker:
   - BA model? (opus/sonnet/haiku)
   - Architect model? (opus/sonnet/haiku)
   - Dev model? (opus/sonnet/haiku)
   - Reviewer model? (opus/sonnet/haiku)
   - Ops model? (opus/sonnet/haiku)

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

3. **Enabled Agents**: Which agents should be enabled?

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
      "Bash(git stash:*)",
      "Bash(npm install:*)",
      "Bash(npm test:*)",
      "Bash(npm run:*)",
      "Bash(pip install:*)",
      "Bash(pytest:*)",
      "Bash(mkdir:*)",
      "Bash(cd:*)",
      "Bash(gh pr:*)",
      "Bash(gh issue:*)",
      "Bash(gh api:*)",
      "Bash(python3:*)",
      "mcp__joan__*",
      "mcp__plugin_agents_joan__*",
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

## Step 5b: Create Logs Directory

Create the `.claude/logs` directory for webhook receiver and worker activity logs:

```bash
mkdir -p .claude/logs
```

This directory will contain:
- `webhook-receiver.log` - Webhook events and handler dispatch logs
- `worker-activity.log` - Real-time worker progress (for `joan status` monitoring)
- `agent-metrics.jsonl` - Structured metrics for health tracking

**Report:**
```
✓ Logs Directory Created

Path: .claude/logs/
Ready for webhook receiver and worker activity logging.
```

---

## Step 5c: WebSocket Authentication

The Joan agent system uses **WebSocket connections** for real-time event streaming. Authentication is shared with the Joan MCP server.

### Check Authentication Status

First, check if the user is already authenticated via joan-mcp:

```bash
# Check if ~/.joan-mcp/credentials.json exists and is valid
```

If credentials exist and are not expired, report:
```
✓ Authentication: Using existing joan-mcp credentials
  Email: {email from credentials}
  Expires: {expiry date}
```

### Authenticate if Needed

If no valid credentials exist:

```
AskUserQuestion: "WebSocket authentication is required. How would you like to authenticate?"
Options:
  - "Login via browser (recommended)"
  - "Skip - I'll run 'joan-mcp login' later"
```

If "Login via browser" selected:
```
Please run the following command in a separate terminal:

  joan-mcp login

This will open your browser to authenticate with Joan.
Once complete, press Enter to continue...
```

Wait for user confirmation, then verify credentials were created.

### Display Configuration Summary

```
╔═══════════════════════════════════════════════════════════════╗
║  WEBSOCKET AUTHENTICATION                                     ║
╚═══════════════════════════════════════════════════════════════╝

✓ Authentication configured

Credentials: ~/.joan-mcp/credentials.json
Shared with: Joan MCP server (same login)

The WebSocket client will automatically use these credentials.
To re-authenticate later, run: joan-mcp login
```

---

## Note: Agent Commands

**If you installed via the Claude Code plugin system** (recommended):
Agent commands are automatically available through the plugin. No additional setup needed.

```bash
# Plugin installation (one time, globally)
claude plugin marketplace add pollychrome/joan-agents
claude plugin install agents@joan-agents
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

**If "optimized" model config selected:**
```json
{
  "$schema": "./.claude/schemas/joan-agents.schema.json",
  "projectId": "{selected-project-uuid}",
  "projectName": "{selected-project-name}",
  "settings": {
    "models": {
      "ba": "haiku",
      "architect": "opus",
      "dev": "opus",
      "reviewer": "opus",
      "ops": "haiku"
    },
    "mode": "{standard|yolo}",
    "staleClaimMinutes": 120,
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

**If "uniform" model config selected:**
```json
{
  "$schema": "./.claude/schemas/joan-agents.schema.json",
  "projectId": "{selected-project-uuid}",
  "projectName": "{selected-project-name}",
  "settings": {
    "model": "{opus|sonnet|haiku}",
    "mode": "{standard|yolo}",
    "staleClaimMinutes": 120,
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

**If "custom" model config selected:**
```json
{
  "$schema": "./.claude/schemas/joan-agents.schema.json",
  "projectId": "{selected-project-uuid}",
  "projectName": "{selected-project-name}",
  "settings": {
    "models": {
      "ba": "{user-selected}",
      "architect": "{user-selected}",
      "dev": "{user-selected}",
      "reviewer": "{user-selected}",
      "ops": "{user-selected}"
    },
    "mode": "{standard|yolo}",
    "staleClaimMinutes": 120,
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

## Step 6b: Check for Existing Tasks

After saving the configuration, check if the project already has tasks that need workflow integration:

```
# Fetch tasks for the project
tasks = mcp__joan__list_tasks(project_id=PROJECT_ID)

IF tasks.length > 0:
  # Count tasks by column/status
  done_count = tasks.filter(t => t.status == "done").length
  active_count = tasks.length - done_count

  IF active_count > 0:
    Report: ""
    Report: "═══════════════════════════════════════════════════════════════"
    Report: "  EXISTING TASKS DETECTED"
    Report: "═══════════════════════════════════════════════════════════════"
    Report: ""
    Report: "Found {tasks.length} tasks in this project:"
    Report: "  • {active_count} active tasks (need workflow integration)"
    Report: "  • {done_count} completed tasks"
    Report: ""
    Report: "To integrate existing tasks into the workflow, run:"
    Report: "  /agents:clean-project --apply"
    Report: ""
    Report: "This will add appropriate workflow tags based on each task's"
    Report: "current state (column, description content, etc.)"
    Report: ""

    AskUserQuestion: "Would you like to run clean-project now to integrate existing tasks?"
    Options:
      - "Yes, run /agents:clean-project --apply now (recommended)"
      - "No, I'll run it later before starting the workflow"

    IF user selected "Yes":
      Report: "Running clean-project to integrate existing tasks..."
      # This will invoke the clean-project command
      /agents:clean-project --apply
      Report: ""
      Report: "Existing tasks integrated. Continuing with setup..."
```

## Step 7: Initial Task Setup (Optional)

After configuration is saved, offer the user options to add initial tasks:

```
AskUserQuestion: "Would you like to add tasks to your project now?"
Options:
  - "Import from a plan file (I have a plan.md or similar)"
  - "Create tasks interactively (guided questions)"
  - "Skip - I'll add tasks later in Joan"
```

**If "Import from a plan file":**

Ask for the file path:
```
AskUserQuestion: "Enter the path to your plan file:"
Options:
  - Free text input for file path
```

Then execute the project-planner command:
```
/agents:project-planner --file=<user-provided-path>
```

After completion, continue to Step 8.

**If "Create tasks interactively":**

Execute the project-planner command in interactive mode:
```
/agents:project-planner --interactive
```

After completion, continue to Step 8.

**If "Skip":**

Continue directly to Step 8.

---

## Step 8: Confirm Setup & Offer Tutorial

Report the configuration summary:

```
═══════════════════════════════════════════════════════════════
  Joan Agent Configuration Complete
═══════════════════════════════════════════════════════════════

Project: {name}
Model Config: {optimized|uniform|custom}
  {If optimized: BA=haiku, Architect=opus, Dev=opus, Reviewer=opus, Ops=haiku}
  {If uniform: All workers use {model}}
  {If custom: BA={ba}, Architect={architect}, Dev={dev}, Reviewer={reviewer}, Ops={ops}}
Mode: {standard|yolo}

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

WebSocket Configuration:
  • Authentication: ~/.joan-mcp/credentials.json (shared with MCP)
  • Catchup interval: 300s (safety net for missed events)
═══════════════════════════════════════════════════════════════
```

Then ask if the user wants a workflow tutorial:

```
AskUserQuestion: "Would you like an interactive tutorial explaining how the agent workflow operates?"
Options:
  - "Yes, show me the tutorial"
  - "No, I'm ready to start"
```

If user selects tutorial, proceed to Step 9. Otherwise, show quick start commands and finish.

## Step 9: Interactive Workflow Tutorial (Optional)

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
║  RUNNING AGENTS (WebSocket-Driven)                            ║
╚═══════════════════════════════════════════════════════════════╝

The system uses WebSocket connections for real-time events.
When task state changes in Joan, handlers execute immediately.

INVOCATION MODES:
─────────────────────────────────────
  /agents:dispatch --loop    WebSocket client (recommended)
  /agents:dispatch           Single pass (testing/debugging)

WHEN TO USE EACH:
─────────────────────────────────────
  --loop mode:    Production use - WebSocket event streaming
  Single pass:    Testing, debugging, manual intervention

  The --loop flag starts a WebSocket client that receives
  Joan events in real-time. Zero token cost when idle!

HOW IT WORKS (Event-Driven):
─────────────────────────────────────
  1. Task changes in Joan (created, tagged, moved)
  2. Joan pushes event via WebSocket connection
  3. Client dispatches the appropriate handler
  4. Handler processes ONE task and exits
  5. Back to listening (zero cost when idle)

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

2. Start webhook receiver:
   /agents:dispatch --loop              (standard mode)
   /agents:dispatch --loop --mode=yolo  (autonomous mode)

3. Watch tasks flow:
   To Do → BA adds "Ready" tag
   Analyse → Architect creates plan → YOU add "Plan-Approved" tag
   Development → Dev implements → creates PR
   Review → Reviewer checks code → adds "Review-Approved"
   Review → YOU add "Ops-Ready" tag to approve merge
   Deploy → Ops merges to develop (requires BOTH tags)
   Done!

4. Stop webhook receiver:
   Ctrl+C

Need help later? Run /agents:init again to see this tutorial.
```

End of tutorial.

## Final Output

After tutorial (or if skipped), show:

```
Start agents with:
  /agents:dispatch --loop              - WebSocket client (recommended)
  /agents:dispatch --loop --mode=yolo  - Fully autonomous
  /agents:dispatch                     - Single pass (testing only)

Stop: Ctrl+C

Re-authenticate: joan-mcp login
Change model: /agents:model
Onboard backlog: /agents:clean-project
```

Begin the initialization now.
