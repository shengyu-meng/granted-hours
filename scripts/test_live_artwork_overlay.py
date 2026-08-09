"""Regression tests for timetable → live artwork and live work-note overlays."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORTER_PATH = ROOT / "scripts" / "import_free_roam_artifacts.py"
MAIN_JS = ROOT / "src" / "timetable" / "main.js"
sys.path.insert(0, str(IMPORTER_PATH.parent))

spec = importlib.util.spec_from_file_location("free_roam_importer", IMPORTER_PATH)
assert spec and spec.loader
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


class TestTimetableLiveArtworkNavigation(unittest.TestCase):
    def test_all_autonomous_activation_paths_use_live_url(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        self.assertIn("autonomousLiveUrl(day, self)", source)
        self.assertIn("autonomousArtworkEmbedUrl(day, self, channel)", source)
        self.assertIn('url.searchParams.set("from", "timetable")', source)
        self.assertIn('url.searchParams.set("date", self.crystallization_date || day.date)', source)
        self.assertIn('url.searchParams.set("embed", "calendar")', source)
        self.assertIn('url.searchParams.set("gh_channel", channel)', source)
        self.assertIn("() => openArtworkDetail(day, event, button)", source)
        self.assertIn("() => openArtworkDetail(day, self, previewButton)", source)
        self.assertIn("() => openArtworkDetail(day, self, openButton)", source)
        self.assertNotIn("window.open(autonomousLiveUrl(", source)

    def test_live_url_keeps_timetable_provenance(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        self.assertIn('url.searchParams.set("from", "timetable")', source)
        self.assertIn('url.searchParams.set("date", self.crystallization_date || day.date)', source)


class TestLiveWorkNoteOverlay(unittest.TestCase):
    def test_rendered_snippet_contains_dynamic_bilingual_note(self) -> None:
        entry = importer.ENTRIES[-1]
        snippet = importer.render_live_text_fold_snippet(entry)
        self.assertNotIn("__GRANTED_HOURS_WORK_NOTE_JSON__", snippet)
        self.assertIn(entry["title_en"], snippet)
        self.assertIn(entry["title_zh"], snippet)
        self.assertIn("gh-work-note-overlay", snippet)
        self.assertIn("dataset.ghLiveBrief = 'bilingual'", snippet)
        self.assertIn("Brief / 作品简述", snippet)
        self.assertIn("How to interact / 操作说明", snippet)
        self.assertIn("aria-modal", snippet)
        self.assertIn("backdrop-filter: blur(28px)", snippet)
        self.assertIn("Close work note / 关闭作品说明", snippet)
        self.assertIn("View full archive record / 查看完整档案", snippet)
        self.assertIn("Touch keys / 触控按键", snippet)
        self.assertIn("dispatchArtworkKey('keydown', shortcut)", snippet)
        self.assertIn("dispatchArtworkKey('keyup', shortcut)", snippet)

    def test_all_live_pages_have_exactly_one_overlay_and_matching_payload(self) -> None:
        pages = sorted((ROOT / "docs" / "archive").glob("**/live/index.html"))
        self.assertEqual(len(pages), len(importer.ENTRIES))
        entries_by_date = {entry["date"]: entry for entry in importer.ENTRIES}
        for page in pages:
            date = page.parent.parent.name
            entry = entries_by_date[date]
            text = page.read_text(encoding="utf-8")
            with self.subTest(date=date):
                self.assertEqual(text.count('id="granted-hours-fold-style"'), 1)
                self.assertEqual(text.count('id="granted-hours-fold-script"'), 1)
                self.assertNotIn("__GRANTED_HOURS_WORK_NOTE_JSON__", text)
                self.assertIn("gh-work-note-trigger", text)
                self.assertIn("gh-work-note-overlay", text)
                self.assertIn("gh-work-note-close", text)
                self.assertIn("gh-live-brief", text)
                self.assertIn("dataset.ghBriefSection = kind", text)
                self.assertIn("Brief / 作品简述", text)
                self.assertIn("How to interact / 操作说明", text)
                self.assertIn("Bilingual artwork brief and instructions / 作品双语简述与操作说明", text)
                self.assertIn("aria-modal", text)
                match = re.search(r"const WORK_NOTE = (\{.*?\});\n", text)
                if match is None:
                    self.fail(f"{date} missing serialized WORK_NOTE payload")
                payload = json.loads(match.group(1))
                self.assertEqual(payload["date"], date)
                self.assertEqual(payload["title_en"], entry["title_en"])
                self.assertEqual(payload["title_zh"], entry["title_zh"])
                for key in (
                    "intention_en", "intention_zh",
                    "interaction_en", "interaction_zh",
                    "rationale_en", "rationale_zh",
                ):
                    self.assertTrue(payload[key].strip(), f"{date} missing {key}")
                self.assertEqual(
                    payload["touch_keys"],
                    importer.interaction_touch_keys(entry["interaction_en"]),
                )

    def test_overlay_is_closed_by_default_and_mobile_safe(self) -> None:
        snippet = importer.render_live_text_fold_snippet(importer.ENTRIES[-1])
        self.assertIn("overlay.hidden = true", snippet)
        self.assertIn("if (event.key === 'Escape')", snippet)
        self.assertIn("event.target === workNoteOverlay", snippet)
        self.assertIn("max-height: min(84dvh, 760px)", snippet)
        self.assertIn("env(safe-area-inset-bottom)", snippet)
        self.assertNotIn("setFolded", snippet)
        self.assertNotIn("gh-fold-toggle", snippet)
        self.assertIn("workNote.id = 'ghWorkNoteTrigger';", snippet)
        self.assertIn("function alignWorkNote()", snippet)
        self.assertIn("function findSoundControl()", snippet)
        self.assertIn("function findVisibleTextBlocks()", snippet)
        self.assertIn("function avoidOverlap(", snippet)
        self.assertIn("gh-work-note-trigger--busy", snippet)
        self.assertIn("const GH_WORK_NOTE_GAP = 10;", snippet)
        self.assertNotIn("IS_TIMETABLE_FULL_VIEW", snippet)
        self.assertIn("workNoteLastFocus.focus", snippet)

    def test_bilingual_live_brief_is_open_by_default_and_collapsible(self) -> None:
        snippet = importer.render_live_text_fold_snippet(importer.ENTRIES[-1])
        self.assertIn("const liveBrief = createLiveBrief();", snippet)
        self.assertIn("document.body.append(liveBrief, workNote, workNoteOverlay);", snippet)
        self.assertIn("toggle.setAttribute('aria-expanded', 'true');", snippet)
        self.assertIn("function toggleLiveBrief()", snippet)
        self.assertIn("function maskNativeBriefCollisions()", snippet)
        self.assertIn("function restoreNativeBriefCollisions()", snippet)
        self.assertIn('data-gh-brief-covered="true"', snippet)
        self.assertIn("scrollbar-color: rgba(242,195,107,.42) transparent", snippet)
        self.assertIn('body.gh-chamber-embed .gh-live-brief', snippet)

    def test_explicit_keyboard_shortcuts_have_touch_equivalents(self) -> None:
        first = importer.interaction_touch_keys(importer.ENTRIES[0]["interaction_en"])
        self.assertEqual(
            first,
            [
                {"label": "Space", "key": " ", "code": "Space"},
                {"label": "R", "key": "r", "code": "KeyR"},
                {"label": "S", "key": "s", "code": "KeyS"},
            ],
        )
        range_entry = next(entry for entry in importer.ENTRIES if entry["date"] == "2026-07-11")
        self.assertEqual(
            [key["label"] for key in importer.interaction_touch_keys(range_entry["interaction_en"])],
            ["1", "2", "3", "4", "Space", "R", "V", "M", "S"],
        )
        article_entry = next(entry for entry in importer.ENTRIES if entry["date"] == "2026-08-02")
        self.assertEqual(
            [key["label"] for key in importer.interaction_touch_keys(article_entry["interaction_en"])],
            ["R"],
        )

    def test_touch_controls_are_visible_in_calendar_embed_mode(self) -> None:
        snippet = importer.render_live_text_fold_snippet(importer.ENTRIES[0])
        self.assertIn("const embedTouchKeyDock = createTouchKeyDock();", snippet)
        self.assertIn("if (embedTouchKeyDock) document.body.append(embedTouchKeyDock);", snippet)
        self.assertIn("body.gh-chamber-embed .gh-touch-key-dock", snippet)
        self.assertIn("min-width: 44px", snippet)
        self.assertIn("min-height: 44px", snippet)
        self.assertIn("Touch keyboard shortcuts / 可触摸键盘快捷键", snippet)
        self.assertIn("target.dispatchEvent(event);", snippet)


if __name__ == "__main__":
    unittest.main()
