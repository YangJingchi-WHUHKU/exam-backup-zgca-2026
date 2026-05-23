#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: wait-for-agent-idle.sh -S socket -t target [options]

Wait until a child coding CLI appears idle by watching pane stability.

Options:
  -S, --socket-path  tmux socket path, required
  -t, --target       tmux target (session:window.pane), required
  -T, --timeout      seconds to wait (default: 120)
  -i, --interval     poll interval seconds (default: 2)
  -l, --lines        number of lines to inspect (default: 160)
  -s, --stable       identical captures required before success (default: 3)
  -h, --help         show this help
USAGE
}

socket_path=""
target=""
timeout=120
interval=2
lines=160
stable_required=3
stable_count=0
last_capture=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -S|--socket-path) socket_path="${2-}"; shift 2 ;;
    -t|--target)      target="${2-}"; shift 2 ;;
    -T|--timeout)     timeout="${2-}"; shift 2 ;;
    -i|--interval)    interval="${2-}"; shift 2 ;;
    -l|--lines)       lines="${2-}"; shift 2 ;;
    -s|--stable)      stable_required="${2-}"; shift 2 ;;
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

  if printf '%s\n' "$pane_text" | grep -Eq 'Gusting…|Thinking|Running|Esc to interrupt|ctrl\+c to interrupt'; then
    stable_count=0
  elif printf '%s\n' "$pane_text" | grep -Eq '❯|\$ '; then
    if [[ "$pane_text" == "$last_capture" ]]; then
      stable_count=$((stable_count + 1))
    else
      stable_count=1
    fi
    if (( stable_count >= stable_required )); then
      exit 0
    fi
  else
    stable_count=0
  fi

  last_capture="$pane_text"

  now=$(date +%s)
  if (( now >= deadline )); then
    echo "Timed out waiting for agent idle state" >&2
    printf '%s\n' "$pane_text" >&2
    exit 1
  fi

  sleep "$interval"
done
