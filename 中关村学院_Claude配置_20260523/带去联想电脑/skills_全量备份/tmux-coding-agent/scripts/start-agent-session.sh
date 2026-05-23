#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: start-agent-session.sh [options] -- <command>

Create a detached tmux session on a private socket and launch a supported coding CLI.

Options:
  -S, --socket-path  tmux socket path (default: $AGENT_TMUX_SOCKET_DIR/agent.sock)
  -s, --session      session name (default: agent-YYYYmmdd-HHMMSS)
  -w, --workdir      working directory for the session; must equal the current directory
  -n, --window       window name (default: shell)
  -h, --help         show this help
USAGE
}

socket_dir="${AGENT_TMUX_SOCKET_DIR:-${NANOBOT_TMUX_SOCKET_DIR:-${TMPDIR:-/tmp}/agent-tmux-sockets}}"
socket_path=""
session="agent-$(date +%Y%m%d-%H%M%S)"
workdir="$PWD"
window="shell"
allowed_clis=(claude codex claudeniu claudecodex minimax)
claude_family=(claude claudeniu claudecodex minimax)

while [[ $# -gt 0 ]]; do
  case "$1" in
    -S|--socket-path) socket_path="${2-}"; shift 2 ;;
    -s|--session)     session="${2-}"; shift 2 ;;
    -w|--workdir)     workdir="${2-}"; shift 2 ;;
    -n|--window)      window="${2-}"; shift 2 ;;
    -h|--help)        usage; exit 0 ;;
    --)               shift; break ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ $# -eq 0 ]]; then
  echo "A CLI command is required after --" >&2
  usage
  exit 1
fi

cli_name="$1"
startup_cmd="$*"
script_dir="$(cd "$(dirname "$0")" && pwd)"
state_dir="${AGENT_TMUX_STATE_DIR:-$HOME/.tmux-coding-agent-state}"
mkdir -p "$state_dir"

current_resolved="$(python3 - <<'PY'
from pathlib import Path
print(Path.cwd().resolve())
PY
)"
workdir_resolved="$(python3 - "$workdir" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve())
PY
)"

if [[ "$workdir_resolved" != "$current_resolved" ]]; then
  echo "Refusing to start outside current working directory." >&2
  echo "Current: $current_resolved" >&2
  echo "Requested: $workdir_resolved" >&2
  exit 1
fi

allowed=false
for name in "${allowed_clis[@]}"; do
  if [[ "$cli_name" == "$name" ]]; then
    allowed=true
    break
  fi
done
if [[ "$allowed" != true ]]; then
  echo "Unsupported CLI: $cli_name" >&2
  echo "Allowed: ${allowed_clis[*]}" >&2
  exit 1
fi

args=("$@")
for ((i = 1; i < ${#args[@]}; i++)); do
  case "${args[$i]}" in
    --add-dir|-C|--cd)
      echo "Refusing directory-expansion flag: ${args[$i]}" >&2
      exit 1
      ;;
  esac
done

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found in PATH" >&2
  exit 1
fi
"$script_dir/check-agent-cli.sh" "$cli_name" >/dev/null

if [[ -z "$socket_path" ]]; then
  mkdir -p "$socket_dir"
  socket_path="$socket_dir/agent.sock"
else
  mkdir -p "$(dirname "$socket_path")"
fi

if [[ ! -d "$workdir_resolved" ]]; then
  echo "Working directory not found: $workdir_resolved" >&2
  exit 1
fi
if tmux -S "$socket_path" has-session -t "$session" 2>/dev/null; then
  echo "Session already exists on socket: $session" >&2
  exit 1
fi

tmux -S "$socket_path" new-session -d -s "$session" -n "$window" -c "$workdir_resolved" "${SHELL:-/bin/zsh}" -li
target="$session:0.0"

safe_cmd="$(python3 - "$@" <<'PY'
import shlex, sys
print(' '.join(shlex.quote(arg) for arg in sys.argv[1:]))
PY
)"
launch_cmd="$safe_cmd"
for name in "${claude_family[@]}"; do
  if [[ "$cli_name" == "$name" ]]; then
    launch_cmd="unset CLAUDECODE; $safe_cmd"
    break
  fi
done

tmux -S "$socket_path" send-keys -t "$target" -l -- "$launch_cmd"
tmux -S "$socket_path" send-keys -t "$target" Enter

"$script_dir/session-registry.py" register --socket "$socket_path" --session "$session" --target "$target" --workdir "$workdir_resolved" --cli "$cli_name" >/dev/null

cwd_q="$(python3 - "$current_resolved" <<'PY'
import shlex, sys
print(shlex.quote(sys.argv[1]))
PY
)"
socket_q="$(python3 - "$socket_path" <<'PY'
import shlex, sys
print(shlex.quote(sys.argv[1]))
PY
)"
session_q="$(python3 - "$session" <<'PY'
import shlex, sys
print(shlex.quote(sys.argv[1]))
PY
)"
target_q="$(python3 - "$target" <<'PY'
import shlex, sys
print(shlex.quote(sys.argv[1]))
PY
)"

if [[ "${AGENT_TMUX_OPEN_VIEWS:-0}" == "1" ]]; then
  "$script_dir/open-terminal-tab.sh" --title "AI MONITOR / AI监控 — $session" "cd $cwd_q && $script_dir/view-agent-session.sh -S $socket_q -s $session_q -t $target_q" >/dev/null 2>&1 || true
fi

dashboard_marker="$state_dir/dashboard-$(printf '%s' "$socket_path" | shasum | awk '{print $1}').marker"
if [[ "${AGENT_TMUX_OPEN_DASHBOARD:-1}" == "1" && ! -f "$dashboard_marker" ]]; then
  "$script_dir/open-terminal-tab.sh" --title "AI DASHBOARD / AI总控台 — $(basename "$workdir_resolved")" "cd $cwd_q && $script_dir/dashboard.sh -S $socket_q" >/dev/null 2>&1 || true
  date +%s > "$dashboard_marker"
fi

printf 'SOCKET=%s\n' "$socket_path"
printf 'SESSION=%s\n' "$session"
printf 'TARGET=%s\n' "$target"
printf 'WORKDIR=%s\n' "$workdir_resolved"
printf 'ATTACH=%s\n' "$script_dir/takeover-agent-session.sh -S $socket_q -s $session_q -t $target_q"
printf 'CAPTURE=tmux -S "%s" capture-pane -p -J -t "%s" -S -200\n' "$socket_path" "$target"
