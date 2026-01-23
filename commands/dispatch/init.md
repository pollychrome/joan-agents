---
description: Load and validate coordinator configuration (internal module)
allowed-tools: Read, Bash
---

# Coordinator Init Module

This module loads `.joan-agents.json` and validates configuration.
It returns structured config or exits with error.

## Usage

This module is called by the main dispatcher and individual handlers.
It outputs configuration to stdout as structured data.

## Load Configuration

```
CONFIG_FILE = ".joan-agents.json"

IF not exists(CONFIG_FILE):
  Report: "ERROR: Missing .joan-agents.json"
  Report: "Run /agents:init to create configuration"
  EXIT with error

config = JSON.parse(read(CONFIG_FILE))

# Extract core settings
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName
MODEL = config.settings.model OR "opus"
MODE = config.settings.mode OR "standard"
POLL_INTERVAL_MIN = config.settings.pollingIntervalMinutes OR 5
MAX_IDLE = config.settings.maxIdlePolls OR 12
DEV_COUNT = config.agents.devs.count OR 1
STALE_CLAIM_MINUTES = config.settings.staleClaimMinutes OR 120
STUCK_STATE_MINUTES = config.settings.stuckStateMinutes OR 120

# Pipeline settings
BA_DRAINING_ENABLED = config.settings.pipeline.baQueueDraining OR true
MAX_BA_TASKS_PER_CYCLE = config.settings.pipeline.maxBaTasksPerCycle OR 10

# Worker timeouts (in minutes)
TIMEOUT_BA = config.settings.workerTimeouts.ba OR 10
TIMEOUT_ARCHITECT = config.settings.workerTimeouts.architect OR 20
TIMEOUT_DEV = config.settings.workerTimeouts.dev OR 60
TIMEOUT_REVIEWER = config.settings.workerTimeouts.reviewer OR 20
TIMEOUT_OPS = config.settings.workerTimeouts.ops OR 15

# Agent enabled flags
BA_ENABLED = config.agents.businessAnalyst.enabled
ARCHITECT_ENABLED = config.agents.architect.enabled
REVIEWER_ENABLED = config.agents.reviewer.enabled
OPS_ENABLED = config.agents.ops.enabled
DEVS_ENABLED = config.agents.devs.enabled
```

## Validation

```
ERRORS = []

# Enforce strict serial mode
IF DEV_COUNT !== 1:
  ERRORS.push("devs.count must be 1 for strict serial mode")

# Validate required settings
IF not PROJECT_ID:
  ERRORS.push("Missing projectId")
IF not PROJECT_NAME:
  ERRORS.push("Missing projectName")

# Report validation errors
IF ERRORS.length > 0:
  Report: "Configuration validation failed:"
  FOR error IN ERRORS:
    Report: "  - {error}"
  EXIT with error

Report: "Config loaded: {PROJECT_NAME} (mode: {MODE}, model: {MODEL})"
```

## Output

Return configuration object for use by other modules:

```
RETURN {
  projectId: PROJECT_ID,
  projectName: PROJECT_NAME,
  model: MODEL,
  mode: MODE,
  pollIntervalMinutes: POLL_INTERVAL_MIN,
  maxIdlePOLLS: MAX_IDLE,
  devCount: DEV_COUNT,
  staleClaimMinutes: STALE_CLAIM_MINUTES,
  stuckStateMinutes: STUCK_STATE_MINUTES,
  pipeline: {
    baDrainingEnabled: BA_DRAINING_ENABLED,
    maxBaTasksPerCycle: MAX_BA_TASKS_PER_CYCLE
  },
  timeouts: {
    ba: TIMEOUT_BA,
    architect: TIMEOUT_ARCHITECT,
    dev: TIMEOUT_DEV,
    reviewer: TIMEOUT_REVIEWER,
    ops: TIMEOUT_OPS
  },
  enabled: {
    ba: BA_ENABLED,
    architect: ARCHITECT_ENABLED,
    reviewer: REVIEWER_ENABLED,
    ops: OPS_ENABLED,
    devs: DEVS_ENABLED
  }
}
```
