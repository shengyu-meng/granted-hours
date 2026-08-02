#!/usr/bin/env python3
"""Deterministic public-safety tests for cron execution aggregation."""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import import_timetable_pulses as importer
import reminder_disclosure as disclosure


class TimetablePulseImporterTests(unittest.TestCase):
    @staticmethod
    def translation_catalog(
        *translations: tuple[str, str],
    ) -> dict[str, dict[str, str]]:
        catalog = {}
        for summary_original, summary_en in translations:
            source_sha256 = hashlib.sha256(
                summary_original.encode("utf-8")
            ).hexdigest()
            catalog[source_sha256] = {
                "source_sha256": source_sha256,
                "summary_en": summary_en,
                "excerpt_en": summary_en,
                "translation_provenance": (
                    importer.REMINDER_TRANSLATION_PROVENANCE
                ),
            }
        return catalog

    def test_internal_reflection_is_not_published_as_a_personal_reminder(self) -> None:
        self.assertEqual(
            importer.categorize_job("redo-reflection-daily-0750"),
            "background_routine",
        )
        self.assertEqual(
            importer.categorize_job("simon-daily-gentle-dispatch-730"),
            "daily_reminder",
        )

    def test_sensitive_reminder_becomes_routine_footprint(self) -> None:
        self.assertTrue(
            importer.reminder_requires_routine_projection(
                {"summary_original": "检查持仓、发布队列与个人恢复安排。"}
            )
        )
        self.assertFalse(
            importer.reminder_requires_routine_projection(
                {"summary_original": "先把叙事讲清楚，再继续推进。"}
            )
        )
        self.assertTrue(
            importer.reminder_requires_routine_projection(
                {"summary_original": "核对课程讲义、投资巡航与社会媒体队列。"}
            )
        )
        self.assertTrue(
            importer.reminder_requires_routine_projection(
                {"summary_original": "R-02 的 Gateway 重启flag还在等待处理。"}
            )
        )
        self.assertTrue(
            importer.reminder_requires_routine_projection(
                {"summary_original": "今天的 memory 仍然空白，明早再看 startup-brief。"}
            )
        )
        self.assertTrue(
            importer.reminder_requires_routine_projection(
                {"summary_original": "验证已执行：临时脚本完成 JSON 解析。"}
            )
        )
        self.assertTrue(
            importer.reminder_requires_routine_projection(
                {"summary_original": "Verification already completed. JSON valid: YES."}
            )
        )
        self.assertTrue(
            importer.reminder_requires_routine_projection(
                {"summary_original": "已验证完毕，JSON 有效，无需重复操作。"}
            )
        )

    def test_reminder_refresh_summary_does_not_claim_unmeasured_owner_omissions(
        self,
    ) -> None:
        snapshot = {
            "source_file_count": 1,
            "deduplicated_run_count": 1,
            "days": [
                {
                    "date": "2026-07-01",
                    "pulses": [
                        {
                            "category": "daily_reminder",
                            "projection_kind": "verbatim",
                            "count": 1,
                        }
                    ],
                }
            ],
        }
        refresh_stats = {
            "preserved_footprints": 1,
            "receipt_estimate_footprints": 0,
            "removed_stale_reminders": 0,
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            snapshot_path = Path(temporary_directory) / "snapshot.json"
            args = SimpleNamespace(
                refresh_reminders_only=True,
                dates=[],
                jobs=Path("unused-jobs.json"),
                output_dir=Path("unused-output"),
                public_days=Path("unused-days.json"),
                no_session_state=True,
                state_db=None,
                authorize_self_reminders=True,
                authorize_authentic_reminder_disclosure=True,
                private_redaction_terms=None,
                test_only_bypass_entity_detector=True,
                snapshot=snapshot_path,
                reminder_translations=importer.DEFAULT_REMINDER_TRANSLATIONS,
            )
            output = StringIO()
            with (
                mock.patch.object(importer, "parse_args", return_value=args),
                mock.patch.object(
                    importer,
                    "build_snapshot",
                    return_value=snapshot,
                ),
                mock.patch.object(
                    importer,
                    "merge_reminder_refresh",
                    return_value=(snapshot, refresh_stats),
                ),
                redirect_stdout(output),
            ):
                self.assertEqual(importer.main(), 0)

        summary = output.getvalue()
        self.assertIn("Reminder projection aggregates:", summary)
        self.assertNotIn("omitted-other-owner", summary)

    def test_date_scoped_merge_preserves_existing_days(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            snapshot_path = root / "snapshot.json"
            existing = {
                "schema": importer.PULSE_SNAPSHOT_SCHEMA,
                "timezone": "Asia/Shanghai",
                "source_file_count": 2,
                "deduplicated_run_count": 2,
                "observed_session_window_count": 2,
                "days": [
                    {"date": "2026-07-26", "pulses": [{"sentinel": "old"}]},
                    {"date": "2026-07-27", "pulses": [{"sentinel": "stale"}]},
                ],
            }
            rebuilt = {
                **existing,
                "source_file_count": 3,
                "days": [
                    {"date": "2026-07-26", "pulses": [{"sentinel": "rebuilt"}]},
                    {"date": "2026-07-27", "pulses": [{"sentinel": "new"}]},
                ],
            }
            snapshot_path.write_text(json.dumps(existing), encoding="utf-8")

            merged = importer.merge_date_scoped_snapshot(
                snapshot_path,
                rebuilt,
                {"2026-07-27"},
            )

        self.assertEqual(merged["source_file_count"], 3)
        self.assertEqual(
            merged["days"],
            [
                {"date": "2026-07-26", "pulses": [{"sentinel": "old"}]},
                {"date": "2026-07-27", "pulses": [{"sentinel": "new"}]},
            ],
        )

    def test_reminder_refresh_preserves_matching_public_footprints_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            snapshot_path = Path(temporary_directory) / "snapshot.json"
            non_reminder = {"category": "system_routine", "sentinel": "unchanged"}
            old_matching = {
                "category": "daily_reminder",
                "start": "07:59",
                "end": "08:03",
                "duration_minutes": 4,
                "execution_minutes": 3,
                "time_bucket": "morning",
                "count": 1,
                "time_provenance": "observed_session_window",
            }
            old_stale = {
                **old_matching,
                "start": "14:55",
                "end": "15:00",
                "time_bucket": "afternoon",
            }
            existing = {
                "schema": "granted-hours-timetable-pulses-v3",
                "timezone": "Asia/Shanghai",
                "days": [
                    {
                        "date": "2026-07-01",
                        "pulses": [non_reminder, old_matching, old_stale],
                    }
                ],
            }
            fresh_matching = {
                **old_matching,
                "start": "08:02",
                "end": "08:03",
                "duration_minutes": 1,
                "execution_minutes": 1,
                "time_provenance": "receipt_timestamp_estimate",
                "summary_original": "Keep the original reminder.",
                "excerpt_original": "Keep the original reminder.",
            }
            rebuilt = {
                "schema": importer.PULSE_SNAPSHOT_SCHEMA,
                "timezone": "Asia/Shanghai",
                "source_file_count": 1,
                "deduplicated_run_count": 1,
                "observed_session_window_count": 0,
                "days": [
                    {
                        "date": "2026-07-01",
                        "pulses": [fresh_matching],
                    }
                ],
            }
            snapshot_path.write_text(json.dumps(existing), encoding="utf-8")

            merged, stats = importer.merge_reminder_refresh(
                snapshot_path,
                rebuilt,
            )

        pulses = merged["days"][0]["pulses"]
        self.assertEqual(pulses[0], non_reminder)
        [reminder] = [
            pulse for pulse in pulses if pulse["category"] == "daily_reminder"
        ]
        self.assertEqual(
            (
                reminder["start"],
                reminder["end"],
                reminder["duration_minutes"],
                reminder["execution_minutes"],
                reminder["time_provenance"],
            ),
            ("07:59", "08:03", 4, 3, "observed_session_window"),
        )
        self.assertEqual(reminder["summary_original"], "Keep the original reminder.")
        self.assertEqual(
            stats,
            {
                "preserved_footprints": 1,
                "receipt_estimate_footprints": 0,
                "removed_stale_reminders": 1,
            },
        )

    def test_reminder_refresh_fails_closed_when_source_has_no_reminder_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            snapshot_path = Path(temporary_directory) / "snapshot.json"
            existing = {
                "schema": importer.PULSE_SNAPSHOT_SCHEMA,
                "timezone": "Asia/Shanghai",
                "days": [
                    {
                        "date": "2026-07-01",
                        "pulses": [
                            {
                                "category": "daily_reminder",
                                "start": "08:00",
                                "end": "08:01",
                                "time_bucket": "morning",
                                "count": 1,
                            }
                        ],
                    }
                ],
            }
            rebuilt = {
                "schema": importer.PULSE_SNAPSHOT_SCHEMA,
                "timezone": "Asia/Shanghai",
                "source_file_count": 0,
                "deduplicated_run_count": 0,
                "observed_session_window_count": 0,
                "days": [{"date": "2026-07-01", "pulses": []}],
            }
            snapshot_path.write_text(json.dumps(existing), encoding="utf-8")

            with self.assertRaisesRegex(
                SystemExit,
                "no fresh reminder evidence",
            ):
                importer.merge_reminder_refresh(snapshot_path, rebuilt)

    def test_import_uses_run_files_not_schedule_inference_and_deduplicates_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "output"
            output.mkdir()
            jobs_path = root / "jobs.json"
            days_path = root / "days.json"
            state_db_path = root / "state.db"
            jobs_path.write_text(
                json.dumps(
                    {
                        "jobs": [
                            {
                                "id": "market-job",
                                "name": "A-share market sentinel",
                                "schedule": {"kind": "cron", "expr": "0 9 * * *"},
                            },
                            {
                                "id": "brief-job",
                                "name": "AI daily briefing",
                                "schedule": {"kind": "cron", "expr": "30 8 * * *"},
                            },
                            {
                                "id": "scheduled-only",
                                "name": "U.S. market sentinel",
                                "schedule": {"kind": "cron", "expr": "0 21 * * *"},
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            days_path.write_text(
                json.dumps([{"date": "2026-07-01"}, {"date": "2026-07-02"}]),
                encoding="utf-8",
            )
            (output / "market-job").mkdir()
            (output / "brief-job").mkdir()
            (output / "market-job" / "2026-07-01_09-00-00.md").write_text(
                "private prompt with SH.123456 and account details\n## Response\n"
                "市场状态偏防守；本轮无公开动作，存在数据新鲜度警告。",
                encoding="utf-8",
            )
            (output / "market-job_20260701_090001.txt").write_text("duplicate receipt", encoding="utf-8")
            (output / "brief-job" / "2026-07-01_08-30-00.md").write_text(
                "private\n## Response\nAI 日报已完成。",
                encoding="utf-8",
            )
            (output / "unknown-run").mkdir()
            (output / "unknown-run" / "2026-07-02_15-45-00.md").write_text("private", encoding="utf-8")

            with closing(sqlite3.connect(state_db_path)) as connection:
                connection.execute(
                    "CREATE TABLE sessions (id TEXT, source TEXT, started_at REAL, ended_at REAL)"
                )
                connection.executemany(
                    "INSERT INTO sessions VALUES (?, 'cron', strftime('%s', ?), strftime('%s', ?))",
                    [
                        ("cron_market-job_20260701_085500", "2026-07-01 00:55:00", "2026-07-01 01:00:00"),
                        ("cron_brief-job_20260701_082000", "2026-07-01 00:20:00", "2026-07-01 00:30:00"),
                        ("cron_unknown-run_20260702_154400", "2026-07-02 07:44:00", None),
                    ],
                )
                connection.commit()

            snapshot = importer.build_snapshot(jobs_path, output, days_path, state_db_path)

        self.assertEqual(snapshot["schema"], importer.PULSE_SNAPSHOT_SCHEMA)
        self.assertEqual(snapshot["source_file_count"], 4)
        self.assertEqual(snapshot["deduplicated_run_count"], 3)
        self.assertEqual(snapshot["observed_session_window_count"], 2)
        first_day = snapshot["days"][0]["pulses"]
        self.assertEqual([(pulse["start"], pulse["end"]) for pulse in first_day], [("08:20", "08:30"), ("08:55", "09:00")])
        self.assertEqual([pulse["duration_minutes"] for pulse in first_day], [10, 5])
        self.assertTrue(all(pulse["time_provenance"] == "observed_session_window" for pulse in first_day))
        market = first_day[1]
        self.assertIn("防守", market["summary_zh"])
        self.assertIn("新鲜度警告", market["summary_zh"])
        self.assertEqual(market["summary_provenance"], "derived_public_safe")
        fallback = snapshot["days"][1]["pulses"][0]
        self.assertEqual((fallback["start"], fallback["end"]), ("15:44", "15:45"))
        self.assertEqual(fallback["time_provenance"], "receipt_timestamp_estimate")
        serialized = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        for forbidden in (
            "market-job",
            "brief-job",
            "scheduled-only",
            "unknown-run",
            "sentinel",
            "SH.123456",
            "account details",
            "private prompt",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_ai_failure_summary_does_not_invent_login_or_private_state(self) -> None:
        summary_zh, summary_en = importer.public_summary("ai_daily_brief", ["# 采集异常诊断"], 1)
        self.assertIn("未达发布闸门", summary_zh)
        self.assertIn("did not pass", summary_en)
        self.assertNotIn("登录态", summary_zh)
        self.assertNotIn("login", summary_en.lower())

        normal_zh, normal_en = importer.public_summary(
            "ai_daily_brief",
            ["No collection failure was observed; the normal brief completed."],
            1,
        )
        self.assertIn("完成 1 次", normal_zh)
        self.assertIn("completed", normal_en)

        for negated in (
            "并非不发正常 AI 日报；常规日报已经完成。",
            "No collection failure was observed; the normal brief completed.",
            "Status: no collection failure.",
        ):
            normal_zh, normal_en = importer.public_summary("ai_daily_brief", [negated], 1)
            self.assertIn("完成 1 次", normal_zh)
            self.assertIn("completed", normal_en)

        failure_zh, failure_en = importer.public_summary(
            "ai_daily_brief",
            ["Status: collection failure"],
            1,
        )
        self.assertIn("未达发布闸门", failure_zh)
        self.assertIn("did not pass", failure_en)

    def reminder_fixture(
        self,
        root: Path,
        responses: list[tuple[str, str]],
    ) -> tuple[Path, Path, Path]:
        output = root / "output"
        output.mkdir()
        jobs_path = root / "jobs.json"
        days_path = root / "days.json"
        jobs_path.write_text(
            json.dumps(
                {"jobs": [{"id": "reminder-job", "name": "daily reminder"}]}
            ),
            encoding="utf-8",
        )
        dates = sorted({stamp[:10] for stamp, _ in responses})
        days_path.write_text(
            json.dumps([{"date": day_date} for day_date in dates]),
            encoding="utf-8",
        )
        (output / "reminder-job").mkdir()
        for stamp, response in responses:
            (output / "reminder-job" / f"{stamp}.md").write_text(
                f"private prompt\n## Response\n{response}",
                encoding="utf-8",
            )
        return jobs_path, output, days_path

    def test_reminder_ownership_requires_explicit_import_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            jobs_path, output, days_path = self.reminder_fixture(
                root,
                [("2026-07-01_08-00-00", "允许自己休息。")],
            )

            unverified = importer.build_snapshot(
                jobs_path,
                output,
                days_path,
                None,
            )["days"][0]["pulses"][0]
            authorized = importer.build_snapshot(
                jobs_path,
                output,
                days_path,
                None,
                authorize_self_reminders=True,
                authorize_authentic_reminder_disclosure=True,
                allow_entity_detector_bypass_for_tests=True,
                reminder_translations=self.translation_catalog(
                    ("允许自己休息。", "Allow yourself to rest.")
                ),
            )["days"][0]["pulses"][0]

        self.assertEqual(unverified["owner_scope"], "unknown")
        self.assertEqual(unverified["ownership_provenance"], "unverified")
        self.assertEqual(authorized["owner_scope"], "self")
        self.assertEqual(
            authorized["ownership_provenance"],
            "explicit_import_authorization",
        )
        self.assertEqual(
            authorized["disclosure_policy"],
            "semantic_abstraction_entity_masked_reminder_v3",
        )
        self.assertEqual(authorized["summary_original"], "允许自己休息。")
        self.assertEqual(authorized["summary_en"], "Allow yourself to rest.")
        self.assertEqual(authorized["excerpt_en"], "Allow yourself to rest.")
        self.assertEqual(
            authorized["translation_provenance"],
            importer.REMINDER_TRANSLATION_PROVENANCE,
        )
        self.assertNotIn("action_provenance", authorized)

    def test_reminder_and_translation_apply_market_private_denylists_with_parity(
        self,
    ) -> None:
        source = (
            "Source Studio 提醒：关注 HOLDX 的公开价格；"
            "HOLDX 报 24.60 美元，保持耐心。"
        )
        translation = (
            "Source Studio reminder: watch HOLDX's public price; "
            "HOLDX is at $24.60, and stay patient."
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            jobs_path, output, days_path = self.reminder_fixture(
                root,
                [("2026-07-01_08-00-00", source)],
            )
            snapshot = importer.build_snapshot(
                jobs_path,
                output,
                days_path,
                None,
                authorize_self_reminders=True,
                authorize_authentic_reminder_disclosure=True,
                holdings_terms=("HOLDX",),
                source_terms=("Source Studio",),
                allow_entity_detector_bypass_for_tests=True,
                reminder_translations=self.translation_catalog(
                    (source, translation)
                ),
            )

        pulse = snapshot["days"][0]["pulses"][0]
        serialized = json.dumps(pulse, ensure_ascii=False)
        for private_term in ("HOLDX", "Source Studio"):
            self.assertNotIn(private_term, serialized)
        self.assertIn("24.60", pulse["summary_original"])
        self.assertIn("24.60", pulse["summary_en"])
        source_masks = importer.mask_token_count(
            pulse["summary_original"],
            "synthetic source",
        )
        translation_masks = importer.mask_token_count(
            pulse["summary_en"],
            "synthetic translation",
        )
        self.assertEqual(source_masks, translation_masks)
        self.assertEqual(
            importer.mask_token_count(
                pulse["excerpt_original"],
                "synthetic source excerpt",
            ),
            importer.mask_token_count(
                pulse["excerpt_en"],
                "synthetic translation excerpt",
            ),
        )
        self.assertEqual(pulse["redaction_count"], source_masks)
        self.assertEqual(pulse["projection_kind"], "verbatim_redacted")

    def test_existing_reminder_resanitization_uses_pre_sanitization_sidecar_hash(
        self,
    ) -> None:
        source = "Source Studio: HOLDX 报 24.60 美元；继续观察 HOLDX。"
        translation = (
            "Source Studio: HOLDX is at $24.60; keep watching HOLDX."
        )
        pulse = {
            "category": "daily_reminder",
            "summary_provenance": "semantic_public_projection",
            "summary_original": source,
            "excerpt_original": source,
            "summary_en": translation,
            "excerpt_en": translation,
            "redaction_count": 0,
            "projection_kind": "verbatim",
            "semantic_abstraction_count": 0,
        }
        snapshot = {
            "schema": importer.PULSE_SNAPSHOT_SCHEMA,
            "days": [{"date": "2026-07-01", "pulses": [pulse]}],
        }
        source_sha256 = hashlib.sha256(source.encode("utf-8")).hexdigest()
        translations = {
            source_sha256: {
                "source_sha256": source_sha256,
                "summary_en": translation,
                "excerpt_en": disclosure.extractive_prefix(translation),
                "translation_provenance": importer.REMINDER_TRANSLATION_PROVENANCE,
            }
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            snapshot_path = Path(temporary_directory) / "snapshot.json"
            snapshot_path.write_text(
                json.dumps(snapshot, ensure_ascii=False),
                encoding="utf-8",
            )
            sanitized, stats = importer.resanitize_existing_reminders(
                snapshot_path=snapshot_path,
                translations=translations,
                holdings_terms=("HOLDX",),
                source_terms=("Source Studio",),
            )
            snapshot_path.write_text(
                json.dumps(sanitized, ensure_ascii=False),
                encoding="utf-8",
            )
            repeated, repeated_stats = importer.resanitize_existing_reminders(
                snapshot_path=snapshot_path,
                translations=translations,
                holdings_terms=("HOLDX",),
                source_terms=("Source Studio",),
            )

        sanitized_pulse = sanitized["days"][0]["pulses"][0]
        serialized = json.dumps(sanitized_pulse, ensure_ascii=False)
        for private_term in ("HOLDX", "Source Studio"):
            self.assertNotIn(private_term, serialized)
        self.assertEqual(stats, {"checked": 1, "changed": 1, "already_sanitized": 0})
        self.assertEqual(
            repeated_stats,
            {"checked": 1, "changed": 0, "already_sanitized": 1},
        )
        self.assertEqual(repeated, sanitized)
        self.assertEqual(
            importer.mask_token_count(
                sanitized_pulse["summary_original"],
                "synthetic migrated source",
            ),
            importer.mask_token_count(
                sanitized_pulse["summary_en"],
                "synthetic migrated translation",
            ),
        )
        self.assertEqual(
            importer.mask_token_count(
                sanitized_pulse["excerpt_original"],
                "synthetic migrated source excerpt",
            ),
            importer.mask_token_count(
                sanitized_pulse["excerpt_en"],
                "synthetic migrated translation excerpt",
            ),
        )

    def test_excerpt_parity_is_rebuilt_as_faithful_extractive_prefixes(self) -> None:
        source = ("开头 " * 8) + "████ " + ("后续公开提醒。" * 60)
        translation = ("Opening public reminder. " * 18) + "████ " + (
            "Continue the public reminder. " * 20
        )
        projection = {
            "summary_original": source,
            "excerpt_original": disclosure.extractive_prefix(source),
            "redaction_count": 1,
        }
        source_sha256 = hashlib.sha256(source.encode("utf-8")).hexdigest()
        translations = {
            source_sha256: {
                "source_sha256": source_sha256,
                "summary_en": translation,
                "excerpt_en": disclosure.extractive_prefix(translation),
                "translation_provenance": importer.REMINDER_TRANSLATION_PROVENANCE,
            }
        }
        result = importer.translation_for_reminder(projection, translations)
        self.assertEqual(
            importer.mask_token_count(
                result["excerpt_original"],
                "balanced source excerpt",
            ),
            importer.mask_token_count(
                result["excerpt_en"],
                "balanced English excerpt",
            ),
        )
        self.assertTrue(
            result["summary_original"].startswith(
                result["excerpt_original"].removesuffix("…")
            )
        )
        self.assertTrue(
            result["summary_en"].startswith(
                result["excerpt_en"].removesuffix("…")
            )
        )

    def test_exact_emotional_reminder_passes_through_without_translation(self) -> None:
        source = "今天有没有靠近源泉？外部记分板今天是否过响？允许自己休息。"
        projection = importer.project_limited_reminder_response(
            [source],
            "morning",
        )
        self.assertEqual(projection["summary_original"], source)
        self.assertEqual(projection["excerpt_original"], source)
        self.assertEqual(projection["original_language"], "zh")
        self.assertEqual(projection["projection_kind"], "verbatim")
        self.assertEqual(projection["redaction_count"], 0)
        self.assertEqual(
            projection["projection_provenance"],
            "semantic_public_projection",
        )
        self.assertNotIn("summary_zh", projection)
        self.assertNotIn("summary_en", projection)

    def test_private_context_is_abstracted_before_public_projection(self) -> None:
        source = "记录今天的低能量和情绪状态，然后安排恢复。"
        projection = importer.project_limited_reminder_response(
            [source],
            "evening",
        )
        self.assertNotIn("低能量", projection["summary_original"])
        self.assertNotIn("情绪状态", projection["summary_original"])
        self.assertIn("恢复安排", projection["summary_original"])
        self.assertEqual(projection["semantic_abstraction_count"], 1)
        self.assertEqual(projection["projection_kind"], "semantic_abstracted")

    def test_source_sections_keep_order_paragraphs_and_exact_dedup_only(self) -> None:
        first = "先问自己：\n\n- 我累了吗？\n- 我需要休息吗？"
        second = "Then leave uncertainty open."
        projection = importer.project_limited_reminder_response(
            [first, "[SILENT]", first, "", second],
            "evening",
        )
        self.assertEqual(projection["summary_original"], f"{first}\n\n{second}")
        self.assertEqual(projection["original_language"], "mixed")

    def test_synthetic_person_work_project_school_and_unit_are_masked(self) -> None:
        response = (
            "联系 Mara Lin，在 Northlake School 的 Aurora Unit 讨论项目《Orchid "
            "Lantern》，以及名为 “Blue Echo” 的作品。然后允许自己休息。"
        )
        projection = importer.project_limited_reminder_response(
            [response],
            "midday",
            detected_entities=(
                "Mara Lin",
                "Northlake School",
                "Aurora Unit",
            ),
        )
        serialized = json.dumps(projection, ensure_ascii=False, sort_keys=True)
        for value in (
            "Mara Lin",
            "Northlake School",
            "Aurora Unit",
            "Orchid Lantern",
            "Blue Echo",
        ):
            self.assertNotIn(value, serialized)
        self.assertIn("讨论项目《████》", projection["summary_original"])
        self.assertIn("然后允许自己休息。", projection["summary_original"])
        self.assertEqual(projection["projection_kind"], "verbatim_redacted")
        self.assertEqual(
            projection["redaction_policy"],
            "semantic_abstraction_then_entity_mask_v3",
        )
        self.assertNotIn("motif", projection)
        self.assertNotIn("action_structure", projection)

    def test_corner_quotes_backticks_and_bold_artwork_titles_are_masked(self) -> None:
        source = (
            "黑昼今早完成了「Appeal That Does Not Beg」；"
            "昨晚做完了 `Consent Escrow / 同意托管`。"
            "新的互动网页作品：**Dormancy Garden / 休眠花园**。"
            "如果有精力，看看“不下跪的感激”的那个 Canvas 作品。"
        )
        projection = importer.project_limited_reminder_response([source], "morning")
        assert projection is not None
        serialized = json.dumps(projection, ensure_ascii=False)
        for title in (
            "Appeal That Does Not Beg",
            "Consent Escrow",
            "同意托管",
            "Dormancy Garden",
            "休眠花园",
            "不下跪的感激",
        ):
            self.assertNotIn(title, serialized)
        self.assertIn("完成了「████」", projection["summary_original"])
        self.assertIn("作品：**████**", projection["summary_original"])

    def test_ordinary_quotes_dates_and_times_are_not_entities(self) -> None:
        source = "记住“你已经足够了”，明天 2026-07-29 08:30 再看；不要急着回答。"
        projection = importer.project_limited_reminder_response(
            [source],
            "morning",
        )
        self.assertEqual(projection["summary_original"], source)
        self.assertEqual(projection["redaction_count"], 0)

    def test_long_excerpt_is_a_literal_extractive_prefix(self) -> None:
        source = "".join(
            f"第{i}句话提醒你照顾自己的感受，并且保留不确定性。"
            for i in range(1, 260)
        )
        projection = importer.project_limited_reminder_response(
            [source],
            "morning",
        )
        summary = projection["summary_original"]
        excerpt = projection["excerpt_original"]
        self.assertGreater(len(summary), 5000)
        self.assertLessEqual(len(excerpt), 260)
        self.assertTrue(excerpt.endswith("…"))
        self.assertEqual(excerpt[:-1], summary[: len(excerpt) - 1])
        self.assertEqual(excerpt.count("…"), 1)

    def test_empty_and_silent_reminder_can_be_omitted(self) -> None:
        self.assertIsNone(
            importer.project_limited_reminder_response(
                ["", "  ", "[SILENT]", " [SILENT] "],
                "morning",
            )
        )

    def test_private_exact_terms_are_longest_first_and_never_serialized(self) -> None:
        source = "Meet PRIVATE CORMORANT STUDIO and cormorant tomorrow."
        projection = importer.project_limited_reminder_response(
            [source],
            "morning",
            exact_terms=("Cormorant", "Private Cormorant Studio"),
        )
        serialized = json.dumps(projection, ensure_ascii=False)
        self.assertNotIn("private cormorant studio", serialized.casefold())
        self.assertNotIn("cormorant", serialized.casefold())
        self.assertNotIn("exact_terms", serialized)
        self.assertNotRegex(projection["summary_original"], r"█{5,}")

        with tempfile.TemporaryDirectory() as temporary_directory:
            private_dir = Path(temporary_directory) / ".private"
            private_dir.mkdir()
            terms_path = private_dir / "reminder-redactions.json"
            terms_path.write_text(
                json.dumps({"terms": ["Private Cormorant Studio", "Cormorant"]}),
                encoding="utf-8",
            )
            self.assertEqual(
                importer.load_private_redaction_terms(terms_path),
                ("Private Cormorant Studio", "Cormorant"),
            )

    def test_technical_secrets_are_removed_without_phone_date_confusion(self) -> None:
        phone = "138-" + "1234-" + "5678"
        secret_label = "pass" + "word"
        routing_label = "chat" + "_id"
        routing_id = "-100" + "1234567890"
        source = (
            "保留日期 2026-07-29 和时间 08:30。联系 care@example.com 或 "
            f"{phone}；{secret_label}=hunter-echo-77，{routing_label}={routing_id}。"
            "查看 [项目说明](https://example.com/private?id=abc) 与 "
            "`/Users/example/private/note.md`；状态库 state.db，调度目录 cron/output。"
        )
        projection = importer.project_limited_reminder_response([source], "morning")
        assert projection is not None
        masked = projection["summary_original"]
        self.assertIn("2026-07-29", masked)
        self.assertIn("08:30", masked)
        self.assertIn("项目说明", masked)
        self.assertIn("`████`", masked)
        self.assertEqual(projection["redaction_count"], masked.count("████"))
        for secret in (
            "care@example.com",
            phone,
            "hunter-echo-77",
            routing_id,
            "https://example.com",
            "/Users/example",
            "state.db",
            "cron/output",
        ):
            self.assertNotIn(secret, masked)

    def test_batch_detector_is_called_once_for_an_authorized_import(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            jobs_path, output, days_path = self.reminder_fixture(
                root,
                [
                    ("2026-07-01_08-00-00", "Meet Ada at Acme Studio."),
                    ("2026-07-02_18-00-00", "Meet Grace at North Lab."),
                ],
            )
            calls: list[list[str]] = []

            def detector(texts: list[str]) -> list[dict[str, list[str]]]:
                calls.append(texts)
                return [
                    {"PersonalName": ["Ada"], "OrganizationName": ["Acme Studio"]},
                    {"PersonalName": ["Grace"], "OrganizationName": ["North Lab"]},
                ]

            snapshot = importer.build_snapshot(
                jobs_path,
                output,
                days_path,
                None,
                authorize_self_reminders=True,
                authorize_authentic_reminder_disclosure=True,
                entity_detector=detector,
                reminder_translations=self.translation_catalog(
                    ("Meet ████ at ████.", "Meet ████ at ████.")
                ),
            )

        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0]), 2)
        serialized = json.dumps(snapshot, ensure_ascii=False)
        for entity in ("Ada", "Acme Studio", "Grace", "North Lab"):
            self.assertNotIn(entity, serialized)
        for day in snapshot["days"]:
            [pulse] = day["pulses"]
            self.assertEqual(
                pulse["disclosure_policy"],
                "semantic_abstraction_entity_masked_reminder_v3",
            )
            self.assertNotIn("summary_zh", pulse)
            self.assertEqual(pulse["summary_en"], "Meet ████ at ████.")
            self.assertNotIn("action_provenance", pulse)

    def test_authentic_reminder_translation_lookup_fails_closed(self) -> None:
        projection = {
            "summary_original": "允许 ████ 休息。",
            "excerpt_original": "允许 ████ 休息。",
            "redaction_count": 1,
        }
        source_sha256 = hashlib.sha256(
            projection["summary_original"].encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(
            SystemExit,
            f"Missing reminder translation for source_sha256 {source_sha256}",
        ):
            importer.translation_for_reminder(projection, {})

        mismatched = self.translation_catalog(
            (projection["summary_original"], "Allow yourself to rest.")
        )
        with self.assertRaisesRegex(
            SystemExit,
            "summary mask parity mismatch",
        ):
            importer.translation_for_reminder(projection, mismatched)

    def test_snapshot_gate_rejects_excerpt_mismatch(self) -> None:
        snapshot = {
            "days": [
                {
                    "date": "2026-07-01",
                    "pulses": [
                        {
                            "category": "daily_reminder",
                            "summary_provenance": "semantic_public_projection",
                            "summary_original": "允许 ████ 休息。",
                            "summary_en": "Allow ████ to rest.",
                            "excerpt_original": "允许 ████ 休息。",
                            "excerpt_en": "Allow yourself to rest.",
                            "redaction_count": 1,
                        }
                    ],
                }
            ]
        }
        with self.assertRaisesRegex(SystemExit, "excerpt mask parity mismatch"):
            importer.validate_snapshot_reminder_parity(snapshot)

    def test_translation_catalog_loader_rejects_invalid_english(self) -> None:
        summary_original = "允许自己休息。"
        translations = self.translation_catalog(
            (summary_original, "Allow yourself to rest.")
        )
        catalog_source = {
            "schema": importer.REMINDER_TRANSLATION_SCHEMA,
            "translation_provenance": (
                importer.REMINDER_TRANSLATION_PROVENANCE
            ),
            "translations": translations,
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "translations.json"
            path.write_text(json.dumps(catalog_source), encoding="utf-8")
            self.assertEqual(
                importer.load_reminder_translations(path),
                translations,
            )
            record = next(iter(catalog_source["translations"].values()))
            record["summary_en"] = "允许自己休息。"
            record["excerpt_en"] = "允许自己休息。"
            path.write_text(json.dumps(catalog_source), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "summary_en contains CJK"):
                importer.load_reminder_translations(path)

    def test_authorized_detector_failure_fails_closed_without_test_bypass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            jobs_path, output, days_path = self.reminder_fixture(
                root,
                [("2026-07-01_08-00-00", "Meet Ada.")],
            )

            def failed_detector(_texts: list[str]) -> list[dict[str, list[str]]]:
                raise disclosure.EntityDetectionError("synthetic failure")

            with self.assertRaisesRegex(SystemExit, "entity detection failed closed"):
                importer.build_snapshot(
                    jobs_path,
                    output,
                    days_path,
                    None,
                    authorize_self_reminders=True,
                    authorize_authentic_reminder_disclosure=True,
                    entity_detector=failed_detector,
                )

    @unittest.skipUnless(
        sys.platform == "darwin" and shutil.which("swift"),
        "Apple NaturalLanguage helper requires macOS and Swift",
    )
    def test_swift_batch_helper_has_synthetic_json_contract(self) -> None:
        result = importer.detect_reminder_entities_batch(
            ["Ada Lovelace met the team at OpenAI.", "今天允许自己休息。"]
        )
        self.assertEqual(len(result), 2)
        for entry in result:
            self.assertEqual(set(entry), {"PersonalName", "OrganizationName"})
            self.assertTrue(
                all(
                    isinstance(value, str)
                    for values in entry.values()
                    for value in values
                )
            )

    def test_adjacent_invalid_run_cannot_borrow_same_job_valid_window(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "output"
            output.mkdir()
            jobs_path = root / "jobs.json"
            days_path = root / "days.json"
            state_db_path = root / "state.db"
            jobs_path.write_text(
                json.dumps({"jobs": [{"id": "same-job", "name": "system health routine"}]}),
                encoding="utf-8",
            )
            days_path.write_text(json.dumps([{"date": "2026-07-03"}]), encoding="utf-8")
            (output / "same-job").mkdir()
            (output / "same-job" / "2026-07-03_09-00-00.md").write_text(
                "private\n## Response\n[SILENT]",
                encoding="utf-8",
            )
            (output / "same-job" / "2026-07-03_09-10-00.md").write_text(
                "private\n## Response\n[SILENT]",
                encoding="utf-8",
            )
            (output / "same-job" / "2026-07-03_09-20-00.md").write_text(
                "private\n## Response\n[SILENT]",
                encoding="utf-8",
            )

            with closing(sqlite3.connect(state_db_path)) as connection:
                connection.execute(
                    "CREATE TABLE sessions (id TEXT, source TEXT, started_at REAL, ended_at REAL)"
                )
                connection.executemany(
                    "INSERT INTO sessions VALUES (?, 'cron', strftime('%s', ?), strftime('%s', ?))",
                    [
                        ("cron_same-job_20260703_085000", "2026-07-03 00:50:00", "2026-07-03 00:58:00"),
                        ("cron_same-job_20260703_085900", "2026-07-03 00:59:00", None),
                        ("cron_same-job_20260703_090400", "2026-07-03 01:04:00", "2026-07-03 01:10:00"),
                    ],
                )
                connection.commit()

            snapshot = importer.build_snapshot(jobs_path, output, days_path, state_db_path)

        pulses = snapshot["days"][0]["pulses"]
        self.assertEqual(len(pulses), 3)
        self.assertEqual(
            [(pulse["start"], pulse["end"], pulse["time_provenance"]) for pulse in pulses],
            [
                ("08:59", "09:00", "receipt_timestamp_estimate"),
                ("09:04", "09:10", "observed_session_window"),
                ("09:19", "09:20", "receipt_timestamp_estimate"),
            ],
        )
        self.assertEqual(snapshot["observed_session_window_count"], 1)

    def test_absent_source_behavior_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            days_path = root / "days.json"
            days_path.write_text(json.dumps([{"date": "2026-07-01"}]), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "Cron jobs source does not exist"):
                importer.build_snapshot(root / "missing-jobs.json", root / "missing-output", days_path)


if __name__ == "__main__":
    unittest.main()
