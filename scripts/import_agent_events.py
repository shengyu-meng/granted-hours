#!/usr/bin/env python3
"""Backfill evidence-bound Codex/GPT/Claude/subagent foreground events."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sqlite3
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DB = Path.home() / ".hermes" / "profiles" / "heizhou" / "state.db"
DEFAULT_DAYS = ROOT / "metadata" / "days.json"
DEFAULT_HISTORY = ROOT / "metadata" / "timetable-history.json"
TIMEZONE = ZoneInfo("Asia/Shanghai")
HISTORY_SCHEMA = "granted-hours-timetable-history-v3"
FIXED_REDACTION_BLOCK = "████"
MAX_HISTORY_RESIDUES = 6
MAX_AGENT_SESSION_MINUTES = 6 * 60

POSITIVE_COMPLETION_RE = re.compile(
    r"(?ix)\b(?:completed|implemented|created|built|fixed|finished|done|passed|"
    r"reviewed|delivered|generated|wrote|produced|verified|validated)\b"
    r"|(?:已|已经|现已)?(?:完成|实现|修复|通过|交付|生成|写完|制作|审校|核验|验收)"
)
REJECTED_OUTCOME_RE = re.compile(
    r"(?ix)"
    r"\b(?:not\s+(?:completed|finished|done|implemented|fixed|delivered|ready)|"
    r"did\s+not\s+(?:complete|finish|implement|fix|deliver|pass)|"
    r"could\s+not|couldn't|cannot|can't|unable\s+to|"
    r"fail(?:ed|ure)?|unfinished|in[- ]?progress|still\s+(?:working|running)|"
    r"work\s+remains?|remaining\s+work|blocked)\b"
    r"|未完成|没有完成|没完成|无法完成|不能完成|失败|未通过|尚未(?:完成|结束)|"
    r"仍在(?:进行|处理|工作)|还在(?:进行|处理|工作)|正在(?:进行|处理)|卡住"
)
QUOTED_SPAN_RE = re.compile(
    r"(?s)```.*?```|`[^`\n]*`|\"[^\"\n]*\"|'[^'\n]*'|"
    r"“[^”\n]*”|‘[^’\n]*’|「[^」\n]*」|『[^』\n]*』"
)
CATEGORY_PATTERNS = {
    "code_development": (
        re.compile(r"(?ix)\b(?:code|coding|implement|implementation|develop|debug|bug|fix|refactor|test|build|script|api|ui|web|app)\b|编码|开发|实现|调试|修复|重构|测试|脚本|网页|应用"),
        4,
    ),
    "document_processing": (
        re.compile(r"(?ix)\b(?:ppt|powerpoint|presentation|slides?|deck|document|docx|write|writing|draft|article|copy|editorial|edit)\b|PPT|演示文稿|幻灯片|文档|写稿|写作|起草|文稿|文章|审校|编辑"),
        5,
    ),
    "visual_production": (
        re.compile(r"(?ix)\b(?:visual|image|graphic|poster|thumbnail|illustration|render|layout|design|screenshot)\b|视觉|图像|图片|海报|缩略图|插画|渲染|排版|设计|截图"),
        4,
    ),
    "research_synthesis": (
        re.compile(r"(?ix)\b(?:research|investigate|analysis|analy[sz]e|evidence|source|audit|review|verify|fact[- ]?check|synthesis)\b|调研|研究|分析|证据|来源|审计|审查|复核|核验|验收|综述"),
        3,
    ),
    "social_media_organization": (
        re.compile(r"(?ix)\b(?:social|post|publish|weibo|twitter|newsletter|content\s+queue)\b|社交媒体|微博|推文|发布|内容队列"),
        3,
    ),
    "system_maintenance": (
        re.compile(r"(?ix)\b(?:maintenance|backup|deploy|health|cron|system|config|upgrade|migration|monitor)\b|系统|维护|备份|部署|健康检查|配置|升级|迁移|监控"),
        2,
    ),
}
EVENT_PRIORITY = {
    "document_processing": 0,
    "visual_production": 1,
    "code_development": 2,
    "research_synthesis": 3,
    "social_media_organization": 4,
    "system_maintenance": 5,
}
AGENT_LABEL_ORDER = ("Codex", "GPT", "Claude", "subagent")


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict) -> bool:
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if serialized == existing:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(serialized)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass
    return True


def _public_dates(path: Path) -> list[str]:
    source = read_json(path)
    if not isinstance(source, list):
        raise ValueError("Public days must be a list")
    dates = sorted(
        str(entry.get("date", ""))
        for entry in source
        if isinstance(entry, dict)
    )
    if not dates or any(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None for value in dates):
        raise ValueError("Public days contain an invalid date")
    for value in dates:
        date.fromisoformat(value)
    return dates


def _classify(_task: str, result: str) -> str | None:
    """Classify only when the terminal result itself names the delivered work."""
    scores: list[tuple[int, int, str]] = []
    for category, (pattern, weight) in CATEGORY_PATTERNS.items():
        matches = pattern.findall(result)
        if matches:
            scores.append((len(matches) * weight, -EVENT_PRIORITY[category], category))
    return max(scores)[2] if scores else None


def _agent_labels(source: str, model: str) -> tuple[str, ...]:
    """Derive public actor labels from trusted session metadata only."""
    labels = set()
    lowered_model = model.casefold()
    if source == "cli":
        labels.add("Codex")
    if "gpt" in lowered_model:
        labels.add("GPT")
    if "claude" in lowered_model:
        labels.add("Claude")
    if source == "subagent":
        labels.add("subagent")
    return tuple(label for label in AGENT_LABEL_ORDER if label in labels)


def _is_positive_terminal_result(result: str) -> bool:
    """Admit an unquoted positive outcome and reject any terminal uncertainty."""
    unquoted = QUOTED_SPAN_RE.sub(" ", result)
    if REJECTED_OUTCOME_RE.search(unquoted):
        return False
    return POSITIVE_COMPLETION_RE.search(unquoted) is not None


def _observed_window(started_at: object, ended_at: object) -> tuple[str, str, str] | None:
    """Return a bounded same-day observed window rounded outward to minutes."""
    try:
        start_value = float(started_at)
        end_value = float(ended_at)
    except (TypeError, ValueError, OverflowError):
        return None
    if (
        not math.isfinite(start_value)
        or not math.isfinite(end_value)
        or end_value < start_value
        or end_value - start_value > MAX_AGENT_SESSION_MINUTES * 60
    ):
        return None
    try:
        start_at = datetime.fromtimestamp(start_value, TIMEZONE)
        end_at = datetime.fromtimestamp(end_value, TIMEZONE)
    except (OSError, OverflowError, ValueError):
        return None
    if start_at.date() != end_at.date():
        return None
    start_minute = start_at.hour * 60 + start_at.minute
    end_minute = end_at.hour * 60 + end_at.minute
    if end_at.second or end_at.microsecond:
        end_minute += 1
    end_minute = max(end_minute, start_minute + 1)
    if end_minute > 24 * 60:
        return None
    end_clock = "24:00" if end_minute == 24 * 60 else f"{end_minute // 60:02d}:{end_minute % 60:02d}"
    return (
        start_at.date().isoformat(),
        f"{start_minute // 60:02d}:{start_minute % 60:02d}",
        end_clock,
    )


def _subtypes(category: str, text: str) -> tuple[str, ...]:
    candidates = {
        "code_development": (
            (r"(?i)\b(?:code|coding|implement|develop|debug|fix|refactor)\b|编码|开发|实现|调试|修复|重构", "coding"),
            (r"(?i)\b(?:test|qa|review|verify|audit)\b|测试|审校|复核|审计|验收", "review"),
        ),
        "document_processing": (
            (r"(?i)\b(?:ppt|powerpoint|presentation|slides?|deck)\b|PPT|演示文稿|幻灯片", "PPT"),
            (r"(?i)\b(?:write|writing|draft|article|copy)\b|写稿|写作|起草|文稿|文章", "writing"),
            (r"(?i)\b(?:review|edit|editorial|proofread)\b|审校|编辑|复核", "review"),
        ),
        "visual_production": (
            (r"(?i)\b(?:visual|image|graphic|design|render|layout)\b|视觉|图像|设计|渲染|排版", "visual production"),
        ),
        "research_synthesis": (
            (r"(?i)\b(?:research|investigate|analysis|synthesis)\b|调研|研究|分析|综述", "research"),
            (r"(?i)\b(?:review|audit|verify|evidence|fact[- ]?check)\b|审查|审计|核验|证据|验收", "review"),
        ),
        "social_media_organization": (
            (r"(?i)\b(?:social|post|publish|content)\b|社交媒体|发布|内容", "social-media organization"),
        ),
        "system_maintenance": (
            (r"(?i)\b(?:maintenance|backup|deploy|health|system)\b|系统|维护|备份|部署|健康检查", "system maintenance"),
        ),
    }
    values = [
        label
        for pattern, label in candidates[category]
        if re.search(pattern, text)
    ]
    return tuple(dict.fromkeys(values)) or (category.replace("_", " "),)


def _summary(
    category: str,
    labels: tuple[str, ...],
    subtypes: tuple[str, ...],
    day_date: str,
) -> tuple[str, str]:
    agent_en = "/".join(labels)
    agent_zh = "/".join(
        "子 Agent" if label == "subagent" else label for label in labels
    )
    joined = ", ".join(subtypes[:-1]) + (
        f" and {subtypes[-1]}" if len(subtypes) > 1 else subtypes[0]
    )
    if category == "code_development":
        en = f"On {day_date}, {agent_en} completed evidence-backed {joined} for {FIXED_REDACTION_BLOCK}; an implementation or validation result was returned."
        zh = f"{day_date}，{agent_zh} 完成 {FIXED_REDACTION_BLOCK} 的编码与审校，并返回实现或验收结果。"
    elif category == "document_processing":
        en = f"On {day_date}, {agent_en} completed evidence-backed {joined} for {FIXED_REDACTION_BLOCK}; a finished document result was returned."
        zh = f"{day_date}，{agent_zh} 完成 {FIXED_REDACTION_BLOCK} 的 PPT、写稿或审校，并返回成品结果。"
    elif category == "visual_production":
        en = f"On {day_date}, {agent_en} completed evidence-backed {joined} for {FIXED_REDACTION_BLOCK}; a visual result was returned."
        zh = f"{day_date}，{agent_zh} 完成 {FIXED_REDACTION_BLOCK} 的视觉制作，并返回视觉结果。"
    elif category == "research_synthesis":
        en = f"On {day_date}, {agent_en} completed evidence-backed {joined} for {FIXED_REDACTION_BLOCK}; findings or review results were returned."
        zh = f"{day_date}，{agent_zh} 完成 {FIXED_REDACTION_BLOCK} 的调研与审校，并返回发现或核验结果。"
    elif category == "social_media_organization":
        en = f"On {day_date}, {agent_en} completed evidence-backed {joined} for {FIXED_REDACTION_BLOCK}; an organized result was returned."
        zh = f"{day_date}，{agent_zh} 完成 {FIXED_REDACTION_BLOCK} 的内容整理，并返回整理结果。"
    else:
        en = f"On {day_date}, {agent_en} completed evidence-backed {joined} for {FIXED_REDACTION_BLOCK}; a maintenance result was returned."
        zh = f"{day_date}，{agent_zh} 完成 {FIXED_REDACTION_BLOCK} 的系统维护，并返回维护结果。"
    if len(en) > 300 or len(zh) > 90:
        raise ValueError("Agent event summary exceeded its public bounds")
    return en, zh


def collect_agent_events(
    state_db_path: Path,
    public_dates: list[str],
    *,
    excluded_parent_sources: set[str] | None = None,
) -> dict[str, list[dict]]:
    if not state_db_path.exists():
        raise ValueError("Hermes state database does not exist")
    first = datetime.combine(
        date.fromisoformat(public_dates[0]),
        datetime.min.time(),
        tzinfo=TIMEZONE,
    ).timestamp()
    last = datetime.combine(
        date.fromisoformat(public_dates[-1]) + timedelta(days=1),
        datetime.min.time(),
        tzinfo=TIMEZONE,
    ).timestamp()
    connection = sqlite3.connect(state_db_path)
    try:
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(sessions)")}
        parent_select = "COALESCE(parent.source, '')" if "parent_session_id" in columns else "''"
        parent_join = "LEFT JOIN sessions AS parent ON parent.id = s.parent_session_id" if "parent_session_id" in columns else ""
        rows = connection.execute(
            f"""
            SELECT s.id, s.source, COALESCE(s.model, ''), s.started_at,
                   s.ended_at,
                   m.role, COALESCE(m.content, ''), m.timestamp, {parent_select}
            FROM sessions AS s
            JOIN messages AS m ON m.session_id = s.id
            {parent_join}
            WHERE s.source IN ('cli', 'subagent')
              AND s.started_at >= ? AND s.started_at < ?
              AND s.ended_at IS NOT NULL
              AND COALESCE(m.active, 1) = 1
              AND m.role IN ('user', 'assistant')
            ORDER BY s.started_at, s.id, m.timestamp, m.id
            """,
            (first, last),
        ).fetchall()
    finally:
        connection.close()

    grouped_messages: dict[str, dict] = {}
    for session_id, source, model, started_at, ended_at, role, content, _timestamp, parent_source in rows:
        record = grouped_messages.setdefault(
            str(session_id),
            {
                "source": str(source),
                "model": str(model),
                "started_at": started_at,
                "ended_at": ended_at,
                "parent_source": str(parent_source),
                "user": [],
                "assistant": [],
            },
        )
        if content.strip():
            record[role].append(content.strip())

    evidence_by_date: dict[str, list[dict]] = defaultdict(list)
    allowed_dates = set(public_dates)
    seen_evidence: set[tuple[object, ...]] = set()
    for record in grouped_messages.values():
        if record["parent_source"] in (excluded_parent_sources or set()):
            continue
        task = "\n".join(record["user"])[:100_000]
        result = record["assistant"][-1][:100_000] if record["assistant"] else ""
        if not task or not result or not _is_positive_terminal_result(result):
            continue
        observed = _observed_window(record["started_at"], record["ended_at"])
        if observed is None:
            continue
        day_date, start, end = observed
        if day_date not in allowed_dates:
            continue
        category = _classify(task, result)
        if category is None:
            continue
        labels = _agent_labels(record["source"], record["model"])
        if not labels:
            continue
        evidence_identity = (
            record["source"],
            record["model"],
            record["started_at"],
            record["ended_at"],
            task,
            result,
        )
        if evidence_identity in seen_evidence:
            continue
        seen_evidence.add(evidence_identity)
        subtypes = _subtypes(category, result)
        en, zh = _summary(category, labels, subtypes, day_date)
        evidence_by_date[day_date].append(
            {
                "category": category,
                "en": en,
                "zh": zh,
                "redaction_status": "partial",
                "redaction_count": 1,
                "source_kind": "agent_session",
                "faithfulness": "faithful_summary",
                "evidence_count": 1,
                "agent_labels": list(labels),
                "start": start,
                "end": end,
                "time_provenance": "observed_session_window",
            }
        )

    for events in evidence_by_date.values():
        events.sort(
            key=lambda event: (
                EVENT_PRIORITY[event["category"]],
                event["start"],
                event["end"],
                event["en"],
            )
        )
    return dict(evidence_by_date)


def _merge_history(
    history: dict,
    events_by_date: dict[str, list[dict]],
    *,
    max_events_per_day: int,
) -> dict:
    if history.get("schema") != HISTORY_SCHEMA or not isinstance(history.get("days"), list):
        raise ValueError("History has an invalid schema")
    merged_days = []
    for entry in history["days"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("assigned_residues"), list):
            raise ValueError("History contains an invalid day")
        existing = [
            residue
            for residue in entry["assigned_residues"]
            if not (
                isinstance(residue, dict)
                and residue.get("source_kind") == "agent_session"
            )
        ]
        available = max(0, MAX_HISTORY_RESIDUES - len(existing))
        selected = events_by_date.get(str(entry.get("date")), [])[
            : min(max_events_per_day, available)
        ]
        merged_days.append(
            {
                **entry,
                "assigned_residues": [*selected, *existing],
            }
        )
    return {**history, "days": merged_days}


def import_agent_events(
    *,
    state_db_path: Path = DEFAULT_STATE_DB,
    days_path: Path = DEFAULT_DAYS,
    history_path: Path = DEFAULT_HISTORY,
    max_events_per_day: int = 3,
    dry_run: bool = False,
) -> dict:
    if not 1 <= max_events_per_day <= 3:
        raise ValueError("max_events_per_day must be between 1 and 3")
    public_dates = _public_dates(days_path)
    history = read_json(history_path)
    events_by_date = collect_agent_events(state_db_path, public_dates)
    merged = _merge_history(
        history,
        events_by_date,
        max_events_per_day=max_events_per_day,
    )
    inserted = [
        residue
        for entry in merged["days"]
        for residue in entry["assigned_residues"]
        if isinstance(residue, dict) and residue.get("source_kind") == "agent_session"
    ]
    category_counts = Counter(residue["category"] for residue in inserted)
    category_dates: dict[str, set[str]] = defaultdict(set)
    for entry in merged["days"]:
        for residue in entry["assigned_residues"]:
            if isinstance(residue, dict) and residue.get("source_kind") == "agent_session":
                category_dates[residue["category"]].add(entry["date"])
    event_dates = sorted(
        entry["date"]
        for entry in merged["days"]
        if any(
            isinstance(residue, dict)
            and residue.get("source_kind") == "agent_session"
            for residue in entry["assigned_residues"]
        )
    )
    serialized = json.dumps(merged, ensure_ascii=False, indent=2) + "\n"
    changed = serialized != history_path.read_text(encoding="utf-8")
    if changed and not dry_run:
        _write_json(history_path, merged)
    return {
        "changed": changed,
        "event_dates": event_dates,
        "category_counts": dict(sorted(category_counts.items())),
        "category_date_counts": {
            category: len(category_dates[category])
            for category in sorted(category_dates)
        },
        "event_count": len(inserted),
        "history": merged,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-db", type=Path, default=DEFAULT_STATE_DB)
    parser.add_argument("--days", type=Path, default=DEFAULT_DAYS)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--max-events-per-day", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = import_agent_events(
            state_db_path=args.state_db,
            days_path=args.days,
            history_path=args.history,
            max_events_per_day=args.max_events_per_day,
            dry_run=args.dry_run,
        )
    except (
        OSError,
        ValueError,
        TypeError,
        OverflowError,
        sqlite3.Error,
        json.JSONDecodeError,
    ):
        print("Agent event import failed.", file=sys.stderr)
        return 1
    mode = "would write" if args.dry_run else "wrote"
    if not result["changed"]:
        mode = "already current"
    aggregates = "; ".join(
        f"{category}: events={count}, dates={result['category_date_counts'][category]}"
        for category, count in result["category_counts"].items()
    ) or "none: events=0, dates=0"
    print(f"Agent events {mode}; category aggregates: {aggregates}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
