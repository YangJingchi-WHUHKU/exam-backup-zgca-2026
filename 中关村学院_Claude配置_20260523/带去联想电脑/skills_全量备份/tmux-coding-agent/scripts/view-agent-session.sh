#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: view-agent-session.sh -S socket -s session -t target
USAGE
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
  usage >&2
  exit 1
fi
script_dir="$(cd "$(dirname "$0")" && pwd)"
pybin="$($script_dir/python_for_views.sh)"
exec "$pybin" "$script_dir/live_views.py" monitor --socket "$socket" --session "$session" --target "$target"
