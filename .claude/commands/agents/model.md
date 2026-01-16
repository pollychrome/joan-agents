---
description: Update the Claude model used by all Joan agents
allowed-tools: Read, Write, AskUserQuestion
---

# Update Agent Model

Change the Claude model used by all Joan agents in this project.

## Step 1: Load Current Config

Read `.joan-agents.json` from project root.

If it doesn't exist:
```
Configuration not found. Run /agents:init first to set up your Joan project.
```
Exit.

## Step 2: Show Current Model

Display the current model setting:

```
Current agent model: {config.settings.model || "not set (defaulting to opus)"}
```

## Step 3: Ask for New Model

Use AskUserQuestion to let user select a model:

**Question**: Which Claude model should agents use?

**Options**:
1. **Opus (Recommended)** - Best instruction-following, most thorough. Ideal for complex multi-step workflows where reliability matters.
2. **Sonnet** - Faster and lower cost. Good for simpler tasks or when optimizing for speed.
3. **Haiku** - Fastest and lowest cost. Best for very simple, quick operations.

## Step 4: Update Configuration

Update the `model` field in `.joan-agents.json`:

```json
{
  "settings": {
    "model": "{selected-model}",
    ...
  }
}
```

## Step 5: Confirm Change

```
Agent model updated: {old-model} → {new-model}

All agents started with /agents:start will now use {new-model}.

Model characteristics:
- opus: Thorough, reliable, best for complex workflows
- sonnet: Balanced speed and capability
- haiku: Fast, lightweight, for simple tasks

Running agents are not affected. Restart them to use the new model.
```

Begin now.
