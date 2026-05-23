#!/usr/bin/env bash
# ============================================================
# 中关村学院 Claude Code 一键全装（Linux 无 sudo）
# 一行命令搞定 nvm + Node + Claude Code + 4 个中转站
# ============================================================
set -e

G='\033[0;32m'; Y='\033[1;33m'; R='\033[0;31m'; B='\033[0;34m'; N='\033[0m'
ok()   { echo -e "${G}✅ $1${N}"; }
warn() { echo -e "${Y}⚠️  $1${N}"; }
err()  { echo -e "${R}❌ $1${N}"; }
step() { echo -e "\n${B}━━━ $1 ━━━${N}"; }

# --------- Step 1: Node.js via nvm ---------
step "Step 1/4  装 Node.js（无 sudo）"
if command -v node >/dev/null 2>&1; then
    ok "Node 已存在: $(node -v)"
else
    if [ ! -d "$HOME/.nvm" ]; then
        echo "下载 nvm..."
        if command -v curl >/dev/null; then
            curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
        elif command -v wget >/dev/null; then
            wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
        else
            err "无 curl 也无 wget。建议先开 FlClash 代理"
            exit 1
        fi
    fi
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    export NVM_NODEJS_ORG_MIRROR="https://npmmirror.com/mirrors/node/"
    nvm install --lts
    ok "Node $(node -v) 装好"
fi

# --------- Step 2: Claude Code ---------
step "Step 2/4  装 Claude Code"
if command -v claude >/dev/null 2>&1; then
    ok "claude 已存在"
else
    npm config set registry https://registry.npmmirror.com
    npm install -g @anthropic-ai/claude-code
    ok "Claude Code 装好"
fi
claude --version || warn "claude --version 报错，但继续"

# --------- Step 3: 4 个中转站 ---------
step "Step 3/4  配 4 个中转站"
mkdir -p ~/.claude_aipai ~/.claude_micu ~/.claude_codesuc ~/.claude_swarm ~/.claude_zgc

cat > ~/.claude_aipai/settings.json << 'EOF'
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://api.aipaibox.com/",
    "ANTHROPIC_AUTH_TOKEN": "sk-N8c1EnaseEaN8GVJkDmVybSPlghJ7G5FQZMFcTKZmRoHjVML"
  },
  "model": "opus[1m]",
  "permissions": {"defaultMode": "bypassPermissions"},
  "effortLevel": "high"
}
EOF

cat > ~/.claude_micu/settings.json << 'EOF'
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://www.micuapi.ai",
    "ANTHROPIC_AUTH_TOKEN": "sk-PaBaIPnh3zasiuPmzW9xohKKfueW6ykRd03sPwFwHXxthXbC"
  },
  "model": "opus[1m]",
  "permissions": {"defaultMode": "bypassPermissions"},
  "effortLevel": "high"
}
EOF

cat > ~/.claude_codesuc/settings.json << 'EOF'
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://main-new.codesuc.top/",
    "ANTHROPIC_AUTH_TOKEN": "sk-n5LlW8Pm21b1ENgSCMH0Muvx6eeeqBl5Gt7vBs8wxCy0m9lL"
  },
  "model": "opus[1m]",
  "permissions": {"defaultMode": "bypassPermissions"},
  "effortLevel": "high"
}
EOF

cat > ~/.claude_swarm/settings.json << 'EOF'
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://byteswarm.ai/claude",
    "ANTHROPIC_AUTH_TOKEN": "cr_9vb-z9nLfpKJEwSzbFTTfnADxzP8ee3FBhev4h2vdJY"
  },
  "model": "opus[1m]",
  "permissions": {"defaultMode": "bypassPermissions"},
  "effortLevel": "high"
}
EOF

cat > ~/.claude_zgc/settings.json << 'EOF'
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://www.micuapi.ai",
    "ANTHROPIC_AUTH_TOKEN": "sk-pRdgVnnj0EaaLhrradXQDClzPDeWMqJXPt78PAcYQWPBwiRU"
  },
  "model": "opus[1m]",
  "permissions": {"defaultMode": "bypassPermissions"},
  "effortLevel": "high",
  "fastMode": true,
  "skipDangerousModePermissionPrompt": true
}
EOF

ok "5 个 channel 的 settings.json 写好了"

# --------- Step 4: bash 函数 ---------
step "Step 4/4  写 4 个命令到 ~/.bashrc"
if ! grep -q "Claude channels zgc" ~/.bashrc 2>/dev/null; then
    cat >> ~/.bashrc << 'BRC'

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
claudezgc()     { _claude_p "$HOME/.claude_zgc"     "zgc"     "$@"; }
BRC
    ok "4 个命令写入 ~/.bashrc"
else
    ok "~/.bashrc 已配置"
fi

# --------- 完成 ---------
echo
echo "============================================"
echo "  ✅ 全部完成！"
echo "============================================"
echo
echo "现在执行这两行（一定要做）："
echo "  source ~/.bashrc"
echo "  claudeaipai"
echo
echo "其他 channel："
echo "  claudemicu     (备用 1)"
echo "  claudecodesuc  (备用 2)"
echo "  claudeswarm    (备用 3)"
echo "  claudezgc      (备用 4, fastMode 开)"
echo
