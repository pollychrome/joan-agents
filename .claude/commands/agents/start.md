---
description: Start a Joan agent using repository configuration
argument-hint: <agent-type> [--loop] [--max-idle=N]
allowed-tools: mcp__joan__*, mcp__github__*, Read, Write, Edit, Bash, Grep, Glob, Task, View, computer, AskUserQuestion
---

# Start Joan Agent

Start an agent using the configuration from `.joan-agents.json`.

## Arguments

- `$1` - Agent type: `ba`, `architect`, `pm`, `reviewer`, `dev`, or `all`
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
- `pm` or `project-manager` → Project Manager
- `reviewer` or `review` → Code Reviewer
- `dev` → Dev agent (specify ID or defaults to 1)
- `all` → Start all enabled agents in parallel

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

### For Single Agent (`ba`, `architect`, `pm`, `reviewer`, `dev`)

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
- `pm` → subagent_type: "project-manager"
- `reviewer` → subagent_type: "code-reviewer"
- `dev` → subagent_type: "implementation-worker"

Pass configuration in the prompt including:
- PROJECT_ID, PROJECT_NAME
- POLL_INTERVAL, MAX_IDLE
- **LOOP_MODE** - If true, agent runs continuously; if false, single pass

### For `all`

Launch multiple Task tools in parallel for each enabled agent.
For devs, launch `config.agents.devs.count` parallel devs with IDs 1, 2, 3...

**Each Task call MUST include `model: "{MODEL}"` from config.**
**Each Task call MUST include loop mode setting from --loop flag.**

Report:
```
Starting agents for project: {projectName}
Mode: {LOOP_MODE ? "Continuous loop" : "Single pass"}

Launching:
- Business Analyst {LOOP_MODE ? "(loop mode)" : "(single pass)"}
- Architect {LOOP_MODE ? "(loop mode)" : "(single pass)"}
- Code Reviewer {LOOP_MODE ? "(loop mode)" : "(single pass)"}
- Project Manager {LOOP_MODE ? "(loop mode)" : "(single pass)"}
- Dev #1 {LOOP_MODE ? "(loop mode)" : "(single pass)"}
- Dev #2 {LOOP_MODE ? "(loop mode)" : "(single pass)"}

{IF LOOP_MODE}
Agents will poll every {POLL_INTERVAL} min.
Auto-shutdown after {MAX_IDLE} consecutive idle polls ({calculated time}).
{ENDIF}
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
