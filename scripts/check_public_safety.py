#!/usr/bin/env python3
"""Lightweight public mirror safety scan for 授时 / Granted Hours."""
from __future__ import annotations
import argparse
import re
from pathlib import Path

from public_projection_privacy import denied_terms_present, load_private_denylist
from semantic_public_policy import semantic_risk_tags

ROOT = Path(__file__).resolve().parents[1]
IDENTITY_DENYLIST = ROOT / '.private' / 'identity-denylist.json'
ALLOWED_TOKENS = {
    'shengyu-meng',
    'https://shengyu-meng.github.io/granted-hours/',
    'https://github.com/shengyu-meng/granted-hours',
    'Simon Meng',
}
PATTERNS = [
    ('absolute_user_path', re.compile(r'/Users/(?!example|name|yourname)[A-Za-z0-9._-]+')),
    ('github_token', re.compile(r'(ghp_|github_pat_)[A-Za-z0-9_]{20,}')),
    ('openai_key', re.compile(r'sk-[A-Za-z0-9_-]{20,}')),
    ('aws_access_key', re.compile(r'AKIA[0-9A-Z]{16}')),
    ('bearer_token', re.compile(r'(?i)\bbearer\s+[A-Za-z0-9._~-]{16,}')),
    ('generic_secret_assignment', re.compile(r'(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*["\']?[^\s"\']{8,}')),
    ('telegram_or_discord_id', re.compile(r'(?i)(telegram:|discord:|chat_id|thread_id)')),
    ('email_address', re.compile(r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b')),
    ('phone_number', re.compile(r'(?<![A-Za-z0-9.])(?:\+?86[- ]?)?1[3-9]\d(?:\d{8}|[- ]\d{4}[- ]\d{4})(?![A-Za-z0-9.])')),
    ('bank_account_number', re.compile(r'(?<![A-Za-z0-9.])(?:\d{4}[- ]?){3}\d{4}(?:[- ]?\d{1,3})?(?![A-Za-z0-9.])')),
    ('private_profile_storage', re.compile(r'(?i)(?:\.hermes|profiles?[/\\]heizhou|state\.db|cron[/\\](?:jobs\.json|output))')),
]
EDUCATION_IDENTITY_RE = re.compile(
    r"(?i)\b(?:school|university|college|faculty|department|institute|academy|"
    r"accounting|digital[- ]accounting|mba|degree|undergraduate|graduate|"
    r"bachelor(?:'s)?|master(?:'s)?|doctoral|education|teaching|teacher|instructor|"
    r"course(?:work|s|[- ]materials?|[- ]program)?|syllabus|curriculum|"
    r"dissertation|talent[- ](?:training|development))\b"
    r"|\b(?:academic\s+major|major\s+(?:identity|program|subject|field))\b"
    r"|(?:学校|大学|学院|学部|院系|系部|研究院|研究所|书院|教师|导师|"
    r"专业(?:名称|身份|方向|课程|建设|设置|申报|培养)|"
    r"财会|会计|工商管理硕士|数智人才|人才培养|本科|硕士|博士|学位|课程|课件|"
    r"教学|教案|毕业设计)"
    r"|(?:MBA|stress-management|压力管理|财会专业|会计专业|财会人才|会计人才|影子回放|规则提案|shadow replay)"
    r"|(?:本科|硕士|博士|学位|毕业|会计).{0,8}论文"
    r"|论文.{0,8}(?:评阅|外审|导师|学生|学位)"
)
SPOUSE_ACTIVITY_RE = re.compile(
    r"(?i)(?:广西民族大学|人才小高地|会计学|管理学|工商管理硕士|数智财会|财会人才)"
    r"|\bMBA\b|\bGuangxi\s+Minzu\s+University\b|\btalent[- ]highland\b"
    r"|\bmanagement\s+(?:studies|science|degree|discipline)\b"
    r"|\baccounting\b.{0,40}\b(?:thes(?:is|es)|course|teaching|teacher|student|talent|degree|undergraduate|proposal|training)\b"
    r"|\b(?:thes(?:is|es)|course|teaching|teacher|student|talent|degree|undergraduate|proposal|training)\b.{0,40}\baccounting\b"
)
PROPOSAL_TITLE_CONTEXT_RE = re.compile(
    r"(?i)\b(?:school|university|college|faculty|department|institute|academy|"
    r"accounting|digital[- ]accounting|mba|education|course|curriculum|"
    r"talent[- ](?:training|development))(?:[a-z0-9&/()'’-]*[ -]+){0,5}"
    r"(?:proposal|application)\b"
    r"|(?:学校|大学|学院|学部|院系|研究院|研究所|书院|专业|财会|会计|人才培养|"
    r"本科|硕士|博士|学位|课程|教学)[^，。；;]{0,24}(?:申报书|申请书)"
    r"|《[^》]{2,40}》(?:申报书|申请书)"
)
PULSE_PRIVATE_ID_RE = re.compile(
    r"(?i)[\"'](?:job[_ -]?id|channel|delivery[_ -]?target|prompt)[\"']\s*:"
    r"|\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b"
)
SKIP_DIRS = {'.git', '.private', 'node_modules'}
SKIP_PREFIXES = {'audits/', 'docs/plans/', 'scripts/test_'}
SKIP_FILES = {
    'scripts/check_public_safety.py',
    'scripts/import_agent_events.py',
    'scripts/import_collaboration_events.py',
    'scripts/import_free_roam_artifacts.py',
    'scripts/import_timetable_pulses.py',
    'scripts/build_timetable_data.py',
    'scripts/public_projection_privacy.py',
    'scripts/refresh_private_market_denylists.py',
    'scripts/reminder_disclosure.py',
    'scripts/test_public_safety.py',
}
SEMANTIC_PUBLIC_FILES = {
    'metadata/timetable-history.json',
    'metadata/timetable-pulses.json',
    'metadata/timetable-reminder-translations.json',
    'src/timetable/timetable-data.js',
}

def scrub_allowed_tokens(line: str) -> str:
    """Remove explicitly public names/URLs without exempting the rest of a line."""
    result = line
    for token in ALLOWED_TOKENS:
        result = result.replace(token, "")
    return result

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser.parse_args()


def main(root: Path) -> int:
    findings = []
    root = root.resolve()
    identity_terms = load_private_denylist(
        root / '.private' / IDENTITY_DENYLIST.name,
        'identities',
    )
    for path in root.rglob('*'):
        if path.is_dir() or any(part in SKIP_DIRS for part in path.parts):
            continue
        rel = path.relative_to(root).as_posix()
        if rel in SKIP_FILES or any(rel.startswith(prefix) for prefix in SKIP_PREFIXES):
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        if rel in SEMANTIC_PUBLIC_FILES or (
            rel.startswith('docs/timetable/')
            and path.suffix.lower() in {'.html', '.js', '.json'}
        ):
            semantic_tags = semantic_risk_tags(text)
            for tag in semantic_tags:
                findings.append((rel, 0, f'semantic_private_context:{tag}', '[value withheld]'))
        for i, line in enumerate(text.splitlines(), 1):
            scan_line = scrub_allowed_tokens(line)
            if denied_terms_present(scan_line, identity_terms):
                findings.append((rel, i, 'private_identity', '[value withheld]'))
            for name, rx in PATTERNS:
                if rx.search(scan_line):
                    findings.append((rel, i, name, line.strip()[:220]))
            if rel == "metadata/timetable-history.json":
                for name, rx in (
                    ("spouse_activity", SPOUSE_ACTIVITY_RE),
                    ("education_identity", EDUCATION_IDENTITY_RE),
                    ("proposal_title_context", PROPOSAL_TITLE_CONTEXT_RE),
                ):
                    if rx.search(line):
                        findings.append((rel, i, name, line.strip()[:220]))
            if rel == "metadata/timetable-pulses.json" and PULSE_PRIVATE_ID_RE.search(line):
                findings.append((rel, i, "cron_private_identifier", line.strip()[:220]))
    if findings:
        print('Public safety scan found possible issues:')
        for rel, i, name, line in findings:
            print(f'- {rel}:{i} [{name}] {line}')
        return 1
    print('Public safety scan passed.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main(parse_args().root))
