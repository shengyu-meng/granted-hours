#!/usr/bin/env python3
"""Coverage, lineage, privacy, and idempotence tests for dialogue imports."""
from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import import_collaboration_events as importer


TIMEZONE = ZoneInfo("Asia/Shanghai")


class CollaborationEventImporterTests(unittest.TestCase):
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
