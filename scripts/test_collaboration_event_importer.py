#!/usr/bin/env python3
"""Coverage, lineage, privacy, and idempotence tests for dialogue imports."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from unittest import mock
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import apply_semantic_public_policy as policy
import import_collaboration_events as importer


TIMEZONE = ZoneInfo("Asia/Shanghai")


class CollaborationEventImporterTests(unittest.TestCase):
    def test_scoped_merge_preserves_every_non_target_day_exactly(self) -> None:
        untouched = {
            "date": "2026-08-09",
            "provenance": "dialogue_based",
            "assigned_residues": [{"source_kind": "manual", "sentinel": "unchanged"}],
        }
        target = {
            "date": "2026-08-10",
            "provenance": "record_based",
            "assigned_residues": [],
        }
        history = {
            "schema": importer.HISTORY_SCHEMA,
            "note": {"en": "note", "zh": "说明"},
            "days": [untouched, target],
        }
        agent = {
            "source_kind": "agent_session",
            "category": "code_development",
            "en": "Scoped completed result",
            "zh": "限定日期的完成结果",
        }

        merged = importer.merge_history_scoped(
            history,
            {},
            {"2026-08-10": [agent]},
            ["2026-08-10"],
            {},
            [],
            ("2026-08-10",),
        )

        self.assertEqual(merged["days"][0], untouched)
        self.assertEqual(merged["days"][1]["date"], "2026-08-10")
        self.assertEqual(merged["days"][1]["assigned_residues"], [agent])

    def test_new_public_date_with_foreground_is_added_without_placeholder(self) -> None:
        history = {
            "schema": importer.HISTORY_SCHEMA,
            "note": {"en": "note", "zh": "说明"},
            "days": [],
        }
        collaboration = {
            "category": "code_development",
            "en": "Development and validation",
            "zh": "开发与验证",
            "redaction_status": "none",
            "redaction_count": 0,
            "source_kind": "collaboration_session",
            "faithfulness": "faithful_summary",
            "evidence_count": 1,
            "session_count": 1,
            "delegated_agent_count": 0,
            "returned_agent_count": 0,
            "agent_labels": ["Hermes"],
            "start": "10:00",
            "end": "10:10",
            "time_provenance": "observed_message_envelope",
            "_request_zh": "实现并验证一项开发修改，同时保留可以检查的测试结果。",
            "_request_en": "Implement and validate a development change, retaining checkable test results.",
            "_outcome_zh": "完成实现、聚焦测试与结果核验，并保留后续维护所需的边界。",
            "_outcome_en": "Completed the implementation, focused tests, and result verification, preserving maintenance boundaries.",
            "_contour_signature": "fixture-contour-1",
            "_request_topics": (),
            "_has_safe_assistant_outcome": True,
        }
        contour = {
            "date": "2026-08-02",
            "category": "code_development",
            "request_zh": collaboration["_request_zh"],
            "request_en": collaboration["_request_en"],
            "outcome_zh": collaboration["_outcome_zh"],
            "outcome_en": collaboration["_outcome_en"],
            "completion_status": "completed",
            "pair_provenance": "assistant_result_summary",
        }
        merged = importer.merge_history(
            history,
            {"2026-08-02": [collaboration]},
            {},
            ["2026-08-02"],
            {"fixture-contour-1": contour},
            [],
        )
        self.assertEqual(len(merged["days"]), 1)
        self.assertEqual(merged["days"][0]["date"], "2026-08-02")
        self.assertEqual(merged["days"][0]["provenance"], "dialogue_based")
        residue = merged["days"][0]["assigned_residues"][0]
        self.assertEqual(residue["completion_status"], "completed")
        self.assertEqual(residue["pair_provenance"], "assistant_result_summary")
        self.assertIn("实现", residue["request_zh"])
        self.assertIn("Implement", residue["request_en"])
        self.assertIn("完成", residue["outcome_zh"])
        self.assertIn("Completed", residue["outcome_en"])

    def test_new_public_date_without_foreground_keeps_builder_fallback(self) -> None:
        history = {
            "schema": importer.HISTORY_SCHEMA,
            "note": {"en": "note", "zh": "说明"},
            "days": [],
        }
        merged = importer.merge_history(history, {}, {}, ["2026-08-02"])
        self.assertEqual(merged["days"], [])

    def test_existing_public_date_can_intentionally_have_no_assigned_residues(self) -> None:
        history = {
            "schema": importer.HISTORY_SCHEMA,
            "days": [
                {
                    "date": "2026-08-02",
                    "provenance": "withheld",
                    "assigned_residues": [],
                }
            ],
        }
        merged = importer.merge_history(history, {}, {}, ["2026-08-02"])
        self.assertEqual(merged["days"][0]["assigned_residues"], [])
        self.assertEqual(merged["days"][0]["provenance"], "record_based")

    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.db = self.root / "state.db"
        self.days = self.root / "days.json"
        self.history = self.root / "history.json"
        self.detector = self.root / "detector.py"
        self.holdings = self.root / "holdings.json"
        self.self_media = self.root / "self-media.json"
        self.identities = self.root / "identities.json"
        self.contours = self.root / "contours.json"
        self.days.write_text(json.dumps([{"date": "2026-07-01"}]), encoding="utf-8")
        self.history.write_text(
            json.dumps(
                {
                    "schema": importer.HISTORY_SCHEMA,
                    "days": [
                        {
                            "date": "2026-07-01",
                            "provenance": "record_based",
                            "assigned_residues": [self.existing_residue()],
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.holdings.write_text(
            json.dumps({"terms": ["SecretTicker"]}), encoding="utf-8"
        )
        self.self_media.write_text(
            json.dumps({"terms": ["PrivateChannel"]}), encoding="utf-8"
        )
        self.identities.write_text(
            json.dumps({"terms": ["陈墨川"]}), encoding="utf-8"
        )
        self.contours.write_text(
            json.dumps(
                {
                    "schema": importer.COLLABORATION_CONTOURS_SCHEMA,
                    "contours": {},
                }
            ),
            encoding="utf-8",
        )
        self.detector.write_text(
            """#!/usr/bin/env python3
import json, sys
texts = json.load(sys.stdin)
terms = ["Alice Smith", "Secret City", "Omega Project"]
print(json.dumps([{"PrivateEntityTerms": [term for term in terms if term in text]} for text in texts]))
""",
            encoding="utf-8",
        )
        os.chmod(self.detector, 0o755)
        with sqlite3.connect(self.db) as connection:
            connection.executescript(
                """
                CREATE TABLE sessions (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    user_id TEXT,
                    model TEXT,
                    chat_type TEXT,
                    chat_id TEXT,
                    session_key TEXT,
                    origin_json TEXT,
                    parent_session_id TEXT,
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
        connection.close()
        self.add_session(
            "owner-current",
            source="telegram",
            user_id="100",
            chat_type="dm",
            chat_id="100",
            session_key="heizhou:primary:telegram:dm:100",
            origin_json=json.dumps(
                {
                    "platform": "telegram",
                    "user_id": "100",
                    "chat_id": "100",
                    "chat_type": "dm",
                }
            ),
            started="2026-07-01 09:00:00",
        )
        self.add_session(
            "owner-legacy",
            source="telegram",
            user_id="100",
            started="2026-07-01 13:00:00",
        )
        self.add_session(
            "other-group-user",
            source="telegram",
            user_id="999",
            chat_type="group",
            chat_id="-200",
            session_key="heizhou:primary:telegram:group:-200:999",
            origin_json=json.dumps(
                {
                    "platform": "telegram",
                    "user_id": "999",
                    "chat_id": "-200",
                    "chat_type": "group",
                }
            ),
            started="2026-07-01 14:00:00",
        )
        self.add_session(
            "child-agent",
            source="subagent",
            model="gpt-5.6-sol",
            parent_session_id="owner-current",
            started="2026-07-01 09:10:00",
            ended="2026-07-01 09:20:00",
        )
        self.add_message(
            "owner-current",
            "user",
            (
                "请研究 Omega Project，并解释为什么 Alice Smith 在 Secret City 提出的"
                "论文《Hidden Paper》与疾病名 Alpha综合征、持仓 SecretTicker 有关；陈墨川说"
                "如果证据不足，就明确区分事实与推断。"
            ),
            "2026-07-01 09:05:00",
        )
        self.add_message(
            "owner-current",
            "assistant",
            "核验完成：比较了三组公开证据，保留可复核的共同结论，并把推断与事实分开。",
            "2026-07-01 09:05:30",
        )
        self.add_message(
            "owner-current",
            "assistant",
            "已经完成 Cloudflare API Token 状态核验并记录部署结果。",
            "2026-07-01 09:05:40",
        )
        self.add_message(
            "owner-current",
            "assistant",
            "已经完成具体药物与身体状态的整理，并确认恢复安排。",
            "2026-07-01 09:05:50",
        )
        self.add_message("owner-current", "user", "继续", "2026-07-01 09:06:00")
        self.add_message(
            "owner-current",
            "user",
            "[IMPORTANT: Background process] tool-progress notice",
            "2026-07-01 09:07:00",
        )
        self.add_message(
            "owner-legacy",
            "user",
            "请修改视觉海报的层级，让核心判断更醒目，同时保留版式的留白与节奏。",
            "2026-07-01 13:05:00",
        )
        self.add_message(
            "other-group-user",
            "user",
            "请把其他用户的私密项目写进公开日程。",
            "2026-07-01 14:05:00",
        )
        self.add_message(
            "child-agent",
            "user",
            "Research primary evidence and return a concise audit.",
            "2026-07-01 09:10:01",
        )
        self.add_message(
            "child-agent",
            "assistant",
            "Completed the research audit and returned verified findings.",
            "2026-07-01 09:19:59",
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def serialized(value: object) -> str:
        return json.dumps(value, ensure_ascii=False, indent=2) + "\n"

    @staticmethod
    def collaboration_residue(history: dict) -> dict:
        return next(
            residue
            for day in history["days"]
            for residue in day["assigned_residues"]
            if residue["source_kind"] == "collaboration_session"
        )

    @staticmethod
    def existing_residue() -> dict:
        return {
            "category": "system_maintenance",
            "en": "Verify the public service-health record",
            "zh": "核验公开服务健康记录",
            "redaction_status": "none",
            "redaction_count": 0,
            "source_kind": "daily_record",
            "faithfulness": "faithful_summary",
        }

    @staticmethod
    def timestamp(value: str) -> float:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=TIMEZONE
        ).timestamp()

    def add_session(
        self,
        session_id: str,
        *,
        source: str,
        started: str,
        user_id: str | None = None,
        model: str | None = None,
        chat_type: str | None = None,
        chat_id: str | None = None,
        session_key: str | None = None,
        origin_json: str | None = None,
        parent_session_id: str | None = None,
        ended: str | None = None,
    ) -> None:
        with sqlite3.connect(self.db) as connection:
            connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    source,
                    user_id,
                    model,
                    chat_type,
                    chat_id,
                    session_key,
                    origin_json,
                    parent_session_id,
                    self.timestamp(started),
                    self.timestamp(ended) if ended else None,
                ),
            )
        connection.close()

    def add_message(self, session: str, role: str, content: str, at: str) -> None:
        with sqlite3.connect(self.db) as connection:
            connection.execute(
                "INSERT INTO messages(session_id, role, content, timestamp, active) VALUES (?, ?, ?, ?, 1)",
                (session, role, content, self.timestamp(at)),
            )
        connection.close()

    def run_import(self, *, dry_run: bool) -> dict:
        collaborations, _audit = importer.collect(
            self.db,
            [item["date"] for item in json.loads(self.days.read_text())],
            self.detector,
            (self.holdings, self.self_media, self.identities),
        )
        contours = {}
        for day, events in collaborations.items():
            for event in events:
                contours[event["_contour_signature"]] = {
                    "date": day,
                    "category": event["category"],
                    "request_zh": event["_request_zh"],
                    "request_en": f"Requested: {event['_request_zh']}",
                    "outcome_zh": event["_outcome_zh"],
                    "outcome_en": f"Outcome: {event['_outcome_zh']}",
                    "completion_status": (
                        "completed"
                        if event["_has_safe_assistant_outcome"]
                        else "unverified"
                    ),
                    "pair_provenance": (
                        "assistant_result_summary"
                        if event["_has_safe_assistant_outcome"]
                        else "no_public_result_evidence"
                    ),
                }
        self.contours.write_text(
            json.dumps(
                {
                    "schema": importer.COLLABORATION_CONTOURS_SCHEMA,
                    "contours": contours,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return importer.import_events(
            self.db,
            self.days,
            self.history,
            self.detector,
            (self.holdings, self.self_media, self.identities),
            dry_run,
            self.contours,
        )

    def test_owner_dialogue_legacy_sessions_and_child_lineage_are_covered(self) -> None:
        result = self.run_import(dry_run=True)
        collaborations = [
            residue
            for residue in result["history"]["days"][0]["assigned_residues"]
            if residue["source_kind"] == "collaboration_session"
        ]
        self.assertEqual(result["audit"]["meaningful_message_count"], 2)
        self.assertEqual({item["category"] for item in collaborations}, {
            "research_synthesis",
            "visual_production",
        })
        research = next(
            item for item in collaborations if item["category"] == "research_synthesis"
        )
        self.assertEqual(research["delegated_agent_count"], 1)
        self.assertEqual(research["returned_agent_count"], 1)
        self.assertIn("subagent", research["agent_labels"])

    def test_private_topic_does_not_suppress_safe_topic_in_same_category(self) -> None:
        self.add_message(
            "owner-legacy",
            "user",
            "请设计一张视觉海报，整理股票持仓和账户收益，并调整图片构图。",
            "2026-07-01 13:06:00",
        )
        with mock.patch.object(importer, "TOPIC_GROUPING_EFFECTIVE_DATE", "2026-07-01"):
            collaborations, _audit = importer.collect(
                self.db,
                ["2026-07-01"],
                self.detector,
                (self.holdings, self.self_media, self.identities),
            )
        visual_events = [
            event
            for event in collaborations["2026-07-01"]
            if event["category"] == "visual_production"
        ]
        self.assertEqual(len(visual_events), 1)
        self.assertIn("视觉海报", visual_events[0]["_request_zh"])
        self.assertNotIn("持仓", visual_events[0]["_request_zh"])
        self.assertNotIn("账户收益", visual_events[0]["_request_zh"])

    def test_same_category_preservation_matches_evidence_not_first_category(self) -> None:
        day = "2026-08-02"

        def collaboration(start: str, end: str, evidence_count: int) -> dict:
            return {
                "category": "visual_production",
                "en": "Visual creation and revision",
                "zh": "视觉创作与修改",
                "redaction_status": "none",
                "redaction_count": 0,
                "source_kind": "collaboration_session",
                "faithfulness": "faithful_summary",
                "evidence_count": evidence_count,
                "session_count": 1,
                "delegated_agent_count": 0,
                "returned_agent_count": 0,
                "agent_labels": ["Hermes"],
                "start": start,
                "end": end,
                "time_provenance": "observed_message_envelope",
                "_request_zh": "新的原始请求",
                "_outcome_zh": importer.UNVERIFIED_OUTCOME_PAIR[0],
                "_contour_signature": f"missing-{start}",
                "_request_topics": (),
                "_has_safe_assistant_outcome": False,
            }

        first = collaboration("09:00", "09:20", 2)
        second = collaboration("15:00", "15:40", 3)
        previous = []
        for label, raw in (("上午公开说明", first), ("下午公开说明", second)):
            preserved = {key: value for key, value in raw.items() if not key.startswith("_")}
            preserved.update(
                request_zh=label,
                request_en=label,
                outcome_zh="未核验",
                outcome_en="Unverified",
                completion_status="unverified",
                pair_provenance="no_public_result_evidence",
            )
            previous.append(preserved)
        history = {
            "schema": importer.HISTORY_SCHEMA,
            "days": [{"date": day, "provenance": "dialogue_based", "assigned_residues": previous}],
        }
        merged = importer.merge_history(history, {day: [second, first]}, {}, [day], {}, [])
        self.assertEqual(
            [item["request_zh"] for item in merged["days"][0]["assigned_residues"]],
            ["上午公开说明", "下午公开说明"],
        )
        self.assertEqual(
            [item["start"] for item in merged["days"][0]["assigned_residues"]],
            ["09:00", "15:00"],
        )

    def test_history_limit_is_ten_not_six(self) -> None:
        history = {
            "schema": importer.HISTORY_SCHEMA,
            "days": [
                {
                    "date": "2026-08-02",
                    "provenance": "record_based",
                    "assigned_residues": [self.existing_residue() for _ in range(10)],
                }
            ],
        }
        merged = importer.merge_history(history, {}, {}, ["2026-08-02"])
        self.assertEqual(len(merged["days"][0]["assigned_residues"]), 10)

    def test_audited_historical_agent_expansion_is_preserved(self) -> None:
        day = "2026-07-31"
        agents = [
            {
                "source_kind": "agent_session",
                "category": category,
                "en": f"Agent result {index}",
                "zh": f"Agent 结果 {index}",
            }
            for index, category in enumerate(
                ("research_synthesis", "system_maintenance", "code_development"),
                1,
            )
        ]
        history = {
            "schema": importer.HISTORY_SCHEMA,
            "days": [
                {
                    "date": day,
                    "provenance": "record_based",
                    "assigned_residues": agents[:2],
                }
            ],
        }
        merged = importer.merge_history(history, {}, {day: agents}, [day])
        retained = [
            residue
            for residue in merged["days"][0]["assigned_residues"]
            if residue["source_kind"] == "agent_session"
        ]
        self.assertEqual(len(retained), 2)

    def test_historical_dates_do_not_gain_unaudited_agent_events(self) -> None:
        day = "2026-07-25"
        agent = {
            "source_kind": "agent_session",
            "category": "research_synthesis",
            "en": "Agent result",
            "zh": "Agent 结果",
        }
        history = {
            "schema": importer.HISTORY_SCHEMA,
            "days": [
                {
                    "date": day,
                    "provenance": "record_based",
                    "assigned_residues": [],
                }
            ],
        }
        merged = importer.merge_history(history, {}, {day: [agent]}, [day])
        self.assertEqual(merged["days"][0]["assigned_residues"], [])

    def test_future_dates_accept_up_to_three_agent_events(self) -> None:
        day = importer.AGENT_EXPANSION_EFFECTIVE_DATE
        agents = [
            {
                "source_kind": "agent_session",
                "category": category,
                "en": f"Agent result {index}",
                "zh": f"Agent 结果 {index}",
            }
            for index, category in enumerate(
                ("research_synthesis", "system_maintenance", "code_development"),
                1,
            )
        ]
        history = {
            "schema": importer.HISTORY_SCHEMA,
            "days": [
                {
                    "date": day,
                    "provenance": "record_based",
                    "assigned_residues": [],
                }
            ],
        }
        merged = importer.merge_history(history, {}, {day: agents}, [day])
        self.assertEqual(len(merged["days"][0]["assigned_residues"]), 3)

    def test_bilingual_pairs_mask_named_scopes_and_exclude_other_users(self) -> None:
        result = self.run_import(dry_run=True)
        serialized = json.dumps(result["history"], ensure_ascii=False)
        for forbidden in (
            "Alice Smith",
            "Secret City",
            "Omega Project",
            "Hidden Paper",
            "Alpha综合征",
            "SecretTicker",
            "陈墨川",
            "其他用户的私密项目",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertGreater(result["audit"]["public_excerpt_count"], 0)
        research = next(
            residue
            for residue in result["history"]["days"][0]["assigned_residues"]
            if residue["source_kind"] == "collaboration_session"
            and residue["category"] == "research_synthesis"
        )
        self.assertNotIn("你主动与", research["zh"])
        self.assertNotIn("Hermes", research["zh"])
        self.assertNotIn("you initiated", research["en"].lower())
        self.assertTrue(research["request_zh"])
        self.assertTrue(research["request_en"])
        self.assertTrue(research["outcome_zh"])
        self.assertTrue(research["outcome_en"])
        self.assertEqual(research["completion_status"], "completed")
        self.assertIn(
            research["pair_provenance"],
            {"assistant_result_summary", "matched_public_result_record"},
        )
        self.assertNotIn("public_excerpts", research)
        self.assertGreaterEqual(result["audit"]["rejected_outcome_candidate_count"], 2)
        self.assertNotIn("Cloudflare", serialized)
        self.assertNotIn("API Token", serialized)
        self.assertNotIn("具体药物", serialized)

    def test_missing_result_is_labeled_unverified_in_both_languages(self) -> None:
        collaboration = {
            "category": "document_processing",
            "en": "Writing and document refinement",
            "zh": "写作与文档打磨",
            "redaction_status": "none",
            "redaction_count": 0,
            "source_kind": "collaboration_session",
            "faithfulness": "faithful_summary",
            "evidence_count": 1,
            "session_count": 1,
            "delegated_agent_count": 0,
            "returned_agent_count": 0,
            "agent_labels": ["Hermes"],
            "start": "10:00",
            "end": "10:10",
            "time_provenance": "observed_message_envelope",
            "_request_zh": "整理现有材料，改善结构与措辞，并形成可继续审阅的版本。",
            "_request_en": "Organize the available material, improve structure and wording, and produce a reviewable version.",
            "_outcome_zh": "当天没有找到可以安全公开、并与这组要求可靠对应的完成记录；不把计划或推断写成已完成。",
            "_outcome_en": "No public-safe completion record was found that reliably matches this request group.",
            "_contour_signature": "fixture-contour-2",
            "_request_topics": (),
            "_has_safe_assistant_outcome": False,
        }
        contour = {
            "date": "2026-08-02",
            "category": "document_processing",
            "request_zh": collaboration["_request_zh"],
            "request_en": collaboration["_request_en"],
            "outcome_zh": importer.UNVERIFIED_OUTCOME_PAIR[0],
            "outcome_en": importer.UNVERIFIED_OUTCOME_PAIR[1],
            "completion_status": "unverified",
            "pair_provenance": "no_public_result_evidence",
        }
        merged = importer.merge_history(
            {"schema": importer.HISTORY_SCHEMA, "days": []},
            {"2026-08-02": [collaboration]},
            {},
            ["2026-08-02"],
            {"fixture-contour-2": contour},
            [],
        )
        residue = merged["days"][0]["assigned_residues"][0]
        self.assertEqual(residue["completion_status"], "unverified")
        self.assertEqual(residue["pair_provenance"], "no_public_result_evidence")
        self.assertIn("不把计划或推断写成已完成", residue["outcome_zh"])
        self.assertIn("not presented as completed work", residue["outcome_en"])

    def test_request_uses_masked_owner_contour_not_category_template(self) -> None:
        result = self.run_import(dry_run=True)
        collaborations = [
            residue
            for day in result["history"]["days"]
            for residue in day["assigned_residues"]
            if residue["source_kind"] == "collaboration_session"
        ]
        self.assertTrue(collaborations)
        forbidden_templates = {
            "要求澄清一个工作判断，比较可行路径，并保留后续复核所需的边界。",
            "要求调整视觉表达，使构图、层级与生成方法更清楚、更可复核。",
            "完成了视觉结构调整与结果核验，使主要判断、构图和迭代路径可以逐项检查。",
            "要求实现并验证一项开发修改，同时保留可以检查的测试结果。",
            "要求整理现有材料，改善结构与措辞，并形成可以继续审阅的版本。",
        }
        for residue in collaborations:
            self.assertNotIn(residue["request_zh"], forbidden_templates)
            self.assertNotIn(residue["outcome_zh"], forbidden_templates)

    def test_missing_contour_fails_closed(self) -> None:
        self.contours.write_text(
            json.dumps(
                {
                    "schema": importer.COLLABORATION_CONTOURS_SCHEMA,
                    "contours": {},
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(ValueError):
            importer.import_events(
                self.db,
                self.days,
                self.history,
                self.detector,
                (self.holdings, self.self_media, self.identities),
                True,
                self.contours,
            )

    def test_import_is_idempotent(self) -> None:
        first = self.run_import(dry_run=False)
        second = self.run_import(dry_run=False)
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])

    def test_import_then_semantic_import_semantic_reaches_fixed_point(self) -> None:
        # A manually authored contour whose bilingual copy the semantic public
        # policy abstracts. A re-import of identical evidence must preserve that
        # transformation instead of restoring the sensitive contour/source text,
        # so import -> semantic -> import -> semantic is a zero-change fixed
        # point while new evidence still regenerates (evidence pairing).
        day = "2026-08-02"
        collaboration = {
            "category": "social_media_organization",
            "en": "Content organization and publishing",
            "zh": "内容组织与发布",
            "redaction_status": "none",
            "redaction_count": 0,
            "source_kind": "collaboration_session",
            "faithfulness": "faithful_summary",
            "evidence_count": 1,
            "session_count": 1,
            "delegated_agent_count": 0,
            "returned_agent_count": 0,
            "agent_labels": ["Hermes"],
            "start": "10:00",
            "end": "10:10",
            "time_provenance": "observed_message_envelope",
            "_request_zh": "把剩余三条微博定时发出（配额已恢复）。",
            "_outcome_zh": "完成公开内容排期与核验。",
            "_contour_signature": "fixture-publishing-contour",
            "_request_topics": (),
            "_has_safe_assistant_outcome": True,
        }
        contour = {
            "date": day,
            "category": collaboration["category"],
            "request_zh": collaboration["_request_zh"],
            "request_en": (
                "Schedule the remaining three weibo posts now that quota is "
                "restored."
            ),
            "outcome_zh": collaboration["_outcome_zh"],
            "outcome_en": (
                "Completed public-content scheduling and verification."
            ),
            "completion_status": "completed",
            "pair_provenance": "assistant_result_summary",
        }
        contours = {"fixture-publishing-contour": contour}
        collaborations = {day: [collaboration]}
        empty = {"schema": importer.HISTORY_SCHEMA, "days": []}

        first = importer.merge_history(empty, collaborations, {}, [day], contours, [])
        self.assertNotEqual(self.serialized(first), self.serialized(empty))

        semantic_first = json.loads(self.serialized(first))
        policy.sanitize_history(semantic_first, identity_terms=())
        self.assertNotEqual(
            self.serialized(semantic_first),
            self.serialized(first),
        )
        preserved_residue = self.collaboration_residue(semantic_first)
        self.assertNotIn("配额", preserved_residue["request_zh"])
        self.assertNotIn("微博定时发出", preserved_residue["request_zh"])
        self.assertIn("排期与归档", preserved_residue["request_zh"])

        second = importer.merge_history(
            json.loads(self.serialized(semantic_first)),
            collaborations,
            {},
            [day],
            contours,
            [],
        )
        self.assertEqual(self.serialized(second), self.serialized(semantic_first))

        semantic_second = json.loads(self.serialized(second))
        policy.sanitize_history(semantic_second, identity_terms=())
        self.assertEqual(
            self.serialized(semantic_second),
            self.serialized(second),
        )

        third = importer.merge_history(
            json.loads(self.serialized(semantic_second)),
            collaborations,
            {},
            [day],
            contours,
            [],
        )
        self.assertEqual(self.serialized(third), self.serialized(semantic_second))

        # New evidence still regenerates from the contour (evidence pairing).
        changed = dict(collaboration)
        changed["evidence_count"] = 2
        refreshed = importer.merge_history(
            json.loads(self.serialized(semantic_second)),
            {day: [changed]},
            {},
            [day],
            contours,
            [],
        )
        self.assertNotEqual(
            self.serialized(refreshed),
            self.serialized(semantic_second),
        )
        refreshed_residue = self.collaboration_residue(refreshed)
        self.assertEqual(refreshed_residue["request_zh"], contour["request_zh"])
        self.assertEqual(refreshed_residue["evidence_count"], 2)

    def test_outcome_gate_rejects_private_domains_and_masks_unknown_names(self) -> None:
        self.assertTrue(
            importer.outcome_publication_eligible(
                "结论：界面结构已经修复，视觉证据与文字判断可以逐项对应。",
                "visual_production",
            )
        )
        for text, category in (
            ("结论：单股触发价已经确认。", "research_synthesis"),
            ("部署链路已经通过远程验证。", "code_development"),
            ("你的情绪结果已经整理。", "document_processing"),
            ("结论：系统边界已经确认。", "redacted_private"),
        ):
            self.assertFalse(importer.outcome_publication_eligible(text, category))
        sanitized = importer.sanitize_outcome_excerpt(
            "结论：Rodin 页面结构已经修复，并保留可验证的视觉证据与完整判断链条。",
            [],
            (),
        )
        self.assertNotIn("Rodin", sanitized)
        self.assertIn(importer.MASK, sanitized)

    def test_sanitizer_fails_closed_without_private_denylists(self) -> None:
        self.holdings.unlink()
        with self.assertRaises(ValueError):
            self.run_import(dry_run=True)


if __name__ == "__main__":
    unittest.main()
