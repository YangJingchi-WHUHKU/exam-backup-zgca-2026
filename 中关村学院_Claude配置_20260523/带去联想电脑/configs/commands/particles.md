---
description: 查看当前目录里的 tmux AI 颗粒
argument-hint: "[name-or-cli]"
allowed-tools: ["Bash(/Users/yangjingchi/.config/agents/skills/tmux-coding-agent/scripts/session-shortcuts.py list:*)"]
model: haiku
---

列出当前工作目录里由 `tmux-coding-agent` 启动的活跃颗粒。若提供参数，则按 session 名或 CLI 名过滤。

```!
/Users/yangjingchi/.config/agents/skills/tmux-coding-agent/scripts/session-shortcuts.py list $ARGUMENTS
```
