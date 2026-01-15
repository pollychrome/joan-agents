---
description: Start a Joan agent using repository configuration
argument-hint: <agent-type> [options]
allowed-tools: mcp__joan__*, mcp__github__*, Read, Write, Edit, Bash, Grep, Glob, Task, View, computer, AskUserQuestion
---

# Start Joan Agent

Start an agent using the configuration from `.joan-agents.json`.

## Arguments

- `$1` - Agent type: `ba`, `architect`, `pm`, `worker`, or `all`
- `$2` - (Optional) Worker ID (only for worker type) or `--max-idle=N` override

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
- `worker` → Implementation Worker (requires ID in $2 or defaults to 1)
- `all` → Start all enabled agents in parallel

Parse optional `--max-idle=N` from arguments to override config.

## Step 3: Validate Agent Enabled

Check if the requested agent is enabled in config.

If disabled:
```
Agent '{type}' is disabled in configuration.
Enable it in .joan-agents.json or run /agents:init to reconfigure.
```

## Step 4: Launch Agent

Set these variables from config:
- `PROJECT_ID` = config.projectId
- `PROJECT_NAME` = config.projectName
- `POLL_INTERVAL` = config.settings.pollingIntervalMinutes
- `MAX_IDLE` = override or config.settings.maxIdlePolls

### For Single Agent (`ba`, `architect`, `pm`, `worker`)

Launch the Task tool with the appropriate subagent:
- `ba` → subagent_type: "business-analyst"
- `architect` → subagent_type: "architect"
- `pm` → subagent_type: "project-manager"
- `worker` → subagent_type: "implementation-worker"

Pass configuration in the prompt.

### For `all`

Launch multiple Task tools in parallel for each enabled agent.
For workers, launch `config.agents.workers.count` parallel workers with IDs 1, 2, 3...

Report:
```
Starting agents for project: {projectName}

Launching:
- Business Analyst (polling every {N} min, max {M} idle)
- Architect (polling every {N} min, max {M} idle)
- Project Manager (polling every {N} min, max {M} idle)
- Worker #1 (polling every {N} min, max {M} idle)
- Worker #2 (polling every {N} min, max {M} idle)

Agents will auto-shutdown after {M} consecutive idle polls ({calculated time}).
```

Begin now with agent type: $1
