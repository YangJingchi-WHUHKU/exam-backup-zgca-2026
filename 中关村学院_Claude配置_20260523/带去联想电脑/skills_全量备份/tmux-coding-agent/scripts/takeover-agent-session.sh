#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: takeover-agent-session.sh -S socket -s session -t target" >&2
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
cmd="$(python3 - "$PWD" "$script_dir" "$socket" "$session" "$target" <<'PY'
import shlex, sys
cwd, script_dir, socket, session, target = sys.argv[1:]
print(
    f"cd {shlex.quote(cwd)} && "
    f"{shlex.quote(script_dir + '/human-attach.sh')} "
    f"-S {shlex.quote(socket)} -s {shlex.quote(session)} -t {shlex.quote(target)}"
)
PY
)"
"$script_dir/open-terminal-tab.sh" "$cmd"
