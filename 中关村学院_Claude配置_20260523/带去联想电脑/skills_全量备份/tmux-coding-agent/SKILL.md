---
name: tmux-coding-agent
description: "Launch and control coding CLIs in isolated tmux sessions. This skill should be used when the user asks to 'start agent session', 'run claude in tmux', 'launch codex', 'show dashboard', 'takeover session', '启动agent', '运行子agent', '打开总控台', '接管颗粒', '看看有哪些颗粒', '并行运行agent', '批量并行处理', '批量跑案例', '并发agent', 'batch parallel', 'run N agents', or needs persistent TTY for interactive CLI tools."
---

# Tmux Coding Agent

Use this skill when a normal shell command is not enough because the target tool needs a persistent interactive TTY. This skill is intentionally confined to the current working directory only. It must not launch child agents into any other directory.

## Core Layout Rules (Mandatory)

1. **Window > Pane**: Always create new tmux **windows** (not panes) for parallel jobs.
   - Panes share the terminal height — 10+ panes will fail to split on small terminals.
   - Windows have no such limit; 10, 20, 50 jobs each get their own full-screen window.
   - Only use panes if the user explicitly requests a split-screen layout.

2. **Auto-launch Dashboard on every tmux trigger**: Every time this skill starts one or more agent sessions, it **must** automatically open the Dashboard overview (via `dashboard.sh`).
   - The Dashboard shows all windows/sessions: name, CLI type, state (idle/busy/blocked), owner.
   - This is the "command center" — the user should always be able to see all agents at a glance.
   - Do NOT wait for the user to ask for it; open it proactively.
   - Set `AGENT_TMUX_OPEN_DASHBOARD=1` before calling `start-agent-session.sh`.

3. **Multi-line prompts**: Use `tmux load-buffer + paste-buffer` (not `send-keys -l`) when prompt text contains newlines. `send-keys` truncates at newlines in zsh.

## Safety Boundary

- Child sessions must start in the current working directory only.
- Do not pass `--add-dir`, `-C`, `--cd`, or any equivalent directory-expansion flag.
- Do not prepend `cd /other/path && ...` or otherwise launch outside the current workspace.
- Use the exact CLI name requested by the user.
- If the requested CLI is missing, stop and report that exact command.


## Intent Shortcuts

This skill should also be used when the user says things like:

- "接管刚才那个颗粒"
- "打开 Dashboard" / "打开总控台"
- "看看现在有哪些颗粒"
- "打开那个 claude 的监控"
- "我来接手这个 agent"

Prefer natural-language requests first. The default viewing mode is the Dashboard. If a direct command is needed, use these short commands:

- `/particles`
- `/takeover [session-or-cli]`
- `/watch-agent [session-or-cli]`
- `/agent-dashboard [session-or-cli]`

## Supported CLIs

- `claude`
- `codex`
- `claudeniu`
- `claudecodex`
- `minimax`

For Claude-family CLIs, the launcher automatically clears the parent `CLAUDECODE` marker before startup so a child Claude session can run inside tmux even when the parent agent is already Claude Code.

## Visibility Model

Every started child session should, by default:

1. Start inside its own tmux session on a private socket.
2. Automatically open a Dashboard window once per socket for multi-session overview.
3. Open the single-agent monitor only when the user asks to watch a specific particle.
4. Keep human takeover separate from read-only viewing.

The read-only monitor tab does **not** attach as a tmux client, so AI control can continue without being mistaken for human activity.

## Human Takeover Protocol

- Humans should normally intervene by natural language first, for example: "接管刚才那个颗粒"、"我来接手这个 agent"、"打开那个 claude 的监控"、"打开总控台". Only use raw commands as fallback.
- Takeover opens a real attached Terminal tab for manual control.
- While a human attached client is active, AI sends must stop.
- If no human input is detected for `${AGENT_TMUX_HUMAN_TIMEOUT:-30}` seconds, AI may resume control.
- Detach with `Ctrl+b` then `d`.

## Environment Checks

Before starting, verify the required binaries exist:

```bash
command -v tmux
{baseDir}/scripts/check-agent-cli.sh claude
{baseDir}/scripts/check-agent-cli.sh codex
```

## Preferred Workflow

### 1. Start a child session in the current directory

```bash
{baseDir}/scripts/start-agent-session.sh -s reviewer -w "$PWD" -- claude
```

The launcher prints:

- `SOCKET`
- `SESSION`
- `TARGET`
- `ATTACH` — the takeover entry command
- `CAPTURE` — raw pane capture command

### 2. Wait for readiness

Use the readiness helper to auto-confirm the common Claude trust prompt and wait until the child session is usable:

```bash
{baseDir}/scripts/wait-for-agent-ready.sh -S "$SOCKET" -t "$TARGET"
```

### 3. Send work only when AI owns the session

```bash
{baseDir}/scripts/send-text.sh -S "$SOCKET" -t "$TARGET" -- "Inspect the repo and fix the failing tests."
```

`send-text.sh` refuses to send while active human control is detected.

### 4. Wait for idle before reading results

```bash
{baseDir}/scripts/wait-for-agent-idle.sh -S "$SOCKET" -t "$TARGET"
tmux -S "$SOCKET" capture-pane -p -J -t "$TARGET" -S -200
```

### 5. Open a single-agent monitor only when needed

If you want to watch one particle in detail, open the monitor on demand:

```bash
/watch-agent [session-or-cli]
```

Or say things like "打开刚才那个颗粒的监控".

### 6. Human takeover when needed

Use the printed `ATTACH` command, or run:

```bash
{baseDir}/scripts/takeover-agent-session.sh -S "$SOCKET" -s "$SESSION" -t "$TARGET"
```

This opens a dedicated Terminal tab with a real tmux attach for manual intervention.

## Dashboard

The dashboard presents all sessions on a socket with:

- session name
- CLI type
- state (`starting`, `idle`, `busy`, `blocked-trust`)
- owner (`ai` or `human`)
- target identifier
- takeover command per session

Manual launch:

```bash
{baseDir}/scripts/dashboard.sh -S "$SOCKET"
```

## Batch Parallel Workflow

Use `batch-parallel.sh` when you need to run N agents concurrently on different inputs (e.g., 10 cases, 20 documents).

### Jobs File Format (TSV)
```
# id<TAB>prompt_text
case001	分析以下判决书并输出链图：...
case002	分析以下判决书并输出链图：...
```

### Usage
```bash
# prepare a jobs.tsv, then:
{baseDir}/scripts/batch-parallel.sh \
  -j /path/to/jobs.tsv \
  -o ./batch-output \
  -c claude \
  --wait               # optional: block until all agents finish
```

This creates **one tmux window per job** (not panes), automatically launches the Dashboard, and handles multi-line prompts via `tmux load-buffer + paste-buffer`.

Output files are written to `<output-dir>/<id>.txt` after each agent goes idle.

### Key Design Decisions (from real pain points)
| Problem | Solution |
|---------|----------|
| `bash mapfile`/`${!arr[@]}` fails in zsh | `batch-parallel.sh` is `zsh`-native, uses `typeset -a` |
| 10 panes too cramped, terminal can't split | One window per job — no height limit |
| Multi-line text truncated by `send-keys` | Uses `tmux load-buffer + paste-buffer` |
| No output collection flow | `--wait` flag captures pane output to `<output-dir>/<id>.txt` |

## Bundled Scripts

- `check-agent-cli.sh` — verify that a requested CLI exists as a binary or zsh shell function
- `start-agent-session.sh` — start a child CLI in tmux, confined to the current directory, auto-open Dashboard + monitor tabs, register session metadata
- `batch-parallel.sh` — **NEW** launch N parallel agents (one window each), send per-job prompts via buffer, collect outputs; zsh-native
- `wait-for-agent-ready.sh` — auto-confirm the common trust prompt and wait until the child CLI is ready
- `send-text.sh` — send literal text to a pane, but refuse while active human control is detected
- `wait-for-agent-idle.sh` — wait until the child CLI appears idle using pane-stability heuristics
- `view-agent-session.sh` — read-only live monitor for one session in Terminal
- `takeover-agent-session.sh` — open a real attached Terminal tab for human control
- `dashboard.sh` — show all active sessions on a socket in a single overview screen (**auto-opens on every session start**)
- `find-sessions.sh` — inspect active sessions on one socket or scan all private sockets
- `wait-for-text.sh` — low-level regex wait helper for custom flows

## Claude Example

```bash
{baseDir}/scripts/start-agent-session.sh -s claude-worker -w "$PWD" -- claude
{baseDir}/scripts/wait-for-agent-ready.sh -S "$SOCKET" -t "$TARGET"
{baseDir}/scripts/send-text.sh -S "$SOCKET" -t "$TARGET" -- "Reply with a short plan, then fix the failing tests."
{baseDir}/scripts/wait-for-agent-idle.sh -S "$SOCKET" -t "$TARGET"
tmux -S "$SOCKET" capture-pane -p -J -t "$TARGET" -S -200
```

## Codex Example

```bash
{baseDir}/scripts/start-agent-session.sh -s codex-worker -w "$PWD" -- codex --yolo
{baseDir}/scripts/wait-for-agent-ready.sh -S "$SOCKET" -t "$TARGET"
{baseDir}/scripts/send-text.sh -S "$SOCKET" -t "$TARGET" -- "Fix the lint errors and summarize the changes."
{baseDir}/scripts/wait-for-agent-idle.sh -S "$SOCKET" -t "$TARGET"
```
