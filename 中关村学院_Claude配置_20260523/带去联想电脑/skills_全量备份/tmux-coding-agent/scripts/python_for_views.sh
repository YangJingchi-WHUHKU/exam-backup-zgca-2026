#!/usr/bin/env bash
set -euo pipefail

candidates=()
if [[ -n "${TMUX_CODING_AGENT_PYTHON:-}" ]]; then
  candidates+=("$TMUX_CODING_AGENT_PYTHON")
fi
candidates+=("/Users/yangjingchi/miniconda3/bin/python3" "python3")

for candidate in "${candidates[@]}"; do
  if [[ "$candidate" == *"/"* ]]; then
    [[ -x "$candidate" ]] || continue
    bin="$candidate"
  else
    bin="$(command -v "$candidate" 2>/dev/null || true)"
    [[ -n "$bin" ]] || continue
  fi
  if "$bin" - <<'PY' >/dev/null 2>&1
try:
    import rich
except Exception:
    raise SystemExit(1)
PY
  then
    echo "$bin"
    exit 0
  fi
done

# Fallback: return first available python3 even without rich
for candidate in "${candidates[@]}"; do
  if [[ "$candidate" == *"/"* ]]; then
    [[ -x "$candidate" ]] || continue
    echo "$candidate"
    exit 0
  else
    bin="$(command -v "$candidate" 2>/dev/null || true)"
    [[ -n "$bin" ]] || continue
    echo "$bin"
    exit 0
  fi
done

echo "python3 not found" >&2
exit 1
