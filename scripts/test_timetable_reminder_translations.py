#!/usr/bin/env python3
"""Completeness and safety tests for public reminder translations."""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

import import_timetable_pulses as importer


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "metadata" / "timetable-pulses.json"
CATALOG_PATH = ROOT / "metadata" / "timetable-reminder-translations.json"
CJK_RE = re.compile(
    r"[\u3040-\u30ff\u3100-\u312f\u31a0-\u31bf\u31f0-\u31ff"
    r"\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uf900-\ufaff]"
)


class TimetableReminderTranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        cls.catalog_source = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.catalog = importer.load_reminder_translations(CATALOG_PATH)
        cls.reminders = [
            (day["date"], pulse)
            for day in cls.snapshot["days"]
            for pulse in day["pulses"]
            if pulse.get("category") == "daily_reminder"
            and pulse.get("summary_provenance")
            == "semantic_public_projection"
        ]

    def test_catalog_and_sanitized_snapshot_have_bounded_unique_coverage(self) -> None:
        source_hashes = [
            hashlib.sha256(pulse["summary_original"].encode("utf-8")).hexdigest()
            for _day_date, pulse in self.reminders
        ]
        self.assertGreaterEqual(len(self.reminders), 100)
        self.assertGreaterEqual(
            len({date for date, _pulse in self.reminders}),
            45,
        )
        self.assertEqual(len(source_hashes), len(self.reminders))
        self.assertGreaterEqual(len(set(source_hashes)), 100)
        source_hash_set = set(source_hashes)
        self.assertTrue(source_hash_set.issubset(self.catalog))
        # Dormant records are intentional inputs for future date-scoped rebuilds;
        # keep the sidecar bounded without requiring it to mirror only the
        # currently merged snapshot.
        self.assertLessEqual(len(self.catalog), len(source_hash_set) + 64)
        matching_lookup_count = sum(
            source_sha256 in self.catalog for source_sha256 in source_hashes
        )
        self.assertEqual(matching_lookup_count, len(self.reminders))

    def test_catalog_records_are_hash_bound_mask_safe_english(self) -> None:
        for source_sha256, record in self.catalog.items():
            with self.subTest(record_index=len(source_sha256)):
                self.assertEqual(record["source_sha256"], source_sha256)
                self.assertEqual(
                    record["translation_provenance"],
                    importer.REMINDER_TRANSLATION_PROVENANCE,
                )
                self.assertTrue(record["summary_en"].strip())
                self.assertTrue(record["excerpt_en"].strip())
                self.assertRegex(record["summary_en"], r"[A-Za-z]")
                self.assertRegex(record["excerpt_en"], r"[A-Za-z]")
                self.assertIsNone(CJK_RE.search(record["summary_en"]))
                self.assertIsNone(CJK_RE.search(record["excerpt_en"]))
                importer.mask_token_count(record["summary_en"], "catalog summary")
                importer.mask_token_count(record["excerpt_en"], "catalog excerpt")
                self.assertLessEqual(len(record["excerpt_en"]), 260)
                if len(record["summary_en"]) <= 260:
                    self.assertEqual(record["excerpt_en"], record["summary_en"])
                else:
                    self.assertTrue(record["excerpt_en"].endswith("…"))
                    self.assertTrue(
                        record["summary_en"].startswith(
                            record["excerpt_en"][:-1]
                        )
                    )

    def test_snapshot_uses_parity_safe_extractive_translation(self) -> None:
        for _day_date, pulse in self.reminders:
            source_sha256 = hashlib.sha256(
                pulse["summary_original"].encode("utf-8")
            ).hexdigest()
            record = self.catalog.get(source_sha256)
            if record is not None:
                self.assertEqual(pulse["summary_en"], record["summary_en"])
            self.assertEqual(
                pulse["translation_provenance"],
                importer.REMINDER_TRANSLATION_PROVENANCE,
            )
            self.assertEqual(
                importer.mask_token_count(
                    pulse["summary_original"],
                    "snapshot original summary",
                ),
                importer.mask_token_count(
                    pulse["summary_en"],
                    "snapshot English summary",
                ),
            )
            self.assertEqual(
                importer.mask_token_count(
                    pulse["excerpt_original"],
                    "snapshot original excerpt",
                ),
                importer.mask_token_count(
                    pulse["excerpt_en"],
                    "snapshot English excerpt",
                ),
            )
            for summary, excerpt in (
                (pulse["summary_original"], pulse["excerpt_original"]),
                (pulse["summary_en"], pulse["excerpt_en"]),
            ):
                if len(summary) <= 260:
                    self.assertEqual(excerpt, summary)
                else:
                    self.assertTrue(excerpt.endswith("…"))
                    self.assertTrue(summary.startswith(excerpt[:-1]))

    def test_catalog_json_format_is_deterministic(self) -> None:
        self.assertEqual(
            list(self.catalog_source["translations"]),
            sorted(self.catalog_source["translations"]),
        )
        self.assertEqual(
            CATALOG_PATH.read_text(encoding="utf-8"),
            json.dumps(self.catalog_source, ensure_ascii=False, indent=2) + "\n",
        )


if __name__ == "__main__":
    unittest.main()
