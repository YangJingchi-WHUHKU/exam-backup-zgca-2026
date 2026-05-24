#!/bin/bash
# Claude Code 回复美化阅读器
# 在独立 tmux 窗格运行，自动监听 ~/.claude/projects 下最新 transcript，提取最后一条 assistant 回复并用 glow 渲染
# 跨平台：macOS / Linux

PROJECTS_DIR="$HOME/.claude/projects"
LAST_HASH=""

# 跨平台 md5
if command -v md5sum >/dev/null 2>&1; then
    HASH_CMD="md5sum"
elif command -v md5 >/dev/null 2>&1; then
    HASH_CMD="md5"
else
    echo "❌ 找不到 md5/md5sum"
    exit 1
fi

if ! command -v glow >/dev/null 2>&1; then
    echo "❌ glow 未安装。macOS: brew install glow  |  Linux: 见 README.md"
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ python3 未安装"
    exit 1
fi

if [ ! -d "$PROJECTS_DIR" ]; then
    echo "❌ $PROJECTS_DIR 不存在 — 先运行一次 Claude Code 生成会话记录"
    exit 1
fi

echo "👁  监听 Claude 回复中... (Ctrl+C 退出)"

while true; do
    LATEST=$(ls -t "$PROJECTS_DIR"/*/*.jsonl 2>/dev/null | head -1)
    if [ -n "$LATEST" ] && [ -f "$LATEST" ]; then
        TEXT=$(python3 - "$LATEST" <<'PYEOF'
import json, sys
path = sys.argv[1]
try:
    with open(path) as f:
        lines = f.readlines()
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            if msg.get("type") == "assistant":
                content = msg.get("message", {}).get("content", "")
                if isinstance(content, list):
                    text = "".join(
                        c.get("text", "")
                        for c in content
                        if isinstance(c, dict) and c.get("type") == "text"
                    )
                else:
                    text = str(content)
                if text.strip():
                    print(text)
                    break
        except:
            continue
except:
    pass
PYEOF
)
        HASH=$(echo "$TEXT" | head -c 200 | $HASH_CMD | awk '{print $1}')
        if [ "$HASH" != "$LAST_HASH" ] && [ -n "$TEXT" ]; then
            LAST_HASH="$HASH"
            echo "$TEXT" > /tmp/claude-response.md
            clear
            glow /tmp/claude-response.md
            echo ""
            echo "────────────────────────────────"
            echo "  上次更新: $(date '+%H:%M:%S')"
        fi
    fi
    sleep 1
done
