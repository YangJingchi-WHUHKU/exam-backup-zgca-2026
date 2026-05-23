#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REGISTRY = SCRIPT_DIR / 'session-registry.py'
BUSY_PATTERNS = [r'Gusting…', r'Thinking', r'Running', r'Esc to interrupt', r'ctrl\+c to interrupt', r'✻ ', r'✳ ', r'✶ ']
PROMPT_PATTERNS = [r'❯', r'\$ ']


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def load_session(socket: str, session: str) -> dict:
    raw = run([str(REGISTRY), 'list', '--socket', socket])
    data = json.loads(raw or '{"sessions": []}')
    for item in data.get('sessions', []):
        if item.get('session') == session:
            return item
    return {'socket': socket, 'session': session}


def capture(socket: str, target: str, lines: int) -> str:
    result = subprocess.run(['tmux', '-S', socket, 'capture-pane', '-p', '-J', '-t', target, '-S', f'-{lines}'], capture_output=True, text=True)
    return result.stdout


def attached_clients(socket: str, session: str) -> list[dict]:
    result = subprocess.run(['tmux', '-S', socket, 'list-clients', '-t', session, '-F', '#{client_activity}\t#{client_tty}'], capture_output=True, text=True)
    if result.returncode != 0:
        return []
    clients = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        activity_str, tty = (line.split('\t', 1) + [''])[:2]
        try:
            activity = int(activity_str)
        except Exception:
            activity = 0
        clients.append({'activity': activity, 'tty': tty})
    return clients


def extract_tail(pane: str, max_lines: int = 6) -> list[str]:
    lines = [line.rstrip() for line in pane.splitlines()]
    cleaned = [line for line in lines if line.strip()]
    return cleaned[-max_lines:]


def latest_meaningful_line(lines: list[str]) -> str:
    ignore_patterns = [r'^[-─=]+$', r'^❯\s*$', r'^\s*$', r'^  ⏵⏵ ', r'^Updated: ']
    for line in reversed(lines):
        if any(re.search(p, line) for p in ignore_patterns):
            continue
        return line[:200]
    return ''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket', required=True)
    parser.add_argument('--session', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--timeout', type=int, default=int(os.environ.get('AGENT_TMUX_HUMAN_TIMEOUT', '30')))
    parser.add_argument('--lines', type=int, default=120)
    args = parser.parse_args()

    meta = load_session(args.socket, args.session)
    pane = capture(args.socket, args.target, args.lines)
    now = int(time.time())
    clients = attached_clients(args.socket, args.session)
    active_human = False
    recent_activity_age = None
    for client in clients:
        age = max(0, now - client['activity']) if client['activity'] else 10**9
        if recent_activity_age is None or age < recent_activity_age:
            recent_activity_age = age
        if age <= args.timeout:
            active_human = True

    if 'Quick safety check:' in pane:
        state = 'blocked-trust'
    elif any(re.search(p, pane) for p in BUSY_PATTERNS):
        state = 'busy'
    elif any(re.search(p, pane) for p in PROMPT_PATTERNS):
        state = 'idle'
    elif pane.strip():
        state = 'starting'
    else:
        state = 'unknown'

    hint_age = None
    if meta.get('last_human_attach'):
        hint_age = max(0, now - int(meta['last_human_attach']))
    hinted_human = meta.get('owner_hint') == 'human' and hint_age is not None and hint_age <= args.timeout
    owner = 'human' if (active_human or hinted_human) else 'ai'

    tail_lines = extract_tail(pane)
    latest_line = latest_meaningful_line(tail_lines)

    output = {
        'socket': args.socket,
        'session': args.session,
        'target': args.target,
        'cli': meta.get('cli'),
        'workdir': meta.get('workdir'),
        'state': state,
        'owner': owner,
        'attached_clients': len(clients),
        'recent_human_activity_age': recent_activity_age,
        'last_prompt_preview': meta.get('last_prompt_preview'),
        'last_prompt_at': meta.get('last_prompt_at'),
        'pane_excerpt': '\n'.join(tail_lines),
        'pane_tail_lines': tail_lines,
        'latest_output_line': latest_line,
    }
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
