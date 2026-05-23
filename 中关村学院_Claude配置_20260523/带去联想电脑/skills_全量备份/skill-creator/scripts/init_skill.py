#!/usr/bin/env python3
"""
Skill Initialization Script

Creates a new skill in the unified location (~/.config/agents/skills/) with proper
directory structure, SKILL.md template, and verifies symlinks for all Claude configurations.

Usage:
    scripts/init_skill.py <skill-name> [--path <custom-output-directory>]

Examples:
    scripts/init_skill.py my-new-skill
    scripts/init_skill.py my-new-skill --path /custom/location
"""

import argparse
import os
import sys
from pathlib import Path
import subprocess

# Default unified location for all skills
DEFAULT_SKILLS_DIR = Path.home() / ".config" / "agents" / "skills"

# Claude configurations that should have symlinks
CLAUDE_CONFIGS = [
    ".claude_duck",
    ".claude_minimax",
    ".claude_codex",
    ".codex"
]

SKILL_MD_TEMPLATE = """---
name: {skill_name}
description: TODO - Describe when this skill should be used and what it does
---

# {skill_title}

TODO - Provide a brief overview of what this skill does.

## Purpose

TODO - Explain the purpose of this skill in a few sentences.

## When to Use

This skill should be used when:
- TODO - List specific scenarios
- TODO - Add more use cases

## How It Works

TODO - Explain the workflow and how to use this skill.

### Using Scripts

If this skill includes scripts in `scripts/`, explain how to use them:

```bash
scripts/example_script.py <arguments>
```

### Using References

If this skill includes reference documentation in `references/`, explain when to consult them.

### Using Assets

If this skill includes assets in `assets/`, explain how they are used in the output.

## Examples

TODO - Provide concrete examples of using this skill.

## Notes

TODO - Add any additional notes or best practices.
"""

EXAMPLE_SCRIPT = """#!/usr/bin/env python3
\"\"\"
Example script for {skill_name}

TODO - Describe what this script does
\"\"\"

def main():
    print("TODO - Implement script functionality")

if __name__ == "__main__":
    main()
"""

EXAMPLE_REFERENCE = """# Reference Documentation

TODO - Add reference documentation that Claude should consult when using this skill.

This could include:
- API documentation
- Database schemas
- Domain-specific knowledge
- Company policies
- Detailed workflow guides
"""

EXAMPLE_ASSET_README = """# Assets Directory

This directory contains files that are used in the output Claude produces, not loaded into context.

Examples:
- Templates (HTML, PowerPoint, etc.)
- Images and icons
- Fonts
- Boilerplate code
- Sample documents

TODO - Add your asset files here and remove this README.
"""


def verify_symlinks():
    """Verify and create symlinks for all Claude configurations."""
    print("\n🔗 Verifying symlinks for Claude configurations...")

    home = Path.home()
    target = DEFAULT_SKILLS_DIR

    for config in CLAUDE_CONFIGS:
        config_path = home / config
        symlink_path = config_path / "skills"

        # Check if config directory exists
        if not config_path.exists():
            print(f"  ⚠️  {config} directory not found, skipping")
            continue

        # Check if symlink exists and is correct
        if symlink_path.is_symlink():
            current_target = symlink_path.resolve()
            if current_target == target:
                print(f"  ✓ {config}/skills correctly linked")
            else:
                print(f"  ⚠️  {config}/skills linked to wrong location: {current_target}")
                print(f"     Updating to: {target}")
                symlink_path.unlink()
                symlink_path.symlink_to(target)
                print(f"  ✓ {config}/skills updated")
        elif symlink_path.exists():
            print(f"  ⚠️  {config}/skills exists but is not a symlink")
            print(f"     Please manually remove and run this script again")
        else:
            print(f"  Creating symlink: {config}/skills → {target}")
            symlink_path.symlink_to(target)
            print(f"  ✓ {config}/skills created")


def create_skill(skill_name: str, output_dir: Path):
    """Create a new skill with proper directory structure."""

    # Validate skill name
    if not skill_name.replace("-", "").replace("_", "").isalnum():
        print(f"❌ Error: Skill name '{skill_name}' contains invalid characters")
        print("   Use only letters, numbers, hyphens, and underscores")
        sys.exit(1)

    # Create skill directory
    skill_dir = output_dir / skill_name

    if skill_dir.exists():
        print(f"❌ Error: Skill directory already exists: {skill_dir}")
        sys.exit(1)

    print(f"\n📦 Creating skill: {skill_name}")
    print(f"   Location: {skill_dir}")

    # Create main directory
    skill_dir.mkdir(parents=True, exist_ok=True)
    print(f"  ✓ Created {skill_dir}")

    # Create SKILL.md
    skill_title = skill_name.replace("-", " ").replace("_", " ").title()
    skill_md_content = SKILL_MD_TEMPLATE.format(
        skill_name=skill_name,
        skill_title=skill_title
    )
    skill_md_path = skill_dir / "SKILL.md"
    skill_md_path.write_text(skill_md_content)
    print(f"  ✓ Created SKILL.md")

    # Create example directories
    scripts_dir = skill_dir / "scripts"
    scripts_dir.mkdir(exist_ok=True)
    example_script = scripts_dir / "example_script.py"
    example_script.write_text(EXAMPLE_SCRIPT.format(skill_name=skill_name))
    example_script.chmod(0o755)
    print(f"  ✓ Created scripts/ with example script")

    references_dir = skill_dir / "references"
    references_dir.mkdir(exist_ok=True)
    example_ref = references_dir / "example_reference.md"
    example_ref.write_text(EXAMPLE_REFERENCE)
    print(f"  ✓ Created references/ with example reference")

    assets_dir = skill_dir / "assets"
    assets_dir.mkdir(exist_ok=True)
    assets_readme = assets_dir / "README.md"
    assets_readme.write_text(EXAMPLE_ASSET_README)
    print(f"  ✓ Created assets/ with README")

    print(f"\n✅ Skill '{skill_name}' created successfully!")
    print(f"\nNext steps:")
    print(f"1. Edit {skill_md_path}")
    print(f"2. Replace TODO placeholders with actual content")
    print(f"3. Customize or remove example files in scripts/, references/, and assets/")
    print(f"4. Test the skill")
    print(f"5. Package with: scripts/package_skill.py {skill_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Initialize a new skill in the unified location",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s my-new-skill
  %(prog)s my-new-skill --path /custom/location

By default, skills are created in: ~/.config/agents/skills/
        """
    )
    parser.add_argument(
        "skill_name",
        help="Name of the skill to create (use lowercase with hyphens)"
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=DEFAULT_SKILLS_DIR,
        help=f"Custom output directory (default: {DEFAULT_SKILLS_DIR})"
    )

    args = parser.parse_args()

    # Ensure output directory exists
    args.path.mkdir(parents=True, exist_ok=True)

    # Verify symlinks (only if using default location)
    if args.path == DEFAULT_SKILLS_DIR:
        verify_symlinks()

    # Create the skill
    create_skill(args.skill_name, args.path)


if __name__ == "__main__":
    main()
