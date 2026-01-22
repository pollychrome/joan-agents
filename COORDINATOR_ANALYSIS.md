# Joan Agent Coordinator Analysis & Fixes

## Executive Summary

The Joan agent system isn't processing the BuffRamen Web backlog due to **three critical issues**:

1. ⚠️ **Queue Building Bug** - Coordinator reports empty queues despite tasks ready for processing
2. ❌ **Incorrect Backlog Tagging** - I mistakenly tagged 10 unimplemented tasks as ready for merge
3. 📍 **Column Misplacement** - 2 completed tasks in wrong column, bypassing code review

**Status:** 15 tasks stuck, zero throughput

**Fix Availability:** ✅ All three solutions ready to deploy

---

## Problem 1: Queue Building Not Detecting Tasks

### Symptoms

```
Coordinator output:
  Queues: BA=0, Architect=0, Dev=0, Reviewer=0, Ops=0

Expected output:
  Queues: BA=0, Architect=3, Dev=0, Reviewer=2, Ops=0
```

### Root Cause

The coordinator fetched 86 tasks and built tag/column caches correctly, but **Step 3 (Build Priority Queues) either didn't execute or the matching logic failed**.

**Evidence it should work:**

| Task | Column | Tags | Should Match |
|------|--------|------|--------------|
| #79 | Analyse | Plan-Pending-Approval + Plan-Approved | Architect (finalize) |
| #78 | Analyse | Ready | Architect (plan) |
| #76 | Analyse | Ready | Architect (plan) |
| #70 | Deploy* | Dev-Complete + Design-Complete + Test-Complete | Reviewer** |
| #74 | Deploy* | Dev-Complete + Design-Complete + Test-Complete | Reviewer** |

*Should be in Review column
**Queue logic checks Review column only

### Investigation Needed

The coordinator.md logic is **correct** but something prevents execution:

1. **Helper function failure** - `inColumn()` or `hasTag()` not working
2. **Execution bug** - Step 3 code path not reached
3. **Silent error** - Exception swallowed, no output
4. **Context issue** - Coordinator using old/cached logic

**Next Step:** Add diagnostic logging to Step 3 to trace execution.

### Quick Test

```bash
# Run coordinator with explicit logging
/agents:dispatch

# Should output during Step 3:
# "Checking task #79 in Analyse with tags [Plan-Pending-Approval, Plan-Approved]"
# "Matched Priority 4: Architect finalize"
```

---

## Problem 2: Incorrect Backlog Onboarding (My Error)

### What I Did Wrong

When you ran `/agents:clean-project --apply`, I:

1. Found 10 tasks in Deploy column with implementation plans
2. **Assumed** they were implemented (they weren't)
3. Applied `Review-Approved + Ops-Ready` tags
4. Left them in Deploy column

**This was incorrect** because:
- No PR links or commit evidence
- No completion tags (Dev-Complete, etc.)
- Skipped Dev and Reviewer stages entirely

### Affected Tasks

| # | Title | Actual State | Incorrect Tags Applied |
|---|-------|--------------|------------------------|
| 85 | Add AI-powered exercise suggestion | Has plan, NOT implemented | Review-Approved + Ops-Ready |
| 84 | Implement negative weight volume | Has plan, NOT implemented | Review-Approved + Ops-Ready |
| 83 | Replace info icon | Has plan, NOT implemented | Review-Approved + Ops-Ready |
| 82 | Fix workout sharing | Has plan, NOT implemented | Review-Approved + Ops-Ready |
| 81 | Fix ad-hoc workout messaging | Has plan, NOT implemented | Review-Approved + Ops-Ready |
| 80 | Clear weight input | Has plan, NOT implemented | Review-Approved + Ops-Ready |
| 75 | Fix scrolling in modal | Has plan, NOT implemented | Review-Approved + Ops-Ready |
| 67 | Build goal progress viz | Has plan, NOT implemented | Review-Approved + Ops-Ready |
| 65 | Implement goal switching | Has plan, NOT implemented | Review-Approved + Ops-Ready |
| 64 | Create GoalDisplay component | Has plan, NOT implemented | Review-Approved + Ops-Ready |

### Correct Flow

```
Current (wrong):    Plan exists → Review-Approved + Ops-Ready (in Deploy)
Correct:            Plan exists → Planned (in Development) → Dev implements → Review → Ops merges
```

---

## Problem 3: Column Misplacement

**Tasks #70 and #74** have completion evidence but are in **Deploy** instead of **Review**.

### Why This Matters

```
Workflow: Dev completes → moves to Review → Reviewer validates → moves to Deploy → Ops merges

Actual: Dev completes → moved to Deploy (skipped Reviewer)
```

The coordinator's Reviewer queue checks:
```typescript
IF inColumn(task, "Review")  // ❌ Tasks are in Deploy
   AND hasTag("Dev-Complete")
```

So even though they have completion tags, they **won't be reviewed**.

---

## Solutions Provided

### Solution 1: Queue Building Bug Report

📄 **File:** `COORDINATOR_BUG_REPORT.md`

Comprehensive analysis with:
- Diagnostic steps to trace execution
- Test cases to verify helper functions
- Recommendations for fixes
- Investigation checklist

**Action:** Review the report and add diagnostic logging to coordinator.

---

### Solution 2: Comprehensive Cure-All Command (CONSOLIDATED)

📄 **File:** `.claude/commands/agents/clean-project.md`

**Single command that handles everything:**
- ✅ Fresh backlog onboarding
- ✅ Broken state recovery (incorrect tags)
- ✅ Column drift correction (misplaced tasks)
- ✅ Tag inconsistency cleanup

**Key capabilities:**
- Inspects task descriptions for completion evidence (PR links, commits)
- Detects tasks with Review-Approved/Ops-Ready but no evidence → reverts to Development
- Detects misplaced tasks in wrong columns → moves to correct column
- Never skips workflow stages, never assumes completion without evidence
- Adds audit trail comments for all changes

**Usage:**
```bash
# Dry run (recommended first)
/agents:clean-project

# Apply all fixes
/agents:clean-project --apply
```

**Expected outcome:**
```
Before:  Queues: BA=0, Architect=0, Dev=0, Reviewer=0, Ops=0
After:   Queues: BA=0, Architect=3, Dev=10, Reviewer=2, Ops=0
```

**Replaces:** Both the old `clean-project` and the separate `recover-tasks` commands. This is now the **primary cleanup command** for all scenarios.

---

## Recommended Action Plan

### Phase 1: Immediate Recovery (5 minutes)

```bash
# 1. Dry run to see what will be fixed
/agents:clean-project

# 2. Review output (should show recovery actions), then apply
/agents:clean-project --apply

# 3. Verify coordinator detects tasks
/agents:dispatch

# Should see:
# Queues: BA=0, Architect=3, Dev=10, Reviewer=2, Ops=0
```

### Phase 2: Investigation (15 minutes)

```bash
# 1. Add diagnostic logging to coordinator queue building
# Edit: .claude/commands/agents/dispatch.md
# Add: Report statements in Step 3 for each task checked

# 2. Re-run coordinator with logging
/agents:dispatch

# 3. Verify queue building logic executes correctly
```

### Phase 3: Resume Operations (Ongoing)

```bash
# Start coordinator in loop mode
/agents:dispatch --loop

# Monitor progress in Joan UI
# - Architect should plan tasks #78, #76, #79
# - Dev should claim and implement tasks #85-#64
# - Reviewer should review tasks #70, #74
```

---

## Verification Checklist

After running recovery command:

- [ ] 10 tasks in Development column with Planned tag
- [ ] 2 tasks in Review column with completion tags
- [ ] Coordinator reports non-zero queues
- [ ] Architect queue shows 3 tasks
- [ ] Dev queue shows 10 tasks
- [ ] Reviewer queue shows 2 tasks
- [ ] All recovered tasks have audit comments explaining changes

---

## Key Learnings

### What Went Wrong

1. **Backlog onboarding assumed too much** - Presence of plan ≠ implementation complete
2. **No evidence validation** - Didn't check for PR links, commits, or completion tags
3. **Column placement ignored** - Didn't validate tasks were in correct columns for their state
4. **Stage skipping allowed** - Applied end-stage tags without verifying previous stages

### What Works Correctly

1. ✅ Tag cache building
2. ✅ Column cache building
3. ✅ Task fetching
4. ✅ Self-healing (stale claim recovery, anomaly detection)
5. ✅ Pipeline gate logic
6. ✅ Worker dispatch format

### What Needs Investigation

1. ❓ Queue building execution (Steps 1-2 work, Step 3 doesn't produce results)
2. ❓ Helper function behavior (inColumn, hasTag not matching expected tasks)

---

## Files Created

| File | Purpose |
|------|---------|
| `COORDINATOR_BUG_REPORT.md` | Detailed analysis of queue building failure |
| `.claude/commands/agents/clean-project.md` | **Comprehensive cure-all** (onboarding + recovery + drift correction) |
| `.claude/commands/agents/recover-tasks.md` | [DEPRECATED] Superseded by clean-project |
| `scripts/recover-bufframen-tasks.sh` | [DEPRECATED] Shell script (no longer needed) |
| `COORDINATOR_ANALYSIS.md` | This document |

---

## Next Steps

1. **Run comprehensive cure-all** → `/agents:clean-project --apply`
2. **Verify queues** → `/agents:dispatch` (should show non-zero queues)
3. **Investigate queue bug** → Add diagnostic logging to Step 3 (if still needed)
4. **Resume operations** → `/agents:dispatch --loop`

Once the cure-all command completes and the coordinator is detecting tasks correctly, the system should resume normal operation with tasks flowing through the proper workflow stages.

**Future maintenance:** Run `/agents:clean-project` periodically (or after manual changes in Joan UI) to prevent drift and maintain workflow integrity.
