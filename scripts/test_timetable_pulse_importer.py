#!/usr/bin/env python3
"""Deterministic public-safety tests for cron execution aggregation."""
from __future__ import annotations

import json
import tempfile
import unittest
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
            (output / "market-job" / "2026-07-01_09-00-00.md").write_text("private", encoding="utf-8")
            (output / "market-job_20260701_090001.txt").write_text("duplicate receipt", encoding="utf-8")
            (output / "brief-job" / "2026-07-01_08-30-00.md").write_text("private", encoding="utf-8")
            (output / "unknown-run").mkdir()
            (output / "unknown-run" / "2026-07-02_15-45-00.md").write_text("private", encoding="utf-8")

            snapshot = importer.build_snapshot(jobs_path, output, days_path)

        self.assertEqual(snapshot["schema"], "granted-hours-timetable-pulses-v1")
        self.assertEqual(snapshot["source_file_count"], 4)
        self.assertEqual(snapshot["deduplicated_run_count"], 3)
        self.assertEqual(
            snapshot["days"],
            [
                {
                    "date": "2026-07-01",
                    "pulses": [
                        {
                            "time": "08:30",
                            "time_bucket": "morning",
                            "category": "ai_daily_brief",
                            "count": 1,
                        },
                        {
                            "time": "09:00",
                            "time_bucket": "morning",
                            "category": "ah_market_scan",
                            "count": 1,
                        },
                    ],
                },
                {
                    "date": "2026-07-02",
                    "pulses": [
                        {
                            "time": "15:45",
                            "time_bucket": "afternoon",
                            "category": "background_routine",
                            "count": 1,
                        }
                    ],
                },
            ],
        )
        serialized = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        for forbidden in ("market-job", "brief-job", "scheduled-only", "unknown-run", "sentinel"):
            self.assertNotIn(forbidden, serialized)

    def test_absent_source_behavior_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            days_path = root / "days.json"
            days_path.write_text(json.dumps([{"date": "2026-07-01"}]), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "Cron jobs source does not exist"):
                importer.build_snapshot(root / "missing-jobs.json", root / "missing-output", days_path)


if __name__ == "__main__":
    unittest.main()
