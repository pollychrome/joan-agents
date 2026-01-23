---
description: [DEPRECATED - ALIAS] Use /agents:dispatch instead
deprecated: true
redirectsTo: "/agents:dispatch"
argument-hint: [--loop] [--max-idle=N] [--interval=N]
allowed-tools: Bash
---

# Start Joan Agent (DEPRECATED)

**DEPRECATED:** This command is superseded by `/agents:dispatch`. It now redirects automatically.

## Why Deprecated?

The old background dispatch architecture (`run_in_background: true`) is incompatible with the MCP-proxy pattern where the coordinator must execute `WorkerResult` actions via Joan MCP.

All functionality has been consolidated into `/agents:dispatch` for proper MCP integration.

## Migration

Replace all usage with `/agents:dispatch`:

```bash
# Old (deprecated)
/agents:start --loop

# New (recommended)
/agents:dispatch --loop
```

All options work the same:

```bash
# Single pass
/agents:dispatch

# Continuous operation (external scheduler)
/agents:dispatch --loop

# With options
/agents:dispatch --loop --interval=180 --max-idle=24
```

## What This Command Does Now

This command automatically redirects to `/agents:dispatch` with the same arguments for backward compatibility.

**Implementation:** The command handler immediately invokes `/agents:dispatch` with forwarded arguments.

```
Parse all arguments (--loop, --max-idle, --interval)
Build command string: "/agents:dispatch [args]"
Report: "Note: /agents:start is deprecated - use /agents:dispatch instead"
Report: "Redirecting to: {command string}"
Report: ""
Execute: claude {command string}
```

This ensures existing scripts and workflows continue to work seamlessly while encouraging migration to the new command.
