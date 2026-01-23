# Worker Result Schema (MCP Proxy Pattern)

This document defines the structured result format that workers return to the coordinator.
Workers do not have direct MCP access - they return action requests that the coordinator executes.

## Overview

```
Coordinator                          Worker
    │                                   │
    │  ── Work Package (prompt) ──────► │
    │                                   │  (does work)
    │  ◄── WorkerResult (JSON) ──────── │
    │                                   │
    │  (validates & executes actions)   │
    │  (verifies post-conditions)       │
```

## WorkerResult Schema

```typescript
interface WorkerResult {
  // Required fields
  success: boolean;           // Did the worker complete its task?
  summary: string;            // Human-readable summary of what was done

  // Joan MCP actions to execute
  joan_actions: {
    add_tags?: string[];      // Tag NAMES to add (coordinator resolves to IDs)
    remove_tags?: string[];   // Tag NAMES to remove
    add_comment?: string;     // Full comment content (use ALS format)
    move_to_column?: string;  // Column NAME to move task to
    update_description?: string; // Replace task description (for plans)
  };

  // Git actions (for dev workers)
  git_actions?: {
    branch_created?: string;     // Name of branch that was created
    files_changed?: string[];    // List of files modified
    commit_made?: boolean;       // Whether a commit was created
    commit_sha?: string;         // SHA of commit if created
    pr_created?: {               // PR details if created
      number: number;
      url: string;
      title: string;
    };
  };

  // Error handling
  errors?: string[];          // List of errors encountered
  needs_human?: string;       // If human intervention required, explain why

  // Metadata
  worker_type: string;        // "ba" | "architect" | "dev" | "reviewer" | "ops"
  task_id: string;            // Task ID that was processed
  execution_time_ms?: number; // How long the worker took

  // Stage Context Handoff (for passing context to next workflow stage)
  stage_context?: StageContext;

  // Agent Invocation (for cross-agent consultation)
  invoke_agent?: AgentInvocation;
}

/**
 * Request another agent's help during workflow execution.
 * Used when a worker encounters a situation requiring specialist consultation.
 * Example: Ops invokes Architect for complex merge conflict analysis.
 */
interface AgentInvocation {
  // Which agent to invoke
  agent_type: "architect" | "ba" | "reviewer";

  // Agent-specific mode for the invocation
  mode: string;  // e.g., "advisory-conflict", "clarify-requirement"

  // Context for the invoked agent
  context: {
    reason: string;           // Why this agent is being invoked
    question?: string;        // Specific question to answer
    files_of_interest?: string[];  // Files relevant to the consultation

    // For conflict resolution (Ops → Architect)
    conflict_details?: {
      conflicting_files: string[];
      develop_summary: string;   // What develop branch changed
      feature_summary: string;   // What feature branch changed
    };
  };

  // How to resume the original workflow after invocation
  resume_as: {
    agent_type: "dev" | "ops" | "reviewer";  // Original worker type
    mode: string;  // e.g., "merge-with-guidance"
  };
}

/**
 * Context passed between workflow stages via ALS handoff comments.
 * Each handoff is per-transition (not cumulative) - contains only what the next stage needs.
 * Total serialized size must not exceed 3KB.
 */
interface StageContext {
  from_stage: "ba" | "architect" | "dev" | "reviewer";
  to_stage: "architect" | "dev" | "reviewer" | "ops";

  // Key decisions made in this stage (max 5 items, 200 chars each)
  key_decisions: string[];

  // Files relevant to next stage (max 10 file paths)
  files_of_interest?: string[];

  // Warnings for next stage (max 3 items, 100 chars each)
  warnings?: string[];

  // Dependencies or prerequisites (max 5 items)
  dependencies?: string[];

  // Arbitrary metadata (max 1KB serialized)
  metadata?: Record<string, unknown>;
}
```

## ALS Comment Format

All comments should use the ALS (Agentic Language Syntax) format:

```
ALS/1
actor: {worker_type}
intent: {status|decision|question|recovery}
action: {specific-action-name}
tags.add: [{tag1}, {tag2}]
tags.remove: [{tag3}]
summary: {one-line summary}
details:
- {detail 1}
- {detail 2}
```

## Worker-Specific Result Examples

### BA Worker Result

```json
{
  "success": true,
  "summary": "Task requirements are complete and clear",
  "joan_actions": {
    "add_tags": ["Ready"],
    "remove_tags": ["Needs-Clarification", "Clarification-Answered"],
    "add_comment": "ALS/1\nactor: ba\nintent: decision\naction: mark-ready\ntags.add: [Ready]\ntags.remove: [Needs-Clarification, Clarification-Answered]\nsummary: Requirements validated; task ready for architecture.",
    "move_to_column": "Analyse"
  },
  "worker_type": "ba",
  "task_id": "uuid-here"
}
```

### Architect Worker Result

```json
{
  "success": true,
  "summary": "Implementation plan created with 8 subtasks",
  "joan_actions": {
    "add_tags": ["Plan-Pending-Approval"],
    "remove_tags": ["Ready"],
    "add_comment": "ALS/1\nactor: architect\nintent: status\naction: plan-created\n...",
    "update_description": "## Implementation Plan\n\n### Development\n- [ ] DEV-1: ...\n..."
  },
  "worker_type": "architect",
  "task_id": "uuid-here"
}
```

### Dev Worker Result

```json
{
  "success": true,
  "summary": "Implemented feature with 5 files changed",
  "joan_actions": {
    "add_tags": ["Dev-Complete", "Design-Complete", "Test-Complete"],
    "remove_tags": ["Claimed-Dev-1", "Planned"],
    "add_comment": "ALS/1\nactor: dev\nintent: status\naction: implementation-complete\n...",
    "move_to_column": "Review",
    "update_description": "## Original Requirements\n{original description}\n\n---\n\n## 📋 Implementation Plan\n\n**Branch**: `feature/implement-xyz`\n\n### Sub-Tasks (completed)\n\n#### Design\n- [x] DES-1: Create component UI\n\n#### Development\n- [x] DEV-1: Implement core logic\n- [x] DEV-2: Add API integration\n\n#### Testing\n- [x] TEST-1: Unit tests for core logic"
  },
  "git_actions": {
    "branch_created": "feature/implement-xyz",
    "files_changed": ["src/a.ts", "src/b.ts", "tests/a.test.ts"],
    "commit_made": true,
    "commit_sha": "abc123",
    "pr_created": {
      "number": 42,
      "url": "https://github.com/org/repo/pull/42",
      "title": "feat: Implement XYZ feature"
    }
  },
  "worker_type": "dev",
  "task_id": "uuid-here"
}
```

### Reviewer Worker Result

```json
{
  "success": true,
  "summary": "Code review passed - approved for merge",
  "joan_actions": {
    "add_tags": ["Review-Approved"],
    "remove_tags": ["Review-In-Progress"],
    "add_comment": "ALS/1\nactor: reviewer\nintent: decision\naction: review-approve\n..."
  },
  "worker_type": "reviewer",
  "task_id": "uuid-here"
}
```

### Ops Worker Result

```json
{
  "success": true,
  "summary": "Merged to develop successfully",
  "joan_actions": {
    "add_tags": [],
    "remove_tags": ["Review-Approved", "Ops-Ready"],
    "add_comment": "ALS/1\nactor: ops\nintent: status\naction: ops-merge\n...",
    "move_to_column": "Deploy"
  },
  "git_actions": {
    "commit_sha": "def456"
  },
  "worker_type": "ops",
  "task_id": "uuid-here"
}
```

### Ops Worker Result (Invoking Architect for Conflict)

When Ops encounters a complex merge conflict that AI resolution can't handle,
it can invoke the Architect for specialist guidance:

```json
{
  "success": true,
  "summary": "Complex merge conflict detected; invoking Architect for guidance",
  "joan_actions": {
    "add_tags": ["Invoke-Architect"],
    "remove_tags": [],
    "add_comment": "ALS/1\nactor: ops\nintent: request\naction: invoke-request\ntags.add: [Invoke-Architect]\nsummary: Invoking Architect for merge conflict resolution guidance.\ndetails:\n- conflicting files: src/api/auth.ts, src/config/settings.ts\n- AI resolution failed: semantic conflict requires architectural decision",
    "move_to_column": null
  },
  "invoke_agent": {
    "agent_type": "architect",
    "mode": "advisory-conflict",
    "context": {
      "reason": "AI conflict resolution failed - semantic conflict requires architectural decision",
      "question": "How should we resolve the conflicting authentication approaches?",
      "files_of_interest": ["src/api/auth.ts", "src/config/settings.ts"],
      "conflict_details": {
        "conflicting_files": ["src/api/auth.ts", "src/config/settings.ts"],
        "develop_summary": "Refactored auth to use JWT tokens with refresh mechanism",
        "feature_summary": "Added OAuth2 provider integration with session tokens"
      }
    },
    "resume_as": {
      "agent_type": "ops",
      "mode": "merge-with-guidance"
    }
  },
  "worker_type": "ops",
  "task_id": "uuid-here"
}
```

## Coordinator Responsibilities

When receiving a WorkerResult, the coordinator MUST:

1. **Validate the result** - Check required fields are present
2. **Resolve tag names to IDs** - Use TAG_CACHE to convert names
3. **Execute joan_actions in order**:
   a. Add tags
   b. Remove tags
   c. Add comment
   d. Move to column
   e. Update description (if present)
4. **Handle stage_context** - If present, format and store as ALS handoff comment
5. **Handle invoke_agent** - If present:
   a. Add the invocation tag (e.g., `Invoke-Architect`)
   b. Store invocation context as ALS comment for the invoked agent
   c. Set INVOCATION_PENDING flag to skip sleep and re-poll immediately
   d. On next poll, dispatch the invoked agent with stored context
   e. After invoked agent completes, dispatch original worker in resume mode
6. **Verify post-conditions** - Re-fetch task and confirm state matches expected
7. **Handle failures** - If any action fails, log and potentially retry
8. **Handle needs_human** - If set, add appropriate flag tag and log

## Error Handling

If `success: false`:
- Check `errors` array for specific issues
- Check `needs_human` for intervention requirements
- Coordinator should NOT execute joan_actions on failure
- Coordinator should add appropriate failure tag

## Version History

- v1.1 (2026-01-21): Added `invoke_agent` field for cross-agent consultation
- v1.0 (2026-01-20): Initial schema for MCP Proxy Pattern
