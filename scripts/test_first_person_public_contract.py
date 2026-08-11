#!/usr/bin/env python3
"""Fail closed when the public timetable loses its owner-approved first-person voice."""
from __future__ import annotations

import json
import re
from pathlib import Path

import build_timetable_data as builder


ROOT = Path(__file__).resolve().parents[1]
SATISFACTION_RE = re.compile(
    r"Simon (?:很满意|满意|不满意|非常喜欢)|Simon (?:was|is) (?:satisfied|dissatisfied|pleased)",
    re.IGNORECASE,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def collaboration_voice_index(task: dict) -> int | None:
    for index, (prefix_zh, prefix_en) in enumerate(
        builder.COLLABORATION_REQUEST_VOICES
    ):
        if task["request_zh"].startswith(prefix_zh) and task[
            "request_en"
        ].startswith(prefix_en):
            return index
    return None


def reminder_voice_index(pulse: dict) -> int | None:
    for index, (prefix_zh, prefix_en) in enumerate(builder.REMINDER_VOICES):
        original_prefix = (
            prefix_en if pulse.get("original_language") == "en" else prefix_zh
        )
        if pulse["summary_original"].startswith(original_prefix) and pulse[
            "summary_en"
        ].startswith(prefix_en):
            return index
    return None


def main() -> int:
    public_days = builder.read_json(builder.DEFAULT_PUBLIC_DAYS)
    config = builder.read_json(builder.DEFAULT_CONFIG)
    history = builder.load_history(builder.DEFAULT_HISTORY)
    pulses = builder.load_pulses(builder.DEFAULT_PULSES)
    legacy = builder.load_legacy(builder.DEFAULT_LEGACY_OVERRIDES)
    output = builder.build_data(public_days, config, legacy, history, pulses)
    require("第一人称档案位置" in output["note_zh"], "Missing Chinese first-person archive note")
    require(
        "first-person archival position" in output["note_en"],
        "Missing English first-person archive note",
    )

    task_count = 0
    collaboration_count = 0
    assessment_count = 0
    owner_response_count = 0
    routine_count = 0
    reminder_count = 0
    delivered_audit_count = 0
    collaboration_voice_variants = set()
    reminder_voice_variants = set()
    for day in output["days"]:
        for task in day["task_residues"]:
            task_count += 1
            require(
                task["voice_policy_version"] == builder.VOICE_POLICY_VERSION,
                f"{day['date']} has a stale task voice policy",
            )
            if task["source_kind"] == "withheld":
                require(not task["zh"].startswith("我"), f"{day['date']} withheld task became first person")
                continue
            require(task["zh"].startswith("我"), f"{day['date']} task is not first person in Chinese")
            require(
                task["en"].startswith(("I ", "During ", "Through ")),
                f"{day['date']} task is not first person in English",
            )
            if task["source_kind"] != "collaboration_session":
                continue
            collaboration_count += 1
            voice_index = collaboration_voice_index(task)
            require(voice_index is not None, f"{day['date']} request lost paired owner voice")
            collaboration_voice_variants.add(voice_index)
            if task["completion_status"] == "completed":
                require(task["outcome_zh"].startswith("我"), f"{day['date']} completion lost first person")
                require(task["outcome_en"].startswith("I "), f"{day['date']} completion lost first person")
            if "授权通道" in task["outcome_zh"]:
                require(
                    "authorized channel" in task["outcome_en"],
                    f"{day['date']} delivery evidence is not bilingual",
                )
                delivered_audit_count += 1
            if task.get("assessment_zh"):
                assessment_count += 1
                require(bool(task.get("assessment_en")), f"{day['date']} assessment is not bilingual")
                require(
                    task.get("assessment_provenance") == "owner_approved_ai_assessment",
                    f"{day['date']} assessment is not owner-approved",
                )
            if task.get("owner_response_zh"):
                owner_response_count += 1
                require(bool(task.get("owner_response_en")), f"{day['date']} owner response is not bilingual")
                require(
                    task.get("owner_response_provenance") == "explicit_owner_feedback"
                    and task.get("owner_response_evidence_count", 0) > 0,
                    f"{day['date']} owner response lacks explicit evidence",
                )

        pulse_map = {pulse["footprint_id"]: pulse for pulse in day["background_pulses"]}
        for pulse in day["background_pulses"]:
            if pulse["category"] == "daily_reminder":
                reminder_count += 1
                require(
                    pulse.get("voice_policy_version") == builder.VOICE_POLICY_VERSION,
                    f"{day['date']} reminder has a stale voice policy",
                )
                voice_index = reminder_voice_index(pulse)
                require(voice_index is not None, f"{day['date']} reminder lost paired first-person voice")
                reminder_voice_variants.add(voice_index)
                continue
            routine_count += 1
            require(pulse["summary_zh"].startswith("我"), f"{day['date']} routine pulse lost Chinese first person")
            require(pulse["summary_en"].startswith("I "), f"{day['date']} routine pulse lost English first person")
        for item in day["reading_items"]:
            if item["classification"] != "climate_aggregate":
                continue
            sources = [pulse_map[source_ref] for source_ref in item["source_refs"]]
            summary_zh, summary_en = builder.climate_group_summary(sources)
            require(summary_zh.startswith("我"), f"{day['date']} climate card lost Chinese first person")
            require(summary_en.startswith("I "), f"{day['date']} climate card lost English first person")

    serialized = json.dumps(output, ensure_ascii=False)
    require(SATISFACTION_RE.search(serialized) is None, "Public data infers owner satisfaction")
    require(assessment_count == 7, "The seven approved AI assessments are not all public")
    require(delivered_audit_count == 9, "The nine approved delivery-backed cards are incomplete")
    require(owner_response_count == 0, "An owner response was published without this audit's evidence")
    require(
        len(collaboration_voice_variants) >= 5,
        "Collaboration narration has become formulaic",
    )
    require(
        len(reminder_voice_variants) >= 5,
        "Reminder narration has become formulaic",
    )

    ui_source = (ROOT / "src" / "timetable" / "main.js").read_text(encoding="utf-8")
    for marker in (
        "function collaborationSummary",
        "isZh ? task.request_zh : task.request_en",
        "isZh ? task.outcome_zh : task.outcome_en",
        "我的判断",
        "My assessment",
        "我在 ${windowCount}",
        "I completed ${runCount}",
    ):
        require(marker in ui_source, f"Browser runtime is missing first-person contract marker: {marker}")
    require(
        '${isZh ? "要求" : "Request"}' not in ui_source,
        "Browser runtime wrapped the first-person collaboration voice in a generic request label",
    )

    print(
        json.dumps(
            {
                "passed": True,
                "voice_policy": builder.VOICE_POLICY_VERSION,
                "tasks": task_count,
                "collaborations": collaboration_count,
                "approved_assessments": assessment_count,
                "approved_delivered_cards": delivered_audit_count,
                "routine_pulses": routine_count,
                "first_person_reminders": reminder_count,
                "collaboration_voice_variants": len(collaboration_voice_variants),
                "reminder_voice_variants": len(reminder_voice_variants),
                "owner_responses_with_explicit_evidence": owner_response_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
