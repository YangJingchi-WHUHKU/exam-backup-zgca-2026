---
description: 打开最近或指定颗粒的只读监控页
argument-hint: "[session-or-cli]"
allowed-tools: ["Bash(/Users/yangjingchi/.config/agents/skills/tmux-coding-agent/scripts/session-shortcuts.py watch:*)"]
model: haiku
---

打开当前工作目录里最近的颗粒监控页；如果提供参数，则打开匹配的 session 名或 CLI 名。

示例：
- `/watch-agent`
- `/watch-agent claude`
- `/watch-agent codex-worker`

```!
/Users/yangjingchi/.config/agents/skills/tmux-coding-agent/scripts/session-shortcuts.py watch $ARGUMENTS
```
