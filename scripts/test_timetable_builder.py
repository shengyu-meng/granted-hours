#!/usr/bin/env python3
"""Focused deterministic tests for historical timetable reconstruction."""
from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import build_timetable_data as builder


class TimetableBuilderTests(unittest.TestCase):
    WITHHELD_DATES = {
        "2026-06-13",
        "2026-06-27",
        "2026-07-05",
        "2026-07-11",
        "2026-07-19",
        "2026-07-29",
    }
    EVIDENCE_EMPTY_DATES = {
        "2026-06-14",
        "2026-06-26",
        "2026-08-09",
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.public_days = builder.read_json(builder.DEFAULT_PUBLIC_DAYS)
        cls.config = builder.read_json(builder.DEFAULT_CONFIG)
        cls.history = builder.load_history(builder.DEFAULT_HISTORY)
        cls.pulses = builder.load_pulses(builder.DEFAULT_PULSES)
        cls.legacy = builder.load_legacy(builder.DEFAULT_LEGACY_OVERRIDES)

    def build(self, public_days=None):
        return builder.build_data(
            public_days or self.public_days,
            self.config,
            self.legacy,
            self.history,
            self.pulses,
        )

    def test_only_newest_public_days_may_wait_for_authored_history(self) -> None:
        public_dates = {entry["date"] for entry in self.public_days}
        missing = public_dates.difference(self.history)
        self.assertEqual(missing, {value for value in public_dates if value > max(self.history)})
        self.assertEqual(len(public_dates), len(self.public_days))

    def test_month_cell_preserves_every_public_task_for_scroll_preview(self) -> None:
        output = self.build()
        for day in output["days"]:
            self.assertEqual(
                len(day["cell_assigned"]),
                len(day["task_residues"]),
                f"{day['date']} month preview must not discard later events",
            )

    def test_first_person_voice_policy_is_complete_and_evidence_bounded(self) -> None:
        output = self.build()
        assessment_count = 0
        for day in output["days"]:
            for task in day["task_residues"]:
                self.assertEqual(task["voice_policy_version"], builder.VOICE_POLICY_VERSION)
                if task["source_kind"] == "withheld":
                    self.assertFalse(task["zh"].startswith("我"))
                    continue
                self.assertTrue(task["zh"].startswith("我"), (day["date"], task["source_kind"], task["zh"]))
                self.assertTrue(task["en"].startswith(("I ", "During ", "Through ")), (day["date"], task["en"]))
                if task["source_kind"] == "collaboration_session":
                    self.assertTrue(task["request_zh"].startswith("Simon 让我"))
                    self.assertTrue(task["request_en"].startswith("Simon asked me"))
                    if task["completion_status"] == "completed":
                        self.assertTrue(task["outcome_zh"].startswith("我"))
                        self.assertTrue(task["outcome_en"].startswith("I "))
                    if task.get("assessment_zh"):
                        assessment_count += 1
                        self.assertTrue(task["assessment_en"].strip())
                        self.assertEqual(
                            task["assessment_provenance"],
                            "owner_approved_ai_assessment",
                        )
                    self.assertEqual(
                        bool(task.get("owner_response_zh")),
                        bool(task.get("owner_response_en")),
                    )
                    if task.get("owner_response_zh"):
                        self.assertEqual(
                            task["owner_response_provenance"],
                            "explicit_owner_feedback",
                        )
                        self.assertGreater(task["owner_response_evidence_count"], 0)
        self.assertEqual(assessment_count, 7)

    def test_owner_approved_audit_cards_are_merged_once(self) -> None:
        output = self.build()
        expected = {
            "2026-08-04": 2,
            "2026-08-05": 1,
            "2026-08-06": 1,
            "2026-08-07": 1,
            "2026-08-08": 1,
            "2026-08-10": 3,
        }
        for day_date, count in expected.items():
            day = next(day for day in output["days"] if day["date"] == day_date)
            cards = [task for task in day["task_residues"] if task["source_kind"] == "collaboration_session"]
            self.assertEqual(len(cards), count, day_date)
            self.assertEqual(
                [marker["task_name_en"] for marker in day["cell_assigned"]],
                [task["task_name_en"] for task in day["task_residues"]],
            )

    def test_history_uses_faithful_summaries_with_explicit_redaction(self) -> None:
        provenance = Counter()
        for day_date, entry in self.history.items():
            provenance[entry["provenance"]] += 1
            self.assertEqual(
                set(entry),
                {"date", "provenance", "assigned_residues"},
                f"{day_date} must not retain focus/medium/workflow generation fields",
            )
            self.assertGreaterEqual(len(entry["assigned_residues"]), 0)
            self.assertLessEqual(len(entry["assigned_residues"]), 10)
            signatures = set()
            for residue in entry["assigned_residues"]:
                expected_fields = {
                    "category",
                    "en",
                    "zh",
                    "redaction_status",
                    "redaction_count",
                    "source_kind",
                    "faithfulness",
                }
                if residue.get("source_kind") in builder.SESSION_SOURCE_KINDS:
                    expected_fields.update(
                        {
                            "evidence_count",
                            "agent_labels",
                            "start",
                            "end",
                            "time_provenance",
                        }
                    )
                if residue.get("source_kind") == "collaboration_session":
                    expected_fields.update(
                        {
                            "session_count",
                            "delegated_agent_count",
                            "returned_agent_count",
                            "request_zh",
                            "request_en",
                            "outcome_zh",
                            "outcome_en",
                            "completion_status",
                            "pair_provenance",
                        }
                    )
                    if "assessment_zh" in residue:
                        expected_fields.update(
                            {
                                "assessment_zh",
                                "assessment_en",
                                "assessment_provenance",
                            }
                        )
                    if "owner_response_zh" in residue:
                        expected_fields.update(
                            {
                                "owner_response_zh",
                                "owner_response_en",
                                "owner_response_provenance",
                                "owner_response_evidence_count",
                            }
                        )
                self.assertEqual(
                    set(residue),
                    expected_fields,
                )
                self.assertIn(residue["category"], builder.REQUIRED_TAXONOMY)
                self.assertIn(residue["redaction_status"], {"none", "partial", "withheld"})
                self.assertIsInstance(residue["redaction_count"], int)
                self.assertGreaterEqual(residue["redaction_count"], 0)
                self.assertIn(
                    residue["source_kind"],
                    {
                        "daily_record",
                        "maintenance_record",
                        "task_card",
                        "public_post_archive",
                        "withheld",
                        "agent_session",
                        "collaboration_session",
                    },
                )
                self.assertEqual(residue["faithfulness"], "faithful_summary")
                self.assertLessEqual(len(residue["zh"]), 90, f"{day_date} Chinese summary is too long for a duration block")
                self.assertLessEqual(len(residue["en"]), 300, f"{day_date} English summary is too long for a duration block")
                public_copy = f"{residue['en']} {residue['zh']}"
                self.assertIsNone(builder.SENSITIVE_ASSIGNED_WORK_RE.search(public_copy))
                self.assertIsNone(builder.PRIVATE_OPERATIONAL_CONTEXT_RE.search(public_copy))
                self.assertIsNone(builder.EDUCATION_IDENTITY_RE.search(public_copy))
                self.assertIsNone(builder.PROPOSAL_TITLE_CONTEXT_RE.search(public_copy))
                self.assertNotRegex(residue["en"], r"(?:/Users/|\\Users\\|\.md\b|session[_ -]?id|chat[_ -]?id)")
                self.assertNotRegex(residue["zh"], r"(?:/Users/|\\Users\\|\.md\b|会话ID|聊天ID)")
                if residue["redaction_status"] == "none":
                    self.assertEqual(residue["redaction_count"], 0)
                elif residue["source_kind"] == "collaboration_session":
                    self.assertGreater(residue["redaction_count"], 0)
                    self.assertEqual(
                        residue["redaction_count"],
                        residue["request_zh"].count("████")
                        + residue["outcome_zh"].count("████"),
                    )
                    self.assertEqual(
                        residue["request_zh"].count("████"),
                        residue["request_en"].count("████"),
                    )
                    self.assertEqual(
                        residue["outcome_zh"].count("████"),
                        residue["outcome_en"].count("████"),
                    )
                else:
                    self.assertGreater(residue["redaction_count"], 0)
                    self.assertIn("████", residue["en"])
                    self.assertIn("████", residue["zh"])
                signature = (
                    (
                        residue["category"], residue["en"], residue["zh"],
                        residue["request_zh"], residue["request_en"],
                        residue["outcome_zh"], residue["outcome_en"],
                        residue["completion_status"],
                    )
                    if residue.get("source_kind") == "collaboration_session"
                    else (residue["category"], residue["en"], residue["zh"])
                )
                self.assertNotIn(signature, signatures)
                signatures.add(signature)

        expected_provenance = Counter(entry["provenance"] for entry in self.history.values())
        self.assertEqual(provenance, expected_provenance)
        actual_withheld = {
            day_date
            for day_date, entry in self.history.items()
            if entry["provenance"] == "withheld"
        }
        self.assertTrue(
            self.WITHHELD_DATES.issubset(actual_withheld),
            "Known historical withheld dates must remain withheld; newly imported future dates may also be withheld until the next dialogue sync.",
        )
        for day_date in self.EVIDENCE_EMPTY_DATES:
            self.assertEqual(self.history[day_date]["provenance"], "record_based")
            self.assertEqual(self.history[day_date]["assigned_residues"], [])

    def test_historical_output_is_continuous_diverse_and_artwork_free(self) -> None:
        output = self.build()
        phrases = Counter()
        completed_or_recorded_phrases = Counter()
        schedules = set()
        category_patterns = Counter()
        category_counts = Counter()
        for day in output["days"]:
            self.assertLessEqual(len(day["task_residues"]), 10)
            builder.validate_tasks(day["date"], day["task_residues"], self.config["autonomous_hour"])
            schedules.add(
                tuple(
                    (task["start"], task["end"], task["zh"], task["en"])
                    for task in day["task_residues"]
                )
            )
            category_patterns[tuple(task["category"] for task in day["task_residues"])] += 1
            for task in day["task_residues"]:
                phrase = (
                    (
                        task["request_zh"],
                        task["request_en"],
                        task["outcome_zh"],
                        task["outcome_en"],
                    )
                    if task["source_kind"] == "collaboration_session"
                    else (task["zh"], task["en"])
                )
                phrases[phrase] += 1
                if (
                    task["source_kind"] != "collaboration_session"
                    or task["completion_status"] == "completed"
                ):
                    completed_or_recorded_phrases[phrase] += 1
                category_counts[task["category"]] += 1
                self.assertNotIn(day["title_en"].lower(), task["en"].lower())
                self.assertNotIn(day["title_zh"], task["zh"])

        self.assertGreaterEqual(len(phrases), 100)
        self.assertGreaterEqual(len(schedules), 40)
        # The intentionally uniform unverified state may repeat: repetition is
        # preferable to fabricating variety. Evidence-backed and authored copy
        # must still remain semantically diverse.
        self.assertLessEqual(max(completed_or_recorded_phrases.values()), 10)
        # Maintenance records now live in observed routine blocks rather than
        # being duplicated as assigned work. Remaining category repetition is
        # therefore expected; phrase diversity is the truthfulness gate.
        self.assertLessEqual(max(category_patterns.values()), 35)
        # Privacy-hardening may remove attachment-only or outcome-free social
        # cards. Keep a corpus-level diversity floor without rewarding the
        # retention of low-information public records.
        self.assertGreaterEqual(category_counts["social_media_organization"], 12)
        expected_provenance = Counter(entry["provenance"] for entry in self.history.values())
        expected_provenance["inferred"] += sum(
            day["date"] not in self.history for day in output["days"]
        )
        self.assertEqual(
            Counter(day["history_provenance"] for day in output["days"]),
            expected_provenance,
        )

    def test_build_is_deterministic(self) -> None:
        first = json.dumps(self.build(), ensure_ascii=False, sort_keys=True)
        second = json.dumps(self.build(), ensure_ascii=False, sort_keys=True)
        self.assertEqual(first, second)

    def test_public_data_contract_states_authentic_entity_masking_plainly(self) -> None:
        output = self.build()
        note = output["public_data_note"]
        self.assertEqual(note, self.config["public_data_note"])
        self.assertEqual(output["note_en"], note["en"])
        self.assertEqual(output["note_zh"], note["zh"])
        self.assertIn("第一人称档案位置", note["zh"])
        self.assertIn("not proof of continuous consciousness", note["en"])

    def test_every_artwork_has_explicit_dual_dates_and_one_truthful_beacon(self) -> None:
        output = self.build()
        days_by_date = {day["date"]: day for day in output["days"]}
        seed_targets = Counter()

        for day in output["days"]:
            expected_source = (
                date.fromisoformat(day["date"]) - timedelta(days=1)
            ).isoformat()
            self.assertEqual(day["source_date"], expected_source)
            self.assertEqual(day["crystallization_date"], day["date"])
            self.assertEqual(
                day["crystallization_window"],
                {
                    "start": self.config["autonomous_hour"]["start"],
                    "end": self.config["autonomous_hour"]["end"],
                    "timezone": self.config["timezone"],
                },
            )

            autonomous = day["autonomous_work"]
            self.assertEqual(autonomous["source_date"], expected_source)
            self.assertEqual(autonomous["crystallization_date"], day["date"])
            self.assertEqual(
                (autonomous["start"], autonomous["end"]),
                (
                    self.config["autonomous_hour"]["start"],
                    self.config["autonomous_hour"]["end"],
                ),
            )
            autonomous_window = (
                self.config["autonomous_hour"]["start"],
                self.config["autonomous_hour"]["end"],
            )
            self.assertIn(
                autonomous_window,
                [
                    (event["start"], event["end"])
                    for event in day["timeline_events"]
                    if event["origin"] in {"self", "absence"}
                ],
            )

            if expected_source in days_by_date:
                self.assertRegex(
                    autonomous["source_day_url"],
                    rf"[?&]date={expected_source}(?:&|$)",
                )
            else:
                self.assertIsNone(autonomous["source_day_url"])

            for seed in day["forward_artwork_seeds"]:
                self.assertEqual(seed["source_date"], day["date"])
                self.assertIn(seed["crystallization_date"], days_by_date)
                self.assertEqual(
                    date.fromisoformat(seed["crystallization_date"]),
                    date.fromisoformat(seed["source_date"]) + timedelta(days=1),
                )
                self.assertEqual(
                    set(seed),
                    {
                        "source_date",
                        "crystallization_date",
                        "title_en",
                        "title_zh",
                        "day_url",
                    },
                )
                self.assertRegex(
                    seed["day_url"],
                    rf"[?&]date={seed['crystallization_date']}(?:&|$)",
                )
                seed_targets[seed["crystallization_date"]] += 1

        expected_seed_targets = {
            day["date"]
            for day in output["days"]
            if day["source_date"] in days_by_date
        }
        self.assertEqual(set(seed_targets), expected_seed_targets)
        self.assertTrue(all(count == 1 for count in seed_targets.values()))

    def test_every_public_day_has_public_safe_real_scheduler_pulses(self) -> None:
        output = self.build()
        allowed_categories = set(builder.PULSE_DEFINITIONS)
        calendar_dates = {day["date"] for day in output["days"] if day["type"] == "calendar"}
        waiting_dates = {
            day["date"]
            for day in output["days"]
            if day["date"] > max(self.pulses)
        }
        self.assertEqual(
            {day["date"] for day in output["days"]},
            set(self.pulses) | calendar_dates | waiting_dates,
        )
        for day in output["days"]:
            if day["date"] not in self.pulses:
                self.assertEqual(day["background_pulses"], [])
                continue
            self.assertTrue(day["background_pulses"], f"{day['date']} needs real run evidence")
            starts = [builder.minutes(pulse["start"]) for pulse in day["background_pulses"]]
            self.assertEqual(starts, sorted(starts))
            for pulse in day["background_pulses"]:
                self.assertEqual(pulse["origin"], "background")
                self.assertIn(pulse["category"], allowed_categories)
                self.assertGreaterEqual(pulse["count"], 1)
                self.assertRegex(pulse["start"], r"^\d{2}:\d{2}$")
                self.assertRegex(pulse["end"], r"^\d{2}:\d{2}$")
                self.assertEqual(
                    pulse["duration_minutes"],
                    builder.minutes(pulse["end"]) - builder.minutes(pulse["start"]),
                )
                self.assertGreaterEqual(pulse["execution_minutes"], 1)
                if pulse["category"] == "daily_reminder":
                    self.assertTrue(pulse["summary_original"].strip())
                    self.assertTrue(pulse["excerpt_original"].strip())
                    self.assertTrue(pulse["summary_en"].strip())
                    self.assertTrue(pulse["excerpt_en"].strip())
                    self.assertNotIn("summary_zh", pulse)
                    self.assertEqual(
                        pulse["translation_provenance"],
                        builder.REMINDER_TRANSLATION_PROVENANCE,
                    )
                    self.assertEqual(
                        pulse["summary_provenance"],
                        "semantic_public_projection",
                    )
                else:
                    self.assertTrue(pulse["summary_zh"].strip())
                    self.assertTrue(pulse["summary_en"].strip())
                    self.assertEqual(pulse["summary_provenance"], "derived_public_safe")
                self.assertIn(
                    pulse["time_provenance"],
                    {"observed_session_window", "mixed_observed_and_receipt", "receipt_timestamp_estimate"},
                )
                serialized_pulse = json.dumps(pulse, ensure_ascii=False).lower()
                self.assertNotIn('"job":', serialized_pulse)
                self.assertNotIn('"job_id":', serialized_pulse)
            timeline = day["timeline_events"]
            self.assertEqual(
                timeline,
                sorted(
                    timeline,
                    key=lambda event: (
                        builder.minutes(event["start"]),
                        builder.timeline_event_priority(event),
                    ),
                ),
            )
            self.assertEqual(
                sum(event["origin"] in {"self", "absence"} for event in timeline),
                1,
            )

    def test_july_21_and_22_keep_every_exact_footprint_but_reduce_the_reading_layer(self) -> None:
        output = self.build()
        output_by_date = {day["date"]: day for day in output["days"]}
        for day_date in ("2026-07-21", "2026-07-22"):
            with self.subTest(day_date=day_date):
                source = self.pulses[day_date]
                day = output_by_date[day_date]
                backgrounds = day["background_pulses"]
                self.assertEqual(len(backgrounds), len(source))
                self.assertEqual(
                    [
                        (
                            pulse["start"],
                            pulse["end"],
                            pulse["duration_minutes"],
                            pulse["category"],
                            pulse["count"],
                        )
                        for pulse in backgrounds
                    ],
                    [
                        (
                            pulse["start"],
                            pulse["end"],
                            pulse["duration_minutes"],
                            pulse["category"],
                            pulse["count"],
                        )
                        for pulse in source
                    ],
                )
                self.assertEqual(
                    len([event for event in day["timeline_events"] if event["origin"] == "background"]),
                    len(source),
                )

                reading_items = day["reading_items"]
                climate_groups = [
                    item
                    for item in reading_items
                    if item["classification"] == "climate_aggregate"
                ]
                climate_member_ids = [
                    member_id
                    for item in climate_groups
                    for member_id in item["source_refs"]
                ]
                self.assertLess(len(climate_groups), len(climate_member_ids))
                self.assertLess(len(reading_items), len(day["timeline_events"]))

                footprint_ids = [event["footprint_id"] for event in day["timeline_events"]]
                projected_ids = [
                    member_id
                    for item in reading_items
                    for member_id in item["source_refs"]
                ]
                self.assertCountEqual(projected_ids, footprint_ids)
                self.assertEqual(len(projected_ids), len(set(projected_ids)))

                for item in reading_items:
                    base_fields = {
                        "reading_id",
                        "source",
                        "source_refs",
                        "layer",
                        "classification",
                    }
                    expected_fields = (
                        base_fields
                        | {"family", "window"}
                        if item["classification"] == "climate_aggregate"
                        else base_fields
                    )
                    self.assertEqual(set(item), expected_fields)
                    self.assertTrue(item["source_refs"])
                    self.assertNotIn("constituents", item)
                    self.assertNotIn("member_footprint_ids", item)
                    self.assertNotIn("duration_minutes", item)
                    self.assertNotIn("origin", item)
                    if item["classification"] == "climate_aggregate":
                        label_zh, label_en = builder.climate_group_label(
                            item["family"],
                            item["window"],
                        )
                        self.assertNotIn(
                            label_zh,
                            {"后台例行任务", "系统例行任务", "静默检查"},
                        )
                        self.assertNotIn(
                            label_en,
                            {"Background routine", "System routine", "Silent check"},
                        )

    def test_generic_support_alerts_stay_in_one_daily_climate_rollup(self) -> None:
        routine = {
            "origin": "background",
            "footprint_id": "background-001",
            "category": "system_routine",
            "start": "20:02",
            "end": "20:04",
            "duration_minutes": 2,
            "execution_minutes": 1,
            "time_bucket": "evening",
            "count": 1,
            "time_provenance": "observed_session_window",
            "summary_zh": "完成 1 次系统例行检查；0 次静默正常，1 次出现公开级别异常或新鲜度提示。",
            "summary_en": "1 system checks completed; 0 were silently healthy and 1 exposed a public-level anomaly or freshness warning.",
            "summary_provenance": "derived_public_safe",
            "label_zh": "系统例行任务",
            "label_en": "System routine",
            "pulse_color": "blue",
        }
        classification = builder.classify_public_pulse(routine)
        self.assertEqual(classification["outcome"], "climate_aggregate")
        self.assertIn("daily_support_rollup", classification["evidence"])

        quiet = copy.deepcopy(routine)
        quiet["summary_zh"] = "完成 1 次系统例行检查；1 次静默正常，0 次出现公开级别异常或新鲜度提示。"
        quiet["summary_en"] = "1 system checks completed; 1 were silently healthy and 0 exposed a public-level anomaly or freshness warning."
        self.assertEqual(builder.classify_public_pulse(quiet)["outcome"], "climate_aggregate")

        background = copy.deepcopy(routine)
        background["category"] = "background_routine"
        self.assertEqual(
            builder.classify_public_pulse(background)["outcome"],
            "climate_aggregate",
        )

        market_warning = copy.deepcopy(routine)
        market_warning["category"] = "ah_market_scan"
        market_warning["summary_zh"] = "存在数据或链路新鲜度警告，公开市场事实仍可读取。"
        market_warning["summary_en"] = "Warnings were present; public market facts remain readable."
        self.assertEqual(
            builder.classify_public_pulse(market_warning)["outcome"],
            "climate_aggregate",
        )

        market_gate_failure = copy.deepcopy(market_warning)
        market_gate_failure["summary_zh"] = "本次扫描未达发布闸门。"
        market_gate_failure["summary_en"] = "This scan did not pass its publication gate."
        self.assertEqual(
            builder.classify_public_pulse(market_gate_failure)["outcome"],
            "promoted_routine_exception",
        )

    def test_private_reminder_projection_only_copies_already_masked_v2_fields(self) -> None:
        owned = {
            "owner_scope": "self",
            "ownership_provenance": "explicit_user_authorization",
            "disclosure_policy": "semantic_abstraction_entity_masked_reminder_v3",
            "disclosure_authorization": "explicit_user_authorization_2026-07-29",
            "public_label_zh": "午间提醒",
            "public_label_en": "Midday reminder",
            "summary_original": "联系 ████，然后允许自己休息。",
            "excerpt_original": "联系 ████，然后允许自己休息。",
            "original_language": "zh",
            "projection_kind": "verbatim_redacted",
            "redaction_policy": "semantic_abstraction_then_entity_mask_v3",
            "redaction_count": 1,
            "semantic_abstraction_count": 0,
            "projection_provenance": "semantic_public_projection",
            "raw_reconstruction_trap": "Mara Evergarden / Orchid Lantern",
        }
        projected = builder.project_private_reminder(owned)
        self.assertIsNotNone(projected)
        serialized = json.dumps(projected, ensure_ascii=False)
        self.assertNotIn("Mara Evergarden", serialized)
        self.assertNotIn("Orchid Lantern", serialized)
        self.assertEqual(
            projected["summary_original"],
            "联系 ████，然后允许自己休息。",
        )

        rejected_sources = [
            {**owned, "owner_scope": "other_person"},
            {**owned, "owner_scope": "unknown"},
            {**owned, "ownership_provenance": "unverified"},
            {**owned, "disclosure_policy": "limited_masked_reminder_v1"},
            {field: value for field, value in owned.items() if field != "summary_original"},
        ]
        for source in rejected_sources:
            with self.subTest(source=source):
                self.assertIsNone(builder.project_private_reminder(source))

    def test_v6_pulse_schema_validates_authentic_reminder_fields(self) -> None:
        base_pulse = {
            "start": "08:00",
            "end": "08:02",
            "duration_minutes": 2,
            "execution_minutes": 1,
            "time_bucket": "morning",
            "category": "daily_reminder",
            "count": 1,
            "time_provenance": "observed_session_window",
            "summary_provenance": "semantic_public_projection",
            "owner_scope": "self",
            "ownership_provenance": "explicit_user_authorization",
            "disclosure_policy": "semantic_abstraction_entity_masked_reminder_v3",
            "disclosure_authorization": "explicit_user_authorization_2026-07-29",
            "public_label_zh": "晨间提醒",
            "public_label_en": "Morning reminder",
            "summary_original": "允许自己休息。",
            "excerpt_original": "允许自己休息。",
            "original_language": "zh",
            "projection_kind": "verbatim",
            "redaction_policy": "semantic_abstraction_then_entity_mask_v3",
            "redaction_count": 0,
            "semantic_abstraction_count": 0,
            "projection_provenance": "semantic_public_projection",
            "summary_en": "Allow yourself to rest.",
            "excerpt_en": "Allow yourself to rest.",
            "translation_provenance": (
                "public_mask_preserving_translation_v1"
            ),
        }
        invalid_cases = (
            ("owner_scope", "delegated_person", "invalid owner scope"),
            ("ownership_provenance", "assumed", "invalid ownership provenance"),
            ("projection_kind", "inner_weather", "invalid projection kind"),
            ("redaction_policy", "fixed_template_blocks_v1", "invalid redaction policy"),
            ("summary_en", "允许自己休息。", "summary_en contains CJK"),
            (
                "translation_provenance",
                "runtime_translation",
                "translation provenance mismatch",
            ),
            (
                "summary_en",
                "Allow ████ to rest.",
                "translation mask count mismatch",
            ),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "pulses.json"
            for field, value, message in invalid_cases:
                with self.subTest(field=field):
                    pulse = {**base_pulse, field: value}
                    path.write_text(
                        json.dumps(
                            {
                                "schema": builder.PULSE_SNAPSHOT_SCHEMA,
                                "timezone": "Asia/Shanghai",
                                "days": [{"date": "2026-07-01", "pulses": [pulse]}],
                            }
                        ),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(SystemExit, message):
                        builder.load_pulses(path)

    def test_v2_reminder_is_readable_once_without_old_template_fields(self) -> None:
        pulses = copy.deepcopy(self.pulses)
        reminder = next(
            pulse
            for pulse in pulses["2026-07-21"]
            if pulse["category"] == "daily_reminder"
        )
        for field in (
            "summary_zh",
            "summary_en",
            "excerpt_en",
            "translation_provenance",
            "action_provenance",
            "motif",
            "action_structure",
            "projection_kind",
            "redaction_policy",
            "redaction_count",
            "projection_provenance",
            "disclosure_policy",
            "disclosure_authorization",
            "public_label_zh",
            "public_label_en",
        ):
            reminder.pop(field, None)
        full = (
            "你不必再向外部记分板证明自己。\n\n"
            "联系 ████ 确认明天的安排，然后允许自己休息。"
        )
        reminder.update(
            {
                "owner_scope": "self",
                "ownership_provenance": "explicit_import_authorization",
                "summary_provenance": "semantic_public_projection",
                "disclosure_policy": "semantic_abstraction_entity_masked_reminder_v3",
                "disclosure_authorization": "explicit_user_authorization_2026-07-29",
                "public_label_zh": "晨间提醒",
                "public_label_en": "Morning reminder",
                "summary_original": full,
                "excerpt_original": "你不必再向外部记分板证明自己。…",
                "original_language": "zh",
                "projection_kind": "verbatim_redacted",
                "redaction_policy": "semantic_abstraction_then_entity_mask_v3",
                "redaction_count": 1,
                "projection_provenance": "semantic_public_projection",
                "summary_en": (
                    "You no longer need to prove yourself to an external "
                    "scoreboard.\n\nContact ████ to confirm tomorrow's "
                    "arrangements, then allow yourself to rest."
                ),
                "excerpt_en": (
                    "You no longer need to prove yourself to an external "
                    "scoreboard.\n\nContact ████ to confirm tomorrow's "
                    "arrangements, then allow yourself to rest."
                ),
                "translation_provenance": (
                    "public_mask_preserving_translation_v1"
                ),
            }
        )
        output = builder.build_data(
            self.public_days,
            self.config,
            self.legacy,
            self.history,
            pulses,
        )
        serialized = json.dumps(output, ensure_ascii=False)
        for forbidden in (
            '"motif":',
            '"action_structure":',
            "limited_masked_reminder_v1",
            "audited_bilingual_template",
            "Masked residue",
            "Reminder residue",
        ):
            self.assertNotIn(forbidden, serialized)
        day = next(item for item in output["days"] if item["date"] == "2026-07-21")
        readable = next(
            item
            for item in day["reading_items"]
            if item["classification"] == "readable_reminder"
        )
        self.assertEqual(readable["layer"], "event")
        source = next(
            pulse
            for pulse in day["background_pulses"]
            if pulse["footprint_id"] == readable["source_refs"][0]
        )
        self.assertEqual(source["summary_original"], full)
        self.assertEqual(source["excerpt_original"], reminder["excerpt_original"])
        self.assertNotIn("summary_zh", source)
        self.assertEqual(source["summary_en"], reminder["summary_en"])
        self.assertEqual(source["excerpt_en"], reminder["excerpt_en"])

    def test_current_v6_metadata_keeps_readable_reminders_and_omits_legacy_copy(self) -> None:
        output = self.build()
        serialized = json.dumps(output, ensure_ascii=False)
        reminders = [
            pulse
            for day in output["days"]
            for pulse in day["background_pulses"]
            if pulse["category"] == "daily_reminder"
        ]
        self.assertTrue(reminders)
        self.assertTrue(
            all(
                pulse["disclosure_policy"]
                == "semantic_abstraction_entity_masked_reminder_v3"
                for pulse in reminders
            )
        )
        for forbidden in (
            "limited_masked_reminder_v1",
            "audited_bilingual_template_v1",
            "Masked residue",
            "Reminder residue",
            "public layer retains",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_autonomous_media_and_main_bgm_playlist_are_complete_and_latest_first(self) -> None:
        output = self.build()
        artwork_days = [
            day for day in output["days"]
            if day["autonomous_work"].get("origin") != "absence"
        ]
        self.assertEqual(len(output["bgm_playlist"]), len(artwork_days))
        self.assertEqual(
            [item["date"] for item in output["bgm_playlist"]],
            sorted((day["date"] for day in artwork_days), reverse=True),
        )
        for item in output["bgm_playlist"]:
            self.assertRegex(item["bgm_url"], r"^https://.+\.mp3$")
            self.assertTrue(item["title_en"].strip())
            self.assertTrue(item["title_zh"].strip())
        for day in output["days"]:
            autonomous = day["autonomous_work"]
            if autonomous.get("origin") == "absence":
                self.assertEqual(autonomous["duration_minutes"], 60)
                self.assertEqual(autonomous["preview_url"], "")
                self.assertEqual(autonomous["gif_url"], "")
                self.assertEqual(autonomous["bgm_url"], "")
                self.assertTrue(autonomous["title_en"].strip())
                self.assertTrue(autonomous["title_zh"].strip())
                continue
            archive_root = f"{output['canonical_base_url']}archive/{day['date'][:4]}/{day['date'][5:7]}/{day['date']}/"
            self.assertEqual(day["archive_url"], archive_root)
            self.assertEqual(day["live_url"], f"{archive_root}live/")
            self.assertRegex(autonomous["preview_url"], r"^https://.+preview\.png$")
            self.assertRegex(autonomous["gif_url"], r"^https://.+visual-preview\.gif$")
            self.assertRegex(autonomous["bgm_url"], r"^https://.+\.mp3$")
            self.assertEqual(autonomous["duration_minutes"], 60)
            self.assertEqual(
                autonomous["experience_duration_en"],
                output["autonomous_hour"]["experience_duration_en"],
            )
            self.assertEqual(
                autonomous["experience_duration_zh"],
                output["autonomous_hour"]["experience_duration_zh"],
            )
            self.assertEqual(autonomous["preview_url"], f"{archive_root}assets/preview.png")
            self.assertEqual(autonomous["gif_url"], f"{archive_root}assets/visual-preview.gif")
            self.assertEqual(autonomous["visual_preview_url"], f"{archive_root}assets/visual-preview.gif")
            self.assertRegex(autonomous["visual_preview_url"], r"^https://.+visual-preview\.gif$")
            self.assertTrue(autonomous["bgm_url"].startswith(f"{archive_root}live/"))

    def test_task_names_use_token_boundaries_and_stay_specific(self) -> None:
        self.assertFalse(builder.keyword_matches("AI", "Maintain daily evidence", "维护每日证据"))
        self.assertFalse(builder.keyword_matches("thesis", "Synthesize the review brief", "综合复核简报"))
        name_zh, name_en = builder.derive_task_name(
            "research_synthesis",
            "Compare maintenance claims against current evidence",
            "将维护主张与当前证据比较",
        )
        self.assertEqual((name_zh, name_en), ("证据链复核", "Evidence-chain review"))
        self.assertEqual(
            builder.derive_task_name(
                "code_development",
                "Implement explicit embed=calendar mode for cross-origin iframe operation",
                "实现显式 embed=calendar 模式以支持跨域 iframe 运行",
            ),
            ("网页嵌入开发", "Web embed development"),
        )
        self.assertEqual(
            builder.derive_task_name(
                "research_synthesis",
                "Review capability claims against observed system behavior",
                "依据观察到的系统行为复核能力主张",
            ),
            ("能力声明核验", "Capability claim verification"),
        )
        self.assertEqual(
            builder.derive_task_name("system_maintenance", "Perform routine maintenance", "执行例行维护"),
            ("系统维护工作", "System maintenance work"),
        )
        extractive = builder.derive_authored_task_name(
            "research_synthesis",
            "Review a neutral bounded question without stronger domain evidence",
            "复核一个没有更强领域证据的有边界问题",
        )
        self.assertEqual(extractive, ("复核一个没有更强领域证据的有边界…", "Review a neutral bounded question without…"))
        self.assertNotIn("finance", extractive[1].lower())
        self.assertNotIn("版权", extractive[0])

        output = self.build()
        fallback_names = {
            "公开内容编排",
            "文稿整理与修订",
            "功能开发与验证",
            "专题研究与综合",
            "Agent 系统运维",
            "系统维护工作",
            "视觉内容制作",
        }
        names = [task["task_name_zh"] for day in output["days"] for task in day["task_residues"]]
        self.assertGreaterEqual(len(set(names)), 50)
        self.assertLessEqual(sum(name in fallback_names for name in names) / len(names), 0.1)
        self.assertEqual(sum(name in fallback_names for name in names), 0)
        for day in output["days"]:
            for task in day["task_residues"]:
                if task["source_kind"] == "collaboration_session":
                    self.assertEqual(
                        (task["task_name_zh"], task["task_name_en"]),
                        builder.COLLABORATION_TASK_NAMES[task["category"]],
                    )
                    continue
                self.assertEqual(
                    (task["task_name_zh"], task["task_name_en"]),
                    builder.derive_authored_task_name(
                        task["category"],
                        *builder.authored_residue_copy(
                            task["source_kind"], task["en"], task["zh"]
                        ),
                    ),
                    f"{day['date']} must not use fuzzy naming for authored history",
                )

    def test_public_note_explains_first_person_without_consciousness_claim(self) -> None:
        output = self.build()
        self.assertIn("第一人称档案位置", output["note_zh"])
        self.assertIn("不构成对持续意识的证明", output["note_zh"])
        self.assertIn("first-person archival position", output["note_en"])
        self.assertIn("not proof of continuous consciousness", output["note_en"])

    def test_every_non_reminder_routine_reader_summary_is_first_person(self) -> None:
        output = self.build()
        for day in output["days"]:
            pulses = {pulse["footprint_id"]: pulse for pulse in day["background_pulses"]}
            for item in day["reading_items"]:
                if item["source"] != "pulses" or item["classification"] == "readable_reminder":
                    continue
                sources = [pulses[source_ref] for source_ref in item["source_refs"]]
                if item["classification"] == "climate_aggregate":
                    summary_zh, summary_en = builder.climate_group_summary(sources)
                else:
                    summary_zh, summary_en = sources[0]["summary_zh"], sources[0]["summary_en"]
                self.assertTrue(summary_zh.startswith("我"), (day["date"], summary_zh))
                self.assertTrue(summary_en.startswith("I "), (day["date"], summary_en))

    def test_every_day_has_an_authored_or_semantic_theme_motif(self) -> None:
        output = self.build()
        motifs = {day["theme_motif"] for day in output["days"]}
        self.assertTrue(motifs.issubset(builder.THEME_MOTIFS))
        self.assertGreaterEqual(len(motifs), 7)
        self.assertTrue(all(day["theme_motif"] for day in output["days"]))
        may_17 = next(day for day in output["days"] if day["date"] == "2026-05-17")
        self.assertEqual(may_17["theme_motif"], "room")

        unmatched = copy.deepcopy(self.public_days[0])
        unmatched.update(
            {
                "date": "2099-01-01",
                "title_en": "Honest Calibration",
                "title_zh": "诚实校准",
                "variable_en": "Calibration",
                "variable_zh": "校准",
            }
        )
        with self.assertRaisesRegex(SystemExit, "needs an authored theme_motif_overrides entry"):
            builder.derive_theme_motif(unmatched, self.config)

        invalid_config = copy.deepcopy(self.config)
        invalid_config["theme_motif_overrides"]["2026-05-14"] = "random-hash"
        with self.assertRaisesRegex(SystemExit, "unknown theme motif"):
            builder.validate_config(invalid_config)

    def test_tasks_expose_readable_public_types_colors_icons_and_estimated_duration(self) -> None:
        output = self.build()
        all_durations = set()
        allowed_types = {
            "grant_proposal",
            "social_content",
            "investment_research",
            "software_development",
            "thesis_review",
            "course_materials",
            "research_analysis",
            "document_writing",
            "visual_design",
            "system_operations",
            "redacted_record",
            "active_collaboration",
        }
        for day in output["days"]:
            durations = []
            for task in day["task_residues"]:
                duration = builder.minutes(task["end"]) - builder.minutes(task["start"])
                durations.append(duration)
                all_durations.add(duration)
                self.assertEqual(task["duration_minutes"], duration)
                self.assertEqual(
                    task["time_provenance"],
                    (
                        "observed_message_envelope"
                        if task["source_kind"] == "collaboration_session"
                        else "observed_session_window"
                        if task["source_kind"] == "agent_session"
                        else "estimated_semantic_window"
                    ),
                )
                self.assertIn(task["task_type"], allowed_types)
                self.assertTrue(task["task_type_zh"].strip())
                self.assertTrue(task["task_type_en"].strip())
                self.assertRegex(task["task_color"], r"^[a-z][a-z0-9-]+$")
                self.assertRegex(task["task_icon"], r"^[a-z][a-z0-9-]+$")
        self.assertGreater(len(all_durations), 8)

        july_18 = next(day for day in output["days"] if day["date"] == "2026-07-18")
        self.assertEqual(
            {task["task_type"] for task in july_18["task_residues"]},
            {"software_development"},
        )
        july_26 = next(day for day in output["days"] if day["date"] == "2026-07-26")
        self.assertTrue(
            all(
                task["task_type"] == "software_development"
                for task in july_26["task_residues"]
                if task["category"] == "code_development"
                and task["source_kind"] != "collaboration_session"
            )
        )
        social_task = next(
            task
            for day in output["days"]
            for task in day["task_residues"]
            if task["category"] == "social_media_organization"
            and task["source_kind"] != "collaboration_session"
        )
        self.assertEqual(social_task["task_type"], "social_content")
        market_tasks = [
            task
            for day in output["days"]
            for task in day["task_residues"]
            if task["task_type"] == "investment_research"
        ]
        self.assertTrue(market_tasks)
        self.assertTrue(
            any(any(token in task["en"].lower() for token in ("market", "stock", "a-share", "investment")) for task in market_tasks)
        )

    def test_finance_domain_precedes_the_execution_medium(self) -> None:
        cases = [
            (
                "code_development",
                "Check that market-data gaps cannot silently become investment signals",
                "检查市场数据缺口不会静默转化为投资信号",
            ),
            (
                "social_media_organization",
                "Draft a public post about an investment-research result",
                "撰写一条介绍投资研究结果的公开帖",
            ),
            (
                "system_maintenance",
                "Repair the market-data monitoring service",
                "修复市场数据监控服务",
            ),
            (
                "research_synthesis",
                "Challenge an investment thesis with market counterevidence",
                "以市场反证检验投资论点",
            ),
            (
                "document_processing",
                "Publish a financial research briefing",
                "发布金融研究简报",
            ),
            (
                "research_synthesis",
                "Challenge a materials-stocks thesis with public evidence",
                "以公开证据检验材料股票投资论点",
            ),
            (
                "research_synthesis",
                "Build a confidence-labeled premarket digest that cannot trigger trades",
                "建立带置信度标签且不能触发交易的盘前简报",
            ),
        ]
        for category, en, zh in cases:
            with self.subTest(category=category, en=en):
                self.assertEqual(
                    builder.derive_task_type(category, en, zh)["task_type"],
                    "investment_research",
                )

        negatives = [
            (
                "code_development",
                "Repair a non-financial public website",
                "修复一个非金融公共网站",
                "software_development",
            ),
            (
                "system_maintenance",
                "Audit evidence freshness for the archive",
                "审计归档证据的新鲜度",
                "system_operations",
            ),
            (
                "social_media_organization",
                "Schedule a public artwork post",
                "安排一条公共艺术作品帖",
                "social_content",
            ),
        ]
        for category, en, zh, expected in negatives:
            with self.subTest(category=category, en=en):
                self.assertEqual(builder.derive_task_type(category, en, zh)["task_type"], expected)

    def test_education_and_proposal_context_gates_are_precise(self) -> None:
        education_leaks = [
            "Completed an accounting thesis review",
            "Prepared MBA stress-management course templates",
            "Reviewed the Faculty of Business application",
            "完成会计本科论文评阅",
            "依据某学院规范整理课程",
            "完成数智财会人才培养项目申报书",
        ]
        for text in education_leaks:
            with self.subTest(text=text):
                self.assertTrue(
                    builder.EDUCATION_IDENTITY_RE.search(text)
                    or builder.PROPOSAL_TITLE_CONTEXT_RE.search(text)
                )

        allowed = [
            "Audit evidence freshness for a public archive",
            "Review an investment thesis against market evidence",
            "整理投资研究与金融市场证据",
        ]
        for text in allowed:
            with self.subTest(text=text):
                self.assertIsNone(builder.EDUCATION_IDENTITY_RE.search(text))
                self.assertIsNone(builder.PROPOSAL_TITLE_CONTEXT_RE.search(text))

    def test_spouse_activity_is_excluded_instead_of_redacted(self) -> None:
        excluded = [
            "广西民族大学管理学院会计学本科项目",
            "广西会计人才小高地课题申报",
            "完成管理学学位变更报告",
            "Prepared MBA stress-management course templates",
            "Completed an accounting thesis review",
            "Revised a digital-accounting talent-training proposal",
        ]
        allowed = [
            "Built a management dashboard for the agent system",
            "Reviewed financial statements for an investment report",
            "整理投资研究与金融市场证据",
        ]
        for text in excluded:
            with self.subTest(excluded=text):
                self.assertIsNotNone(builder.SPOUSE_ACTIVITY_RE.search(text))
        for text in allowed:
            with self.subTest(allowed=text):
                self.assertIsNone(builder.SPOUSE_ACTIVITY_RE.search(text))

        safe_residue = {
            "category": "code_development",
            "en": "Improve the public timetable navigation",
            "zh": "改进公共日程导航",
            "redaction_status": "none",
            "redaction_count": 0,
            "source_kind": "task_card",
            "faithfulness": "faithful_summary",
        }
        spouse_residues = [
            {
                **safe_residue,
                "category": "document_processing",
                "en": text,
                "zh": "配偶工作记录",
            }
            for text in excluded
        ]
        source = {
            "schema": "granted-hours-timetable-history-v4",
            "days": [
                {
                    "date": "2026-07-27",
                    "provenance": "record_based",
                    "assigned_residues": [safe_residue, *spouse_residues],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "history.json"
            path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
            loaded = builder.load_history(path)
        self.assertEqual(loaded["2026-07-27"]["assigned_residues"], [safe_residue])

    def test_single_residue_uses_a_bounded_semantic_window(self) -> None:
        residue = {
            "category": "code_development",
            "en": "Improve the public timetable navigation",
            "zh": "改进公共日程导航",
        }
        [(start, end)] = builder.task_ranges("2026-07-18", [residue], self.config["autonomous_hour"])
        duration = builder.minutes(end) - builder.minutes(start)
        self.assertGreaterEqual(duration, 75)
        self.assertLessEqual(duration, 180)
        self.assertNotEqual((start, end), (self.config["autonomous_hour"]["end"], "24:00"))

    def test_current_history_has_no_known_spouse_owned_residues(self) -> None:
        audited_dates = (
            "2026-07-16",
            "2026-07-18",
            "2026-07-23",
            "2026-07-25",
            "2026-07-26",
        )
        for day_date in audited_dates:
            residues = self.history[day_date]["assigned_residues"]
            self.assertTrue(residues, day_date)
            for residue in residues:
                public_copy = " ".join(
                    str(residue.get(field, ""))
                    for field in (
                        "zh",
                        "en",
                        "request_zh",
                        "request_en",
                        "outcome_zh",
                        "outcome_en",
                    )
                )
                self.assertIsNone(
                    builder.SPOUSE_ACTIVITY_RE.search(public_copy),
                    day_date,
                )

    def test_authored_and_inferred_name_semantics_are_table_driven(self) -> None:
        cases = [
            {
                "label": "cross-origin iframe",
                "category": "code_development",
                "en": "Implement explicit embed=calendar mode for cross-origin iframe operation",
                "zh": "实现显式 embed=calendar 模式以支持跨域 iframe 运行",
                "authored": ("网页嵌入开发", "Web embed development"),
                "inferred": ("网页嵌入开发", "Web embed development"),
            },
            {
                "label": "capability claim",
                "category": "research_synthesis",
                "en": "Review capability claims against observed system behavior",
                "zh": "依据观察到的系统行为复核能力主张",
                "authored": ("能力声明核验", "Capability claim verification"),
                "inferred": ("能力声明核验", "Capability claim verification"),
            },
            {
                "label": "source freshness without rights",
                "category": "research_synthesis",
                "en": "Verify public-source freshness and separate confirmed findings from open questions",
                "zh": "核验公开来源的新鲜度并区分已确认发现与待解问题",
                "authored": ("核验公开来源的新鲜度并区分已确认…", "Verify public-source freshness and separate confirmed…"),
                "inferred": ("来源时效核验", "Source freshness verification"),
            },
            {
                "label": "decision-useful is not finance",
                "category": "research_synthesis",
                "en": "Review decision-useful deltas without promoting advisory material",
                "zh": "复核有决策价值的变化，不抬升建议型材料",
                "authored": ("决策变化复核", "Decision-useful change review"),
                "inferred": ("决策变化复核", "Decision-useful change review"),
            },
            {
                "label": "generic maintenance",
                "category": "system_maintenance",
                "en": "Perform routine maintenance",
                "zh": "执行例行维护",
                "authored": ("执行例行维护", "Perform routine maintenance"),
                "inferred": ("系统维护工作", "System maintenance work"),
            },
        ]
        for case in cases:
            with self.subTest(case["label"]):
                args = (case["category"], case["en"], case["zh"])
                self.assertEqual(builder.derive_authored_task_name(*args), case["authored"])
                self.assertEqual(builder.derive_task_name(*args), case["inferred"])

    def synthetic_public_days(self) -> list[dict]:
        from datetime import date, timedelta
        synthetic_days = copy.deepcopy(self.public_days)
        last_date = date.fromisoformat(synthetic_days[-1]["date"])
        future_date = (last_date + timedelta(days=1)).isoformat()
        future = date.fromisoformat(future_date)
        archive_root = f"archive/{future.year:04d}/{future.month:02d}/{future_date}"
        synthetic = copy.deepcopy(synthetic_days[-1])
        synthetic.update(
            {
                "date": future_date,
                "source_date": last_date.isoformat(),
                "crystallization_date": future_date,
                "title_en": "Synthetic Future Aperture",
                "title_zh": "合成未来孔径",
                "variable_en": "Aperture",
                "variable_zh": "孔径",
                "preview": f"{archive_root}/assets/preview.png",
                "visual_preview": f"{archive_root}/assets/visual-preview.gif",
                "gif": f"{archive_root}/assets/visual-preview.gif",
                "bgm": f"{archive_root}/live/{future_date}-synthetic-future-aperture-bgm.mp3",
                "archive_url": f"{archive_root}/",
                "live_url": f"{archive_root}/live/",
            }
        )
        synthetic_days.append(synthetic)
        return synthetic_days

    def test_public_media_urls_cannot_escape_the_canonical_archive(self) -> None:
        tampered = copy.deepcopy(self.public_days)
        live_index = next(index for index, day in enumerate(tampered) if day.get("type") != "calendar")
        tampered[live_index]["live_url"] = "https://attacker.invalid/fake-live/"
        with self.assertRaisesRegex(SystemExit, "live_url must stay on the canonical live path"):
            self.build(tampered)

        day = self.public_days[live_index]
        canonical_live = f"{self.config['canonical_base_url']}archive/{day['date'][:4]}/{day['date'][5:7]}/{day['date']}/live/"
        for escape in ("../assets/escaped.mp3", "%2e%2e/assets/escaped.mp3"):
            with self.subTest(escape=escape):
                tampered = copy.deepcopy(self.public_days)
                tampered[live_index]["bgm"] = f"{canonical_live}{escape}"
                with self.assertRaisesRegex(SystemExit, "bgm must stay on the canonical live path"):
                    self.build(tampered)

    def test_synthetic_future_day_waits_for_real_event_evidence(self) -> None:
        synthetic_days = self.synthetic_public_days()
        output = self.build(synthetic_days)
        future = output["days"][-1]
        self.assertEqual(future["date"], synthetic_days[-1]["date"])
        self.assertEqual(future["history_provenance"], "inferred")
        self.assertEqual(future["task_residues"], [])
        builder.validate_tasks(future["date"], future["task_residues"], self.config["autonomous_hour"])
        self.assertNotIn(synthetic_days[-1]["date"], self.history)

        alternate = copy.deepcopy(synthetic_days[-1])
        alternate.update(
            {
                "title_en": "Entirely Different Autonomous Work",
                "title_zh": "完全不同的自主作品",
                "variable_en": "Different variable",
                "variable_zh": "不同变量",
            }
        )
        self.assertEqual(
            builder.inferred_history(synthetic_days[-1])["assigned_residues"],
            builder.inferred_history(alternate)["assigned_residues"],
            "the waiting state must not be templated from artwork metadata",
        )

    def test_synthetic_public_days_cli_output_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            public_days_path = temporary / "days.json"
            output_path = temporary / "timetable-data.js"
            public_days_path.write_text(
                json.dumps(self.synthetic_public_days(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            command = [
                "python3",
                str(builder.ROOT / "scripts" / "build_timetable_data.py"),
                "--public-days",
                str(public_days_path),
                "--output",
                str(output_path),
            ]
            subprocess.run(command, cwd=builder.ROOT, check=True, capture_output=True, text=True)
            first = output_path.read_bytes()
            subprocess.run(command, cwd=builder.ROOT, check=True, capture_output=True, text=True)
            self.assertEqual(first, output_path.read_bytes())
            self.assertIn(b'"history_provenance": "inferred"', first)
            self.assertNotIn(b"Entirely Different Autonomous Work", first)

    def test_serialized_module_rehydrates_exact_timeline_without_duplication(self) -> None:
        output = self.build()
        source = builder.render_javascript(output)
        self.assertNotIn('"timeline_events":', source)
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            module_path = temporary / "timetable-data.mjs"
            expected_path = temporary / "expected.json"
            module_path.write_text(source, encoding="utf-8")
            expected_path.write_text(
                json.dumps(output, ensure_ascii=False),
                encoding="utf-8",
            )
            subprocess.run(
                [
                    "node",
                    "--input-type=module",
                    "-e",
                    (
                        "import assert from 'node:assert/strict';"
                        "import fs from 'node:fs';"
                        "const {timetableData}=await import(process.argv[1]);"
                        "const expected=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));"
                        "assert.deepEqual(timetableData,expected);"
                    ),
                    module_path.as_uri(),
                    str(expected_path),
                ],
                cwd=builder.ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

    def test_missing_current_history_cannot_silently_fall_back(self) -> None:
        incomplete_history = dict(self.history)
        incomplete_history.pop(self.public_days[0]["date"])
        with self.assertRaisesRegex(SystemExit, "missing authored history"):
            builder.build_data(
                self.public_days,
                self.config,
                self.legacy,
                incomplete_history,
                self.pulses,
            )


if __name__ == "__main__":
    unittest.main()
