# Claude Code × Codex 共享记忆桥

> 这是**已有**机制的架构说明，不是新功能。撰写于 2026-04-18，用于未来维护和排错。

---

## 一句话总结

Claude Code 和所有 Codex CLI wrapper（codex / codexa / codexb / codexc / codexbb / codexduck）都把**记忆的 SSOT 指向同一个目录** `~/.claude/memory/`。两边读写同一批 Markdown / JSON 文件——这就是"互通"的全部。没有特殊协议，没有私有 API。

---

## 三层结构

```
┌───────────────────────────────────────────────────────────────┐
│  层 1  SSOT 文件（人类可读，两边都用）                         │
│  ~/.claude/memory/                                            │
│    ├── today.md            ← 当天进展（hot data）             │
│    ├── active-tasks.json   ← 跨 session 的 in-flight task     │
│    ├── patterns.md         ← 可复用的 pattern / pitfall 库    │
│    ├── projects.md         ← 跨项目状态概览                   │
│    └── goals.md            ← 长期目标                         │
│  每个项目下还有：                                              │
│    <project>/PROJECT_CONTEXT.md  ← 项目级 SSOT                │
│    <project>/CLAUDE.md           ← 项目级指令                 │
└───────────────────────────────────────────────────────────────┘
                  ↑                           ↑
                  │                           │
       ┌──────────┴─────────┐       ┌─────────┴──────────┐
       │  层 2a  Claude     │       │  层 2b  Codex      │
       │  Code 读取路径     │       │  hooks 读写路径    │
       └────────────────────┘       └────────────────────┘

Claude Code:                        Codex CLI:
  ~/.claude/CLAUDE.md                ~/.codex/hooks.json
  （全局指令，里面引用            （注册 3 个 hook，都执行
    memory/ 下各个文件）             ~/.claude/ 外的共享脚本）
                                    │
                                    ├── SessionStart
                                    │     ~/.codex/hooks/session_start.py
                                    │     → 读 today.md + PROJECT_CONTEXT.md
                                    │     → 作为 additionalContext 注入
                                    │
                                    ├── UserPromptSubmit
                                    │     ~/.codex/hooks/user_prompt_submit.py
                                    │     → 写 today.md 新条目
                                    │     → 记录 session/turn state
                                    │
                                    └── Stop
                                          ~/.codex/hooks/stop_writeback.py
                                          → 写回进展/下一步到 today.md
                                          → 写回 active-tasks.json
                                          → 写回 PROJECT_CONTEXT.md handoff 块
```

---

## 层 3：为什么不同 CLI wrapper 也共享

关键在 `.zshrc` 里的 wrapper 定义——**全部把 `CODEX_HOME` 设成 `$HOME/.codex`**：

```zsh
codex     → codex-account-switch default → CODEX_HOME=~/.codex
codexa    → codex-account-switch a       → CODEX_HOME=~/.codex
codexb    → codex-account-switch b       → CODEX_HOME=~/.codex
codexc    → codex-account-switch c       → CODEX_HOME=~/.codex
codexbb   → CODEX_HOME=~/.codex command codex -c model_provider=codexbb ...
codexduck → CODEX_HOME=~/.codex command codex -c model_provider=duckcoding ...
```

三个历史遗留的 `CODEX_HOME` 目录（`.codex`、`.codex_duck`、`.codex_bb`）现在都有 `hooks.json`，**全部指向同一组 Python 脚本**（`/Users/yangjingchi/.codex/hooks/*.py`）。即使将来某个 wrapper 的 `CODEX_HOME` 不小心被指回 `.codex_duck` 或 `.codex_bb`，它触发的 hooks 依然读写 `~/.claude/memory/`，共享语义不会被破坏。

---

## 读写行为细节

### 写入是实时的（每轮都写）

- `UserPromptSubmit`：用户按回车的一瞬间，在 `today.md` 追加一个 session header（`### SN (~HH:MM) [project] Working on XXX...`）
- `Stop`：本轮 assistant 输出完后，用正则从输出里提取"进展"和"下一步"，回写到同一个 session block
- 同一轮 prompt 会在 `today.md` 里从"已启动"→"进展：XXX"→"下一步：YYY" 三段式演化

### 读取是**启动一次**的

- `SessionStart` 在 `startup` 和 `resume` 时各触发一次，把 `today.md` 相关条目 + `PROJECT_CONTEXT.md` 的 handoff 块作为 `additionalContext` 注入 context
- **一旦 session 开始，hook 不会再读 `today.md`**。所以 codex A 会话活着的时候，codex B 写了新条目，A 要等下次恢复才能看到

### Claude Code 侧

- Claude Code 启动时自动加载 `~/.claude/CLAUDE.md`，里面又通过 `Contents of ...` 机制把 `memory/MEMORY.md` 索引到的文件读进来
- 对 `today.md` 和 `active-tasks.json` 是 on-demand 读取（有需要时用 Read 工具）

---

## 关键文件速查

| 位置 | 作用 |
|------|------|
| `~/.claude/memory/today.md` | 当天所有 session 的增量进展 |
| `~/.claude/memory/active-tasks.json` | 跨 session 的 in-flight 任务注册表 |
| `~/.claude/memory/patterns.md` | 反复踩坑后沉淀的 pattern 库 |
| `~/.claude/CLAUDE.md` | 全局指令，Claude Code 自动加载 |
| `~/.codex/hooks.json` | Codex 的 hook 注册（SessionStart/UserPromptSubmit/Stop） |
| `~/.codex/hooks/session_start.py` | 把 `.claude/memory` 的内容注入 Codex session |
| `~/.codex/hooks/shared_memory.py` | 读写 today.md / active-tasks.json 的工具库 |
| `~/.codex/hooks/stop_writeback.py` | 每轮回写进展到 today.md 和 PROJECT_CONTEXT.md |
| `~/.codex_duck/hooks.json` | 镜像主 hooks（指向 ~/.codex/hooks/*.py） |
| `~/.codex_bb/hooks.json` | 同上 |
| `~/.local/bin/codex-account-switch` | CLI wrapper 的统一入口，保证 CODEX_HOME 统一 |
| `~/.local/bin/codex-unified-resume` | 共享 /resume 入口，查 `~/.codex/state_5.sqlite` |

---

## 验证清单

怀疑互通断了，依次验证：

```bash
# 1. hooks.json 是否都指向共享脚本
for d in ~/.codex ~/.codex_duck ~/.codex_bb; do
  echo "=== $d/hooks.json ==="
  cat "$d/hooks.json" | grep command
done
# 期望：三套 hooks.json 的 command 路径都是 /Users/yangjingchi/.codex/hooks/*.py

# 2. today.md 是否被当前活跃 session 实时写
stat -f "%Sm %N" ~/.claude/memory/today.md
# 期望：mtime 接近 "now"；tail today.md 能看到最近几分钟的 session block

# 3. 所有 wrapper 的 CODEX_HOME 都指向 ~/.codex
grep -nE 'CODEX_HOME' ~/.zshrc
# 期望：全是 CODEX_HOME="$HOME/.codex"，没有 .codex_duck / .codex_bb

# 4. SessionStart hook 能读到 .claude
python3 -c "
import os, sys
os.chdir('/tmp')  # 非项目目录，触发 shell/CLI 模式
sys.path.insert(0, '/Users/yangjingchi/.codex/hooks')
import json
from session_start import build_context
print(build_context({'cwd': '/tmp', 'source': 'startup'}))
"
# 期望：输出 "Shared Claude memory bridge active for startup." 及相关内容
```

---

## 常见误解

**❌ "Codex 记忆被清空了"**
→ 通常指的是 Codex.app 侧边栏显示的**线程列表**变少了，不是 `~/.claude/memory/` 文件夹没内容。两件事要分开。

**❌ "CLI 之间不互通"**
→ 如果 `today.md` 在实时被写入，就是通的。误判往往是因为 A session 活着时看不到 B session 的增量——这是读取机制（SessionStart 一次性）决定的，不是不通。

**❌ "要靠改 app.asar 实现互通"**
→ 不需要。app.asar 的补丁只影响 Codex.app 侧边栏展示哪些线程，跟记忆完全无关。改 asar 还会被 code signing / Electron integrity 校验拒绝加载，风险很大。

---

## 已知限制

1. **跨 session 读取不实时**：A 和 B 同时活着时，A 感知不到 B 刚写到 `today.md` 的新内容，要等 A 重启/恢复。修法：改 `user_prompt_submit.py`，每轮额外注入 today.md 最新片段。（暂未实施）
2. **session_index.jsonl 有滞后**：Codex.app 侧边栏的一些元数据从这个文件读，它不是每轮更新，落后几十分钟很常见。不影响记忆内容本身。
3. **Codex.app 侧边栏默认只显示当前 provider 的线程**：这是 App 前端写死的 `modelProviders:null`，和记忆系统无关。要让 App 看到所有 CLI 线程要改 asar，但有代码签名风险，当前放弃该路线。

---

## 历史背景（防止重踩坑）

- 曾经有过 `codex-retag-provider-view` 脚本，按 cwd 批量改 `state_5.sqlite` 的 `model_provider`，会破坏线程 provider 归属。**该脚本已改成 no-op**，但旧的 `shell_snapshots/` 里残影还在，不会被新线程执行。
- 曾经 `~/.codex_duck/` 和 `~/.codex_bb/` 各有独立 SQLite store，导致三套数据割裂。现在 wrapper 全部指向 `~/.codex`，另外两个目录变成冷备。
- 曾经试过改 `/Applications/Codex.app/Contents/Resources/app.asar` 让侧边栏显示所有 provider，打补丁两次都把 App 搞崩（2026-04-18），原因是 Electron 的 asar integrity 校验会拒绝改过的 asar。**当前放弃该路线**。
