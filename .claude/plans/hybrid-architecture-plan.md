# Hybrid Architecture Implementation Plan

## Overview

Transform the joan-agents system from a Claude-heavy architecture to a hybrid model where:
- **Joan Backend** handles deterministic state machine transitions (zero tokens)
- **Smart Events** include pre-validated payloads (reduce fetches)
- **Claude Workers** focus only on intelligence-requiring tasks

**Expected Improvements:**
- Token reduction: 40-60%
- Speed improvement: 2-3x for mechanical operations
- Simpler client code (fewer handlers, direct worker dispatch)

---

## Phase 1: Joan Backend - State Machine Rules

### Goal
Move deterministic tag/column transitions to Joan backend, eliminating Claude invocations for mechanical operations.

### Implementation Location
`/Users/alexbenson/joan/workers/src/services/workflow-rules.ts` (new file)

### State Machine Rules

```typescript
// Rule format: When tag X is added, if conditions are met, execute actions
interface WorkflowRule {
  trigger_tag: string;
  requires_tags?: string[];      // All must be present
  requires_column?: string;      // Must be in this column
  forbids_tags?: string[];       // None can be present
  actions: WorkflowAction[];
  emit_event?: string | null;    // Custom event for Claude, null = suppress
  audit_reason: string;          // For ALS comment
}

interface WorkflowAction {
  type: 'add_tag' | 'remove_tag' | 'move_to_column' | 'add_comment';
  value: string;
}
```

### Rules to Implement

#### Rule 1: Plan Approval → Finalization
```typescript
{
  trigger_tag: "Plan-Approved",
  requires_tags: ["Plan-Pending-Approval"],
  requires_column: "Analyse",
  actions: [
    { type: "remove_tag", value: "Plan-Pending-Approval" },
    { type: "remove_tag", value: "Plan-Approved" },
    { type: "add_tag", value: "Planned" },
    { type: "move_to_column", value: "Development" },
    { type: "add_comment", value: "ALS/1\nactor: system\nintent: workflow\naction: plan-finalized\nsummary: Plan approved and finalized. Task ready for development." }
  ],
  emit_event: "task_ready_for_dev",  // New event type
  audit_reason: "Automatic plan finalization on approval"
}
```

#### Rule 2: All Completion Tags → Ready for Review
```typescript
{
  trigger_tag: "Test-Complete",  // Last completion tag typically added
  requires_tags: ["Dev-Complete", "Design-Complete"],
  requires_column: "Development",
  forbids_tags: ["Review-In-Progress"],
  actions: [
    { type: "move_to_column", value: "Review" }
  ],
  emit_event: "task_ready_for_review",
  audit_reason: "All completion tags present, moving to review"
}
```

#### Rule 3: Review Approved + Ops Ready → Ready for Merge
```typescript
{
  trigger_tag: "Ops-Ready",
  requires_tags: ["Review-Approved"],
  requires_column: "Review",
  actions: [],  // No automatic actions, just emit event
  emit_event: "task_ready_for_merge",
  audit_reason: "Task approved for merge"
}
```

#### Rule 4: Rework Requested → Back to Development
```typescript
{
  trigger_tag: "Rework-Requested",
  requires_column: "Review",
  actions: [
    { type: "remove_tag", value: "Dev-Complete" },
    { type: "remove_tag", value: "Design-Complete" },
    { type: "remove_tag", value: "Test-Complete" },
    { type: "remove_tag", value: "Review-In-Progress" },
    { type: "add_tag", value: "Planned" },
    { type: "move_to_column", value: "Development" }
  ],
  emit_event: "task_needs_rework",
  audit_reason: "Reviewer requested changes"
}
```

#### Rule 5: YOLO Auto-Approval (Conditional)
```typescript
// This rule only activates if project has YOLO mode enabled
{
  trigger_tag: "Plan-Pending-Approval",
  requires_column: "Analyse",
  project_setting: "workflow_mode == 'yolo'",  // Conditional on project setting
  actions: [
    { type: "add_tag", value: "Plan-Approved" },
    { type: "add_comment", value: "ALS/1\nactor: system\nintent: auto-approve\naction: yolo-plan-approved\nsummary: YOLO mode auto-approved plan" }
  ],
  emit_event: null,  // Plan-Approved triggers Rule 1
  audit_reason: "YOLO mode auto-approval"
}
```

#### Rule 6: YOLO Auto-Ops-Ready
```typescript
{
  trigger_tag: "Review-Approved",
  requires_column: "Review",
  project_setting: "workflow_mode == 'yolo'",
  actions: [
    { type: "add_tag", value: "Ops-Ready" },
    { type: "add_comment", value: "ALS/1\nactor: system\nintent: auto-approve\naction: yolo-ops-ready\nsummary: YOLO mode auto-approved for merge" }
  ],
  emit_event: null,  // Ops-Ready triggers Rule 3
  audit_reason: "YOLO mode auto-merge approval"
}
```

### Validation Rules (Prevent Invalid States)

```typescript
interface ValidationRule {
  tag: string;
  conflicts_with: string[];
  error_message: string;
}

const VALIDATION_RULES: ValidationRule[] = [
  {
    tag: "Ready",
    conflicts_with: ["Planned", "Plan-Pending-Approval"],
    error_message: "Cannot add Ready tag when task already has a plan"
  },
  {
    tag: "Planned",
    conflicts_with: ["Ready", "Plan-Pending-Approval"],
    error_message: "Cannot add Planned tag without plan approval"
  },
  {
    tag: "Review-Approved",
    conflicts_with: ["Rework-Requested"],
    error_message: "Cannot approve and request rework simultaneously"
  },
  {
    tag: "Claimed-Dev-1",
    conflicts_with: ["Implementation-Failed", "Branch-Setup-Failed"],
    error_message: "Cannot claim a failed task"
  }
];
```

### Integration Point

Modify `/Users/alexbenson/joan/workers/src/routes/project-tags.ts`:

```typescript
// In POST /:projectId/tasks/:taskId/tags/:tagId handler
// BEFORE inserting tag:

import { validateAndExecuteWorkflowRules } from '../services/workflow-rules';

// 1. Validate tag addition
const validation = await validateTagAddition(db, projectId, taskId, tagName);
if (!validation.allowed) {
  return c.json({ error: validation.error_message }, 400);
}

// 2. Execute workflow rules (may add/remove other tags, move columns)
const workflowResult = await executeWorkflowRules(
  env, db, projectId, taskId, tagName, triggeredBy
);

// 3. Insert the original tag (if not already added by rules)
if (!workflowResult.tagAlreadyAdded) {
  await db.prepare(`INSERT INTO task_tags ...`).run();
}

// 4. Broadcast events (main event + any rule-generated events)
for (const event of workflowResult.events) {
  await broadcastEvent(env, projectId, event);
}
```

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `workers/src/services/workflow-rules.ts` | CREATE | Rule engine implementation |
| `workers/src/routes/project-tags.ts` | MODIFY | Add rule execution hook |
| `workers/src/services/event-broadcast.ts` | MODIFY | Add new event types |
| `workers/src/types/workflow.ts` | CREATE | TypeScript interfaces |

### New Event Types

| Event | Triggered By | Contains | Claude Action |
|-------|-------------|----------|---------------|
| `task_ready_for_dev` | Plan-Approved rule | Task + handoff context | dispatch dev-worker |
| `task_ready_for_review` | Completion tags rule | Task + PR info | dispatch reviewer-worker |
| `task_ready_for_merge` | Ops-Ready rule | Task + review summary | dispatch ops-worker |
| `task_needs_rework` | Rework-Requested rule | Task + feedback | dispatch dev-worker (rework) |
| `task_needs_ba` | task_created | Task data | dispatch ba-worker |
| `task_needs_plan` | Ready tag | Task + BA context | dispatch architect-worker |

---

## Phase 2: Smart Event Payloads

### Goal
Include pre-fetched data in WebSocket events to eliminate redundant API calls from handlers.

### Current Problem
```
Event: tag_added (Ready)
  → Handler fetches: task, columns, tags, comments, project settings
  → Handler builds: work package with all context
  → Handler dispatches: worker with work package

This happens EVERY time, burning tokens on data fetching.
```

### Solution
```
Event: task_needs_plan
  → Event ALREADY CONTAINS: task, tags, handoff context, project settings
  → Client dispatches: worker directly with event payload

Zero fetching, immediate dispatch.
```

### Enhanced Event Payload Schema

```typescript
interface SmartEvent {
  // Standard fields
  type: string;
  project_id: string;
  task_id: string;
  timestamp: string;
  triggered_by: 'user' | 'agent' | 'system';

  // NEW: Pre-fetched task data
  task: {
    id: string;
    title: string;
    description: string;
    status: string;
    priority: string;
    column_id: string;
    column_name: string;
  };

  // NEW: Current tags
  tags: string[];

  // NEW: Handoff context (extracted from comments)
  handoff_context?: {
    from_stage: string;
    to_stage: string;
    key_decisions: string[];
    files_of_interest: string[];
    warnings: string[];
    metadata: Record<string, any>;
  };

  // NEW: Project settings relevant to workflow
  project_settings: {
    workflow_mode: 'standard' | 'yolo';
    model: 'opus' | 'sonnet' | 'haiku';
  };

  // NEW: For review events
  pr_info?: {
    number: number;
    branch: string;
    url: string;
  };

  // NEW: For rework events
  rework_feedback?: {
    blockers: string[];
    warnings: string[];
    files_to_fix: string[];
  };
}
```

### Implementation

Modify `/Users/alexbenson/joan/workers/src/services/event-broadcast.ts`:

```typescript
async function buildSmartEventPayload(
  env: Env,
  db: D1Database,
  projectId: string,
  taskId: string,
  eventType: string
): Promise<SmartEvent> {
  // Fetch task with column info
  const task = await db.prepare(`
    SELECT t.*, c.name as column_name
    FROM tasks t
    JOIN project_columns c ON t.column_id = c.id
    WHERE t.id = ?
  `).bind(taskId).first();

  // Fetch current tags
  const tags = await db.prepare(`
    SELECT pt.name
    FROM task_tags tt
    JOIN project_tags pt ON tt.tag_id = pt.id
    WHERE tt.task_id = ?
  `).bind(taskId).all();

  // Extract handoff context from recent comments
  const handoffContext = await extractLatestHandoff(db, taskId);

  // Fetch project settings
  const projectSettings = await getProjectWorkflowSettings(db, projectId);

  return {
    type: eventType,
    project_id: projectId,
    task_id: taskId,
    timestamp: new Date().toISOString(),
    triggered_by: 'system',
    task: {
      id: task.id,
      title: task.title,
      description: task.description,
      status: task.status,
      priority: task.priority,
      column_id: task.column_id,
      column_name: task.column_name
    },
    tags: tags.results.map(t => t.name),
    handoff_context: handoffContext,
    project_settings: projectSettings
  };
}
```

### Project Settings Storage

Add workflow settings to projects table or a new table:

```sql
-- Option A: Add to projects table
ALTER TABLE projects ADD COLUMN workflow_settings JSONB DEFAULT '{}';

-- Option B: New table (cleaner separation)
CREATE TABLE project_workflow_settings (
  project_id UUID PRIMARY KEY REFERENCES projects(id),
  workflow_mode TEXT DEFAULT 'standard',
  model TEXT DEFAULT 'opus',
  worker_timeouts JSONB DEFAULT '{}',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
```

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `workers/src/services/event-broadcast.ts` | MODIFY | Add smart payload building |
| `workers/src/services/handoff-extractor.ts` | CREATE | Extract handoff from comments |
| `workers/src/types/events.ts` | CREATE | Smart event interfaces |
| `workers/migrations/add_workflow_settings.sql` | CREATE | Database migration |

---

## Phase 3: Simplified Client

### Goal
Replace the handler layer with direct worker dispatch, since Joan now handles state machine logic.

### Current Architecture (Complex)
```
ws-client.py
  → receives: tag_added
  → dispatches: handle-architect.md (handler)
    → handler reads config
    → handler fetches task, columns, tags
    → handler builds work package
    → handler dispatches architect-worker
    → handler processes result
    → handler executes joan_actions
  → client logs result
```

### New Architecture (Simple)
```
ws-client.py
  → receives: task_needs_plan (smart event with full payload)
  → dispatches: architect-worker directly (skip handler)
    → worker uses payload directly (no fetching)
    → worker returns simple result
  → client sends result to Joan API
  → Joan applies state transition (already defined in rules)
```

### Simplified Client Flow

```python
# ws-client.py - simplified

EVENT_TO_WORKER = {
    'task_needs_ba': 'ba-worker',
    'task_needs_plan': 'architect-worker',
    'task_ready_for_dev': 'dev-worker',
    'task_needs_rework': 'dev-worker',
    'task_ready_for_review': 'reviewer-worker',
    'task_ready_for_merge': 'ops-worker',
}

async def handle_event(event: dict):
    event_type = event['type']

    if event_type not in EVENT_TO_WORKER:
        log(f"Ignoring event: {event_type}")
        return

    worker = EVENT_TO_WORKER[event_type]

    # Direct worker dispatch - no handler layer
    result = await dispatch_worker(
        worker=worker,
        work_package=event  # Smart event IS the work package
    )

    # Send result to Joan API (Joan applies state transitions)
    await submit_worker_result(
        task_id=event['task_id'],
        worker=worker,
        result=result
    )
```

### Worker Result API

Add new endpoint to Joan for processing worker results:

```
POST /api/projects/:projectId/tasks/:taskId/worker-result
{
  "worker": "architect-worker",
  "success": true,
  "result_type": "plan_created",
  "output": {
    "plan_content": "...",
    "branch_name": "feature/..."
  },
  "comment": "ALS/1\nactor: architect\n..."
}
```

Joan processes result:
1. Validates result matches expected worker
2. Applies appropriate tags based on result_type
3. Adds comment if provided
4. Broadcasts completion event

### Simplified Worker Output

Workers return simple, standardized results:

```typescript
interface WorkerResult {
  success: boolean;
  result_type: string;  // 'plan_created', 'implementation_complete', 'review_approved', etc.
  output?: {
    // Worker-specific output data
    plan_content?: string;
    branch_name?: string;
    pr_number?: number;
    blockers?: string[];
    warnings?: string[];
  };
  comment?: string;  // ALS comment to add
  error?: string;    // If success=false
}
```

### Result Type → State Transition Mapping

```typescript
const RESULT_TRANSITIONS: Record<string, WorkflowAction[]> = {
  'requirements_complete': [
    { type: 'add_tag', value: 'Ready' },
    { type: 'move_to_column', value: 'Analyse' }
  ],
  'needs_clarification': [
    { type: 'add_tag', value: 'Needs-Clarification' }
  ],
  'plan_created': [
    { type: 'add_tag', value: 'Plan-Pending-Approval' },
    { type: 'remove_tag', value: 'Ready' }
  ],
  'implementation_complete': [
    { type: 'add_tag', value: 'Dev-Complete' },
    { type: 'add_tag', value: 'Design-Complete' },
    { type: 'add_tag', value: 'Test-Complete' },
    { type: 'remove_tag', value: 'Claimed-Dev-1' },
    { type: 'remove_tag', value: 'Planned' }
  ],
  'review_approved': [
    { type: 'add_tag', value: 'Review-Approved' },
    { type: 'remove_tag', value: 'Review-In-Progress' }
  ],
  'review_rejected': [
    { type: 'add_tag', value: 'Rework-Requested' },
    { type: 'remove_tag', value: 'Review-In-Progress' }
  ],
  'merge_complete': [
    { type: 'remove_tag', value: 'Review-Approved' },
    { type: 'remove_tag', value: 'Ops-Ready' },
    { type: 'move_to_column', value: 'Deploy' }
  ]
};
```

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `scripts/ws-client.py` | MODIFY | Simplified event handling |
| `workers/src/routes/worker-results.ts` | CREATE | Worker result API endpoint |
| `workers/src/services/result-processor.ts` | CREATE | Process results and apply transitions |
| `commands/*.md` | MODIFY | Workers accept smart events directly |

---

## Implementation Order

### Week 1: Phase 1 - Backend Rules

**Day 1-2: Core Infrastructure**
- [ ] Create `workflow-rules.ts` with rule engine
- [ ] Create `types/workflow.ts` interfaces
- [ ] Add validation rules for invalid tag combinations

**Day 3-4: Integration**
- [ ] Modify `project-tags.ts` to call rule engine
- [ ] Implement rule execution with transaction support
- [ ] Add audit comments for system actions

**Day 5: Testing**
- [ ] Unit tests for rule engine
- [ ] Integration tests with actual tag operations
- [ ] Verify events are correctly emitted/suppressed

### Week 2: Phase 2 - Smart Events

**Day 1-2: Payload Building**
- [ ] Create `handoff-extractor.ts`
- [ ] Modify `event-broadcast.ts` for smart payloads
- [ ] Add project workflow settings storage

**Day 3-4: New Event Types**
- [ ] Implement `task_needs_*` event types
- [ ] Update ProjectEventsDO for new event structure
- [ ] Database migration for workflow settings

**Day 5: Testing**
- [ ] Verify smart events contain all required data
- [ ] Test handoff extraction accuracy
- [ ] Benchmark payload size vs. fetch overhead

### Week 3: Phase 3 - Simplified Client

**Day 1-2: Client Refactor**
- [ ] Simplify ws-client.py event handling
- [ ] Remove handler dispatch, add direct worker dispatch
- [ ] Update worker prompts to accept smart events

**Day 3-4: Result API**
- [ ] Create `worker-results.ts` endpoint
- [ ] Implement `result-processor.ts`
- [ ] Connect result types to state transitions

**Day 5: End-to-End Testing**
- [ ] Full workflow test (task creation → done)
- [ ] YOLO mode test
- [ ] Error handling and recovery

---

## Rollout Strategy

### Phase 1: Shadow Mode
- Deploy backend rules but don't suppress old events
- Both old (tag_added) and new (task_needs_*) events fire
- Client continues using old handlers
- Verify rules execute correctly

### Phase 2: Gradual Migration
- Enable smart events for one project
- Run new simplified client alongside old
- Compare results, measure token savings

### Phase 3: Full Migration
- Disable old event types
- Deploy simplified client to all projects
- Monitor for issues
- Remove old handler code

---

## Success Metrics

| Metric | Current | Target | Measurement |
|--------|---------|--------|-------------|
| Tokens per task lifecycle | ~50k | ~25k | API usage tracking |
| Time: plan approval → dev | ~30s | ~5s | Event timestamps |
| Time: dev complete → review | ~20s | ~5s | Event timestamps |
| Handler invocations | 8-10 per task | 4-5 per task | Client logs |
| Redundant fetches | ~20 per task | 0 | API call tracking |

---

## Risk Mitigation

### Risk: Rule conflicts
**Mitigation:** Rules execute in defined order with explicit priority. Validation prevents conflicting states.

### Risk: Event loss during transition
**Mitigation:** Shadow mode ensures both old and new systems run in parallel during migration.

### Risk: Smart events too large
**Mitigation:** Handoff context is truncated to 3KB max. Full description available via API if needed.

### Risk: Worker result processing fails
**Mitigation:** Results are idempotent. Failed result processing is retried. Manual recovery via doctor.

---

## Questions to Resolve

1. **Project settings storage:** Add to projects table or separate table?
2. **Rule priority:** How to handle multiple rules matching same trigger?
3. **Backward compatibility:** How long to support old event format?
4. **YOLO mode storage:** Per-project setting in Joan, or client-side config?
