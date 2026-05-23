#!/bin/zsh
set -euo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
  echo "Usage: $0 <command_name> <base_url> <api_key> [model]" >&2
  exit 1
fi

command_name="$1"
base_url="$2"
api_key="$3"
model="${4:-opus[1m]}"

suffix="$command_name"
if [[ "$command_name" == claude* ]]; then
  suffix="${command_name#claude}"
elif [[ "$command_name" == cluade* ]]; then
  suffix="${command_name#cluade}"
fi
[[ -n "$suffix" ]] || suffix="custom"

profile_dir="$HOME/.claude_${suffix}"
shared_dir="$HOME/.claude"
zshrc="$HOME/.zshrc"

mkdir -p "$profile_dir" "$profile_dir/backups" "$shared_dir/sessions" "$shared_dir/projects" "$shared_dir/session-env"
[[ -f "$shared_dir/history.jsonl" ]] || : > "$shared_dir/history.jsonl"

zshrc_backup="$HOME/.zshrc.backup.${command_name}.$(date +%Y%m%d%H%M%S)"
cp "$zshrc" "$zshrc_backup"

python3 - "$zshrc" "$command_name" "$profile_dir" <<'PY'
import pathlib, re, sys
zshrc = pathlib.Path(sys.argv[1])
command_name = sys.argv[2]
profile_dir = sys.argv[3]
text = zshrc.read_text()
start = f"# BEGIN claude-profile-provisioner:{command_name}"
end = f"# END claude-profile-provisioner:{command_name}"
block = f'''{start}\n{command_name} () {{\n  unset ANTHROPIC_AUTH_TOKEN ANTHROPIC_API_KEY ANTHROPIC_BASE_URL ANTHROPIC_MODEL\n  export CLAUDE_CONFIG_DIR=\"{profile_dir}\"\n  \"$_claude_bin\" --setting-sources=user \"$@\"\n}}\n{end}\n'''
pattern = re.compile(re.escape(start) + r"\\n.*?" + re.escape(end) + r"\\n?", re.S)
if pattern.search(text):
    text = pattern.sub(block, text)
else:
    if not text.endswith("\n"):
        text += "\n"
    text += "\n" + block
zshrc.write_text(text)
PY

cat > "$profile_dir/settings.json" <<EOF2
{
  "env": {
    "ANTHROPIC_BASE_URL": "$base_url",
    "ANTHROPIC_AUTH_TOKEN": "$api_key"
  },
  "permissions": {
    "defaultMode": "bypassPermissions"
  },
  "model": "$model",
  "fastMode": true,
  "skipDangerousModePermissionPrompt": true,
  "autoUpdates": false
}
EOF2

python3 - "$profile_dir" "$shared_dir" <<'PY'
import filecmp, json, os, pathlib, shutil, sys, time
profile = pathlib.Path(sys.argv[1])
shared = pathlib.Path(sys.argv[2])
backup_root = profile / 'backups' / f'provision-{int(time.time()*1000)}'
backup_root.mkdir(parents=True, exist_ok=True)

static_items = ['CLAUDE.md', 'agents', 'commands', 'docs', 'memory', 'rules', 'skills', 'plugins']
resume_items = ['sessions', 'history.jsonl', 'projects', 'session-env']

# Merge any existing local resume data into shared store before linking.
local_sessions = profile / 'sessions'
if local_sessions.is_dir() and not local_sessions.is_symlink():
    for src in local_sessions.glob('*.json'):
        dst = shared / 'sessions' / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
        elif not filecmp.cmp(src, dst, shallow=False):
            shutil.copy2(src, shared / 'sessions' / f'{profile.name}-{src.name}')

local_projects = profile / 'projects'
if local_projects.is_dir() and not local_projects.is_symlink():
    for src in local_projects.rglob('*'):
        rel = src.relative_to(local_projects)
        dst = shared / 'projects' / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or src.stat().st_mtime > dst.stat().st_mtime:
            shutil.copy2(src, dst)

local_senv = profile / 'session-env'
if local_senv.is_dir() and not local_senv.is_symlink():
    for src in local_senv.rglob('*'):
        rel = src.relative_to(local_senv)
        dst = shared / 'session-env' / rel
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            shutil.copy2(src, dst)

local_history = profile / 'history.jsonl'
shared_history = shared / 'history.jsonl'
if local_history.exists() and not local_history.is_symlink():
    seen = set()
    merged = []
    for hist in [shared_history, local_history]:
        with hist.open('r', encoding='utf-8', errors='replace') as f:
            for raw in f:
                line = raw.rstrip('\n')
                if line and line not in seen:
                    seen.add(line)
                    merged.append(line)
    with shared_history.open('w', encoding='utf-8') as f:
        for line in merged:
            f.write(line + '\n')

for name in static_items + resume_items:
    dst = profile / name
    src = shared / name
    if dst.is_symlink():
        if os.readlink(dst) == str(src):
            continue
        dst.unlink()
    elif dst.exists():
        shutil.move(str(dst), str(backup_root / name))
    dst.symlink_to(src)
PY

python3 - "$profile_dir/.claude.json" <<'PY'
import glob, json, os, pathlib, shutil, time, sys
out_path = pathlib.Path(sys.argv[1])
if out_path.exists():
    backup = out_path.parent / 'backups' / f'.claude.json.backup.{int(time.time()*1000)}'
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(out_path, backup)
    data = json.load(open(out_path, 'r', encoding='utf-8'))
else:
    data = {}
merged = {}
for path in sorted(glob.glob(os.path.expanduser('~/.claude_*'))):
    src = pathlib.Path(path) / '.claude.json'
    if not src.exists():
        continue
    try:
        payload = json.load(open(src, 'r', encoding='utf-8'))
    except Exception:
        continue
    merged.update(payload.get('mcpServers', {}))
if merged:
    current = data.get('mcpServers', {})
    current.update(merged)
    data['mcpServers'] = current
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write('\n')
print('mcpServers=' + ','.join(sorted(data.get('mcpServers', {}).keys())))
PY

printf 'command=%s\n' "$command_name"
printf 'profile_dir=%s\n' "$profile_dir"
printf 'zshrc_backup=%s\n' "$zshrc_backup"
zsh -ic "which $command_name"
zsh -ic "$command_name --version"
