#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

try:
    from rich.columns import Columns
    from rich.console import Console, Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    RICH_OK = True
except Exception:
    RICH_OK = False

SCRIPT_DIR = Path(__file__).resolve().parent
REGISTRY = SCRIPT_DIR / 'session-registry.py'
STATUS = SCRIPT_DIR / 'session-status.py'

STATE_LABELS = {
    'idle': 'idle / 空闲',
    'busy': 'busy / 忙碌',
    'blocked-trust': 'blocked / 卡住',
    'starting': 'starting / 启动中',
    'unknown': 'unknown / 未知',
}
OWNER_LABELS = {
    'ai': 'ai / 自动',
    'human': 'human / 人工',
}


def run_json(cmd: list[str]) -> dict:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def load_sessions(socket: str) -> list[dict]:
    data = run_json([str(REGISTRY), 'list', '--socket', socket])
    return data.get('sessions', [])


def load_status(socket: str, session: str, target: str) -> dict:
    return run_json([str(STATUS), '--socket', socket, '--session', session, '--target', target])


def state_style(state: str) -> str:
    return {
        'idle': 'green',
        'busy': 'yellow',
        'blocked-trust': 'red',
        'starting': 'cyan',
        'unknown': 'magenta',
    }.get(state, 'white')


def owner_style(owner: str) -> str:
    return 'bright_magenta' if owner == 'human' else 'bright_blue'


def prompt_history_lines(status: dict, max_items: int = 3) -> list[str]:
    history = status.get('prompt_history') or []
    if not history:
        return ['(no prompt history yet) / （暂无任务历史）']
    out = []
    for idx, item in enumerate(history[-max_items:], start=max(1, len(history) - max_items + 1)):
        out.append(f"{idx}. {item.get('text','')}")
    return out


def build_session_card(item: dict, status: dict) -> Panel:
    summary = Table.grid(expand=True)
    summary.add_column(ratio=2)
    summary.add_column(ratio=3)
    summary.add_column(ratio=2)
    summary.add_column(ratio=3)
    summary.add_row('Session / 会话', item['session'], 'CLI / 命令', item.get('cli', '-'))
    summary.add_row('State / 状态', f"[{state_style(status.get('state','unknown'))}]{STATE_LABELS.get(status.get('state','unknown'), status.get('state','unknown'))}[/]", 'Owner / 控制', f"[{owner_style(status.get('owner','ai'))}]{OWNER_LABELS.get(status.get('owner','ai'), status.get('owner','ai'))}[/]")
    summary.add_row('Watch / 监控', f"/watch-agent {item['session']}", 'Takeover / 接管', f"/takeover {item['session']}")

    initial_prompt = status.get('initial_prompt_preview') or '(none) / （无）'
    latest_output = status.get('latest_output_line') or '(no meaningful output yet) / （暂无有效输出）'
    prompt_history = prompt_history_lines(status)

    details = Table.grid(expand=True)
    details.add_column()
    details.add_row(f"[bold cyan]Initial Task / 初始任务[/]: {initial_prompt}")
    details.add_row(f"[bold green]Latest Output / 最近输出[/]: {latest_output}")
    details.add_row("[bold]Recent Prompts / 最近几次输入[/]:")
    for line in prompt_history:
        details.add_row(f"  • {line}")

    return Panel(Group(summary, Text(''), details), border_style=state_style(status.get('state', 'unknown')), title=f"{item['session']}" )


def build_dashboard(socket: str):
    sessions = sorted(load_sessions(socket), key=lambda x: x.get('created_at', 0), reverse=True)
    header = Panel.fit(
        Text(f'AI Dashboard / AI 总控台\nSocket / 套接字: {socket}', justify='left'),
        border_style='bright_blue',
        title='Tmux Coding Agent / Tmux 编排器',
    )
    if not sessions:
        return Group(header, Panel('No active sessions on this socket. / 当前套接字下没有活跃颗粒。', border_style='red'))

    cards = []
    for item in sessions:
        status = load_status(item['socket'], item['session'], item['target'])
        item = dict(item)
        item.update({
            'initial_prompt_preview': status.get('initial_prompt_preview'),
            'prompt_history': status.get('prompt_history'),
        })
        cards.append(build_session_card(item, status))
    return Group(header, Columns(cards, expand=True, equal=False))


def build_monitor(socket: str, session: str, target: str):
    status = load_status(socket, session, target)
    summary = Table.grid(expand=True)
    summary.add_column(ratio=2)
    summary.add_column(ratio=3)
    summary.add_row('Session / 会话', status.get('session', session))
    summary.add_row('CLI / 命令', status.get('cli', '-'))
    summary.add_row('State / 状态', f"[{state_style(status.get('state','unknown'))}]{STATE_LABELS.get(status.get('state','unknown'), status.get('state','unknown'))}[/]")
    summary.add_row('Owner / 控制', f"[{owner_style(status.get('owner','ai'))}]{OWNER_LABELS.get(status.get('owner','ai'), status.get('owner','ai'))}[/]")
    summary.add_row('Workdir / 目录', status.get('workdir', '-'))

    initial_prompt = status.get('initial_prompt_preview') or '(none) / （无）'
    latest_prompt = status.get('last_prompt_preview') or '(none) / （无）'
    prompt_hist = prompt_history_lines(status, max_items=5)
    prompts = Table.grid(expand=True)
    prompts.add_column()
    prompts.add_row(f"[bold cyan]Initial Task / 初始任务[/]: {initial_prompt}")
    prompts.add_row(f"[bold cyan]Latest Prompt / 最新输入[/]: {latest_prompt}")
    prompts.add_row('[bold]Prompt History / 输入历史[/]:')
    for line in prompt_hist:
        prompts.add_row(f"  • {line}")

    tail_lines = status.get('pane_tail_lines') or ['(no output yet) / （暂无输出）']
    output_panel = Panel(Text('\n'.join(tail_lines)), title='Recent Output / 最近输出', border_style='bright_green')
    footer = Panel(f"Watch only / 这里只读监控。To control directly / 如需亲自操作：/takeover {session}", border_style='magenta')

    return Group(
        Panel(summary, title=f'AI Monitor / AI 监控 — {session}', border_style='cyan'),
        Panel(prompts, border_style='bright_blue', title='Task Context / 任务上下文'),
        output_panel,
        footer,
    )


def build_plain_dashboard(socket: str) -> str:
    sessions = sorted(load_sessions(socket), key=lambda x: x.get('created_at', 0), reverse=True)
    lines = [f"AI Dashboard / AI 总控台", f"Socket / 套接字: {socket}", ""]
    if not sessions:
        return "\n".join(lines + ["No active sessions / 没有活跃颗粒"])
    for item in sessions:
        status = load_status(item['socket'], item['session'], item['target'])
        lines.append(f"- {item['session']} | {item.get('cli','-')} | {STATE_LABELS.get(status.get('state','unknown'), status.get('state','unknown'))} | {OWNER_LABELS.get(status.get('owner','ai'), status.get('owner','ai'))}")
        lines.append(f"  Initial / 初始: {status.get('initial_prompt_preview') or '(none)'}")
        history = status.get('prompt_history') or []
        if history:
            lines.append("  History / 历史:")
            for h in history[-3:]:
                lines.append(f"    - {h.get('text','')}")
        lines.append(f"  Latest / 最近输出: {status.get('latest_output_line') or '(none)'}")
        lines.append(f"  /watch-agent {item['session']} | /takeover {item['session']}")
        lines.append("")
    return "\n".join(lines)

def build_plain_monitor(socket: str, session: str, target: str) -> str:
    status = load_status(socket, session, target)
    lines = [f"AI Monitor / AI 监控 — {session}", f"CLI: {status.get('cli','-')}", f"State / 状态: {STATE_LABELS.get(status.get('state','unknown'), status.get('state','unknown'))}", f"Owner / 控制: {OWNER_LABELS.get(status.get('owner','ai'), status.get('owner','ai'))}", f"Initial / 初始: {status.get('initial_prompt_preview') or '(none)'}", f"Latest Prompt / 最新输入: {status.get('last_prompt_preview') or '(none)'}", "Recent Output / 最近输出:", status.get('pane_excerpt') or '(none)', f"Takeover / 接管: /takeover {session}"]
    return "\n".join(lines)

def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='mode', required=True)
    p = sub.add_parser('dashboard')
    p.add_argument('--socket', required=True)
    p = sub.add_parser('monitor')
    p.add_argument('--socket', required=True)
    p.add_argument('--session', required=True)
    p.add_argument('--target', required=True)
    args = parser.parse_args()

    if not RICH_OK or not __import__('sys').stdout.isatty():
        if args.mode == 'dashboard':
            print(build_plain_dashboard(args.socket))
        else:
            print(build_plain_monitor(args.socket, args.session, args.target))
        return 0

    console = Console()
    render = (lambda: build_dashboard(args.socket)) if args.mode == 'dashboard' else (lambda: build_monitor(args.socket, args.session, args.target))
    with Live(render(), console=console, refresh_per_second=4, screen=False, auto_refresh=False) as live:
        while True:
            live.update(render(), refresh=True)
            time.sleep(1.0 if args.mode == 'monitor' else 1.5)


if __name__ == '__main__':
    raise SystemExit(main())
