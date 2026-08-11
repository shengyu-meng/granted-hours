#!/usr/bin/env python3
"""Focused tests for the public mirror safety boundary."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_public_safety as safety


class PublicSafetyTests(unittest.TestCase):
    def scan(self, files: dict[str, str]) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            private_dir = root / ".private"
            private_dir.mkdir()
            (private_dir / "identity-denylist.json").write_text(
                json.dumps(
                    {
                        "schema": "granted-hours-private-denylist-v1",
                        "kind": "identities",
                        "terms": ["Synthetic Private Person", "Simon Private Person"],
                    }
                ),
                encoding="utf-8",
            )
            metadata_dir = root / "metadata"
            metadata_dir.mkdir()
            (metadata_dir / "public-identity-allowlist.json").write_text(
                json.dumps(
                    {
                        "schema": "granted-hours-public-identity-allowlist-v1",
                        "authorization": "explicit_owner_authorization_2026-08-11",
                        "names": ["Simon", "Simon的白日梦", "Simon Meng"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = safety.main(root)
            return result, output.getvalue()

    def test_authentic_narrative_language_is_not_treated_as_a_secret(self) -> None:
        result, output = self.scan({
            "public.txt": (
                "黑昼提醒：今天看看源泉，也可以复核持仓和仓位。"
                "Hermes Agent 的工作流是今天真实发生的一部分。"
            )
        })
        self.assertEqual(result, 0, output)

    def test_owner_authorized_public_names_are_allowed_without_exempting_context(self) -> None:
        public_names = ("Simon的白日梦", "Simon Meng", "Simon")
        sanctioned = safety.scrub_allowed_tokens(
            '"request_zh":"Simon 让我修复日历","request_en":"Simon asked me to repair it"',
            public_names,
        )
        self.assertNotIn("Simon", sanctioned)
        self.assertIn("让我修复日历", sanctioned)
        self.assertIn("asked me to repair it", sanctioned)
        self.assertNotIn(
            "Simon",
            safety.scrub_allowed_tokens(
                "Simon Meng / Simon的白日梦 / Simon owns a public archive",
                public_names,
            ),
        )

        fake_secret = "sk-" + "B" * 24
        result, output = self.scan({"public.txt": f"Simon {fake_secret}"})
        self.assertEqual(result, 1)
        self.assertIn("openai_key", output)

        identity_result, identity_output = self.scan({
            "public.txt": "Simon Private Person",
        })
        self.assertEqual(identity_result, 1)
        self.assertIn("private_identity", identity_output)

    def test_public_url_does_not_exempt_a_secret_on_the_same_line(self) -> None:
        fake_secret = "sk-" + "A" * 24
        result, output = self.scan({
            "public.txt": (
                "https://shengyu-meng.github.io/granted-hours/ " + fake_secret
            )
        })
        self.assertEqual(result, 1)
        self.assertIn("openai_key", output)

    def test_prose_prompt_is_allowed_but_serialized_private_key_is_not(self) -> None:
        prose_result, prose_output = self.scan({
            "metadata/timetable-pulses.json": '{"summary_original":"把 prompt 写清楚"}'
        })
        self.assertEqual(prose_result, 0, prose_output)

        key_result, key_output = self.scan({
            "metadata/timetable-pulses.json": '{"prompt":"private scheduler text"}'
        })
        self.assertEqual(key_result, 1)
        self.assertIn("cron_private_identifier", key_output)

    def test_private_input_adapters_do_not_hide_public_artifact_findings(self) -> None:
        result, output = self.scan({
            "scripts/import_agent_events.py": "DEFAULT = '/Users/private/.hermes/state.db'",
            "metadata/timetable-pulses.json": '{"summary":"/Users/private/leak"}',
        })
        self.assertEqual(result, 1)
        self.assertIn("metadata/timetable-pulses.json", output)
        self.assertNotIn("scripts/import_agent_events.py", output)

    def test_public_artwork_brief_metaphor_is_not_private_context(self) -> None:
        result, output = self.scan({
            "src/timetable/timetable-data.js": (
                'const timetableDataSource={"brief_zh":"崩溃始于系统没有更小的诚实形状",'
                '"brief_en":"The work refuses escape as a default."};'
            ),
            "docs/timetable/assets/index-test.js": (
                'const x={"brief_zh":"不是逃避真相，而是保留不可见的边界"};'
            ),
        })
        self.assertEqual(result, 0, output)

    def test_private_context_outside_artwork_brief_still_fails(self) -> None:
        result, output = self.scan({
            "src/timetable/timetable-data.js": (
                '{"brief_zh":"作品把崩溃画成系统隐喻",'
                '"note_zh":"记录了具体情绪状态"}'
            ),
        })
        self.assertEqual(result, 1)
        self.assertIn("health_or_emotional_state", output)


if __name__ == "__main__":
    unittest.main()
