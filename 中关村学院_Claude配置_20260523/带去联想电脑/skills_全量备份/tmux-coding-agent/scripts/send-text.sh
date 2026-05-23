#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: send-text.sh -t target [options] [-- text...]

Send literal text to a tmux pane, optionally from stdin, and press Enter.

Options:
  -S, --socket-path  tmux socket path (default: $AGENT_TMUX_SOCKET_DIR/agent.sock)
  -t, --target       tmux target (session:window.pane), required
  -n, --no-enter     do not press Enter after sending text
  -f, --file         read text from a file
  --force            bypass active human-control guard
  -h, --help         show this help
USAGE
}

socket_dir="${AGENT_TMUX_SOCKET_DIR:-${NANOBOT_TMUX_SOCKET_DIR:-${TMPDIR:-/tmp}/agent-tmux-sockets}}"
socket_path="$socket_dir/agent.sock"
target=""
submit_enter=true
file_path=""
force_send=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -S|--socket-path) socket_path="${2-}"; shift 2 ;;
    -t|--target)      target="${2-}"; shift 2 ;;
    -n|--no-enter)    submit_enter=false; shift ;;
    -f|--file)        file_path="${2-}"; shift 2 ;;
    --force)          force_send=true; shift ;;
    -h|--help)        usage; exit 0 ;;
    --)               shift; break ;;
    *) break ;;
  esac
done

if [[ -z "$target" ]]; then
  echo "target is required" >&2
  usage
  exit 1
fi
if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found in PATH" >&2
  exit 1
fi

payload=""
if [[ -n "$file_path" ]]; then
  payload="$(cat "$file_path")"
elif [[ $# -gt 0 ]]; then
  payload="$*"
elif [[ ! -t 0 ]]; then
  payload="$(cat)"
fi
if [[ -z "$payload" ]]; then
  echo "No text provided" >&2
  exit 1
fi

session_name="${target%%:*}"
script_dir="$(cd "$(dirname "$0")" && pwd)"

if [[ "$force_send" != true ]]; then
  status_json="$($script_dir/session-status.py --socket "$socket_path" --session "$session_name" --target "$target")"
  owner="$(python3 - "$status_json" <<'PY'
import json, sys
print(json.loads(sys.argv[1])['owner'])
PY
)"
  if [[ "$owner" == "human" ]]; then
    echo "Refusing to send while human control is active for $session_name" >&2
    exit 1
  fi
fi

tmux -S "$socket_path" send-keys -t "$target" -l -- "$payload"
payload_preview="$(python3 - "$payload" <<'PY'
import sys
text = sys.argv[1].replace('\n', ' ')
print(text[:160])
PY
)"
"$script_dir/session-registry.py" append-prompt --socket "$socket_path" --session "$session_name" --prompt "$payload_preview" >/dev/null || true
if [[ "$submit_enter" == true ]]; then
  tmux -S "$socket_path" send-keys -t "$target" Enter
fi
printf 'Sent %s chars to %s on %s\n' "${#payload}" "$target" "$socket_path"
