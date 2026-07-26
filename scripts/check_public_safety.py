#!/usr/bin/env python3
"""Lightweight public mirror safety scan for 授时 / Granted Hours."""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOW = {
    'shengyu-meng',
    'https://shengyu-meng.github.io/granted-hours/',
    'https://github.com/shengyu-meng/granted-hours',
    '████ Meng',
}
PATTERNS = [
    ('absolute_user_path', re.compile(r'/Users/(?!example|name|yourname)[A-Za-z0-9._-]+')),
    ('github_token', re.compile(r'(ghp_|github_pat_)[A-Za-z0-9_]{20,}')),
    ('openai_key', re.compile(r'sk-[A-Za-z0-9_-]{20,}')),
    ('generic_secret_assignment', re.compile(r'(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*["\']?[^\s"\']{8,}')),
    ('telegram_or_discord_id', re.compile(r'(?i)(telegram:|discord:|chat_id|thread_id)')),
    ('private_profile_name', re.compile(r'(?i)(heizhou|黑昼|telegram)')),
    (
        'financial_account_activity',
        re.compile(r'(?i)\bholdings\b|\bbroker\s+positions?\b|\baccount\s+exposure\b|\bportfolio\s+(?:allocation|holdings|exposure)\b|持仓|仓位|试仓|账户敞口|券商头寸|组合(?:持仓|配置)'),
    ),
    (
        'private_operational_context',
        re.compile(
            r'(?i)(?:openclaw|hermes)(?:\s+(?:agent|skills?|workflow|watchdog|host-health))'
            r'|(?:wechat|微信).{0,64}(?:local\s+history|本地历史|incremental\s+messages|增量消息|private\s+chats|私聊)'
        ),
    ),
]
SKIP_DIRS = {'.git', 'node_modules'}
SKIP_FILES = {'scripts/check_public_safety.py', 'scripts/import_free_roam_artifacts.py', 'scripts/build_timetable_data.py'}

def allowed(line: str) -> bool:
    return any(x in line for x in ALLOW)

def main() -> int:
    findings = []
    for path in ROOT.rglob('*'):
        if path.is_dir() or any(part in SKIP_DIRS for part in path.parts):
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel in SKIP_FILES:
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if allowed(line):
                continue
            for name, rx in PATTERNS:
                if rx.search(line):
                    findings.append((rel, i, name, line.strip()[:220]))
    if findings:
        print('Public safety scan found possible issues:')
        for rel, i, name, line in findings:
            print(f'- {rel}:{i} [{name}] {line}')
        return 1
    print('Public safety scan passed.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
