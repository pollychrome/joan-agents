# Joan Application Startup Guide

## Known Issues
- **Port 5173**: Default Vite port often has binding issues. Use port 3000 instead.
- **Process Timeouts**: The dev server command will timeout after 2 minutes in the terminal, but this is expected behavior - it means the server is running.

## Startup Procedure

### 1. Kill Any Existing Processes
```bash
pkill -f "vite" || true
pkill -f "node.*dev" || true
```

### 2. Start Frontend Development Server
```bash
cd /Users/alexbenson/Joan/frontend
npx vite --port 3000
```

### 3. Verify Server is Running
After starting, verify the server is actually running by checking:

```bash
# Check if port is listening
lsof -i :3000

# Test HTTP connection
curl -I http://localhost:3000

# Alternative: Check with wget
wget --spider -S http://localhost:3000 2>&1 | grep "HTTP/"
```

### 4. Expected Success Indicators
- Terminal shows: `VITE v7.0.0 ready in XX ms`
- `curl -I` returns `HTTP/1.1 200 OK`
- Browser can access http://localhost:3000

### 5. Common Failure Indicators
- `curl: (7) Failed to connect to localhost port 3000`
- No process listed in `lsof -i :3000`
- Browser shows "This site can't be reached"

## Backend Server (When Needed)
```bash
cd /Users/alexbenson/Joan/backend
uvicorn app.main:app --reload --port 8000
```

## Troubleshooting

### If Port 3000 is Blocked
Try alternative ports:
```bash
npx vite --port 3001
npx vite --port 3002
npx vite --port 4000
```

### If Vite Won't Start
1. Clear cache: `rm -rf node_modules/.vite`
2. Check for errors: `npm run build`
3. Reinstall dependencies: `npm install`

### Process Management
To run in background and verify:
```bash
# Start in background
nohup npx vite --port 3000 > vite.log 2>&1 &

# Check if running
ps aux | grep vite
tail -f vite.log
```

## Quick Verification Script
```bash
# Save this as check-server.sh
#!/bin/bash
if curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 | grep -q "200"; then
    echo "✅ Server is running on http://localhost:3000"
else
    echo "❌ Server is NOT running"
fi
```

## Important Notes
- Always verify the server is actually accessible before reporting it's running
- The timeout message after 2 minutes is normal - it doesn't mean the server stopped
- Use the verification steps above to confirm the server status