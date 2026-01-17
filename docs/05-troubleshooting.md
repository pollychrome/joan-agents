# Troubleshooting Guide

Solutions for common issues with the Joan Multi-Agent System.

---

## Agent Issues

### Agent Won't Start

**Symptoms:**
- Terminal shows error immediately
- Claude Code fails to initialize

**Solutions:**

1. **Check Claude Code installation:**
   ```bash
   claude --version
   ```
   If not found, reinstall Claude Code.

2. **Check MCP configuration:**
   ```bash
   cat ~/.claude/mcp.json
   ```
   Ensure Joan MCP is configured correctly.

3. **Test MCP connection:**
   ```bash
   claude
   > Use Joan MCP to list projects
   ```
   If this fails, your MCP server isn't running or configured.

4. **Check permissions:**
   ```bash
   chmod +x joan-agents/*.sh
   ```

### Agent Exits Immediately

**Symptoms:**
- Agent starts but exits within seconds
- No error message visible

**Solutions:**

1. **Check logs:**
   ```bash
   tail -f joan-agents/logs/{project}/*.log
   ```

2. **Run coordinator manually to see errors:**
   ```bash
   cd your-project
   claude --dangerously-skip-permissions "/agents:start --loop"
   ```

3. **Common causes:**
   - Invalid project name
   - MCP server not responding
   - Network issues

### Agent Not Picking Up Tasks

**Symptoms:**
- Agent running but tasks sit in column
- No activity in logs

**Solutions:**

1. **Verify task is in correct column:**
   - BA watches: To Do, Analyse (Needs-Clarification)
   - Architect watches: Analyse (Ready, Plan-Pending-Approval)
   - Dev watches: Development (Planned, Rework-Requested)
   - Reviewer watches: Review (completion tags present, no Rework-Requested)
   - Ops watches: Review (Review-Approved), Deploy

2. **Verify tags are correct:**
   - Ready tasks need `Ready` tag for Architect
   - Planned tasks need `Planned` tag for implementation agents

3. **Check project name matches:**
   ```bash
   # In agent logs, verify project name
   grep "project:" joan-agents/logs/{project}/*.log
   ```

4. **Check Joan API is returning tasks:**
   ```bash
   claude
   > Use Joan MCP to get tasks in To Do column for project X
   ```

### Agent Loops Forever Without Progress

**Symptoms:**
- Agent polls continuously
- Same task evaluated repeatedly
- No state changes

**Solutions:**

1. **Check for permission issues:**
   - Agent may not have permission to update Joan
   - Check Joan API key permissions

2. **Check for tag conflicts:**
   - Task may have conflicting tags
   - Remove invalid tags manually

3. **Check agent logs for errors:**
   ```bash
   grep -i "error\|failed\|exception" joan-agents/logs/{project}/*.log
   ```

---

## Git Issues

### Merge Conflicts

**Symptoms:**
- Ops agent reports conflict
- Agent comments asking @developer to resolve

**Solutions:**

1. **Developer resolves manually:**
   ```bash
   git checkout feature/{branch}
   git merge develop
   # Resolve conflicts
   git add .
   git commit -m "Resolve merge conflicts"
   git push
   ```

2. **Ops will retry on next cycle**

### Feature Branch Doesn't Exist

**Symptoms:**
- Developer/Designer can't find branch
- Git checkout fails

**Solutions:**

1. **Create branch manually:**
   ```bash
   git checkout develop
   git pull
   git checkout -b feature/{name}
   git push -u origin feature/{name}
   ```

2. **Or wait for first agent to create it**

### PR Creation Fails

**Symptoms:**
- Developer completes tasks but no PR
- GitHub API errors in logs

**Solutions:**

1. **Check GitHub MCP configuration:**
   ```json
   // ~/.claude/mcp.json
   {
     "mcpServers": {
       "github": {
         "env": {
           "GITHUB_TOKEN": "your-token-with-repo-scope"
         }
       }
     }
   }
   ```

2. **Check token permissions:**
   - Needs `repo` scope
   - Needs write access to repository

3. **Create PR manually:**
   ```bash
   gh pr create --base develop --head feature/{branch}
   ```

---

## Joan Issues

### MCP Connection Failed

**Symptoms:**
- "MCP server not responding"
- Timeout errors

**Solutions:**

1. **Check Joan MCP server is running:**
   ```bash
   # If it's a local server
   ps aux | grep joan-mcp
   
   # Check if it responds
   curl http://localhost:3000/health  # or your MCP endpoint
   ```

2. **Check MCP configuration:**
   ```bash
   cat ~/.claude/mcp.json | jq '.mcpServers.joan'
   ```

3. **Restart MCP server:**
   ```bash
   # Kill existing
   pkill -f joan-mcp
   
   # Restart
   node /path/to/joan-mcp/index.js &
   ```

### Tasks Not Updating

**Symptoms:**
- Agent says it updated task
- Joan UI doesn't reflect changes

**Solutions:**

1. **Check Joan API response:**
   - Look for error responses in agent logs
   
2. **Verify API permissions:**
   - Your Joan API key may be read-only
   - Check API key scopes

3. **Check for validation errors:**
   - Tag names may be invalid
   - Column names may be misspelled

### Comments Not Appearing

**Symptoms:**
- Agent says it commented
- No comment visible in Joan

**Solutions:**

1. **Check Joan comment API:**
   ```bash
   claude
   > Use Joan MCP to add a test comment to task ID X
   ```

2. **Check task ID is correct:**
   - Agent may be using wrong ID format

---

## Performance Issues

### High CPU Usage

**Symptoms:**
- Mac fans running constantly
- System slowdown

**Solutions:**

1. **Reduce concurrent devs:**
   - Lower `agents.devs.count` in `.joan-agents.json`
   - Disable unused agents in `.joan-agents.json`

2. **Increase poll interval:**
   - Edit `settings.pollingIntervalMinutes` in `.joan-agents.json`

3. **Check for infinite loops:**
   - Coordinator may be stuck processing the same task

### High Memory Usage

**Symptoms:**
- Memory pressure warnings
- Claude Code processes using GB of RAM

**Solutions:**

1. **Restart agents periodically:**
   - Long-running Claude Code sessions accumulate memory
   - Schedule daily restarts

2. **Use Sonnet instead of Opus:**
   - Use `/agents:model` or edit `.joan-agents.json` → `settings.model`

3. **Reduce concurrent devs:**
   - Lower `agents.devs.count` in `.joan-agents.json`

### Logs Growing Too Large

**Symptoms:**
- Disk space warnings
- Logs directory very large

**Solutions:**

1. **Set up log rotation:**
   ```bash
   # Add to crontab
   0 0 * * * find /path/to/joan-agents/logs -name "*.log" -mtime +7 -delete
   ```

2. **Compress old logs:**
   ```bash
   find joan-agents/logs -name "*.log" -mtime +1 -exec gzip {} \;
   ```

---

## Common Error Messages

### "No tasks found matching criteria"

**Cause:** Agent polling found no work to do.

**Action:** This is normal. Agent will retry next cycle.

### "Task dependency not met"

**Cause:** Sub-task depends on another that isn't complete.

**Action:** Wait for dependent task to complete, or check if it's blocked.

### "Failed to update task after 3 attempts"

**Cause:** Joan API rejected updates repeatedly.

**Action:** Check Joan API status, permissions, and payload format.

### "Branch already exists"

**Cause:** Feature branch was already created.

**Action:** Normal if another agent created it. Agent will checkout instead.

### "Rate limit exceeded"

**Cause:** Too many API calls to Claude or Joan.

**Action:** Increase poll interval or reduce concurrent tasks.

---

## Recovery Procedures

### Restart Coordinator

```bash
# Stop coordinator
./joan-agents/stop-agents.sh

# Wait for graceful shutdown
sleep 10

# Force kill if needed
pkill -9 -f "claude.*agents"

# Restart (from your project directory)
cd your-project
./joan-agents/start-agents.sh          # Terminal.app
# or
./joan-agents/start-agents-iterm.sh    # iTerm2
```

### Reset a Stuck Task

1. Open task in Joan
2. Remove all agent-managed tags:
   - Needs-Clarification
   - Ready
   - Plan-Pending-Approval
   - Planned
   - Claimed-Dev-*
   - Dev-Complete
   - Design-Complete
   - Test-Complete
   - Review-In-Progress
   - Rework-Requested
   - Merge-Conflict
   - Implementation-Failed
   - Worktree-Failed
3. Move task back to To Do
4. BA will re-evaluate from scratch

### Clear Coordinator State

The coordinator doesn't maintain local state beyond the current iteration, but to fully reset:

```bash
# Stop coordinator
./joan-agents/stop-agents.sh

# Clear logs
rm -rf joan-agents/logs/*

# Restart (from your project directory)
cd your-project
./joan-agents/start-agents.sh
```

### Manual Task Progression

If automation is stuck, progress task manually:

1. **To Do → Analyse:**
   - Add `Ready` tag if requirements are clear
   - Or add `Needs-Clarification` with questions

2. **Analyse → Development:**
   - Create plan manually in task description
   - Add `Planned` tag
   - Move to Development column

3. **Development → Review:**
   - Add all three Complete tags (Dev-Complete, Design-Complete, Test-Complete)
   - Create PR if not already created
   - Move to Review column

4. **Review → Deploy:**
   - Merge develop into feature branch (resolve any conflicts)
   - Add `Review-Approved` tag on the task
   - Ops will merge PR to develop and move to Deploy
   - Or manually: merge PR to develop, then move to Deploy

5. **Deploy → Done:**
   - After production deployment, move to Done column
   - (No merge happens here - PR was already merged in step 4)

---

## Getting Help

1. **Check logs first:**
   ```bash
   tail -100 joan-agents/logs/{project}/coordinator.log
   ```

2. **Run coordinator interactively:**
   ```bash
   cd your-project
   claude --dangerously-skip-permissions "/agents:start --loop"
   ```

3. **Test MCP separately:**
   ```bash
   claude
   > List all Joan MCP tools available
   > Use Joan MCP to get task {id}
   ```

4. **Simplify to isolate:**
   - Run coordinator in single-pass mode (without --loop)
   - Test with a single simple task
   - Verify each step manually
