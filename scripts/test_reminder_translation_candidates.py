#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import prepare_reminder_translation_candidates as candidates


class ReminderTranslationCandidateTests(unittest.TestCase):
    def test_candidate_masks_private_terms_and_rebuilds_excerpt(self) -> None:
        projection = {
            "summary_original": "研究 HOLDX 后，保留一个完整的公开句子。",
            "excerpt_original": "研究 HOLDX",
            "redaction_count": 0,
            "semantic_abstraction_count": 0,
        }
        result = candidates.sanitize_candidate(
            projection,
            holdings_terms=("HOLDX",),
            source_terms=(),
        )
        self.assertNotIn("HOLDX", json.dumps(result, ensure_ascii=False))
        self.assertIn("████", result["summary_original"])
        self.assertEqual(result["excerpt_original"], result["summary_original"])
        self.assertEqual(result["redaction_count"], 1)

    def test_private_writer_uses_mode_0600(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / ".private" / "candidates.json"
            candidates.write_private_json(output, {"candidates": []})
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_private_writer_rejects_public_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SystemExit):
                candidates.write_private_json(
                    Path(directory) / "candidates.json",
                    {"candidates": []},
                )


if __name__ == "__main__":
    unittest.main()
