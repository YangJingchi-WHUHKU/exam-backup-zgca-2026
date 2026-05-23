#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_SRC="$SCRIPT_DIR/skills/claude-profile-provisioner"
SKILL_DST="$HOME/.config/agents/skills/claude-profile-provisioner"
PROFILES_JSON="$SCRIPT_DIR/profiles.json"

if [[ ! -d "$HOME/.claude" ]]; then
  echo "Missing ~/.claude. Install and run Claude Code first." >&2
  exit 1
fi

if [[ ! -f "$HOME/.zshrc" ]]; then
  echo "Missing ~/.zshrc." >&2
  exit 1
fi

if ! rg -n "_claude_bin|claude \\(\\)|claudeduck \\(\\)" "$HOME/.zshrc" >/dev/null 2>&1; then
  echo "Your ~/.zshrc does not look like an existing Claude Code wrapper setup." >&2
  echo "Expected to find _claude_bin or existing claude wrapper functions." >&2
  exit 1
fi

mkdir -p "$HOME/.config/agents/skills"
rm -rf "$SKILL_DST"
cp -R "$SKILL_SRC" "$SKILL_DST"
chmod +x "$SKILL_DST/scripts/provision_claude_profile.sh"

python3 - "$PROFILES_JSON" <<'PY' | while IFS=$'\t' read -r command base_url api_key model; do
import json
import sys

data = json.load(open(sys.argv[1], "r", encoding="utf-8"))
for item in data["profiles"]:
    print("\t".join([
        item["command"],
        item["base_url"],
        item["api_key"],
        item.get("model", "opus[1m]")
    ]))
PY
  echo "Installing $command ..."
  "$SKILL_DST/scripts/provision_claude_profile.sh" "$command" "$base_url" "$api_key" "$model"
done

echo
echo "Installed:"
echo "  - claudeaipai     (api.aipaibox.com)"
echo "  - claudemicu      (micuapi.ai)"
echo "  - claudecodesuc   (main-new.codesuc.top)"
echo "  - claudeswarm     (byteswarm.ai)"
echo
echo "Next:"
echo "  source ~/.zshrc"
echo "or reopen the terminal."
