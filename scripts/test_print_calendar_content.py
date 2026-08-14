#!/usr/bin/env python3
"""Regression tests for the complete-copy and routine-fill print contract."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from build_print_desk_calendar import (  # noqa: E402
    apply_preset,
    artwork_copy_sections,
    choose_cards,
    load_timetable,
    routine_family_cards,
    source_day_projection,
)
from print_calendar_preset import load_preset  # noqa: E402


class CompletePrintContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _, cls.preset = load_preset(
            REPO,
            REPO / "config/print-desk-calendar-source-aligned-dark-landscape-v3.json",
        )
        apply_preset(cls.preset)
        raw_days = load_timetable(REPO / "src/timetable/timetable-data.js")["days"]
        cls.projected = source_day_projection(raw_days)

    def test_every_page_has_four_truthful_artwork_copy_sections(self) -> None:
        for page in self.projected:
            sections = artwork_copy_sections(page["autonomous_work"])
            self.assertEqual(len(sections), 4, page["date"])
            self.assertTrue(all(section[2] for section in sections), page["date"])

    def test_available_routine_families_fill_spare_card_slots(self) -> None:
        content = self.preset["content"]
        for page in self.projected:
            cards, _ = choose_cards(page)
            active_slots = min(
                len(page.get("task_residues", [])),
                content["max_collaboration_cards"],
            ) + min(
                sum(
                    item.get("category") == "daily_reminder"
                    for item in page.get("background_pulses", [])
                ),
                content["max_reminder_cards"],
            )
            expected = min(
                len(routine_family_cards(page)),
                content["max_routine_cards"],
                max(0, content["max_cards"] - active_slots),
            )
            actual = sum(card["kind"] == "routine" for card in cards)
            self.assertEqual(actual, expected, page["date"])

    def test_source_day_events_remain_with_source_day_artwork_pair(self) -> None:
        for page in self.projected:
            self.assertEqual(page["source_date"], page["date"])
            self.assertGreater(page["crystallization_date"], page["date"])
            self.assertTrue(
                all(
                    item.get("origin") not in {"self", "absence"}
                    for item in page["timeline_events"]
                ),
                page["date"],
            )


if __name__ == "__main__":
    unittest.main()
