#!/usr/bin/env bash
# 添加 claudezgc（第 5 个 channel）
set -e

mkdir -p ~/.claude_zgc

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

if ! grep -q "claudezgc()" ~/.bashrc; then
    echo 'claudezgc() { _claude_p "$HOME/.claude_zgc" "zgc" "$@"; }' >> ~/.bashrc
fi

echo "✅ claudezgc 已加好"
echo "跑: source ~/.bashrc && claudezgc"
