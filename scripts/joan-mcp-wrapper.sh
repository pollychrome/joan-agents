#!/bin/bash
# Wrapper script that ensures JOAN_AUTH_TOKEN is available to joan-mcp
# Always loads from credentials file to guarantee valid auth, regardless of
# how Claude passes (or doesn't pass) environment variables to MCP servers.

DEBUG_LOG="/tmp/joan-wrapper-debug.log"

# Log invocation
echo "[$(date -Iseconds)] wrapper invoked" >> "$DEBUG_LOG"

# Always load token from credentials file (most reliable)
# This bypasses any issues with Claude not passing env vars correctly
TOKEN=$(python3 << 'PYEOF'
import json
from pathlib import Path
from datetime import datetime

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
    from cryptography.hazmat.backends import default_backend

    cred_file = Path.home() / '.joan-mcp' / 'credentials.json'
    if not cred_file.exists():
        exit(1)

    with open(cred_file) as f:
        creds = json.load(f)

    # Check expiration
    if creds.get('expiresAt'):
        exp = datetime.fromisoformat(creds['expiresAt'].replace('Z', '+00:00'))
        if exp < datetime.now(exp.tzinfo):
            exit(1)

    # Decrypt token
    import os
    username = os.environ.get('USER') or os.environ.get('USERNAME') or 'joan'
    salt = f"{Path.home()}-{username}"
    kdf = Scrypt(salt=salt.encode(), length=32, n=16384, r=8, p=1, backend=default_backend())
    key = kdf.derive(b'joan-mcp-local-encryption')

    aesgcm = AESGCM(key)
    iv = bytes.fromhex(creds['iv'])
    ct = bytes.fromhex(creds['token']) + bytes.fromhex(creds['authTag'])
    plaintext = aesgcm.decrypt(iv, ct, None)
    print(plaintext.decode())
except Exception as e:
    import sys
    print(f"Error: {e}", file=sys.stderr)
    exit(1)
PYEOF
)

if [ -n "$TOKEN" ]; then
    echo "[$(date -Iseconds)] loaded token from credentials (${#TOKEN} chars)" >> "$DEBUG_LOG"
    export JOAN_AUTH_TOKEN="$TOKEN"
else
    echo "[$(date -Iseconds)] FAILED to load token from credentials" >> "$DEBUG_LOG"
    # Fall back to env var if credentials load failed
    if [ -n "$JOAN_AUTH_TOKEN" ]; then
        echo "[$(date -Iseconds)] using fallback env token" >> "$DEBUG_LOG"
    else
        echo "[$(date -Iseconds)] NO TOKEN AVAILABLE" >> "$DEBUG_LOG"
    fi
fi

exec joan-mcp serve
