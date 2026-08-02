#!/usr/bin/env python3
"""Focused tests for public dialogue-residue upserts."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_timetable_data as builder
import upsert_dialogue_residues as upsert


class FailingWriter:
    """A context-managed descriptor owner that fails on its first write."""

    def __init__(self, descriptor: int) -> None:
        self.descriptor = descriptor

    def __enter__(self) -> "FailingWriter":
        return self

    def __exit__(self, *unused: object) -> None:
        os.close(self.descriptor)

    def write(self, value: str) -> int:
        os.write(self.descriptor, value[:8].encode("utf-8"))
        raise OSError("simulated write failure")


def public_residue(index: int = 1) -> dict:
    return {
        "category": "code_development" if index % 2 else "research_synthesis",
        "en": f"Refined generic public calendar behavior {index}.",
        "zh": f"优化通用公共日历行为 {index}。",
    }


def rich_residue(index: int = 1) -> dict:
    return {
        **public_residue(index),
        "redaction_status": "none",
        "redaction_count": 0,
        "source_kind": "daily_record",
        "faithfulness": "faithful_summary",
    }


def input_document(day_date: str, count: int = 2) -> dict:
    return {
        "schema": upsert.INPUT_SCHEMA,
        "date": day_date,
        "provenance": "dialogue_based",
        "assigned_residues": [
            public_residue(index)
            for index in range(1, count + 1)
        ],
    }


class DialogueResidueUpsertTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)
        self.history_path = self.directory / "history.json"
        self.days_path = self.directory / "days.json"
        self.input_path = self.directory / "input.json"
        self.entity_detector_path = self.directory / "fake-entity-detector"
        self.history_path.write_text(
            json.dumps(
                {
                    "schema": upsert.HISTORY_SCHEMA,
                    "note": {"en": "preserve", "zh": "保留"},
                    "days": [
                        {
                            "date": "2026-07-29",
                            "provenance": "record_based",
                            "assigned_residues": [rich_residue(9)],
                        },
                        {
                            "date": "2026-07-31",
                            "provenance": "record_based",
                            "assigned_residues": [rich_residue(31)],
                        },
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.days_path.write_text(
            json.dumps(
                [
                    {"date": "2026-07-29"},
                    {"date": "2026-07-30"},
                    {"date": "2026-07-31"},
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.write_fake_entity_detector("clean")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_input(self, data: dict) -> None:
        self.input_path.write_text(
            json.dumps(data, ensure_ascii=False),
            encoding="utf-8",
        )

    def write_fake_entity_detector(self, mode: str) -> None:
        self.entity_detector_path.write_text(
            f"""#!/usr/bin/env python3
import json
import sys

mode = {mode!r}
if mode == "failure":
    sys.exit(7)
if mode == "malformed-json":
    print("not-json")
    sys.exit(0)

texts = json.load(sys.stdin)
if not isinstance(texts, list):
    sys.exit(8)
if mode == "require-four-clean" and len(texts) != 4:
    sys.exit(9)
if mode == "wrong-shape":
    json.dump({{"PersonalName": [], "OrganizationName": []}}, sys.stdout)
    sys.exit(0)

results = [
    {{"PersonalName": [], "OrganizationName": []}}
    for _ in texts
]
if mode == "person":
    results[0]["PersonalName"] = ["detected"]
if mode == "organization":
    results[-1]["OrganizationName"] = ["detected"]
json.dump(results, sys.stdout)
""",
            encoding="utf-8",
        )
        self.entity_detector_path.chmod(0o755)

    def run_upsert(self) -> bool:
        return upsert.upsert_dialogue_residues(
            self.input_path,
            history_path=self.history_path,
            days_path=self.days_path,
            entity_detector_path=self.entity_detector_path,
        )

    def test_accepts_valid_counts_two_and_six(self) -> None:
        for count in (2, 6):
            with self.subTest(count=count):
                data = input_document("2026-07-30", count)
                _, provenance, residues = upsert.validate_input(data)
                self.assertEqual(provenance, "dialogue_based")
                self.assertEqual(len(residues), count)
                self.assertTrue(all(set(item) == upsert.OUTPUT_RESIDUE_KEYS for item in residues))

    def test_rejects_counts_one_and_seven(self) -> None:
        for count in (1, 7):
            with self.subTest(count=count):
                with self.assertRaisesRegex(ValueError, "2-6"):
                    upsert.validate_input(input_document("2026-07-30", count))

    def test_rejects_top_level_and_residue_extra_fields(self) -> None:
        top_extra = {**input_document("2026-07-30"), "source": "private"}
        with self.assertRaisesRegex(ValueError, "exactly"):
            upsert.validate_input(top_extra)

        residue_extra = input_document("2026-07-30")
        residue_extra["assigned_residues"][0]["session_id"] = "private"
        with self.assertRaisesRegex(ValueError, "exactly"):
            upsert.validate_input(residue_extra)

    def test_rejects_bad_nonexistent_and_absent_dates(self) -> None:
        for day_date in ("2026/07/30", "2026-02-30"):
            with self.subTest(day_date=day_date):
                with self.assertRaises(ValueError):
                    upsert.validate_input(input_document(day_date))

        self.write_input(input_document("2026-07-28"))
        with self.assertRaisesRegex(ValueError, "not found"):
            self.run_upsert()

    def test_rejects_bad_category(self) -> None:
        data = input_document("2026-07-30")
        data["assigned_residues"][0]["category"] = "invented_category"
        with self.assertRaisesRegex(ValueError, "unknown category"):
            upsert.validate_input(data)

    def test_rejects_adversarial_private_identifiers_and_excluded_scope(self) -> None:
        fake_authorization_value = "".join(["not", "-", "a", "-", "credential"])
        fake_phone = "".join(["+86", "138", "1234", "5678"])
        fake_mixed_ids = [
            "".join(parts)
            for parts in (
                ("a", "1", "b", "2"),
                ("ab", "-", "1", "c"),
                ("x", "_", "7", "z"),
            )
        ]
        unsafe_examples = [
            "Contact person@example.com for the result.",
            f"Call {fake_phone} for the result.",
            "Call (415) 555-0123 for the result.",
            "Read https://example.com/private for the result.",
            "Read example.com/private for the result.",
            "Read /Users/person/private/report.json for the result.",
            "Read /home/person/private/report.json for the result.",
            "Read /var/tmp/report.json for the result.",
            "Read /private/tmp/report.json for the result.",
            "Read /Volumes/private/report.json for the result.",
            "Read /tmp/report.json for the result.",
            "Read /etc/passwd for the result.",
            "Read /opt/project/report.json for the result.",
            "Read path=/Users/person/private/report.json for the result.",
            "Read path:/Users/person/private/report.json for the result.",
            "Read file:///tmp/report.json for the result.",
            r"Read C:\Users\person\report.json for the result.",
            r"Read D:\work\private\report.json for the result.",
            "Read reports/private.json for the result.",
            "Read reports/private for the result.",
            "Read alpha/beta for the result.",
            r"Read alpha\beta for the result.",
            r"Read \\server\share\report.json for the result.",
            "Read //server/share/report for the result.",
            "Read $HOME for the result.",
            "Read ${HOME} for the result.",
            "Read %USERPROFILE% for the result.",
            "Read $HOME/private/report.json for the result.",
            r"Read %USERPROFILE%\private\report.json for the result.",
            "Read ~/private/report.json for the result.",
            "Read ./private/report.json for the result.",
            "Read ../private/report.json for the result.",
            "Updated account ID 1234 for the result.",
            "Processed reference 1234567 for the result.",
            "Processed reference 1234567890 for the result.",
            "Processed 123e4567-e89b-12d3-a456-426614174000 for the result.",
            "Processed deadbeefdeadbeef for the result.",
            "Processed abcdefghijklmnop12345678 for the result.",
            "Processed " + "42b17xyz" + " for the result.",
            "Processed opaque id " + "42b17xyz" + " for the result.",
            "Rotated " + "AKIA" + "A" * 16 + " for the result.",
            "Rotated " + "eyJ" + "a" * 8 + "." + "b" * 8 + "." + "c" * 8 + " for the result.",
            "Saw -----BEGIN " + "PRIVATE KEY----- in the result.",
            "Rotated " + "ghp_" + "a" * 16 + " for the result.",
            "Rotated " + "github_pat_" + "a" * 16 + " for the result.",
            "Rotated " + "sk-" + "a" * 16 + " for the result.",
            "Rotated token=abcdefghijklmnop for the result.",
            "Rotated password=abcdefghijklmnop for the result.",
            "Rotated secret=abcdefghijklmnop for the result.",
            "Rotated secret：abcdefghijklmnop for the result.",
            "Used Authorization: Bearer " + "a" * 24 + " for the result.",
            "Used Authorization=" + fake_authorization_value + " for the result.",
            "Used Bearer " + "b" * 24 + " for the result.",
            "Used Basic:" + "c" * 24 + " for the result.",
            "Used Digest " + "d" * 24 + " for the result.",
            "Used Digest:" + "e" * 24 + " for the result.",
            "Used Token " + "f" * 24 + " for the result.",
            "Used Token:" + "g" * 24 + " for the result.",
            "Contact @private_handle for the result.",
            "Reviewed portfolio holdings for the result.",
            "Reviewed account positions for the result.",
            "Reviewed ticker $AAPL for the result.",
            "Reviewed NASDAQ:AAPL for the result.",
            "Reviewed HK:0700 for the result.",
            "Reviewed 0700.HK for the result.",
            "Reviewed AAPL.US for the result.",
            "Reviewed stock 600519 for the result.",
            "Reviewed stock tsla for the result.",
            "Reviewed investment 0700 for the result.",
            "Reviewed investment 12345 for the result.",
            "Reviewed market 123456 for the result.",
            "Reviewed nasdaq:tsla for the result.",
            "Reviewed 0700.hk for the result.",
            "Reviewed TSLA for the result.",
            "Reviewed DB stock performance for the result.",
            "Reviewed the Hermes agent state for the result.",
            "Reviewed OpenClaw private operations for the result.",
            "Reviewed spouse activity for the result.",
            "Reviewed wife activity for the result.",
            "Reviewed husband activity for the result.",
            "Reviewed 配偶 activity for the result.",
            "Reviewed 妻子 activity for the result.",
            "Reviewed 丈夫 activity for the result.",
            "Reviewed Feishu notes for the result.",
            "Reviewed 飞书 notes for the result.",
            "Reviewed F notes for the result.",
            "Reviewed group notes for the result.",
            "Reviewed chat notes for the result.",
            "Reviewed channel notes for the result.",
            "Reviewed topic notes for the result.",
            "Reviewed 群聊 notes for the result.",
            "Reviewed 频道 notes for the result.",
            "Reviewed 话题 notes for the result.",
            "Reviewed MBA course notes for the result.",
            "Reviewed school notes for the result.",
            "Reviewed university notes for the result.",
            "Reviewed 学校 notes for the result.",
            "Reviewed 大学 notes for the result.",
            "Reviewed 持仓 notes for the result.",
            "Reviewed 账户 notes for the result.",
            *[
                f"Processed {fake_mixed_id} for the result."
                for fake_mixed_id in fake_mixed_ids
            ],
        ]
        for unsafe_text in unsafe_examples:
            with self.subTest(unsafe_text=unsafe_text):
                data = input_document("2026-07-30")
                data["assigned_residues"][0]["en"] = unsafe_text
                with self.assertRaises(ValueError):
                    upsert.validate_input(data)

    def test_vanadium_titanium_continuous_word_is_redacted(self) -> None:
        data = input_document("2026-07-30")
        data["assigned_residues"][0]["en"] = "Researched 钒钛 material."
        data["assigned_residues"][0]["zh"] = "研发钒钛新材料"
        residues = upsert.validate_input(data)[2]
        self.assertEqual(residues[0]["en"], "Researched ████ material.")
        self.assertEqual(residues[0]["zh"], "研发████新材料")
        self.assertEqual(residues[0]["redaction_status"], "partial")
        self.assertEqual(residues[0]["redaction_count"], 1)

        allowed_examples = ("钛金属", "钒电池", "vanadium", "titanium")
        for allowed_text in allowed_examples:
            with self.subTest(allowed_text=allowed_text):
                allowed = input_document("2026-07-30")
                field = "zh" if any("\u4e00" <= char <= "\u9fff" for char in allowed_text) else "en"
                allowed["assigned_residues"][0][field] = allowed_text
                validated = upsert.validate_input(allowed)[2][0]
                self.assertEqual(validated[field], allowed_text)
                self.assertEqual(validated["redaction_status"], "none")
                self.assertEqual(validated["redaction_count"], 0)

    def test_tight_technical_acronym_allowlist_remains_public_safe(self) -> None:
        data = input_document("2026-07-30")
        data["assigned_residues"][0]["en"] = (
            "Refined API JSON UI behavior with CI QA checks."
        )
        _, _, residues = upsert.validate_input(data)
        self.assertEqual(len(residues), 2)

    def test_entity_detector_batches_english_and_chinese_and_clean_passes(self) -> None:
        self.write_fake_entity_detector("require-four-clean")
        self.write_input(input_document("2026-07-30"))
        self.assertTrue(self.run_upsert())

    def test_entity_detector_rejects_person_and_organization(self) -> None:
        self.write_input(input_document("2026-07-30"))
        original_history = self.history_path.read_bytes()
        for mode in ("person", "organization"):
            with self.subTest(mode=mode):
                self.write_fake_entity_detector(mode)
                with self.assertRaisesRegex(
                    ValueError,
                    "personal or organization name",
                ):
                    self.run_upsert()
                self.assertEqual(self.history_path.read_bytes(), original_history)

    def test_entity_detector_failure_and_malformed_output_fail_closed(self) -> None:
        self.write_input(input_document("2026-07-30"))
        original_history = self.history_path.read_bytes()
        for mode in ("failure", "malformed-json", "wrong-shape"):
            with self.subTest(mode=mode):
                self.write_fake_entity_detector(mode)
                with self.assertRaisesRegex(ValueError, "detector"):
                    self.run_upsert()
                self.assertEqual(self.history_path.read_bytes(), original_history)

    def test_mask_counts_must_match_between_languages(self) -> None:
        valid = input_document("2026-07-30")
        valid["assigned_residues"][0]["en"] = "Refined ████ public navigation."
        valid["assigned_residues"][0]["zh"] = "优化 ████ 公共导航。"
        residues = upsert.validate_input(valid)[2]
        self.assertEqual(residues[0]["redaction_status"], "partial")
        self.assertEqual(residues[0]["redaction_count"], 1)

        invalid = input_document("2026-07-30")
        invalid["assigned_residues"][0]["en"] = "Refined ████ public navigation."
        with self.assertRaisesRegex(ValueError, "mask counts"):
            upsert.validate_input(invalid)

    def test_idempotent_rerun_is_byte_for_byte(self) -> None:
        self.write_input(input_document("2026-07-30"))
        self.assertTrue(self.run_upsert())
        first_bytes = self.history_path.read_bytes()
        self.assertFalse(self.run_upsert())
        self.assertEqual(self.history_path.read_bytes(), first_bytes)

    def test_atomic_replace_failure_preserves_history_and_cleans_temp(self) -> None:
        self.write_input(input_document("2026-07-30"))
        original_history = self.history_path.read_bytes()

        with mock.patch.object(
            upsert.os,
            "replace",
            side_effect=OSError("simulated replace failure"),
        ):
            with self.assertRaises(OSError):
                self.run_upsert()

        self.assertEqual(self.history_path.read_bytes(), original_history)
        self.assertEqual(list(self.directory.glob(".history.json.*.tmp")), [])

    def test_atomic_write_failure_preserves_history_and_cleans_temp(self) -> None:
        self.write_input(input_document("2026-07-30"))
        original_history = self.history_path.read_bytes()

        def failing_fdopen(descriptor: int, *args: object, **kwargs: object) -> FailingWriter:
            return FailingWriter(descriptor)

        with mock.patch.object(upsert.os, "fdopen", side_effect=failing_fdopen):
            with self.assertRaises(OSError):
                self.run_upsert()

        self.assertEqual(self.history_path.read_bytes(), original_history)
        self.assertEqual(list(self.directory.glob(".history.json.*.tmp")), [])

    def test_atomic_write_preserves_existing_regular_file_mode(self) -> None:
        self.history_path.chmod(0o640)
        self.write_input(input_document("2026-07-30"))

        self.assertTrue(self.run_upsert())

        self.assertEqual(self.history_path.stat().st_mode & 0o777, 0o640)

    def test_atomic_write_replaces_symlink_without_touching_target(self) -> None:
        self.write_input(input_document("2026-07-30"))
        trap_path = self.directory / "trap-history.json"
        trap_bytes = self.history_path.read_bytes()
        trap_path.write_bytes(trap_bytes)
        self.history_path.unlink()
        self.history_path.symlink_to(trap_path)

        self.assertTrue(self.run_upsert())

        self.assertEqual(trap_path.read_bytes(), trap_bytes)
        self.assertFalse(self.history_path.is_symlink())
        self.assertTrue(self.history_path.is_file())
        self.assertEqual(self.history_path.stat().st_mode & 0o777, 0o644)

    def test_replacement_preserves_document_and_sorts_dates(self) -> None:
        self.write_input(input_document("2026-07-30"))
        self.assertTrue(self.run_upsert())
        first = json.loads(self.history_path.read_text(encoding="utf-8"))
        self.assertEqual(first["note"], {"en": "preserve", "zh": "保留"})
        self.assertEqual(
            [entry["date"] for entry in first["days"]],
            ["2026-07-29", "2026-07-30", "2026-07-31"],
        )

        replacement = input_document("2026-07-30")
        replacement["assigned_residues"].reverse()
        self.write_input(replacement)
        self.assertTrue(self.run_upsert())
        second = json.loads(self.history_path.read_text(encoding="utf-8"))
        replaced = next(entry for entry in second["days"] if entry["date"] == "2026-07-30")
        self.assertEqual(
            [item["en"] for item in replaced["assigned_residues"]],
            [item["en"] for item in replacement["assigned_residues"]],
        )

    def test_builder_accepts_output_and_emits_dialogue_provenance(self) -> None:
        self.write_input(input_document("2026-07-30"))
        self.run_upsert()
        loaded = builder.load_history(self.history_path)
        self.assertEqual(loaded["2026-07-30"]["provenance"], "dialogue_based")
        self.assertEqual(len(loaded["2026-07-30"]["assigned_residues"]), 2)

    def test_output_serializes_no_source_metadata(self) -> None:
        self.write_input(input_document("2026-07-30"))
        self.run_upsert()
        document = json.loads(self.history_path.read_text(encoding="utf-8"))
        entry = next(item for item in document["days"] if item["date"] == "2026-07-30")
        self.assertEqual(set(entry), {"date", "provenance", "assigned_residues"})
        self.assertTrue(
            all(set(residue) == upsert.OUTPUT_RESIDUE_KEYS for residue in entry["assigned_residues"])
        )
        serialized_entry = json.dumps(entry, ensure_ascii=False).lower()
        for forbidden in ("source_metadata", "session_id", "message_id", "chat_id"):
            self.assertNotIn(forbidden, serialized_entry)

    def test_cli_dry_run_uses_fixed_default_detector_and_only_temp_files(self) -> None:
        self.write_input(input_document("2026-07-30"))
        original_history = self.history_path.read_bytes()
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            mock.patch.object(upsert, "DEFAULT_ENTITY_DETECTOR", self.entity_detector_path),
            mock.patch.object(
                sys,
                "argv",
                [
                    str(Path(upsert.__file__)),
                    "--input",
                    str(self.input_path),
                    "--history",
                    str(self.history_path),
                    "--days",
                    str(self.days_path),
                    "--dry-run",
                ],
            ),
            mock.patch("sys.stdout", stdout),
            mock.patch("sys.stderr", stderr),
        ):
            return_code = upsert.main()

        self.assertEqual(return_code, 0, stderr.getvalue())
        self.assertEqual(self.history_path.read_bytes(), original_history)
        self.assertNotIn("PersonalName", stdout.getvalue())
        self.assertNotIn("OrganizationName", stdout.getvalue())

    def test_cli_rejects_entity_detector_override(self) -> None:
        stderr = io.StringIO()
        with (
            mock.patch.object(
                sys,
                "argv",
                [
                    str(Path(upsert.__file__)),
                "--input",
                str(self.input_path),
                "--entity-detector",
                str(self.entity_detector_path),
                ],
            ),
            mock.patch("sys.stderr", stderr),
            self.assertRaises(SystemExit) as raised,
        ):
            upsert.parse_args()
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
