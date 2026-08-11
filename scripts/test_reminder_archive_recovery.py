#!/usr/bin/env python3
from __future__ import annotations

import unittest

import restore_historical_reminders as recovery


def reminder(start: str, end: str, text_zh: str, text_en: str) -> dict:
    return {
        "start": start,
        "end": end,
        "duration_minutes": 2,
        "execution_minutes": 2,
        "time_bucket": "morning" if start < "12:00" else "evening",
        "category": "daily_reminder",
        "count": 1,
        "time_provenance": "observed_session_window",
        "summary_provenance": "source_wording_entity_masked",
        "owner_scope": "self",
        "ownership_provenance": "explicit_import_authorization",
        "public_label_zh": "晨间提醒",
        "public_label_en": "Morning reminder",
        "projection_kind": "verbatim",
        "redaction_policy": "targeted_entity_mask_v2",
        "redaction_count": 0,
        "summary_original": text_zh,
        "excerpt_original": text_zh,
        "original_language": "zh",
        "disclosure_policy": "authentic_entity_masked_reminder_v2",
        "disclosure_authorization": recovery.DISCLOSURE_AUTHORIZATION,
        "projection_provenance": "source_wording_entity_masked",
        "summary_en": text_en,
        "excerpt_en": text_en,
        "translation_provenance": recovery.REMINDER_TRANSLATION_PROVENANCE,
    }


class ReminderArchiveRecoveryTests(unittest.TestCase):
    def test_missing_public_reminder_is_restored_and_existing_one_wins(self) -> None:
        current = {
            "schema": recovery.PULSE_SNAPSHOT_SCHEMA,
            "timezone": "Asia/Shanghai",
            "days": [
                {
                    "date": "2026-07-01",
                    "pulses": [
                        recovery.migrate_reminder(
                            reminder("07:30", "07:32", "先做一件小事。", "Begin with one small thing."),
                            (),
                        )
                    ],
                }
            ],
        }
        historical = {
            "days": [
                {
                    "date": "2026-07-01",
                    "pulses": [
                        reminder("07:29", "07:31", "旧的同窗提醒。", "Older copy in the same window."),
                        reminder("23:30", "23:32", "今晚记得收束。", "Remember to close the day gently."),
                    ],
                }
            ]
        }
        restored, stats = recovery.restore_snapshot(current, historical, ())
        pulses = restored["days"][0]["pulses"]
        self.assertEqual(len(pulses), 2)
        self.assertEqual(stats["already_present"], 1)
        self.assertEqual(stats["restored"], 1)
        self.assertEqual(pulses[1]["disclosure_policy"], recovery.DISCLOSURE_POLICY)

    def test_semantic_risk_is_abstracted_in_both_languages(self) -> None:
        migrated = recovery.migrate_reminder(
            reminder(
                "07:30",
                "07:32",
                "今天复核持仓与交易账户。",
                "Review the portfolio holdings and trading account today.",
            ),
            (),
        )
        self.assertGreater(migrated["semantic_abstraction_count"], 0)
        self.assertNotIn("持仓", migrated["summary_original"])
        self.assertNotIn("trading account", migrated["summary_en"])

    def test_historical_public_copy_upgrades_a_withheld_footprint(self) -> None:
        current = {
            "schema": recovery.PULSE_SNAPSHOT_SCHEMA,
            "days": [
                {
                    "date": "2026-07-01",
                    "pulses": [
                        {
                            "category": "daily_reminder",
                            "start": "23:30",
                            "end": "23:32",
                            "time_bucket": "evening",
                            "count": 1,
                            "projection_kind": "withheld",
                        }
                    ],
                }
            ],
        }
        historical = {
            "days": [
                {
                    "date": "2026-07-01",
                    "pulses": [
                        reminder(
                            "23:30",
                            "23:32",
                            "今晚把一天轻轻收好。",
                            "Close the day gently tonight.",
                        )
                    ],
                }
            ]
        }
        restored, stats = recovery.restore_snapshot(current, historical, ())
        [pulse] = restored["days"][0]["pulses"]
        self.assertEqual(pulse["disclosure_policy"], recovery.DISCLOSURE_POLICY)
        self.assertEqual(stats["upgraded_withheld"], 1)

    def test_restoration_removes_the_matching_reduced_routine(self) -> None:
        current = {
            "schema": recovery.PULSE_SNAPSHOT_SCHEMA,
            "days": [
                {
                    "date": "2026-07-01",
                    "pulses": [
                        {
                            "category": "background_routine",
                            "start": "07:30",
                            "end": "07:32",
                            "time_bucket": "morning",
                            "count": 1,
                            "summary_zh": recovery.REDUCED_REMINDER_SUMMARY[0],
                            "summary_en": recovery.REDUCED_REMINDER_SUMMARY[1],
                        }
                    ],
                }
            ],
        }
        historical = {
            "days": [
                {
                    "date": "2026-07-01",
                    "pulses": [
                        reminder(
                            "07:30",
                            "07:32",
                            "今天先靠近真正重要的事。",
                            "Move closer to what matters today.",
                        )
                    ],
                }
            ]
        }
        restored, stats = recovery.restore_snapshot(current, historical, ())
        [pulse] = restored["days"][0]["pulses"]
        self.assertEqual(pulse["category"], "daily_reminder")
        self.assertEqual(stats["removed_reduced_routines"], 1)


if __name__ == "__main__":
    unittest.main()
