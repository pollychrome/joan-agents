---
description: Diagnose and recover tasks from invalid workflow states
argument-hint: [--project=NAME] [--task=ID] [--dry-run] [--verbose]
allowed-tools: Bash, Read, mcp__joan__*
---

# Doctor Agent

The Doctor agent specializes in diagnosing and recovering tasks from invalid workflow states.
It can unblock pipelines, fix orphaned tags, and restore tasks to valid states.

## When to Use

- Pipeline is stuck with no apparent cause
- Tasks have conflicting or missing tags
- Scheduler reports idle despite pending work
- Manual task moves left tasks in limbo
- After coordinator crashes or context overflow

## Arguments

- `--project=NAME` → Target specific project (default: current directory's project)
- `--task=ID` → Diagnose/fix specific task only
- `--dry-run` → Report issues without fixing them
- `--verbose` → Show detailed diagnostic information

## Configuration

Load from `.joan-agents.json`:
```
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName
```

## Execution

### Step 1: Load Project State

```
1. Fetch all project tags → TAG_CACHE
2. Fetch all project columns → COLUMN_CACHE
3. Fetch all tasks with full details
4. Build task state map

Report: "Doctor examining {PROJECT_NAME}..."
Report: "Found {tasks.length} tasks across {columns.length} columns"
```

### Step 2: Diagnostic Scan

Run comprehensive diagnostics on all tasks (or single task if --task specified):

```
ISSUES = []
WARNINGS = []

For each task:

  # ═══════════════════════════════════════════════════════════════
  # DIAGNOSIS 1: Invalid Tag Combinations
  # ═══════════════════════════════════════════════════════════════

  # Check for conflicting tags that should never coexist
  INVALID_COMBOS = [
    ["Ready", "Plan-Pending-Approval"],
    ["Ready", "Planned"],
    ["Plan-Approved", "Plan-Rejected"],
    ["Review-Approved", "Rework-Requested"],
    ["Claimed-Dev-*", "Dev-Complete"],
    ["Claimed-Dev-*", "Implementation-Failed"],
  ]

  FOR combo IN INVALID_COMBOS:
    IF task has all tags in combo:
      ISSUES.push({
        task: task,
        type: "INVALID_TAG_COMBO",
        severity: "HIGH",
        description: "Task has conflicting tags: {combo}",
        tags_involved: combo,
        fix: {
          action: "remove_stale_tag",
          tag_to_remove: determine_stale_tag(combo),
          reason: "Remove older/invalid tag to restore valid state"
        }
      })

  # ═══════════════════════════════════════════════════════════════
  # DIAGNOSIS 2: Column/Tag Mismatch
  # ═══════════════════════════════════════════════════════════════

  # Tasks in wrong column for their tags
  IF inColumn(task, "Development"):
    IF NOT hasAnyTag(task, ["Planned", "Rework-Requested", "Merge-Conflict", "Claimed-Dev-*", "Implementation-Failed", "Branch-Setup-Failed"]):
      ISSUES.push({
        task: task,
        type: "ORPHANED_IN_DEVELOPMENT",
        severity: "HIGH",
        description: "Task in Development without workflow tags",
        current_tags: task.tags,
        fix: {
          action: "add_tag_or_move",
          options: [
            {add_tag: "Planned", reason: "If task has a plan, make it claimable"},
            {move_to: "Analyse", reason: "If no plan, needs architect"}
          ]
        }
      })

  IF inColumn(task, "Review"):
    has_completion = hasTag(task, "Dev-Complete") AND hasTag(task, "Design-Complete") AND hasTag(task, "Test-Complete")
    has_review_state = hasTag(task, "Review-Approved") OR hasTag(task, "Rework-Requested") OR hasTag(task, "Review-In-Progress")
    has_rework = hasTag(task, "Rework-Complete")

    IF NOT (has_completion OR has_review_state OR has_rework):
      ISSUES.push({
        task: task,
        type: "ORPHANED_IN_REVIEW",
        severity: "HIGH",
        description: "Task in Review without completion tags or review state",
        current_tags: task.tags,
        fix: {
          action: "move_to_development",
          add_tag: "Planned",
          reason: "Task needs to go through dev workflow properly"
        }
      })

  IF inColumn(task, "Deploy"):
    # Deploy should have NO workflow tags (waiting for production deploy)
    workflow_tags = get_workflow_tags(task)
    IF workflow_tags.length > 0:
      ISSUES.push({
        task: task,
        type: "STALE_TAGS_IN_DEPLOY",
        severity: "MEDIUM",
        description: "Task in Deploy has stale workflow tags: {workflow_tags}",
        current_tags: workflow_tags,
        fix: {
          action: "remove_tags",
          tags_to_remove: workflow_tags,
          reason: "Deploy tasks should have no workflow tags"
        }
      })

  IF inColumn(task, "Analyse"):
    # Analyse tasks should have: Ready, Plan-Pending-Approval, Needs-Clarification, or Plan-Approved
    valid_analyse_tags = ["Ready", "Plan-Pending-Approval", "Plan-Approved", "Plan-Rejected", "Needs-Clarification", "Clarification-Answered"]
    has_valid = false
    FOR tag IN valid_analyse_tags:
      IF hasTag(task, tag):
        has_valid = true
        BREAK

    IF NOT has_valid:
      ISSUES.push({
        task: task,
        type: "ORPHANED_IN_ANALYSE",
        severity: "HIGH",
        description: "Task in Analyse without expected workflow tags",
        current_tags: task.tags,
        fix: {
          action: "add_tag",
          tag_to_add: "Ready",
          reason: "Make task available for architect planning"
        }
      })

  # ═══════════════════════════════════════════════════════════════
  # DIAGNOSIS 3: Stale Claims
  # ═══════════════════════════════════════════════════════════════

  IF hasTag(task, "Claimed-Dev-1"):
    claim_age_hours = (NOW - task.updated_at) in hours

    IF claim_age_hours > 2:
      ISSUES.push({
        task: task,
        type: "STALE_CLAIM",
        severity: "HIGH",
        description: "Task claimed for {claim_age_hours} hours without progress",
        claim_age: claim_age_hours,
        fix: {
          action: "release_claim",
          tag_to_remove: "Claimed-Dev-1",
          reason: "Release stale claim so task can be picked up"
        }
      })

  # ═══════════════════════════════════════════════════════════════
  # DIAGNOSIS 4: Pipeline Blockers
  # ═══════════════════════════════════════════════════════════════

  # Tasks that should progress but are stuck
  IF inColumn(task, "Analyse") AND hasTag(task, "Plan-Pending-Approval") AND hasTag(task, "Plan-Approved"):
    state_age_hours = (NOW - task.updated_at) in hours

    IF state_age_hours > 1:
      ISSUES.push({
        task: task,
        type: "STUCK_PLAN_FINALIZATION",
        severity: "HIGH",
        description: "Plan approved {state_age_hours} hours ago but not finalized",
        fix: {
          action: "flag_for_architect",
          reason: "Architect needs to finalize and move to Development"
        }
      })

  IF inColumn(task, "Review") AND hasTag(task, "Review-Approved") AND hasTag(task, "Ops-Ready"):
    state_age_hours = (NOW - task.updated_at) in hours

    IF state_age_hours > 1:
      ISSUES.push({
        task: task,
        type: "STUCK_OPS_MERGE",
        severity: "HIGH",
        description: "Task approved for merge {state_age_hours} hours ago",
        fix: {
          action: "flag_for_ops",
          reason: "Ops needs to merge this PR"
        }
      })

  # ═══════════════════════════════════════════════════════════════
  # DIAGNOSIS 5: Missing Prerequisites
  # ═══════════════════════════════════════════════════════════════

  IF hasTag(task, "Plan-Approved") AND NOT hasTag(task, "Plan-Pending-Approval"):
    IF NOT inColumn(task, "Development") AND NOT inColumn(task, "Review") AND NOT inColumn(task, "Deploy") AND NOT inColumn(task, "Done"):
      ISSUES.push({
        task: task,
        type: "ORPHANED_APPROVAL",
        severity: "MEDIUM",
        description: "Plan-Approved without Plan-Pending-Approval",
        fix: {
          action: "add_missing_tag",
          tag_to_add: "Plan-Pending-Approval",
          reason: "Restore paired tags for architect finalization"
        }
      })

  # ═══════════════════════════════════════════════════════════════
  # DIAGNOSIS 6: Git/PR State Mismatches
  # ═══════════════════════════════════════════════════════════════

  # Check if task mentions a PR that might already be merged
  IF inColumn(task, "Review") OR inColumn(task, "Development"):
    pr_match = extract_pr_number_from_description(task.description)
    IF pr_match:
      # Check PR status via gh CLI
      pr_status = check_pr_status(pr_match)

      IF pr_status == "merged" AND NOT inColumn(task, "Deploy") AND NOT inColumn(task, "Done"):
        ISSUES.push({
          task: task,
          type: "PR_ALREADY_MERGED",
          severity: "HIGH",
          description: "PR #{pr_match} is merged but task not in Deploy/Done",
          pr_number: pr_match,
          fix: {
            action: "move_to_deploy",
            remove_tags: ["all workflow tags"],
            reason: "PR is already merged, task should be in Deploy"
          }
        })

      IF pr_status == "closed" AND NOT hasTag(task, "Rework-Requested"):
        WARNINGS.push({
          task: task,
          type: "PR_CLOSED_WITHOUT_MERGE",
          description: "PR #{pr_match} was closed without merging",
          recommendation: "May need manual intervention to determine next steps"
        })

  # ═══════════════════════════════════════════════════════════════
  # DIAGNOSIS 7: Webhook Configuration Health
  # ═══════════════════════════════════════════════════════════════

  # Only check webhooks once (not per-task)
  IF NOT webhook_check_done:
    webhook_check_done = true

    # Load webhook config from .joan-agents.json
    webhook_config = config.settings.webhooks

    IF webhook_config AND webhook_config.enabled:
      # Check if webhook receiver is running
      receiver_running = Bash: pgrep -f "webhook-receiver" > /dev/null && echo "running" || echo "stopped"

      IF receiver_running == "stopped":
        WARNINGS.push({
          type: "WEBHOOK_RECEIVER_NOT_RUNNING",
          description: "Webhooks enabled but receiver is not running",
          recommendation: "Start receiver with: ./scripts/webhook-receiver.sh --port {webhook_config.port}"
        })

      # Check for recent webhook log activity (if log exists)
      webhook_log = "{PROJECT_DIR}/.claude/logs/webhook-receiver.log"
      IF file_exists(webhook_log):
        # Check if log was updated in last 24 hours
        log_age_hours = Bash: find {webhook_log} -mtime -1 | wc -l
        IF log_age_hours == 0:
          WARNINGS.push({
            type: "WEBHOOK_LOG_STALE",
            description: "Webhook receiver log hasn't been updated in 24+ hours",
            recommendation: "Check if webhook URL is correctly configured in Joan project settings"
          })

      # Check if webhook secret is configured
      IF NOT webhook_config.secret:
        WARNINGS.push({
          type: "WEBHOOK_NO_SECRET",
          description: "Webhooks enabled but no secret configured",
          recommendation: "Run /agents:init to generate a webhook secret"
        })

Report: ""
Report: "═══════════════════════════════════════════════════════════════"
Report: "DIAGNOSTIC REPORT"
Report: "═══════════════════════════════════════════════════════════════"
Report: ""
Report: "Issues found: {ISSUES.length}"
Report: "Warnings: {WARNINGS.length}"
Report: ""

IF ISSUES.length == 0 AND WARNINGS.length == 0:
  Report: "✓ All tasks are in valid workflow states"
  Report: "✓ No pipeline blockers detected"
  Report: "✓ No action needed"
  EXIT

FOR issue IN ISSUES:
  Report: "──────────────────────────────────────────────────────────────"
  Report: "[{issue.severity}] {issue.type}"
  Report: "Task: #{issue.task.task_number} {issue.task.title}"
  Report: "Column: {issue.task.column}"
  Report: "Tags: {issue.task.tags}"
  Report: "Problem: {issue.description}"
  Report: "Fix: {issue.fix.action} - {issue.fix.reason}"

FOR warning IN WARNINGS:
  Report: "──────────────────────────────────────────────────────────────"
  Report: "[WARNING] {warning.type}"
  Report: "Task: #{warning.task.task_number} {warning.task.title}"
  Report: "Note: {warning.description}"
  Report: "Recommendation: {warning.recommendation}"
```

### Step 3: Apply Fixes (unless --dry-run)

```
IF DRY_RUN:
  Report: ""
  Report: "DRY RUN - No changes applied"
  Report: "Run without --dry-run to apply fixes"
  EXIT

Report: ""
Report: "═══════════════════════════════════════════════════════════════"
Report: "APPLYING FIXES"
Report: "═══════════════════════════════════════════════════════════════"

FIXED = 0
FAILED = 0

FOR issue IN ISSUES:
  Report: ""
  Report: "Fixing: #{issue.task.task_number} {issue.task.title}"

  TRY:
    SWITCH issue.fix.action:

      CASE "remove_stale_tag":
        mcp__joan__remove_tag_from_task(PROJECT_ID, issue.task.id, TAG_CACHE[issue.fix.tag_to_remove])
        add_doctor_comment(issue.task.id, "Removed stale tag: {issue.fix.tag_to_remove}", issue)
        Report: "  ✓ Removed tag: {issue.fix.tag_to_remove}"
        FIXED++

      CASE "remove_tags":
        FOR tag_name IN issue.fix.tags_to_remove:
          IF TAG_CACHE[tag_name]:
            mcp__joan__remove_tag_from_task(PROJECT_ID, issue.task.id, TAG_CACHE[tag_name])
        add_doctor_comment(issue.task.id, "Removed stale tags: {issue.fix.tags_to_remove}", issue)
        Report: "  ✓ Removed tags: {issue.fix.tags_to_remove}"
        FIXED++

      CASE "add_tag":
        mcp__joan__add_tag_to_task(PROJECT_ID, issue.task.id, TAG_CACHE[issue.fix.tag_to_add])
        add_doctor_comment(issue.task.id, "Added missing tag: {issue.fix.tag_to_add}", issue)
        Report: "  ✓ Added tag: {issue.fix.tag_to_add}"
        FIXED++

      CASE "add_missing_tag":
        mcp__joan__add_tag_to_task(PROJECT_ID, issue.task.id, TAG_CACHE[issue.fix.tag_to_add])
        add_doctor_comment(issue.task.id, "Added missing prerequisite tag: {issue.fix.tag_to_add}", issue)
        Report: "  ✓ Added tag: {issue.fix.tag_to_add}"
        FIXED++

      CASE "release_claim":
        mcp__joan__remove_tag_from_task(PROJECT_ID, issue.task.id, TAG_CACHE[issue.fix.tag_to_remove])
        add_doctor_comment(issue.task.id, "Released stale claim after {issue.claim_age} hours", issue)
        Report: "  ✓ Released claim: {issue.fix.tag_to_remove}"
        FIXED++

      CASE "move_to_development":
        mcp__joan__update_task(issue.task.id, column_id=COLUMN_CACHE["Development"])
        mcp__joan__add_tag_to_task(PROJECT_ID, issue.task.id, TAG_CACHE[issue.fix.add_tag])
        add_doctor_comment(issue.task.id, "Moved to Development with Planned tag", issue)
        Report: "  ✓ Moved to Development + added Planned tag"
        FIXED++

      CASE "move_to_deploy":
        # Remove all workflow tags first
        workflow_tags = get_all_workflow_tags()
        FOR tag_name IN workflow_tags:
          IF hasTag(issue.task, tag_name) AND TAG_CACHE[tag_name]:
            mcp__joan__remove_tag_from_task(PROJECT_ID, issue.task.id, TAG_CACHE[tag_name])
        mcp__joan__update_task(issue.task.id, column_id=COLUMN_CACHE["Deploy"])
        add_doctor_comment(issue.task.id, "PR already merged - moved to Deploy", issue)
        Report: "  ✓ Moved to Deploy + cleaned workflow tags"
        FIXED++

      CASE "flag_for_architect":
        Report: "  ⚠ Flagged for Architect attention (will be picked up next dispatch)"
        add_doctor_comment(issue.task.id, "Doctor flagged: needs architect finalization", issue)
        FIXED++

      CASE "flag_for_ops":
        Report: "  ⚠ Flagged for Ops attention (will be picked up next dispatch)"
        add_doctor_comment(issue.task.id, "Doctor flagged: needs ops merge", issue)
        FIXED++

      CASE "add_tag_or_move":
        # Interactive decision - check task description for plan
        IF task_has_plan(issue.task):
          mcp__joan__add_tag_to_task(PROJECT_ID, issue.task.id, TAG_CACHE["Planned"])
          add_doctor_comment(issue.task.id, "Added Planned tag (plan exists in description)", issue)
          Report: "  ✓ Added Planned tag (found plan in description)"
        ELSE:
          mcp__joan__update_task(issue.task.id, column_id=COLUMN_CACHE["Analyse"])
          mcp__joan__add_tag_to_task(PROJECT_ID, issue.task.id, TAG_CACHE["Ready"])
          add_doctor_comment(issue.task.id, "Moved to Analyse with Ready tag (no plan found)", issue)
          Report: "  ✓ Moved to Analyse + added Ready tag"
        FIXED++

  CATCH error:
    Report: "  ✗ Failed to fix: {error}"
    FAILED++

Report: ""
Report: "═══════════════════════════════════════════════════════════════"
Report: "SUMMARY"
Report: "═══════════════════════════════════════════════════════════════"
Report: "Fixed: {FIXED}"
Report: "Failed: {FAILED}"
Report: "Warnings (manual review needed): {WARNINGS.length}"

IF FIXED > 0:
  Report: ""
  Report: "✓ Pipeline should now be unblocked"
  Report: "Run /agents:dispatch to resume workflow"

# === Write Doctor Metrics ===
# Log metrics to track Doctor invocations over time
METRICS_FILE = "{PROJECT_DIR}/.claude/logs/agent-metrics.jsonl"

metric_entry = {
  "timestamp": NOW in ISO format,
  "event": "doctor_invocation",
  "project": PROJECT_NAME,
  "trigger": "manual",  # Invoked by human via /agents:doctor
  "mode": DRY_RUN ? "dry-run" : "fix",
  "issues_found": ISSUES.length,
  "fixes_applied": FIXED,
  "fixes_failed": FAILED,
  "warnings": WARNINGS.length,
  "issues": ISSUES.map(i => ({
    type: i.type,
    severity: i.severity,
    task_title: i.task.title,
    task_id: i.task.id,
    workflow_step: determine_workflow_step(i.task),
    fix_action: i.fix.action
  })),
  "fixes": ISSUES.filter(i => i.fixed).map(i => ({
    task_title: i.task.title,
    fix_action: i.fix.action,
    workflow_step: determine_workflow_step(i.task)
  }))
}

Run bash command:
  mkdir -p "$(dirname {METRICS_FILE})"
  echo '{JSON.stringify(metric_entry)}' >> {METRICS_FILE}

Report: ""
Report: "Metrics logged to: {METRICS_FILE}"
```

### Helper Functions

```
determine_workflow_step(task):
  # Determine which workflow step the task was in when Doctor found the issue
  IF inColumn(task, "To Do"):
    RETURN "To Do"
  ELIF inColumn(task, "Analyse"):
    IF hasTag(task, "Ready"):
      RETURN "Analyse (Ready)"
    ELIF hasTag(task, "Plan-Pending-Approval"):
      RETURN "Analyse (Planning)"
    ELIF hasTag(task, "Plan-Approved"):
      RETURN "Analyse (Plan Approved)"
    RETURN "Analyse"
  ELIF inColumn(task, "Development"):
    IF hasTag(task, "Planned"):
      RETURN "Development (Planned)"
    ELIF isClaimedByAnyDev(task):
      RETURN "Development (In Progress)"
    ELIF hasTag(task, "Rework-Requested"):
      RETURN "Development (Rework)"
    RETURN "Development"
  ELIF inColumn(task, "Review"):
    IF hasTag(task, "Review-Approved"):
      RETURN "Review (Approved)"
    ELIF hasTag(task, "Rework-Requested"):
      RETURN "Review (Rejected)"
    RETURN "Review"
  ELIF inColumn(task, "Deploy"):
    RETURN "Deploy"
  ELIF inColumn(task, "Done"):
    RETURN "Done"
  RETURN "Unknown"

add_doctor_comment(task_id, summary, issue):
  mcp__joan__create_task_comment(task_id,
    "ALS/1
    actor: doctor
    intent: recovery
    action: {issue.fix.action}
    tags.add: [{tags added if any}]
    tags.remove: [{tags removed if any}]
    summary: {summary}
    details:
    - issue_type: {issue.type}
    - severity: {issue.severity}
    - original_state: {issue.description}
    - fix_applied: {issue.fix.reason}")

get_workflow_tags(task):
  WORKFLOW_TAGS = ["Review-Approved", "Ops-Ready", "Plan-Approved", "Planned",
                   "Plan-Pending-Approval", "Ready", "Rework-Requested",
                   "Dev-Complete", "Design-Complete", "Test-Complete",
                   "Review-In-Progress", "Rework-Complete", "Claimed-Dev-1",
                   "Clarification-Answered", "Plan-Rejected", "Invoke-Architect",
                   "Architect-Assist-Complete", "Merge-Conflict", "Implementation-Failed",
                   "Branch-Setup-Failed", "Needs-Clarification"]

  found = []
  FOR tag IN task.tags:
    IF tag.name IN WORKFLOW_TAGS:
      found.push(tag.name)
  RETURN found

task_has_plan(task):
  # Check if task description contains implementation plan markers
  description = task.description OR ""
  RETURN "## Implementation Plan" IN description OR
         "### Sub-Tasks" IN description OR
         "### Development" IN description OR
         "- [ ] DEV-" IN description

check_pr_status(pr_number):
  # Use gh CLI to check PR status
  result = Bash: gh pr view {pr_number} --json state,merged --jq '.state + " " + (.merged | tostring)'
  # Returns "MERGED true", "OPEN false", "CLOSED false"
  IF "MERGED true" IN result:
    RETURN "merged"
  ELIF "CLOSED" IN result:
    RETURN "closed"
  ELSE:
    RETURN "open"

extract_pr_number_from_description(description):
  # Look for PR references like "PR #3" or "pull/3"
  match = regex_search(description, /PR #(\d+)|pull\/(\d+)|#(\d+)/)
  IF match:
    RETURN match group
  RETURN null
```

## Examples

```bash
# Diagnose all tasks in current project
/agents:doctor

# Diagnose specific task
/agents:doctor --task=851f92ae-d3f2-4c2d-b0da-b59f706a28c3

# Dry run - see issues without fixing
/agents:doctor --dry-run

# Verbose output with detailed diagnostics
/agents:doctor --verbose

# Target specific project
/agents:doctor --project=yolo-test
```

## Constraints

- NEVER delete tasks or remove non-workflow tags
- ALWAYS add ALS comment documenting changes
- Prefer minimal fixes (change as little as needed)
- When uncertain, flag for manual review rather than auto-fix
- Do not modify task descriptions (only tags, comments, columns)
