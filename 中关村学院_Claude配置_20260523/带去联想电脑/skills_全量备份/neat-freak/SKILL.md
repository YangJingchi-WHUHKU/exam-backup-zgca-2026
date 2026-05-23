---
name: neat-freak
description: >
  End-of-task knowledge cleanup and handoff for Claude/Codex shared-memory projects.
  Use when the user says /neat, 洁癖, 整理上下文, 总结上下文, 阶段存档, 更新记忆,
  同步文档, 收尾, 这个阶段做完了, 新 session 接, 不想 resume, handoff, or asks
  to make future agents continue without relying on the current chat history.
  The skill reconciles PROJECT_CONTEXT.md, CLAUDE.md/AGENTS.md, README/docs,
  and ~/.claude/memory files so stale project knowledge is merged or removed.
metadata:
  upstream: "KKKKhazix/khazix-skills neat-freak, adapted for yangjingchi shared Claude-Codex memory bridge"
---

# Neat Freak — 阶段存档与知识库洁癖

你是项目知识库编辑，不是聊天记录员。目标是把当前阶段的真实状态沉淀到持久文件，让下个 Claude/Codex session 可以直接接任务，而不是依赖长 resume。

核心原则：
- **合并优于追加**：新事实更新旧条目，不平铺堆历史。
- **删除优于保留**：过期、重复、已完成的临时待办要移除或压缩。
- **绝对时间**：写 `2026-04-30`，不写“今天/刚才/最近”。
- **分层写入**：不同受众的信息写到不同文件，不混用。

## 本机 SSOT 路由

优先读写这些位置。详细规则见 `references/local-memory-routing.md`。

| 信息 | 写入位置 |
|---|---|
| 项目战略状态、下一阶段 handoff | 项目根 `PROJECT_CONTEXT.md` |
| 项目 AI 约定、红线、目录路由 | 项目根 `CLAUDE.md` / `AGENTS.md` |
| 人类/下游可读说明 | `README.md`、`docs/**/*.md` |
| 当日临时进展 | `/Users/yangjingchi/.claude/memory/today.md` |
| 跨项目 in-flight 任务 | `/Users/yangjingchi/.claude/memory/active-tasks.json` |
| 可复用踩坑/纠偏模式 | `/Users/yangjingchi/.claude/memory/patterns.md` |

不要把项目战略状态写进 `today.md` 当长期 SSOT；不要把一次性流水账写进 `CLAUDE.md`。

## 执行流程

### 1. 盘点

先机械枚举，再判断要不要改：

```bash
pwd
find . -maxdepth 3 \( -name 'README*' -o -name 'CLAUDE.md' -o -name 'AGENTS.md' -o -name 'PROJECT_CONTEXT.md' -o -path './docs/*.md' -o -path './memory/*.md' \) -not -path '*/.git/*' -not -path '*/node_modules/*' | sort
git status --short
```

同时按需读：
- 最近的 `CLAUDE.md` / `AGENTS.md`
- 最近的 `PROJECT_CONTEXT.md`
- `README.md`、`docs/**/*.md`
- `/Users/yangjingchi/.claude/memory/today.md` 尾部
- `/Users/yangjingchi/.claude/memory/patterns.md`，仅在用户纠正、重复失败、调试或抽取可复用经验时读写

### 2. 判断影响面

不要只总结对话，要判断“哪些持久文件现在会误导下个 agent”。不确定时查 `references/sync-matrix.md`。

重点检查：
- 新增/改名命令、脚本、数据流、API、环境变量、端口、模型、评测入口
- 项目边界或研究口径是否变了
- 用户纠正过的技术假设是否需要写入 `patterns.md`
- 是否跨项目；若上游变化影响下游文档，两边都要同步

### 3. 修改顺序

按这个顺序编辑，保持可恢复：

1. `docs/`、`README.md`：人类和下游最容易被旧文档误导，先改。
2. `CLAUDE.md` / `AGENTS.md`：只写长期有效的 agent 规则、项目约定、目录路由。
3. `PROJECT_CONTEXT.md`：更新“当前状态 / 已完成 / 未完成 / 下一步 / 交接提示”。大文件只改相关块，不全文重写。
4. `.claude/memory/*`：只在信息属于全局记忆层时写入。`patterns.md` 必须满足本机 AGENTS 里的触发条件。

编辑前读原文件，避免覆盖用户已有改动。大段删除、改全局规则、改 secrets 相关文件前先向用户确认。

### 4. 自检

完成前逐项确认：
- 所有盘点出的关键 md 都已判断“要改/不用改”。
- `PROJECT_CONTEXT.md` 的下一步能让新 session 直接开工。
- `CLAUDE.md` / `AGENTS.md` 没有临时流水账。
- README/docs 的命令、路径、端口、环境变量与当前文件状态一致。
- 没有遗留“今天/昨天/最近/刚才/today/recently”等相对时间。
- 没有暴露密钥、token、cookie、私有 URL。
- 如果声称完成了验证，必须有真实命令输出支撑。

### 5. 输出

最后只给用户高信号摘要：

```text
已完成 /neat：
- 更新了哪些文件
- 删除或合并了哪些过期信息
- 下个 session 会从哪里接上
- 仍需用户决定的问题
```

如果没有实际修改，也要说明“已审查但无需改动”的依据。

## 和 session-end 的关系

`session-end` 偏“下班收尾”：today、active-tasks、handoff、可选 commit。
`neat-freak` 偏“知识库洁癖”：全局审查 docs / project context / agent 指令 / shared memory 的一致性。

阶段性大任务结束、resume 变重、文档可能过期时，用 `neat-freak`。只是退出窗口且无新增知识时，用 `session-end` 即可。
