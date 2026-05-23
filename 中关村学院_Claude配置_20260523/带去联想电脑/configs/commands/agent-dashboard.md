---
description: 打开当前目录颗粒总控台
argument-hint: "[session-or-cli]"
allowed-tools: ["Bash(/Users/yangjingchi/.config/agents/skills/tmux-coding-agent/scripts/session-shortcuts.py dashboard:*)"]
model: haiku
---

打开当前工作目录里颗粒对应的 Dashboard。若提供参数，则优先用匹配的颗粒来定位 socket；不提供则默认最近颗粒。

示例：
- `/agent-dashboard`
- `/agent-dashboard claudecodex`

```!
/Users/yangjingchi/.config/agents/skills/tmux-coding-agent/scripts/session-shortcuts.py dashboard $ARGUMENTS
```
