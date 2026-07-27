#!/usr/bin/env python3
"""Aggregate real cron run filenames into a public-safe timetable snapshot.

The importer never reads cron output contents. It uses only job metadata for a
coarse public category and run filenames for execution evidence. Raw job names,
IDs, delivery targets, and source paths are never written to the snapshot.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_DAYS = ROOT / "metadata" / "days.json"
DEFAULT_SNAPSHOT = ROOT / "metadata" / "timetable-pulses.json"

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


def fail(message: str) -> None:
    raise SystemExit(message)


def parse_jobs(path: Path) -> dict[str, str]:
    if not path.exists():
        fail(f"Cron jobs source does not exist: {path}")
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"Could not read cron jobs source: {error}")
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
        fail(f"Public days source does not exist: {path}")
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"Could not read public days source: {error}")
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


def deduplicate_runs(runs: list[tuple[str, datetime]]) -> list[tuple[str, datetime]]:
    """Collapse .md/.txt companion receipts emitted within two seconds."""
    result: list[tuple[str, datetime]] = []
    previous_by_job: dict[str, datetime] = {}
    for job_id, timestamp in sorted(runs, key=lambda item: (item[0], item[1])):
        previous = previous_by_job.get(job_id)
        if previous is not None and (timestamp - previous).total_seconds() <= 2:
            continue
        result.append((job_id, timestamp))
        previous_by_job[job_id] = timestamp
    return result


def build_snapshot(jobs_path: Path, output_dir: Path, public_days_path: Path) -> dict:
    job_names = parse_jobs(jobs_path)
    if not output_dir.exists() or not output_dir.is_dir():
        fail(f"Cron output source does not exist: {output_dir}")
    dates = public_dates(public_days_path)
    parsed_runs: list[tuple[str, datetime]] = []
    source_file_count = 0
    for path in sorted(candidate for candidate in output_dir.rglob("*") if candidate.is_file()):
        parsed = parse_run_file(path, output_dir)
        if parsed is None or parsed[1].date().isoformat() not in dates:
            continue
        source_file_count += 1
        parsed_runs.append(parsed)
    runs = deduplicate_runs(parsed_runs)

    grouped: dict[tuple[str, str, str], dict] = {}
    for job_id, timestamp in runs:
        day_date = timestamp.date().isoformat()
        bucket, coarse_time = time_bucket(timestamp)
        category = categorize_job(job_names.get(job_id, ""))
        key = (day_date, bucket, category)
        if key not in grouped:
            grouped[key] = {
                "time": coarse_time,
                "time_bucket": bucket,
                "category": category,
                "count": 0,
            }
        grouped[key]["time"] = min(grouped[key]["time"], coarse_time)
        grouped[key]["count"] += 1

    days = []
    for day_date in sorted(dates):
        pulses = [
            value
            for (date_key, _bucket, _category), value in grouped.items()
            if date_key == day_date
        ]
        pulses.sort(key=lambda pulse: (pulse["time"], pulse["category"]))
        days.append({"date": day_date, "pulses": pulses})

    return {
        "schema": "granted-hours-timetable-pulses-v1",
        "timezone": "Asia/Shanghai",
        "source_file_count": source_file_count,
        "deduplicated_run_count": len(runs),
        "days": days,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--public-days", type=Path, default=DEFAULT_PUBLIC_DAYS)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = build_snapshot(args.jobs, args.output_dir, args.public_days)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
