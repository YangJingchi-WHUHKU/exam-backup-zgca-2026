# Claude Code 回复美化阅读器（glow + tmux）

每次 Claude 回复完，自动在另一个窗格用 glow 漂亮渲染。

## 一键启动（已装好依赖）

```bash
tmux new-session -d -s glow 'bash ~/.claude/hooks/glow-watch.sh' \; split-window -h \; attach
```

左边自动渲染，右边正常用 Claude Code。

## 安装

### 1. 装依赖

**macOS**：
```bash
brew install glow tmux
```

**Linux（Ubuntu/Debian）**：
```bash
sudo apt install tmux python3
# glow:
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://repo.charm.sh/apt/gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/charm.gpg
echo "deb [signed-by=/etc/apt/keyrings/charm.gpg] https://repo.charm.sh/apt/ * *" | sudo tee /etc/apt/sources.list.d/charm.list
sudo apt update && sudo apt install glow
```

**Linux 无 sudo**（考试机用）：
```bash
# 直接下二进制
mkdir -p ~/bin
curl -L https://github.com/charmbracelet/glow/releases/latest/download/glow_Linux_x86_64.tar.gz | tar xz -C ~/bin glow
export PATH=$HOME/bin:$PATH  # 加到 .bashrc/.zshrc
```

### 2. 安装脚本

```bash
mkdir -p ~/.claude/hooks
cp glow-watch.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/glow-watch.sh
```

### 3. tmux 配置（推荐）

```bash
echo "set -g focus-events on" >> ~/.tmux.conf
```

## 用法

```bash
# 启动
tmux new-session -d -s glow 'bash ~/.claude/hooks/glow-watch.sh' \; split-window -h \; attach

# 退出 tmux 但保留会话：Ctrl+B 然后 D
# 重新进入：tmux attach -t glow
# 彻底关闭：tmux kill-session -t glow
```

## 原理

- 脚本每秒 poll `~/.claude/projects/*/*.jsonl`，找最新被修改的 transcript
- 提取最后一条 `type=="assistant"` 消息的文本
- 用 md5 hash 判断是否变化，变了就写到 `/tmp/claude-response.md`
- 调 `glow` 渲染显示

不依赖 Claude Code 的 Stop hook（hook 在 tmux 里可能不触发），纯文件 poll，稳定。

## 排错

| 问题 | 原因 |
|------|------|
| 左边一直空白 | `~/.claude/projects/` 没有 jsonl — 先在右边正常对话一次 |
| 提示找不到 glow | 上面装依赖那一步没做 |
| 内容不刷新 | 可能 Claude Code 用了不同的 projects 目录，改脚本顶部的 `PROJECTS_DIR` |
| 中文乱码 | 终端 locale 不对，`export LANG=en_US.UTF-8` |
