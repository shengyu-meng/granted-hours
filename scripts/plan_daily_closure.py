#!/usr/bin/env python3
"""Build a deterministic, privacy-safe plan for the daily public closure."""
from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
DEFAULT_RECEIPTS = WORKSPACE / "tmp" / "granted-hours-free-roam-ready"
DEFAULT_STATE = WORKSPACE / "tmp" / "granted-hours-daily-closure-state.json"
DEFAULT_DAYS = ROOT / "metadata" / "days.json"


def fail(message: str) -> None:
    raise SystemExit(message)


def parse_day(value: object, context: str) -> str:
    if not isinstance(value, str) or DATE_RE.fullmatch(value) is None:
        fail(f"{context} has an invalid date")
    try:
        date.fromisoformat(value)
    except ValueError:
        fail(f"{context} has an invalid date")
    return value


def read_json(path: Path, context: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        fail(f"Could not read valid {context} JSON")


def public_dates(path: Path) -> set[str]:
    source = read_json(path, "public days")
    entries = source.get("days") if isinstance(source, dict) else source
    if not isinstance(entries, list):
        fail("Public days JSON has no day list")
    values = {
        parse_day(entry.get("date"), "Public day")
        for entry in entries
        if isinstance(entry, dict)
    }
    if len(values) != len(entries):
        fail("Public days contain an invalid or duplicate entry")
    return values


def complete_receipt_dates(path: Path) -> tuple[set[str], list[str]]:
    if not path.is_dir():
        fail("Ready receipt directory does not exist")
    complete: set[str] = set()
    incomplete: list[str] = []
    for receipt_path in sorted(path.glob("*.json")):
        stem_date = parse_day(receipt_path.stem, "Ready receipt filename")
        source = read_json(receipt_path, "ready receipt")
        if not isinstance(source, dict):
            fail("Ready receipt must be an object")
        receipt_date = parse_day(source.get("date"), "Ready receipt")
        if receipt_date != stem_date:
            fail("Ready receipt date disagrees with its filename")
        if source.get("assetsComplete") is True:
            complete.add(receipt_date)
        else:
            incomplete.append(receipt_date)
    return complete, incomplete


def state_dates(source: dict, field: str) -> set[str]:
    values = source.get(field, [])
    if values is None:
        return set()
    if not isinstance(values, list):
        fail(f"Closure state {field} must be a list")
    parsed = {parse_day(value, f"Closure state {field}") for value in values}
    if len(parsed) != len(values):
        fail(f"Closure state {field} contains duplicates")
    return parsed


def build_plan(
    *,
    current_date: str,
    receipts_path: Path,
    state_path: Path,
    days_path: Path,
) -> dict:
    today = parse_day(current_date, "Current date")
    published = public_dates(days_path)
    complete, incomplete = complete_receipt_dates(receipts_path)
    state_source = read_json(state_path, "closure state") if state_path.exists() else {}
    if not isinstance(state_source, dict):
        fail("Closure state must be an object")
    artwork_backlog = state_dates(state_source, "backlog_dates")
    event_backlog = state_dates(state_source, "event_backlog_dates")
    artwork_dates = sorted((complete | artwork_backlog).difference(published))
    if any(value > today for value in artwork_dates):
        fail("Artwork backlog contains a future date")
    eligible_events = {value for value in event_backlog if value < today}
    available_after_artwork = published | set(artwork_dates)
    event_dates = sorted(eligible_events & available_after_artwork)
    waiting_event_dates = sorted(event_backlog.difference(event_dates))
    return {
        "schema": "granted-hours-daily-closure-plan-v1",
        "current_date": today,
        "artwork_dates": artwork_dates,
        "event_dates": event_dates,
        "waiting_event_dates": waiting_event_dates,
        "incomplete_receipt_dates": sorted(set(incomplete).difference(published)),
        "no_change": not artwork_dates and not event_dates,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--current-date",
        default=datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat(),
    )
    parser.add_argument("--receipts", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--days", type=Path, default=DEFAULT_DAYS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(
        json.dumps(
            build_plan(
                current_date=args.current_date,
                receipts_path=args.receipts,
                state_path=args.state,
                days_path=args.days,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
