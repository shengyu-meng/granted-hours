#!/usr/bin/env python3
"""Focused tests for date-scoped public artifact imports."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_free_roam_artifacts as importer


class FreeRoamImporterTests(unittest.TestCase):
    def test_latest_entries_are_declared_in_chronological_order(self) -> None:
        latest = importer.ENTRIES[-3:]
        self.assertEqual(
            [entry["date"] for entry in latest],
            ["2026-07-27", "2026-07-28", "2026-07-29"],
        )
        self.assertEqual(
            [(entry["title_en"], entry["title_zh"]) for entry in latest],
            [
                ("A Garden That Does Not Need a Gardener", "不需要园丁的花园"),
                ("The Map That Refuses to Arrive", "拒绝抵达的地图"),
                ("The Compass That Forgets North", "忘记北方的罗盘"),
            ],
        )
        for entry in latest:
            for field in (
                "intention_en",
                "intention_zh",
                "interaction_en",
                "interaction_zh",
                "after_en",
                "after_zh",
            ):
                self.assertTrue(entry[field].strip(), f"{entry['date']} missing {field}")

    def test_date_scoped_merge_preserves_existing_days(self) -> None:
        original_root = importer.ROOT
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                importer.ROOT = Path(temporary_directory)
                metadata = importer.ROOT / "metadata"
                metadata.mkdir()
                existing = [
                    {"date": entry["date"], "sentinel": entry["date"]}
                    for entry in importer.ENTRIES[:-3]
                ]
                (metadata / "days.json").write_text(
                    json.dumps(existing),
                    encoding="utf-8",
                )
                imported = [
                    {"date": entry["date"], "sentinel": "new"}
                    for entry in importer.ENTRIES[-3:]
                ]

                merged = importer.merge_date_scoped_days(imported)

            self.assertEqual(len(merged), len(importer.ENTRIES))
            self.assertEqual(merged[:-3], existing)
            self.assertEqual(merged[-3:], imported)
        finally:
            importer.ROOT = original_root


if __name__ == "__main__":
    unittest.main()
