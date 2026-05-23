---
name: skill-manager
description: This skill should be used when the user asks to "install a skill", "import a skill", "download a skill", "add a skill", "manage skills", "organize skills", "move skills to unified location", "check skill location", "list all skills", "安装skill", "导入skill", "下载skill", "添加skill", "管理skill", "skill放到哪", "skill怎么装", or needs to copy/move downloaded skills into the correct directory, or ensure all Claude configurations share the same skills directory.
---

# Skill Manager

Manage and organize skills across Global Core, project-specific packs, and the Cold Vault. Do not treat the source catalog as a loading layer.

## Purpose

This skill helps maintain a structured source of truth across three loading layers:

- Global Core: `~/.config/agents/skillsets/global-core/`
- Project Packs: `<project>/.claude/skills/`
- Cold Vault: `~/.config/agents/skill-vault/`

`~/.config/agents/skills/` is the source catalog used by `project_skills.json`; it is not a layer that should be loaded wholesale.

It prevents skill duplication and makes placement explicit.

## Skill Placement Model

### 1. Global Core

**Location:** `~/.config/agents/skillsets/global-core/`

Use for:

- minimal, highly reusable skills that should be visible in every session
- operational safety skills such as investigation, planning, debugging, verification, reviews, session-end, MCP sync, and basic document handling

Shared profiles should point to Global Core:
- `~/.claude/skills` -> `~/.config/agents/skillsets/global-core/`
- `~/.claude_duck/skills` -> `~/.config/agents/skillsets/global-core/`
- `~/.claude_minimax/skills` -> `~/.config/agents/skillsets/global-core/`
- `~/.claude_codex/skills` -> `~/.config/agents/skillsets/global-core/`
- `~/.codex/skills` -> `~/.config/agents/skillsets/global-core/`

### 2. Project Packs

**Location:** `<project>/.claude/skills/`

Use for:

- project-specific skills
- skills promoted from the vault for one project
- local overrides and bespoke project workflows

Project packs should contain only project-specific skills. Global Core is loaded separately.

### 3. Cold Vault

**Location:** `~/.config/agents/skill-vault/`

Use for:

- newly downloaded external skills
- dormant skills not meant for daily loading
- skills that still need human review

### Source Catalog

**Location:** `~/.config/agents/skills/`

Use for:

- the canonical source files referenced by `project_skills.json`
- staging maintained skills before they are selected into Global Core or a Project Pack

Do not point runtime profiles at the entire source catalog.

## When to Use

Invoke this skill when the user:
- Wants to install a new skill
- Needs to check where skills are located
- Wants to list all available skills
- Asks to organize or consolidate skills
- Has multiple Claude configurations and wants unified skill access

## Workflow

### Check Current Skill Setup

```bash
# Verify symlinks exist
for dir in .claude_duck .claude_minimax .claude_codex .codex; do
    ls -l ~/$dir/skills 2>/dev/null
done

# List source catalog entries
ls -1 ~/.config/agents/skills/
```

### Create Symlinks (if missing)

```bash
# For each Claude configuration
ln -sf ~/.config/agents/skillsets/global-core ~/.claude/skills
ln -sf ~/.config/agents/skillsets/global-core ~/.claude_duck/skills
ln -sf ~/.config/agents/skillsets/global-core ~/.claude_minimax/skills
ln -sf ~/.config/agents/skillsets/global-core ~/.claude_codex/skills
ln -sf ~/.config/agents/skillsets/global-core ~/.codex/skills
```

### Place a New Skill

Default rule:

1. New external skill → install into the cold vault first
2. Review it
3. Promote it into a project pack if needed
4. Only register it in the source catalog and add it to Global Core or a Project Pack when it becomes a long-term maintained skill

**Option 1: Download into the cold vault**
```bash
python3 ~/.config/agents/skills/skill-finder/scripts/manage_skill.py install \
  --repo <owner>/<repo> \
  --path <skill-path> \
  --target vault
```

**Option 2: Download, then use in a project**
```bash
python3 ~/.config/agents/skills/skill-finder/scripts/manage_skill.py install \
  --repo <owner>/<repo> \
  --path <skill-path> \
  --target project \
  --project /path/to/project
```

This still does `vault first -> project pack second`.

**Option 3: Create a new skill**
Use `skill-creator`, but choose placement deliberately:

- vault/local for draft or experimental skills
- project `.claude/skills/` for project-bound skills
- source catalog only when it is intentionally maintained

### Verify Skill Structure

Every skill must have:
- `SKILL.md` file with YAML frontmatter
- `name:` field in frontmatter
- `description:` field in frontmatter

```bash
# Check skill structure
for skill in ~/.config/agents/skills/*/; do
    name=$(basename "$skill")
    if [ -f "$skill/SKILL.md" ]; then
        echo "✓ $name"
    else
        echo "✗ $name (missing SKILL.md)"
    fi
done
```

### Promote Vault Skill To Project

```bash
python3 ~/.config/agents/skills/skill-finder/scripts/manage_skill.py promote \
  --skill-name <skill-name> \
  --project /path/to/project
```

### Refresh Project Packs

```bash
python3 ~/.config/agents/scripts/project_skill_manager.py sync-all
```

## Skill Structure Requirements

Standard skill structure:
```
skill-name/
├── SKILL.md (required)
│   └── YAML frontmatter with name and description
├── assets/ (optional)
├── references/ (optional)
└── scripts/ (optional)
```

## Common Tasks

### List Source Catalog

```bash
ls -1 ~/.config/agents/skills/ | grep -v "^\."
```

### Check Skill Metadata

```bash
for skill in ~/.config/agents/skills/*/SKILL.md; do
    echo "=== $(dirname "$skill" | xargs basename) ==="
    head -10 "$skill" | grep -E "^name:|^description:"
    echo ""
done
```

### Verify All Configurations Use Unified Location

```bash
for dir in .claude_duck .claude_minimax .claude_codex .codex; do
    if [ -L ~/$dir/skills ]; then
        target=$(readlink ~/$dir/skills)
        if [ "$target" = "/Users/$(whoami)/.config/agents/skillsets/global-core" ]; then
            echo "✓ $dir correctly linked"
        else
            echo "✗ $dir linked to wrong location: $target"
        fi
    else
        echo "✗ $dir not a symlink"
    fi
done
```

## Best Practices

1. **Do not auto-promote downloads into the source catalog or Global Core**.
2. **Use the cold vault as the default landing zone for external skills**.
3. **Use project packs for project-scoped activation**.
4. **Reserve global core for highly reusable, stable skills**.
5. **Use skill-creator for structured local skill authoring**.

## Troubleshooting

### Skill not appearing in Claude

1. Check symlink exists: `ls -l ~/.claude_duck/skills`
2. Verify SKILL.md exists: `ls ~/.config/agents/skills/skill-name/SKILL.md`
3. Check frontmatter format: `head -5 ~/.config/agents/skills/skill-name/SKILL.md`
4. Restart Claude Code session

### Multiple versions of same skill

1. Find all instances: `find ~ -name "skill-name" -type d`
2. Keep source copies in `~/.config/agents/skills/`, then expose only selected skills through Global Core or a Project Pack
3. Remove duplicates from other locations

### Symlink broken

```bash
# Remove broken symlink
rm ~/.claude_duck/skills

# Create new symlink
ln -sf ~/.config/agents/skillsets/global-core ~/.claude_duck/skills
```

## Notes

- Not every skill should be globally active.
- In this local setup, placement is part of the skill-management job.
- New skills are only “naturally correct” when they follow the placement model above.
