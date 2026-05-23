#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$SCRIPT_DIR/skills_全量备份"
DST_CONFIG="$HOME/.config/agents/skills"
DST_CLAUDE="$HOME/.claude/skills"

mkdir -p "$DST_CONFIG" "$DST_CLAUDE"
count=0
for skill_dir in "$SRC"/*/; do
  name=$(basename "$skill_dir")
  rm -rf "$DST_CONFIG/$name"
  cp -R "$skill_dir" "$DST_CONFIG/$name"
  # 在 ~/.claude/skills 建立软链，让 4 个 channel 都看得到
  rm -f "$DST_CLAUDE/$name"
  ln -s "$DST_CONFIG/$name" "$DST_CLAUDE/$name"
  count=$((count+1))
  echo "  ✅ $name"
done
echo "---"
echo "✅ 共安装 $count 个 skill 到 $DST_CONFIG 并软链到 $DST_CLAUDE"
