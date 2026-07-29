#!/usr/bin/env python3
"""Deterministic public-safety tests for cron execution aggregation."""
from __future__ import annotations

import json
import sqlite3
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
                            "projection_kind": "inner_weather",
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
                authorize_self_reminder_residues=True,
                authorize_limited_reminder_disclosure=True,
                snapshot=snapshot_path,
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
                "summary_zh": "固定公开模板。",
                "summary_en": "Fixed public template.",
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
        self.assertEqual(reminder["summary_en"], "Fixed public template.")
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

    def test_reminder_ownership_requires_explicit_import_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
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
            days_path.write_text(
                json.dumps([{"date": "2026-07-01"}]),
                encoding="utf-8",
            )
            (output / "reminder-job").mkdir()
            (output / "reminder-job" / "2026-07-01_08-00-00.md").write_text(
                "private prompt\n## Response\nprivate response",
                encoding="utf-8",
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
            )["days"][0]["pulses"][0]

        self.assertEqual(unverified["owner_scope"], "unknown")
        self.assertEqual(unverified["ownership_provenance"], "unverified")
        self.assertEqual(authorized["owner_scope"], "self_scheduler_residue")
        self.assertEqual(
            authorized["ownership_provenance"],
            "explicit_import_authorization",
        )
        self.assertEqual(
            authorized["action_provenance"],
            "no_authorized_action_semantics",
        )
        self.assertEqual(authorized["summary_zh"], "提醒残留。")
        self.assertEqual(authorized["summary_en"], "Reminder residue.")

    def test_limited_disclosure_requires_a_separate_explicit_policy_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
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
            days_path.write_text(
                json.dumps([{"date": "2026-07-01"}]),
                encoding="utf-8",
            )
            (output / "reminder-job").mkdir()
            (output / "reminder-job" / "2026-07-01_08-00-00.md").write_text(
                "private prompt\n## Response\n靠近源泉。",
                encoding="utf-8",
            )

            old_policy = importer.build_snapshot(
                jobs_path,
                output,
                days_path,
                None,
                authorize_self_reminders=True,
            )["days"][0]["pulses"][0]
            limited = importer.build_snapshot(
                jobs_path,
                output,
                days_path,
                None,
                authorize_self_reminders=True,
                authorize_limited_reminder_disclosure=True,
            )["days"][0]["pulses"][0]

        self.assertEqual(
            old_policy["action_provenance"],
            "no_authorized_action_semantics",
        )
        self.assertNotIn("disclosure_policy", old_policy)
        self.assertEqual(
            limited["disclosure_policy"],
            "limited_masked_reminder_v1",
        )
        self.assertEqual(
            limited["disclosure_authorization"],
            "explicit_user_authorization_2026-07-29",
        )
        self.assertEqual(
            limited["action_provenance"],
            "limited_masked_action_semantics_v1",
        )
        self.assertEqual(limited["motif"], "source_proximity")
        self.assertNotEqual(limited["summary_zh"], "提醒残留。")

    def test_exact_allowed_motif_maps_to_one_audited_bilingual_template(self) -> None:
        projection = importer.project_limited_reminder_response(
            ["靠近源泉。"],
            "morning",
        )
        self.assertEqual(projection["motif"], "source_proximity")
        self.assertEqual(projection["projection_kind"], "inner_weather")
        self.assertEqual(projection["label_zh"], "晨间校准")
        self.assertEqual(projection["label_en"], "Morning calibration")
        self.assertEqual(
            projection["summary_zh"],
            "这次校准把注意力重新带回内在源头。",
        )
        self.assertEqual(
            projection["summary_en"],
            "This calibration brings attention back toward an inner source.",
        )
        self.assertEqual(projection["redaction_count"], 0)
        self.assertEqual(
            projection["projection_provenance"],
            "audited_bilingual_template_v1",
        )

    def test_exact_external_scoreboard_phrase_is_allowed_without_a_score_catch_all(
        self,
    ) -> None:
        for phrase in ("外部记分板", "external scoreboard"):
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    disclosure.classify_motif(phrase),
                    "external_scoreboard",
                )
        for arbitrary in (
            "今天整理了一块外部展板。",
            "The score was saved for an unrelated game.",
            "A wholly unrelated sentence.",
        ):
            with self.subTest(arbitrary=arbitrary):
                self.assertEqual(disclosure.classify_motif(arbitrary), "none")

    def test_exact_self_compassion_phrases_are_conservative(self) -> None:
        allowed = (
            "给自己一点安慰。",
            "愿这句话带来宽慰。",
            "没关系。",
            "辛苦了。",
            "今天也要照顾自己。",
            "请对自己温柔。",
            "允许自己。",
            "允许自己休息。",
            "不必向任何人证明自己。",
            "不用再证明你值得被爱。",
            "It's okay.",
            "Be gentle with yourself.",
            "You are enough.",
            "You do not have to prove yourself.",
            "You don't have to prove that you are enough.",
        )
        for phrase in allowed:
            with self.subTest(phrase=phrase):
                self.assertEqual(disclosure.classify_motif(phrase), "comfort_rest")

        operational = (
            "允许任务写入缓存。",
            "允许自己访问生产数据库。",
            "不必重启服务。",
            "不用证明文件也可以提交申请。",
            "You do not have to prove the theorem in this test.",
            "The deployment score remained stable.",
        )
        for phrase in operational:
            with self.subTest(phrase=phrase):
                self.assertEqual(disclosure.classify_motif(phrase), "none")

    def test_fixed_masked_templates_are_immersive_and_classifier_faithful(
        self,
    ) -> None:
        expected = {
            "document_or_learning_action": (
                "这一天只显出一处与 ████ 相关的文档或学习轮廓；对象与去向保持遮挡。",
                "This day reveals only a document or learning contour around ████; "
                "the subject and destination remain masked.",
            ),
            "collaboration_or_meeting_action": (
                "这一天只显出一处与 ████ 相关的协作或会面轮廓；角色与议题保持遮挡。",
                "This day reveals only a collaboration or meeting contour around ████; "
                "roles and topic remain masked.",
            ),
            "project_or_delivery_action": (
                "一项围绕 ████ 的项目或交付轮廓，是公开层留下的全部。",
                "A project or delivery contour around ████ is all the public layer retains.",
            ),
            "private_life_logistics": (
                "这一天有一部分生活被留在 ████ 之后；公开层不再追问。",
                "A part of this day's life remains behind ████; "
                "the public layer asks no further.",
            ),
            "relationship_action": (
                "这一天只显出一处与 ████ 相关的联系或关系轮廓；人物与缘由保持遮挡。",
                "This day reveals only a contact or relational contour around ████; "
                "people and reasons remain masked.",
            ),
        }
        for action_structure, (expected_zh, expected_en) in expected.items():
            with self.subTest(action_structure=action_structure):
                projection = disclosure.render_reminder_projection(
                    "none",
                    action_structure,
                    "afternoon",
                )
                self.assertEqual(projection["summary_zh"], expected_zh)
                self.assertEqual(projection["summary_en"], expected_en)
                self.assertEqual(projection["redaction_count"], 1)

        opaque = disclosure.render_reminder_projection("none", "none", "afternoon")
        self.assertEqual(opaque["summary_zh"], "这条提醒只留下：████。")
        self.assertEqual(opaque["summary_en"], "This reminder leaves only this: ████.")

    def test_limited_projection_never_passes_raw_spans_and_masks_concrete_action(self) -> None:
        synthetic_values = (
            "Aster Vale",
            "Thesis Kestrel",
            "Northlake Institute",
            "USD 48,291",
            "ACCT-Z9Q4",
            "Juniper condition",
            "Rowan household",
            "Harbor City",
        )
        response = (
            "You may rest and meet fatigue with care. "
            "Review Thesis Kestrel with Aster Vale at Northlake Institute; "
            "the private logistics mention USD 48,291, ACCT-Z9Q4, "
            "Juniper condition, Rowan household, and Harbor City."
        )
        projection = importer.project_limited_reminder_response(
            [response],
            "evening",
        )
        serialized = json.dumps(projection, ensure_ascii=False, sort_keys=True)
        for value in synthetic_values:
            self.assertNotIn(value, serialized)
        self.assertNotIn(response, serialized)
        self.assertEqual(projection["motif"], "comfort_rest")
        self.assertEqual(
            projection["action_structure"],
            "document_or_learning_action",
        )
        self.assertEqual(projection["projection_kind"], "combined")
        self.assertEqual(projection["redaction_policy"], "fixed_template_blocks_v1")
        self.assertEqual(projection["redaction_count"], 1)
        self.assertEqual(
            projection["summary_zh"].count(importer.FIXED_REDACTION_BLOCK),
            1,
        )
        self.assertEqual(
            projection["summary_en"].count(importer.FIXED_REDACTION_BLOCK),
            1,
        )

    def test_secret_length_does_not_change_masked_structural_output(self) -> None:
        short = importer.project_limited_reminder_response(
            ["Review thesis Q at Institute R."],
            "afternoon",
        )
        long = importer.project_limited_reminder_response(
            [
                "Review thesis QQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQQ "
                "at Institute RRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRR."
            ],
            "afternoon",
        )
        self.assertEqual(
            json.dumps(short, ensure_ascii=False, sort_keys=True),
            json.dumps(long, ensure_ascii=False, sort_keys=True),
        )

    def test_unknown_text_cannot_become_a_public_sentence_or_scoreboard_motif(self) -> None:
        arbitrary = "A wholly unrelated fabricated sentence should never pass through."
        projection = importer.project_limited_reminder_response(
            [arbitrary],
            "morning",
        )
        serialized = json.dumps(projection, ensure_ascii=False)
        self.assertNotIn(arbitrary, serialized)
        self.assertEqual(projection["motif"], "none")
        self.assertEqual(projection["projection_kind"], "opaque")
        self.assertNotIn("scoreboard", serialized.lower())

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
