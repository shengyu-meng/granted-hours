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
    def test_unknown_explicit_date_is_declared_from_sanitized_public_note(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "free-roam"
            source.mkdir()
            day = "2026-08-11"
            file_base = f"{day}-self-maintaining-margin"
            (source / f"{file_base}-note.md").write_text(
                """# Self-Maintaining Margin / 自维护的边

- **Free variable / 自由变量**: continuity / 连续性
- **Interaction claim / 交互主张**: a field can resume without possession / 场可以在不占有的情况下恢复
- **Intention / 发心**: 让作品在完成后安全地进入公开日历。
  *Let the work enter the public calendar safely after completion.*
- **Interaction / 交互**: 移动指针，让边缘缓慢打开。
  *Move the pointer and let the margin open slowly.*
- **Afterimage / 余像**: 自主不等于失去维护。
  *Autonomy does not require abandoning maintenance.*
- **Source Day / 源日**: 2026-08-10
- **Crystallization Day / 结晶日**: 2026-08-11
- **Granted duration / 授予时长**: 03:17–04:17 Asia/Shanghai
- **Experience duration / 体验时长**: open-ended / 开放
- **BGM**: original public-safe instrumental.
""",
                encoding="utf-8",
            )
            for suffix in (
                ".html",
                "-preview.png",
                "-preview.gif",
                "-visual-preview.gif",
                "-visual-preview.webp",
                "-bgm.mp3",
            ):
                (source / f"{file_base}{suffix}").write_bytes(b"fixture")

            entry = importer.discover_entry_from_note(source, day)

        self.assertEqual(entry["date"], day)
        self.assertEqual(entry["slug"], "self-maintaining-margin")
        self.assertEqual(entry["title_en"], "Self-Maintaining Margin")
        self.assertEqual(entry["title_zh"], "自维护的边")
        self.assertEqual(entry["seed"], 20260811)
        self.assertEqual(entry["interaction_en"], "Move the pointer and let the margin open slowly.")

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
        self.assertIn("Touch keys / 触控按键", refreshed)
        self.assertIn("const embedTouchKeyDock = createTouchKeyDock();", refreshed)
        self.assertIn("const MEDIA_VERSION = 2;", refreshed)
        self.assertIn("postMediaEvent('ready', 'ready')", refreshed)
        self.assertIn("retryEmbeddedMediaFromGesture", refreshed)
        self.assertIn("gh-media-unlock", refreshed)
        self.assertIn("window.addEventListener('load', syncEmbeddedMediaState", refreshed)
        self.assertIn("function touchKeyInstructionExcerpt(value)", refreshed)
        self.assertIn("gh-touch-key-dock-copy", refreshed)
        self.assertIn("dispatchArtworkKey('keydown', shortcut)", refreshed)
        self.assertIn("dispatchArtworkKey('keyup', shortcut)", refreshed)
        self.assertIn("function offsetNativeControlText()", refreshed)
        self.assertIn("function nativeControlOffsetTarget(", refreshed)
        self.assertIn('data-gh-control-offset="true"', refreshed)
        self.assertIn('data-gh-sound-geometry="compact"', refreshed)
        self.assertIn('"touch_keys":[', refreshed)
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
