#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: human-attach.sh -S socket -s session -t target" >&2
}

socket=""
session=""
target=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -S|--socket-path) socket="${2-}"; shift 2 ;;
    -s|--session)     session="${2-}"; shift 2 ;;
    -t|--target)      target="${2-}"; shift 2 ;;
    -h|--help)        usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done
if [[ -z "$socket" || -z "$session" || -z "$target" ]]; then
  usage
  exit 1
fi
script_dir="$(cd "$(dirname "$0")" && pwd)"
"$script_dir/session-registry.py" set-owner --socket "$socket" --session "$session" --owner human >/dev/null || true
clear
echo "Human takeover active for $session"
echo "If you stop typing for ${AGENT_TMUX_HUMAN_TIMEOUT:-30}s, AI may resume control."
echo "Detach with Ctrl+b then d."
tmux -S "$socket" attach -t "$session" || true
"$script_dir/session-registry.py" set-owner --socket "$socket" --session "$session" --owner ai >/dev/null || true
