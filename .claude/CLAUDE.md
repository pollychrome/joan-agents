# Joan Multi-Agent System (v2 - Worktree Edition)

This system uses git worktrees for true parallel feature development.

## Agent Communication Protocol

All agents communicate through Joan MCP and task comments/tags.

### Tag Conventions

| Tag | Meaning | Set By |
|-----|---------|--------|
| `Needs-Clarification` | Task has unanswered questions | BA |
| `Ready` | Requirements complete | BA |
| `Plan-Pending-Approval` | Plan created, awaiting @architect | Architect |
| `Planned` | Plan approved, available for workers | Architect |
| `Claimed-Worker-N` | Worker N is implementing this task | Worker |
| `Dev-Complete` | All DEV sub-tasks done | Worker |
| `Design-Complete` | All DES sub-tasks done | Worker |
| `Test-Complete` | All TEST sub-tasks pass | Worker |
| `Implementation-Failed` | Worker couldn't complete | Worker |

### Claim Protocol

Workers use atomic tagging to claim tasks:
1. Find task with `Planned` tag and NO `Claimed-Worker-*` tag
2. Immediately add `Claimed-Worker-{N}` tag
3. Verify claim succeeded before proceeding
4. Remove claim tag when done (success or failure)

### Comment Triggers

| Mention | Effect |
|---------|--------|
| `@architect` | Approves plan |
| `@business-analyst` | Escalates requirement questions |

## Worktree Management

Workers create worktrees in `../worktrees/`:

```bash
# Create
git worktree add ../worktrees/{task-id} feature/{branch}

# Work happens here
cd ../worktrees/{task-id}

# Cleanup
git worktree remove ../worktrees/{task-id} --force
git worktree prune
```

All worktrees share the same `.git` directory.

## Sub-Task Format

Plans define sub-tasks executed in order:

```markdown
### Design (first)
- [ ] DES-1: Description

### Development (second)  
- [ ] DEV-1: Description
- [ ] DEV-2: Description (depends: DEV-1)

### Testing (last)
- [ ] TEST-1: Description (depends: DEV-1, DES-1)
```

Workers check off tasks as completed:
- [x] DEV-1: Description ✅

## Branch Naming

Feature branches: `feature/{task-title-kebab-case}`

This name is specified in the Architect's plan and used by Workers to create worktrees.
