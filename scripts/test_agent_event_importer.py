#!/usr/bin/env python3
"""Evidence and privacy tests for Codex/GPT/Claude/subagent backfill."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import import_agent_events as importer


TIMEZONE = ZoneInfo("Asia/Shanghai")


class AgentEventImporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.db_path = self.root / "state.db"
        self.days_path = self.root / "days.json"
        self.history_path = self.root / "history.json"
        self.days_path.write_text(
            json.dumps(
                [
                    {"date": "2026-07-01"},
                    {"date": "2026-07-02"},
                    {"date": "2026-07-03"},
                ]
            ),
            encoding="utf-8",
        )
        self.history_path.write_text(
            json.dumps(
                {
                    "schema": "granted-hours-timetable-history-v3",
                    "days": [
                        {
                            "date": day,
                            "provenance": "record_based",
                            "assigned_residues": [self.existing_residue()],
                        }
                        for day in ("2026-07-01", "2026-07-02", "2026-07-03")
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        with sqlite3.connect(self.db_path) as connection:
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
        self.add_session(
            "private-cli-session-001",
            "cli",
            "gpt-5.5",
            "2026-07-01 10:00:00",
            "Implement code and regression tests for ConfidentialProduct.",
            "Completed the implementation and review; focused tests PASS.",
        )
        self.add_session(
            "private-subagent-session-002",
            "subagent",
            "claude-4-opus",
            "2026-07-02 14:00:00",
            "Create a PPT deck, write the draft, and review PrivateCourse materials.",
            "Completed the presentation, writing, and editorial review.",
        )
        self.add_session(
            "private-subagent-session-003",
            "subagent",
            "gpt-5.6-sol",
            "2026-07-03 09:00:00",
            "Research primary evidence and audit the claims for PrivateClient.",
            "Research synthesis and evidence review completed with findings returned.",
        )
        self.add_session(
            "private-incomplete-session-004",
            "subagent",
            "gpt-5.6-sol",
            "2026-07-03 11:00:00",
            "Build a visual for an unfinished task.",
            None,
        )
        self.add_session(
            "private-outside-session-005",
            "cli",
            "gpt-5.5",
            "2026-07-04 10:00:00",
            "Implement code for an outside date.",
            "Completed implementation.",
        )
        self.add_session(
            "private-negated-session-006",
            "cli",
            "gpt-5.5",
            "2026-07-01 12:00:00",
            "Implement code and tests.",
            "The code was not completed; tests failed and work is still in progress.",
        )
        self.add_session(
            "private-unfinished-session-007",
            "subagent",
            "claude-4-opus",
            "2026-07-02 16:00:00",
            "Create and review a presentation.",
            "Completed the presentation review.",
            ended=False,
        )
        self.add_session(
            "private-quoted-session-008",
            "cli",
            "gpt-5.5",
            "2026-07-01 13:00:00",
            "Implement code and tests.",
            "The requested status word is 'completed'; coding and review remain in progress.",
        )
        self.add_session(
            "private-final-result-session-009",
            "cli",
            "gpt-5.5",
            "2026-07-02 17:00:00",
            "Implement code and review it.",
            "Completed code review.",
        )
        self.add_assistant_message(
            "private-final-result-session-009",
            "Still working; the implementation is not completed.",
            "2026-07-02 17:04:59",
        )
        self.add_session(
            "private-spoof-session-010",
            "subagent",
            "neutral-model",
            "2026-07-03 12:00:00",
            "Research and review evidence.",
            "Completed research and evidence review. Codex, GPT, and Claude are quoted names.",
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

    def add_session(
        self,
        session_id: str,
        source: str,
        model: str,
        started: str,
        task: str,
        result: str | None,
        *,
        ended: bool = True,
        duration_seconds: int = 300,
    ) -> None:
        timestamp = datetime.strptime(started, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=TIMEZONE
        ).timestamp()
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, NULL, ?, ?)",
                (
                    session_id,
                    source,
                    model,
                    timestamp,
                    timestamp + duration_seconds if ended else None,
                ),
            )
            connection.execute(
                "INSERT INTO messages(session_id, role, content, timestamp, active) "
                "VALUES (?, 'user', ?, ?, 1)",
                (session_id, task, timestamp + 1),
            )
            if result is not None:
                connection.execute(
                    "INSERT INTO messages(session_id, role, content, timestamp, active) "
                    "VALUES (?, 'assistant', ?, ?, 1)",
                    (session_id, result, timestamp + 299),
                )

    def add_assistant_message(
        self,
        session_id: str,
        result: str,
        timestamp_text: str,
    ) -> None:
        timestamp = datetime.strptime(
            timestamp_text,
            "%Y-%m-%d %H:%M:%S",
        ).replace(tzinfo=TIMEZONE).timestamp()
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "INSERT INTO messages(session_id, role, content, timestamp, active) "
                "VALUES (?, 'assistant', ?, ?, 1)",
                (session_id, result, timestamp),
            )

    def test_only_completed_direct_evidence_dates_are_backfilled(self) -> None:
        result = importer.import_agent_events(
            state_db_path=self.db_path,
            days_path=self.days_path,
            history_path=self.history_path,
            dry_run=True,
        )

        self.assertEqual(set(result["event_dates"]), {
            "2026-07-01",
            "2026-07-02",
            "2026-07-03",
        })
        self.assertEqual(result["category_counts"]["code_development"], 1)
        self.assertEqual(result["category_counts"]["document_processing"], 1)
        self.assertEqual(result["category_counts"]["research_synthesis"], 2)
        self.assertNotIn("visual_production", result["category_counts"])

        serialized = json.dumps(result["history"], ensure_ascii=False)
        for forbidden in (
            "private-cli-session-001",
            "private-subagent-session-002",
            "private-subagent-session-003",
            "private-spoof-session-010",
            "ConfidentialProduct",
            "PrivateCourse",
            "PrivateClient",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_events_are_foreground_ready_with_observed_times_and_no_public_hashes(self) -> None:
        result = importer.import_agent_events(
            state_db_path=self.db_path,
            days_path=self.days_path,
            history_path=self.history_path,
            dry_run=True,
        )
        residues = [
            residue
            for day in result["history"]["days"]
            for residue in day["assigned_residues"]
            if residue["source_kind"] == "agent_session"
        ]
        self.assertEqual(len(residues), 4)
        for residue in residues:
            self.assertEqual(residue["redaction_status"], "partial")
            self.assertEqual(residue["redaction_count"], 1)
            self.assertEqual(residue["en"].count("████"), 1)
            self.assertEqual(residue["zh"].count("████"), 1)
            self.assertEqual(residue["faithfulness"], "faithful_summary")
            self.assertGreaterEqual(residue["evidence_count"], 1)
            self.assertTrue(residue["agent_labels"])
            self.assertEqual(residue["time_provenance"], "observed_session_window")
            self.assertRegex(residue["start"], r"^\d{2}:\d{2}$")
            self.assertRegex(residue["end"], r"^(?:\d{2}:\d{2}|24:00)$")

        serialized = json.dumps(result["history"], ensure_ascii=False)
        forbidden_public_fragment = "evidence" + "_hash"
        self.assertNotIn(forbidden_public_fragment, serialized)

        code = next(item for item in residues if item["category"] == "code_development")
        self.assertIn("Codex", code["en"])
        self.assertIn("GPT", code["en"])
        document = next(
            item for item in residues if item["category"] == "document_processing"
        )
        self.assertIn("Claude", document["en"])
        self.assertIn("subagent", document["en"])
        self.assertRegex(document["en"], r"PPT|presentation")
        self.assertRegex(document["en"], r"writing|review")
        spoof = next(
            item
            for item in residues
            if item["agent_labels"] == ["subagent"]
            and item["category"] == "research_synthesis"
        )
        self.assertNotIn("Codex", spoof["en"])
        self.assertNotIn("GPT", spoof["en"])
        self.assertNotIn("Claude", spoof["en"])

    def test_invalid_or_unsafe_observed_windows_are_omitted(self) -> None:
        public_dates = ["2026-07-01", "2026-07-02", "2026-07-03"]
        baseline = importer.collect_agent_events(self.db_path, public_dates)
        self.add_session(
            "private-overlong-session",
            "cli",
            "gpt-5.5",
            "2026-07-01 14:00:00",
            "Implement code.",
            "Completed code implementation.",
            duration_seconds=7 * 60 * 60,
        )
        self.add_session(
            "private-cross-day-session",
            "cli",
            "gpt-5.5",
            "2026-07-01 23:59:00",
            "Implement code.",
            "Completed code implementation.",
            duration_seconds=120,
        )
        self.assertEqual(
            importer.collect_agent_events(self.db_path, public_dates),
            baseline,
        )

    def test_cli_failure_is_fixed_and_pathless(self) -> None:
        missing = self.root / "private-source-location" / "private-state.db"
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(importer.__file__)),
                "--state-db",
                str(missing),
                "--days",
                str(self.days_path),
                "--history",
                str(self.history_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        output = completed.stdout + completed.stderr
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(output.strip(), "Agent event import failed.")
        self.assertNotIn(str(missing), output)

    def test_reimport_is_deterministic_and_does_not_duplicate_agent_events(self) -> None:
        first = importer.import_agent_events(
            state_db_path=self.db_path,
            days_path=self.days_path,
            history_path=self.history_path,
            dry_run=False,
        )
        first_bytes = self.history_path.read_bytes()
        second = importer.import_agent_events(
            state_db_path=self.db_path,
            days_path=self.days_path,
            history_path=self.history_path,
            dry_run=False,
        )
        self.assertEqual(self.history_path.read_bytes(), first_bytes)
        self.assertTrue(first["changed"])
        self.assertFalse(second["changed"])


if __name__ == "__main__":
    unittest.main()
