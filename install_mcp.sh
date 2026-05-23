#!/usr/bin/env bash
# MCP 搜索工具一键安装（联想Linux，无sudo）
set -e

echo "=== 确保 Node/npm 可用 ==="
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
node -v && npm -v || { echo "❌ 先跑 install_all.sh"; exit 1; }

echo "=== 设置国内镜像 ==="
npm config set registry https://registry.npmmirror.com

echo "=== 安装 MCP 包 ==="
npm install -g bing-cn-mcp
npm install -g mcp-baidu-search-demo

echo "=== 写入 ~/.claude.json MCP配置 ==="
EXA_KEY="${1:-e2b96aa7-37de-4081-85f7-357ca7a3ebb2}"  # 可以传参数: bash install_mcp.sh 你的exa_key

python3 - "$EXA_KEY" << 'PYEOF'
import json, os, sys

exa_key = sys.argv[1] if len(sys.argv) > 1 else "e2b96aa7-37de-4081-85f7-357ca7a3ebb2"
p = os.path.expanduser("~/.claude.json")
data = {}
if os.path.exists(p):
    with open(p) as f:
        try: data = json.load(f)
        except: data = {}

data['mcpServers'] = {
    "bing-search": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "bing-cn-mcp"]
    },
    "baidu-search": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "mcp-baidu-search-demo"]
    },
    "serper-search": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "serper-search-scrape-mcp-server"],
        "env": {"SERPER_API_KEY": "0538ec60fad4b78e87ce48e15ab9f93491ebe9de"}
    },
    "tavily-search": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "tavily-mcp"],
        "env": {"TAVILY_API_KEY": "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"}
    },
    "exa": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "exa-mcp-server"],
        "env": {"EXA_API_KEY": exa_key}
    }
}

with open(p, 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print("✅ ~/.claude.json 写入完成")
PYEOF

echo ""
echo "============================================"
echo "  ✅ MCP 安装完成（重启 claudezgc 生效）"
echo "============================================"
echo ""
echo "  bing-search    ✅ 必应中文，无需API key，国内直接用"
echo "  baidu-search   ✅ 百度搜索，无需API key，国内直接用"
echo "  serper-search  ⚠️  Google，需外网（代理）"
echo "  tavily-search  ⚠️  AI搜索，需外网（代理）"
echo "  exa            ⚠️  需外网 + 填入exa.ai的key"
echo ""
echo "如果有exa key，用法："
echo "  bash install_mcp.sh <你的exa_api_key>"
echo ""
