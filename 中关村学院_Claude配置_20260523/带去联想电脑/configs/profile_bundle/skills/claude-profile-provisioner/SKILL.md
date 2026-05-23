---
name: claude-profile-provisioner
description: Provision and maintain Claude Code channel profiles backed by custom gateways. Use when the user asks to create or update terminal commands like 'claudexxx', 'cluadexxx', '新增一个claude命令', '再加一个渠道', '给这个渠道配 url 和 key', '共享 skill 和 mcp', '共享 /resume', or wants a new Claude profile that reuses the shared skills, MCP servers, rules, commands, docs, memory, plugins, and resume/session storage setup.
---

# Claude Profile Provisioner

Create and maintain local Claude Code channel profiles such as `claudecodex`, `minimax`, `claudeaipai`, or similar custom commands.

## Purpose

This skill standardizes a channel profile so it behaves like the user's existing setup instead of creating a one-off isolated profile.

The profile should:
- add a shell command in `~/.zshrc`
- create a dedicated config directory such as `~/.claude_<suffix>`
- write `settings.json` with the provided base URL and API key
- share the common profile assets from `~/.claude`
- merge existing MCP server definitions into the new profile's `.claude.json`
- share the common `/resume` store so sessions can be resumed across Claude profiles
- keep only gateway-specific config private
- verify the command with `which` and `--version`

## Trigger Phrases

Use this skill when the user says things like:
- create a new `claude...` terminal command
- add another Claude channel
- configure a new gateway with URL and key
- make this new profile share skills and MCP
- make `/resume` common across profiles
- 新建一个 claude 命令
- 再创建一个渠道
- 给这个渠道配 url 和 key
- 让新 profile 跟以前共享 skill / mcp / plugins
- 让新 profile 共享 /resume

## Inputs To Collect

Collect or infer these values:
- command name, for example `claudeaipai` or `claudemicu`
- base URL
- API key
- optional model name, default `opus[1m]`
- optional explicit config suffix if the command name is unusual

If the command starts with `claude`, use the remainder as suffix.
If the command starts with `cluade`, treat that as a literal command typo but still derive the suffix from the remainder.
If neither rule applies, use the whole command name as suffix.

## Shared Static Items

The new profile should symlink these paths to the shared `~/.claude` location:
- `CLAUDE.md`
- `agents`
- `commands`
- `docs`
- `memory`
- `rules`
- `skills`
- `plugins`

## Shared Resume Store

The new profile should also symlink these paths to the shared `~/.claude` location so `/resume` is common across Claude profiles:
- `sessions`
- `history.jsonl`
- `projects`
- `session-env`

If the target profile already contains local resume data, merge it into the shared store before creating the symlinks.

## Private Items

These stay private to the profile:
- `.claude.json`
- `settings.json`
- `cache`
- `backups`
- `telemetry`

## Workflow

### 1. Inspect Existing Setup

Read `~/.zshrc` and inspect existing `~/.claude_*` directories before editing anything. Reuse the same `_claude_bin` launcher pattern already present in the user's shell config.

### 2. Create Or Update The Shell Command

Add or update a shell function in `~/.zshrc`:

```bash
<command> () {
  unset ANTHROPIC_AUTH_TOKEN ANTHROPIC_API_KEY ANTHROPIC_BASE_URL ANTHROPIC_MODEL
  export CLAUDE_CONFIG_DIR="$HOME/.claude_<suffix>"
  "$_claude_bin" --setting-sources=user "$@"
}
```

Avoid duplicate functions. Replace the managed block if it already exists.

### 3. Create Or Update The Profile Directory

Create `~/.claude_<suffix>` and write `settings.json` with:
- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_AUTH_TOKEN`
- `permissions.defaultMode = bypassPermissions`
- `model = opus[1m]` unless the user provided a different model
- `fastMode = true`
- `skipDangerousModePermissionPrompt = true`
- `autoUpdates = false`

### 4. Align Shared Symlinks

Back up conflicting files or directories first, then create symlinks for the shared static items and the shared resume store listed above.

### 5. Merge MCP Servers

Read `.claude.json` from existing `~/.claude_*` profiles, collect every `mcpServers` entry, and merge them into the target profile's `.claude.json`.

Do not delete unrelated keys already present in the target `.claude.json`.

### 6. Verify

Run:

```bash
zsh -ic 'which <command>'
zsh -ic '<command> --version'
```

Report the config directory, the shared links that were created, and the MCP server names now available.

## Implementation Note

Prefer using the helper script in `scripts/provision_claude_profile.sh` so repeated profile creation stays consistent.
