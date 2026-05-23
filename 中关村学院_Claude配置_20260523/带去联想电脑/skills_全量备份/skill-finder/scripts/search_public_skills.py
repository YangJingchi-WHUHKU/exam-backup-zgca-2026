#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
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

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
SOURCES_PATH = ROOT_DIR / "sources.json"

REQUEST_TIMEOUT_SECONDS = 8
def load_sources() -> dict:
    return json.loads(SOURCES_PATH.read_text(encoding="utf-8"))


def github_request(url: str, user_agent: str) -> bytes:
    headers = {"User-Agent": user_agent}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read()


def load_json_url(url: str, user_agent: str) -> object:
    payload = github_request(url, user_agent)
    return json.loads(payload.decode("utf-8"))


def github_contents_url(repo: str, path: str, ref: str) -> str:
    encoded_path = urllib.parse.quote(path.strip("/"))
    return f"https://api.github.com/repos/{repo}/contents/{encoded_path}?ref={ref}"


def github_raw_url(repo: str, ref: str, path: str) -> str:
    owner, name = repo.split("/", 1)
    return f"https://raw.githubusercontent.com/{owner}/{name}/{ref}/{path}"


def github_repo_search_url(query: str, per_page: int = 8) -> str:
    encoded = urllib.parse.quote(query)
    return f"https://api.github.com/search/repositories?q={encoded}&sort=stars&order=desc&per_page={per_page}"


SKIP_DIRS = {
    ".git",
    ".github",
    ".claude-plugin",
    ".cursor-plugin",
    "assets",
    "scripts",
    "templates",
    "resources",
    "agents",
    "apps",
}


def list_dir(repo: str, ref: str, path: str) -> list[dict]:
    data = load_json_url(github_contents_url(repo, path, ref), "skill-finder-contents")
    return data if isinstance(data, list) else []


def discover_skill_dirs(repo: str, ref: str, root: str, depth: int = 0, max_depth: int = 4) -> list[str]:
    if depth > max_depth:
        return []
    try:
        items = list_dir(repo, ref, root)
    except Exception:
        return []

    names = {item.get("name", "") for item in items}
    if "SKILL.md" in names:
        return [root.rstrip("/")]

    found: list[str] = []
    for item in items:
        if item.get("type") != "dir":
            continue
        name = item.get("name", "")
        if name in SKIP_DIRS:
            continue
        child_path = item.get("path") or f"{root.rstrip('/')}/{name}"
        found.extend(discover_skill_dirs(repo, ref, child_path, depth + 1, max_depth))
    return found


def search_catalog(catalog: dict, query_tokens: list[str]) -> list[dict]:
    candidates: list[dict] = []
    seen_paths: set[str] = set()

    for prefix in catalog["prefixes"]:
        for skill_dir in discover_skill_dirs(catalog["repo"], catalog["ref"], prefix):
            if skill_dir in seen_paths:
                continue
            seen_paths.add(skill_dir)
            skill_basename = skill_dir.rstrip("/").split("/")[-1]
            raw_text = github_request(
                github_raw_url(catalog["repo"], catalog["ref"], f"{skill_dir}/SKILL.md"),
                "skill-finder-raw",
            ).decode("utf-8", errors="ignore")
            name, description = extract_summary(raw_text, skill_basename)
            score = score_text(query_tokens, skill_dir, name, description, raw_text[:4000])
            if score <= 0:
                continue
            try:
                top_items = list_dir(catalog["repo"], catalog["ref"], skill_dir)
            except Exception:
                top_items = []
            has_scripts = any(item.get("type") == "dir" and item.get("name") == "scripts" for item in top_items)
            has_templates = any(item.get("type") == "dir" and item.get("name") == "templates" for item in top_items)
            has_resources = any(
                item.get("type") == "dir" and item.get("name") in {"resources", "references", "assets"} for item in top_items
            )
            helper_texts = []
            if has_scripts:
                try:
                    script_items = list_dir(catalog["repo"], catalog["ref"], f"{skill_dir}/scripts")
                except Exception:
                    script_items = []
                for helper in script_items[:5]:
                    if helper.get("type") != "file":
                        continue
                    try:
                        helper_texts.append(
                            github_request(
                                github_raw_url(catalog["repo"], catalog["ref"], helper["path"]),
                                "skill-finder-script",
                            ).decode("utf-8", errors="ignore")[:4000]
                        )
                    except Exception:
                        continue

            safety = grade_safety(has_scripts, inspect_texts(helper_texts), catalog["id"])
            completeness = grade_completeness(raw_text, description, has_scripts, has_templates, has_resources)
            trust = grade_trust(catalog["id"])
            review = summarize_review(score, safety, completeness, trust)
            candidates.append(
                {
                    "source_type": "catalog",
                    "catalog_id": catalog["id"],
                    "catalog_label": catalog["label"],
                    "repo": catalog["repo"],
                    "ref": catalog["ref"],
                    "path": skill_dir,
                    "name": name,
                    "description": description,
                    "score": score,
                    "tree_url": f"https://github.com/{catalog['repo']}/tree/{catalog['ref']}/{skill_dir}",
                    "review": review,
                }
            )

    candidates.sort(key=lambda item: (-item["score"], item["repo"], item["path"]))
    return candidates


def search_github_repos(query: str, query_tokens: list[str], covered_repos: set[str]) -> list[dict]:
    url = github_repo_search_url(f"{query} skill agent")
    data = load_json_url(url, "skill-finder-repo-search")
    items = data.get("items", []) if isinstance(data, dict) else []
    matches: list[dict] = []

    for item in items[:6]:
        repo = item.get("full_name")
        if not repo or repo in covered_repos:
            continue
        default_branch = item.get("default_branch") or "main"
        repo_score = score_text(
            query_tokens,
            repo,
            item.get("description") or "",
            " ".join(item.get("topics") or []),
        )
        if repo_score <= 0:
            continue
        matches.append(
            {
                "source_type": "github_repo",
                "repo": repo,
                "ref": default_branch,
                "name": repo.split("/")[-1],
                "description": item.get("description") or "",
                "score": repo_score,
                "repo_url": item.get("html_url"),
                "review": {
                    "safety_level": "unknown",
                    "safety_reason": "repo-level result only; skill internals not inspected yet",
                    "completeness_level": "unknown",
                    "completeness_reason": "repo-level result only; no SKILL.md parsed yet",
                    "trust_level": "medium",
                    "trust_reason": "public GitHub repository search result",
                    "recommendation": "discovery_only",
                },
            }
        )

    matches.sort(key=lambda item: (-item["score"], item["repo"]))
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(description="Search public skill sources.")
    parser.add_argument("query", help="Natural language search query")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    query_tokens = tokenize(args.query)
    sources = load_sources()

    catalog_matches = []
    covered_repos = set()
    for catalog in sources["installable_catalogs"]:
        covered_repos.add(catalog["repo"])
        try:
            catalog_matches.extend(search_catalog(catalog, query_tokens))
        except Exception as exc:
            catalog_matches.append(
                {
                    "source_type": "catalog_error",
                    "catalog_id": catalog["id"],
                    "catalog_label": catalog["label"],
                    "score": -1,
                    "error": str(exc),
                }
            )

    repo_search_error = None
    try:
        repo_matches = search_github_repos(args.query, query_tokens, covered_repos)
    except Exception as exc:
        repo_matches = []
        repo_search_error = str(exc)
    payload = {
        "query": args.query,
        "catalog_matches": [item for item in catalog_matches if item.get("score", 0) > 0][: args.limit],
        "repo_matches": repo_matches[: max(3, min(args.limit, 6))],
        "indexes": sources.get("discovery_indexes", []),
        "repo_search_error": repo_search_error,
    }

    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"query: {args.query}")
    print("catalog_matches:")
    if payload["catalog_matches"]:
        for item in payload["catalog_matches"]:
            print(
                f"- score={item['score']} name={item['name']} source={item['catalog_label']} "
                f"repo={item['repo']} path={item['path']}"
            )
            if item.get("description"):
                print(f"  description={item['description']}")
            print(f"  install_url={item['tree_url']}")
            print(
                "  review="
                f"safety:{item['review']['safety_level']}, "
                f"completeness:{item['review']['completeness_level']}, "
                f"trust:{item['review']['trust_level']}, "
                f"recommendation:{item['review']['recommendation']}"
            )
    else:
        print("- none")

    print("github_repo_matches:")
    if payload["repo_matches"]:
        for item in payload["repo_matches"]:
            print(f"- score={item['score']} repo={item['repo']} url={item['repo_url']}")
            if item.get("description"):
                print(f"  description={item['description']}")
            print(
                "  review="
                f"safety:{item['review']['safety_level']}, "
                f"completeness:{item['review']['completeness_level']}, "
                f"trust:{item['review']['trust_level']}, "
                f"recommendation:{item['review']['recommendation']}"
            )
    else:
        print("- none")
        if payload.get("repo_search_error"):
            print(f"  note=repo search skipped: {payload['repo_search_error']}")

    print("discovery_indexes:")
    for item in payload["indexes"]:
        print(f"- {item['label']}: {item['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
