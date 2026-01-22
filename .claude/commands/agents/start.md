---
description: [ALIAS] Use /agents:dispatch instead
argument-hint: [--loop] [--max-idle=N] [--interval=N]
allowed-tools: Bash
---

# Start Joan Agent (ALIAS)

**This command is an alias for `/agents:dispatch`.**

All functionality has been consolidated into `/agents:dispatch` for simplicity.

## Use Instead

```bash
# Single pass
/agents:dispatch

# Continuous operation (external scheduler)
/agents:dispatch --loop

# With options
/agents:dispatch --loop --interval=180 --max-idle=24
```

## Redirection

For backward compatibility, this command redirects to `/agents:dispatch`:

```
Parse all arguments (--loop, --max-idle, --interval)
Build command string: "/agents:dispatch [args]"
Report: "Note: /agents:start is now an alias for /agents:dispatch"
Report: "Redirecting to: {command string}"
Report: ""
Execute: claude {command string}
```

This ensures existing scripts and workflows continue to work seamlessly.
