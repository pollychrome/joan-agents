# Revised Architecture: Worktree-Based Parallelism

This document describes the updated architecture using git worktrees for true parallel feature development.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              JOAN KANBAN BOARD                              │
├──────────┬──────────┬─────────────────────────────────┬──────────┬─────────┤
│  To Do   │ Analyse  │          Development            │  Review  │ Deploy  │
├──────────┼──────────┼─────────────────────────────────┼──────────┼─────────┤
│          │          │                                 │          │         │
│    ↓     │    ↓     │    ↓       ↓       ↓       ↓   │    ↓     │    ↓    │
│   BA     │ Architect│   Dev     Dev     Dev     Dev  │ Reviewer │   PM    │
│  Agent   │  Agent   │    #1      #2      #3      #4  │  Agent   │  Agent  │
│          │          │    │       │       │       │   │          │         │
│          │          │    ▼       ▼       ▼       ▼   │          │         │
│          │          │ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐│          │         │
│          │          │ │WT-1 │ │WT-2 │ │WT-3 │ │WT-4 ││          │         │
│          │          │ │auth │ │dash │ │api  │ │ui   ││          │         │
│          │          │ └─────┘ └─────┘ └─────┘ └─────┘│          │         │
└──────────┴──────────┴─────────────────────────────────┴──────────┴─────────┘

WT = Git Worktree (isolated working directory)
```

## Key Changes from Original Design

| Aspect | Original | Revised |
|--------|----------|---------|
| Development agents | 3 (Dev, Design, Test) | N Devs (configurable) |
| Parallelism | Time-sliced within one repo | True parallel via worktrees |
| Task assignment | Agents pick tasks by type | Devs claim entire tasks |
| Working directory | Single shared repo | One worktree per active task |
| Throughput | 1 feature at a time | N features simultaneously |

## Agent Roles (Revised)

### Unchanged Agents

| Agent | Count | Role |
|-------|-------|------|
| Business Analyst | 1 | Evaluates requirements, asks questions |
| Architect | 1 | Creates implementation plans |
| Project Manager | 1 | Merges PRs, tracks deployments |

### New: Dev Agents + Reviewer

| Agent | Count | Role |
|-------|-------|------|
| Dev | N (configurable) | Claims a task, creates worktree, does ALL implementation (dev + design + test), creates PR, cleans up |
| Reviewer | 1 | Reviews completed PRs, merges develop into feature, approves or requests rework |

## How It Works

### 1. Task Enters Development

```
Architect approves plan
        │
        ▼
Task moves to Development (tagged "Planned")
        │
        ▼
Task enters the "Available Work" pool
```

### 2. Dev Claims Task

```
Dev #1 polls Joan ──▶ Finds unclaimed "Planned" task
        │
        ▼
Dev tags task "Claimed-Dev-1" (prevents others from claiming)
        │
        ▼
Dev extracts branch name from plan: feature/user-auth
```

### 3. Worktree Creation

```
Dev #1 creates worktree:
        │
        ▼
git worktree add ../worktrees/user-auth feature/user-auth
        │
        ▼
Dev changes to: ../worktrees/user-auth/
        │
        ▼
All file operations happen in this isolated directory
```

### 4. Implementation (Sequential in Worktree)

```
┌─────────────────────────────────────────────┐
│         Worktree: ../worktrees/user-auth    │
│                                             │
│  1. Execute DES-* tasks (design first)      │
│         │                                   │
│         ▼                                   │
│  2. Execute DEV-* tasks (implementation)    │
│         │                                   │
│         ▼                                   │
│  3. Execute TEST-* tasks (verification)     │
│         │                                   │
│         ▼                                   │
│  4. Create Pull Request                     │
│                                             │
└─────────────────────────────────────────────┘
```

### 5. Cleanup & Next Task

```
Dev #1 finishes task
        │
        ├──▶ Moves task to Review column
        │
        ├──▶ Removes worktree: git worktree remove ../worktrees/user-auth
        │
        └──▶ Polls for next available task
```

## Parallel Execution Example

With 4 devs and 6 planned tasks:

```
Time ─────────────────────────────────────────────────────────────▶

Dev 1: [═══ Task A ═══][═══ Task E ═══]
Dev 2: [═══ Task B ═══][═══ Task F ═══]
Dev 3: [═══ Task C ═════════]
Dev 4: [═══ Task D ═══]

Worktrees:
  ../worktrees/task-a/  (created → used → removed)
  ../worktrees/task-b/  (created → used → removed)
  ../worktrees/task-c/  (created → used → removed)
  ../worktrees/task-d/  (created → used → removed)
  ../worktrees/task-e/  (created → used → removed)
  ../worktrees/task-f/  (created → used → removed)
```

4 features developed truly in parallel!

## Directory Structure

```
your-project/                    # Main repo (Architect works here)
├── .git/
├── .claude/
├── src/
└── ...

../worktrees/                    # Parallel workspaces
├── user-auth/                   # Dev 1's current task
│   ├── .git → ../../your-project/.git
│   ├── src/
│   └── ...
├── dashboard/                   # Dev 2's current task
│   └── ...
├── api-refactor/                # Dev 3's current task
│   └── ...
└── payment-flow/                # Dev 4's current task
    └── ...
```

All worktrees share the same `.git` directory (via symlink), so:
- Branches are shared
- Commits are visible across worktrees
- Pushing from any worktree updates the remote

## Claim Protocol

To prevent multiple devs from claiming the same task:

```
1. Dev polls Joan for tasks:
   - Column: Development
   - Tag: Planned
   - NOT tagged: Claimed-Dev-*

2. Dev finds candidate task

3. Dev IMMEDIATELY tags: "Claimed-Dev-{N}"
   (This is atomic - first writer wins)

4. Dev verifies claim stuck
   - If yes: proceed
   - If no (race condition): skip, poll again

5. When done, Dev removes claim tag and moves task
```

## Resource Usage

| Configuration | Terminal Windows | Parallel Features |
|---------------|------------------|-------------------|
| Minimal | 4 | 1 feature |
| Standard | 6 | 3 features |
| Maximum | 8 | 5 features |

Breakdown:
- BA Agent: 1
- Architect Agent: 1
- PM Agent: 1
- Dev Agents: 1-5 (your choice)
- Reviewer Agent: 1

## Benefits

1. **True Parallelism**: N features developed simultaneously
2. **Isolation**: Each task has its own working directory
3. **No Conflicts**: Devs never step on each other's files
4. **Efficient**: Single dev handles entire task lifecycle
5. **Scalable**: Add more devs for more parallelism
6. **Clean**: Worktrees created and destroyed automatically

## Trade-offs

1. **Disk Space**: Each worktree is a full checkout (~50-200MB typical)
2. **Memory**: More devs = more Claude Code instances
3. **Sequential Within Task**: Dev/Design/Test run sequentially per task
4. **Coordination**: Need claim protocol to prevent races
