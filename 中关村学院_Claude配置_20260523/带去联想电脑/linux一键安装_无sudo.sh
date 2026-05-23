#!/usr/bin/env bash
# ====================================================================
# 中关村学院 — Linux 无 sudo 一键安装（适用学校锁权限的笔记本）
# 用法:
#   bash linux一键安装_无sudo.sh
# 前提:
#   - 能联网（用 nvm 下 node）
#   - python3 已装（Ubuntu 默认装了）
# ====================================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; BLUE='\033[0;34m'; NC='\033[0m'
step() { echo -e "\n${BLUE}━━━ $1 ━━━${NC}"; }
ok()   { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
err()  { echo -e "${RED}❌ $1${NC}"; }

# --------------------------------------------------------------------
step "Step 1/5  Node.js（通过 nvm，无 sudo）"
# --------------------------------------------------------------------
if command -v node >/dev/null 2>&1; then
    ok "Node 已存在: $(node -v)"
else
    if [ ! -d "$HOME/.nvm" ]; then
        echo "装 nvm 到 ~/.nvm（不用 sudo）..."
        if command -v curl >/dev/null; then
            curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash || {
                err "curl 失败，可能 GitHub 不通"
                warn "尝试用国内镜像..."
                curl -fsSL https://gitee.com/mirrors/nvm/raw/master/install.sh | bash || true
            }
        elif command -v wget >/dev/null; then
            wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
        else
            err "无 curl 也无 wget，没法装 nvm"
            err "请用手机热点联网，或找管理员装 nodejs"
            exit 1
        fi
    fi
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

    # 国内镜像加速 node 下载
    export NVM_NODEJS_ORG_MIRROR="https://npmmirror.com/mirrors/node/"
    nvm install --lts || nvm install 20
    nvm use --lts 2>/dev/null || nvm use 20
fi
ok "Node $(node -v) | npm $(npm -v)"

# --------------------------------------------------------------------
step "Step 2/5  Claude Code CLI（无 sudo）"
# --------------------------------------------------------------------
if ! command -v claude >/dev/null 2>&1; then
    echo "切国内镜像 + 安装 claude-code..."
    npm config set registry https://registry.npmmirror.com
    npm install -g @anthropic-ai/claude-code
fi
ok "claude: $(which claude)"
claude --version 2>/dev/null || true

# --------------------------------------------------------------------
step "Step 3/5  4 个 channel 配置"
# --------------------------------------------------------------------
PROFILES="$SCRIPT_DIR/configs/profile_bundle/profiles.json"
if [ ! -f "$PROFILES" ]; then
    err "找不到 $PROFILES"
    exit 1
fi

python3 - "$PROFILES" <<'PY'
import json, os, sys
HOME = os.path.expanduser('~')
data = json.load(open(sys.argv[1]))
for p in data['profiles']:
    suffix = p['command'].replace('claude', '', 1)
    d = f"{HOME}/.claude_{suffix}"
    os.makedirs(d, exist_ok=True)
    s = {
        "env": {
            "ANTHROPIC_BASE_URL": p['base_url'],
            "ANTHROPIC_AUTH_TOKEN": p['api_key']
        },
        "model": p.get('model', 'opus[1m]'),
        "permissions": {"defaultMode": "bypassPermissions"},
        "effortLevel": "high",
        "includeCoAuthoredBy": False,
        "skipDangerousModePermissionPrompt": True
    }
    with open(f"{d}/settings.json", 'w') as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
    print(f"  OK {p['command']} -> {d}")
PY

# --------------------------------------------------------------------
step "Step 4/5  bash 函数写入 ~/.bashrc"
# --------------------------------------------------------------------
MARKER="# === Claude channels zgc ==="
if ! grep -q "$MARKER" ~/.bashrc 2>/dev/null; then
    cat >> ~/.bashrc <<'BRC'

# === Claude channels zgc ===
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
_claude_p() {
    local d=$1 n=$2; shift 2
    unset ANTHROPIC_AUTH_TOKEN ANTHROPIC_API_KEY ANTHROPIC_BASE_URL ANTHROPIC_MODEL
    export CLAUDE_CONFIG_DIR=$d CLAUDE_CHANNEL_NAME=$n
    command claude --setting-sources=user "$@"
}
claudeaipai()   { _claude_p "$HOME/.claude_aipai"   "aipai"   "$@"; }
claudemicu()    { _claude_p "$HOME/.claude_micu"    "micu"    "$@"; }
claudecodesuc() { _claude_p "$HOME/.claude_codesuc" "codesuc" "$@"; }
claudeswarm()   { _claude_p "$HOME/.claude_swarm"   "swarm"   "$@"; }
# === End Claude channels zgc ===
BRC
    ok "4 个命令已写入 ~/.bashrc"
else
    ok "~/.bashrc 已有 channel 命令，跳过"
fi

# --------------------------------------------------------------------
step "Step 5/5  全局配置 + Skill"
# --------------------------------------------------------------------
mkdir -p ~/.claude
[ -f configs/settings.json ] && cp configs/settings.json ~/.claude/ && ok "~/.claude/settings.json"
[ -f configs/CLAUDE.md ]    && cp configs/CLAUDE.md    ~/.claude/ && ok "~/.claude/CLAUDE.md（含 Karpathy 4 原则）"
for d in rules docs commands; do
    if [ -d "configs/$d" ]; then
        rm -rf ~/.claude/$d
        cp -r configs/$d ~/.claude/$d
        ok "~/.claude/$d/"
    fi
done

echo ""
read -rp "装 34 个 skill 吗 [Y/n]? " yn
yn=${yn:-Y}
if [[ "$yn" =~ ^[Yy]$ ]]; then
    mkdir -p ~/.config/agents/skills ~/.claude/skills
    cnt=0
    for s in skills_全量备份/*/; do
        n=$(basename "$s")
        rm -rf "$HOME/.config/agents/skills/$n" "$HOME/.claude/skills/$n"
        cp -r "$s" "$HOME/.config/agents/skills/$n"
        ln -sf "$HOME/.config/agents/skills/$n" "$HOME/.claude/skills/$n"
        cnt=$((cnt+1))
    done
    ok "$cnt 个 skill 装好"
else
    warn "跳过 skill 安装"
fi

# --------------------------------------------------------------------
cat <<'EOF'

============================================
  ✅ 全部完成（无 sudo）
============================================

下一步：
  1. 跑这条让配置生效（必须）：
       source ~/.bashrc

  2. 试一下：
       claudeaipai

     备用：
       claudemicu
       claudecodesuc
       claudeswarm

  3. 进入 Claude 后输入：
       > 你能看到几个 skill？什么 model？
     预期：34 个 skill，model = opus[1m]

EOF
