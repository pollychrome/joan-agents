---
description: Run coordinator (single pass or continuous WebSocket client)
argument-hint: [--loop] [--mode=standard|yolo] [--handler=ba|architect|dev|reviewer|ops] [--task=UUID]
allowed-tools: Skill
---

# Dispatch Coordinator

This is the main entry point for the Joan agent coordinator.

## Usage

```bash
/agents:dispatch --loop              # WebSocket client (recommended)
/agents:dispatch --loop --mode=yolo  # Fully autonomous mode
/agents:dispatch                     # Single pass (testing/debugging)
```

## Implementation

This command delegates to the modular router at `/agents:dispatch:router`.

```
# Forward all arguments to the router
Skill: agents:dispatch:router with all original arguments

# Example argument forwarding:
# /agents:dispatch --loop --mode=yolo
#   → /agents:dispatch:router --loop --mode=yolo
```

Forward the command by invoking the Skill tool with skill="agents:dispatch:router" and passing any arguments from the original invocation.
