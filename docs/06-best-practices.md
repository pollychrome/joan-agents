# Best Practices

Recommendations for getting the most out of the Joan Multi-Agent System.

---

## Task Creation

### Write Clear Titles

**Good:**
- "Add user authentication with email/password"
- "Fix: Dashboard crashes on empty data"
- "Refactor: Extract payment logic to service"

**Bad:**
- "Auth stuff"
- "Bug fix"
- "Update code"

### Provide Context in Description

Even if incomplete, give agents a starting point:

```markdown
## Background
Users have requested the ability to export their data.

## Requirements (draft)
- Export user profile data
- Export activity history
- Format: CSV or JSON

## Notes
- Check GDPR compliance requirements
- Similar to the import feature we built last month
```

### Set Accurate Priority

Agents process tasks by priority. Use consistently:

| Priority | When to Use |
|----------|-------------|
| Critical | Production is down |
| High | Blocking other work |
| Medium | Normal feature work |
| Low | Nice to have, can wait |

---

## Working with BA Agent

### Answer Questions Promptly

The faster you answer, the faster development starts.

### Be Specific

**Good answer:**
```markdown
1. Yes, users should be able to export as CSV and JSON
2. Include: name, email, created_at, last_login
3. Exclude: password_hash, internal_id
4. File should be named: export_{user_id}_{timestamp}.csv
```

**Bad answer:**
```markdown
1. yes
2. the usual stuff
3. whatever makes sense
```

### Anticipate Edge Cases

When answering, think about:
- What if the user has no data?
- What if the export is very large?
- What about concurrent exports?
- Error handling?

---

## Working with Architect Agent

### Review Plans Carefully

Plans determine everything that follows. Check:

- [ ] Are all requirements addressed?
- [ ] Are sub-tasks truly atomic?
- [ ] Are dependencies correctly ordered?
- [ ] Is the branch name sensible?
- [ ] Are acceptance criteria testable?

### Request Changes Early

It's easier to revise a plan than to redo implementation:

```markdown
Before approving, please adjust:

1. DEV-2 should be split into two tasks:
   - DEV-2a: Add endpoint
   - DEV-2b: Add validation

2. Add DES task for loading states

3. TEST-2 should include error scenarios

@architect please revise
```

### Approve Explicitly

Use the exact trigger: `@architect`

```markdown
Plan looks good, approved. @architect
```

---

## During Implementation

### Monitor Progress

Check task descriptions for checkbox updates:

```markdown
### Development
- [x] DEV-1 ✅
- [x] DEV-2 ✅
- [ ] DEV-3 (in progress)
```

### Don't Interfere Mid-Task

Let agents complete their work. Avoid:
- Editing task description while agents are working
- Moving tasks between columns
- Adding/removing tags

### Handle Bugs Efficiently

When Tester reports a bug:

1. Review the bug report
2. If valid, wait for Developer to fix
3. If invalid (test was wrong), comment clarification

---

## Code Review

### Review Thoroughly

Even with AI implementation, check:

- [ ] Logic is correct
- [ ] Security considerations
- [ ] Performance implications
- [ ] Code style/conventions
- [ ] Test coverage
- [ ] Documentation

### Provide Actionable Feedback

**Good:**
```markdown
Please address:
1. Line 45: Add null check before accessing user.profile
2. Line 78: This query could be N+1, consider eager loading
3. Missing: Add rate limiting to this endpoint
```

**Bad:**
```markdown
Looks wrong, please fix
```

### Use Review Column Appropriately

- Move to Deploy = Approved
- Move back to Development = Changes needed
- Comment without moving = Discussion (agents won't act)

---

## Deployment

### Batch Related Features

The deploy status shows what's ready. Consider:
- Do these features go together?
- Any migration order dependencies?
- Roll back plan if issues arise?

### Deploy at Appropriate Times

- Avoid Friday afternoon deployments
- Consider user timezone for impactful changes
- Have rollback plan ready

### Verify After Deploy

After merging to main:
1. Monitor CI/CD pipeline
2. Check production for errors
3. Verify feature works as expected
4. PM will move to Done automatically

---

## System Maintenance

### Regular Log Cleanup

```bash
# Weekly: Remove logs older than 7 days
find joan-agents/logs -name "*.log" -mtime +7 -delete
```

### Periodic Agent Restart

Long-running sessions can accumulate issues:

```bash
# Daily restart (add to crontab)
0 6 * * * /path/to/joan-agents/stop-agents.sh && sleep 30 && /path/to/joan-agents/start-agents-iterm.sh my-project
```

### Keep Claude Code Updated

```bash
# Check for updates
claude update
```

---

## Performance Optimization

### Right-Size Concurrency

If agents are slow or system is overloaded:

1. Reduce max concurrent tasks (default: 5)
2. Reduce number of active agents
3. Increase poll interval

### Use Appropriate Model

For cost/speed optimization, edit agent definitions:

```yaml
# Faster, cheaper (for simple tasks)
model: claude-sonnet-4-5-20250929

# Smarter (for complex planning)
model: claude-opus-4-5-20250929
```

### Optimize Task Granularity

**Too large:**
- "Build entire user management system"
- Results in huge plans, slow progress

**Too small:**
- "Add semicolon to line 45"
- Creates overhead, many tiny tasks

**Just right:**
- "Add user profile page with edit capability"
- Clear scope, manageable plan

---

## Team Workflows

### Multiple People, One Project

When multiple humans work with the system:

1. **Communicate** who is reviewing what
2. **Don't both** approve the same plan
3. **Coordinate** production deploys

### Multiple Projects

Run separate agent swarms per project:

```bash
# Terminal window 1: Project A
./start-agents-iterm.sh project-a

# Terminal window 2: Project B
./start-agents-iterm.sh project-b
```

### Handoffs

When going offline:
1. Note any pending reviews in team chat
2. Ensure no tasks are stuck waiting for your input
3. Others can answer BA questions / approve plans

---

## Avoiding Common Pitfalls

### Don't Edit While Agents Work

Agents poll and update every 30 seconds. Manual edits during this can cause:
- Lost updates
- Conflicting states
- Confused agents

### Don't Skip the Workflow

Resist the urge to:
- Create tasks directly in Development
- Move tasks without proper tags
- Manually edit sub-task checkboxes

The workflow exists to maintain consistency.

### Don't Ignore Agent Comments

Agent comments contain:
- Important questions needing answers
- Bug reports needing attention
- Status updates tracking progress

Check them regularly.

### Don't Over-Specify

Let agents do their job:
- BA will identify missing requirements
- Architect will break down into sub-tasks
- Developer will choose implementation details

You provide what, agents figure out how.

---

## Measuring Success

### Track Cycle Time

Measure time from To Do to Done:
- < 24 hours: Excellent
- 1-3 days: Good
- 3-7 days: Needs improvement
- > 7 days: Investigate bottlenecks

### Monitor Quality

Track:
- Bugs found after deploy
- Code review rejection rate
- Test coverage trends

### Identify Bottlenecks

Common bottlenecks:
1. **Human response time** - Answer questions faster
2. **Complex plans** - Break into smaller features
3. **Bug loops** - Improve initial requirements
4. **CI failures** - Fix infrastructure issues

### Iterate on Prompts

If agents consistently produce subpar results:
1. Review their definition files
2. Add more specific guidance
3. Include examples of good output
4. Test and refine
