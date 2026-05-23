---
description: 接管最近或指定的 AI 颗粒
argument-hint: "[session-or-cli]"
allowed-tools: ["Bash(/Users/yangjingchi/.config/agents/skills/tmux-coding-agent/scripts/session-shortcuts.py takeover:*)"]
model: haiku
---

接管当前工作目录里最近的颗粒；如果提供参数，则接管匹配的 session 名或 CLI 名。

示例：
- `/takeover`
- `/takeover claudecodex`
- `/takeover reviewer`

```!
/Users/yangjingchi/.config/agents/skills/tmux-coding-agent/scripts/session-shortcuts.py takeover $ARGUMENTS
```
