#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: wait-for-agent-ready.sh -S socket -t target [options]

Wait for a child coding CLI to become ready. Automatically confirms the common
Claude workspace trust prompt when it appears.

Options:
  -S, --socket-path  tmux socket path, required
  -t, --target       tmux target (session:window.pane), required
  -T, --timeout      seconds to wait (default: 30)
  -i, --interval     poll interval seconds (default: 1)
  -l, --lines        number of lines to inspect (default: 120)
  -h, --help         show this help
USAGE
}

socket_path=""
target=""
timeout=30
interval=1
lines=120
trust_confirmed=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    -S|--socket-path) socket_path="${2-}"; shift 2 ;;
    -t|--target)      target="${2-}"; shift 2 ;;
    -T|--timeout)     timeout="${2-}"; shift 2 ;;
    -i|--interval)    interval="${2-}"; shift 2 ;;
    -l|--lines)       lines="${2-}"; shift 2 ;;
    -h|--help)        usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$socket_path" || -z "$target" ]]; then
  echo "socket path and target are required" >&2
  usage
  exit 1
fi

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found in PATH" >&2
  exit 1
fi

start_epoch=$(date +%s)
deadline=$((start_epoch + timeout))

while true; do
  pane_text="$(tmux -S "$socket_path" capture-pane -p -J -t "$target" -S "-${lines}" 2>/dev/null || true)"

  if [[ "$trust_confirmed" == false ]] && printf '%s\n' "$pane_text" | grep -q 'Quick safety check:'; then
    tmux -S "$socket_path" send-keys -t "$target" Enter
    trust_confirmed=true
    sleep 1
    continue
  fi

  if printf '%s\n' "$pane_text" | grep -Eq '❯|Try ".*"'; then
    exit 0
  fi

  now=$(date +%s)
  if (( now >= deadline )); then
    echo "Timed out waiting for agent readiness" >&2
    printf '%s\n' "$pane_text" >&2
    exit 1
  fi

  sleep "$interval"
done

