#!/usr/bin/env python3
"""Build public-safe, evidence-rich calendar windows from real cron runs.

The importer reads only the final ``## Response`` section of run receipts and
reduces it to a tiny fixed-vocabulary status summary. Raw job names, IDs,
prompts, output text, delivery targets, accounts, holdings, and source paths are
never written to the snapshot.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
from collections import defaultdict
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from reminder_disclosure import (
    ACTION_PROVENANCE as LIMITED_ACTION_PROVENANCE,
    DISCLOSURE_AUTHORIZATION,
    DISCLOSURE_POLICY,
    FIXED_REDACTION_BLOCK,
    project_limited_reminder_response,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_DAYS = ROOT / "metadata" / "days.json"
DEFAULT_SNAPSHOT = ROOT / "metadata" / "timetable-pulses.json"
DEFAULT_STATE_DB = Path.home() / ".hermes" / "profiles" / "heizhou" / "state.db"
TIMEZONE = ZoneInfo("Asia/Shanghai")
PULSE_SNAPSHOT_SCHEMA = "granted-hours-timetable-pulses-v4"

NESTED_RUN_RE = re.compile(r"^(?P<stamp>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.(?:md|txt)$")
FLAT_RUN_RE = re.compile(
    r"^(?P<job>.+)_(?P<stamp>\d{8}_\d{6})\.(?:md|txt)$"
)
PUBLIC_CATEGORIES = {
    "ah_market_scan",
    "us_market_scan",
    "ai_daily_brief",
    "daily_reminder",
    "system_routine",
    "background_routine",
}

US_MARKET_RE = re.compile(
    r"(?i)(?:\bus\b|u\.s\.|nasdaq|nyse|premarket|overnight|wall.?street)"
)
AH_MARKET_RE = re.compile(
    r"(?i)(?:a[- ]?share|\bah\b|hong.?kong|\bhk\b|market|stock|portfolio|"
    r"investment|futu|qmt|sepa|quote|radar|lof|fund|holdings|capflow|"
    r"put|call|equity|allocation|市场|股票|投资|港股|美股|A股)"
)
AI_BRIEF_RE = re.compile(r"(?i)(?:ai[- ]?daily|daily[- ]?brief|AI日报)")
REMINDER_RE = re.compile(
    r"(?i)(?:remind|reminder|gentle|dispatch|回顾|提醒|晚安|日记|reflection)"
)
SYSTEM_RE = re.compile(
    r"(?i)(?:backup|sync|health|update|maintenance|workspace|version|"
    r"full[- ]?loop|calibration|watchdog|archive)"
)
SESSION_ID_RE = re.compile(r"^cron_(?P<job>.+)_(?P<date>\d{8})_(?P<time>\d{6})$")
WARNING_RE = re.compile(r"(?i)(?:失败|异常|不可达|陈旧|新鲜度|警告|stale|warning|error|failed|unreachable)")
NO_ACTION_RE = re.compile(r"(?i)(?:\[SILENT\]|本周无|无直接|不产生直接|无公开动作|no\s+(?:direct\s+)?action)")
DEFENSIVE_RE = re.compile(r"(?i)(?:防守|风险收缩|risk[- ]?off|defensive)")
BALANCED_RE = re.compile(r"(?i)(?:均衡|中性|平衡|balanced|neutral)")
OFFENSIVE_RE = re.compile(r"(?i)(?:进攻|风险扩张|risk[- ]?on|offensive)")
AI_BRIEF_FAILURE_LINE_RE = re.compile(
    r"""(?ix)
    ^\s*(?:\#{1,6}\s*)?
    (?:
        (?:采集异常诊断|采集未达标|不发正常\s*AI\s*日报)
        |
        (?:状态|结论|采集状态)\s*[:：]\s*(?:失败|异常|未达标)
        |
        collection\s+failure
        |
        (?:status|result|collection\s+status)\s*[:：]\s*(?:collection\s+failure|failure|failed|insufficient)
    )
    (?:\s*[:：—-]\s*.*)?\s*$
    """
)
SAFE_MARKET_THEMES = (
    (re.compile(r"(?i)(?:AI\s*硬件|AI hardware|半导体|semiconductor|存储|memory cycle)"), "AI 硬件与半导体", "AI hardware and semiconductors"),
    (re.compile(r"(?i)(?:CPO|光互连|optical interconnect|光通信)"), "光互连", "optical interconnects"),
    (re.compile(r"(?i)(?:机器人|具身智能|robotics|embodied AI)"), "具身智能", "embodied AI"),
    (re.compile(r"(?i)(?:能源|资源|利率|energy|resources|rates|duration pressure)"), "资源与利率", "resources and rates"),
    (re.compile(r"(?i)(?:市场状态|market regime|波动|volatility)"), "市场状态与波动", "market regime and volatility"),
)


def fail(message: str) -> None:
    raise SystemExit(message)


def parse_jobs(path: Path) -> dict[str, str]:
    if not path.exists():
        fail("Cron jobs source does not exist")
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        fail("Could not read cron jobs source")
    except json.JSONDecodeError:
        fail("Cron jobs source is not valid JSON")
    jobs = source.get("jobs") if isinstance(source, dict) else source
    if not isinstance(jobs, list):
        fail("Cron jobs source must contain a jobs list")
    result = {}
    for job in jobs:
        if not isinstance(job, dict):
            continue
        job_id = str(job.get("id", "")).strip()
        if job_id:
            result[job_id] = str(job.get("name", ""))
    return result


def public_dates(path: Path) -> set[str]:
    if not path.exists():
        fail("Public days source does not exist")
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        fail("Could not read public days source")
    except json.JSONDecodeError:
        fail("Public days source is not valid JSON")
    if not isinstance(source, list):
        fail("Public days source must be a list")
    dates = {str(item.get("date", "")) for item in source if isinstance(item, dict)}
    if not dates or "" in dates:
        fail("Every public day must have a date")
    return dates


def parse_run_file(path: Path, output_dir: Path) -> tuple[str, datetime] | None:
    relative = path.relative_to(output_dir)
    if len(relative.parts) == 2:
        match = NESTED_RUN_RE.fullmatch(relative.name)
        if not match:
            return None
        return relative.parts[0], datetime.strptime(match.group("stamp"), "%Y-%m-%d_%H-%M-%S")
    if len(relative.parts) == 1:
        match = FLAT_RUN_RE.fullmatch(relative.name)
        if not match:
            return None
        return match.group("job"), datetime.strptime(match.group("stamp"), "%Y%m%d_%H%M%S")
    return None


def categorize_job(name: str) -> str:
    """Map private job metadata to one of six intentionally coarse labels."""
    if AI_BRIEF_RE.search(name):
        return "ai_daily_brief"
    if US_MARKET_RE.search(name):
        return "us_market_scan"
    if AH_MARKET_RE.search(name):
        return "ah_market_scan"
    if REMINDER_RE.search(name):
        return "daily_reminder"
    if SYSTEM_RE.search(name):
        return "system_routine"
    return "background_routine"


def time_bucket(timestamp: datetime) -> tuple[str, str]:
    """Return a four-hour bucket and a 15-minute coarse display time."""
    buckets = (
        (0, "overnight"),
        (4, "dawn"),
        (7, "morning"),
        (11, "midday"),
        (14, "afternoon"),
        (18, "evening"),
    )
    bucket = max((entry for entry in buckets if timestamp.hour >= entry[0]), key=lambda entry: entry[0])
    coarse_minute = (timestamp.minute // 15) * 15
    return bucket[1], f"{timestamp.hour:02d}:{coarse_minute:02d}"


def deduplicate_runs(runs: list[tuple[str, datetime, Path]]) -> list[tuple[str, datetime, Path]]:
    """Collapse .md/.txt companion receipts emitted within two seconds."""
    result: list[tuple[str, datetime, Path]] = []
    for run in sorted(runs, key=lambda item: (item[0], item[1], -item[2].stat().st_size)):
        if result and result[-1][0] == run[0] and (run[1] - result[-1][1]).total_seconds() <= 2:
            if run[2].stat().st_size > result[-1][2].stat().st_size:
                result[-1] = run
            continue
        result.append(run)
    return result


def load_session_records(path: Path | None) -> dict[str, list[dict]]:
    """Read cron session identities, retaining invalid runs for safe matching.

    Invalid/null sessions remain in the local matching set so that a receipt
    cannot skip over its own failed run and borrow a nearby valid window.
    Session identifiers never enter the public snapshot.
    """
    if path is None or not path.exists():
        return {}
    try:
        with closing(sqlite3.connect(path)) as connection:
            rows = connection.execute(
                "SELECT id, started_at, ended_at FROM sessions WHERE source = 'cron'"
            ).fetchall()
    except sqlite3.Error as error:
        fail(f"Could not read cron session windows: {error}")
    records: dict[str, list[dict]] = defaultdict(list)
    for session_id, started_at, ended_at in rows:
        match = SESSION_ID_RE.fullmatch(str(session_id))
        if match is None or started_at is None:
            continue
        start = datetime.fromtimestamp(float(started_at), TIMEZONE).replace(tzinfo=None)
        end = None
        if ended_at is not None:
            candidate_end = datetime.fromtimestamp(float(ended_at), TIMEZONE).replace(tzinfo=None)
            if start < candidate_end <= start + timedelta(hours=6):
                end = candidate_end
        records[match.group("job")].append({"start": start, "end": end})
    for entries in records.values():
        entries.sort(key=lambda entry: entry["start"])
    return dict(records)


def match_run_windows(
    runs: list[tuple[str, datetime, Path]],
    session_records: dict[str, list[dict]],
) -> dict[Path, tuple[datetime, datetime, str]]:
    """Match each receipt to at most one same-job session in run order.

    The latest unmatched session that actually started before the receipt is
    treated as that receipt's run identity. If that session has a null or
    invalid end, the receipt remains an estimate even when another valid
    same-job session happens to end nearby.
    """
    matches: dict[Path, tuple[datetime, datetime, str]] = {}
    runs_by_job: dict[str, list[tuple[datetime, Path]]] = defaultdict(list)
    for job_id, receipt_time, path in runs:
        runs_by_job[job_id].append((receipt_time, path))

    for job_id, job_runs in runs_by_job.items():
        records = session_records.get(job_id, [])
        used: set[int] = set()
        for receipt_time, path in sorted(job_runs, key=lambda item: (item[0], str(item[1]))):
            eligible = [
                (index, record)
                for index, record in enumerate(records)
                if index not in used
                and record["start"] <= receipt_time
                and receipt_time - record["start"] <= timedelta(hours=6)
            ]
            if not eligible:
                matches[path] = (
                    receipt_time - timedelta(minutes=1),
                    receipt_time,
                    "receipt_fallback",
                )
                continue
            index, record = max(eligible, key=lambda item: item[1]["start"])
            # Any older unmatched session has already been superseded by this
            # receipt's latest pre-receipt identity. Retire all of them now so
            # a later receipt cannot borrow a stale valid window that belonged
            # before an invalid/null run.
            used.update(candidate_index for candidate_index, _ in eligible)
            end = record["end"]
            if end is not None and abs((end - receipt_time).total_seconds()) <= 30 * 60:
                matches[path] = (record["start"], end, "observed_session")
            else:
                matches[path] = (
                    receipt_time - timedelta(minutes=1),
                    receipt_time,
                    "receipt_fallback",
                )
    return matches


def ai_brief_failed(text: str) -> bool:
    """Recognize only explicit line-level failure markers, never prose negation."""
    return any(AI_BRIEF_FAILURE_LINE_RE.fullmatch(line) for line in text.splitlines())


def final_response(path: Path) -> str:
    """Return only the explicit final-response section; prompts are never parsed."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    marker = "\n## Response\n"
    if marker not in text:
        return ""
    return text.rsplit(marker, 1)[-1].strip()[:50_000]


def public_summary(category: str, responses: list[str], count: int) -> tuple[str, str]:
    """Reduce private outputs to fixed-vocabulary, public-safe operational facts."""
    texts = [text for text in responses if text]
    combined = "\n".join(texts)
    silent_count = sum(text.strip() == "[SILENT]" for text in texts)
    warning_count = sum(bool(WARNING_RE.search(text)) for text in texts)
    no_action_count = sum(bool(NO_ACTION_RE.search(text)) for text in texts)

    if category in {"ah_market_scan", "us_market_scan"}:
        label_zh = "A/H 市场扫描" if category == "ah_market_scan" else "美股市场扫描"
        label_en = "A/H market scans" if category == "ah_market_scan" else "U.S. market scans"
        state_candidates = [
            (sum(bool(DEFENSIVE_RE.search(text)) for text in texts), "防守 / 风险收缩", "defensive / risk-contraction"),
            (sum(bool(OFFENSIVE_RE.search(text)) for text in texts), "进攻 / 风险扩张", "offensive / risk-expansion"),
            (sum(bool(BALANCED_RE.search(text)) for text in texts), "均衡 / 中性", "balanced / neutral"),
        ]
        state_score, state_zh, state_en = max(state_candidates, key=lambda item: item[0])
        if state_score == 0:
            state_zh, state_en = "未形成公开级别结论", "no public-level regime conclusion"
        themes = [(zh, en) for pattern, zh, en in SAFE_MARKET_THEMES if pattern.search(combined)][:2]
        theme_zh = "、".join(item[0] for item in themes) if themes else "无额外公开主题"
        theme_en = ", ".join(item[1] for item in themes) if themes else "no additional public theme"
        action_zh = f"{max(silent_count, no_action_count)} 次未形成公开动作信号" if max(silent_count, no_action_count) else "存在公开报告输出"
        action_en = f"{max(silent_count, no_action_count)} run(s) produced no public action signal" if max(silent_count, no_action_count) else "public report output was produced"
        warning_zh = "；存在数据或链路新鲜度警告" if warning_count else "；未检测到公开级别链路警告"
        warning_en = "; data or pipeline-freshness warnings were present" if warning_count else "; no public-level pipeline warning was detected"
        return (
            f"本窗口完成 {count} 次{label_zh}；状态：{state_zh}；{action_zh}{warning_zh}。公开主题：{theme_zh}。",
            f"{count} {label_en} completed in this window; regime: {state_en}; {action_en}{warning_en}. Public themes: {theme_en}.",
        )

    if category == "ai_daily_brief":
        if ai_brief_failed(combined):
            return (
                "AI 日报流程报告采集未达发布闸门，因此没有生成常规日报。",
                "The AI-brief workflow reported that collection did not pass its publication gate, so no normal brief was generated.",
            )
        return (
            f"完成 {count} 次 AI 日报流程；{silent_count} 次静默，{warning_count} 次含公开级别采集警告。",
            f"{count} AI-brief run(s) completed; {silent_count} stayed silent and {warning_count} contained a public-level collection warning.",
        )

    if category == "daily_reminder":
        return (
            "提醒残留。",
            "Reminder residue.",
        )

    if category == "system_routine":
        return (
            f"完成 {count} 次系统例行检查；{silent_count} 次静默正常，{warning_count} 次出现公开级别异常或新鲜度提示。",
            f"{count} system checks completed; {silent_count} were silently healthy and {warning_count} exposed a public-level anomaly or freshness warning.",
        )

    return (
        f"完成 {count} 次后台流程；{silent_count} 次静默，{warning_count} 次出现公开级别异常提示；私有内容未进入日程。",
        f"{count} background run(s) completed; {silent_count} stayed silent and {warning_count} exposed a public-level warning; private content was not imported into the timetable.",
    )


def format_clock(timestamp: datetime, *, end: bool = False) -> str:
    if end and timestamp.hour == 0 and timestamp.minute == 0:
        return "24:00"
    return timestamp.strftime("%H:%M")


def build_snapshot(
    jobs_path: Path,
    output_dir: Path,
    public_days_path: Path,
    state_db_path: Path | None = DEFAULT_STATE_DB,
    *,
    authorize_self_reminders: bool = False,
    authorize_limited_reminder_disclosure: bool = False,
) -> dict:
    if authorize_limited_reminder_disclosure and not authorize_self_reminders:
        fail(
            "Limited reminder disclosure also requires explicit self-reminder authorization"
        )
    job_names = parse_jobs(jobs_path)
    if not output_dir.exists() or not output_dir.is_dir():
        fail("Cron output source does not exist")
    dates = public_dates(public_days_path)
    session_records = load_session_records(state_db_path)
    parsed_runs: list[tuple[str, datetime, Path]] = []
    source_file_count = 0
    for path in sorted(candidate for candidate in output_dir.rglob("*") if candidate.is_file()):
        parsed = parse_run_file(path, output_dir)
        if parsed is None or parsed[1].date().isoformat() not in dates:
            continue
        source_file_count += 1
        parsed_runs.append((*parsed, path))
    runs = deduplicate_runs(parsed_runs)
    run_windows = match_run_windows(runs, session_records)

    evidence_by_day_category: dict[tuple[str, str], list[dict]] = defaultdict(list)
    observed_count = 0
    for job_id, timestamp, path in runs:
        day_date = timestamp.date().isoformat()
        category = categorize_job(job_names.get(job_id, ""))
        start, end, provenance = run_windows[path]
        if provenance == "observed_session":
            observed_count += 1
        day_start = datetime.strptime(day_date, "%Y-%m-%d")
        day_end = day_start + timedelta(days=1)
        start = max(start, day_start)
        end = min(max(end, start + timedelta(minutes=1)), day_end)
        evidence_by_day_category[(day_date, category)].append(
            {
                "start_at": start,
                "end_at": end,
                "category": category,
                "count": 1,
                "execution_seconds": max(60.0, (end - start).total_seconds()),
                "responses": [final_response(path)],
                "observed_count": int(provenance == "observed_session"),
            }
        )

    grouped: dict[str, list[dict]] = defaultdict(list)
    for (day_date, _category), evidence in evidence_by_day_category.items():
        current = None
        for run in sorted(evidence, key=lambda item: (item["start_at"], item["end_at"])):
            if current is not None and run["start_at"] <= current["end_at"] + timedelta(minutes=2):
                current["end_at"] = max(current["end_at"], run["end_at"])
                current["count"] += 1
                current["execution_seconds"] += run["execution_seconds"]
                current["responses"].extend(run["responses"])
                current["observed_count"] += run["observed_count"]
                continue
            current = dict(run)
            grouped[day_date].append(current)

    days = []
    for day_date in sorted(dates):
        pulses = []
        for group in grouped.get(day_date, []):
            display_start = group["start_at"].replace(second=0, microsecond=0)
            display_end = group["end_at"].replace(second=0, microsecond=0)
            if group["end_at"] > display_end:
                display_end += timedelta(minutes=1)
            next_midnight = datetime.combine(
                display_start.date() + timedelta(days=1),
                datetime.min.time(),
            )
            display_end = min(display_end, next_midnight)
            display_end = max(display_end, display_start + timedelta(minutes=1))
            duration_minutes = int((display_end - display_start).total_seconds() // 60)
            bucket, _coarse_time = time_bucket(display_start)
            reminder_projection = None
            if (
                group["category"] == "daily_reminder"
                and authorize_self_reminders
                and authorize_limited_reminder_disclosure
            ):
                reminder_projection = project_limited_reminder_response(
                    group["responses"],
                    bucket,
                )
                summary_zh = reminder_projection["summary_zh"]
                summary_en = reminder_projection["summary_en"]
            else:
                summary_zh, summary_en = public_summary(
                    group["category"],
                    group["responses"],
                    group["count"],
                )
            pulse = {
                "start": format_clock(display_start),
                "end": format_clock(display_end, end=display_end.date() > display_start.date()),
                "duration_minutes": duration_minutes,
                "execution_minutes": max(1, math.ceil(group["execution_seconds"] / 60)),
                "time_bucket": bucket,
                "category": group["category"],
                "count": group["count"],
                "time_provenance": (
                    "observed_session_window"
                    if group["observed_count"] == group["count"]
                    else "receipt_timestamp_estimate"
                    if group["observed_count"] == 0
                    else "mixed_observed_and_receipt"
                ),
                "summary_zh": summary_zh,
                "summary_en": summary_en,
                "summary_provenance": "derived_public_safe",
            }
            if group["category"] == "daily_reminder":
                pulse.update(
                    {
                        "owner_scope": (
                            "self_scheduler_residue"
                            if authorize_self_reminders
                            else "unknown"
                        ),
                        "ownership_provenance": (
                            "explicit_import_authorization"
                            if authorize_self_reminders
                            else "unverified"
                        ),
                        "action_provenance": (
                            LIMITED_ACTION_PROVENANCE
                            if reminder_projection is not None
                            else "no_authorized_action_semantics"
                        ),
                    }
                )
                if reminder_projection is not None:
                    pulse.update(
                        {
                            "disclosure_policy": DISCLOSURE_POLICY,
                            "disclosure_authorization": DISCLOSURE_AUTHORIZATION,
                            "public_label_zh": reminder_projection["label_zh"],
                            "public_label_en": reminder_projection["label_en"],
                            "motif": reminder_projection["motif"],
                            "action_structure": reminder_projection[
                                "action_structure"
                            ],
                            "projection_kind": reminder_projection[
                                "projection_kind"
                            ],
                            "redaction_policy": reminder_projection[
                                "redaction_policy"
                            ],
                            "redaction_count": reminder_projection[
                                "redaction_count"
                            ],
                            "projection_provenance": reminder_projection[
                                "projection_provenance"
                            ],
                        }
                    )
            pulses.append(pulse)
        pulses.sort(key=lambda pulse: (pulse["start"], pulse["category"]))
        days.append({"date": day_date, "pulses": pulses})

    return {
        "schema": PULSE_SNAPSHOT_SCHEMA,
        "timezone": "Asia/Shanghai",
        "source_file_count": source_file_count,
        "deduplicated_run_count": len(runs),
        "observed_session_window_count": observed_count,
        "days": days,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--public-days", type=Path, default=DEFAULT_PUBLIC_DAYS)
    parser.add_argument("--state-db", type=Path, default=DEFAULT_STATE_DB)
    parser.add_argument(
        "--no-session-state",
        action="store_true",
        help="Do not read a session-state database; use receipt timestamp estimates.",
    )
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument(
        "--date",
        dest="dates",
        action="append",
        help=(
            "Replace only this YYYY-MM-DD day in an existing snapshot while "
            "preserving every other public day; repeat for multiple dates."
        ),
    )
    parser.add_argument(
        "--authorize-self-reminder-residues",
        action="store_true",
        help=(
            "Explicitly authorize reminder run residues as self-owned for masked "
            "public projection. Without this flag they are marked unknown and "
            "the timetable builder omits them."
        ),
    )
    parser.add_argument(
        "--authorize-limited-reminder-disclosure",
        action="store_true",
        help=(
            "Apply the explicitly authorized limited-masked reminder policy. "
            "This also requires --authorize-self-reminder-residues."
        ),
    )
    parser.add_argument(
        "--refresh-reminders-only",
        action="store_true",
        help=(
            "Replace reminder evidence from the current receipts while "
            "preserving matching existing public footprints and all "
            "non-reminder pulses."
        ),
    )
    return parser.parse_args()


def merge_date_scoped_snapshot(
    existing_path: Path,
    rebuilt_snapshot: dict,
    requested_dates: set[str],
) -> dict:
    """Merge selected rebuilt days without rewriting older public evidence."""
    if not existing_path.exists():
        fail("Date-scoped pulse import requires an existing snapshot")
    try:
        existing_snapshot = json.loads(existing_path.read_text(encoding="utf-8"))
    except OSError:
        fail("Could not read existing pulse snapshot")
    except json.JSONDecodeError:
        fail("Existing pulse snapshot is not valid JSON")
    if existing_snapshot.get("schema") != PULSE_SNAPSHOT_SCHEMA:
        fail(f"Existing pulse snapshot schema must be {PULSE_SNAPSHOT_SCHEMA}")
    existing_days = existing_snapshot.get("days")
    rebuilt_days = rebuilt_snapshot.get("days")
    if not isinstance(existing_days, list) or not isinstance(rebuilt_days, list):
        fail("Pulse snapshots must contain day lists")
    existing_by_date = {
        entry.get("date"): entry
        for entry in existing_days
        if isinstance(entry, dict)
    }
    rebuilt_by_date = {
        entry.get("date"): entry
        for entry in rebuilt_days
        if isinstance(entry, dict)
    }
    if len(existing_by_date) != len(existing_days):
        fail("Existing pulse snapshot contains an invalid or duplicate date")
    if len(rebuilt_by_date) != len(rebuilt_days):
        fail("Rebuilt pulse snapshot contains an invalid or duplicate date")
    unknown_dates = requested_dates.difference(rebuilt_by_date)
    if unknown_dates:
        fail(f"Requested pulse dates are not public: {', '.join(sorted(unknown_dates))}")
    merged_by_date = dict(existing_by_date)
    for day_date in requested_dates:
        merged_by_date[day_date] = rebuilt_by_date[day_date]
    missing_dates = set(rebuilt_by_date).difference(merged_by_date)
    extra_dates = set(merged_by_date).difference(rebuilt_by_date)
    if missing_dates or extra_dates:
        fail(
            "Date-scoped pulse merge does not match the public day set: "
            f"missing={sorted(missing_dates)}, extra={sorted(extra_dates)}"
        )
    return {
        **rebuilt_snapshot,
        "days": [merged_by_date[day_date] for day_date in sorted(merged_by_date)],
    }


def clock_minutes(value: str) -> int:
    if value == "24:00":
        return 24 * 60
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def merge_reminder_refresh(
    existing_path: Path,
    rebuilt_snapshot: dict,
) -> tuple[dict, dict[str, int]]:
    """Replace reminder evidence while preserving matching public footprints.

    Existing non-reminder pulses are retained exactly. A fresh reminder may
    reuse an existing public timing window only when date, bucket, run count,
    and receipt-adjacent end time all agree. Unmatched fresh reminders keep
    their truthful receipt-timestamp estimate; unmatched old reminders are
    removed as stale.
    """
    if not existing_path.exists():
        fail("Reminder refresh requires an existing public snapshot")
    try:
        existing_snapshot = json.loads(existing_path.read_text(encoding="utf-8"))
    except OSError:
        fail("Could not read existing pulse snapshot")
    except json.JSONDecodeError:
        fail("Existing pulse snapshot is not valid JSON")
    existing_days = existing_snapshot.get("days")
    rebuilt_days = rebuilt_snapshot.get("days")
    if not isinstance(existing_days, list) or not isinstance(rebuilt_days, list):
        fail("Pulse snapshots must contain day lists")
    existing_by_date = {
        entry.get("date"): entry
        for entry in existing_days
        if isinstance(entry, dict)
    }
    rebuilt_by_date = {
        entry.get("date"): entry
        for entry in rebuilt_days
        if isinstance(entry, dict)
    }
    if (
        len(existing_by_date) != len(existing_days)
        or len(rebuilt_by_date) != len(rebuilt_days)
        or set(existing_by_date) != set(rebuilt_by_date)
    ):
        fail("Reminder refresh snapshots must have the same unique public dates")
    existing_reminder_count = sum(
        1
        for day in existing_days
        for pulse in day.get("pulses", [])
        if pulse.get("category") == "daily_reminder"
    )
    fresh_reminder_count = sum(
        1
        for day in rebuilt_days
        for pulse in day.get("pulses", [])
        if pulse.get("category") == "daily_reminder"
    )
    if existing_reminder_count and not fresh_reminder_count:
        fail("Reminder refresh found no fresh reminder evidence")

    stats = {
        "preserved_footprints": 0,
        "receipt_estimate_footprints": 0,
        "removed_stale_reminders": 0,
    }
    observed_session_window_count = int(
        existing_snapshot.get("observed_session_window_count", 0)
    )
    merged_days = []
    for day_date in sorted(rebuilt_by_date):
        old_pulses = existing_by_date[day_date].get("pulses", [])
        fresh_pulses = rebuilt_by_date[day_date].get("pulses", [])
        if not isinstance(old_pulses, list) or not isinstance(fresh_pulses, list):
            fail(f"{day_date} pulse lists are invalid")
        non_reminders = [
            dict(pulse)
            for pulse in old_pulses
            if pulse.get("category") != "daily_reminder"
        ]
        old_reminders = [
            pulse
            for pulse in old_pulses
            if pulse.get("category") == "daily_reminder"
        ]
        fresh_reminders = [
            dict(pulse)
            for pulse in fresh_pulses
            if pulse.get("category") == "daily_reminder"
        ]
        used_old: set[int] = set()
        preserved_fields = (
            "start",
            "end",
            "duration_minutes",
            "execution_minutes",
            "time_provenance",
        )
        for fresh in fresh_reminders:
            eligible = []
            for index, old in enumerate(old_reminders):
                if index in used_old:
                    continue
                if (
                    old.get("time_bucket") != fresh.get("time_bucket")
                    or old.get("count") != fresh.get("count")
                ):
                    continue
                try:
                    end_delta = abs(
                        clock_minutes(str(old["end"]))
                        - clock_minutes(str(fresh["end"]))
                    )
                except (KeyError, TypeError, ValueError):
                    continue
                if end_delta <= 30:
                    eligible.append((end_delta, index, old))
            if eligible:
                _, index, old = min(eligible, key=lambda item: (item[0], item[1]))
                used_old.add(index)
                for field in preserved_fields:
                    fresh[field] = old[field]
                stats["preserved_footprints"] += 1
            else:
                stats["receipt_estimate_footprints"] += 1
                if (
                    fresh.get("time_provenance")
                    == "observed_session_window"
                ):
                    observed_session_window_count += int(
                        fresh.get("count", 0)
                    )
        stats["removed_stale_reminders"] += len(old_reminders) - len(used_old)
        observed_session_window_count -= sum(
            int(old.get("count", 0))
            for index, old in enumerate(old_reminders)
            if index not in used_old
            and old.get("time_provenance") == "observed_session_window"
        )

        combined = [*non_reminders, *fresh_reminders]
        combined.sort(
            key=lambda pulse: (
                clock_minutes(str(pulse.get("start", "00:00"))),
                str(pulse.get("category", "")),
            )
        )
        merged_days.append({"date": day_date, "pulses": combined})

    return (
        {
            **rebuilt_snapshot,
            "observed_session_window_count": observed_session_window_count,
            "days": merged_days,
        },
        stats,
    )


def main() -> int:
    args = parse_args()
    if args.refresh_reminders_only and args.dates:
        fail("--refresh-reminders-only cannot be combined with --date")
    snapshot = build_snapshot(
        args.jobs,
        args.output_dir,
        args.public_days,
        None if args.no_session_state else args.state_db,
        authorize_self_reminders=args.authorize_self_reminder_residues,
        authorize_limited_reminder_disclosure=(
            args.authorize_limited_reminder_disclosure
        ),
    )
    reminder_refresh_stats = None
    if args.refresh_reminders_only:
        snapshot, reminder_refresh_stats = merge_reminder_refresh(
            args.snapshot,
            snapshot,
        )
    if args.dates:
        snapshot = merge_date_scoped_snapshot(
            args.snapshot,
            snapshot,
            set(args.dates),
        )
    args.snapshot.parent.mkdir(parents=True, exist_ok=True)
    args.snapshot.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    empty_dates = [entry["date"] for entry in snapshot["days"] if not entry["pulses"]]
    if empty_dates:
        fail(f"Public dates without cron run evidence: {', '.join(empty_dates)}")
    print(
        "Wrote public timetable pulses: "
        f"{snapshot['source_file_count']} files -> "
        f"{snapshot['deduplicated_run_count']} runs -> "
        f"{sum(len(day['pulses']) for day in snapshot['days'])} pulses across "
        f"{len(snapshot['days'])} dates."
    )
    if reminder_refresh_stats is not None:
        projection_counts: dict[str, int] = defaultdict(int)
        reminder_dates = set()
        for day in snapshot["days"]:
            for pulse in day["pulses"]:
                if pulse["category"] != "daily_reminder":
                    continue
                reminder_dates.add(day["date"])
                projection_counts[pulse.get("projection_kind", "opaque")] += (
                    pulse["count"]
                )
        print(
            "Reminder projection aggregates: "
            f"inner-weather={projection_counts['inner_weather']}, "
            f"masked-only={projection_counts['masked_only']}, "
            f"combined={projection_counts['combined']}, "
            f"opaque={projection_counts['opaque']}, "
            f"date-coverage={len(reminder_dates)}, "
            f"preserved-footprints={reminder_refresh_stats['preserved_footprints']}, "
            f"receipt-estimates={reminder_refresh_stats['receipt_estimate_footprints']}, "
            f"removed-stale={reminder_refresh_stats['removed_stale_reminders']}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
