---
description: Start a Joan agent using repository configuration
argument-hint: <agent-type> [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, mcp__github__*, Read, Write, Edit, Bash, Grep, Glob, Task, View, computer, AskUserQuestion
---

# Start Joan Agent

Start an agent using the configuration from `.joan-agents.json`.

## Arguments

- `$1` - Agent type: `ba`, `architect`, `ops`, `reviewer`, `dev`, or `all`
- `--loop` - Run in continuous loop mode (poll until idle threshold)
- `--max-idle=N` - Override idle threshold (only applies in loop mode)
- Dev ID - For dev type only, specify which dev (1, 2, 3...)

## Step 1: Load Configuration

Read `.joan-agents.json` from project root.

If file doesn't exist, report:
```
Configuration not found. Run /agents:init first to set up your Joan project.
```
And exit.

## Step 2: Parse Arguments

Agent type from `$1`:
- `ba` or `business-analyst` → Business Analyst
- `architect` or `arch` → Architect
- `ops` → Ops
- `reviewer` or `review` → Code Reviewer
- `dev` → Dev agent (specify ID or defaults to 1)
- `all` → Start all enabled agents in separate terminal windows

Parse optional flags:
- `--loop` → Enable continuous loop mode
- `--max-idle=N` → Override config's maxIdlePolls

## Step 3: Validate Agent Enabled

Check if the requested agent is enabled in config.

If disabled:
```
Agent '{type}' is disabled in configuration.
Enable it in .joan-agents.json or run /agents:init to reconfigure.
```

## Step 4: Launch Agent

Set these variables from config:
- `MODEL` = config.settings.model (default: "opus")
- `PROJECT_ID` = config.projectId
- `PROJECT_NAME` = config.projectName
- `POLL_INTERVAL` = config.settings.pollingIntervalMinutes
- `MAX_IDLE` = override or config.settings.maxIdlePolls
- `LOOP_MODE` = true if --loop flag present
- `DEV_COUNT` = config.agents.devs.count (for `all`)

### For Single Agent (`ba`, `architect`, `ops`, `reviewer`, `dev`)

Launch the Task tool with the appropriate subagent.

**CRITICAL: Always pass the `model` parameter from config to ensure correct model usage.**

```
Task tool call:
  - subagent_type: "{agent-type}"
  - model: "{MODEL from config}"  ← REQUIRED
  - prompt: "... configuration and instructions ..."
```

Agent type mapping:
- `ba` → subagent_type: "business-analyst"
- `architect` → subagent_type: "architect"
- `ops` → subagent_type: "ops"
- `reviewer` → subagent_type: "code-reviewer"
- `dev` → subagent_type: "implementation-worker"

Pass configuration in the prompt including:
- PROJECT_ID, PROJECT_NAME
- POLL_INTERVAL, MAX_IDLE
- **LOOP_MODE** - If true, agent runs continuously; if false, single pass

### For `all` - Launch Separate Terminal Windows

When `all` is specified, launch each agent in its own Terminal window for better isolation and monitoring.

**Use Bash tool to execute osascript commands that open Terminal windows.**

```bash
# Create log directory
LOG_DIR="$(pwd)/logs/{PROJECT_NAME}"
mkdir -p "$LOG_DIR"

# Build the loop flag string
LOOP_FLAG=""
if LOOP_MODE:
  LOOP_FLAG="--loop"

# Launch each agent in separate terminal
# BA Agent
osascript -e 'tell application "Terminal" to do script "cd \"'$(pwd)'\" && claude /agents:ba '"$LOOP_FLAG"'"'

# Architect Agent
osascript -e 'tell application "Terminal" to do script "cd \"'$(pwd)'\" && claude /agents:architect '"$LOOP_FLAG"'"'

# Reviewer Agent
osascript -e 'tell application "Terminal" to do script "cd \"'$(pwd)'\" && claude /agents:reviewer '"$LOOP_FLAG"'"'

# Ops Agent
osascript -e 'tell application "Terminal" to do script "cd \"'$(pwd)'\" && claude /agents:ops '"$LOOP_FLAG"'"'

# Dev Agents (based on config.agents.devs.count)
for i in 1..DEV_COUNT:
  osascript -e 'tell application "Terminal" to do script "cd \"'$(pwd)'\" && claude /agents:dev '"$i $LOOP_FLAG"'"'
```

**Sleep 1 second between each launch to avoid race conditions.**

Report after launching:
```
🚀 Starting Joan Multi-Agent System for: {PROJECT_NAME}
Mode: {LOOP_MODE ? "Continuous loop" : "Single pass"}

Launched in separate terminals:
- 🔍 Business Analyst
- 📐 Architect
- 🔬 Code Reviewer
- 🔧 Ops
- ⚙️  Dev #1
- ⚙️  Dev #2
...

{IF LOOP_MODE}
Each agent will poll every {POLL_INTERVAL} min.
Auto-shutdown after {MAX_IDLE} consecutive idle polls.
{ENDIF}

Log directory: {LOG_DIR}
To view logs: tail -f {LOG_DIR}/*.log
```

## Examples

```bash
# Single pass (process once and exit)
/agents:start ba
/agents:start dev 2
/agents:start all

# Continuous loop mode
/agents:start ba --loop
/agents:start all --loop
/agents:start dev 1 --loop --max-idle=12
```

Begin now with agent type: $1
