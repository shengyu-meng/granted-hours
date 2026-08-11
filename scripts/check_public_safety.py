#!/usr/bin/env python3
"""Lightweight public mirror safety scan for 授时 / Granted Hours."""
from __future__ import annotations
import argparse
import re
from pathlib import Path

from public_projection_privacy import (
    denied_terms_present,
    exclude_public_identity_terms,
    load_private_denylist,
    load_public_identity_allowlist,
)
from semantic_public_policy import semantic_risk_tags

ROOT = Path(__file__).resolve().parents[1]
IDENTITY_DENYLIST = ROOT / '.private' / 'identity-denylist.json'
PUBLIC_IDENTITY_ALLOWLIST = ROOT / 'metadata' / 'public-identity-allowlist.json'
LEGACY_COLLABORATION_TEMPLATES = (
    "要求澄清一个工作判断，比较可行路径，并保留后续复核所需的边界。",
    "Requested clarification of a working judgment, comparison of viable paths, and explicit boundaries for later review.",
    "要求调整视觉表达，使构图、层级与生成方法更清楚、更可复核。",
    "Requested a clearer and more reviewable visual treatment across composition, hierarchy, and generation method.",
    "完成了视觉结构调整与结果核验，使主要判断、构图和迭代路径可以逐项检查。",
    "Completed the visual restructuring and result check, making the main judgment, composition, and iteration path reviewable.",
    "要求整理分散的研究线索，核对证据，并把事实、推断与待验证问题分开。",
    "Requested a synthesis of dispersed research threads, with evidence checked and facts, inferences, and open questions kept separate.",
    "要求独立分析一组材料，提炼核心主张、证据强弱、争议点与仍需验证的问题。",
    "Requested an independent analysis of source material, covering its main claims, evidential strength, disputes, and open questions.",
    "要求整理现有材料，改善结构与措辞，并形成可以继续审阅的版本。",
    "Requested that the available material be organized, structurally refined, and turned into a reviewable draft.",
    "要求实现并验证一项开发修改，同时保留可以检查的测试结果。",
    "Requested an implementation and validation pass, with testable evidence retained.",
    "要求整理公开内容的结构、节奏与归档方式。",
    "Requested a clearer structure, cadence, and archive path for public content.",
    "要求修复一项运行或维护问题，并让状态与失败信息更容易阅读。",
    "Requested a repair to an operational or maintenance issue, with status and failure evidence made easier to read.",
    "完成了资料归纳与证据对照，保留可复核结论，并把不确定部分列为后续问题。",
    "Completed a synthesis and evidence comparison, retained reviewable conclusions, and left uncertain points as follow-up questions.",
    "完成了材料整理、结构修订与可读性检查，形成了可继续审阅的版本。",
    "Completed the material consolidation, structural revision, and readability check, producing a reviewable version.",
    "完成了实现、聚焦测试与结果核验，并保留了后续维护所需的边界。",
    "Completed the implementation, focused tests, and result verification, while preserving boundaries needed for maintenance.",
    "完成了公开内容的整理与归档核对，保留了可继续执行的发布节奏。",
    "Completed the public-content organization and archive check, preserving an executable release cadence.",
    "完成了相关维护、试运行与状态核验，并保留了可操作的失败证据。",
    "Completed the relevant maintenance, dry run, and status verification, retaining actionable failure evidence.",
    "完成了判断框架的整理，明确了当前结论、保留意见与下一次复核条件。",
    "Completed a structured judgment, separating the current conclusion, reservations, and conditions for the next review.",
    "当天没有找到可以安全公开、并与这组要求可靠对应的完成记录；不把计划或推断写成已完成。",
    "当天记录未留下与这组要求可靠对应、可安全公开的完成结果；不把计划或推断写成已完成。",
    "公开线未留下可核验的完成结果。",
    "公开线未留下可核验完成结果。",
    "No public-safe completion record was found that reliably matches this request group; plans and inferences are not presented as completed work.",
    "No public-safe completion result reliably matched this request group; plans and inferences are not presented as completed work.",
)
ALLOWED_TOKENS = {
    'shengyu-meng',
    'https://shengyu-meng.github.io/granted-hours/',
    'https://github.com/shengyu-meng/granted-hours',
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
TEXT_SUFFIXES = {
    '.css', '.csv', '.html', '.js', '.json', '.md', '.mjs', '.cjs', '.py',
    '.svg', '.toml', '.txt', '.xml', '.yaml', '.yml',
}
TEXT_FILENAMES = {'LICENSE', 'README', 'CNAME'}
SKIP_PREFIXES = {'audits/', 'scripts/test_'}
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
PUBLIC_MARKET_PRIVATE_RE = re.compile(
    r"(?i)\b(?:QMT|Futu|SWHY|workspace[_ -]?id|workspace[_ -]?dir|"
    r"investment[-_/ ]os|qmt_[a-z0-9_]+|record[_ -]?key)\b|"
    r"\b(?:HK|US|SZ|SH)\.\d{3,6}\b|真实账户|真实仓位|持仓|仓位|试仓"
)
PUBLIC_COPY_META_RE = re.compile(
    r"(?is)结果｜|turns?\s+were\s+compacted|handoff\s+from\s+a\s+previous\s+context|"
    r"具体(?:叙事|身心细节|关系信息|主体和活动信息|平台和技术细节|心理判断|资产、账户和操作)不公开|"
    r"(?:underlying narrative|specific (?:physical|relationship|parties|platform|psychological|assets)).{0,80}remains? private"
)
TIMETABLE_ARTWORK_BRIEF_RE = re.compile(
    r'((?:"(?:brief_en|brief_zh)"|(?:brief_en|brief_zh))\s*:\s*)'
    r'(?:"(?:\\.|[^"\\])*"|`(?:\\.|[^`\\])*`)'
)

def scrub_allowed_tokens(line: str, public_names: tuple[str, ...] = ()) -> str:
    """Remove explicitly public names/URLs without exempting the rest of a line."""
    result = line
    for token in sorted((*ALLOWED_TOKENS, *public_names), key=len, reverse=True):
        result = re.sub(re.escape(token), "", result, flags=re.IGNORECASE)
    return result


def semantic_scan_text(rel: str, text: str) -> str:
    """Keep private-context heuristics off canonical public artwork prose.

    Artwork Brief fields come from the already-public, sanitized work note and
    deliberately use metaphorical words such as "collapse" or "escape". Secret,
    path, identity, and other line-level scans still inspect their original text.
    """
    if rel == "src/timetable/timetable-data.js" or (
        rel.startswith("docs/timetable/assets/") and rel.endswith(".js")
    ):
        return TIMETABLE_ARTWORK_BRIEF_RE.sub(r'\1""', text)
    return text

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser.parse_args()


def main(root: Path) -> int:
    findings = []
    root = root.resolve()
    public_names = load_public_identity_allowlist(
        root / 'metadata' / PUBLIC_IDENTITY_ALLOWLIST.name,
    )
    identity_terms = exclude_public_identity_terms(
        load_private_denylist(
            root / '.private' / IDENTITY_DENYLIST.name,
            'identities',
        ),
        public_names,
    )
    for path in root.rglob('*'):
        if (
            path.is_symlink()
            or path.is_dir()
            or any(part in SKIP_DIRS for part in path.parts)
        ):
            continue
        rel = path.relative_to(root).as_posix()
        if rel in SKIP_FILES or any(rel.startswith(prefix) for prefix in SKIP_PREFIXES):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TEXT_FILENAMES:
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            continue
        if rel in SEMANTIC_PUBLIC_FILES or (
            rel.startswith('docs/timetable/')
            and path.suffix.lower() in {'.html', '.js', '.json'}
        ):
            if rel == "metadata/timetable-history.json":
                for template in LEGACY_COLLABORATION_TEMPLATES:
                    if template in text:
                        findings.append(
                            (rel, 0, 'legacy_collaboration_template', '[value withheld]')
                        )
            semantic_tags = semantic_risk_tags(semantic_scan_text(rel, text))
            for tag in semantic_tags:
                findings.append((rel, 0, f'semantic_private_context:{tag}', '[value withheld]'))
            if PUBLIC_MARKET_PRIVATE_RE.search(text):
                findings.append((rel, 0, 'private_market_operational_context', '[value withheld]'))
            if PUBLIC_COPY_META_RE.search(text):
                findings.append((rel, 0, 'reader_facing_audit_or_handoff_copy', '[value withheld]'))
        for i, line in enumerate(text.splitlines(), 1):
            scan_line = scrub_allowed_tokens(line, public_names)
            # Identity authorization is exact-term only. Scan the untouched
            # line so an allowed short name cannot hide a longer private
            # identity that contains it.
            if denied_terms_present(line, identity_terms):
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
