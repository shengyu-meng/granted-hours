#!/usr/bin/env python3
"""Builder contracts for evidence-bound events and readable market climate."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import build_timetable_data as builder


class BuilderAgentMarketProjectionTests(unittest.TestCase):
    @staticmethod
    def agent_residue() -> dict:
        return {
            "category": "code_development",
            "en": "Codex/GPT completed evidence-backed coding for ████; a validation result was returned.",
            "zh": "Codex/GPT 完成 ████ 的编码与审校，并返回验收结果。",
            "redaction_status": "partial",
            "redaction_count": 1,
            "source_kind": "agent_session",
            "faithfulness": "faithful_summary",
            "evidence_count": 1,
            "agent_labels": ["Codex", "GPT"],
            "start": "10:07",
            "end": "10:43",
            "time_provenance": "observed_session_window",
        }

    @staticmethod
    def collaboration_residue() -> dict:
        return {
            "category": "research_synthesis",
            "en": "Research threads and validation",
            "zh": "研究线索与验证",
            "redaction_status": "partial",
            "redaction_count": 1,
            "source_kind": "collaboration_session",
            "faithfulness": "faithful_summary",
            "evidence_count": 3,
            "session_count": 2,
            "delegated_agent_count": 1,
            "returned_agent_count": 1,
            "request_zh": "要求比较 ████ 的证据，并说明为什么结论仍需保留条件。",
            "request_en": "Requested an evidence comparison for ████ and an explanation of why the conclusion remains conditional.",
            "outcome_zh": "完成了证据分层，保留了可复核结论与待验证问题。",
            "outcome_en": "Completed the evidence ranking, retaining reviewable conclusions and open questions.",
            "completion_status": "completed",
            "pair_provenance": "assistant_result_summary",
            "agent_labels": ["Hermes", "GPT", "subagent"],
            "start": "02:30",
            "end": "23:10",
            "time_provenance": "observed_message_envelope",
        }

    def write_history(self, residue: dict) -> Path:
        path = Path(self.temporary_directory.name) / "history.json"
        path.write_text(
            json.dumps(
                {
                    "schema": "granted-hours-timetable-history-v4",
                    "days": [
                        {
                            "date": "2026-07-01",
                            "provenance": "record_based",
                            "assigned_residues": [residue],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_builder_accepts_and_preserves_observed_agent_windows_without_hashes(self) -> None:
        loaded = builder.load_history(self.write_history(self.agent_residue()))
        residue = loaded["2026-07-01"]["assigned_residues"][0]
        self.assertEqual(residue["source_kind"], "agent_session")
        self.assertEqual(residue["agent_labels"], ["Codex", "GPT"])
        forbidden_public_field = "evidence" + "_hashes"
        self.assertNotIn(forbidden_public_field, residue)
        self.assertEqual(
            builder.task_ranges(
                "2026-07-01",
                [residue],
                {"start": "03:17", "end": "04:17"},
            ),
            [("10:07", "10:43")],
        )

    def test_builder_rejects_missing_invalid_or_overlong_agent_windows(self) -> None:
        for mutation in (
            {"start": None},
            {"end": "09:59"},
            {"end": "17:00"},
            {"time_provenance": "estimated_semantic_window"},
        ):
            with self.subTest(mutation=mutation):
                residue = {**self.agent_residue(), **mutation}
                with self.assertRaises(SystemExit):
                    builder.load_history(self.write_history(residue))

    def test_builder_accepts_collaboration_envelopes_and_bilingual_pairs(self) -> None:
        loaded = builder.load_history(self.write_history(self.collaboration_residue()))
        residue = loaded["2026-07-01"]["assigned_residues"][0]
        self.assertEqual(residue["source_kind"], "collaboration_session")
        self.assertEqual(residue["session_count"], 2)
        self.assertEqual(residue["completion_status"], "completed")
        self.assertIn("Requested", residue["request_en"])
        self.assertEqual(
            builder.task_ranges(
                "2026-07-01",
                [residue],
                {"start": "03:17", "end": "04:17"},
            ),
            [("02:30", "23:10")],
        )

    def test_market_occurrence_keeps_public_instruments_prices_and_judgment(self) -> None:
        pulse = {
            "category": "us_market_scan",
            "count": 2,
            "summary_zh": (
                "本窗口完成 2 次美股市场扫描；状态：进攻 / 风险扩张；"
                "主题：AI 硬件与半导体；公开事实：星海科技 SSEA 报 42.30 美元，涨幅 +6.8%。"
            ),
            "summary_en": (
                "2 U.S. market scans completed; regime: offensive / risk-expansion; "
                "themes: AI hardware and semiconductors. Retained public evidence: "
                "SSEA $42.30, +6.8%."
            ),
        }
        summary_zh, summary_en = builder.public_occurrence_summary(pulse)
        public_copy = f"{summary_zh} {summary_en}"
        for expected in ("星海科技", "SSEA", "42.30", "+6.8%", "进攻"):
            self.assertIn(expected, public_copy)
        self.assertNotIn("未形成公开级别", public_copy)
        self.assertNotIn("无额外公开主题", public_copy)

    def test_market_climate_aggregate_retains_distinct_public_facts(self) -> None:
        pulses = [
            {
                "category": "ah_market_scan",
                "start": "08:30",
                "count": 1,
                "summary_zh": "公开事实：星海科技 SSEA 报 42.30 美元，涨幅 +6.8%。",
                "summary_en": "Retained public evidence: SSEA $42.30, +6.8%.",
            },
            {
                "category": "ah_market_scan",
                "start": "14:30",
                "count": 1,
                "summary_zh": "公开事实：轨道科技 ORBT 上涨 3.1%。",
                "summary_en": "Retained public evidence: ORBT rose 3.1%.",
            },
        ]
        summary_zh, summary_en = builder.climate_group_summary(pulses)
        public_copy = f"{summary_zh} {summary_en}"
        for expected in ("SSEA", "42.30", "+6.8%", "ORBT", "3.1%"):
            self.assertIn(expected, public_copy)
        self.assertIn("盘前 1 窗", summary_zh)
        self.assertIn("盘中 1 窗", summary_zh)

    def test_market_climate_groups_merge_to_one_daily_card_per_market(self) -> None:
        pulses = []
        for category, starts in {
            "ah_market_scan": ("08:30", "12:30", "16:00"),
            "us_market_scan": ("06:30", "20:30", "23:00"),
        }.items():
            for index, start in enumerate(starts, 1):
                pulses.append(
                    {
                        "footprint_id": f"{category}-{index}",
                        "category": category,
                        "start": start,
                        "end": "23:59" if start == "23:00" else start,
                        "count": 1,
                        "summary_zh": "公开事实：保留公开市场证据。",
                        "summary_en": "Retained public evidence: public market evidence.",
                    }
                )
        groups = {builder.climate_family_and_window(pulse) for pulse in pulses}
        self.assertEqual(groups, {("ah_market", "daily"), ("us_market", "daily")})

    def test_support_checks_merge_to_one_readable_daily_card(self) -> None:
        pulses = [
            {
                "footprint_id": "background-001",
                "category": "background_routine",
                "start": "00:30",
                "count": 2,
                "public_alert": True,
            },
            {
                "footprint_id": "background-002",
                "category": "system_routine",
                "start": "12:30",
                "count": 3,
            },
            {
                "footprint_id": "background-003",
                "category": "background_routine",
                "start": "21:30",
                "count": 2,
            },
        ]
        groups = {builder.climate_family_and_window(pulse) for pulse in pulses}
        self.assertEqual(groups, {("support_checks", "daily")})
        self.assertTrue(
            all(
                builder.classify_public_pulse(pulse)["outcome"] == "climate_aggregate"
                for pulse in pulses
            )
        )
        self.assertEqual(
            builder.climate_group_label("support_checks", "daily"),
            ("后台例行运行 · 当日合并", "Background routine activity · daily rollup"),
        )
        summary_zh, summary_en = builder.climate_group_summary(pulses)
        self.assertIn("全天 3 个精确窗口共完成 7 次后台例行运行", summary_zh)
        self.assertIn("1 个窗口记录到通用状态变化", summary_zh)
        self.assertIn("2 个窗口无须单独提示", summary_zh)
        self.assertIn("7 background routine run(s)", summary_en)
        self.assertIn("1 window(s) recorded a general status change", summary_en)

    def test_month_cell_sources_distinguish_three_source_types(self) -> None:
        tasks = [
            {"source_kind": "collaboration_session"},
            {"source_kind": "task_card"},
        ]
        pulses = [{"count": 3}]
        sources = builder.build_cell_sources(tasks, pulses)
        self.assertTrue(sources["free_creation"]["present"])
        self.assertEqual(sources["routine"]["count"], 3)
        self.assertEqual(sources["active_collaboration"]["count"], 2)


if __name__ == "__main__":
    unittest.main()
