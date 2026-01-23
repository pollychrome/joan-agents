# ALS v0.1 Spec (Agentic Language Syntax)

ALS defines a compact, machine-readable comment block for all human and agent breadcrumbs.
Tags remain the only triggers; ALS is for auditability and coordination.

## Format
An ALS block is the first content in a comment:

```
ALS/1
actor: human|ba|architect|dev|reviewer|ops|coordinator
intent: request|response|decision|status|handoff|failure
action: <action-id>
tags.add: [TagA, TagB]
tags.remove: [TagC]
summary: One-line outcome (<= 120 chars).
details:
- Optional bullets with instructions or evidence.
links:
- pr: https://...
- plan: plan-123.md
```

Rules:
- ALS block must come first in the comment.
- `tags.add` and `tags.remove` must match the actual tag changes.
- Comments never trigger behavior; tags do.
- Action IDs are shared across actors; use `actor` to indicate who performed the action.

## Action IDs

### Context Handoff (All Stages)
- context-handoff

### BA
- clarify-request
- clarify-verified
- clarify-followup

### Architect
- plan-ready
- plan-approved
- plan-rejected

### Dev
- dev-start
- dev-complete
- rework-start
- rework-complete
- conflict-resolved
- dev-failure

### Reviewer
- review-start
- review-approve
- review-rework
- review-conflict

### Ops
- ops-merge
- ops-rework
- ops-conflict
- ops-deploy

### Invocation (Cross-Agent Consultation)
- invoke-request    # Worker requesting another agent's help
- invoke-advisory   # Invoked agent providing guidance
- invoke-resume     # Original workflow resuming after invocation

### Human (Inbox)
- clarify-answered
- plan-approved
- plan-rejected
- conflict-resolved
- merge-approved
- rework-requested

## Examples

### Plan Ready (Architect)
```
ALS/1
actor: architect
intent: request
action: plan-ready
tags.add: [Plan-Pending-Approval]
tags.remove: [Ready]
summary: Plan attached; add Plan-Approved to proceed.
links:
- plan: plan-123.md
```

### Plan Approved (Human)
```
ALS/1
actor: human
intent: decision
action: plan-approved
tags.add: [Plan-Approved]
tags.remove: []
summary: Approved plan for implementation.
```

### Review Rework (Reviewer)
```
ALS/1
actor: reviewer
intent: decision
action: review-rework
tags.add: [Rework-Requested, Planned]
tags.remove: [Review-In-Progress, Review-Approved, Rework-Complete, Dev-Complete, Design-Complete, Test-Complete]
summary: Fix null guard and add unit test.
details:
- src/foo.ts:42 add guard on user.profile
- tests: add unit coverage for empty profile
```

### Rework Complete (Dev)
```
ALS/1
actor: dev
intent: response
action: rework-complete
tags.add: [Dev-Complete, Design-Complete, Test-Complete, Rework-Complete]
tags.remove: [Planned, Rework-Requested, Merge-Conflict, Claimed-Dev-N]
summary: Addressed null guard + added unit test.
links:
- pr: https://github.com/org/repo/pull/123
```

### Invoke Request (Ops → Architect)
```
ALS/1
actor: ops
intent: request
action: invoke-request
tags.add: [Invoke-Architect]
tags.remove: []
summary: Invoking Architect for merge conflict resolution guidance.
details:
- conflicting files: src/api/auth.ts, src/config/settings.ts
- reason: AI resolution failed - semantic conflict requires architectural decision
- question: How should we resolve the conflicting auth approaches?
invoke_context:
  agent_type: architect
  mode: advisory-conflict
  resume_as: ops/merge-with-guidance
```

### Invoke Advisory (Architect Response)
```
ALS/1
actor: architect
intent: response
action: invoke-advisory
tags.add: [Architect-Assist-Complete]
tags.remove: [Invoke-Architect]
summary: Resolution strategy provided for auth conflict.
details:
- strategy: Keep JWT from develop, add OAuth2 as alternative provider
- src/api/auth.ts: Use feature's OAuth2 code but wrap in provider pattern
- src/config/settings.ts: Merge both configs under providers namespace
- rationale: Both approaches are valid; provider pattern allows flexibility
```

### Invoke Resume (Ops with Guidance)
```
ALS/1
actor: ops
intent: status
action: invoke-resume
tags.add: []
tags.remove: [Architect-Assist-Complete]
summary: Resuming merge with Architect guidance applied.
details:
- applied strategy from invoke-advisory comment
- resolved conflicts per Architect recommendations
```

## Human Inbox Integration

Human Inbox actions should add tags and post an ALS block in one click.
ALS blocks are the canonical breadcrumb format for manual intervention.

---

## Context Handoff Format

Context handoffs pass structured information between workflow stages. Unlike other ALS blocks, handoffs include a YAML payload with stage context.

### Handoff Block Structure

```yaml
ALS/1
actor: {from_stage}
intent: handoff
action: context-handoff
from_stage: {ba|architect|dev|reviewer}
to_stage: {architect|dev|reviewer|ops}
summary: {one-line context description}
key_decisions:
- {decision 1}
- {decision 2}
files_of_interest:
- {file/path/1}
- {file/path/2}
warnings:
- {warning 1}
dependencies:
- {dependency 1}
metadata:
  {key}: {value}
```

### Size Constraints

| Field | Limit |
|-------|-------|
| `key_decisions` | Max 5 items, 200 chars each |
| `files_of_interest` | Max 10 file paths |
| `warnings` | Max 3 items, 100 chars each |
| `dependencies` | Max 5 items |
| `metadata` | Max 1KB serialized |
| **Total** | Max 3KB serialized |

### Handoff Routing

| From Stage | To Stage | Contains |
|------------|----------|----------|
| BA | Architect | Requirements clarifications, user answers |
| Architect | Dev | Architecture decisions, file targets, dependencies |
| Dev | Reviewer | Implementation notes, files changed, warnings |
| Reviewer (approve) | Ops | Approval notes, any conditions |
| Reviewer (reject) | Dev | Rework feedback, specific issues |

### Examples

#### BA → Architect Handoff

```yaml
ALS/1
actor: ba
intent: handoff
action: context-handoff
from_stage: ba
to_stage: architect
summary: Requirements clarified for auth feature
key_decisions:
- Use JWT for session tokens (per user request)
- Token expiry set to 24 hours
- Refresh token support not required for MVP
files_of_interest:
- docs/auth-requirements.md
warnings:
- User mentioned future OAuth2 integration
```

#### Architect → Dev Handoff

```yaml
ALS/1
actor: architect
intent: handoff
action: context-handoff
from_stage: architect
to_stage: dev
summary: Architecture context for authentication implementation
key_decisions:
- Use React Context for auth state management
- Token refresh via Axios interceptor pattern
- Store tokens in httpOnly cookies (not localStorage)
files_of_interest:
- src/services/auth.service.ts
- src/context/AuthContext.tsx
- src/api/interceptors.ts
warnings:
- Existing localStorage usage needs migration
dependencies:
- axios ^1.6.0
- js-cookie ^3.0.0
metadata:
  branch_name: feature/add-authentication
  estimated_complexity: medium
```

#### Dev → Reviewer Handoff

```yaml
ALS/1
actor: dev
intent: handoff
action: context-handoff
from_stage: dev
to_stage: reviewer
summary: Implementation complete, auth flow ready for review
key_decisions:
- Used Context + useReducer (not Redux) per plan
- Added migration script for localStorage → cookies
- Included retry logic for token refresh
files_of_interest:
- src/context/AuthContext.tsx
- src/hooks/useAuth.ts
- src/api/authInterceptor.ts
- tests/auth.test.ts
warnings:
- Migration script needs manual testing in staging
- Added 2 new npm dependencies (js-cookie, axios)
metadata:
  pr_number: 42
  lines_added: 450
  lines_removed: 120
```

#### Reviewer → Ops Handoff (Approval)

```yaml
ALS/1
actor: reviewer
intent: handoff
action: context-handoff
from_stage: reviewer
to_stage: ops
summary: Review approved, ready for merge to develop
key_decisions:
- Code quality acceptable
- Tests passing (87% coverage)
- Security review passed
files_of_interest:
- src/context/AuthContext.tsx
warnings:
- Minor: Consider splitting auth context in future refactor
metadata:
  review_duration_minutes: 45
  blockers_found: 0
  warnings_noted: 1
```

#### Reviewer → Dev Handoff (Rework)

```yaml
ALS/1
actor: reviewer
intent: handoff
action: context-handoff
from_stage: reviewer
to_stage: dev
summary: Rework required - 2 blockers found
key_decisions:
- BLOCKER: Add null check in AuthContext line 42
- BLOCKER: Fix failing test in auth.test.ts
- WARNING: Consider memoizing useAuth hook
files_of_interest:
- src/context/AuthContext.tsx:42
- tests/auth.test.ts:67
metadata:
  blockers: 2
  warnings: 1
```

### Parsing Handoffs

To extract the latest handoff for a stage transition:

1. Scan task comments in reverse chronological order
2. Find ALS block with `intent: handoff` and matching `from_stage`/`to_stage`
3. Parse YAML content after the ALS header
4. Use first matching handoff (most recent)

**Note:** Handoffs are write-only breadcrumbs. Workers should not parse ALL handoffs - only the most recent one matching their expected transition.
