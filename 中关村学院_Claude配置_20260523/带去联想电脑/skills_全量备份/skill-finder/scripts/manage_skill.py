#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


VAULT_ROOT = Path("/Users/yangjingchi/.config/agents/skill-vault")
WEB_IMPORTED_ROOT = VAULT_ROOT / "web-imported"
PROJECT_SKILL_MANAGER = Path("/Users/yangjingchi/.config/agents/scripts/project_skill_manager.py")
INSTALLER = Path("/Users/yangjingchi/.config/agents/skills/.system/skill-installer/scripts/install-skill-from-github.py")


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def resolve_project_root(path: str) -> Path:
    candidate = Path(path).resolve()
    if (candidate / ".claude").exists() or (candidate / "CLAUDE.md").exists() or (candidate / "PROJECT_CONTEXT.md").exists():
        return candidate
    return candidate


def derive_skill_names(args: argparse.Namespace) -> list[str]:
    if args.name:
        return [args.name]
    if not args.path:
        raise SystemExit("--path is required")
    return [Path(path.rstrip("/")).name for path in args.path]


def promote_from_vault_to_project(skill_name: str, project_root: Path, target_name: str | None = None) -> Path:
    skill_source = (VAULT_ROOT / skill_name).resolve()
    if not skill_source.exists():
        direct = (WEB_IMPORTED_ROOT / skill_name).resolve()
        if direct.exists():
            skill_source = direct
        else:
            local = (VAULT_ROOT / "local" / skill_name).resolve()
            if local.exists():
                skill_source = local
            else:
                raise SystemExit(f"Skill not found in vault: {skill_name}")

    project_skills_dir = project_root / ".claude" / "skills"
    project_skills_dir.mkdir(parents=True, exist_ok=True)
    final_name = target_name if target_name else skill_source.name
    target = project_skills_dir / final_name
    if target.exists() or target.is_symlink():
        raise SystemExit(f"Target already exists: {target}")
    target.symlink_to(skill_source)
    return target


def command_search(args: argparse.Namespace) -> int:
    run(["python3", str(Path(__file__).with_name("search_vault.py")), args.query])
    print("---")
    run(["python3", str(Path(__file__).with_name("search_public_skills.py")), args.query])
    return 0


def command_install(args: argparse.Namespace) -> int:
    skill_names = derive_skill_names(args)
    dest = WEB_IMPORTED_ROOT

    cmd = ["python3", str(INSTALLER)]
    if args.url:
        cmd.extend(["--url", args.url])
    elif args.repo:
        cmd.extend(["--repo", args.repo])
    else:
        raise SystemExit("Provide --url or --repo")

    if args.path:
        cmd.extend(["--path", *args.path])
    if args.ref:
        cmd.extend(["--ref", args.ref])
    if args.name:
        cmd.extend(["--name", args.name])
    cmd.extend(["--dest", str(dest)])

    run(cmd)

    if args.target == "project":
        if not args.project:
            raise SystemExit("--project is required when target=project")
        project_root = resolve_project_root(args.project)
        for skill_name in skill_names:
            promote_from_vault_to_project(skill_name, project_root)
        run(["python3", str(PROJECT_SKILL_MANAGER), "init", str(project_root)])
        print(f"vault_installed_to: {dest}")
        print(f"project_refreshed: {project_root}")
    else:
        print(f"vault_installed_to: {dest}")
    return 0


def command_promote(args: argparse.Namespace) -> int:
    project_root = resolve_project_root(args.project)
    target = promote_from_vault_to_project(args.skill_name, project_root, args.name)
    run(["python3", str(PROJECT_SKILL_MANAGER), "init", str(project_root)])
    print(f"promoted: {args.skill_name} -> {target}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search, install, and promote skills.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_search = subparsers.add_parser("search")
    parser_search.add_argument("query")
    parser_search.set_defaults(func=command_search)

    parser_install = subparsers.add_parser("install")
    parser_install.add_argument("--url")
    parser_install.add_argument("--repo")
    parser_install.add_argument("--path", nargs="+")
    parser_install.add_argument("--ref", default="main")
    parser_install.add_argument("--name")
    parser_install.add_argument("--target", choices=["vault", "project"], default="vault")
    parser_install.add_argument("--project")
    parser_install.set_defaults(func=command_install)

    parser_promote = subparsers.add_parser("promote")
    parser_promote.add_argument("--skill-name", required=True)
    parser_promote.add_argument("--project", required=True)
    parser_promote.add_argument("--name")
    parser_promote.set_defaults(func=command_promote)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
