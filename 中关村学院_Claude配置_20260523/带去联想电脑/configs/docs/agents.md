# Agent Configuration & Multi-Model Collaboration

> On-demand loading. Contains Agent assignment, Subagent dispatch, multi-model cross-verification rules.

---

## Agent Task Assignment

> Tier-based routing is the default. Claude orchestrates and handles high-level reasoning/doc writing; Codex is the default execution engine for most coding and research-execution work.

### Participating Models

| Model | Role | Method |
|-------|------|--------|
| **Claude Duck** | Primary orchestrator, architecture judge, final writer | Direct conversation (`~/.claude_duck/`) |
| **Codex CLI** | Default implementation engine for coding + execution-heavy research work | `codex exec "..."` or tmux-launched `codex` (`~/.codex/`) |
| **Codex MCP** | Bounded external reviewer / brainstormer / verifier | Claude Code MCP call to Codex |
| **Claude Codex** | Codex-first Claude profile; use when you intentionally want a Codex-native Claude session | CLI (`~/.claude_codex/`) |
| **MiniMax** | Alternative reasoning & review | CLI (`~/.claude_minimax/`) |
| **Claude NIU** | Supplementary verification | CLI (`~/.claude_niu/`) |

### Coordinator Agent (Main Agent = Claude)

| Duty | Description |
|------|-------------|
| **Orchestrate** | Dispatch tasks to other Agents/Models |
| **Decide** | Final judgment on critical matters |
| **Memory** | Maintain hot data layer (today.md) |
| **Align** | Daily status alignment |

### Built-in Agents

| Agent | Model | Use |
|-------|-------|-----|
| general-purpose | sonnet | General multi-step tasks |
| Explore | haiku | Quick codebase exploration |
| Plan | inherit | Architecture design, implementation planning |
| claude-code-guide | haiku | Claude Code usage guide |

---

## Subagent Dispatch Rules

> **Default parallel, unless there are dependencies**

**Trigger conditions (dispatch when any met)**:
- >=2 independent tasks
- P0 has multiple pending items
- User says "in parallel" / "simultaneously"
- Complex task can be split into independent modules

**Memory injection protocol (mandatory when dispatching subagent)**:
```
You are working on [project-name].

## Context Loading (must read first)
1. ~/.claude/memory/today.md — Today's work context
2. /path/to/project/PROJECT_CONTEXT.md — Project status

## Task
[Specific task description]

## Completion Requirements
1. Run lint + build yourself, confirm PASS
2. Update PROJECT_CONTEXT.md Session Handoff section
3. Report results
```

---

## Multi-Model Collaboration

> Default split: Claude decides and writes; Codex executes and verifies unless the task is too sensitive or too strategy-heavy.

### Claude's Duties (Coordinator)

| Do | Don't |
|----|-------|
| Understand requirements, decompose tasks, choose routing | Write large code blocks locally by default |
| Critical decisions and architecture trade-offs | Hoard routine implementation work that Codex can execute |
| Verify external output and integrate results | Spend premium Claude tokens on repetitive bulk coding |
| Maintain memory system and final narrative quality | Delegate sensitive secrets or irreversible actions blindly |

### Sensitive Code (Never outsource)

- Critical execution logic (orders, state changes, settlements)
- Credential operations (signing, auth, key management)
- Secret/Token handling
- Core business calculations (metrics, risk assessment)

---

## Five-Model Cross-Verification (Standard Practice)

> Claude Duck + Codex CLI + Claude Codex + MiniMax + Claude NIU — five models participate equally in verification to avoid single-point blind spots.

### Trigger Conditions (Proactive)

| Scenario | Must Cross-Verify |
|----------|-------------------|
| **Critical business logic** | Yes |
| **Architecture design** | Yes |
| **Complex bug diagnosis** | Yes |
| **Algorithm implementation correctness** | Yes |

### Output Format

```
Multi-model cross-verification:
- Claude Duck's view: [xxx]
- Codex CLI view: [xxx]
- Claude Codex view: [xxx]
- MiniMax view: [xxx]
- Claude NIU view: [xxx]
- Consensus: [xxx]
- Divergence: [xxx]
- Final conclusion: [xxx]
```

---

## Multi-Model SSOT Collaboration Contract

> All models use Claude as the hub, unified project state management.

### Data Layers

| Layer | Location | Writer | Purpose |
|-------|----------|--------|---------|
| **L0 Rules Layer** | ~/.claude/ | Claude only | Rules, memory, experience |
| **L1 Interface Layer** | PROJECT_CONTEXT.md | All models (restricted) | Project state |
| **L2 Archive Layer** | Knowledge vault | Claude + automation | Persistent knowledge |

### L1 Interface: PROJECT_CONTEXT.md Structure

Fixed structure, external models can only write to the Handoff block:

```markdown
# [Project Name] - Project Context

## Architecture (Claude maintains)
## Current Focus (Claude maintains)

<!-- handoff:start -->
## Session Handoff
- Last: [time] by [model-name]
- Task: [task ID/description]
- Did: [what was done]
- Next: [next steps]
- Blocker: [blockers]
<!-- handoff:end -->

## Tech Debt (Claude maintains)
```

### External Model Injection Template

```bash
codex exec "
# Project Contract (must follow)
1. Read PROJECT_CONTEXT.md first for status
2. Only modify code files + content between <!-- handoff:start/end -->
3. Never create/modify: ROADMAP.md, FOCUS.md, TODO.md, TASKS.md, STATUS.md
4. Never write to ~/.claude/ or knowledge vault (unless task explicitly requires)
5. After completion, write Handoff: Last: [time] by [model], Task: [description]

# Task
[specific task description]

# Verification
[verification commands]
"
```

### File Operation Whitelist

| Model | Can Create | Can Modify | Never Touch |
|-------|-----------|-----------|-------------|
| Claude | Anything (following behaviors.md) | Anything | - |
| External models | Code files | Code + Handoff block | ROADMAP/FOCUS/TODO/TASKS/.claude/vault/ |

### Violation Detection (Claude executes during review)

1. `git diff --name-only` — Check for modifications outside whitelist
2. Check PROJECT_CONTEXT.md changes are within `<!-- handoff:start/end -->` markers
3. Violation → `git checkout -- [file]` rollback + record in patterns.md

---

*Customize agent assignments and model routing based on your specific projects and needs.*

## Default Routing Policy

| Task type | Default engine | Why |
|----------|----------------|-----|
| Small bounded code change | `codex exec` | Cheap, fast, enough context for a single focused task |
| Large implementation / multi-file refactor / long test-fix loop | `tmux-coding-agent` launching `codex` | Persistent TTY, resumable, parallelizable, better for long-running execution |
| Bounded review / novelty check / external critique | Codex MCP | Keeps the exchange inside Claude while offloading reviewer cognition |
| Final document writing / strategy / synthesis / hard trade-off judgment | Claude | Higher value per token on planning and writing quality |

### tmux vs MCP vs codex exec

- **`codex exec`**: one-shot Codex worker, best for bounded implementation tasks.
- **tmux + `codex`**: a real long-lived Codex session, best for big coding jobs, parallel workers, or tasks needing iterative control.
- **Codex MCP**: Codex as a callable reviewer/assistant inside Claude Code, best for bounded consultation, review, and research critique, not for managing a long coding session.
