---
name: skill-finder
description: Find a missing skill before creating a new one. Always search the local cold vault first, then search rich public sources on the web. If a good match is found, install it into the cold vault or promote it into a project pack in one step. Use when the user says "找skill", "缺skill", "有没有这种skill", "search skill", "find a skill", "install a skill", or asks for a missing capability.
---

# Skill Finder

Use this skill when a needed capability may already exist as a reusable skill.

## Goal

Find the best existing skill with the smallest possible search cost:

1. Search the local cold vault first.
2. If the vault has no good match, search rich public sources on the web.
3. For every promising match, do an initial screen on safety, task-completion completeness, and source trust.
4. Present a short summary to the user and wait for feedback before installing anything.
5. Only after the user confirms, support one-step installation into the vault or one-step promotion into a project pack.
6. Only suggest creating a new skill when both steps fail or the available skills are clearly inadequate.

## Local-First Search

The local cold vault is:

- `/Users/yangjingchi/.config/agents/skill-vault`

This directory is not part of the active global/project packs. It is the parking lot for dormant skills.

Run the local helper first:

```bash
python3 /Users/yangjingchi/.config/agents/skills/skill-finder/scripts/search_vault.py "<query>"
```

If the search returns plausible matches:

1. Summarize the best 1-3 hits with skill name, path, and why they match.
2. Include a pre-screen for:
   - safety
   - task-completion completeness
   - source trust
   - recommendation (`candidate_for_install`, `shortlist_for_review`, `inspect_only`, `discovery_only`)
3. Ask whether the user wants to:
   - keep it in the vault and just inspect it
   - promote it into active use
   - copy/link it into a specific project pack

## Web Search Fallback

If the vault search is weak or empty, search the web.

Search order:

1. OpenAI curated and experimental skill catalogs
2. public installable skill repos such as Hugging Face skills and other GitHub skill repos
3. GitHub repository search for repos that contain `SKILL.md`
4. public discovery indexes and marketplaces

Use the public search helper:

```bash
python3 /Users/yangjingchi/.config/agents/skills/skill-finder/scripts/search_public_skills.py "<query>"
```

Or the combined helper:

```bash
python3 /Users/yangjingchi/.config/agents/skills/skill-finder/scripts/manage_skill.py search "<query>"
```

The public search helper must also produce the same pre-screen fields:

- safety
- completeness
- trust
- recommendation

Recommended query patterns:

- `site:github.com SKILL.md <topic> "Claude Code"`
- `site:github.com SKILL.md <topic> "Codex"`
- `site:github.com "<topic>" "skill" "SKILL.md"`
- `site:github.com/openai/skills <topic>`

Recommended public references:

- OpenAI skill installer flow / curated skills
- Hugging Face skills repository
- `awesome-agent-skills` index

## Evaluation Rules

Prefer skills that:

- actually include a `SKILL.md`
- have a clear `name` and `description`
- match the user task closely
- are reasonably scoped, not giant prompt dumps
- contain scripts/templates/resources when the task needs them

Reject or down-rank skills that:

- are obviously stale or broken
- are only vague prompts with no structure
- are much broader than the user needs

## Promotion Rule

If the user wants a found skill to be available later:

1. Put it into the cold vault first.
2. If they want to use it in a project, promote it from the cold vault into that project's `.claude/skills`.
3. Do not skip the vault stage.
4. Do not install immediately after discovery; wait for explicit user feedback on the summary first.

### Install Into The Vault

```bash
python3 /Users/yangjingchi/.config/agents/skills/skill-finder/scripts/manage_skill.py install \
  --repo openai/skills \
  --path skills/.experimental/<skill-name> \
  --target vault
```

### Install For Project Use

This still installs into the vault first, then links it into the project pack.

```bash
python3 /Users/yangjingchi/.config/agents/skills/skill-finder/scripts/manage_skill.py install \
  --repo huggingface/skills \
  --path skills/<skill-name> \
  --target project \
  --project /path/to/project
```

### Promote A Vault Skill Into A Project Pack

```bash
python3 /Users/yangjingchi/.config/agents/skills/skill-finder/scripts/manage_skill.py promote \
  --skill-name <skill-name> \
  --project /path/to/project
```

## Output Format

When reporting results, use this structure:

```text
Search summary
- Local vault: found / not found
- Web search: searched / skipped

Best matches
1. <skill-name> — <why it matches>
   - Safety: <level + one-line reason>
   - Completeness: <level + one-line reason>
   - Trust: <level + one-line reason>
   - Recommendation: <candidate_for_install / shortlist_for_review / inspect_only / discovery_only>
2. ...

Recommended action
- Wait for user feedback
- Then either keep in vault, promote to project, or reject
```

## Notes

- This skill complements `skill-manager`; it does not replace it.
- This skill complements the built-in `skill-installer`; use that workflow if the user wants to install from a public repo after discovery.
- The cold vault lives at `/Users/yangjingchi/.config/agents/skill-vault`.
- The source registry is `/Users/yangjingchi/.config/agents/skills/skill-finder/sources.json`.
- Project use is always `vault first -> project pack second`.
