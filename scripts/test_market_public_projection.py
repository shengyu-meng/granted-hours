#!/usr/bin/env python3
"""Focused disclosure-contract tests for public market summaries."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import import_timetable_pulses as pulse_importer
import public_projection_privacy as privacy


class MarketPublicProjectionTests(unittest.TestCase):
    def write_denylist(
        self,
        root: Path,
        filename: str,
        kind: str,
        terms: list[str],
    ) -> Path:
        private_root = root / ".private"
        private_root.mkdir(exist_ok=True)
        path = private_root / filename
        path.write_text(
            json.dumps(
                {
                    "schema": privacy.PRIVATE_DENYLIST_SCHEMA,
                    "kind": kind,
                    "terms": terms,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def test_public_non_holding_market_facts_remain_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            holdings_path = self.write_denylist(
                root,
                "holdings-denylist.json",
                "holdings",
                ["NOVA", "诺瓦能源"],
            )
            sources_path = self.write_denylist(
                root,
                "self-media-denylist.json",
                "self_media_sources",
                ["秘境财经"],
            )
            holdings = privacy.load_private_denylist(holdings_path, "holdings")
            sources = privacy.load_private_denylist(
                sources_path,
                "self_media_sources",
            )

            facts = privacy.project_market_evidence(
                [
                    (
                        "星海科技 SSEA 报 42.30 美元，涨幅 +6.8%；"
                        "AI 硬件需求改善，市场判断偏进攻。"
                    ),
                    "诺瓦能源 NOVA 现价 18.20 美元；持仓成本 12.10，计划加仓。",
                    "来源：秘境财经；作者：某博主 https://private.example/report",
                ],
                holdings_terms=holdings,
                source_terms=sources,
            )

        public_copy = " ".join(facts)
        for expected in ("星海科技", "SSEA", "42.30", "+6.8%", "AI 硬件", "进攻"):
            self.assertIn(expected, public_copy)
        for forbidden in (
            "NOVA",
            "诺瓦能源",
            "持仓",
            "成本",
            "加仓",
            "秘境财经",
            "某博主",
            "private.example",
            "https://",
        ):
            self.assertNotIn(forbidden, public_copy)

    def test_same_public_ticker_is_masked_once_it_enters_holdings_denylist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            holdings_path = self.write_denylist(
                root,
                "holdings-denylist.json",
                "holdings",
                ["SSEA", "星海科技"],
            )
            sources_path = self.write_denylist(
                root,
                "self-media-denylist.json",
                "self_media_sources",
                ["秘境财经"],
            )
            facts = privacy.project_market_evidence(
                [
                    "星海科技 SSEA 报 42.30 美元，涨幅 +6.8%，市场判断偏进攻。",
                    "秘境财经称另一公开标的 ORBT 上涨 3.1%。",
                ],
                holdings_terms=privacy.load_private_denylist(
                    holdings_path,
                    "holdings",
                ),
                source_terms=privacy.load_private_denylist(
                    sources_path,
                    "self_media_sources",
                ),
            )

        public_copy = " ".join(facts)
        self.assertIn(privacy.FIXED_REDACTION_BLOCK, public_copy)
        self.assertNotIn("SSEA", public_copy)
        self.assertNotIn("星海科技", public_copy)
        self.assertIn("42.30", public_copy)
        self.assertIn("+6.8%", public_copy)
        self.assertIn("进攻", public_copy)
        self.assertIn("ORBT", public_copy)
        self.assertIn("3.1%", public_copy)
        self.assertNotIn("秘境财经", public_copy)
        self.assertNotIn("称", public_copy)

    def test_source_attribution_is_stripped_without_losing_the_stock_fact(self) -> None:
        source_terms = (
            "镜海频道",
            "Lumen Creator",
            "Northstar Account",
            "Orbital Breakout Note",
        )
        facts = privacy.project_market_evidence(
            [
                (
                    "来源：镜海频道称轨道科技 ORBT 报 27.40 美元，"
                    "涨幅 +3.1%，判断强势。"
                ),
                (
                    "Publisher: Lumen Creator — ORBT $27.40, +3.1%, strong; "
                    "account: Northstar Account; article title: Orbital Breakout "
                    "Note https://source.example/private"
                ),
            ],
            holdings_terms=(),
            source_terms=source_terms,
        )
        public_copy = " ".join(facts)
        for expected in ("轨道科技", "ORBT", "27.40", "+3.1%", "强势"):
            self.assertIn(expected, public_copy)
        for forbidden in (
            *source_terms,
            "来源",
            "称",
            "Publisher",
            "account",
            "article title",
            "https://",
            "source.example",
        ):
            self.assertNotIn(forbidden, public_copy)

    def test_technical_receipt_traces_are_dropped_but_market_facts_survive(self) -> None:
        facts = privacy.project_market_evidence(
            [
                "[SILENT]；`futu_sync_live_holdings.py` → `/tmp/live.json`；"
                "临时验证脚本已通过；轨道科技 ORBT 报 27.40 美元，涨幅 +3.1%。"
            ],
            holdings_terms=(),
            source_terms=(),
        )
        public_copy = " ".join(facts)
        for expected in ("轨道科技", "ORBT", "27.40", "+3.1%"):
            self.assertIn(expected, public_copy)
        for forbidden in (
            "SILENT",
            "futu_sync_live_holdings.py",
            "/tmp/",
            "临时验证脚本",
        ):
            self.assertNotIn(forbidden, public_copy)

    def test_private_trade_clauses_do_not_remove_neighboring_public_facts(self) -> None:
        facts = privacy.project_market_evidence(
            [
                (
                    "账户持有 120 股，轨道科技 ORBT 报 27.40 美元，"
                    "持仓成本 19.20 美元，市场判断偏强势。"
                )
            ],
            holdings_terms=(),
            source_terms=(),
        )
        public_copy = " ".join(facts)
        for expected in ("轨道科技", "ORBT", "27.40", "强势"):
            self.assertIn(expected, public_copy)
        for forbidden in ("账户", "持有", "120", "持仓", "成本", "19.20"):
            self.assertNotIn(forbidden, public_copy)

    def test_comma_free_parenthetical_conjunction_and_period_clauses(self) -> None:
        fixtures = (
            "轨道科技 ORBT 报 27.40 美元（持仓成本 19.20 美元）市场判断仍偏强势。",
            "ORBT is at $27.40 with a position cost of $19.20 while the market outlook remains strong.",
            "轨道科技 ORBT 报 27.40 美元且买入 10 股成本 19.20 美元同时机器人主题仍强势。",
            "ORBT $27.40 is strong. My portfolio position cost is $19.20.",
        )
        for response in fixtures:
            with self.subTest(response=response[:12]):
                public_copy = " ".join(
                    privacy.project_market_evidence(
                        [response],
                        holdings_terms=(),
                        source_terms=(),
                    )
                )
                self.assertIn("ORBT", public_copy)
                self.assertIn("27.40", public_copy)
                self.assertNotIn("19.20", public_copy)
                self.assertIsNone(
                    privacy.ACCOUNT_POSITION_TRADE_RE.search(public_copy)
                )

    def test_mixed_private_clauses_are_safe_through_receipt_importer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "output"
            (output / "market-job").mkdir(parents=True)
            jobs = root / "jobs.json"
            days = root / "days.json"
            jobs.write_text(
                json.dumps(
                    {"jobs": [{"id": "market-job", "name": "U.S. market scan"}]}
                ),
                encoding="utf-8",
            )
            days.write_text(
                json.dumps([{"date": "2026-07-01"}]),
                encoding="utf-8",
            )
            (output / "market-job" / "2026-07-01_21-00-00.md").write_text(
                "private prompt\n## Response\n"
                "轨道科技 ORBT 报 27.40 美元（持仓成本 19.20 美元），市场判断仍偏强势。\n"
                "ORBT $27.40 is strong. My portfolio position cost is $19.20.\n"
                "ORBT is at $27.40 and I bought 10 shares at $19.20 while robotics remains strong.",
                encoding="utf-8",
            )
            snapshot = pulse_importer.build_snapshot(
                jobs,
                output,
                days,
                None,
            )

        [pulse] = snapshot["days"][0]["pulses"]
        public_copy = f"{pulse['summary_zh']} {pulse['summary_en']}"
        for expected in ("ORBT", "27.40", "强势"):
            self.assertIn(expected, public_copy)
        for forbidden in ("19.20", "持仓", "成本", "portfolio", "position", "bought"):
            self.assertNotIn(forbidden, public_copy)

    def test_non_held_followed_recommended_and_source_discovered_tickers_stay_public(
        self,
    ) -> None:
        facts = privacy.project_market_evidence(
            [
                "关注标的 FOLW 报 11.20 美元，涨幅 +1.2%。",
                "Heizhou 推荐 RECO，现价 22.40 美元，判断偏强势。",
                "来源：Synthetic Channel 称 FOUND 上涨 3.1%。",
            ],
            holdings_terms=("HELD",),
            source_terms=("Synthetic Channel",),
        )
        public_copy = " ".join(facts)
        for expected in ("FOLW", "RECO", "FOUND", "11.20", "22.40", "3.1%"):
            self.assertIn(expected, public_copy)
        for forbidden in ("HELD", "Synthetic Channel", "来源", "称"):
            self.assertNotIn(forbidden, public_copy)

    def test_denylist_terms_never_serialize_into_public_projection(self) -> None:
        terms = ("PRIVATE-HOLDING-XYZ", "PRIVATE-SOURCE-XYZ")
        facts = privacy.project_market_evidence(
            [
                "PRIVATE-HOLDING-XYZ 报 19.80 美元，+2.4%。",
                "PRIVATE-SOURCE-XYZ：公开公司 SAFE 报 88.00 美元。",
            ],
            holdings_terms=(terms[0],),
            source_terms=(terms[1],),
        )
        serialized = json.dumps({"facts": facts}, ensure_ascii=False)
        for term in terms:
            self.assertNotIn(term, serialized)
        self.assertIn("SAFE", serialized)

    def test_phone_and_long_account_like_numbers_are_always_masked(self) -> None:
        phone = "138" + "1234" + "5678"
        account = "6222" + "0000" + "0000" + "0000" + "123"
        grouped_account = " ".join(["6222", "0000", "0000", "0000", "123"])
        facts = privacy.project_market_evidence(
            [
                f"机器人主题保持强势，联络号 {phone}，上游组件 {account}。",
                f"另一条记录使用分组账号 {grouped_account}。",
            ],
            holdings_terms=(),
            source_terms=(),
        )
        serialized = " ".join(facts)
        self.assertNotIn(phone, serialized)
        self.assertNotIn(account, serialized)
        self.assertNotIn(grouped_account, serialized)
        self.assertIn(privacy.FIXED_REDACTION_BLOCK, serialized)

    def test_market_summary_generator_uses_projected_facts_not_old_fallbacks(self) -> None:
        summary_zh, summary_en = pulse_importer.public_summary(
            "us_market_scan",
            [
                "星海科技 SSEA 报 42.30 美元，涨幅 +6.8%，AI 硬件需求改善。",
                "PRIVATE-HOLDING 现价 18.20 美元，持仓成本 12.10。",
                "来源：PRIVATE-SOURCE https://private.example/report",
            ],
            2,
            holdings_terms=("PRIVATE-HOLDING",),
            source_terms=("PRIVATE-SOURCE",),
        )
        public_copy = f"{summary_zh} {summary_en}"
        for expected in ("SSEA", "42.30", "+6.8%", "AI 硬件"):
            self.assertIn(expected, public_copy)
        for forbidden in (
            "PRIVATE-HOLDING",
            "PRIVATE-SOURCE",
            "持仓成本",
            "private.example",
            "未形成公开级别",
            "无额外公开主题",
            "no public-level regime conclusion",
            "no additional public theme",
        ):
            self.assertNotIn(forbidden, public_copy)

    def test_state_db_market_refresh_backfills_only_direct_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            db_path = root / "state.db"
            snapshot_path = root / "snapshot.json"
            existing_nonmarket = {
                "start": "08:00",
                "end": "08:05",
                "duration_minutes": 5,
                "execution_minutes": 5,
                "time_bucket": "morning",
                "category": "system_routine",
                "count": 1,
                "time_provenance": "observed_session_window",
                "summary_provenance": "derived_public_safe",
                "summary_zh": "保留的非市场记录",
                "summary_en": "Preserved non-market record.",
            }
            snapshot = {
                "schema": pulse_importer.PULSE_SNAPSHOT_SCHEMA,
                "timezone": "Asia/Shanghai",
                "source_file_count": 1,
                "deduplicated_run_count": 1,
                "observed_session_window_count": 1,
                "days": [
                    {
                        "date": "2026-07-01",
                        "pulses": [
                            existing_nonmarket,
                            {
                                **existing_nonmarket,
                                "start": "21:15",
                                "end": "21:16",
                                "duration_minutes": 1,
                                "category": "us_market_scan",
                                "summary_zh": "未形成公开级别结论；无额外公开主题。",
                                "summary_en": "No public-level conclusion; no additional public theme.",
                            },
                        ],
                    }
                ],
            }
            snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
            with sqlite3.connect(db_path) as connection:
                connection.executescript(
                    """
                    CREATE TABLE sessions (
                        id TEXT PRIMARY KEY,
                        source TEXT NOT NULL,
                        model TEXT,
                        title TEXT,
                        started_at REAL NOT NULL,
                        ended_at REAL
                    );
                    CREATE TABLE messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT,
                        timestamp REAL NOT NULL,
                        active INTEGER DEFAULT 1
                    );
                    """
                )
                timestamp = datetime(
                    2026,
                    7,
                    1,
                    21,
                    15,
                    tzinfo=ZoneInfo("Asia/Shanghai"),
                ).timestamp()
                connection.execute(
                    "INSERT INTO sessions VALUES (?, 'cron', 'gpt', ?, ?, ?)",
                    (
                        "private-market-session",
                        "topic-us-market-regime-preopen",
                        timestamp,
                        timestamp + 180,
                    ),
                )
                connection.execute(
                    "INSERT INTO messages(session_id, role, content, timestamp, active) "
                    "VALUES (?, 'assistant', ?, ?, 1)",
                    (
                        "private-market-session",
                        (
                            "星海科技 SSEA 报 42.30 美元，涨幅 +6.8%，市场判断偏进攻。\n"
                            "PRIVATE-HOLDING 报 18.20 美元，持仓成本 12.10。\n"
                            "来源：PRIVATE-SOURCE https://private.example/report"
                        ),
                        timestamp + 179,
                    ),
                )

            refreshed = pulse_importer.refresh_market_snapshot_from_state(
                snapshot_path=snapshot_path,
                state_db_path=db_path,
                holdings_terms=("PRIVATE-HOLDING",),
                source_terms=("PRIVATE-SOURCE",),
            )

        pulses = refreshed["days"][0]["pulses"]
        self.assertIn(existing_nonmarket, pulses)
        [market] = [pulse for pulse in pulses if pulse["category"] == "us_market_scan"]
        public_copy = f"{market['summary_zh']} {market['summary_en']}"
        self.assertIn("SSEA", public_copy)
        self.assertIn("42.30", public_copy)
        self.assertNotIn("PRIVATE-HOLDING", public_copy)
        self.assertNotIn("PRIVATE-SOURCE", public_copy)
        self.assertNotIn("private-market-session", json.dumps(refreshed))
        self.assertNotIn("未形成公开级别", public_copy)

    def test_receipt_reprojection_replaces_markets_only(self) -> None:
        reminder = {
            "start": "08:00",
            "end": "08:01",
            "category": "daily_reminder",
            "summary_original": "保留原提醒 ████",
            "summary_en": "Keep the existing reminder ████.",
        }
        old_market = {
            "start": "21:00",
            "end": "21:01",
            "category": "us_market_scan",
            "summary_zh": "未形成公开级别结论；无额外公开主题。",
            "summary_en": "No public-level conclusion; no additional public theme.",
        }
        new_market = {
            "start": "21:00",
            "end": "21:03",
            "category": "us_market_scan",
            "summary_zh": "公开标的 SAFEQ 报 42.30 美元，判断偏强势。",
            "summary_en": "Public instrument SAFEQ was at $42.30 and remained strong.",
        }
        existing = {
            "schema": pulse_importer.PULSE_SNAPSHOT_SCHEMA,
            "days": [
                {"date": "2026-07-01", "pulses": [reminder, old_market]},
            ],
        }
        rebuilt = {
            "schema": pulse_importer.PULSE_SNAPSHOT_SCHEMA,
            "days": [
                {
                    "date": "2026-07-01",
                    "pulses": [
                        {**reminder, "summary_original": "不应采用的新提醒"},
                        new_market,
                    ],
                }
            ],
        }

        merged, stats = pulse_importer.merge_market_receipt_reprojection(
            existing,
            rebuilt,
            holdings_terms=("PRIVATEQ",),
            source_terms=("Private Source",),
        )

        pulses = merged["days"][0]["pulses"]
        [merged_reminder] = [
            pulse for pulse in pulses if pulse["category"] == "daily_reminder"
        ]
        [merged_market] = [
            pulse for pulse in pulses if pulse["category"] == "us_market_scan"
        ]
        self.assertEqual(merged_reminder, reminder)
        self.assertEqual(merged_market, new_market)
        self.assertEqual(
            stats,
            {
                "replaced": 1,
                "added": 0,
                "legacy_normalized": 0,
                "date_coverage": 1,
            },
        )

    def test_receipt_reprojection_normalizes_safe_legacy_aggregate_if_raw_is_absent(
        self,
    ) -> None:
        existing = {
            "schema": pulse_importer.PULSE_SNAPSHOT_SCHEMA,
            "days": [
                {
                    "date": "2026-07-01",
                    "pulses": [
                        {
                            "start": "21:00",
                            "category": "us_market_scan",
                            "count": 1,
                            "summary_zh": "未形成公开级别结论；公开主题：机器人。",
                            "summary_en": "No public-level conclusion; public theme: robotics.",
                        }
                    ],
                }
            ],
        }
        rebuilt = {
            "schema": pulse_importer.PULSE_SNAPSHOT_SCHEMA,
            "days": [{"date": "2026-07-01", "pulses": []}],
        }

        merged, stats = pulse_importer.merge_market_receipt_reprojection(
            existing,
            rebuilt,
            holdings_terms=(),
            source_terms=(),
        )

        [market] = merged["days"][0]["pulses"]
        public_copy = f"{market['summary_zh']} {market['summary_en']}"
        self.assertIn("具身智能", public_copy)
        self.assertIn("embodied AI", public_copy)
        self.assertNotIn("未形成公开级别", public_copy)
        self.assertNotIn("No public-level conclusion", public_copy)
        self.assertEqual(stats["legacy_normalized"], 1)

    def test_private_denylist_must_live_under_ignored_private_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "holdings-denylist.json"
            path.write_text(
                json.dumps(
                    {
                        "schema": privacy.PRIVATE_DENYLIST_SCHEMA,
                        "kind": "holdings",
                        "terms": ["SSEA"],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "ignored .private"):
                privacy.load_private_denylist(path, "holdings")


if __name__ == "__main__":
    unittest.main()
