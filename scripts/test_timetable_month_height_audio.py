#!/usr/bin/env python3
"""Static guards for month geometry and balanced, default-on calendar audio."""
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

    def test_month_rows_expand_until_three_items_are_fully_visible(self) -> None:
        self.assertIn("function scheduleMonthPreviewFloor()", self.javascript)
        self.assertIn("function applyMonthPreviewFloor()", self.javascript)
        self.assertIn('button.querySelectorAll(".cell-mark")', self.javascript)
        self.assertIn("if (!material || marks.length < 3) continue;", self.javascript)
        self.assertIn("thirdMark.bottom - buttonBox.top + paddingBottom + 1", self.javascript)
        self.assertIn('grid.dataset.previewItemFloor = "3"', self.javascript)
        self.assertIn("scheduleMonthPreviewFloor();", self.javascript)

    def test_sparse_month_previews_start_at_top_and_use_real_routine_fillers(self) -> None:
        self.assertIn("const MONTH_PREVIEW_ITEM_FLOOR = 3;", self.javascript)
        self.assertIn("function monthRoutinePreviewItems(day, limit)", self.javascript)
        self.assertIn('item.source === "pulses"', self.javascript)
        self.assertIn('item.classification === "climate_aggregate"', self.javascript)
        self.assertIn('button.dataset.routineFillerCount', self.javascript)
        self.assertIn('class="cell-mark routine-mark"', self.javascript)
        self.assertIn('class="cell-mark-detail"', self.javascript)
        fitted_rule = re.search(
            r"\.cell-material\.is-fitted\s*\{(?P<body>.*?)\n\}",
            self.styles,
            re.DOTALL,
        )
        self.assertIsNotNone(fitted_rule)
        self.assertIn("align-content: start", fitted_rule.group("body"))
        self.assertNotIn("align-content: end", fitted_rule.group("body"))

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

    def test_piano_and_bgm_share_the_calibrated_output_gain(self) -> None:
        self.assertIn("const CALENDAR_BGM_VOLUME = 0.34;", self.javascript)
        self.assertIn("const PIANO_VOLUME = CALENDAR_BGM_VOLUME;", self.javascript)
        self.assertIn(
            "els.calendarBgm.volume = CALENDAR_BGM_VOLUME;",
            self.javascript,
        )
        self.assertIn(
            "gain.gain.exponentialRampToValueAtTime(PIANO_VOLUME, startAt + 0.03);",
            self.javascript,
        )
        self.assertIn("limiter.threshold.value = -12;", self.javascript)
        self.assertIn("limiter.ratio.value = 8;", self.javascript)
        self.assertIn(
            "gain.connect(state.pianoMasterGain || context.destination);",
            self.javascript,
        )
        self.assertNotIn("const PIANO_VOLUME = 0.045;", self.javascript)

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
