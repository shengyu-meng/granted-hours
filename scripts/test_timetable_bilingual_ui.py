"""Regression checks for bilingual reminder rendering in the timetable UI."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PULSES = ROOT / "metadata" / "timetable-pulses.json"
MAIN_JS = ROOT / "src" / "timetable" / "main.js"
STYLES = ROOT / "src" / "timetable" / "styles.css"
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


class TestBilingualReminderData(unittest.TestCase):
    def test_every_authentic_reminder_has_real_english(self) -> None:
        snapshot = json.loads(PULSES.read_text(encoding="utf-8"))
        reminders = [
            pulse
            for day in snapshot["days"]
            for pulse in day["pulses"]
            if pulse.get("category") == "daily_reminder"
            and pulse.get("disclosure_policy")
        ]
        self.assertGreaterEqual(len(reminders), 90)
        for index, reminder in enumerate(reminders):
            with self.subTest(index=index):
                summary_en = reminder["summary_en"]
                excerpt_en = reminder["excerpt_en"]
                self.assertRegex(summary_en, r"[A-Za-z]")
                self.assertIsNone(CJK_RE.search(summary_en))
                self.assertTrue(excerpt_en.strip())
                self.assertLessEqual(len(excerpt_en), 260)
                self.assertEqual(
                    reminder["summary_original"].count("████"),
                    summary_en.count("████"),
                )


class TestBilingualReminderUiSource(unittest.TestCase):
    def test_selected_day_date_includes_bilingual_weekday(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        self.assertIn('["Monday", "星期一"]', source)
        self.assertIn("new Date(Date.UTC(year, month - 1, day)).getUTCDay()", source)
        self.assertIn("${value} · ${weekday[0]}", source)
        self.assertIn("${weekday[1]}", source)

    def test_reminder_projection_carries_english(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        self.assertIn("summary_en: primary.summary_en", source)
        self.assertIn("excerpt_en: primary.excerpt_en", source)
        self.assertIn("translation_provenance: primary.translation_provenance", source)

    def test_background_routine_rollup_copy_is_bilingual_and_readable(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        self.assertIn(
            'support_checks: ["后台例行运行", "Background routine activity"]',
            source,
        )
        self.assertIn("const alertWindowCount = sources.filter", source)
        self.assertIn("个窗口记录到通用状态变化", source)
        self.assertIn("window(s) recorded a general status change", source)
        self.assertIn("I completed ${runCount} background routine run(s) across", source)

    def test_card_and_inspection_show_english_and_original(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        self.assertIn('class="translated-reminder-copy" lang="en"', source)
        self.assertIn('class="original-reminder-copy" lang="zh"', source)
        self.assertIn("pulse.excerpt_en", source)
        self.assertIn("item.excerpt_en || item.summary_en", source)

    def test_detail_dialog_keeps_both_languages_visible(self) -> None:
        source = MAIN_JS.read_text(encoding="utf-8")
        self.assertIn("Reminder translation + original / 提醒译文与原文", source)
        self.assertIn("renderMarkdownInto(els.taskDetailEn, task.summary_en)", source)
        reminder_branch = source.split('task.classification === "readable_reminder"', 1)[1]
        reminder_branch = reminder_branch.split('task.classification === "promoted_routine_exception"', 1)[0]
        self.assertNotIn("els.taskDetailEn.hidden = true", reminder_branch)
        self.assertNotIn("els.taskDetailSummaryDivider.hidden = true", reminder_branch)

    def test_translated_copy_has_readable_visual_separation(self) -> None:
        styles = STYLES.read_text(encoding="utf-8")
        self.assertIn(".translated-reminder-copy.markdown-content--compact", styles)
        self.assertIn("border-bottom", styles)


if __name__ == "__main__":
    unittest.main()
