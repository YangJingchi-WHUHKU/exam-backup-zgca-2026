#!/usr/bin/env bash
# ============================================================
# MCP 搜索工具一键安装（联想Linux，无sudo）
# bing-cn-mcp (无需API key，国内直接用)
# serper / tavily (需外网)
# ============================================================
set -e

echo "=== Step 1: 确保 Node / npm 可用 ==="
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
node -v && npm -v || { echo "❌ Node未安装，先跑 install_all.sh"; exit 1; }

echo "=== Step 2: 设置国内镜像 ==="
npm config set registry https://registry.npmmirror.com

echo "=== Step 3: 安装 bing-cn-mcp（无需API key）==="
npm install -g bing-cn-mcp
echo "✅ bing-cn-mcp 安装完成"

echo "=== Step 4: 写入 MCP 配置到 ~/.claude.json ==="
python3 - << 'PYEOF'
import json, os

claude_json = os.path.expanduser("~/.claude.json")

# 读现有配置（如果有）
data = {}
if os.path.exists(claude_json):
    with open(claude_json) as f:
        try:
            data = json.load(f)
        except:
            data = {}

# 写入MCP配置
data['mcpServers'] = {
    "bing-search": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "bing-cn-mcp"]
    },
    "serper-search": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "serper-search-scrape-mcp-server"],
        "env": {
            "SERPER_API_KEY": "0538ec60fad4b78e87ce48e15ab9f93491ebe9de"
        }
    },
    "tavily-search": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "tavily-mcp"],
        "env": {
            "TAVILY_API_KEY": "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"
        }
    }
}

with open(claude_json, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("✅ ~/.claude.json MCP配置写入完成")
PYEOF

echo ""
echo "============================================"
echo "  ✅ MCP 安装完成"
echo "============================================"
echo ""
echo "可用搜索工具："
echo "  bing-search    ← 必应中文，国内直接用，无需API key ✅"
echo "  serper-search  ← Google搜索，需外网（代理）"
echo "  tavily-search  ← AI搜索，需外网（代理）"
echo ""
echo "重启 claudezgc 后生效（关闭重新开）"
echo ""
