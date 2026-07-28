#!/usr/bin/env python3
"""Deterministic public-safety tests for cron execution aggregation."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import import_timetable_pulses as importer


class TimetablePulseImporterTests(unittest.TestCase):
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

        self.assertEqual(snapshot["schema"], "granted-hours-timetable-pulses-v3")
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
