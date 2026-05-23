# Claude Profile Bundle

这个包用于在一台已经装好 Claude Code 且已有基础 profile 的电脑上，追加安装：

- `claude-profile-provisioner` skill
- `claudeaipai`
- `claudemicu`
- `claudeterminal`

## 适用前提

- 对方电脑已经能正常运行 `claude` 或同类 Claude Code 包装命令
- 对方使用 `zsh`
- 对方已有 `~/.claude` 主目录
- 对方的 `~/.zshrc` 里已经有 `_claude_bin` 这一类基础 Claude 启动配置

## 安装内容

- 安装 skill 到 `~/.config/agents/skills/claude-profile-provisioner`
- 新增 3 个终端命令
- 让这 3 个新 profile 共享已有的 `skills / memory / plugins / /resume`
- 自动合并现有 MCP 配置

## 安装方法

在这个目录里执行：

```bash
chmod +x install.sh
./install.sh
```

安装完成后，重新打开终端，或者执行：

```bash
source ~/.zshrc
```

## 新增命令

- `claudeaipai`
- `claudemicu`
- `claudeterminal`

## 说明

- 这个包会把三个 profile 按“和当前打包机器一致”的方式安装出来
- 安装后，这三个 profile 的 `/resume` 与本机其他 Claude profile 共通
- `codex` 不在这个包的 `/resume` 共享范围里

## 文件

- `install.sh`: 一键安装脚本
- `profiles.json`: 三个 profile 的固定配置
- `skills/claude-profile-provisioner/`: 可复用 skill
