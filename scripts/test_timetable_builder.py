#!/usr/bin/env python3
"""Focused deterministic tests for historical timetable reconstruction."""
from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from collections import Counter
from pathlib import Path

import build_timetable_data as builder


class TimetableBuilderTests(unittest.TestCase):
    ARCHIVE_BASED_DATES = {
        "2026-05-23",
        "2026-05-24",
        "2026-05-30",
        "2026-05-31",
        "2026-06-13",
        "2026-06-14",
        "2026-06-27",
        "2026-07-05",
        "2026-07-11",
        "2026-07-19",
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.public_days = builder.read_json(builder.DEFAULT_PUBLIC_DAYS)
        cls.config = builder.read_json(builder.DEFAULT_CONFIG)
        cls.history = builder.load_history(builder.DEFAULT_HISTORY)
        cls.legacy = builder.load_legacy(builder.DEFAULT_LEGACY_OVERRIDES)

    def build(self, public_days=None):
        return builder.build_data(
            public_days or self.public_days,
            self.config,
            self.legacy,
            self.history,
        )

    def test_authored_history_covers_every_current_public_date(self) -> None:
        public_dates = {entry["date"] for entry in self.public_days}
        self.assertEqual(public_dates, set(self.history))
        self.assertEqual(len(public_dates), 74)

    def test_history_uses_explicit_public_safe_assigned_residues(self) -> None:
        provenance = Counter()
        for day_date, entry in self.history.items():
            provenance[entry["provenance"]] += 1
            self.assertEqual(
                set(entry),
                {"date", "provenance", "assigned_residues"},
                f"{day_date} must not retain focus/medium/workflow generation fields",
            )
            self.assertGreaterEqual(len(entry["assigned_residues"]), 5)
            self.assertLessEqual(len(entry["assigned_residues"]), 8)
            signatures = set()
            for residue in entry["assigned_residues"]:
                self.assertEqual(set(residue), {"category", "en", "zh"})
                self.assertIn(residue["category"], builder.REQUIRED_TAXONOMY)
                signature = (residue["category"], residue["en"], residue["zh"])
                self.assertNotIn(signature, signatures)
                signatures.add(signature)

        self.assertEqual(provenance, {"record_based": 64, "archive_based": 10})
        self.assertEqual(
            {day_date for day_date, entry in self.history.items() if entry["provenance"] == "archive_based"},
            self.ARCHIVE_BASED_DATES,
        )

    def test_historical_output_is_continuous_diverse_and_artwork_free(self) -> None:
        output = self.build()
        phrases = Counter()
        schedules = set()
        category_patterns = Counter()
        category_counts = Counter()
        for day in output["days"]:
            self.assertGreaterEqual(len(day["task_residues"]), 5)
            self.assertLessEqual(len(day["task_residues"]), 8)
            builder.validate_tasks(day["date"], day["task_residues"], self.config["autonomous_hour"])
            schedules.add(
                tuple(
                    (task["start"], task["end"], task["zh"], task["en"])
                    for task in day["task_residues"]
                )
            )
            category_patterns[tuple(task["category"] for task in day["task_residues"])] += 1
            for task in day["task_residues"]:
                phrases[(task["zh"], task["en"])] += 1
                category_counts[task["category"]] += 1
                self.assertNotIn(day["title_en"].lower(), task["en"].lower())
                self.assertNotIn(day["title_zh"], task["zh"])

        self.assertGreaterEqual(len(phrases), 100)
        self.assertGreaterEqual(len(schedules), 60)
        self.assertLessEqual(max(phrases.values()), 8)
        self.assertLessEqual(max(category_patterns.values()), 8)
        self.assertGreaterEqual(category_counts["social_media_organization"], 20)
        self.assertEqual(
            Counter(day["history_provenance"] for day in output["days"]),
            {"record_based": 64, "archive_based": 10},
        )

    def test_build_is_deterministic(self) -> None:
        first = json.dumps(self.build(), ensure_ascii=False, sort_keys=True)
        second = json.dumps(self.build(), ensure_ascii=False, sort_keys=True)
        self.assertEqual(first, second)

    def synthetic_public_days(self) -> list[dict]:
        synthetic_days = copy.deepcopy(self.public_days)
        synthetic = copy.deepcopy(synthetic_days[-1])
        synthetic.update(
            {
                "date": "2026-07-26",
                "title_en": "Synthetic Future Aperture",
                "title_zh": "合成未来孔径",
                "variable_en": "Aperture",
                "variable_zh": "孔径",
                "preview": "archive/2026/07/2026-07-26/assets/preview.png",
                "gif": "archive/2026/07/2026-07-26/assets/preview.gif",
                "archive_url": "archive/2026/07/2026-07-26/",
                "live_url": "archive/2026/07/2026-07-26/live/",
            }
        )
        synthetic_days.append(synthetic)
        return synthetic_days

    def test_synthetic_future_day_uses_assigned_work_inferred_fallback(self) -> None:
        synthetic_days = self.synthetic_public_days()
        output = self.build(synthetic_days)
        future = output["days"][-1]
        self.assertEqual(future["date"], "2026-07-26")
        self.assertEqual(future["history_provenance"], "inferred")
        self.assertGreaterEqual(len(future["task_residues"]), 5)
        self.assertLessEqual(len(future["task_residues"]), 8)
        builder.validate_tasks(future["date"], future["task_residues"], self.config["autonomous_hour"])
        self.assertNotIn("2026-07-26", self.history)
        for task in future["task_residues"]:
            self.assertNotIn(future["title_en"].lower(), task["en"].lower())
            self.assertNotIn(future["title_zh"], task["zh"])

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
            "future assigned work must not be templated from autonomous artwork metadata",
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

    def test_missing_current_history_cannot_silently_fall_back(self) -> None:
        incomplete_history = dict(self.history)
        incomplete_history.pop(self.public_days[0]["date"])
        with self.assertRaisesRegex(SystemExit, "missing authored history"):
            builder.build_data(
                self.public_days,
                self.config,
                self.legacy,
                incomplete_history,
            )


if __name__ == "__main__":
    unittest.main()
