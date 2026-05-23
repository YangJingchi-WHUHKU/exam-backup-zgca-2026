#!/usr/bin/env bash
# ============================================================
# Codex CLI + 5 个 wrapper (含 codexzgc) 一键安装
# 适用 Linux 无 sudo
# ============================================================
set -e

echo "=== Step 1: 装 codex CLI ==="
if ! command -v codex >/dev/null 2>&1; then
    # 确保 nvm Node 已加载
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
    npm install -g @openai/codex
fi
codex --version 2>/dev/null || echo "codex 装好（可能没 --version 命令，不影响）"

echo "=== Step 2: ~/.codex/config.toml （5 个 provider）==="
mkdir -p ~/.codex
cat > ~/.codex/config.toml << 'CONF'
model_provider = "codexzgc"
model = "gpt-5.5"
model_context_window = 1050000
model_auto_compact_token_limit = 210000
show_raw_agent_reasoning = false
sandbox_mode = "danger-full-access"
approval_policy = "never"
suppress_unstable_features_warning = true
project_doc_fallback_filenames = ["CLAUDE.md"]
project_doc_max_bytes = 65536

[model_providers.codexaipai]
name = "Aipai"
base_url = "https://api.aipaibox.com/v1"
wire_api = "responses"
env_key = "OPENAI_API_KEY"
requires_openai_auth = false

[model_providers.codexmicu]
name = "Micu"
base_url = "https://www.micuapi.ai/v1"
wire_api = "responses"
env_key = "OPENAI_API_KEY"
requires_openai_auth = false

[model_providers.codexcodesuc]
name = "Codesuc"
base_url = "https://main-new.codesuc.top/v1"
wire_api = "responses"
env_key = "OPENAI_API_KEY"
requires_openai_auth = false

[model_providers.codexswarm]
name = "Swarm"
base_url = "https://byteswarm.ai/codex/v1"
wire_api = "responses"
env_key = "OPENAI_API_KEY"
requires_openai_auth = false

[model_providers.codexzgc]
name = "ZGC"
base_url = "https://www.micuapi.ai/v1"
wire_api = "responses"
env_key = "OPENAI_API_KEY"
requires_openai_auth = false
CONF

echo "=== Step 3: 5 个 auth.json ==="
mkdir -p ~/.codex_aipai ~/.codex_micu ~/.codex_codesuc ~/.codex_swarm ~/.codex_zgc

echo '{"OPENAI_API_KEY": "sk-ktojJbk1J2LVeyrqVmYTZHDh8AElxCAcThQqM9xAXUbJI8rG"}' > ~/.codex_aipai/auth.json
echo '{"OPENAI_API_KEY": "sk-0cxV7BxFMqSCp4djRA6ztbPUEnjwhWEKCe2RUNaEcmaPQ3P0"}' > ~/.codex_micu/auth.json
echo '{"OPENAI_API_KEY": "sk-1dCroZfTdqTjwW3XzHqMIvZMxWh8OcGhkdeI2YEHbYigPR56"}' > ~/.codex_codesuc/auth.json
echo '{"OPENAI_API_KEY": "cr_PQJoEZkaYFIiTqXNOres88lT2XOSDjOm4LBoQo2MYQc"}' > ~/.codex_swarm/auth.json
echo '{"OPENAI_API_KEY": "sk-g18W2o8A4b3QYUnXk4qzljPmpT9NjHaaDuUgmo4PpwHf35IC"}' > ~/.codex_zgc/auth.json

echo "=== Step 4: 写 5 个 codex wrapper 到 ~/.bashrc ==="
if ! grep -q "codex wrappers zgc" ~/.bashrc; then
    cat >> ~/.bashrc << 'BRC'

# === codex wrappers zgc ===
_codex_p() {
    local provider="$1" key_file="$2"
    shift 2
    local key
    key=$(python3 -c "import json,sys; print(json.load(open('$key_file'))['OPENAI_API_KEY'])")
    OPENAI_API_KEY="$key" codex -c model_provider="\"$provider\"" "$@"
}
codexaipai()   { _codex_p "codexaipai"   "$HOME/.codex_aipai/auth.json"   "$@"; }
codexmicu()    { _codex_p "codexmicu"    "$HOME/.codex_micu/auth.json"    "$@"; }
codexcodesuc() { _codex_p "codexcodesuc" "$HOME/.codex_codesuc/auth.json" "$@"; }
codexswarm()   { _codex_p "codexswarm"   "$HOME/.codex_swarm/auth.json"   "$@"; }
codexzgc()     { _codex_p "codexzgc"     "$HOME/.codex_zgc/auth.json"     -m gpt-5.5 "$@"; }
# === End codex wrappers zgc ===
BRC
fi

echo ""
echo "============================================"
echo "  ✅ Codex 全套装好"
echo "============================================"
echo ""
echo "5 个 codex 命令："
echo "  codexaipai     codexmicu     codexcodesuc"
echo "  codexswarm     codexzgc  ← 推荐主用（gpt-5.5）"
echo ""
echo "跑这两条："
echo "  source ~/.bashrc"
echo "  codexzgc"
echo ""
