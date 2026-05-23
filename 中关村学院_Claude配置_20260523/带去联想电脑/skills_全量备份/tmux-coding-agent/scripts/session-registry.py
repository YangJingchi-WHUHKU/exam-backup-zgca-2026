#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def state_dir() -> Path:
    root = os.environ.get('AGENT_TMUX_STATE_DIR')
    path = Path(root).expanduser() if root else Path.home() / '.tmux-coding-agent-state'
    path.mkdir(parents=True, exist_ok=True)
    return path


def registry_path() -> Path:
    return state_dir() / 'sessions.json'


def load_registry() -> dict:
    path = registry_path()
    if not path.exists():
        return {'sessions': {}}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {'sessions': {}}


def save_registry(data: dict) -> None:
    registry_path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def tmux_session_exists(socket: str, session: str) -> bool:
    result = subprocess.run(['tmux', '-S', socket, 'has-session', '-t', session], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return result.returncode == 0


def prune_registry(data: dict) -> dict:
    keep = {}
    for k, item in data.get('sessions', {}).items():
        socket = item.get('socket')
        session = item.get('session')
        if socket and session and tmux_session_exists(socket, session):
            keep[k] = item
    data['sessions'] = keep
    return data


def key(socket: str, session: str) -> str:
    return f'{socket}::{session}'


def default_item(args: argparse.Namespace) -> dict:
    return {
        'socket': args.socket,
        'session': args.session,
        'target': args.target,
        'workdir': args.workdir,
        'cli': args.cli,
        'created_at': int(time.time()),
        'owner_hint': 'ai',
        'last_human_attach': None,
        'last_prompt_preview': None,
        'last_prompt_at': None,
        'initial_prompt_preview': None,
        'prompt_history': [],
    }


def cmd_register(args: argparse.Namespace) -> int:
    data = prune_registry(load_registry())
    data['sessions'][key(args.socket, args.session)] = default_item(args)
    save_registry(data)
    return 0


def cmd_set_owner(args: argparse.Namespace) -> int:
    data = prune_registry(load_registry())
    item = data['sessions'].get(key(args.socket, args.session))
    if not item:
        print('session not found', file=sys.stderr)
        return 1
    item['owner_hint'] = args.owner
    if args.owner == 'human':
        item['last_human_attach'] = int(time.time())
    data['sessions'][key(args.socket, args.session)] = item
    save_registry(data)
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    data = prune_registry(load_registry())
    item = data['sessions'].get(key(args.socket, args.session))
    if not item:
        print('session not found', file=sys.stderr)
        return 1
    for pair in args.set or []:
        if '=' not in pair:
            print(f'invalid set pair: {pair}', file=sys.stderr)
            return 1
        k, v = pair.split('=', 1)
        item[k] = v
    data['sessions'][key(args.socket, args.session)] = item
    save_registry(data)
    return 0


def cmd_append_prompt(args: argparse.Namespace) -> int:
    data = prune_registry(load_registry())
    item = data['sessions'].get(key(args.socket, args.session))
    if not item:
        print('session not found', file=sys.stderr)
        return 1
    now = int(time.time())
    prompt = args.prompt.strip()
    history = item.get('prompt_history') or []
    history.append({'text': prompt, 'at': now})
    history = history[-8:]
    item['prompt_history'] = history
    if not item.get('initial_prompt_preview'):
        item['initial_prompt_preview'] = prompt
    item['last_prompt_preview'] = prompt
    item['last_prompt_at'] = now
    data['sessions'][key(args.socket, args.session)] = item
    save_registry(data)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    data = prune_registry(load_registry())
    save_registry(data)
    sessions = list(data.get('sessions', {}).values())
    if args.socket:
        sessions = [s for s in sessions if s.get('socket') == args.socket]
    print(json.dumps({'sessions': sessions}, ensure_ascii=False))
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    data = prune_registry(load_registry())
    data.get('sessions', {}).pop(key(args.socket, args.session), None)
    save_registry(data)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('register')
    p.add_argument('--socket', required=True)
    p.add_argument('--session', required=True)
    p.add_argument('--target', required=True)
    p.add_argument('--workdir', required=True)
    p.add_argument('--cli', required=True)
    p.set_defaults(func=cmd_register)

    p = sub.add_parser('set-owner')
    p.add_argument('--socket', required=True)
    p.add_argument('--session', required=True)
    p.add_argument('--owner', required=True, choices=['ai', 'human'])
    p.set_defaults(func=cmd_set_owner)

    p = sub.add_parser('update')
    p.add_argument('--socket', required=True)
    p.add_argument('--session', required=True)
    p.add_argument('--set', action='append', default=[])
    p.set_defaults(func=cmd_update)

    p = sub.add_parser('append-prompt')
    p.add_argument('--socket', required=True)
    p.add_argument('--session', required=True)
    p.add_argument('--prompt', required=True)
    p.set_defaults(func=cmd_append_prompt)

    p = sub.add_parser('list')
    p.add_argument('--socket')
    p.set_defaults(func=cmd_list)

    p = sub.add_parser('remove')
    p.add_argument('--socket', required=True)
    p.add_argument('--session', required=True)
    p.set_defaults(func=cmd_remove)
    return parser


if __name__ == '__main__':
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.func(args))
