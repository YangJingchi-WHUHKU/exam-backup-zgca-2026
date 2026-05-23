#!/usr/bin/env bash
set -euo pipefail

title=""
if [[ "${1:-}" == "--title" ]]; then
  title="${2-}"
  shift 2
fi
if [[ $# -lt 1 ]]; then
  echo "Usage: open-terminal-tab.sh [--title TITLE] <command>" >&2
  exit 1
fi

cmd="$*"
osascript - "$cmd" "$title" <<'APPLESCRIPT'
on run argv
  set cmd to item 1 of argv
  set ttl to item 2 of argv
  tell application "Terminal"
    activate
    do script cmd
    if ttl is not "" then
      try
        set custom title of selected tab of front window to ttl
      end try
    end if
  end tell
end run
APPLESCRIPT
