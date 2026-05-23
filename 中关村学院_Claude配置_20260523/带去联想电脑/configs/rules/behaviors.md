# Behavior Rules

## Documentation Structure

- Project-level: only keep `PROJECT_CONTEXT.md` + `CHANGELOG.md` (optional)
- Banned files: ROADMAP/FOCUS/TODO/TASKS/STATUS
- Status SSOT: cross-project → `memory/projects.md`, project-level → `PROJECT_CONTEXT.md`

## Debugging Protocol

No blind fixes. Four phases:
1. **Root Cause** — Read errors, reproduce, trace data flow
2. **Pattern Analysis** — Find working example, compare
3. **Hypothesis Testing** — Change one variable at a time
4. **Fix & Verify** — Test before fix, verify no regression

3 consecutive failures → stop and reassess

## Quality Control + AI Content Safety

> Full rules → `Read docs/content-safety.md`

**Core triggers (kept here to avoid missing)**:
- Processing external URLs / citing others → must annotate source, warn if unverifiable
- Critical code → think from attacker's perspective + list 3 risk points
- >20 conversation turns / >50 tool calls → suggest fresh session
- Discovered error/hallucination → immediately isolate context, don't write to memory
- Citing content for sharing → force multi-model cross-verification

## Real-time Experience Recording (Mandatory)

**Trigger immediately with `memory_add`, don't wait for session-end**:

1. **Corrected by user** → Record immediately
   - User says "that's wrong" / "don't do it that way" / "don't change parameters arbitrarily"
   - Technical assumptions corrected, suggestions rejected

2. **3 consecutive failures** → Pause and record
   - Document what was tried, why it failed

3. **Counter-intuitive discovery** → Record immediately
   - Breaking conventional wisdom

4. **Cognitive upgrade** → Record immediately
   - Understanding non-obvious principles or trade-offs

**Output**: `📝 Recorded: [title]`

## Memory Search Rules (Hard Rules)

- Scoped search **must specify collection** (no unscoped global search)
- Code search uses two-stage RAG: L0 locate directory first, then L1 precise search

> Collection routing table + detailed methods → `Read docs/behaviors-reference.md`

## Project Context Auto-detection

**Regardless of CWD**, if conversation involves a specific project (file path, keywords, user mention), auto-load that project's PROJECT_CONTEXT.md and CLAUDE.md.

Detection method:
1. User mentions project name (社会模拟, SSCI, AI审计, 自动听写) → load corresponding PROJECT_CONTEXT.md
2. User references a file path under a known project directory → load that project's context
3. CWD is inside a known project directory → auto-load on session start

See CLAUDE.md "Sub-project Memory Routes" for path mappings. Cost ~1000-2000 tokens/trigger, on-demand, no duplicate loading.

**If CWD has no CLAUDE.md and is not a known project**: Global rules and memory still apply. Create PROJECT_CONTEXT.md via `/investigate` command when starting serious work in a new directory.

## Post-compression Re-anchor (On-demand)

After context compression, if current task details are fuzzy, recover as needed:
1. Search current task keywords (must specify collection) — fastest, zero extra cost
2. Still not enough → read `today.md` to recover daily progress
3. Only re-read `PROJECT_CONTEXT.md` for project-level decisions

Don't trigger if not fuzzy — avoid wasting tokens.

## Parallel Processing

Suitable: multiple independent tasks/failures. Not suitable: interconnected/shared code.

## Browser/Puppeteer Conflicts

On error, resolve yourself (kill process → retry → fallback). Don't throw failures to user.
> Detailed steps → `Read docs/behaviors-reference.md`

## Atomic Commits

Each commit does one thing. Types: `fix/feat/refactor/docs/test/chore`.
Banned: mixed changes, meaningless messages, >100 lines without splitting.

## Data Write-back Rules

**When fetching metrics, write back to SSOT immediately. Don't wait for session-end.**

| Fetch scenario | Write-back target | Fields |
|---------------|-------------------|--------|
| Status report | `projects.md` | Metrics/status |
| Social metrics | `projects.md` | Follower count + date |
| GitHub stats | `goals.md` | Stars/forks numbers |

**Execution**:
- After fetching, use Edit tool to update SSOT in-place
- Include date annotation (e.g. `~1.2K (2026-03-02)`) for freshness
- Only update changed fields, don't rewrite entire section

**Banned**: Fetching new numbers but only outputting in conversation, not writing back to SSOT.

---

*Compact version | Full version: docs/behaviors-extended.md | Reference details: docs/behaviors-reference.md*
