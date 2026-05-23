---
name: planning-with-files
description: File-based planning for complex tasks. Creates task_plan.md, findings.md, and progress.md. This skill should be used when the user has complex multi-step tasks, says '规划', '计划一下', 'plan this', '大任务', '复杂任务', or when task requires more than 5 tool calls or touches more than 5 files.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - WebFetch
  - WebSearch
metadata:
  version: "1.1.0"
  user-invocable: true
---

# Planning with Files

Work like Manus: Use persistent markdown files as your "working memory on disk."

## The Core Pattern

```
Context Window = RAM (volatile, limited)
Filesystem = Disk (persistent, unlimited)

→ Anything important gets written to disk.
```

## Quick Start

Before ANY complex task:

1. **Create planning files immediately** — Use either the simple names or a task-prefixed variant:
   - `task_plan.md` or `<task>_task_plan.md`
   - `findings.md` or `<task>_findings.md`
   - `progress.md` or `<task>_progress.md`
2. **Use task-prefixed names in shared roots** — especially in `~/`, large workspaces, or multi-project coordination tasks
4. **Fill Acceptance Criteria** — Define done *before* writing code
5. **Re-read plan before decisions** — Refreshes goals in attention window
6. **Update after each phase** — Mark complete, log errors

When the task spans multiple projects or skill-placement decisions, prefixed files are strongly preferred.

## File Purposes

| File | Purpose | When to Update |
|------|---------|----------------|
| `task_plan.md` | Phases, progress, decisions | After each phase |
| `findings.md` | Research, discoveries | After ANY discovery |
| `progress.md` | Session log, test results | Throughout session |

Task-prefixed variants have the same purpose; they just prevent collisions.

## Critical Rules

### 1. Create Plan First
Never start a complex task without `task_plan.md`. Non-negotiable.

If the workspace root is noisy or shared, a task-prefixed equivalent is acceptable and preferred.

### 2. The 2-Action Rule
> "After every 2 view/browser/search operations, IMMEDIATELY save key findings to text files."

### 3. Read Before Decide
Before major decisions, read the plan file.

### 4. Update After Act
After completing any phase: mark status, log errors, note files changed.

### 5. Log ALL Errors
Every error goes in the plan file. Builds knowledge, prevents repetition.

### 6. Never Repeat Failures
```
if action_failed:
    next_action != same_action
```

## The 3-Strike Error Protocol

```
ATTEMPT 1: Diagnose & Fix
  → Read error carefully, identify root cause, apply targeted fix

ATTEMPT 2: Alternative Approach
  → Same error? Different method, different tool

ATTEMPT 3: Broader Rethink
  → Question assumptions, search for solutions, consider updating plan

AFTER 3 FAILURES: Escalate to User
  → Explain what you tried, share specific error, ask for guidance
```

## The 5-Question Reboot Test

| Question | Answer Source |
|----------|---------------|
| Where am I? | Current phase in task_plan.md |
| Where am I going? | Remaining phases |
| What's the goal? | Goal statement in plan |
| What have I learned? | findings.md |
| What have I done? | progress.md |

## Special Case: Skill / Multi-Project Tasks

If the task involves skills, project pack placement, or cross-project coordination, always add these notes to the plan:

1. **Placement decision**
   - active library
   - cold vault
   - project `.claude/skills`
   - global core

2. **Affected projects**
   - which project roots are touched
   - whether each needs `project_skill_manager.py sync-all` or `init`

3. **Decision log**
   - what was installed
   - what was rejected
   - why

4. **Verification**
   - which paths were created or linked
   - which template/project mappings changed

For these tasks, the findings file should include a short matrix:

```markdown
| Item | Destination | Reason | Verified |
|------|-------------|--------|----------|
| skill-x | vault | external, not yet trusted | yes/no |
| skill-y | project pack | project-only workflow | yes/no |
```

## Special Case: Research Tasks

For research-heavy work:

1. Record claim-level goals in the plan, not just file edits.
2. Put every important literature / benchmark / method comparison into `findings.md`.
3. Before changing narrative or experimental claims, re-read both the plan and findings files.
4. Distinguish:
   - evidence gathered
   - inference made
   - action decided

## When to Use This Pattern

**Use for**: Multi-step tasks (3+ steps), research, building projects, many tool calls, cross-project coordination, skill-placement work
**Skip for**: Simple questions, single-file edits, quick lookups

## Anti-Patterns

| Don't | Do Instead |
|-------|------------|
| State goals once and forget | Re-read plan before decisions |
| Hide errors and retry silently | Log errors to plan file |
| Start executing immediately | Create plan file FIRST |
| Repeat failed actions | Track attempts, mutate approach |

## Good Defaults In This Local Setup

- For project work: keep planning files in the project root unless the project already has a better planning location.
- For home-directory coordination work: prefer task-prefixed planning files.
- For skill-management work: record whether the target belongs in:
  - `/Users/yangjingchi/.config/agents/skill-vault/`
  - `<project>/.claude/skills/`
  - `/Users/yangjingchi/.config/agents/skills/`
  - `/Users/yangjingchi/.config/agents/skillsets/global-core/`

## Minimal Template

```markdown
# <Task Name>

## Goal
- ...

## Acceptance Criteria
- ...

## Phases
- [ ] Phase 1
- [ ] Phase 2

## Constraints
- ...

## Decisions
- ...
```
