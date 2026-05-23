# MCP 搜索工具配置

## 三个搜索MCP

| MCP | 能否在国内用 | API Key | 用途 |
|-----|------------|---------|------|
| **bing-search** | ✅ 直接用 | 无需 | 必应中文搜索，GitHub/CSDN/贴吧都能搜 |
| serper-search | ⚠️ 需外网 | `0538ec60fad4b78e87ce48e15ab9f93491ebe9de` | Google搜索+网页抓取 |
| tavily-search | ⚠️ 需外网 | `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` | AI优化搜索 |

## 安装方法

```bash
bash /media/$USER/DADAGAGA/install_mcp.sh
```

## 手动配置（如果脚本失败）

在 `~/.claude.json` 的 `mcpServers` 里加：

```json
{
  "mcpServers": {
    "bing-search": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "bing-cn-mcp"]
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
    }
  }
}
```

## 注意
- `bing-search` 在中国网络下搜索 GitHub/CSDN/贴吧没问题
- Reddit / Twitter 在中国访问不了，需要外网代理
- MCP 需要重启 claude session 才生效
