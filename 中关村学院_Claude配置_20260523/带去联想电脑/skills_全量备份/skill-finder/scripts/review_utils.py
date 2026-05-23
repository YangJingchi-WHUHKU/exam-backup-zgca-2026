#!/usr/bin/env python3

from __future__ import annotations

import re
from pathlib import Path


DANGEROUS_PATTERNS = [
    (r"rm\s+-rf", "destructive shell deletion"),
    (r"git\s+reset\s+--hard", "destructive git reset"),
    (r"curl\s+.*\|\s*(bash|sh)", "pipe-to-shell download"),
    (r"wget\s+.*\|\s*(bash|sh)", "pipe-to-shell download"),
    (r"\bsudo\b", "privileged command"),
    (r"chmod\s+777", "unsafe permissions"),
    (r"shutil\.rmtree\(", "recursive delete in script"),
    (r"os\.remove\(", "file deletion in script"),
]


def tokenize(text: str) -> list[str]:
    return [token for token in re.split(r"[^a-zA-Z0-9\u4e00-\u9fff]+", text.lower()) if token]


def extract_summary(text: str, fallback_name: str) -> tuple[str, str]:
    name = fallback_name
    description = ""
    for line in text.splitlines()[:20]:
        stripped = line.strip()
        if stripped.startswith("name:"):
            name = stripped.split(":", 1)[1].strip() or name
        if stripped.startswith("description:"):
            description = stripped.split(":", 1)[1].strip()
    return name, description


def score_text(query_tokens: list[str], *parts: str) -> int:
    haystack = " ".join(parts).lower()
    score = 0
    for token in query_tokens:
        if token in haystack:
            score += 3
    return score


def inspect_texts(texts: list[str]) -> list[str]:
    hits: list[str] = []
    for text in texts:
        lowered = text.lower()
        for pattern, label in DANGEROUS_PATTERNS:
            if re.search(pattern, lowered):
                hits.append(label)
    return sorted(set(hits))


def grade_safety(has_scripts: bool, danger_hits: list[str], trusted_source: str) -> tuple[str, str]:
    if danger_hits:
        return "medium", "contains dangerous patterns: " + ", ".join(danger_hits)
    if has_scripts and trusted_source == "low":
        return "medium", "has executable helper scripts from an untrusted source"
    if has_scripts:
        return "medium", "has helper scripts; inspect before installing"
    return "high", "instruction-only or low-risk structure"


def grade_completeness(skill_text: str, description: str, has_scripts: bool, has_templates: bool, has_resources: bool) -> tuple[str, str]:
    text_lower = skill_text.lower()
    signals = 0
    reasons = []
    if description:
        signals += 1
        reasons.append("has description")
    if "## instructions" in text_lower or "## workflow" in text_lower:
        signals += 1
        reasons.append("has structured instructions")
    if "## examples" in text_lower:
        signals += 1
        reasons.append("has examples")
    if has_scripts:
        signals += 1
        reasons.append("has helper scripts")
    if has_templates or has_resources:
        signals += 1
        reasons.append("has supporting assets")

    if signals >= 4:
        return "high", ", ".join(reasons)
    if signals >= 2:
        return "medium", ", ".join(reasons) if reasons else "partial structure"
    return "low", ", ".join(reasons) if reasons else "very thin skill package"


def grade_trust(source_label: str) -> tuple[str, str]:
    trusted = {"openai-curated", "openai-experimental", "huggingface-skills", "local-vault"}
    if source_label in trusted:
        return "high", "known curated or local-controlled source"
    return "medium", "public source but not curated by your local setup"


def recommend_action(match_score: int, safety: str, completeness: str, trust: str) -> str:
    if safety == "medium" and completeness == "low":
        return "inspect_only"
    if match_score >= 9 and completeness in {"medium", "high"} and trust == "high":
        return "candidate_for_install"
    if match_score >= 6 and completeness in {"medium", "high"}:
        return "shortlist_for_review"
    return "discovery_only"


def summarize_review(match_score: int, safety: tuple[str, str], completeness: tuple[str, str], trust: tuple[str, str]) -> dict:
    recommendation = recommend_action(match_score, safety[0], completeness[0], trust[0])
    return {
        "match_score": match_score,
        "safety_level": safety[0],
        "safety_reason": safety[1],
        "completeness_level": completeness[0],
        "completeness_reason": completeness[1],
        "trust_level": trust[0],
        "trust_reason": trust[1],
        "recommendation": recommendation,
    }

