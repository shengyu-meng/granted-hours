#!/usr/bin/env python3
"""Subprocess coverage for privacy-sensitive production CLI write paths."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import import_timetable_pulses as pulses
import public_projection_privacy as privacy


ROOT = Path(__file__).resolve().parents[1]
TIMEZONE = ZoneInfo("Asia/Shanghai")


class ProductionCliPathTests(unittest.TestCase):
    def run_script(self, script: str, *arguments: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), *(str(value) for value in arguments)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    @staticmethod
    def write_denylist(path: Path, kind: str, terms: list[str]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "schema": privacy.PRIVATE_DENYLIST_SCHEMA,
                    "kind": kind,
                    "terms": terms,
                }
            ),
            encoding="utf-8",
        )

    def test_holdings_refresh_cli_writes_private_owner_only_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "portfolio.json"
            output = root / ".private" / "holdings-denylist.json"
            source.write_text(
                json.dumps(
                    {
                        "positions": [
                            {
                                "code": "SAFEQ",
                                "name": "Synthetic Qualified Holding",
                                "market": "US",
                                "qty": 2,
                                "qty_unknown": False,
                            }
                        ],
                        "watchlist": [{"code": "PUBLICQ"}],
                    }
                ),
                encoding="utf-8",
            )
            completed = self.run_script(
                "refresh_private_market_denylists.py",
                "--holdings-source",
                source,
                "--output",
                output,
            )
            document = json.loads(output.read_text(encoding="utf-8"))
            output_mode = os.stat(output).st_mode & 0o777

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "Refreshed private holdings denylist.")
        self.assertEqual(document["kind"], "holdings")
        self.assertNotIn("PUBLICQ", document["terms"])
        self.assertEqual(output_mode, 0o600)

    def test_market_refresh_cli_rewrites_only_direct_public_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            snapshot = root / "snapshot.json"
            state_db = root / "state.db"
            holdings = root / ".private" / "holdings.json"
            sources = root / ".private" / "sources.json"
            self.write_denylist(holdings, "holdings", ["HOLDQ"])
            self.write_denylist(sources, "self_media_sources", ["Source Studio"])
            snapshot.write_text(
                json.dumps(
                    {
                        "schema": pulses.PULSE_SNAPSHOT_SCHEMA,
                        "timezone": "Asia/Shanghai",
                        "source_file_count": 1,
                        "deduplicated_run_count": 1,
                        "observed_session_window_count": 0,
                        "days": [{"date": "2026-07-01", "pulses": []}],
                    }
                ),
                encoding="utf-8",
            )
            timestamp = datetime(2026, 7, 1, 21, 0, tzinfo=TIMEZONE).timestamp()
            with sqlite3.connect(state_db) as connection:
                connection.executescript(
                    """
                    CREATE TABLE sessions (
                        id TEXT PRIMARY KEY, source TEXT, model TEXT, title TEXT,
                        started_at REAL, ended_at REAL
                    );
                    CREATE TABLE messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT,
                        role TEXT, content TEXT, timestamp REAL, active INTEGER
                    );
                    """
                )
                connection.execute(
                    "INSERT INTO sessions VALUES (?, 'cron', '', 'U.S. market scan', ?, ?)",
                    ("synthetic-market-session", timestamp, timestamp + 180),
                )
                connection.execute(
                    "INSERT INTO messages(session_id, role, content, timestamp, active) "
                    "VALUES (?, 'assistant', ?, ?, 1)",
                    (
                        "synthetic-market-session",
                        "Source Studio reports PUBLICQ at $42.30, +3.1%, strong; HOLDQ position cost $19.20.",
                        timestamp + 179,
                    ),
                )
            completed = self.run_script(
                "import_timetable_pulses.py",
                "--refresh-markets-from-state",
                "--snapshot",
                snapshot,
                "--state-db",
                state_db,
                "--holdings-denylist",
                holdings,
                "--self-media-denylist",
                sources,
            )
            rewritten = json.loads(snapshot.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        public_copy = json.dumps(rewritten, ensure_ascii=False)
        self.assertIn("PUBLICQ", public_copy)
        self.assertIn("42.30", public_copy)
        self.assertNotIn("HOLDQ", public_copy)
        self.assertNotIn("Source Studio", public_copy)

    def test_full_receipt_market_reprojection_preserves_existing_reminder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "output" / "market-job"
            output.mkdir(parents=True)
            jobs = root / "jobs.json"
            days = root / "days.json"
            snapshot = root / "snapshot.json"
            holdings = root / ".private" / "holdings.json"
            sources = root / ".private" / "sources.json"
            self.write_denylist(holdings, "holdings", ["HOLDQ"])
            self.write_denylist(sources, "self_media_sources", ["Source Studio"])
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
            (output / "2026-07-01_21-00-00.md").write_text(
                "private prompt\n## Response\n"
                "Source Studio reports SAFEQ at $42.30, +3.1%, strong; "
                "HOLDQ position cost $19.20.",
                encoding="utf-8",
            )
            reminder = {
                "start": "08:00",
                "end": "08:01",
                "duration_minutes": 1,
                "execution_minutes": 1,
                "time_bucket": "morning",
                "category": "daily_reminder",
                "count": 1,
                "time_provenance": "observed_session_window",
                "summary_provenance": "semantic_public_projection",
                "summary_original": "保留原提醒 ████",
                "excerpt_original": "保留原提醒 ████",
                "summary_en": "Keep the existing reminder ████.",
                "excerpt_en": "Keep the existing reminder ████.",
                "redaction_count": 1,
                "projection_kind": "verbatim_redacted",
                "semantic_abstraction_count": 0,
            }
            snapshot.write_text(
                json.dumps(
                    {
                        "schema": pulses.PULSE_SNAPSHOT_SCHEMA,
                        "timezone": "Asia/Shanghai",
                        "source_file_count": 1,
                        "deduplicated_run_count": 1,
                        "observed_session_window_count": 1,
                        "days": [
                            {
                                "date": "2026-07-01",
                                "pulses": [
                                    reminder,
                                    {
                                        "start": "21:00",
                                        "end": "21:01",
                                        "duration_minutes": 1,
                                        "execution_minutes": 1,
                                        "time_bucket": "evening",
                                        "category": "us_market_scan",
                                        "count": 1,
                                        "time_provenance": "receipt_timestamp_estimate",
                                        "summary_provenance": "derived_public_safe",
                                        "summary_zh": "未形成公开级别结论；无额外公开主题。",
                                        "summary_en": "No public-level conclusion; no additional public theme.",
                                    },
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            completed = self.run_script(
                "import_timetable_pulses.py",
                "--reproject-markets-from-receipts",
                "--jobs",
                jobs,
                "--output-dir",
                root / "output",
                "--public-days",
                days,
                "--snapshot",
                snapshot,
                "--no-session-state",
                "--holdings-denylist",
                holdings,
                "--self-media-denylist",
                sources,
            )
            rewritten = json.loads(snapshot.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Market receipt re-projection: 1 replaced", completed.stdout)
        [rewritten_reminder] = [
            pulse
            for pulse in rewritten["days"][0]["pulses"]
            if pulse["category"] == "daily_reminder"
        ]
        self.assertEqual(rewritten_reminder, reminder)
        public_copy = json.dumps(rewritten, ensure_ascii=False)
        for expected in ("SAFEQ", "42.30", "+3.1%"):
            self.assertIn(expected, public_copy)
        for forbidden in (
            "HOLDQ",
            "Source Studio",
            "no additional public theme",
            "未形成公开级别结论",
        ):
            self.assertNotIn(forbidden, public_copy)

    def test_reminder_resanitization_cli_updates_snapshot_and_sidecar(self) -> None:
        source = "Source Studio reminder: HOLDQ at 24.60; continue calmly."
        translation = "Source Studio reminder: HOLDQ at 24.60; continue calmly."
        source_sha256 = hashlib.sha256(source.encode("utf-8")).hexdigest()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            snapshot = root / "snapshot.json"
            sidecar = root / "translations.json"
            holdings = root / ".private" / "holdings.json"
            sources = root / ".private" / "sources.json"
            self.write_denylist(holdings, "holdings", ["HOLDQ"])
            self.write_denylist(sources, "self_media_sources", ["Source Studio"])
            reminder = {
                "start": "08:00",
                "end": "08:01",
                "duration_minutes": 1,
                "execution_minutes": 1,
                "time_bucket": "morning",
                "category": "daily_reminder",
                "count": 1,
                "time_provenance": "observed_session_window",
                "summary_provenance": "semantic_public_projection",
                "summary_original": source,
                "excerpt_original": source,
                "summary_en": translation,
                "excerpt_en": translation,
                "redaction_count": 0,
                "projection_kind": "verbatim",
                "semantic_abstraction_count": 0,
            }
            snapshot.write_text(
                json.dumps(
                    {
                        "schema": pulses.PULSE_SNAPSHOT_SCHEMA,
                        "timezone": "Asia/Shanghai",
                        "source_file_count": 1,
                        "deduplicated_run_count": 1,
                        "observed_session_window_count": 1,
                        "days": [{"date": "2026-07-01", "pulses": [reminder]}],
                    }
                ),
                encoding="utf-8",
            )
            sidecar.write_text(
                json.dumps(
                    {
                        "schema": pulses.REMINDER_TRANSLATION_SCHEMA,
                        "translation_provenance": pulses.REMINDER_TRANSLATION_PROVENANCE,
                        "translations": {
                            source_sha256: {
                                "source_sha256": source_sha256,
                                "summary_en": translation,
                                "excerpt_en": translation,
                                "translation_provenance": pulses.REMINDER_TRANSLATION_PROVENANCE,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            completed = self.run_script(
                "import_timetable_pulses.py",
                "--resanitize-existing-reminders",
                "--snapshot",
                snapshot,
                "--reminder-translations",
                sidecar,
                "--holdings-denylist",
                holdings,
                "--self-media-denylist",
                sources,
            )
            rewritten = json.loads(snapshot.read_text(encoding="utf-8"))
            rewritten_sidecar = json.loads(sidecar.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        public_copy = json.dumps(rewritten, ensure_ascii=False)
        sidecar_copy = json.dumps(rewritten_sidecar, ensure_ascii=False)
        for private_term in ("HOLDQ", "Source Studio"):
            self.assertNotIn(private_term, public_copy)
            self.assertNotIn(private_term, sidecar_copy)
        [pulse] = rewritten["days"][0]["pulses"]
        self.assertEqual(
            pulse["summary_original"].count("████"),
            pulse["summary_en"].count("████"),
        )
        self.assertEqual(
            pulse["excerpt_original"].count("████"),
            pulse["excerpt_en"].count("████"),
        )

    def test_reminder_cli_mismatch_aborts_before_any_write(self) -> None:
        source = "Allow ████ to rest."
        source_sha256 = hashlib.sha256(source.encode("utf-8")).hexdigest()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            snapshot = root / "snapshot.json"
            sidecar = root / "translations.json"
            holdings = root / ".private" / "holdings.json"
            sources = root / ".private" / "sources.json"
            self.write_denylist(holdings, "holdings", ["UNUSEDH"])
            self.write_denylist(sources, "self_media_sources", ["Unused Source"])
            snapshot.write_text(
                json.dumps(
                    {
                        "schema": pulses.PULSE_SNAPSHOT_SCHEMA,
                        "timezone": "Asia/Shanghai",
                        "source_file_count": 1,
                        "deduplicated_run_count": 1,
                        "observed_session_window_count": 1,
                        "days": [
                            {
                                "date": "2026-07-01",
                                "pulses": [
                                    {
                                        "category": "daily_reminder",
                                        "summary_provenance": "semantic_public_projection",
                                        "summary_original": source,
                                        "excerpt_original": source,
                                        "summary_en": "Allow yourself to rest.",
                                        "excerpt_en": "Allow yourself to rest.",
                                        "redaction_count": 1,
                                        "projection_kind": "verbatim_redacted",
                                        "semantic_abstraction_count": 0,
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            sidecar.write_text(
                json.dumps(
                    {
                        "schema": pulses.REMINDER_TRANSLATION_SCHEMA,
                        "translation_provenance": pulses.REMINDER_TRANSLATION_PROVENANCE,
                        "translations": {
                            source_sha256: {
                                "source_sha256": source_sha256,
                                "summary_en": "Allow yourself to rest.",
                                "excerpt_en": "Allow yourself to rest.",
                                "translation_provenance": pulses.REMINDER_TRANSLATION_PROVENANCE,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            snapshot_before = snapshot.read_bytes()
            sidecar_before = sidecar.read_bytes()
            completed = self.run_script(
                "import_timetable_pulses.py",
                "--resanitize-existing-reminders",
                "--snapshot",
                snapshot,
                "--reminder-translations",
                sidecar,
                "--holdings-denylist",
                holdings,
                "--self-media-denylist",
                sources,
            )
            self.assertEqual(snapshot.read_bytes(), snapshot_before)
            self.assertEqual(sidecar.read_bytes(), sidecar_before)

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("summary mask parity mismatch", completed.stderr)

    def test_agent_import_cli_writes_observed_pathless_public_events(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            days = root / "days.json"
            history = root / "history.json"
            state_db = root / "state.db"
            days.write_text(json.dumps([{"date": "2026-07-01"}]), encoding="utf-8")
            history.write_text(
                json.dumps(
                    {
                        "schema": "granted-hours-timetable-history-v3",
                        "days": [
                            {
                                "date": "2026-07-01",
                                "provenance": "record_based",
                                "assigned_residues": [
                                    {
                                        "category": "system_maintenance",
                                        "en": "Verify a public health record",
                                        "zh": "核验公开健康记录",
                                        "redaction_status": "none",
                                        "redaction_count": 0,
                                        "source_kind": "daily_record",
                                        "faithfulness": "faithful_summary",
                                    }
                                ],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            timestamp = datetime(2026, 7, 1, 10, 7, tzinfo=TIMEZONE).timestamp()
            with sqlite3.connect(state_db) as connection:
                connection.executescript(
                    """
                    CREATE TABLE sessions (
                        id TEXT PRIMARY KEY, source TEXT, model TEXT, title TEXT,
                        started_at REAL, ended_at REAL
                    );
                    CREATE TABLE messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT,
                        role TEXT, content TEXT, timestamp REAL, active INTEGER
                    );
                    """
                )
                connection.execute(
                    "INSERT INTO sessions VALUES (?, 'cli', 'gpt-test', '', ?, ?)",
                    ("synthetic-agent-session", timestamp, timestamp + 125),
                )
                connection.executemany(
                    "INSERT INTO messages(session_id, role, content, timestamp, active) "
                    "VALUES (?, ?, ?, ?, 1)",
                    [
                        ("synthetic-agent-session", "user", "Implement private code.", timestamp + 1),
                        (
                            "synthetic-agent-session",
                            "assistant",
                            "Completed code implementation and review.",
                            timestamp + 124,
                        ),
                    ],
                )
            completed = self.run_script(
                "import_agent_events.py",
                "--state-db",
                state_db,
                "--days",
                days,
                "--history",
                history,
            )
            rewritten = json.loads(history.read_text(encoding="utf-8"))

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("code_development: events=1, dates=1", completed.stdout)
        public_copy = json.dumps(rewritten, ensure_ascii=False)
        forbidden_public_fragment = "evidence" + "_hash"
        self.assertNotIn(forbidden_public_fragment, public_copy)
        [agent] = [
            residue
            for residue in rewritten["days"][0]["assigned_residues"]
            if residue["source_kind"] == "agent_session"
        ]
        self.assertEqual((agent["start"], agent["end"]), ("10:07", "10:10"))
        self.assertEqual(agent["time_provenance"], "observed_session_window")


if __name__ == "__main__":
    unittest.main()
