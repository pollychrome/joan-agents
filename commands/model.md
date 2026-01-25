---
description: Update the Claude model used by all Joan agents
allowed-tools: Read, Write, AskUserQuestion
---

# Update Agent Model

Change the Claude model configuration for Joan agents in this project.

## Step 1: Load Current Config

Read `.joan-agents.json` from project root.

If it doesn't exist:
```
Configuration not found. Run /agents:init first to set up your Joan project.
```
Exit.

## Step 2: Show Current Configuration

Display the current model settings:

```
╔═══════════════════════════════════════════════════════════════╗
║  CURRENT MODEL CONFIGURATION                                   ║
╚═══════════════════════════════════════════════════════════════╝
```

**If `settings.models` exists (per-worker config):**
```
Configuration: Per-Worker

  Worker      Model    Default
  ────────────────────────────
  BA          {ba}     haiku
  Architect   {arch}   opus
  Dev         {dev}    opus
  Reviewer    {rev}    opus
  Ops         {ops}    haiku

Note: BA auto-escalates from haiku to sonnet for complex tasks.
```

**If only `settings.model` exists (uniform config):**
```
Configuration: Uniform

  All workers use: {model}

  (No per-worker overrides configured)
```

**If neither exists:**
```
Configuration: Defaults

  Using built-in defaults:
  • BA: haiku (auto-escalates for complex tasks)
  • Architect: opus
  • Dev: opus
  • Reviewer: opus
  • Ops: haiku
```

## Step 3: Ask What to Change

Use AskUserQuestion:

**Question**: What would you like to do?

**Options**:
1. **Use optimized defaults (Recommended)** - Cost-optimized per-worker models
   * BA=haiku, Architect=opus, Dev=opus, Reviewer=opus, Ops=haiku
   * Saves ~25-30% on token costs while maintaining quality

2. **Set uniform model** - Same model for all workers
   * Follow-up: choose opus, sonnet, or haiku

3. **Customize specific worker** - Change model for one worker
   * Follow-up: select worker and model

4. **Configure all workers** - Set model for each worker individually
   * Follow-up: select model for each worker

5. **Reset to defaults** - Remove all model config (use built-in defaults)

## Step 4: Apply Changes

**If "Use optimized defaults" selected:**
```
# Add/update settings.models with optimized values
config.settings.models = {
  "ba": "haiku",
  "architect": "opus",
  "dev": "opus",
  "reviewer": "opus",
  "ops": "haiku"
}
# Remove legacy settings.model if it exists
delete config.settings.model
```

**If "Set uniform model" selected:**
Ask follow-up:
- `opus` - Best instruction-following, most thorough
- `sonnet` - Faster, lower cost, good balance
- `haiku` - Fastest, lowest cost

Then:
```
# Set uniform model, remove per-worker config
config.settings.model = "{selected}"
delete config.settings.models
```

**If "Customize specific worker" selected:**
Ask which worker:
- BA (current: {current or default})
- Architect (current: {current or default})
- Dev (current: {current or default})
- Reviewer (current: {current or default})
- Ops (current: {current or default})

Then ask which model:
- opus
- sonnet
- haiku

Then:
```
# Ensure settings.models exists
IF NOT config.settings.models:
  # Initialize with current effective values
  config.settings.models = {
    "ba": config.settings.model OR "haiku",
    "architect": config.settings.model OR "opus",
    "dev": config.settings.model OR "opus",
    "reviewer": config.settings.model OR "opus",
    "ops": config.settings.model OR "haiku"
  }
  delete config.settings.model

# Update the specific worker
config.settings.models.{worker} = "{selected}"
```

**If "Configure all workers" selected:**
Ask for each worker's model in sequence:
- BA model? (default: haiku)
- Architect model? (default: opus)
- Dev model? (default: opus)
- Reviewer model? (default: opus)
- Ops model? (default: haiku)

Then:
```
config.settings.models = {
  "ba": "{ba-selection}",
  "architect": "{architect-selection}",
  "dev": "{dev-selection}",
  "reviewer": "{reviewer-selection}",
  "ops": "{ops-selection}"
}
delete config.settings.model
```

**If "Reset to defaults" selected:**
```
# Remove all model config - handlers will use built-in defaults
delete config.settings.model
delete config.settings.models
```

## Step 5: Write Configuration

Write the updated config to `.joan-agents.json`.

## Step 6: Confirm Change

Show the new configuration:

```
╔═══════════════════════════════════════════════════════════════╗
║  MODEL CONFIGURATION UPDATED                                   ║
╚═══════════════════════════════════════════════════════════════╝

{Show new configuration using same format as Step 2}

Changes applied:
{List what changed, e.g., "BA: opus → haiku"}

Running agents are not affected. Restart them to use the new models.

Model characteristics:
  • opus: Thorough, reliable, best for complex workflows
  • sonnet: Balanced speed and capability
  • haiku: Fast, lightweight, for simple tasks

BA auto-escalation: When BA uses haiku, it automatically escalates
to sonnet for tasks with long descriptions (>2000 chars), integration
keywords, or many acceptance criteria (>5 bullets).
```

Begin now.
