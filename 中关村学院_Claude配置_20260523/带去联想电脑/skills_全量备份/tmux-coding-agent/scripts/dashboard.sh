#!/usr/bin/env bash
set -euo pipefail

socket=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -S|--socket-path) socket="${2-}"; shift 2 ;;
    -h|--help) echo "Usage: dashboard.sh -S socket"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done
if [[ -z "$socket" ]]; then
  echo "socket required" >&2
  exit 1
fi
script_dir="$(cd "$(dirname "$0")" && pwd)"
pybin="$($script_dir/python_for_views.sh)"
exec "$pybin" "$script_dir/live_views.py" dashboard --socket "$socket"
