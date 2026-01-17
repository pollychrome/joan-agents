---
description: Single-pass BA worker dispatched by coordinator
argument-hint: --task=<task-id> --mode=<evaluate|reevaluate>
allowed-tools: mcp__joan__*, Read, Grep, Glob
---

# BA Worker (Single-Pass)

Process a single task assigned by the coordinator, then exit.

## Arguments

- `--task=<ID>` - Task ID to process (REQUIRED)
- `--mode=<evaluate|reevaluate>` - Processing mode (REQUIRED)
  - `evaluate`: New task from To Do, needs initial evaluation
  - `reevaluate`: Task has Clarification-Answered tag, re-check requirements

## Configuration

Load from `.joan-agents.json`:
```
PROJECT_ID = config.projectId
PROJECT_NAME = config.projectName
```

If config missing, report error and exit.

Parse arguments:
```
TASK_ID = value from --task
MODE = value from --mode
```

If either argument missing, report error and exit.

---

## Step 1: Fetch Task

```
1. Fetch task using get_task(TASK_ID)

2. Validate task is actionable:

   IF MODE == "evaluate":
     - Task should be in "To Do" column
     - Task should NOT have "Ready" tag

   IF MODE == "reevaluate":
     - Task should be in "Analyse" column
     - Task should have "Needs-Clarification" tag
     - Task should have "Clarification-Answered" tag

3. IF validation fails:
   Report: "Task {TASK_ID} not actionable for mode {MODE}"
   EXIT
```

---

## Step 2: Process Task

### Mode: evaluate (new task from To Do)

```
1. Analyze task requirements:
   - Is the description complete and unambiguous?
   - Are acceptance criteria defined?
   - Are there open questions?

2. Move task to "Analyse" column

3. IF requirements INCOMPLETE:
   - Add "Needs-Clarification" tag
   - Comment (ALS breadcrumb):
     "ALS/1
     actor: ba
     intent: request
     action: clarify-request
     tags.add: [Needs-Clarification]
     tags.remove: []
     summary: Clarification needed before planning.
     details:
     - [Specific question]
     - [Another question]
     - After answering, add the Clarification-Answered tag."
   - Report: "Task needs clarification"

4. IF requirements COMPLETE:
   - Add "Ready" tag
   - Comment (ALS breadcrumb):
     "ALS/1
     actor: ba
     intent: response
     action: clarify-verified
     tags.add: [Ready]
     tags.remove: []
     summary: Requirements validated; ready for planning."
   - Report: "Task marked Ready"
```

### Mode: reevaluate (task has answers)

```
1. Fetch task comments using list_task_comments(TASK_ID)

2. Find the last ALS block with action "clarify-request"
   Read any comments that came after (these are the answers)

3. Evaluate if the answers are satisfactory:
   - Do they address all questions?
   - Are there follow-up questions needed?

4. IF answers are SATISFACTORY:
   - Remove "Needs-Clarification" tag
   - Remove "Clarification-Answered" tag
   - Add "Ready" tag
   - Comment (ALS breadcrumb):
     "ALS/1
     actor: ba
     intent: response
     action: clarify-verified
     tags.add: [Ready]
     tags.remove: [Needs-Clarification, Clarification-Answered]
     summary: Clarification received; ready for planning."
   - Report: "Task clarified and marked Ready"

5. IF answers are INCOMPLETE or raise more questions:
   - Keep "Needs-Clarification" tag
   - Remove "Clarification-Answered" tag (so human can re-add after answering)
   - Comment (ALS breadcrumb) with follow-up questions:
     "ALS/1
     actor: ba
     intent: request
     action: clarify-followup
     tags.add: []
     tags.remove: [Clarification-Answered]
     summary: Follow-up clarification required.
     details:
     - [Follow-up question]
     - After answering, add the Clarification-Answered tag again."
   - Report: "Task needs more clarification"
```

---

## Step 3: Exit

```
Report completion summary:
"BA Worker complete:
- Task: {title}
- Mode: {MODE}
- Result: {Ready | Needs-Clarification}"

EXIT
```

---

## Question Guidelines

When requirements are unclear, ask SMART questions:
- **Specific**: Target exact ambiguity
- **Measurable**: Ask for concrete criteria
- **Actionable**: Questions should unblock development
- **Relevant**: Focus on dev/design needs
- **Time-bound**: Ask about deadlines if unclear

## Constraints

- Never modify task descriptions (only comments)
- Never create plans or implementation details
- Always write breadcrumb comments (for audit trail)
- Single task only - process and exit

Begin processing task: $TASK_ID with mode: $MODE
