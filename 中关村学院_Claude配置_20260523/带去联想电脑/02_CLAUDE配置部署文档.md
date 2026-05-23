# Claude 配置部署文档（联想笔记本落地版）

> 目标机器：学校发的联想笔记本
> 准备日期：2026-05-23
> 关键约束：考场只能用国内可达的 channel；4 个 channel **全部走国内反代**，预期可通

---

## 一、4 个可用的 Claude Code Channel（核心资产）

> ⚠️ 不要把这份文档上传任何在线笔记 / Github / Slack。U 盘加密带过去。

| Channel 命令 | Base URL | API Key | Model |
|------|------|------|------|
| `claudeaipai` | `https://api.aipaibox.com/` | `sk-N8c1EnaseEaN8GVJkDmVybSPlghJ7G5FQZMFcTKZmRoHjVML` | `opus[1m]` |
| `claudemicu` | `https://www.micuapi.ai` | `sk-PaBaIPnh3zasiuPmzW9xohKKfueW6ykRd03sPwFwHXxthXbC` | `opus[1m]` |
| `claudecodesuc` | `https://main-new.codesuc.top/` | `sk-n5LlW8Pm21b1ENgSCMH0Muvx6ee...` *(完整 key 在 configs/profile_bundle/profiles.json)* | `opus[1m]` |
| `claudeswarm` | `https://byteswarm.ai/claude` | `cr_9vb-z9nLfpKJEwSzbFTTfnADxzP...` *(完整 key 在 profiles.json)* | `opus[1m]` |

**冗余设计**：1 个挂了用另外 3 个。考场关键时刻一个不能丢。

**Resume 共享**：4 个 channel 共享 `~/.claude` 主目录的 skills / memory / plugins / sessions，`/resume` 可跨 channel 切换。`profile_bundle/install.sh` 自动配置。

> 注：旧 bundle 里的 `claudeterminal` 已不在你这次的选用名单中，已移除。

---

## 二、configs/ 目录内容（已打包）

| 文件/目录 | 作用 |
|------|------|
| `settings.json` | 全局设置：opus[1m]、bypassPermissions、high effort |
| `CLAUDE.md` | 全局个性化指令（已用本机版本，可在新机覆盖 ~/.claude/CLAUDE.md） |
| `rules/` | behaviors / memory-flush / skill-triggers |
| `docs/` | agents / content-safety / behaviors-* |
| `commands/` | 自定义命令（agent-dashboard / particles / watch-agent / takeover） |
| `mcp_servers.json` | **只保留 codex MCP**（本地调用，无外网依赖） |
| `profile_bundle/` | 4 channel 一键安装包（含 profiles.json + install.sh） |

> ⚠️ **memory 已清空** — 不带任何长期记忆，进考场用干净大脑。
> 复刻的 CLAUDE.md 含你的工作偏好/SSOT 路由表，但**不含**任何项目/学术敏感记忆。

---

## 三、MCP 配置（仅 codex）

外网 MCP 全部移除：~~tavily-search / serper-search / exa~~（考场不可用）

保留：
- **codex** — 本地 Codex CLI 调用 MCP，无需外网，可让 Claude 调本地 codex 做协同验证

如联想笔记本本身没装 `codex` CLI，需要先：
```bash
# 安装 codex CLI（如可联网）
brew install codex  # 或对应平台命令
```
若装不上 codex，MCP 不启用即可，**不影响主流程**。

---

## 四、部署 SOP（到联想电脑后）

### 4.1 前置
- Node.js ≥ 18
- zsh 或 bash
- 能访问 `npmjs.org`（不能就提前 `npm pack @anthropic-ai/claude-code` 离线带）

### 4.2 安装 Claude Code
```bash
npm install -g @anthropic-ai/claude-code
# 或离线：npm install -g ./anthropic-ai-claude-code-X.Y.Z.tgz
```

### 4.3 跑 profile bundle（**关键**）
```bash
cd 带去联想电脑/configs/profile_bundle
chmod +x install.sh
./install.sh
source ~/.zshrc  # 或 source ~/.bashrc
```

完成后 4 个命令可用：
```
claudeaipai
claudemicu
claudecodesuc
claudeswarm
```

### 4.4 复制 settings 等
```bash
cd 带去联想电脑/configs
mkdir -p ~/.claude
cp settings.json ~/.claude/
cp CLAUDE.md ~/.claude/
cp -r rules ~/.claude/
cp -r docs ~/.claude/
cp -r commands ~/.claude/
# 注意：不复制 memory（清空状态进考场）
```

### 4.5 安装 31 个 skill
```bash
cd 带去联想电脑
bash install_skills.sh
```
这会：
1. 把 skills 复制到 `~/.config/agents/skills/`
2. 在 `~/.claude/skills/` 建软链，让 4 个 channel 都看得到

### 4.6 配置 codex MCP（可选）
```bash
# 把 configs/mcp_servers.json 的 mcpServers 字段并入 ~/.claude.json
python3 -c "
import json, os
main = json.load(open(os.path.expanduser('~/.claude.json')))
add = json.load(open('configs/mcp_servers.json'))
main.setdefault('mcpServers', {}).update(add['mcpServers'])
json.dump(main, open(os.path.expanduser('~/.claude.json'),'w'), indent=2)
"
```

### 4.7 验证
```bash
claudeaipai
> 看一下你能用几个 skill？现在用的什么 model？
```
应返回：**31 skills, model=opus[1m]**。

试切 channel：
```bash
claudemicu     # 同一 session 历史可通过 /resume 调回
```

---

## 五、网络受限时的应急

如果 4 个 channel 全部不通：
1. `curl -I https://api.aipaibox.com/` 看具体哪个不通
2. 联想笔记本可能默认走学校代理 → 设环境变量：
   ```bash
   export HTTPS_PROXY=http://校园代理:端口
   ```
3. 都不行 → Claude 用不了，**skill 里的算法模板仍可作本地参考**让其他 AI（通义/Kimi）用

---

## 六、考场注意

- **机考期间**：Claude 用不了（生成式 AI 禁用）。**关闭所有联网 client**。违规取消成绩。
- **科研实训当天**：到了再确认学院是否认 Claude 为"国内 AI"——4 个 channel 走的都是国内反代 URL，**严格说应该算"国内 AI 服务"**。
- **time 同步**：让联想笔记本时间和本机时间一致，避免 token 鉴权失败。

---

## 七、打包文件清单

```
带去联想电脑/
├── 01_SKILLS_清单与推荐.md          # skill 分类与推荐
├── 02_CLAUDE配置部署文档.md         # 本文件
├── 03_考试用claude.md               # 科研实训四范式速查
├── install_skills.sh                # skill 一键安装脚本
├── configs/
│   ├── settings.json
│   ├── CLAUDE.md
│   ├── mcp_servers.json
│   ├── rules/
│   ├── docs/
│   ├── commands/
│   └── profile_bundle/              # 4 channel 一键安装
│       ├── install.sh
│       ├── profiles.json            # ← 4 channel 完整配置
│       ├── README.md
│       └── skills/claude-profile-provisioner/
└── skills_全量备份/                 # 31 个 skill
```

---

*最后更新：2026-05-23 杨镜池 临行前*
