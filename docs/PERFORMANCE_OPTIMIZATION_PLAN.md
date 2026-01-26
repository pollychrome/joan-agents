# Joan Agents 100x Performance Optimization Plan

## Executive Summary

The current coordinator architecture has a **15-50 second overhead per cycle** due to:
1. Parsing 2,143-line dispatch.md every spawn
2. Fetching ALL tasks every poll (regardless of changes)
3. Running 5 self-healing passes (O(5n)) every poll
4. Rebuilding caches from scratch every poll

This plan achieves **100x improvement** through:
- **Phase 1 (10-20x)**: Micro-handlers, delta tracking, lazy self-healing
- **Phase 2 (100x)**: Joan backend webhooks, event-driven architecture

---

## Phase 1: Immediate Wins (No Backend Changes)

### 1.1 Split Coordinator into Micro-Handlers — COMPLETED

**Was**: One 2,283-line dispatch.md loaded every spawn.

**Now**: Event-specific handlers loaded only when needed. The monolith has been
renamed to `dispatch-legacy.md` and replaced by the `dispatch/` directory:

```
commands/
├── dispatch-legacy.md       # Archived monolith (2,283 lines, for reference only)
├── dispatch/
│   ├── router.md            # Slim coordinator router (~370 lines, v3)
│   ├── init.md              # Config loading + validation
│   ├── queue-builder.md     # Queue building logic
│   ├── helpers.md           # Shared helper functions
│   ├── handle-ba.md         # BA queue processing
│   ├── handle-architect.md  # Architect queue processing
│   ├── handle-dev.md        # Dev claiming + dispatch
│   ├── handle-reviewer.md   # Review queue processing
│   └── handle-ops.md        # Ops merge processing
```

**Token savings**: ~84% reduction per spawn (~4K vs ~20K tokens)

### 1.2 Delta Task Tracking

**Current**: `mcp__joan__list_tasks()` fetches ALL tasks every poll.

**Optimized**: Track last-modified timestamp, only fetch changes:

```javascript
// .claude/state/last-poll.json
{
  "lastPollTimestamp": "2026-01-23T10:30:00Z",
  "taskHashes": {
    "task-uuid-1": "abc123",  // Hash of task state
    "task-uuid-2": "def456"
  }
}
```

**API change needed**: Joan MCP should support `list_tasks(modified_since: timestamp)`

**Fallback** (no API change): Use tag timestamp from `tag.created_at` to detect recent changes.

### 1.3 Lazy Self-Healing

**Current**: 5 self-healing passes (Steps 2b-2f) run EVERY poll cycle.

**Optimized**: Run self-healing only when triggered:

| Trigger | Passes to Run |
|---------|---------------|
| Normal poll | None (queue building only) |
| Empty queues | Step 3-Doctor diagnostic |
| Worker failure | Step 2b (stale claims) |
| `/agents:doctor` | All passes |
| First poll after restart | All passes |

**Implementation**: Add `--healing-mode=full|minimal|none` flag to dispatch.

### 1.4 Pre-Computed Tag Lookups

**Current**: `hasTag(task, tagName)` scans `task.tags` array every call.

**Optimized**: Build tag index once per task fetch:

```javascript
// Build once when tasks are fetched
function buildTagIndex(tasks) {
  const index = new Map();
  for (const task of tasks) {
    const tagSet = new Set(task.tags.map(t => t.name));
    index.set(task.id, tagSet);
  }
  return index;
}

// O(1) lookup instead of O(tags)
function hasTag(taskId, tagName) {
  return TAG_INDEX.get(taskId)?.has(tagName) || false;
}
```

**Savings**: From ~1,900 array scans to ~1,900 hash lookups per cycle.

### 1.5 Handoff Context Caching

**Current**: `extractStageContext()` parses ENTIRE comment history for every worker dispatch.

**Optimized**:
- Store last handoff comment ID in task metadata
- Only parse the single handoff comment, not full history

```javascript
// After finding handoff, cache the comment ID
task.metadata.lastHandoffCommentId = comment.id

// On next dispatch, fetch only that comment
const handoff = await mcp__joan__get_comment(task.metadata.lastHandoffCommentId)
```

---

## Phase 2: Event-Driven Architecture (Joan Backend Changes)

### 2.1 Webhook Endpoint Design

Add to Joan backend:

```typescript
// POST /api/v1/webhooks/agent-events
interface AgentWebhookPayload {
  event_type: 'task_updated' | 'task_moved' | 'tag_added' | 'tag_removed' | 'comment_added';
  project_id: string;
  task_id: string;
  timestamp: string;
  changes: {
    field: string;
    old_value: any;
    new_value: any;
  }[];
  triggered_by: 'user' | 'agent' | 'system';
}
```

### 2.2 Local Webhook Receiver

A lightweight process that receives webhooks and triggers appropriate handlers:

```bash
#!/bin/bash
# scripts/webhook-receiver.sh
# Listens on local port, triggers Claude handlers on events

PORT=9847
PROJECT_DIR=$(pwd)

# Start HTTP server
while true; do
  nc -l $PORT | while read line; do
    # Parse event type from HTTP body
    EVENT_TYPE=$(echo "$line" | jq -r '.event_type')
    TASK_ID=$(echo "$line" | jq -r '.task_id')

    case "$EVENT_TYPE" in
      "tag_added")
        TAG_NAME=$(echo "$line" | jq -r '.changes[0].new_value')
        case "$TAG_NAME" in
          "Ready")
            claude /agents:dispatch/handle-architect --task=$TASK_ID
            ;;
          "Plan-Approved")
            claude /agents:dispatch/handle-architect --finalize --task=$TASK_ID
            ;;
          "Planned"|"Rework-Requested")
            claude /agents:dispatch/handle-dev --task=$TASK_ID
            ;;
          "Dev-Complete")
            claude /agents:dispatch/handle-reviewer --task=$TASK_ID
            ;;
          "Ops-Ready")
            claude /agents:dispatch/handle-ops --task=$TASK_ID
            ;;
        esac
        ;;
      "task_moved")
        # Handle column transitions
        ;;
    esac
  done
done
```

### 2.3 Joan Backend: Trigger Webhooks

Add webhook dispatch to Joan's task update logic:

```typescript
// workers/src/services/task-service.ts

async function updateTask(taskId: string, updates: TaskUpdates) {
  const oldTask = await getTask(taskId);
  const newTask = await db.update(tasks).set(updates).where(eq(tasks.id, taskId));

  // Compute changes
  const changes = computeChanges(oldTask, newTask);

  // Dispatch webhook if agent integration enabled
  if (project.webhookUrl) {
    await dispatchWebhook(project.webhookUrl, {
      event_type: 'task_updated',
      project_id: project.id,
      task_id: taskId,
      timestamp: new Date().toISOString(),
      changes,
      triggered_by: ctx.source // 'user' | 'agent'
    });
  }

  return newTask;
}
```

### 2.4 Event Flow Examples

**Example: Task gets `Ready` tag**

```
┌────────────────────────────────────────────────────────────────────┐
│ Current (Polling)                                                   │
├────────────────────────────────────────────────────────────────────┤
│ 1. BA adds Ready tag                           T=0                  │
│ 2. [waiting for next poll...]                  T=0-300s             │
│ 3. Coordinator spawns, loads 2143 lines        T=300s               │
│ 4. Fetches ALL tasks                           T=302s               │
│ 5. Runs 5 self-healing passes                  T=305s               │
│ 6. Builds queues, finds Ready task             T=308s               │
│ 7. Dispatches Architect worker                 T=310s               │
│                                                                     │
│ LATENCY: 300-310 seconds                                            │
└────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────┐
│ Optimized (Event-Driven)                                            │
├────────────────────────────────────────────────────────────────────┤
│ 1. BA adds Ready tag                           T=0                  │
│ 2. Joan triggers webhook                       T=0.1s               │
│ 3. Receiver gets event                         T=0.2s               │
│ 4. Spawns: claude handle-architect --task=X    T=0.3s               │
│ 5. Handler loads 120 lines, fetches 1 task     T=1s                 │
│ 6. Dispatches Architect worker                 T=2s                 │
│                                                                     │
│ LATENCY: 2 seconds                                                  │
└────────────────────────────────────────────────────────────────────┘

IMPROVEMENT: 150x faster response
```

### 2.5 Micro-Handler Design

Each handler is focused and lightweight:

```markdown
---
# commands/dispatch/handle-architect.md
description: Handle Architect queue (Ready → Plan or Plan-Approved → Finalize)
argument-hint: --task=UUID [--finalize]
allowed-tools: Bash, Read, Task
---

# Architect Handler

## Arguments
- `--task=UUID` → Process specific task (from webhook)
- `--finalize` → Finalize approved plan (Plan-Approved tag present)

## Logic

1. Fetch single task: `mcp__joan__get_task(TASK_ID)`
2. Validate task is in expected state
3. IF --finalize:
   - Remove Plan-Pending-Approval + Plan-Approved tags
   - Add Planned tag
   - Move to Development column
4. ELSE (new plan):
   - Dispatch Architect worker
   - Process result
   - Add Plan-Pending-Approval tag

## Worker Dispatch

Task agent:
  subagent_type: architect-worker
  prompt: |
    Process this task and return WorkerResult JSON.
    Task: {task_title}
    Mode: {plan|finalize}
    ...
```

---

## Implementation Roadmap

### Phase 1 — COMPLETED

All micro-handlers extracted, router.md (v3) is the production entry point.
Monolith renamed to `dispatch-legacy.md` for reference.

- [x] Create `commands/dispatch/` directory structure
- [x] Extract handler files (handle-ba, handle-architect, handle-dev, handle-reviewer, handle-ops)
- [x] Implement router.md with API-first queue building + MCP fallback
- [x] Add dev claiming protocol to router
- [x] Rename monolith to dispatch-legacy.md

### Week 3: Phase 2 Joan Backend

- [ ] Add webhook configuration to projects table
- [ ] Implement `dispatchWebhook()` in task service
- [ ] Add webhook on tag add/remove
- [ ] Add webhook on column move
- [ ] Add webhook on comment add
- [ ] Test with curl/webhook.site

### Week 4: Phase 2 Event Router

- [ ] Create `scripts/webhook-receiver.sh`
- [ ] Integrate with micro-handlers
- [ ] Add graceful shutdown handling
- [ ] Add error recovery (webhook replay)
- [ ] Performance testing

---

## Metrics & Success Criteria

| Metric | Current | Phase 1 Target | Phase 2 Target |
|--------|---------|----------------|----------------|
| Time to task response | 60-300s | 30-60s | <5s |
| Tokens per cycle | ~30K | ~5K | ~2K |
| Tasks fetched per poll | ALL | Only changed | Single task |
| Self-healing passes | 5/poll | 0-1/poll | On-demand |
| Coordinator spawn time | 15-30s | 5-10s | 1-2s |

---

## Rollback Plan

Each phase is independent:

- **Phase 1 rollback**: Rename `dispatch-legacy.md` back to `dispatch.md` (file takes priority over directory)
- **Phase 2 rollback**: Disable webhook URL in project config, fall back to Phase 1 polling

---

## Questions for Implementation

1. **Joan MCP API**: Can we add `list_tasks(modified_since: timestamp)` parameter?
2. **Webhook security**: Should webhooks use HMAC signing for verification?
3. **Webhook retry**: How many retries on failed webhook delivery?
4. **Multi-project**: One receiver per project or global receiver?

---

## Phase 2 Implementation Status

### Completed Components

#### 1. Joan Backend Webhook Service (`/backend/app/services/webhook_service.py`)

```python
# Event types supported:
- task_created
- task_updated
- task_deleted
- task_moved  (column changes)
- tag_added
- tag_removed
- comment_added

# Features:
- HMAC-SHA256 signature verification
- Configurable timeout and retries
- Triggered-by tracking (user/agent/system)
```

#### 2. Project Model Updates (`/backend/app/models/project.py`)

```python
# New fields:
webhook_url = Column(String, nullable=True)    # e.g., http://localhost:9847
webhook_secret = Column(String, nullable=True)  # HMAC secret
```

#### 3. Task API Integration (`/backend/app/api/tasks.py`)

- `update_task()` now dispatches `task_updated` or `task_moved` webhooks
- Includes `triggered_by` query parameter to prevent loops

#### 4. Database Migration (`/backend/alembic/versions/webhook_fields_migration.py`)

Run migration:
```bash
cd /path/to/Joan/backend
alembic upgrade head
```

#### 5. Webhook Receiver (`/joan-agents/scripts/webhook-receiver.sh`)

Lightweight HTTP server that maps webhook events to handler invocations.

### Setup Instructions

#### Step 1: Run Database Migration (Local Backend)

```bash
cd ~/claude1/Joan/backend
alembic upgrade head
```

#### Step 2: Configure Project Webhook URL

Using Joan API or directly in database:
```sql
UPDATE projects
SET webhook_url = 'http://localhost:9847/webhook',
    webhook_secret = 'your-secret-here'
WHERE id = 'your-project-id';
```

Or via API:
```bash
curl -X PATCH http://localhost:8000/api/v1/projects/{project_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"webhook_url": "http://localhost:9847/webhook", "webhook_secret": "your-secret"}'
```

#### Step 3: Start Webhook Receiver

```bash
cd /path/to/your/project
~/joan-agents/scripts/webhook-receiver.sh --port 9847 --secret your-secret-here
```

Or with environment variables:
```bash
export JOAN_WEBHOOK_PORT=9847
export JOAN_WEBHOOK_SECRET=your-secret-here
export JOAN_PROJECT_DIR=/path/to/project
~/joan-agents/scripts/webhook-receiver.sh
```

#### Step 4: Test the Integration

```bash
# Add a test tag to a task
curl -X POST http://localhost:8000/api/v1/projects/{project_id}/tasks/{task_id}/tags \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Ready"}'

# Check webhook receiver logs
tail -f /path/to/project/.claude/logs/webhook-receiver.log
```

### Cloudflare Workers Implementation

For production (Cloudflare Workers API), add webhook dispatch to:

```typescript
// workers/src/api/tasks.ts

import { dispatchWebhook } from '../services/webhook';

export async function updateTask(c: Context) {
  const taskId = c.req.param('id');
  const updates = await c.req.json();

  // ... existing update logic ...

  // Dispatch webhook after successful update
  await dispatchWebhook(c.env, {
    event_type: 'task_updated',
    project_id: task.project_id,
    task_id: taskId,
    changes: computeChanges(oldTask, newTask),
    triggered_by: c.req.header('X-Triggered-By') || 'user'
  });

  return c.json(updatedTask);
}
```

### Event → Handler Mapping

| Event Type | Tag/Condition | Handler | Mode |
|------------|---------------|---------|------|
| tag_added | Ready | handle-architect | plan |
| tag_added | Plan-Approved | handle-architect | finalize |
| tag_added | Plan-Rejected | handle-architect | revise |
| tag_added | Planned | handle-dev | implement |
| tag_added | Rework-Requested | handle-dev | rework |
| tag_added | Merge-Conflict | handle-dev | conflict |
| tag_added | Dev-Complete | handle-reviewer | review |
| tag_added | Rework-Complete | handle-reviewer | review |
| tag_added | Ops-Ready | handle-ops | merge |
| tag_added | Invoke-Architect | handle-architect | advisory-conflict |
| tag_added | Architect-Assist-Complete | handle-ops | merge-with-guidance |
| tag_added | Clarification-Answered | handle-ba | evaluate |
| task_created | (in To Do) | handle-ba | evaluate |

### Loop Prevention

The webhook system prevents infinite loops through:

1. **triggered_by field**: Webhooks include `triggered_by: agent` when changes come from agents
2. **Receiver filtering**: The webhook receiver ignores events with `triggered_by: agent`
3. **Source tracking**: API calls can pass `?triggered_by=agent` to mark their source

### Comparison: Polling vs Webhooks

| Aspect | Polling (Phase 1) | Webhooks (Phase 2) |
|--------|-------------------|-------------------|
| Latency | 60-300 seconds | <5 seconds |
| Token cost per event | ~5-10K tokens | ~2K tokens |
| Context loaded | Full router + handler | Handler only |
| Complexity | Lower (single process) | Higher (receiver + handlers) |
| Reliability | Simpler failure modes | Needs queue for missed webhooks |
| Best for | Development, testing | Production, responsiveness |
