#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from review_utils import (
    extract_summary,
    grade_completeness,
    grade_safety,
    grade_trust,
    inspect_texts,
    score_text,
    summarize_review,
    tokenize,
)

VAULT_ROOT = Path("/Users/yangjingchi/.config/agents/skill-vault")


def score_skill(skill_md: Path, query_tokens: list[str]) -> dict:
    text = skill_md.read_text(encoding="utf-8", errors="ignore")
    name, description = extract_summary(text, skill_md.parent.name)
    score = score_text(query_tokens, skill_md.parent.name, name, description, text[:4000])
    helpers = list((skill_md.parent / "scripts").glob("**/*")) if (skill_md.parent / "scripts").exists() else []
    helper_texts = []
    for helper in helpers[:5]:
        if helper.is_file():
            try:
                helper_texts.append(helper.read_text(encoding="utf-8", errors="ignore")[:4000])
            except Exception:
                continue

    safety = grade_safety(bool(helpers), inspect_texts(helper_texts), "local-vault")
    completeness = grade_completeness(
        text,
        description,
        bool(helpers),
        (skill_md.parent / "templates").exists(),
        (skill_md.parent / "resources").exists() or (skill_md.parent / "references").exists(),
    )
    trust = grade_trust("local-vault")
    review = summarize_review(score, safety, completeness, trust)
    return {
        "score": score,
        "name": name,
        "description": description,
        "path": skill_md.parent,
        "review": review,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Search the cold skill vault for matching skills.")
    parser.add_argument("query", help="Natural language query")
    args = parser.parse_args()

    query_tokens = tokenize(args.query)
    if not query_tokens:
        print("No usable query tokens.")
        return 1

    candidates = []
    for skill_md in VAULT_ROOT.glob("**/SKILL.md"):
        candidate = score_skill(skill_md, query_tokens)
        if candidate["score"] > 0:
            candidates.append(candidate)

    candidates.sort(key=lambda item: (-item["score"], str(item["path"])))

    print(f"vault_root: {VAULT_ROOT}")
    print(f"query: {args.query}")
    if not candidates:
        print("matches: none")
        return 0

    print("matches:")
    for item in candidates[:10]:
        print(f"- score={item['score']} name={item['name']} path={item['path']}")
        if item["description"]:
            print(f"  description={item['description']}")
        print(
            "  review="
            f"safety:{item['review']['safety_level']}, "
            f"completeness:{item['review']['completeness_level']}, "
            f"trust:{item['review']['trust_level']}, "
            f"recommendation:{item['review']['recommendation']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
