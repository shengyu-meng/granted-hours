#!/usr/bin/env python3
"""Regression tests for the printable Source Day projection."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from build_print_desk_calendar import load_timetable, source_day_projection  # noqa: E402


class SourceDayProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_days = load_timetable(REPO / "src/timetable/timetable-data.js")["days"]
        cls.projected = source_day_projection(cls.raw_days)

    def test_electronic_first_day_is_truthful_absence_with_forward_seed(self) -> None:
        first = self.raw_days[0]
        self.assertEqual(first["date"], "2026-05-06")
        self.assertEqual(first["type"], "calendar")
        self.assertEqual(first["autonomous_work"]["origin"], "absence")
        self.assertEqual(
            first["forward_artwork_seeds"][0]["crystallization_date"],
            "2026-05-07",
        )

    def test_first_print_pair_joins_first_signal_and_first_work(self) -> None:
        first = self.projected[0]
        self.assertEqual(first["date"], "2026-05-06")
        self.assertEqual(first["source_date"], "2026-05-06")
        self.assertEqual(first["crystallization_date"], "2026-05-07")
        self.assertEqual(first["title_zh"], "白夜罗盘")
        self.assertEqual(first["type"], "live")

    def test_source_events_and_forward_artwork_are_not_mixed(self) -> None:
        raw_by_date = {item["date"]: item for item in self.raw_days}
        for page in self.projected:
            source = raw_by_date[page["date"]]
            crystallization = raw_by_date[page["crystallization_date"]]
            self.assertEqual(page["task_residues"], source["task_residues"])
            self.assertEqual(page["background_pulses"], source["background_pulses"])
            self.assertEqual(page["autonomous_work"], crystallization["autonomous_work"])
            self.assertTrue(
                all(
                    event.get("origin") not in {"self", "absence"}
                    for event in page["timeline_events"]
                )
            )

    def test_unpaired_latest_public_day_is_omitted(self) -> None:
        self.assertEqual(len(self.projected), 99)
        self.assertEqual(self.projected[-1]["date"], "2026-08-12")
        self.assertEqual(self.projected[-1]["crystallization_date"], "2026-08-13")
        self.assertEqual(self.raw_days[-1]["date"], "2026-08-13")


if __name__ == "__main__":
    unittest.main()
