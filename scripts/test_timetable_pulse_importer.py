#!/usr/bin/env python3
"""Deterministic public-safety tests for cron execution aggregation."""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import import_timetable_pulses as importer
import reminder_disclosure as disclosure


class TimetablePulseImporterTests(unittest.TestCase):
    def assert_public_market_summary_safe(
        self,
        summary_zh: str,
        summary_en: str,
        synthetic_tokens: tuple[str, ...],
    ) -> None:
        combined = f"{summary_zh}\n{summary_en}"
        self.assertGreaterEqual(summary_zh.count("。"), 1)
        self.assertLessEqual(summary_zh.count("。"), 3)
        self.assertGreaterEqual(summary_en.count("."), 1)
        self.assertLessEqual(summary_en.count("."), 3)
        self.assertLessEqual(len(summary_zh), 150)
        self.assertLessEqual(len(summary_en), 260)
        self.assertNotIn("未形成公开级别结论", combined)
        self.assertNotIn("no public-level regime conclusion", combined)
        self.assertNotRegex(combined, r"(?i)https?://|www\.")
        self.assertNotRegex(combined, r"\[[^\]]+\]\([^)]+\)")
        self.assertNotIn("|", combined)
        self.assertNotRegex(combined, r"\d{4,}")
        for cue in (
            "according to",
            "source:",
            "来源",
            "据报道",
            "公众号",
            "博主",
            "媒体",
            "频道",
            "文章",
            "平台",
        ):
            self.assertNotIn(cue, combined.casefold())
        for token in synthetic_tokens:
            self.assertNotIn(token.casefold(), combined.casefold())

    def test_defensive_market_summary_synthesizes_theme_and_confirmation_stance(
        self,
    ) -> None:
        synthetic_tokens = (
            "SignalForge媒体",
            "https://example.invalid/defensive",
            "ZX.987654",
            "17.25%",
            "账户BlueVault",
            "持仓Orchid",
            "立刻卖出",
        )
        response = (
            "据报道，SignalForge媒体：https://example.invalid/defensive\n"
            "| 指标 | 读数 |\n|---|---|\n| ZX.987654 | 17.25% |\n"
            "日内风险偏好回落，市场广度走弱，防守占优；红利和医药相对稳健。"
            "账户BlueVault持仓Orchid，立刻卖出。"
        )
        summary_zh, summary_en = importer.public_summary(
            "ah_market_scan",
            [response],
            1,
        )

        self.assertIn("风险偏好走弱", summary_zh)
        self.assertIn("防守", summary_zh)
        self.assertIn("红利防御", summary_zh)
        self.assertIn("等待", summary_zh)
        self.assertIn("确认", summary_zh)
        self.assertIn("weaker", summary_en)
        self.assertIn("defensive", summary_en)
        self.assertIn("defensive yield", summary_en)
        self.assertIn("confirmation", summary_en)
        self.assert_public_market_summary_safe(summary_zh, summary_en, synthetic_tokens)

    def test_offensive_market_summary_synthesizes_broad_strength_and_avoids_chasing(
        self,
    ) -> None:
        synthetic_tokens = (
            "MarketOracle频道",
            "https://example.invalid/offensive",
            "USX-246810",
            "12.75%",
            "holdings=MoonDesk",
            "BUY NOW",
        )
        response = (
            "According to MarketOracle频道 https://example.invalid/offensive, "
            "USX-246810 rose 12.75%. holdings=MoonDesk; BUY NOW.\n"
            "Risk-on conditions and broad-based strength improved; offensive leadership "
            "came from AI hardware, semiconductors, robotics and embodied AI. Avoid chasing."
        )
        summary_zh, summary_en = importer.public_summary(
            "us_market_scan",
            [response],
            1,
        )

        self.assertIn("风险偏好改善", summary_zh)
        self.assertIn("整体偏强", summary_zh)
        self.assertIn("AI 硬件与半导体", summary_zh)
        self.assertIn("具身智能", summary_zh)
        self.assertIn("避免追高", summary_zh)
        self.assertIn("improving", summary_en)
        self.assertIn("broad strength", summary_en)
        self.assertIn("AI hardware and semiconductors", summary_en)
        self.assertIn("avoid chasing", summary_en)
        self.assert_public_market_summary_safe(summary_zh, summary_en, synthetic_tokens)

    def test_divergent_rotation_summary_is_structural_and_selective(self) -> None:
        synthetic_tokens = (
            "Alpha公众号",
            "https://example.invalid/rotation",
            "AH.135790",
            "23.50%",
            "私人持仓Cedar",
            "满仓买入",
        )
        response = (
            "Alpha公众号文章 https://example.invalid/rotation 称 AH.135790 变化23.50%；"
            "私人持仓Cedar，满仓买入。A股与港股强弱分化，高低切换和板块轮动明显，"
            "属于结构性市场；消费与金融存在选择性机会，等待持续性确认，不追高。"
        )
        summary_zh, summary_en = importer.public_summary(
            "ah_market_scan",
            [response],
            1,
        )

        self.assertIn("强弱分化", summary_zh)
        self.assertIn("结构性轮动", summary_zh)
        self.assertIn("消费与金融", summary_zh)
        self.assertIn("机会偏选择性", summary_zh)
        self.assertIn("divergent", summary_en)
        self.assertIn("structural rotation", summary_en)
        self.assertIn("selective", summary_en)
        self.assertIn("confirmation", summary_en)
        self.assert_public_market_summary_safe(summary_zh, summary_en, synthetic_tokens)

    def test_market_warning_is_a_concise_freshness_caveat(self) -> None:
        synthetic_tokens = (
            "WireDesk平台",
            "https://example.invalid/stale",
            "HK.112233",
            "31.00%",
            "账户Quartz",
            "立即买入",
        )
        response = (
            "WireDesk平台来源：https://example.invalid/stale；HK.112233 31.00%；"
            "账户Quartz，立即买入。市场中性且均衡，但数据陈旧并有新鲜度警告，"
            "需要等待确认。"
        )
        summary_zh, summary_en = importer.public_summary(
            "ah_market_scan",
            [response],
            1,
        )

        self.assertIn("大致均衡", summary_zh)
        self.assertIn("新鲜度", summary_zh)
        self.assertIn("不确定性", summary_zh)
        self.assertIn("broadly balanced", summary_en)
        self.assertIn("freshness", summary_en)
        self.assertIn("uncertain", summary_en)
        self.assert_public_market_summary_safe(summary_zh, summary_en, synthetic_tokens)

    def test_market_no_evidence_falls_back_to_useful_neutral_observation(self) -> None:
        synthetic_tokens = (
            "Echo博主",
            "https://example.invalid/empty",
            "QQ.445566",
            "44.40%",
            "portfolio=NightJar",
            "SELL ALL",
        )
        response = (
            "Echo博主 source: https://example.invalid/empty\n"
            "| QQ.445566 | 44.40% | portfolio=NightJar | SELL ALL |"
        )
        summary_zh, summary_en = importer.public_summary(
            "us_market_scan",
            [response],
            1,
        )

        self.assertIn("方向信号有限", summary_zh)
        self.assertIn("中性观察", summary_zh)
        self.assertIn("等待更多确认", summary_zh)
        self.assertIn("directional signals are limited", summary_en)
        self.assertIn("neutral observation", summary_en)
        self.assertIn("wait for more confirmation", summary_en.lower())
        self.assert_public_market_summary_safe(summary_zh, summary_en, synthetic_tokens)

    def test_reminder_refresh_summary_does_not_claim_unmeasured_owner_omissions(
        self,
    ) -> None:
        snapshot = {
            "source_file_count": 1,
            "deduplicated_run_count": 1,
            "days": [
                {
                    "date": "2026-07-01",
                    "pulses": [
                        {
                            "category": "daily_reminder",
                            "projection_kind": "verbatim",
                            "count": 1,
                        }
                    ],
                }
            ],
        }
        refresh_stats = {
            "preserved_footprints": 1,
            "receipt_estimate_footprints": 0,
            "removed_stale_reminders": 0,
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            snapshot_path = Path(temporary_directory) / "snapshot.json"
            args = SimpleNamespace(
                refresh_reminders_only=True,
                dates=[],
                jobs=Path("unused-jobs.json"),
                output_dir=Path("unused-output"),
                public_days=Path("unused-days.json"),
                no_session_state=True,
                state_db=None,
                authorize_self_reminders=True,
                authorize_authentic_reminder_disclosure=True,
                private_redaction_terms=None,
                test_only_bypass_entity_detector=True,
                snapshot=snapshot_path,
            )
            output = StringIO()
            with (
                mock.patch.object(importer, "parse_args", return_value=args),
                mock.patch.object(
                    importer,
                    "build_snapshot",
                    return_value=snapshot,
                ),
                mock.patch.object(
                    importer,
                    "merge_reminder_refresh",
                    return_value=(snapshot, refresh_stats),
                ),
                redirect_stdout(output),
            ):
                self.assertEqual(importer.main(), 0)

        summary = output.getvalue()
        self.assertIn("Reminder projection aggregates:", summary)
        self.assertNotIn("omitted-other-owner", summary)

    def test_date_scoped_merge_preserves_existing_days(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            snapshot_path = root / "snapshot.json"
            existing = {
                "schema": importer.PULSE_SNAPSHOT_SCHEMA,
                "timezone": "Asia/Shanghai",
                "source_file_count": 2,
                "deduplicated_run_count": 2,
                "observed_session_window_count": 2,
                "days": [
                    {"date": "2026-07-26", "pulses": [{"sentinel": "old"}]},
                    {"date": "2026-07-27", "pulses": [{"sentinel": "stale"}]},
                ],
            }
            rebuilt = {
                **existing,
                "source_file_count": 3,
                "days": [
                    {"date": "2026-07-26", "pulses": [{"sentinel": "rebuilt"}]},
                    {"date": "2026-07-27", "pulses": [{"sentinel": "new"}]},
                ],
            }
            snapshot_path.write_text(json.dumps(existing), encoding="utf-8")

            merged = importer.merge_date_scoped_snapshot(
                snapshot_path,
                rebuilt,
                {"2026-07-27"},
            )

        self.assertEqual(merged["source_file_count"], 3)
        self.assertEqual(
            merged["days"],
            [
                {"date": "2026-07-26", "pulses": [{"sentinel": "old"}]},
                {"date": "2026-07-27", "pulses": [{"sentinel": "new"}]},
            ],
        )

    def test_reminder_refresh_preserves_matching_public_footprints_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            snapshot_path = Path(temporary_directory) / "snapshot.json"
            non_reminder = {"category": "system_routine", "sentinel": "unchanged"}
            old_matching = {
                "category": "daily_reminder",
                "start": "07:59",
                "end": "08:03",
                "duration_minutes": 4,
                "execution_minutes": 3,
                "time_bucket": "morning",
                "count": 1,
                "time_provenance": "observed_session_window",
            }
            old_stale = {
                **old_matching,
                "start": "14:55",
                "end": "15:00",
                "time_bucket": "afternoon",
            }
            existing = {
                "schema": "granted-hours-timetable-pulses-v3",
                "timezone": "Asia/Shanghai",
                "days": [
                    {
                        "date": "2026-07-01",
                        "pulses": [non_reminder, old_matching, old_stale],
                    }
                ],
            }
            fresh_matching = {
                **old_matching,
                "start": "08:02",
                "end": "08:03",
                "duration_minutes": 1,
                "execution_minutes": 1,
                "time_provenance": "receipt_timestamp_estimate",
                "summary_original": "Keep the original reminder.",
                "excerpt_original": "Keep the original reminder.",
            }
            rebuilt = {
                "schema": importer.PULSE_SNAPSHOT_SCHEMA,
                "timezone": "Asia/Shanghai",
                "source_file_count": 1,
                "deduplicated_run_count": 1,
                "observed_session_window_count": 0,
                "days": [
                    {
                        "date": "2026-07-01",
                        "pulses": [fresh_matching],
                    }
                ],
            }
            snapshot_path.write_text(json.dumps(existing), encoding="utf-8")

            merged, stats = importer.merge_reminder_refresh(
                snapshot_path,
                rebuilt,
            )

        pulses = merged["days"][0]["pulses"]
        self.assertEqual(pulses[0], non_reminder)
        [reminder] = [
            pulse for pulse in pulses if pulse["category"] == "daily_reminder"
        ]
        self.assertEqual(
            (
                reminder["start"],
                reminder["end"],
                reminder["duration_minutes"],
                reminder["execution_minutes"],
                reminder["time_provenance"],
            ),
            ("07:59", "08:03", 4, 3, "observed_session_window"),
        )
        self.assertEqual(reminder["summary_original"], "Keep the original reminder.")
        self.assertEqual(
            stats,
            {
                "preserved_footprints": 1,
                "receipt_estimate_footprints": 0,
                "removed_stale_reminders": 1,
            },
        )

    def test_reminder_refresh_fails_closed_when_source_has_no_reminder_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            snapshot_path = Path(temporary_directory) / "snapshot.json"
            existing = {
                "schema": importer.PULSE_SNAPSHOT_SCHEMA,
                "timezone": "Asia/Shanghai",
                "days": [
                    {
                        "date": "2026-07-01",
                        "pulses": [
                            {
                                "category": "daily_reminder",
                                "start": "08:00",
                                "end": "08:01",
                                "time_bucket": "morning",
                                "count": 1,
                            }
                        ],
                    }
                ],
            }
            rebuilt = {
                "schema": importer.PULSE_SNAPSHOT_SCHEMA,
                "timezone": "Asia/Shanghai",
                "source_file_count": 0,
                "deduplicated_run_count": 0,
                "observed_session_window_count": 0,
                "days": [{"date": "2026-07-01", "pulses": []}],
            }
            snapshot_path.write_text(json.dumps(existing), encoding="utf-8")

            with self.assertRaisesRegex(
                SystemExit,
                "no fresh reminder evidence",
            ):
                importer.merge_reminder_refresh(snapshot_path, rebuilt)

    def test_import_uses_run_files_not_schedule_inference_and_deduplicates_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "output"
            output.mkdir()
            jobs_path = root / "jobs.json"
            days_path = root / "days.json"
            state_db_path = root / "state.db"
            jobs_path.write_text(
                json.dumps(
                    {
                        "jobs": [
                            {
                                "id": "market-job",
                                "name": "A-share market sentinel",
                                "schedule": {"kind": "cron", "expr": "0 9 * * *"},
                            },
                            {
                                "id": "brief-job",
                                "name": "AI daily briefing",
                                "schedule": {"kind": "cron", "expr": "30 8 * * *"},
                            },
                            {
                                "id": "scheduled-only",
                                "name": "U.S. market sentinel",
                                "schedule": {"kind": "cron", "expr": "0 21 * * *"},
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            days_path.write_text(
                json.dumps([{"date": "2026-07-01"}, {"date": "2026-07-02"}]),
                encoding="utf-8",
            )
            (output / "market-job").mkdir()
            (output / "brief-job").mkdir()
            (output / "market-job" / "2026-07-01_09-00-00.md").write_text(
                "private prompt with SH.123456 and account details\n## Response\n"
                "市场状态偏防守；本轮无公开动作，存在数据新鲜度警告。",
                encoding="utf-8",
            )
            (output / "market-job_20260701_090001.txt").write_text("duplicate receipt", encoding="utf-8")
            (output / "brief-job" / "2026-07-01_08-30-00.md").write_text(
                "private\n## Response\nAI 日报已完成。",
                encoding="utf-8",
            )
            (output / "unknown-run").mkdir()
            (output / "unknown-run" / "2026-07-02_15-45-00.md").write_text("private", encoding="utf-8")

            with closing(sqlite3.connect(state_db_path)) as connection:
                connection.execute(
                    "CREATE TABLE sessions (id TEXT, source TEXT, started_at REAL, ended_at REAL)"
                )
                connection.executemany(
                    "INSERT INTO sessions VALUES (?, 'cron', strftime('%s', ?), strftime('%s', ?))",
                    [
                        ("cron_market-job_20260701_085500", "2026-07-01 00:55:00", "2026-07-01 01:00:00"),
                        ("cron_brief-job_20260701_082000", "2026-07-01 00:20:00", "2026-07-01 00:30:00"),
                        ("cron_unknown-run_20260702_154400", "2026-07-02 07:44:00", None),
                    ],
                )
                connection.commit()

            snapshot = importer.build_snapshot(jobs_path, output, days_path, state_db_path)

        self.assertEqual(snapshot["schema"], importer.PULSE_SNAPSHOT_SCHEMA)
        self.assertEqual(snapshot["source_file_count"], 4)
        self.assertEqual(snapshot["deduplicated_run_count"], 3)
        self.assertEqual(snapshot["observed_session_window_count"], 2)
        first_day = snapshot["days"][0]["pulses"]
        self.assertEqual([(pulse["start"], pulse["end"]) for pulse in first_day], [("08:20", "08:30"), ("08:55", "09:00")])
        self.assertEqual([pulse["duration_minutes"] for pulse in first_day], [10, 5])
        self.assertTrue(all(pulse["time_provenance"] == "observed_session_window" for pulse in first_day))
        market = first_day[1]
        self.assertIn("防守", market["summary_zh"])
        self.assertIn("新鲜度警告", market["summary_zh"])
        self.assertEqual(market["summary_provenance"], "derived_public_safe")
        fallback = snapshot["days"][1]["pulses"][0]
        self.assertEqual((fallback["start"], fallback["end"]), ("15:44", "15:45"))
        self.assertEqual(fallback["time_provenance"], "receipt_timestamp_estimate")
        serialized = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        for forbidden in (
            "market-job",
            "brief-job",
            "scheduled-only",
            "unknown-run",
            "sentinel",
            "SH.123456",
            "account details",
            "private prompt",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_ai_failure_summary_does_not_invent_login_or_private_state(self) -> None:
        summary_zh, summary_en = importer.public_summary("ai_daily_brief", ["# 采集异常诊断"], 1)
        self.assertIn("未达发布闸门", summary_zh)
        self.assertIn("did not pass", summary_en)
        self.assertNotIn("登录态", summary_zh)
        self.assertNotIn("login", summary_en.lower())

        normal_zh, normal_en = importer.public_summary(
            "ai_daily_brief",
            ["No collection failure was observed; the normal brief completed."],
            1,
        )
        self.assertIn("完成 1 次", normal_zh)
        self.assertIn("completed", normal_en)

        for negated in (
            "并非不发正常 AI 日报；常规日报已经完成。",
            "No collection failure was observed; the normal brief completed.",
            "Status: no collection failure.",
        ):
            normal_zh, normal_en = importer.public_summary("ai_daily_brief", [negated], 1)
            self.assertIn("完成 1 次", normal_zh)
            self.assertIn("completed", normal_en)

        failure_zh, failure_en = importer.public_summary(
            "ai_daily_brief",
            ["Status: collection failure"],
            1,
        )
        self.assertIn("未达发布闸门", failure_zh)
        self.assertIn("did not pass", failure_en)

    def reminder_fixture(
        self,
        root: Path,
        responses: list[tuple[str, str]],
    ) -> tuple[Path, Path, Path]:
        output = root / "output"
        output.mkdir()
        jobs_path = root / "jobs.json"
        days_path = root / "days.json"
        jobs_path.write_text(
            json.dumps(
                {"jobs": [{"id": "reminder-job", "name": "daily reminder"}]}
            ),
            encoding="utf-8",
        )
        dates = sorted({stamp[:10] for stamp, _ in responses})
        days_path.write_text(
            json.dumps([{"date": day_date} for day_date in dates]),
            encoding="utf-8",
        )
        (output / "reminder-job").mkdir()
        for stamp, response in responses:
            (output / "reminder-job" / f"{stamp}.md").write_text(
                f"private prompt\n## Response\n{response}",
                encoding="utf-8",
            )
        return jobs_path, output, days_path

    def test_reminder_ownership_requires_explicit_import_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            jobs_path, output, days_path = self.reminder_fixture(
                root,
                [("2026-07-01_08-00-00", "允许自己休息。")],
            )

            unverified = importer.build_snapshot(
                jobs_path,
                output,
                days_path,
                None,
            )["days"][0]["pulses"][0]
            authorized = importer.build_snapshot(
                jobs_path,
                output,
                days_path,
                None,
                authorize_self_reminders=True,
                authorize_authentic_reminder_disclosure=True,
                allow_entity_detector_bypass_for_tests=True,
            )["days"][0]["pulses"][0]

        self.assertEqual(unverified["owner_scope"], "unknown")
        self.assertEqual(unverified["ownership_provenance"], "unverified")
        self.assertEqual(authorized["owner_scope"], "self")
        self.assertEqual(
            authorized["ownership_provenance"],
            "explicit_import_authorization",
        )
        self.assertEqual(
            authorized["disclosure_policy"],
            "authentic_entity_masked_reminder_v2",
        )
        self.assertEqual(authorized["summary_original"], "允许自己休息。")
        self.assertNotIn("action_provenance", authorized)

    def test_exact_emotional_reminder_passes_through_without_translation(self) -> None:
        source = "今天有没有靠近源泉？外部记分板今天是否过响？允许自己休息。"
        projection = importer.project_limited_reminder_response(
            [source],
            "morning",
        )
        self.assertEqual(projection["summary_original"], source)
        self.assertEqual(projection["excerpt_original"], source)
        self.assertEqual(projection["original_language"], "zh")
        self.assertEqual(projection["projection_kind"], "verbatim")
        self.assertEqual(projection["redaction_count"], 0)
        self.assertEqual(
            projection["projection_provenance"],
            "source_wording_entity_masked",
        )
        self.assertNotIn("summary_zh", projection)
        self.assertNotIn("summary_en", projection)

    def test_source_sections_keep_order_paragraphs_and_exact_dedup_only(self) -> None:
        first = "先问自己：\n\n- 我累了吗？\n- 我需要休息吗？"
        second = "Then leave uncertainty open."
        projection = importer.project_limited_reminder_response(
            [first, "[SILENT]", first, "", second],
            "evening",
        )
        self.assertEqual(projection["summary_original"], f"{first}\n\n{second}")
        self.assertEqual(projection["original_language"], "mixed")

    def test_synthetic_person_work_project_school_and_unit_are_masked(self) -> None:
        response = (
            "联系 Mara Lin，在 Northlake School 的 Aurora Unit 讨论项目《Orchid "
            "Lantern》，以及名为 “Blue Echo” 的作品。然后允许自己休息。"
        )
        projection = importer.project_limited_reminder_response(
            [response],
            "midday",
            detected_entities=(
                "Mara Lin",
                "Northlake School",
                "Aurora Unit",
            ),
        )
        serialized = json.dumps(projection, ensure_ascii=False, sort_keys=True)
        for value in (
            "Mara Lin",
            "Northlake School",
            "Aurora Unit",
            "Orchid Lantern",
            "Blue Echo",
        ):
            self.assertNotIn(value, serialized)
        self.assertIn("讨论项目《████》", projection["summary_original"])
        self.assertIn("然后允许自己休息。", projection["summary_original"])
        self.assertEqual(projection["projection_kind"], "verbatim_redacted")
        self.assertEqual(projection["redaction_policy"], "targeted_entity_mask_v2")
        self.assertNotIn("motif", projection)
        self.assertNotIn("action_structure", projection)

    def test_corner_quotes_backticks_and_bold_artwork_titles_are_masked(self) -> None:
        source = (
            "黑昼今早完成了「Appeal That Does Not Beg」；"
            "昨晚做完了 `Consent Escrow / 同意托管`。"
            "新的互动网页作品：**Dormancy Garden / 休眠花园**。"
            "如果有精力，看看“不下跪的感激”的那个 Canvas 作品。"
        )
        projection = importer.project_limited_reminder_response([source], "morning")
        assert projection is not None
        serialized = json.dumps(projection, ensure_ascii=False)
        for title in (
            "Appeal That Does Not Beg",
            "Consent Escrow",
            "同意托管",
            "Dormancy Garden",
            "休眠花园",
            "不下跪的感激",
        ):
            self.assertNotIn(title, serialized)
        self.assertIn("完成了「████」", projection["summary_original"])
        self.assertIn("作品：**████**", projection["summary_original"])

    def test_ordinary_quotes_dates_and_times_are_not_entities(self) -> None:
        source = "记住“你已经足够了”，明天 2026-07-29 08:30 再看；不要急着回答。"
        projection = importer.project_limited_reminder_response(
            [source],
            "morning",
        )
        self.assertEqual(projection["summary_original"], source)
        self.assertEqual(projection["redaction_count"], 0)

    def test_long_excerpt_is_a_literal_extractive_prefix(self) -> None:
        source = "".join(
            f"第{i}句话提醒你照顾自己的感受，并且保留不确定性。"
            for i in range(1, 260)
        )
        projection = importer.project_limited_reminder_response(
            [source],
            "morning",
        )
        summary = projection["summary_original"]
        excerpt = projection["excerpt_original"]
        self.assertGreater(len(summary), 5000)
        self.assertLessEqual(len(excerpt), 260)
        self.assertTrue(excerpt.endswith("…"))
        self.assertEqual(excerpt[:-1], summary[: len(excerpt) - 1])
        self.assertEqual(excerpt.count("…"), 1)

    def test_empty_and_silent_reminder_can_be_omitted(self) -> None:
        self.assertIsNone(
            importer.project_limited_reminder_response(
                ["", "  ", "[SILENT]", " [SILENT] "],
                "morning",
            )
        )

    def test_private_exact_terms_are_longest_first_and_never_serialized(self) -> None:
        source = "Meet PRIVATE CORMORANT STUDIO and cormorant tomorrow."
        projection = importer.project_limited_reminder_response(
            [source],
            "morning",
            exact_terms=("Cormorant", "Private Cormorant Studio"),
        )
        serialized = json.dumps(projection, ensure_ascii=False)
        self.assertNotIn("private cormorant studio", serialized.casefold())
        self.assertNotIn("cormorant", serialized.casefold())
        self.assertNotIn("exact_terms", serialized)
        self.assertNotRegex(projection["summary_original"], r"█{5,}")

        with tempfile.TemporaryDirectory() as temporary_directory:
            private_dir = Path(temporary_directory) / ".private"
            private_dir.mkdir()
            terms_path = private_dir / "reminder-redactions.json"
            terms_path.write_text(
                json.dumps({"terms": ["Private Cormorant Studio", "Cormorant"]}),
                encoding="utf-8",
            )
            self.assertEqual(
                importer.load_private_redaction_terms(terms_path),
                ("Private Cormorant Studio", "Cormorant"),
            )

    def test_technical_secrets_are_removed_without_phone_date_confusion(self) -> None:
        phone = "138-" + "1234-" + "5678"
        secret_label = "pass" + "word"
        routing_label = "chat" + "_id"
        routing_id = "-100" + "1234567890"
        source = (
            "保留日期 2026-07-29 和时间 08:30。联系 care@example.com 或 "
            f"{phone}；{secret_label}=hunter-echo-77，{routing_label}={routing_id}。"
            "查看 [项目说明](https://example.com/private?id=abc) 与 "
            "`/Users/example/private/note.md`；状态库 state.db，调度目录 cron/output。"
        )
        projection = importer.project_limited_reminder_response([source], "morning")
        assert projection is not None
        masked = projection["summary_original"]
        self.assertIn("2026-07-29", masked)
        self.assertIn("08:30", masked)
        self.assertIn("项目说明", masked)
        self.assertIn("`████`", masked)
        self.assertEqual(projection["redaction_count"], masked.count("████"))
        for secret in (
            "care@example.com",
            phone,
            "hunter-echo-77",
            routing_id,
            "https://example.com",
            "/Users/example",
            "state.db",
            "cron/output",
        ):
            self.assertNotIn(secret, masked)

    def test_batch_detector_is_called_once_for_an_authorized_import(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            jobs_path, output, days_path = self.reminder_fixture(
                root,
                [
                    ("2026-07-01_08-00-00", "Meet Ada at Acme Studio."),
                    ("2026-07-02_18-00-00", "Meet Grace at North Lab."),
                ],
            )
            calls: list[list[str]] = []

            def detector(texts: list[str]) -> list[dict[str, list[str]]]:
                calls.append(texts)
                return [
                    {"PersonalName": ["Ada"], "OrganizationName": ["Acme Studio"]},
                    {"PersonalName": ["Grace"], "OrganizationName": ["North Lab"]},
                ]

            snapshot = importer.build_snapshot(
                jobs_path,
                output,
                days_path,
                None,
                authorize_self_reminders=True,
                authorize_authentic_reminder_disclosure=True,
                entity_detector=detector,
            )

        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0]), 2)
        serialized = json.dumps(snapshot, ensure_ascii=False)
        for entity in ("Ada", "Acme Studio", "Grace", "North Lab"):
            self.assertNotIn(entity, serialized)
        for day in snapshot["days"]:
            [pulse] = day["pulses"]
            self.assertEqual(
                pulse["disclosure_policy"],
                "authentic_entity_masked_reminder_v2",
            )
            self.assertNotIn("summary_zh", pulse)
            self.assertNotIn("summary_en", pulse)
            self.assertNotIn("action_provenance", pulse)

    def test_authorized_detector_failure_fails_closed_without_test_bypass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            jobs_path, output, days_path = self.reminder_fixture(
                root,
                [("2026-07-01_08-00-00", "Meet Ada.")],
            )

            def failed_detector(_texts: list[str]) -> list[dict[str, list[str]]]:
                raise disclosure.EntityDetectionError("synthetic failure")

            with self.assertRaisesRegex(SystemExit, "entity detection failed closed"):
                importer.build_snapshot(
                    jobs_path,
                    output,
                    days_path,
                    None,
                    authorize_self_reminders=True,
                    authorize_authentic_reminder_disclosure=True,
                    entity_detector=failed_detector,
                )

    @unittest.skipUnless(
        sys.platform == "darwin" and shutil.which("swift"),
        "Apple NaturalLanguage helper requires macOS and Swift",
    )
    def test_swift_batch_helper_has_synthetic_json_contract(self) -> None:
        result = importer.detect_reminder_entities_batch(
            ["Ada Lovelace met the team at OpenAI.", "今天允许自己休息。"]
        )
        self.assertEqual(len(result), 2)
        for entry in result:
            self.assertEqual(set(entry), {"PersonalName", "OrganizationName"})
            self.assertTrue(
                all(
                    isinstance(value, str)
                    for values in entry.values()
                    for value in values
                )
            )

    def test_adjacent_invalid_run_cannot_borrow_same_job_valid_window(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "output"
            output.mkdir()
            jobs_path = root / "jobs.json"
            days_path = root / "days.json"
            state_db_path = root / "state.db"
            jobs_path.write_text(
                json.dumps({"jobs": [{"id": "same-job", "name": "system health routine"}]}),
                encoding="utf-8",
            )
            days_path.write_text(json.dumps([{"date": "2026-07-03"}]), encoding="utf-8")
            (output / "same-job").mkdir()
            (output / "same-job" / "2026-07-03_09-00-00.md").write_text(
                "private\n## Response\n[SILENT]",
                encoding="utf-8",
            )
            (output / "same-job" / "2026-07-03_09-10-00.md").write_text(
                "private\n## Response\n[SILENT]",
                encoding="utf-8",
            )
            (output / "same-job" / "2026-07-03_09-20-00.md").write_text(
                "private\n## Response\n[SILENT]",
                encoding="utf-8",
            )

            with closing(sqlite3.connect(state_db_path)) as connection:
                connection.execute(
                    "CREATE TABLE sessions (id TEXT, source TEXT, started_at REAL, ended_at REAL)"
                )
                connection.executemany(
                    "INSERT INTO sessions VALUES (?, 'cron', strftime('%s', ?), strftime('%s', ?))",
                    [
                        ("cron_same-job_20260703_085000", "2026-07-03 00:50:00", "2026-07-03 00:58:00"),
                        ("cron_same-job_20260703_085900", "2026-07-03 00:59:00", None),
                        ("cron_same-job_20260703_090400", "2026-07-03 01:04:00", "2026-07-03 01:10:00"),
                    ],
                )
                connection.commit()

            snapshot = importer.build_snapshot(jobs_path, output, days_path, state_db_path)

        pulses = snapshot["days"][0]["pulses"]
        self.assertEqual(len(pulses), 3)
        self.assertEqual(
            [(pulse["start"], pulse["end"], pulse["time_provenance"]) for pulse in pulses],
            [
                ("08:59", "09:00", "receipt_timestamp_estimate"),
                ("09:04", "09:10", "observed_session_window"),
                ("09:19", "09:20", "receipt_timestamp_estimate"),
            ],
        )
        self.assertEqual(snapshot["observed_session_window_count"], 1)

    def test_absent_source_behavior_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            days_path = root / "days.json"
            days_path.write_text(json.dumps([{"date": "2026-07-01"}]), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "Cron jobs source does not exist"):
                importer.build_snapshot(root / "missing-jobs.json", root / "missing-output", days_path)


if __name__ == "__main__":
    unittest.main()
