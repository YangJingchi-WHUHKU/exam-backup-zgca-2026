#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REGISTRY = SCRIPT_DIR / 'session-registry.py'
OPEN_TAB = SCRIPT_DIR / 'open-terminal-tab.sh'
VIEW = SCRIPT_DIR / 'view-agent-session.sh'
TAKEOVER = SCRIPT_DIR / 'takeover-agent-session.sh'
DASHBOARD = SCRIPT_DIR / 'dashboard.sh'


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True)


def current_workdir() -> str:
    return str(Path.cwd().resolve())


def load_sessions() -> list[dict]:
    result = run([str(REGISTRY), 'list'])
    raw = result.stdout or '{"sessions": []}'
    data = json.loads(raw)
    return data.get('sessions', [])


def filter_current_workdir(items: list[dict]) -> list[dict]:
    cwd = current_workdir()
    return [item for item in items if Path(item.get('workdir', '')).resolve() == Path(cwd)]


def select_session(items: list[dict], query: str | None) -> dict:
    if not items:
        raise SystemExit('No active tmux coding-agent sessions for the current directory.')
    if not query:
        return sorted(items, key=lambda x: x.get('created_at', 0), reverse=True)[0]

    query_lower = query.lower()
    exact = [i for i in items if i.get('session', '').lower() == query_lower]
    if exact:
        return sorted(exact, key=lambda x: x.get('created_at', 0), reverse=True)[0]

    contains = [
        i for i in items
        if query_lower in i.get('session', '').lower() or query_lower in i.get('cli', '').lower()
    ]
    if not contains:
        raise SystemExit(f'No session matching {query!r} in the current directory.')
    return sorted(contains, key=lambda x: x.get('created_at', 0), reverse=True)[0]


def shell_join(parts: list[str]) -> str:
    import shlex
    return ' '.join(shlex.quote(p) for p in parts)


def cmd_list(args: argparse.Namespace) -> int:
    items = filter_current_workdir(load_sessions())
    if args.query:
        items = [
            i for i in items
            if args.query.lower() in i.get('session', '').lower() or args.query.lower() in i.get('cli', '').lower()
        ]
    items = sorted(items, key=lambda x: x.get('created_at', 0), reverse=True)
    if not items:
        print('No active tmux coding-agent sessions for the current directory.')
        return 0
    print(f"Current directory: {current_workdir()}")
    print(f"{'SESSION':<20} {'CLI':<14} {'TARGET':<24}")
    print('-' * 64)
    for item in items:
        print(f"{item.get('session','')[:20]:<20} {item.get('cli','')[:14]:<14} {item.get('target','')[:24]:<24}")
    print('\nShortcuts:')
    print('  /takeover [name]')
    print('  /watch-agent [name]')
    print('  /agent-dashboard')
    return 0


def cmd_takeover(args: argparse.Namespace) -> int:
    item = select_session(filter_current_workdir(load_sessions()), args.query)
    result = run([str(TAKEOVER), '-S', item['socket'], '-s', item['session'], '-t', item['target']])
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    print(f"Taking over {item['session']} ({item['cli']}) in a new Terminal tab.")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    item = select_session(filter_current_workdir(load_sessions()), args.query)
    cmd = shell_join([str(VIEW), '-S', item['socket'], '-s', item['session'], '-t', item['target']])
    result = run([str(OPEN_TAB), f'cd {shell_join([current_workdir()])} && {cmd}'])
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    print(f"Opened monitor for {item['session']} ({item['cli']}) in a new Terminal tab.")
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    items = filter_current_workdir(load_sessions())
    item = select_session(items, args.query) if items else None
    if not item:
        raise SystemExit('No active tmux coding-agent sessions for the current directory.')
    cmd = shell_join([str(DASHBOARD), '-S', item['socket']])
    result = run([str(OPEN_TAB), f'cd {shell_join([current_workdir()])} && {cmd}'])
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    print(f"Opened dashboard for socket {item['socket']} in a new Terminal tab.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('list')
    p.add_argument('query', nargs='?')
    p.set_defaults(func=cmd_list)

    p = sub.add_parser('takeover')
    p.add_argument('query', nargs='?')
    p.set_defaults(func=cmd_takeover)

    p = sub.add_parser('watch')
    p.add_argument('query', nargs='?')
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser('dashboard')
    p.add_argument('query', nargs='?')
    p.set_defaults(func=cmd_dashboard)
    return parser


if __name__ == '__main__':
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))
