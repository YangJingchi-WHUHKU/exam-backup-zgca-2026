#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: check-agent-cli.sh <command>

Verify that a requested interactive coding CLI is available either as:
- a real executable on PATH, or
- an interactive zsh alias/function defined in ~/.zshrc.

Examples:
  check-agent-cli.sh claude
  check-agent-cli.sh codex
  check-agent-cli.sh claudeniu
USAGE
}

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 1
fi

cmd="$1"

if command -v "$cmd" >/dev/null 2>&1; then
  path="$(command -v "$cmd")"
  tmpfile="/tmp/check-agent-cli.$$"
  "$cmd" --version >"$tmpfile" 2>&1 || true
  version="$(python3 - "$tmpfile" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
text = p.read_text(encoding='utf-8', errors='replace').strip().splitlines()
print(text[0] if text else '')
PY
)"
  rm -f "$tmpfile"
  printf 'FOUND executable %s %s\n' "$path" "$version"
  exit 0
fi

if zsh -lic "whence -v $cmd" >/tmp/check-agent-cli.$$ 2>&1; then
  kind="$(python3 - "/tmp/check-agent-cli.$$" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
text = p.read_text(encoding='utf-8', errors='replace').strip().splitlines()
print(text[0] if text else '')
PY
)"
  rm -f /tmp/check-agent-cli.$$
  printf 'FOUND shell %s\n' "$kind"
  exit 0
fi

rm -f /tmp/check-agent-cli.$$ || true
echo "MISSING $cmd" >&2
exit 1
