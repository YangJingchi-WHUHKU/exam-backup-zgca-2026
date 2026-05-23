#!/usr/bin/env zsh
# batch-parallel.sh — launch N parallel agent windows, send per-item prompts,
# collect output to files, and optionally wait for all to finish.
#
# Usage:
#   batch-parallel.sh [options] --jobs-file <file>
#
# jobs-file format (TSV, one job per line):
#   <id>\t<prompt_text>
#
# Options:
#   -S, --socket-path   tmux socket (default: $AGENT_TMUX_SOCKET_DIR/agent.sock)
#   -s, --session       base session name (default: batch-<timestamp>)
#   -c, --cli           CLI to run (default: claude)
#   -w, --workdir       working directory (default: $PWD)
#   -j, --jobs-file     path to TSV jobs file (required)
#   -o, --output-dir    directory to write per-job output files (default: ./batch-output)
#   --wait              wait for all agents to finish before exiting (default: false)
#   --timeout           per-job idle timeout in seconds (default: 300)
#   -h, --help          show this help
#
# Key design decisions (from real-world pain points):
#   1. ZSH-native syntax — no bash mapfile/${!arr[@]}
#   2. Each job gets its own tmux WINDOW (not pane) inside one session to avoid
#      terminal height/split limits when running 10+ parallel jobs
#   3. Multi-line prompt text is sent via tmux load-buffer + paste-buffer to
#      avoid shell truncation at newlines

set -euo pipefail

# ── helpers ──────────────────────────────────────────────────────────────────
usage() {
  sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
  echo ""
}

log()  { printf '[batch] %s\n' "$*" >&2; }
die()  { printf '[batch] ERROR: %s\n' "$*" >&2; exit 1; }

# send multiline text safely via tmux buffer (avoids newline truncation)
send_multiline() {
  local socket="$1" target="$2" text="$3"
  local buf_name="batch-buf-$$-$RANDOM"
  # write to tmux buffer then paste — handles \n inside text correctly
  tmux -S "$socket" load-buffer -b "$buf_name" - <<<"$text"
  tmux -S "$socket" paste-buffer -b "$buf_name" -t "$target" -d
  tmux -S "$socket" send-keys -t "$target" Enter
}

# ── argument parsing ──────────────────────────────────────────────────────────
socket_dir="${AGENT_TMUX_SOCKET_DIR:-${NANOBOT_TMUX_SOCKET_DIR:-${TMPDIR:-/tmp}/agent-tmux-sockets}}"
socket_path="$socket_dir/agent.sock"
session="batch-$(date +%Y%m%d-%H%M%S)"
cli_name="claude"
workdir="$PWD"
jobs_file=""
output_dir="$PWD/batch-output"
do_wait=false
timeout_sec=300

while [[ $# -gt 0 ]]; do
  case "$1" in
    -S|--socket-path) socket_path="$2"; shift 2 ;;
    -s|--session)     session="$2";     shift 2 ;;
    -c|--cli)         cli_name="$2";    shift 2 ;;
    -w|--workdir)     workdir="$2";     shift 2 ;;
    -j|--jobs-file)   jobs_file="$2";   shift 2 ;;
    -o|--output-dir)  output_dir="$2";  shift 2 ;;
    --wait)           do_wait=true;     shift   ;;
    --timeout)        timeout_sec="$2"; shift 2 ;;
    -h|--help)        usage; exit 0 ;;
    --) shift; break ;;
    *) die "Unknown option: $1" ;;
  esac
done

# ── validation ────────────────────────────────────────────────────────────────
[[ -n "$jobs_file" ]] || die "--jobs-file is required"
[[ -f "$jobs_file" ]] || die "jobs file not found: $jobs_file"
command -v tmux >/dev/null 2>&1 || die "tmux not found in PATH"

script_dir="$(cd "$(dirname "$0")" && pwd)"
"$script_dir/check-agent-cli.sh" "$cli_name" >/dev/null

mkdir -p "$socket_dir" "$(dirname "$socket_path")" "$output_dir"

# resolve workdir
workdir_resolved="$(python3 -c "from pathlib import Path; print(Path('$workdir').resolve())")"
[[ -d "$workdir_resolved" ]] || die "workdir not found: $workdir_resolved"

# safety: must be inside current directory tree
current_resolved="$(python3 -c "from pathlib import Path; print(Path.cwd().resolve())")"
case "$workdir_resolved" in
  "$current_resolved"*) ;;  # OK
  *) die "workdir must be inside current directory. Current: $current_resolved, Requested: $workdir_resolved" ;;
esac

# ── load jobs (zsh-native, no mapfile) ───────────────────────────────────────
typeset -a job_ids job_prompts
while IFS=$'\t' read -r jid jprompt; do
  [[ -z "$jid" || "$jid" == \#* ]] && continue  # skip empty / comment lines
  job_ids+=("$jid")
  job_prompts+=("$jprompt")
done < "$jobs_file"

total=${#job_ids[@]}
[[ $total -gt 0 ]] || die "No jobs found in $jobs_file"
log "Loaded $total jobs from $jobs_file"

# ── create or reuse session ───────────────────────────────────────────────────
claude_family=(claude claudeniu claudecodex minimax)
is_claude_family=false
for name in "${claude_family[@]}"; do
  [[ "$cli_name" == "$name" ]] && is_claude_family=true && break
done

if ! tmux -S "$socket_path" has-session -t "$session" 2>/dev/null; then
  # Create session with a dummy first window (window 0 = "ctrl")
  tmux -S "$socket_path" new-session -d -s "$session" -n "ctrl" -c "$workdir_resolved" "${SHELL:-/bin/zsh}" -li
  log "Created tmux session: $session on socket: $socket_path"
fi

# ── launch one window per job ─────────────────────────────────────────────────
typeset -a targets
for (( i = 1; i <= total; i++ )); do
  jid="${job_ids[$i]}"
  win_name="job-${jid}"

  # create a new window for this job (avoids pane split height limits)
  tmux -S "$socket_path" new-window -t "$session" -n "$win_name" -c "$workdir_resolved" "${SHELL:-/bin/zsh}" -li
  win_idx=$(tmux -S "$socket_path" display-message -t "$session:$win_name" -p '#{window_index}')
  target="$session:${win_idx}.0"
  targets+=("$target")

  # launch CLI
  if [[ "$is_claude_family" == true ]]; then
    tmux -S "$socket_path" send-keys -t "$target" "unset CLAUDECODE; $cli_name" Enter
  else
    tmux -S "$socket_path" send-keys -t "$target" "$cli_name" Enter
  fi

  log "[$i/$total] Launched window $win_name → target $target"
done

log "All $total windows created. Waiting for CLIs to be ready..."

# ── wait for ready + send prompts ─────────────────────────────────────────────
for (( i = 1; i <= total; i++ )); do
  jid="${job_ids[$i]}"
  prompt="${job_prompts[$i]}"
  target="${targets[$i]}"

  # wait for ready
  "$script_dir/wait-for-agent-ready.sh" -S "$socket_path" -t "$target" 2>/dev/null || {
    log "WARNING: job $jid ready-wait failed, sending anyway"
  }

  # send prompt via buffer to handle multi-line text
  send_multiline "$socket_path" "$target" "$prompt"
  log "[$i/$total] Sent prompt to job $jid ($(echo "$prompt" | wc -c | tr -d ' ') bytes)"
done

log "All prompts sent. Output dir: $output_dir"
printf 'SOCKET=%s\nSESSION=%s\nJOBS=%d\nOUTPUT_DIR=%s\n' \
  "$socket_path" "$session" "$total" "$output_dir"

# ── optionally wait and collect output ───────────────────────────────────────
if [[ "$do_wait" == true ]]; then
  log "Waiting for all jobs to finish (timeout: ${timeout_sec}s each)..."
  for (( i = 1; i <= total; i++ )); do
    jid="${job_ids[$i]}"
    target="${targets[$i]}"
    out_file="$output_dir/${jid}.txt"

    "$script_dir/wait-for-agent-idle.sh" -S "$socket_path" -t "$target" --timeout "$timeout_sec" 2>/dev/null || {
      log "WARNING: job $jid idle-wait timed out"
    }

    # capture last 500 lines of pane output
    tmux -S "$socket_path" capture-pane -p -J -t "$target" -S -500 > "$out_file"
    log "[$i/$total] Job $jid output → $out_file"
  done
  log "All done. Results in $output_dir/"
else
  log "Jobs running in background. To collect output later, run:"
  log "  tmux -S '$socket_path' capture-pane -p -J -t '<target>' -S -500"
  log "  See session in Dashboard: $script_dir/dashboard.sh -S '$socket_path'"
fi
