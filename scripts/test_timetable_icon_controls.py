#!/usr/bin/env python3
"""Static generator-source checks for compact accessible header controls."""
from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TimetableIconControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (ROOT / "src/timetable/index.html").read_text(encoding="utf-8")
        cls.javascript = (ROOT / "src/timetable/main.js").read_text(encoding="utf-8")

    def test_theme_button_is_icon_only_and_imports_sun_moon_svg_icons(self) -> None:
        button = re.search(
            r'<button class="theme-toggle"[^>]*>(.*?)</button>',
            self.html,
            re.DOTALL,
        )
        self.assertIsNotNone(button)
        self.assertEqual(button.group(1).strip(), "")
        self.assertNotIn("Theme / 主题", self.html)
        self.assertIn('icons/moon.mjs', self.javascript)
        self.assertIn('icons/sun.mjs', self.javascript)
        self.assertIn('setAttribute("aria-label"', self.javascript)

    def test_bgm_button_is_icon_only_and_visible_status_copy_is_removed(self) -> None:
        button = re.search(
            r'<button\s+class="calendar-bgm-toggle".*?>(.*?)</button>',
            self.html,
            re.DOTALL,
        )
        self.assertIsNotNone(button)
        self.assertEqual(button.group(1).strip(), "")
        self.assertNotIn('class="calendar-bgm-status"', self.html)
        self.assertIn('icons/music.mjs', self.javascript)
        self.assertNotIn('icons/pause.mjs', self.javascript)
        self.assertNotIn("calendarBgmToggle.textContent", self.javascript)

    def test_assigned_timing_labels_follow_public_provenance(self) -> None:
        self.assertGreaterEqual(
            self.javascript.count("routineTimingLabel(task.time_provenance)"),
            3,
        )
        self.assertNotIn(
            '"timing: semantic estimate / 语义估算"',
            self.javascript,
        )


if __name__ == "__main__":
    unittest.main()
