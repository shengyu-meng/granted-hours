#!/usr/bin/env python3
"""Static guards for equal month-row geometry and versioned default-on audio."""
from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TimetableMonthHeightAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.javascript = (ROOT / "src/timetable/main.js").read_text(encoding="utf-8")
        cls.styles = (ROOT / "src/timetable/styles.css").read_text(encoding="utf-8")

    def test_month_rows_use_one_viewport_height_per_week(self) -> None:
        self.assertIn('els.monthGrid.dataset.weekCount = String(cellCount / 7)', self.javascript)
        self.assertIn("--month-row-height:", self.styles)
        self.assertIn("grid-auto-rows: var(--month-row-height)", self.styles)
        self.assertNotIn("grid-auto-rows: minmax(92px, 1fr)", self.styles)
        self.assertNotIn("grid-auto-rows: minmax(55px, 1fr)", self.styles)

    def test_legacy_audio_preferences_migrate_once_to_default_on(self) -> None:
        self.assertIn('const AUDIO_DEFAULTS_VERSION = "2026-08-10-default-on-v2"', self.javascript)
        migration = re.search(
            r"function migrateDefaultAudioPreferences\(\) \{(?P<body>.*?)\n\}",
            self.javascript,
            re.DOTALL,
        )
        self.assertIsNotNone(migration)
        body = migration.group("body")
        self.assertIn('localStorage.setItem(BGM_STORAGE_KEY, "on")', body)
        self.assertIn('localStorage.setItem(PIANO_STORAGE_KEY, "on")', body)
        self.assertIn("AUDIO_DEFAULTS_STORAGE_KEY", body)
        self.assertLess(
            self.javascript.index("migrateDefaultAudioPreferences();"),
            self.javascript.index("setupCalendarBgm();"),
        )

    def test_enabled_sound_treatment_is_low_contrast(self) -> None:
        enabled = re.search(
            r'\.calendar-bgm-toggle\[aria-pressed="true"\],.*?\n\}',
            self.styles,
            re.DOTALL,
        )
        self.assertIsNotNone(enabled)
        rule = enabled.group(0)
        self.assertIn("var(--gold-trace) 8%", rule)
        self.assertNotIn("var(--gold-trace) 76%", rule)
        self.assertNotIn("var(--gold-pale) 80%", rule)
        self.assertNotIn("0 6px 16px", rule)


if __name__ == "__main__":
    unittest.main()
