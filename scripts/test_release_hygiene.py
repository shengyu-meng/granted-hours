#!/usr/bin/env python3
"""Release-scope guards for generated/private artifacts."""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseHygieneTests(unittest.TestCase):
    def test_generated_roots_are_ignored_as_directory_or_symlink_entries(self) -> None:
        for entry in (".pytest_cache", ".wrangler", "dist", "node_modules"):
            completed = subprocess.run(
                ["git", "check-ignore", "--quiet", entry],
                cwd=ROOT,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, entry)

    def test_publish_script_uses_allowlist_and_rejects_forbidden_staging(self) -> None:
        source = (ROOT / "scripts" / "publish_public_mirror.sh").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("git add .", source)
        self.assertIn("PUBLIC_ALLOWLIST", source)
        self.assertIn("git diff --cached --name-only", source)
        for forbidden_scope in (
            ".private",
            ".pytest_cache",
            ".wrangler",
            "node_modules",
            "dist",
            "*.db",
            "*.sqlite",
            "*.log",
            "/source/",
        ):
            self.assertIn(forbidden_scope, source)


if __name__ == "__main__":
    unittest.main()
