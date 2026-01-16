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

## Step 4: Write Configuration

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
    "projectManager": { "enabled": {true/false} },
    "devs": { "enabled": {true/false}, "count": {user-choice} }
  }
}
```

## Step 5: Confirm Setup

Report the configuration summary:

```
Joan Agent Configuration Created

Project: {name} ({id})
Model: {opus|sonnet|haiku}
Polling: Every {N} minutes
Auto-shutdown: After {N} idle polls ({calculated time})

Enabled Agents:
- Business Analyst: {enabled/disabled}
- Architect: {enabled/disabled}
- Code Reviewer: {enabled/disabled}
- Project Manager: {enabled/disabled}
- Devs: {enabled/disabled} (x{count})

Start agents with:
  /agents:start ba         - Start Business Analyst
  /agents:start architect  - Start Architect
  /agents:start reviewer   - Start Code Reviewer
  /agents:start pm         - Start Project Manager
  /agents:start dev 1      - Start Dev #1
  /agents:start all        - Start all enabled agents

Change model with:
  /agents:model            - Update model for all agents
```

Begin the initialization now.
