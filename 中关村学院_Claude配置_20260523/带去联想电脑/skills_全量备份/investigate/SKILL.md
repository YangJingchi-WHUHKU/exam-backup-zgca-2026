---
name: investigate
description: Investigate and document directory architecture. This skill should be used when entering a new project, when the user says 'investigate', '分析架构', '看看这个项目', '了解一下代码', '熟悉项目', 'explore codebase', or when starting work in an undocumented directory.
---

# Investigate — 项目架构分析

## When to Trigger

- Entering a new project or codebase area
- User says "investigate" / "分析架构" / "看看这个项目"
- Starting serious work in a directory without CLAUDE.md
- First time working in a project directory

## Execution Steps

### 1. Investigate Architecture

Analyze the implementation principles and architecture of the code in the target directory and its subdirectories:

- Design patterns being used
- Dependencies and their purposes
- Key abstractions and interfaces
- Naming conventions and code organization
- Entry points and data flow

### 2. Create or Update CLAUDE.md

Capture discovered knowledge in a CLAUDE.md file at the project root. If one already exists, update it with newly discovered information. Include:

- Purpose and responsibility of this module
- Key architectural decisions
- Important implementation details
- Common patterns used throughout the code
- Any gotchas or non-obvious behaviors
- Build/test/lint commands

### 3. Create PROJECT_CONTEXT.md

If it doesn't exist, create with the standard template:

```markdown
# [Project Name] - Project Context
Last Updated: [date]

## Architecture
(filled by investigation above)

## Current Focus
(to be filled)

## Session Handoff
<!-- SESSION_HANDOFF_START -->
(Claude auto-maintains)
<!-- SESSION_HANDOFF_END -->

## Tech Debt
(to be filled)
```

### 4. Report Summary

Output a brief summary of what was found: tech stack, structure, key files, and any concerns.
