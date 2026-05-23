# Local Claude-Codex Memory Routing

This machine uses `/Users/yangjingchi/.claude` as the human-readable shared memory layer. Codex resume history is still under `/Users/yangjingchi/.codex`, but cross-session project continuity should be reconstructed from project docs and `.claude/memory`.

## Read Order

1. Nearest project `CLAUDE.md`
2. Nearest project `PROJECT_CONTEXT.md`
3. Nearest project `memory/MEMORY.md`
4. `/Users/yangjingchi/.claude/memory/active-tasks.json`
5. `/Users/yangjingchi/.claude/memory/today.md`
6. `/Users/yangjingchi/.claude/memory/patterns.md` when debugging, stuck, or corrected

## Write Routing

| Layer | File | Use for |
|---|---|---|
| Project strategic SSOT | `<project>/PROJECT_CONTEXT.md` | Current state, completed stage, next stage, durable handoff |
| Project agent contract | `<project>/CLAUDE.md` / `<project>/AGENTS.md` | Long-lived rules, directory map, tool entrypoints, constraints |
| Human docs | `<project>/README.md`, `<project>/docs/**/*.md` | Usage, architecture, runbook, integration guide |
| Daily hot layer | `/Users/yangjingchi/.claude/memory/today.md` | Temporary progress and short daily handoff |
| Active task registry | `/Users/yangjingchi/.claude/memory/active-tasks.json` | Cross-project tasks that remain in flight |
| Pattern library | `/Users/yangjingchi/.claude/memory/patterns.md` | Reusable lessons triggered by correction, repeated failure, counter-intuitive finding, or non-obvious trade-off |
| Cross-project overview | `/Users/yangjingchi/.claude/memory/projects.md` | Summary pointers only, not detailed project status |

## What Not To Do

- Do not rely on Codex `/resume` as the only handoff for multi-day work.
- Do not dump full conversation summaries into `CLAUDE.md`.
- Do not let `today.md` become the long-term project state.
- Do not write secrets or local tokens into any memory file.
- Do not update `patterns.md` for routine one-off bugs.

## Good Handoff Shape

For `PROJECT_CONTEXT.md`, prefer a compact block:

```markdown
## Session Handoff

### 2026-04-30 — <stage name>

**Completed**
- ...

**Current truth**
- ...

**Next session should start with**
- Command/path/check to run first

**Open risks**
- ...
```

Keep it operational. The next agent should know what to read, what not to redo, and what exact action comes next.
