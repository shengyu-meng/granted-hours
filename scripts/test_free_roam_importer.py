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
    def test_live_enhancement_adds_one_embed_aware_work_note_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            live_html = Path(temporary_directory) / "index.html"
            live_html.write_text(
                """<!doctype html>
<html>
<head>
  <style id="granted-hours-fold-style">stale style</style>
  <script id="granted-hours-fold-script">stale script</script>
</head>
<body><canvas></canvas><section class="panel"><h1>Artwork</h1><p>Statement</p></section></body>
</html>
""",
                encoding="utf-8",
            )

            entry = importer.ENTRIES[-1]
            importer.enhance_live_html(live_html, entry)
            importer.enhance_live_html(live_html, entry)
            refreshed = live_html.read_text(encoding="utf-8")

        self.assertEqual(refreshed.count('id="granted-hours-fold-style"'), 1)
        self.assertEqual(refreshed.count('id="granted-hours-fold-script"'), 1)
        self.assertEqual(refreshed.count("workNote.className = 'gh-work-note-trigger';"), 1)
        self.assertEqual(refreshed.count("archive.href = '../';"), 1)
        self.assertEqual(
            refreshed.count("workNote.textContent = 'Work note / 作品说明';"),
            1,
        )
        self.assertEqual(
            refreshed.count(
                "workNote.setAttribute('aria-label', "
                "'Open the artwork note over the interactive work / 在交互作品上方打开作品说明');"
            ),
            1,
        )
        self.assertIn("body.gh-chamber-embed .gh-work-note-trigger", refreshed)
        self.assertIn("const workNoteOverlay = createWorkNoteOverlay();", refreshed)
        self.assertIn("overlay.setAttribute('aria-modal', 'true');", refreshed)
        self.assertIn("overlay.hidden = true;", refreshed)
        self.assertIn("document.body.append(liveBrief, workNote, workNoteOverlay);", refreshed)
        self.assertIn("const liveBrief = createLiveBrief();", refreshed)
        self.assertIn("Brief / 作品简述", refreshed)
        self.assertIn("How to interact / 操作说明", refreshed)
        self.assertIn("workNote.id = 'ghWorkNoteTrigger';", refreshed)
        self.assertNotIn(".gh-fold-toggle", refreshed)
        self.assertIn("backdrop-filter: blur(28px)", refreshed)
        self.assertIn('"duration_minutes":60', refreshed)
        self.assertIn('"experience_duration_en":"Open-ended; visitor-controlled"', refreshed)
        self.assertIn("granted ${WORK_NOTE.duration_minutes} min", refreshed)
        self.assertIn("experience ${WORK_NOTE.experience_duration_en}", refreshed)
        self.assertIn(entry["title_en"], refreshed)
        self.assertIn(entry["title_zh"], refreshed)
        self.assertNotIn("workNote.href = '../';", refreshed)

    def test_latest_entries_are_declared_in_chronological_order(self) -> None:
        dates = [entry["date"] for entry in importer.ENTRIES]
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(len(dates), len(set(dates)))
        latest = importer.ENTRIES[-3:]
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

    def test_archive_dual_date_metadata_links_only_existing_public_source_days(self) -> None:
        config = json.loads(
            (Path(__file__).resolve().parents[1] / "metadata" / "timetable-calendar.json")
            .read_text(encoding="utf-8")
        )
        linked = importer.build_dual_date_metadata(
            "2026-07-29",
            {"2026-07-28", "2026-07-29"},
            config,
        )
        self.assertEqual(linked["source_date"], "2026-07-28")
        self.assertEqual(linked["crystallization_date"], "2026-07-29")
        self.assertEqual(
            (linked["start"], linked["end"]),
            ("03:17", "04:17"),
        )
        self.assertEqual(linked["duration_minutes"], 60)
        self.assertEqual(linked["experience_duration_en"], "Open-ended; visitor-controlled")
        self.assertRegex(
            linked["source_day_url"],
            r"/timetable/\?date=2026-07-28$",
        )
        html = importer.render_archive_dual_date_html(linked)
        markdown = importer.render_archive_dual_date_markdown(linked)
        for copy in (
            "Source Day / 来源日",
            "Crystallization Day / 结晶日",
            "2026-07-28",
            "2026-07-29",
            "03:17–04:17",
            "Granted-time duration / 授时时长",
            "60 min / 60 分钟",
            "Experience duration / 体验时长",
            "Open-ended; visitor-controlled / 开放式，由观众决定",
        ):
            self.assertIn(copy, html)
            self.assertIn(copy, markdown)

        first = importer.build_dual_date_metadata(
            "2026-05-07",
            {"2026-05-07"},
            config,
        )
        self.assertEqual(first["source_date"], "2026-05-06")
        self.assertIsNone(first["source_day_url"])
        first_html = importer.render_archive_dual_date_html(first)
        self.assertIn("2026-05-06", first_html)
        self.assertNotIn("?date=2026-05-06", first_html)

    def test_checked_in_archive_explanations_have_dual_date_copy(self) -> None:
        root = Path(__file__).resolve().parents[1]
        public_days = json.loads(
            (root / "metadata" / "days.json").read_text(encoding="utf-8")
        )
        for day in public_days:
            if day.get("type") == "calendar":
                continue
            with self.subTest(day=day["date"]):
                year, month, _ = day["date"].split("-")
                archive_page = (
                    root
                    / "docs"
                    / "archive"
                    / year
                    / month
                    / day["date"]
                    / "index.html"
                ).read_text(encoding="utf-8")
                self.assertIn("Source Day / 来源日", archive_page)
                self.assertIn(
                    "Crystallization Day / 结晶日",
                    archive_page,
                )


if __name__ == "__main__":
    unittest.main()
