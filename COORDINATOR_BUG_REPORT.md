# Coordinator Queue Building Bug Report

## Issue Summary

The coordinator reported `Queues: BA=0, Architect=0, Dev=0, Reviewer=0, Ops=0` but multiple tasks should have been queued.

## Root Causes

### Bug 1: Tasks in Wrong Columns (Critical)

**Tasks #70 and #74** have completion tags but are in **Deploy** column instead of **Review** column.

```
Expected: Dev completes → moves to Review column (for Reviewer)
Actual:   Tasks manually moved to Deploy (bypassing Reviewer)
```

**Queue matching logic (lines 683-691):**
```typescript
IF inColumn(task, "Review")     // ❌ Fails - tasks are in Deploy
   AND hasTag("Dev-Complete")
   AND hasTag("Design-Complete")
   AND hasTag("Test-Complete")
```

**Why this happened:**
- Tasks were manually created/moved in Joan UI
- Bypassed the normal Dev → Review workflow
- The coordinator correctly uses `column_id` but can't find tasks in wrong columns

---

### Bug 2: Architect Queue Not Building (Critical)

**Tasks #79, #78, #76** are in Analyse column with workflow tags but weren't queued.

From coordinator output:
```
Step 1: Cache Tags and Columns ✅
Step 2: Fetch Tasks ✅ (86 tasks)
Step 3: Build Priority Queues
Queues: BA=0, Architect=0, Dev=0, Reviewer=0, Ops=0 ❌
```

**Expected queue matches:**

| Task | Column | Tags | Should Match |
|------|--------|------|--------------|
| #79 | Analyse | Plan-Pending-Approval + Plan-Approved | Priority 4: Architect finalize |
| #78 | Analyse | Ready | Priority 5: Architect plan |
| #76 | Analyse | Ready | Priority 5: Architect plan |

**Possible causes:**

1. **inColumn() helper failure** - Not correctly checking column_id
2. **TAG_CACHE not populated** - Tags not found during hasTag() checks
3. **COLUMN_CACHE not populated** - Column name → ID mapping failed
4. **Queue building logic skipped** - Execution never reached Step 3

**Most likely:** The coordinator execution is NOT actually following the prompt logic in dispatch.md. It may be using outdated/simplified logic or hitting an execution bug.

---

### Bug 3: Deploy Column Handling Gap

**Priority 9 (lines 703-709)** tries to handle tasks in Deploy:

```typescript
IF (inColumn(task, "Review") OR inColumn(task, "Deploy"))
   AND hasTag("Review-Approved")
   AND hasTag("Ops-Ready"):
  OPS_QUEUE.push({task, mode: "merge"})
```

But there's **no similar fallback** for Reviewer queue. Tasks with completion tags in Deploy are orphaned.

---

## Diagnostic Steps

### Step 1: Verify Column Cache Building

The coordinator should output:
```
Found 6 column(s):
 - To Do (ID: 09dc2866-8091-4250-9d6d-dc7ae1b51f00)
 - Analyse (ID: 059e4ad0-7a16-4eda-b54a-2c2af842c574)
 - Development (ID: a19e07cc-520d-492a-bc93-3b1b8c6d5746)
 - Review (ID: bd96db3b-9050-4980-a47b-27eb8d0f33d3)
 - Deploy (ID: a2eed4df-d151-40ad-9ca4-c7b1ccda8ce9)
 - Done (ID: 524f88e1-cc4b-4e90-8197-e1847453d1e3)
```

✅ This succeeded in the coordinator output.

### Step 2: Verify Tag Cache Building

The coordinator should output:
```
Found 21 tag(s) for project f2f5340a-42c8-4ca1-b327-d465dee21b8e
```

✅ This succeeded - all workflow tags present.

### Step 3: Verify Task Fetching

```
Found 86 task(s)
```

✅ This succeeded.

### Step 4: Check Queue Building Execution

**Expected output:**
```
For each task in tasks:
  # Check Priority 1: Dev conflicts
  # Check Priority 2: Dev rework
  ...
  # Check Priority 8: Reviewer

Report queue sizes:
"Queues: BA=0, Architect=3, Dev=0, Reviewer=2, Ops=0"
```

**Actual output:**
```
Queues: BA=0, Architect=0, Dev=0, Reviewer=0, Ops=0
```

❌ Queue building logic either didn't execute OR the helpers (inColumn, hasTag) failed.

---

## Testing Required

### Test 1: Manual Queue Building

Verify the logic with explicit checks:

```typescript
// For task #79
task = get_task("c04455f0-fff3-4700-861b-ae8bbffadfa5")
console.log("Task #79:")
console.log("  column_id:", task.column_id)
console.log("  Expected Analyse:", COLUMN_CACHE["Analyse"])
console.log("  inColumn(Analyse):", task.column_id === COLUMN_CACHE["Analyse"])
console.log("  Tags:", task.tags.map(t => t.name))
console.log("  hasTag(Plan-Pending-Approval):", task.tags.find(t => t.id === TAG_CACHE["Plan-Pending-Approval"]))
console.log("  hasTag(Plan-Approved):", task.tags.find(t => t.id === TAG_CACHE["Plan-Approved"]))
```

Expected: All checks return true → should queue for Architect finalize.

### Test 2: Diagnostic Logging

Add logging in dispatch.md Step 3:

```typescript
Report: "Building queues for {tasks.length} tasks..."

FOR EACH task:
  IF task.tags.length > 0 OR inColumn(task, "Analyse") OR inColumn(task, "Review"):
    Report: "  Checking '{task.title}' (column: {get_column_name(task.column_id)}, tags: {task.tags.map(t => t.name)})"
```

This will show which tasks are being evaluated.

---

## Recommendations

### Immediate Fix 1: Move Misplaced Tasks

```bash
# Move #70, #74 from Deploy → Review
joan update_task --id=ef21d8d8-d691-48c9-93bc-78db24d0513d --column=Review
joan update_task --id=e369f776-e362-4c44-8a53-de43ab4321df --column=Review
```

### Immediate Fix 2: Add Diagnostic UNQUEUED Reporting

Already present in dispatch.md (lines 718-726):

```typescript
# DIAGNOSTIC: Identify tasks with workflow tags that didn't match any queue
workflow_tags_present = []
FOR tagName IN WORKFLOW_TAGS:
  IF hasTag(task, tagName):
    workflow_tags_present.push(tagName)

IF workflow_tags_present.length > 0:
  Report: "UNQUEUED: '{task.title}' has tags {workflow_tags_present} in column '{task.column}' but didn't match any queue condition"
```

This would have caught tasks #78, #76, #79 if the logic ran.

### Long-term Fix: Add Deploy Fallback for Reviewer

Update Priority 8 (lines 683-691):

```typescript
# Priority 8: Reviewer tasks ready for review
# NOTE: Check both Review AND Deploy to handle column drift
IF (inColumn(task, "Review") OR inColumn(task, "Deploy"))  // 👈 Add Deploy fallback
   AND hasTag("Dev-Complete")
   AND hasTag("Design-Complete")
   AND hasTag("Test-Complete")
   AND NOT hasTag("Review-In-Progress")
   AND NOT hasTag("Review-Approved")
   AND NOT hasTag("Rework-Requested"):
  REVIEWER_QUEUE.push({task})
  CONTINUE
```

### Investigation Required

**Why didn't the coordinator run the queue building logic?**

Possible explanations:
1. The coordinator agent is NOT using the dispatch.md prompt
2. The Task tool isn't correctly loading the command file
3. There's a runtime error that's being silently swallowed
4. The coordinator is using cached/old logic

**Next step:** Run the coordinator with explicit logging enabled to see if Step 3 executes.

---

## Impact

- **3 tasks** stuck in Analyse (not being planned)
- **2 tasks** stuck in Deploy (not being reviewed)
- **10 tasks** incorrectly tagged as Review-Approved + Ops-Ready (will be processed but shouldn't have been)

**Total stuck:** ~15 tasks affected
