#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import plan_daily_closure as planner


class DailyClosurePlanTests(unittest.TestCase):
    def test_artwork_first_and_current_day_events_wait(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            receipts = root / "receipts"
            receipts.mkdir()
            (receipts / "2026-08-10.json").write_text(
                json.dumps({"date": "2026-08-10", "assetsComplete": True}),
                encoding="utf-8",
            )
            days = root / "days.json"
            days.write_text(
                json.dumps({"days": [{"date": "2026-08-09"}]}),
                encoding="utf-8",
            )
            state = root / "state.json"
            state.write_text(
                json.dumps(
                    {
                        "backlog_dates": ["2026-08-10"],
                        "event_backlog_dates": ["2026-08-09", "2026-08-10"],
                    }
                ),
                encoding="utf-8",
            )

            plan = planner.build_plan(
                current_date="2026-08-10",
                receipts_path=receipts,
                state_path=state,
                days_path=days,
            )

        self.assertEqual(plan["artwork_dates"], ["2026-08-10"])
        self.assertEqual(plan["event_dates"], ["2026-08-09"])
        self.assertEqual(plan["waiting_event_dates"], ["2026-08-10"])
        self.assertFalse(plan["no_change"])

    def test_published_legacy_incomplete_receipts_are_not_reopened(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            receipts = root / "receipts"
            receipts.mkdir()
            (receipts / "2026-08-09.json").write_text(
                json.dumps({"date": "2026-08-09", "assetsComplete": False}),
                encoding="utf-8",
            )
            days = root / "days.json"
            days.write_text(
                json.dumps({"days": [{"date": "2026-08-09"}]}),
                encoding="utf-8",
            )
            state = root / "state.json"
            state.write_text("{}", encoding="utf-8")

            plan = planner.build_plan(
                current_date="2026-08-10",
                receipts_path=receipts,
                state_path=state,
                days_path=days,
            )

        self.assertEqual(plan["incomplete_receipt_dates"], [])
        self.assertTrue(plan["no_change"])


if __name__ == "__main__":
    unittest.main()
