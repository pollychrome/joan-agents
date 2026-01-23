---
description: '[DEPRECATED] Use /agents:clean-project instead'
argument-hint: [--apply]
allowed-tools: mcp__joan__*, Read
---

# ⚠️ DEPRECATED - Use /agents:clean-project Instead

**This command has been superseded by `/agents:clean-project`**, which provides comprehensive cure-all functionality including:
- All recovery logic from this command
- Plus backlog onboarding
- Plus column drift detection
- Plus tag inconsistency cleanup

**Use the main command:**
```bash
/agents:clean-project          # Dry run
/agents:clean-project --apply  # Apply fixes
```

---

# Original Task Recovery Command (Historical)

Fixes the broken state caused by incorrect /agents:clean-project tagging.

## What This Fixes

1. **10 tasks** incorrectly tagged with Review-Approved + Ops-Ready (should be in Development with Planned)
2. **2 tasks** in Deploy column that should be in Review (for code review)

## Mode

- `--apply` → Execute fixes
- No flag → Dry run (report only)

---

## Configuration

```typescript
PROJECT_ID = "f2f5340a-42c8-4ca1-b327-d465dee21b8e"
PROJECT_NAME = "BuffRamen Web"

# Tag IDs
TAG_IDS = {
  "Review-Approved": "a111daee-56da-40cd-93a3-a8fdb3e4203c",
  "Ops-Ready": "b8c0a56a-2fdc-4df9-8481-a2a0a3d3fd3f",
  "Planned": "81dde4ea-39be-4930-b8b0-5d0456bbfe3c"
}

# Column IDs
COLUMN_IDS = {
  "Development": "a19e07cc-520d-492a-bc93-3b1b8c6d5746",
  "Review": "bd96db3b-9050-4980-a47b-27eb8d0f33d3"
}
```

---

## Recovery Actions

### Group 1: Remove Incorrect End-Stage Tags (10 tasks)

These tasks have implementation plans but NO evidence of completion.
They were incorrectly tagged as ready for Ops merge.

**Correct flow:** Development (Planned) → Dev implements → Review → Ops

```typescript
TASKS_GROUP_1 = [
  {id: "b45ae00f-c899-4a1f-8118-32e88e005c3a", num: 85, title: "Add AI-powered exercise suggestion"},
  {id: "e6ed2086-4235-4fc9-9e2a-a36797b90017", num: 84, title: "Implement negative weight volume calculation"},
  {id: "2e46f9af-ecf0-4cbd-bb44-5d21d56629c9", num: 83, title: "Replace info icon with video icon"},
  {id: "f84c87bb-2112-4c98-acda-c9d08812d05c", num: 82, title: "Fix workout sharing exercise sequence"},
  {id: "740d89d4-c654-4657-b56e-edd1c75235eb", num: 81, title: "Fix ad-hoc workout completion messaging"},
  {id: "3834cea3-afc2-447b-9430-85d554884710", num: 80, title: "Clear weight input during calibration"},
  {id: "535123ac-34f6-493b-bc44-f08e22b755b5", num: 75, title: "Fix scrolling in exercise search modal"},
  {id: "13fde474-e351-4e80-a915-3b8c34246fff", num: 67, title: "Build goal progress visualization"},
  {id: "db6d62e1-0455-4bbb-a6b5-680099db0540", num: 65, title: "Implement goal switching"},
  {id: "1f7f90d8-330c-4e2a-8528-19017649ab41", num: 64, title: "Create GoalDisplay component"}
]

FOR EACH task IN TASKS_GROUP_1:
  actions = {
    remove_tags: ["Review-Approved", "Ops-Ready"],
    add_tags: ["Planned"],
    move_to_column: "Development",
    reason: "Task has plan but was never implemented - reverting to Development"
  }
```

### Group 2: Fix Column Misplacement (2 tasks)

These tasks have completion tags (Dev-Complete, Design-Complete, Test-Complete) but are in **Deploy** column instead of **Review** column. They need code review before Ops can merge.

```typescript
TASKS_GROUP_2 = [
  {id: "ef21d8d8-d691-48c9-93bc-78db24d0513d", num: 70, title: "Add re-calibrate option to exercise menu"},
  {id: "e369f776-e362-4c44-8a53-de43ab4321df", num: 74, title: "Fix double-tap rep confirmation"}
]

FOR EACH task IN TASKS_GROUP_2:
  actions = {
    move_to_column: "Review",
    reason: "Task has completion tags but was in Deploy, bypassing Reviewer"
  }
```

---

## Execution Logic

```typescript
Report: "═══════════════════════════════════════════════════════════════"
Report: "  Task Recovery for BuffRamen Web"
Report: "═══════════════════════════════════════════════════════════════"
Report: ""

DRY_RUN = ("--apply" NOT IN args)

IF DRY_RUN:
  Report: "MODE: Dry run (use --apply to execute)"
ELSE:
  Report: "MODE: Applying fixes"

Report: ""
Report: "Group 1: Remove incorrect end-stage tags (10 tasks)"
Report: "Group 2: Fix column misplacement (2 tasks)"
Report: ""

success_count = 0
failure_count = 0

# === GROUP 1: Remove incorrect tags ===

Report: "───────────────────────────────────────────────────────────────"
Report: "  Group 1: Reverting to Development"
Report: "───────────────────────────────────────────────────────────────"
Report: ""

FOR task IN TASKS_GROUP_1:
  Report: "Task #{task.num}: {task.title}"

  IF DRY_RUN:
    Report: "  [DRY RUN] Would remove: Review-Approved, Ops-Ready"
    Report: "  [DRY RUN] Would add: Planned"
    Report: "  [DRY RUN] Would move to: Development"
  ELSE:
    TRY:
      # Remove incorrect tags
      mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_IDS["Review-Approved"])
      Report: "  ✓ Removed Review-Approved"

      mcp__joan__remove_tag_from_task(PROJECT_ID, task.id, TAG_IDS["Ops-Ready"])
      Report: "  ✓ Removed Ops-Ready"

      # Add correct tag
      mcp__joan__add_tag_to_task(PROJECT_ID, task.id, TAG_IDS["Planned"])
      Report: "  ✓ Added Planned"

      # Move to correct column
      mcp__joan__update_task(task.id, column_id=COLUMN_IDS["Development"])
      Report: "  ✓ Moved to Development"

      # Add audit comment
      comment = "ALS/1
actor: coordinator
intent: recovery
action: revert-incorrect-tagging
tags.add: [Planned]
tags.remove: [Review-Approved, Ops-Ready]
summary: Reverted incorrect end-stage tagging from backlog onboarding.
details:
- issue: Task was tagged as ready for Ops merge but was never implemented
- correction: Moved to Development with Planned tag
- next_step: Dev worker will claim and implement this task"

      mcp__joan__create_task_comment(task.id, comment)
      Report: "  ✓ Added audit comment"

      success_count++

    CATCH error:
      Report: "  ✗ Failed: {error.message}"
      failure_count++

  Report: ""

# === GROUP 2: Fix column misplacement ===

Report: "───────────────────────────────────────────────────────────────"
Report: "  Group 2: Moving to Review"
Report: "───────────────────────────────────────────────────────────────"
Report: ""

FOR task IN TASKS_GROUP_2:
  Report: "Task #{task.num}: {task.title}"

  IF DRY_RUN:
    Report: "  [DRY RUN] Would move from Deploy to Review"
  ELSE:
    TRY:
      # Move to correct column
      mcp__joan__update_task(task.id, column_id=COLUMN_IDS["Review"])
      Report: "  ✓ Moved to Review"

      # Add audit comment
      comment = "ALS/1
actor: coordinator
intent: recovery
action: column-correction
tags.add: []
tags.remove: []
summary: Moved from Deploy to Review for proper code review.
details:
- issue: Task has completion tags but was in Deploy, bypassing Reviewer
- correction: Moved to Review column
- next_step: Reviewer will validate and approve for merge"

      mcp__joan__create_task_comment(task.id, comment)
      Report: "  ✓ Added audit comment"

      success_count++

    CATCH error:
      Report: "  ✗ Failed: {error.message}"
      failure_count++

  Report: ""

# === SUMMARY ===

Report: "═══════════════════════════════════════════════════════════════"
Report: "  Summary"
Report: "═══════════════════════════════════════════════════════════════"
Report: ""

IF DRY_RUN:
  Report: "Dry run complete - no changes made"
  Report: "Run with --apply to execute these fixes"
ELSE:
  Report: "Recovery complete:"
  Report: "  Success: {success_count} tasks"
  Report: "  Failed:  {failure_count} tasks"
  Report: ""
  Report: "Next steps:"
  Report: "  1. Verify task placement in Joan UI"
  Report: "  2. Run /agents:dispatch --loop to process corrected tasks"
  Report: "  3. Monitor coordinator queue building"

Report: ""
Report: "═══════════════════════════════════════════════════════════════"
```

---

## Usage

```bash
# Dry run (recommended first)
/agents:recover-tasks

# Apply fixes
/agents:recover-tasks --apply
```

---

## Expected Outcome

After running with `--apply`:

1. **10 tasks** will be in Development column with Planned tag (ready for dev to claim)
2. **2 tasks** will be in Review column with completion tags (ready for reviewer)
3. All audit comments will explain the recovery actions
4. Coordinator will detect and process these tasks on next poll

## Verification

After recovery, verify with:

```bash
# Run coordinator in single-pass mode
/agents:dispatch

# Should see:
# Queues: BA=0, Architect=3, Dev=10, Reviewer=2, Ops=0
```

The coordinator should now correctly queue:
- **3 Architect tasks** (#79, #78, #76 in Analyse with Ready/Plan-Approved)
- **10 Dev tasks** (#85, #84, #83, #82, #81, #80, #75, #67, #65, #64 in Development with Planned)
- **2 Reviewer tasks** (#70, #74 in Review with completion tags)
