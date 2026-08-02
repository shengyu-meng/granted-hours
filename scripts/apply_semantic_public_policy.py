#!/usr/bin/env python3
"""Apply the semantic public policy to tracked timetable source artifacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from import_timetable_pulses import (
    REMINDER_TRANSLATION_PROVENANCE,
    REMINDER_TRANSLATION_SCHEMA,
    parity_preserving_reminder_fields,
)
from reminder_disclosure import (
    DISCLOSURE_AUTHORIZATION,
    DISCLOSURE_POLICY,
    PROJECTION_PROVENANCE,
    REDACTION_POLICY,
    extractive_prefix,
    projection_kind_for_counts,
)
from public_projection_privacy import load_private_denylist, replace_private_terms
from semantic_public_policy import (
    abstract_for_tags,
    abstract_sensitive_public_text,
    polish_public_excerpt,
    projection_tags,
    reminder_requires_routine_projection,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY = ROOT / "metadata" / "timetable-history.json"
DEFAULT_PULSES = ROOT / "metadata" / "timetable-pulses.json"
DEFAULT_TRANSLATIONS = ROOT / "metadata" / "timetable-reminder-translations.json"
DEFAULT_IDENTITY_DENYLIST = ROOT / ".private" / "identity-denylist.json"
MASK = "████"
ROUTINE_SUMMARY = (
    "日常计划与优先级复核。",
    "Daily planning and priority review.",
)
KNOWN_HISTORY_ABSTRACTIONS = {
    "2026-05-10": {1: ("intimate_family_dream",), 2: ("intimate_family_dream",)},
    "2026-05-19": {1: ("health_or_emotional_state",)},
    "2026-06-06": {
        1: ("unpublished_commercial_brief",),
        3: ("unpublished_commercial_brief",),
    },
    "2026-07-02": {
        0: ("unpublished_commercial_brief",),
        1: ("unpublished_commercial_brief",),
        2: ("unpublished_commercial_brief",),
    },
    "2026-07-31": {
        1: ("unpublished_commercial_brief",),
        2: ("unpublished_commercial_brief",),
    },
}


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_json(path: Path, value: object) -> bool:
    serialized = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == serialized:
        return False
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(serialized)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def sanitize_history(
    source: dict,
    *,
    identity_terms: tuple[str, ...] = (),
) -> tuple[dict, dict[str, int]]:
    stats = {
        "fields": 0,
        "abstracted": 0,
        "identity_masks": 0,
        "merged_duplicates": 0,
    }
    for day in source.get("days", []):
        day_date = str(day.get("date", ""))
        for residue_index, residue in enumerate(day.get("assigned_residues", [])):
            forced_tags = KNOWN_HISTORY_ABSTRACTIONS.get(day_date, {}).get(
                residue_index,
                (),
            )
            zh = residue.get("zh")
            en = residue.get("en")
            if isinstance(zh, str) and isinstance(en, str):
                masked_zh = replace_private_terms(zh, identity_terms, MASK)
                masked_en = replace_private_terms(en, identity_terms, MASK)
                stats["identity_masks"] += int(masked_zh != zh) + int(
                    masked_en != en
                )
                zh, en = masked_zh, masked_en
                residue["zh"] = zh
                residue["en"] = en
                tags = tuple(
                    dict.fromkeys(
                        (*forced_tags, *projection_tags(zh), *projection_tags(en))
                    )
                )
                stats["fields"] += 2
                if tags:
                    new_zh = abstract_for_tags(tags, "zh")
                    new_en = abstract_for_tags(tags, "en")
                    stats["abstracted"] += int(zh != new_zh) + int(en != new_en)
                    residue["zh"] = new_zh
                    residue["en"] = new_en
            excerpts = residue.get("public_excerpts")
            if not isinstance(excerpts, list):
                zh_masks = residue.get("zh", "").count(MASK)
                en_masks = residue.get("en", "").count(MASK)
                if zh_masks != en_masks:
                    residue["zh"] = residue["zh"].replace(MASK, "某项未公开内容")
                    residue["en"] = residue["en"].replace(MASK, "a private item")
                    zh_masks = en_masks = 0
                residue["redaction_count"] = zh_masks
                residue["redaction_status"] = "partial" if zh_masks else "none"
                continue
            sanitized_excerpts: list[str] = []
            if forced_tags:
                sanitized = abstract_for_tags(forced_tags, "zh")
                stats["fields"] += len(excerpts)
                stats["abstracted"] += sum(
                    str(excerpt) != sanitized for excerpt in excerpts
                )
                sanitized_excerpts = [polish_public_excerpt(sanitized)]
            else:
                for excerpt in excerpts:
                    stats["fields"] += 1
                    original_excerpt = str(excerpt)
                    masked_excerpt = replace_private_terms(
                        original_excerpt,
                        identity_terms,
                        MASK,
                    )
                    stats["identity_masks"] += int(
                        masked_excerpt != original_excerpt
                    )
                    sanitized, tags = abstract_sensitive_public_text(masked_excerpt)
                    sanitized = polish_public_excerpt(sanitized)
                    if tags:
                        stats["abstracted"] += 1
                    if sanitized and sanitized not in sanitized_excerpts:
                        sanitized_excerpts.append(sanitized)
            residue["public_excerpts"] = sanitized_excerpts
            excerpt_masks = sum(excerpt.count(MASK) for excerpt in sanitized_excerpts)
            residue["excerpt_redaction_count"] = excerpt_masks
            residue["redaction_count"] = excerpt_masks
            residue["redaction_status"] = "partial" if excerpt_masks else "none"
        unique_residues = []
        signatures = set()
        for residue in day.get("assigned_residues", []):
            signature = (
                residue.get("category"),
                residue.get("en"),
                residue.get("zh"),
            )
            if signature in signatures:
                stats["merged_duplicates"] += 1
                continue
            signatures.add(signature)
            unique_residues.append(residue)
        day["assigned_residues"] = unique_residues
    return source, stats


def sanitize_pulses(
    source: dict,
    *,
    identity_terms: tuple[str, ...] = (),
) -> tuple[dict, dict[str, int]]:
    stats = {
        "fields": 0,
        "abstracted": 0,
        "identity_masks": 0,
        "reminders": 0,
        "routine_reductions": 0,
    }
    for day in source.get("days", []):
        for pulse in day.get("pulses", []):
            if pulse.get("category") == "daily_reminder" and all(
                isinstance(pulse.get(field), str)
                for field in ("summary_original", "summary_en")
            ):
                stats["reminders"] += 1
                previous_original = pulse["summary_original"]
                previous_english = pulse["summary_en"]
                masked_original = replace_private_terms(
                    previous_original,
                    identity_terms,
                    MASK,
                )
                masked_english = replace_private_terms(
                    previous_english,
                    identity_terms,
                    MASK,
                )
                stats["identity_masks"] += int(
                    masked_original != previous_original
                ) + int(masked_english != previous_english)
                if reminder_requires_routine_projection(
                    f"{previous_original}\n{previous_english}"
                ):
                    retained = {
                        key: pulse[key]
                        for key in (
                            "start",
                            "end",
                            "duration_minutes",
                            "execution_minutes",
                            "time_bucket",
                            "count",
                            "time_provenance",
                        )
                        if key in pulse
                    }
                    pulse.clear()
                    pulse.update(retained)
                    pulse.update(
                        {
                            "category": "background_routine",
                            "summary_zh": ROUTINE_SUMMARY[0],
                            "summary_en": ROUTINE_SUMMARY[1],
                            "summary_provenance": "derived_public_safe",
                        }
                    )
                    stats["routine_reductions"] += 1
                    continue
                original_tags = projection_tags(masked_original)
                english_tags = projection_tags(masked_english)
                tags = tuple(dict.fromkeys((*original_tags, *english_tags)))
                if tags:
                    original = abstract_for_tags(tags, "zh")
                    english = abstract_for_tags(tags, "en")
                else:
                    original = masked_original
                    english = masked_english
                if original.count(MASK) != english.count(MASK):
                    original = original.replace(MASK, "某项未公开内容")
                    english = english.replace(MASK, "a private item")
                original, english, excerpt_original, excerpt_en = (
                    parity_preserving_reminder_fields(original, english)
                )
                stats["fields"] += 2
                stats["abstracted"] += int(previous_original != original) + int(
                    previous_english != english
                )
                pulse["summary_original"] = original
                pulse["summary_en"] = english
                pulse["excerpt_original"] = excerpt_original
                pulse["excerpt_en"] = excerpt_en
                pulse["redaction_count"] = original.count(MASK)
                pulse["semantic_abstraction_count"] = max(
                    len(tags),
                    int(pulse.get("semantic_abstraction_count", 0)),
                )
                pulse["projection_kind"] = projection_kind_for_counts(
                    pulse["redaction_count"],
                    pulse["semantic_abstraction_count"],
                )
                pulse["redaction_policy"] = REDACTION_POLICY
                pulse["projection_provenance"] = PROJECTION_PROVENANCE
                pulse["summary_provenance"] = PROJECTION_PROVENANCE
                pulse["disclosure_policy"] = DISCLOSURE_POLICY
                pulse["disclosure_authorization"] = DISCLOSURE_AUTHORIZATION
                continue
            for field in ("summary_zh", "summary_en"):
                value = pulse.get(field)
                if not isinstance(value, str):
                    continue
                stats["fields"] += 1
                masked = replace_private_terms(value, identity_terms, MASK)
                stats["identity_masks"] += int(masked != value)
                sanitized, tags = abstract_sensitive_public_text(masked)
                pulse[field] = sanitized
                if tags:
                    stats["abstracted"] += 1
    return source, stats


def translation_catalog_from_pulses(pulses: dict) -> dict:
    translations: dict[str, dict[str, str]] = {}
    for day in pulses.get("days", []):
        for pulse in day.get("pulses", []):
            if pulse.get("category") != "daily_reminder":
                continue
            summary_original = pulse.get("summary_original")
            summary_en = pulse.get("summary_en")
            excerpt_en = pulse.get("excerpt_en")
            if not all(
                isinstance(value, str) and value
                for value in (summary_original, summary_en, excerpt_en)
            ):
                continue
            source_sha256 = hashlib.sha256(
                summary_original.encode("utf-8")
            ).hexdigest()
            record = {
                "source_sha256": source_sha256,
                "summary_en": summary_en,
                "excerpt_en": excerpt_en,
                "translation_provenance": REMINDER_TRANSLATION_PROVENANCE,
            }
            previous = translations.get(source_sha256)
            if previous is not None and previous != record:
                raise ValueError("Conflicting translations for one public reminder")
            translations[source_sha256] = record
    return {
        "schema": REMINDER_TRANSLATION_SCHEMA,
        "translation_provenance": REMINDER_TRANSLATION_PROVENANCE,
        "translations": {key: translations[key] for key in sorted(translations)},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--pulses", type=Path, default=DEFAULT_PULSES)
    parser.add_argument("--translations", type=Path, default=DEFAULT_TRANSLATIONS)
    parser.add_argument(
        "--identity-denylist",
        type=Path,
        default=DEFAULT_IDENTITY_DENYLIST,
    )
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    identity_terms = load_private_denylist(args.identity_denylist, "identities")
    history, history_stats = sanitize_history(
        read_json(args.history),
        identity_terms=identity_terms,
    )
    pulses, pulse_stats = sanitize_pulses(
        read_json(args.pulses),
        identity_terms=identity_terms,
    )
    translations = translation_catalog_from_pulses(pulses)
    changed = {"history": False, "pulses": False, "translations": False}
    if args.write:
        changed["history"] = atomic_write_json(args.history, history)
        changed["pulses"] = atomic_write_json(args.pulses, pulses)
        changed["translations"] = atomic_write_json(args.translations, translations)
    print(
        "Semantic public policy "
        f"mode={'write' if args.write else 'audit'}; "
        f"history_abstracted={history_stats['abstracted']}; "
        f"pulse_abstracted={pulse_stats['abstracted']}; "
        f"identity_masks={history_stats['identity_masks'] + pulse_stats['identity_masks']}; "
        f"reminders={pulse_stats['reminders']}; "
        f"routine_reductions={pulse_stats['routine_reductions']}; "
        f"changed={sum(changed.values())}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
