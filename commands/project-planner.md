---
description: Create project tasks from a plan file or interactively
argument-hint: "[--file=path/to/plan.md] [--interactive] [--preview]"
allowed-tools: mcp__joan__*, Read, AskUserQuestion, Glob
---

# Project Planner

Create tasks and milestones from a plan file or through guided interactive questions.

## Parse Arguments

Check the user's input for flags:
- `--file=<path>` → File Import Mode (Mode A)
- `--interactive` → Interactive Mode (Mode B)
- `--preview` → Show what would be created without creating anything
- No flags → Default to Interactive Mode

## Step 1: Load Configuration

Read `.joan-agents.json` to get the project ID:

```
Read .joan-agents.json
```

If the file doesn't exist, inform the user:
```
Project not configured. Run /agents:init first to set up your project.
```

Extract `projectId` and `projectName` from the config.

## Step 2: Fetch Project Context

Get the "To Do" column ID and existing tags:

```
mcp__joan__list_columns(project_id)
mcp__joan__list_project_tags(project_id)
```

Find the "To Do" column (case-insensitive match). Store:
- `TODO_COLUMN_ID` - where new tasks will be placed
- `EXISTING_TAGS` - for validation

---

# MODE A: File Import

If `--file=<path>` was provided:

## A1: Read and Parse Plan File

```
Read <path>
```

If file doesn't exist, inform the user and suggest using `--interactive` instead.

### Supported Formats

The parser should detect and handle three formats:

**Format 1: Milestone-hierarchy (recommended)**
```markdown
## Milestone: MVP Launch
Target: 2024-03-15

### Task: User Authentication
Priority: high
Description: Implement login flow with OAuth2

- User can sign in with email/password
- OAuth support for Google and GitHub
- Session management with JWT

### Task: Dashboard UI
Priority: medium
Description: Main dashboard after login

- Shows user profile
- Quick stats panel
```

**Format 2: Simple task list (no milestones)**
```markdown
## User Authentication
Priority: high

- Implement login flow
- Add password reset
- Support OAuth providers

## Dashboard UI
Priority: medium

- Main layout component
- Stats widgets
```

**Format 3: Bullet list (quick import)**
```markdown
- [ ] User Authentication (high)
- [ ] Dashboard UI (medium)
- [ ] API Integration (low)
- [ ] Documentation
```

### Parsing Rules

1. **Milestone Detection:**
   - Lines starting with `## Milestone:` or `# Milestone:`
   - Extract name after the colon
   - Look for `Target:` line for due date (optional)

2. **Task Detection:**
   - Lines starting with `### Task:` or `## ` (without Milestone prefix)
   - Lines starting with `- [ ]` or `- [x]`
   - Extract title from the line

3. **Priority Detection:**
   - Lines starting with `Priority:` following a task header
   - Parenthetical suffix: `(high)`, `(medium)`, `(low)`
   - Default to `none` if not specified

4. **Description Detection:**
   - Lines starting with `Description:` following a task header
   - Bullet points following a task header become acceptance criteria
   - Combine into description with format:
     ```
     {Description line if present}

     Acceptance Criteria:
     - {bullet 1}
     - {bullet 2}
     ```

5. **Milestone Assignment:**
   - Tasks under a milestone header belong to that milestone
   - Tasks before any milestone header have no milestone

## A2: Gap Detection

After parsing, identify tasks that need clarification:

**Gaps to detect:**

| Gap Type | Detection Rule | Question |
|----------|----------------|----------|
| Missing description | Description < 10 chars AND no bullets | "What should '{title}' accomplish?" |
| Vague title | Contains: "fix", "update", "misc", "stuff", "todo", "thing" | "Can you be more specific about '{title}'?" |
| No acceptance criteria | No bullets AND no "should"/"must"/"when" in description | "What are the acceptance criteria for '{title}'?" |
| Large scope, no priority | Title contains "system", "full", "complete" AND priority=none | "What priority for '{title}'?" |

For each gap found, use AskUserQuestion to get clarification:

```
AskUserQuestion: "{question}"
Options:
  - Provide specific input (text field)
  - Skip this task
  - Mark as low priority placeholder
```

Update the parsed task with user's response.

## A3: Preview (if --preview)

If `--preview` flag was provided, display what would be created:

```
═══════════════════════════════════════════════════════════════
  PROJECT PLANNER - Preview Mode
═══════════════════════════════════════════════════════════════

Project: {projectName}
Source: {file path}

MILESTONES TO CREATE ({count}):
──────────────────────────────────────────────────────────────
  1. MVP Launch (target: 2024-03-15)
  2. Beta Release (target: 2024-04-01)

TASKS TO CREATE ({count}):
──────────────────────────────────────────────────────────────
  1. [high] User Authentication
     └─ Milestone: MVP Launch
     └─ 3 acceptance criteria

  2. [medium] Dashboard UI
     └─ Milestone: MVP Launch
     └─ 2 acceptance criteria

  3. [low] Documentation
     └─ No milestone
     └─ 1 acceptance criteria

═══════════════════════════════════════════════════════════════
  Preview complete. Run without --preview to create these items.
═══════════════════════════════════════════════════════════════
```

Exit after preview.

## A4: Confirm Before Creating

If not preview mode, show summary and ask for confirmation:

```
AskUserQuestion: "Ready to create {milestone_count} milestones and {task_count} tasks?"
Options:
  - "Yes, create all"
  - "Preview first"
  - "Cancel"
```

If "Preview first", show A3 output then re-ask.

## A5: Create in Joan

### Create Milestones First

For each milestone:
```
mcp__joan__create_milestone(
  project_id: PROJECT_ID,
  name: milestone.name,
  target_date: milestone.target_date,  // if provided
  status: "upcoming"
)
```

Store the returned `milestone_id` for task linking.

### Create Tasks

For each task:
```
mcp__joan__create_task(
  title: task.title,
  description: task.description,
  priority: task.priority,
  project_id: PROJECT_ID,
  column_id: TODO_COLUMN_ID,
  status: "todo"
)
```

Store the returned `task_id`.

### Link Tasks to Milestones

For tasks with milestone assignments:
```
mcp__joan__link_tasks_to_milestone(
  project_id: PROJECT_ID,
  milestone_id: milestone.id,
  task_ids: [task_ids...]
)
```

## A6: Report Results

```
═══════════════════════════════════════════════════════════════
  PROJECT PLANNER - Complete
═══════════════════════════════════════════════════════════════

Created:
  • {milestone_count} milestones
  • {task_count} tasks in "To Do" column

Tasks are ready for the BA agent to evaluate.
Start agents with: /agents:dispatch --loop

View in Joan: https://joan.ai/projects/{projectId}
═══════════════════════════════════════════════════════════════
```

---

# MODE B: Interactive

If `--interactive` flag was provided (or default):

## B1: Project Overview

```
AskUserQuestion: "What is this project about? (Brief description to understand context)"
Options:
  - Free text input
```

Store response as `PROJECT_CONTEXT` for guiding task creation.

## B2: Milestones Decision

```
AskUserQuestion: "Do you want to organize tasks into milestones?"
Options:
  - "Yes, let me define milestones first"
  - "No, just create standalone tasks"
```

## B3: Collect Milestones (if yes)

If user wants milestones:

```
AskUserQuestion: "Define your milestones. Format: Name | Target Date (optional)
Examples:
  MVP Launch | 2024-03-15
  Beta Release
  Production Ready | 2024-06-01

Enter milestones (one per line, or 'done' when finished):"
Options:
  - Free text input for milestones
  - "Done defining milestones"
```

Parse the input:
- Split by newlines
- Extract name before `|`
- Extract date after `|` if present
- Validate date format (YYYY-MM-DD)

Store as `MILESTONES` array.

## B4: Task Collection Loop

Enter a loop to collect tasks:

```
═══════════════════════════════════════════════════════════════
  Task Entry Mode
═══════════════════════════════════════════════════════════════
  Commands:
    - Type a task title to add it
    - 'list' - Show tasks entered so far
    - 'done' - Finish and create tasks
    - 'cancel' - Exit without creating
═══════════════════════════════════════════════════════════════
```

### For each task:

**Step 1: Title**
```
AskUserQuestion: "Task title (or 'done'/'list'/'cancel'):"
Options:
  - Free text input
  - "done" - Finish entering tasks
  - "list" - Show entered tasks
  - "cancel" - Exit without saving
```

If 'done', go to B5.
If 'list', show current tasks and continue.
If 'cancel', exit.

**Step 2: Description**
```
AskUserQuestion: "What should this task accomplish? Include acceptance criteria."
Options:
  - Free text input
  - "skip" - Add without description
```

**Step 3: Priority**
```
AskUserQuestion: "Priority for '{title}'?"
Options:
  - "High - Critical path, do first"
  - "Medium - Important but not blocking"
  - "Low - Nice to have"
  - "None - No priority set"
```

**Step 4: Milestone (if milestones exist)**
```
AskUserQuestion: "Assign to milestone?"
Options:
  - "{milestone1.name}"
  - "{milestone2.name}"
  - ...
  - "No milestone"
```

Add task to `TASKS` array and loop back for next task.

## B5: Preview and Confirm

Show summary:

```
═══════════════════════════════════════════════════════════════
  Tasks to Create
═══════════════════════════════════════════════════════════════

{If milestones:}
Milestones:
  1. {name} (target: {date or "none"})
  ...

Tasks:
  1. [{priority}] {title}
     └─ Milestone: {milestone or "none"}
  ...

═══════════════════════════════════════════════════════════════
```

```
AskUserQuestion: "Create these items in Joan?"
Options:
  - "Yes, create all"
  - "Add more tasks"
  - "Cancel"
```

If "Add more tasks", go back to B4.

## B6: Create in Joan

Same as A5 - create milestones first, then tasks, then link.

## B7: Report Results

Same as A6.

---

# Error Handling

**File not found:**
```
Could not read file at '{path}'.

Check that:
  • The path is correct
  • The file exists
  • You have read permissions

Try: /agents:project-planner --interactive
```

**No project configured:**
```
No Joan project configured for this repository.

Run /agents:init first to:
  1. Select your Joan project
  2. Set up Kanban columns
  3. Configure workflow tags

Then run /agents:project-planner again.
```

**Joan API errors:**
```
Failed to create {item type}: {error message}

Successfully created before error:
  • {N} milestones
  • {N} tasks

You may need to manually clean up partial creations in Joan.
```

---

# Task Quality Guidelines

Tasks created by project-planner should be ready for the BA agent to evaluate.

**Good tasks have:**
- Clear, specific title (verb + noun: "Add user authentication", "Fix login timeout")
- Description explaining the goal
- Acceptance criteria as bullet points
- Appropriate priority set

**The BA agent will:**
- Validate requirements completeness
- Ask clarifying questions if needed
- Add "Ready" tag when task is clear
- Move to Analyse column

**Flow after project-planner:**
```
project-planner → "To Do" column → BA evaluates → "Ready" tag → Architect plans
```

---

# Examples

**Import from file:**
```
/agents:project-planner --file=project-plan.md
```

**Preview before creating:**
```
/agents:project-planner --file=plan.md --preview
```

**Interactive session:**
```
/agents:project-planner --interactive
```

**Default (interactive):**
```
/agents:project-planner
```
