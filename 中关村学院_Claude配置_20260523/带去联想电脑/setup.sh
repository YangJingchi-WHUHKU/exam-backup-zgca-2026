#!/usr/bin/env bash
# ===================================================================
# 中关村学院科研实训 — 联想笔记本一键 Claude 配置脚本
# 用法: cd 带去联想电脑 && bash setup.sh
# 适用: macOS / Linux (zsh 或 bash)
# 作者: 杨镜池 / Claude 助手
# 日期: 2026-05-23
# ===================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

step() { echo -e "\n${BLUE}━━━ $1 ━━━${NC}"; }
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
err()  { echo -e "${RED}❌ $1${NC}"; }

# ===================================================================
step "Step 0/7  前置环境检查"
# ===================================================================

# 检查 OS
OS=$(uname -s)
echo "操作系统: $OS"

# 检查 shell
USER_SHELL=$(basename "$SHELL")
echo "当前 shell: $USER_SHELL"
if [[ "$USER_SHELL" != "zsh" && "$USER_SHELL" != "bash" ]]; then
    warn "shell 是 $USER_SHELL，profile_bundle 默认假设 zsh，可能需要手动调整"
fi

# 检查 node
if ! command -v node &>/dev/null; then
    err "未找到 node。请先安装 Node.js ≥ 18: https://nodejs.org/"
    exit 1
fi
NODE_VER=$(node -v)
ok "Node $NODE_VER"

# 检查 npm
if ! command -v npm &>/dev/null; then
    err "未找到 npm。"
    exit 1
fi
ok "npm $(npm -v)"

# 检查 git
if ! command -v git &>/dev/null; then
    warn "未找到 git；部分功能不可用但不影响主流程"
fi

# ===================================================================
step "Step 1/7  安装 Claude Code CLI（若已装则跳过）"
# ===================================================================

if command -v claude &>/dev/null; then
    ok "claude 已安装: $(claude --version 2>/dev/null || echo 'version unknown')"
else
    echo "安装 @anthropic-ai/claude-code ..."
    npm install -g @anthropic-ai/claude-code || {
        err "npm 安装失败，可能网络问题。请离线安装或换源后重跑。"
        exit 1
    }
    ok "Claude Code 安装完成"
fi

# ===================================================================
step "Step 2/7  确保 ~/.claude 目录存在并复制全局配置"
# ===================================================================

mkdir -p ~/.claude

# settings.json
cp configs/settings.json ~/.claude/settings.json
ok "settings.json"

# CLAUDE.md（含 Karpathy 4 原则）
cp configs/CLAUDE.md ~/.claude/CLAUDE.md
ok "CLAUDE.md（已含 Karpathy 4 原则）"

# rules / docs / commands
for d in rules docs commands; do
    rm -rf ~/.claude/$d
    cp -R configs/$d ~/.claude/$d
    ok "$d/"
done

# memory 不复制（保持干净）
mkdir -p ~/.claude/memory

# ===================================================================
step "Step 3/7  安装 4 个 Channel（aipai / micu / codesuc / swarm）"
# ===================================================================

if [ ! -f ~/.zshrc ]; then
    if [ "$USER_SHELL" = "bash" ]; then
        warn "未找到 ~/.zshrc。profile_bundle/install.sh 要求 zsh。"
        warn "尝试切换：chsh -s $(which zsh) 或手动初始化 ~/.zshrc 后重跑此 step"
        warn "如果坚持用 bash，需要手动改写 profile_bundle/install.sh 的 wrapper 部分"
    fi
fi

# profile_bundle 依赖 _claude_bin / claude wrapper 在 zshrc 里存在
# 若没有，先注入一个最简版
if [ -f ~/.zshrc ]; then
    if ! grep -q "_claude_bin" ~/.zshrc 2>/dev/null; then
        warn "~/.zshrc 缺少 _claude_bin wrapper，注入最简版..."
        cat >> ~/.zshrc <<'ZSHRC_EOF'

# === Claude Code wrapper (injected by setup.sh) ===
_claude_resolve_bin() {
    local bin
    bin=$(command -v claude) || return 1
    echo "$bin"
}
_claude_exec() {
    local claude_bin
    claude_bin="$(_claude_resolve_bin)" || return 1
    "$claude_bin" "$@"
}
_sync_proxy_from_macos() { :; }
_claude_update_terminal_title() {
    if [ -n "${CLAUDE_CHANNEL_NAME-}" ]; then
        printf '\033]0;%s\007' "$CLAUDE_CHANNEL_NAME"
    fi
}
_claude_use_profile() {
    local config_dir="$1"
    local channel_name="$2"
    shift 2
    unset ANTHROPIC_AUTH_TOKEN ANTHROPIC_API_KEY ANTHROPIC_BASE_URL ANTHROPIC_MODEL
    export CLAUDE_CONFIG_DIR="$config_dir"
    export CLAUDE_CHANNEL_NAME="$channel_name"
    _claude_update_terminal_title
    _claude_exec --setting-sources=user "$@"
}
claude() { _claude_use_profile "$HOME/.claude" "Claude Official" "$@"; }
# === End Claude Code wrapper ===
ZSHRC_EOF
        ok "_claude_bin wrapper 已注入 ~/.zshrc"
    fi
fi

cd configs/profile_bundle
chmod +x install.sh
if [ "$USER_SHELL" = "zsh" ] && [ -f ~/.zshrc ]; then
    zsh ./install.sh
else
    # bash 兼容运行
    bash ./install.sh || {
        warn "install.sh 直接 bash 运行失败，请手动 zsh ./install.sh"
    }
fi
cd "$SCRIPT_DIR"

ok "4 channel 安装完成: claudeaipai / claudemicu / claudecodesuc / claudeswarm"

# ===================================================================
step "Step 4/7  安装 34 个 Skill"
# ===================================================================

chmod +x install_skills.sh
bash install_skills.sh

# ===================================================================
step "Step 5/7  配置 codex MCP（可选）"
# ===================================================================

if command -v codex &>/dev/null; then
    echo "检测到 codex CLI，配置 MCP..."
    python3 - "$SCRIPT_DIR/configs/mcp_servers.json" <<'PY'
import json, os, sys
add = json.load(open(sys.argv[1]))['mcpServers']
main_path = os.path.expanduser('~/.claude.json')
if os.path.exists(main_path):
    main = json.load(open(main_path))
else:
    main = {}
main.setdefault('mcpServers', {}).update(add)
json.dump(main, open(main_path, 'w'), indent=2, ensure_ascii=False)
print('✅ codex MCP 已并入 ~/.claude.json')
PY
else
    warn "未找到 codex CLI，跳过 MCP 配置（不影响主流程）"
    warn "如需安装 codex：brew install codex 或参考 https://github.com/openai/codex"
fi

# ===================================================================
step "Step 6/7  验证"
# ===================================================================

echo
echo "已安装 channel 命令："
for cmd in claudeaipai claudemicu claudecodesuc claudeswarm; do
    if grep -q "^$cmd ()" ~/.zshrc 2>/dev/null || grep -q "^$cmd () {" ~/.zshrc 2>/dev/null; then
        ok "$cmd"
    else
        warn "$cmd 未在 ~/.zshrc 找到"
    fi
done

echo
echo "已安装 skill 数（~/.config/agents/skills/）："
SKILL_COUNT=$(ls -1 ~/.config/agents/skills/ 2>/dev/null | wc -l | tr -d ' ')
echo "  $SKILL_COUNT 个"
if [ "$SKILL_COUNT" -lt 30 ]; then
    warn "数量低于预期（应 ≥34）"
fi

echo
echo "settings.json："
cat ~/.claude/settings.json | head -10

# ===================================================================
step "Step 7/7  完成 🎉"
# ===================================================================

cat <<EOF

================================================================
✅ 配置完成！

下一步：
  1. 重新打开终端 或 source ~/.zshrc
  2. 试一下命令：
       claudeaipai     # 推荐 first try
       claudemicu      # 备用 1
       claudecodesuc   # 备用 2
       claudeswarm     # 备用 3

  3. 进入 Claude 后输入测试：
       > 你现在用的什么 model？能看到几个 skill？
       预期返回：opus[1m]，约 34 个 skill

  4. 任一 channel 内可用 /resume 切回之前的会话（4 channel 共享）

⚠️  注意事项：
  - 笔试 / 机试期间禁用 Claude（违规取消成绩）
  - 科研实训当天确认学院是否认可"通过国内反代的 Claude"
  - 4 个 channel 任意一个不通时立即换另外 3 个

📂 关键文件位置：
  ~/.claude/CLAUDE.md          # 全局指令（含 Karpathy 4 原则）
  ~/.claude/settings.json      # opus[1m] / bypassPermissions
  ~/.config/agents/skills/     # 34 个 skill
  ~/.claude.json               # MCP 配置（含 codex）

================================================================
EOF
