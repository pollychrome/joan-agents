#!/bin/bash
# Wrapper script that ensures JOAN_AUTH_TOKEN is available to joan-mcp
# This handles the case where Claude doesn't pass env vars to MCP servers

# If JOAN_AUTH_TOKEN is set, use it
if [ -n "$JOAN_AUTH_TOKEN" ]; then
    exec joan-mcp serve
fi

# Otherwise, try to load from credentials file using Python
TOKEN=$(python3 -c "
import sys
sys.path.insert(0, '$HOME/joan-agents/scripts')
try:
    from importlib.machinery import SourceFileLoader
    ws = SourceFileLoader('ws_client', '$HOME/joan-agents/scripts/ws-client.py').load_module()
    token = ws.get_auth_token()
    if token:
        print(token)
except Exception as e:
    pass
" 2>/dev/null)

if [ -n "$TOKEN" ]; then
    export JOAN_AUTH_TOKEN="$TOKEN"
fi

exec joan-mcp serve
