#!/usr/bin/env python3
"""Prepare private, public-safe reminder translation candidates.

The output contains only entity-masked and semantically abstracted source
copy. It is always written with mode 0600 and must remain under ``.private``.
No missing translation is invented automatically: an AI author reviews this
file, writes a faithful English pair to the tracked catalog, then reruns the
normal authorized importer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import import_timetable_pulses as importer
from public_projection_privacy import (
    assert_private_terms_absent,
    load_private_denylist,
    replace_private_terms,
)


def fail(message: str) -> None:
    raise SystemExit(message)


def sanitize_candidate(
    projection: dict,
    *,
    holdings_terms: tuple[str, ...],
    source_terms: tuple[str, ...],
) -> dict:
    result = dict(projection)
    for field in ("summary_original", "excerpt_original"):
        value = replace_private_terms(
            result[field],
            holdings_terms,
            importer.FIXED_REDACTION_BLOCK,
            contextual_ambiguous=True,
        )
        value = replace_private_terms(
            value,
            source_terms,
            importer.FIXED_REDACTION_BLOCK,
        )
        assert_private_terms_absent(
            value,
            holdings_terms=holdings_terms,
            source_terms=source_terms,
        )
        result[field] = value
    result["excerpt_original"] = importer.extractive_prefix(
        result["summary_original"]
    )
    redaction_count = importer.mask_token_count(
        result["summary_original"],
        "Private reminder translation candidate",
    )
    result["redaction_count"] = redaction_count
    result["projection_kind"] = importer.projection_kind_for_counts(
        redaction_count,
        int(result.get("semantic_abstraction_count", 0)),
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--public-days", type=Path, default=importer.DEFAULT_PUBLIC_DAYS)
    parser.add_argument("--state-db", type=Path, default=importer.DEFAULT_STATE_DB)
    parser.add_argument("--date", dest="dates", action="append", required=True)
    parser.add_argument("--private-redaction-terms", type=Path, required=True)
    parser.add_argument(
        "--public-identity-allowlist",
        type=Path,
        default=importer.DEFAULT_PUBLIC_IDENTITY_ALLOWLIST,
    )
    parser.add_argument(
        "--holdings-denylist",
        type=Path,
        default=importer.DEFAULT_HOLDINGS_DENYLIST,
    )
    parser.add_argument(
        "--self-media-denylist",
        type=Path,
        default=importer.DEFAULT_SELF_MEDIA_DENYLIST,
    )
    parser.add_argument(
        "--reminder-translations",
        type=Path,
        default=importer.DEFAULT_REMINDER_TRANSLATIONS,
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def write_private_json(path: Path, payload: dict) -> None:
    resolved = path.resolve()
    if ".private" not in resolved.parts:
        fail("Reminder translation candidates must stay under a .private directory")
    resolved.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        resolved,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.chmod(resolved, 0o600)


def main() -> int:
    args = parse_args()
    target_dates = set(args.dates)
    holdings_terms = load_private_denylist(args.holdings_denylist, "holdings")
    source_terms = load_private_denylist(
        args.self_media_denylist,
        "self_media_sources",
    )
    snapshot = importer.build_snapshot(
        args.jobs,
        args.output_dir,
        args.public_days,
        args.state_db,
        authorize_self_reminders=True,
        authorize_authentic_reminder_disclosure=True,
        private_redaction_terms=importer.load_private_redaction_terms(
            args.private_redaction_terms,
            args.public_identity_allowlist,
        ),
        holdings_terms=holdings_terms,
        source_terms=source_terms,
        allow_missing_reminder_translations_for_candidates=True,
    )
    translations = importer.load_reminder_translations(
        args.reminder_translations
    )
    candidates = []
    translated_count = 0
    for day in snapshot["days"]:
        if day["date"] not in target_dates:
            continue
        for pulse in day["pulses"]:
            if pulse.get("category") != "daily_reminder":
                continue
            source_sha256 = hashlib.sha256(
                pulse["summary_original"].encode("utf-8")
            ).hexdigest()
            if source_sha256 in translations:
                translated_count += 1
                continue
            public_projection = sanitize_candidate(
                pulse,
                holdings_terms=holdings_terms,
                source_terms=source_terms,
            )
            candidates.append(
                {
                    "date": day["date"],
                    "start": pulse["start"],
                    "time_bucket": pulse["time_bucket"],
                    "source_sha256": source_sha256,
                    "summary_original": public_projection[
                        "summary_original"
                    ],
                    "excerpt_original": public_projection[
                        "excerpt_original"
                    ],
                    "original_language": public_projection[
                        "original_language"
                    ],
                    "redaction_count": public_projection[
                        "redaction_count"
                    ],
                    "semantic_abstraction_count": public_projection[
                        "semantic_abstraction_count"
                    ],
                }
            )
    candidates.sort(key=lambda item: (item["date"], item["start"]))
    write_private_json(
        args.output,
        {
            "schema": "granted-hours-private-reminder-translation-candidates-v1",
            "dates": sorted(target_dates),
            "translated_reminders": translated_count,
            "missing_translations": len(candidates),
            "candidates": candidates,
        },
    )
    print(
        "Prepared private reminder translation candidates: "
        f"dates={len(target_dates)}; translated={translated_count}; "
        f"missing={len(candidates)}; output-mode=0600."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
