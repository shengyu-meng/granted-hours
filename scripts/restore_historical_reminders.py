#!/usr/bin/env python3
"""Restore previously public reminder projections without reviving private text.

The recovery source must be a tracked historical public snapshot. Legacy v2
copy is rechecked with the current private denylists and semantic policy before
it is admitted to the current v6 snapshot. Existing reminder footprints win;
only genuinely missing date/time-bucket records are restored.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from import_timetable_pulses import (
    DEFAULT_PUBLIC_IDENTITY_ALLOWLIST,
    DEFAULT_SNAPSHOT,
    DISCLOSURE_AUTHORIZATION,
    DISCLOSURE_POLICY,
    FIXED_REDACTION_BLOCK,
    PROJECTION_PROVENANCE,
    PULSE_SNAPSHOT_SCHEMA,
    REMINDER_TRANSLATION_PROVENANCE,
    clock_minutes,
    load_private_redaction_terms,
    mask_token_count,
    parity_preserving_reminder_fields,
    projection_kind_for_counts,
)
from public_projection_privacy import replace_private_terms
from reminder_disclosure import REDACTION_POLICY
from semantic_public_policy import (
    abstract_for_tags,
    abstract_sensitive_public_text,
    projection_tags,
    semantic_abstraction_is_complete,
)

REDUCED_REMINDER_SUMMARY = (
    "日常计划与优先级复核。",
    "Daily planning and priority review.",
)


def fail(message: str) -> None:
    raise SystemExit(message)


def read_revision_snapshot(revision: str) -> dict:
    try:
        payload = subprocess.check_output(
            [
                "git",
                "show",
                f"{revision}:metadata/timetable-pulses.json",
            ]
        )
    except (OSError, subprocess.CalledProcessError) as error:
        fail(f"Could not read the historical public reminder snapshot: {error}")
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        fail("Historical public reminder snapshot is not valid JSON")


def sanitize_field(value: str, private_terms: tuple[str, ...]) -> str:
    return replace_private_terms(
        value,
        private_terms,
        FIXED_REDACTION_BLOCK,
    )


def migrate_reminder(pulse: dict, private_terms: tuple[str, ...]) -> dict:
    required = {
        "summary_original",
        "summary_en",
        "excerpt_original",
        "excerpt_en",
        "original_language",
        "public_label_zh",
        "public_label_en",
    }
    if not required.issubset(pulse):
        fail("Historical reminder projection is incomplete")

    original = sanitize_field(str(pulse["summary_original"]), private_terms)
    english = sanitize_field(str(pulse["summary_en"]), private_terms)
    original_abstracted, original_tags = abstract_sensitive_public_text(original)
    english_abstracted, english_tags = abstract_sensitive_public_text(english)
    tags = tuple(dict.fromkeys((*original_tags, *english_tags)))

    if (
        set(original_tags) != set(english_tags)
        or mask_token_count(original_abstracted, "Historical reminder source")
        != mask_token_count(english_abstracted, "Historical reminder translation")
    ):
        if not tags:
            fail("Historical reminder mask parity changed without a semantic abstraction")
        original_abstracted = abstract_for_tags(tags, "zh")
        english_abstracted = abstract_for_tags(tags, "en")

    if not semantic_abstraction_is_complete(original_abstracted):
        fail("Historical Chinese reminder still contains semantic risk")
    if not semantic_abstraction_is_complete(english_abstracted):
        fail("Historical English reminder still contains semantic risk")

    (
        original_abstracted,
        english_abstracted,
        excerpt_original,
        excerpt_en,
    ) = parity_preserving_reminder_fields(
        original_abstracted,
        english_abstracted,
    )
    redaction_count = mask_token_count(
        original_abstracted,
        "Migrated historical reminder",
    )
    return {
        **{
            key: pulse[key]
            for key in (
                "start",
                "end",
                "duration_minutes",
                "execution_minutes",
                "time_bucket",
                "category",
                "count",
                "time_provenance",
                "owner_scope",
                "ownership_provenance",
                "public_label_zh",
                "public_label_en",
                "original_language",
            )
        },
        "summary_provenance": PROJECTION_PROVENANCE,
        "projection_kind": projection_kind_for_counts(
            redaction_count,
            len(tags),
        ),
        "redaction_policy": REDACTION_POLICY,
        "redaction_count": redaction_count,
        "semantic_abstraction_count": len(tags),
        "summary_original": original_abstracted,
        "excerpt_original": excerpt_original,
        "disclosure_policy": DISCLOSURE_POLICY,
        "disclosure_authorization": DISCLOSURE_AUTHORIZATION,
        "projection_provenance": PROJECTION_PROVENANCE,
        "summary_en": english_abstracted,
        "excerpt_en": excerpt_en,
        "translation_provenance": REMINDER_TRANSLATION_PROVENANCE,
    }


def matching_reminder_index(existing: list[dict], candidate: dict) -> int | None:
    eligible: list[tuple[int, int]] = []
    for index, pulse in enumerate(existing):
        if pulse.get("category") != "daily_reminder":
            continue
        if (
            pulse.get("time_bucket") != candidate.get("time_bucket")
            or pulse.get("count") != candidate.get("count")
        ):
            continue
        try:
            delta = abs(
                clock_minutes(str(pulse["end"]))
                - clock_minutes(str(candidate["end"]))
            )
        except (KeyError, TypeError, ValueError):
            continue
        if delta <= 30:
            eligible.append((delta, index))
    return min(eligible)[1] if eligible else None


def matching_reduced_routine_index(
    existing: list[dict],
    candidate: dict,
) -> int | None:
    eligible: list[tuple[int, int]] = []
    for index, pulse in enumerate(existing):
        if (
            pulse.get("category") != "background_routine"
            or (
                pulse.get("summary_zh"),
                pulse.get("summary_en"),
            )
            != REDUCED_REMINDER_SUMMARY
            or pulse.get("time_bucket") != candidate.get("time_bucket")
            or pulse.get("count") != candidate.get("count")
        ):
            continue
        try:
            delta = abs(
                clock_minutes(str(pulse["end"]))
                - clock_minutes(str(candidate["end"]))
            )
        except (KeyError, TypeError, ValueError):
            continue
        if delta <= 30:
            eligible.append((delta, index))
    return min(eligible)[1] if eligible else None


def restore_snapshot(
    current: dict,
    historical: dict,
    private_terms: tuple[str, ...],
) -> tuple[dict, dict[str, int]]:
    if current.get("schema") != PULSE_SNAPSHOT_SCHEMA:
        fail("Current reminder recovery requires the v6 pulse snapshot")
    current_days = current.get("days")
    historical_days = historical.get("days")
    if not isinstance(current_days, list) or not isinstance(historical_days, list):
        fail("Reminder recovery snapshots require day lists")
    by_date = {
        day["date"]: {**day, "pulses": [dict(pulse) for pulse in day["pulses"]]}
        for day in current_days
    }
    stats = {
        "historical_reminders": 0,
        "already_present": 0,
        "upgraded_withheld": 0,
        "removed_reduced_routines": 0,
        "restored": 0,
    }
    for historical_day in historical_days:
        day_date = historical_day.get("date")
        if day_date not in by_date:
            continue
        pulses = by_date[day_date]["pulses"]
        for pulse in historical_day.get("pulses", []):
            if pulse.get("category") != "daily_reminder":
                continue
            stats["historical_reminders"] += 1
            existing_index = matching_reminder_index(pulses, pulse)
            if existing_index is not None:
                existing = pulses[existing_index]
                if (
                    existing.get("disclosure_policy") == DISCLOSURE_POLICY
                    and isinstance(existing.get("summary_original"), str)
                    and isinstance(existing.get("summary_en"), str)
                ):
                    stats["already_present"] += 1
                    continue
                pulses[existing_index] = migrate_reminder(pulse, private_terms)
                stats["upgraded_withheld"] += 1
                continue
            reduced_index = matching_reduced_routine_index(pulses, pulse)
            if reduced_index is not None:
                pulses.pop(reduced_index)
                stats["removed_reduced_routines"] += 1
            pulses.append(migrate_reminder(pulse, private_terms))
            stats["restored"] += 1
        pulses.sort(key=lambda item: (clock_minutes(item["start"]), item["category"]))
    return (
        {**current, "days": [by_date[day["date"]] for day in current_days]},
        stats,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-revision", required=True)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--private-redaction-terms", type=Path, required=True)
    parser.add_argument(
        "--public-identity-allowlist",
        type=Path,
        default=DEFAULT_PUBLIC_IDENTITY_ALLOWLIST,
    )
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    current = json.loads(args.snapshot.read_text(encoding="utf-8"))
    historical = read_revision_snapshot(args.legacy_revision)
    private_terms = load_private_redaction_terms(
        args.private_redaction_terms,
        args.public_identity_allowlist,
    )
    restored, stats = restore_snapshot(current, historical, private_terms)
    if args.write:
        args.snapshot.write_text(
            json.dumps(restored, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({"write": args.write, **stats}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
