#!/bin/bash
# Task Recovery Script for BuffRamen Web Project
# Fixes the broken state caused by incorrect backlog onboarding

set -e

PROJECT_ID="f2f5340a-42c8-4ca1-b327-d465dee21b8e"
PROJECT_NAME="BuffRamen Web"

echo "═══════════════════════════════════════════════════════════════"
echo "  Task Recovery Script"
echo "  Project: $PROJECT_NAME"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counter
FIXED=0
FAILED=0

fix_task() {
  local TASK_ID=$1
  local TASK_NUM=$2
  local TITLE=$3
  local ACTION=$4
  shift 4
  local OPERATIONS=("$@")

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Task #$TASK_NUM: $TITLE"
  echo "Action: $ACTION"
  echo ""

  for OP in "${OPERATIONS[@]}"; do
    echo "  → $OP"
    if eval "$OP"; then
      echo -e "    ${GREEN}✓${NC}"
    else
      echo -e "    ${RED}✗ Failed${NC}"
      ((FAILED++))
      return 1
    fi
  done

  ((FIXED++))
  echo ""
}

echo "Step 1: Remove incorrect Review-Approved + Ops-Ready tags"
echo "───────────────────────────────────────────────────────────────"
echo ""

# Tasks #85, #84, #83, #82, #81, #80, #75, #67, #65, #64
# These were incorrectly tagged as ready for Ops merge
# They should be moved to Development with Planned tag instead

TASKS_TO_FIX=(
  "b45ae00f-c899-4a1f-8118-32e88e005c3a:85:Add AI-powered exercise suggestion feature"
  "e6ed2086-4235-4fc9-9e2a-a36797b90017:84:Implement negative weight volume calculation"
  "2e46f9af-ecf0-4cbd-bb44-5d21d56629c9:83:Replace info icon with video icon"
  "f84c87bb-2112-4c98-acda-c9d08812d05c:82:Fix workout sharing exercise sequence"
  "740d89d4-c654-4657-b56e-edd1c75235eb:81:Fix ad-hoc workout completion messaging"
  "3834cea3-afc2-447b-9430-85d554884710:80:Clear weight input during calibration"
  "535123ac-34f6-493b-bc44-f08e22b755b5:75:Fix scrolling in exercise search modal"
  "13fde474-e351-4e80-a915-3b8c34246fff:67:Build goal progress visualization"
  "db6d62e1-0455-4bbb-a6b5-680099db0540:65:Implement goal switching"
  "1f7f90d8-330c-4e2a-8528-19017649ab41:64:Create GoalDisplay component"
)

REVIEW_APPROVED_TAG="a111daee-56da-40cd-93a3-a8fdb3e4203c"
OPS_READY_TAG="b8c0a56a-2fdc-4df9-8481-a2a0a3d3fd3f"
PLANNED_TAG="81dde4ea-39be-4930-b8b0-5d0456bbfe3c"
DEVELOPMENT_COLUMN="a19e07cc-520d-492a-bc93-3b1b8c6d5746"

echo "Using Claude CLI to execute Joan MCP operations..."
echo ""

for TASK_INFO in "${TASKS_TO_FIX[@]}"; do
  IFS=':' read -r TASK_ID TASK_NUM TITLE <<< "$TASK_INFO"

  OPERATIONS=(
    "claude -t 'Remove Review-Approved tag from task $TASK_ID' mcp__joan__remove_tag_from_task '{\"project_id\":\"$PROJECT_ID\",\"task_id\":\"$TASK_ID\",\"tag_id\":\"$REVIEW_APPROVED_TAG\"}'"
    "claude -t 'Remove Ops-Ready tag from task $TASK_ID' mcp__joan__remove_tag_from_task '{\"project_id\":\"$PROJECT_ID\",\"task_id\":\"$TASK_ID\",\"tag_id\":\"$OPS_READY_TAG\"}'"
    "claude -t 'Add Planned tag to task $TASK_ID' mcp__joan__add_tag_to_task '{\"project_id\":\"$PROJECT_ID\",\"task_id\":\"$TASK_ID\",\"tag_id\":\"$PLANNED_TAG\"}'"
    "claude -t 'Move task $TASK_ID to Development' mcp__joan__update_task '{\"task_id\":\"$TASK_ID\",\"column_id\":\"$DEVELOPMENT_COLUMN\"}'"
  )

  fix_task "$TASK_ID" "$TASK_NUM" "$TITLE" "Remove incorrect tags, add Planned, move to Development" "${OPERATIONS[@]}"
done

echo ""
echo "Step 2: Fix misplaced tasks with completion tags"
echo "───────────────────────────────────────────────────────────────"
echo ""

# Tasks #70, #74 have completion tags but are in Deploy instead of Review
# Move them to Review so Reviewer can process them

MISPLACED_TASKS=(
  "ef21d8d8-d691-48c9-93bc-78db24d0513d:70:Add re-calibrate option to exercise 3-dot menu"
  "e369f776-e362-4c44-8a53-de43ab4321df:74:Fix double-tap rep confirmation"
)

REVIEW_COLUMN="bd96db3b-9050-4980-a47b-27eb8d0f33d3"

for TASK_INFO in "${MISPLACED_TASKS[@]}"; do
  IFS=':' read -r TASK_ID TASK_NUM TITLE <<< "$TASK_INFO"

  OPERATIONS=(
    "claude -t 'Move task $TASK_ID to Review column' mcp__joan__update_task '{\"task_id\":\"$TASK_ID\",\"column_id\":\"$REVIEW_COLUMN\"}'"
    "claude -t 'Add audit comment to task $TASK_ID' mcp__joan__create_task_comment '{\"task_id\":\"$TASK_ID\",\"content\":\"ALS/1\\nactor: coordinator\\nintent: recovery\\naction: column-correction\\ntags.add: []\\ntags.remove: []\\nsummary: Moved from Deploy to Review for proper code review.\\ndetails:\\n- reason: Task has completion tags but was in Deploy, bypassing Reviewer\"}'"
  )

  fix_task "$TASK_ID" "$TASK_NUM" "$TITLE" "Move from Deploy to Review" "${OPERATIONS[@]}"
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Recovery Complete"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo -e "${GREEN}Fixed: $FIXED tasks${NC}"
if [ $FAILED -gt 0 ]; then
  echo -e "${RED}Failed: $FAILED operations${NC}"
fi
echo ""
echo "Next steps:"
echo "1. Verify task placement in Joan UI"
echo "2. Run /agents:dispatch --loop to process corrected tasks"
echo "3. Monitor coordinator queue building"
echo ""
