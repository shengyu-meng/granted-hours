#!/usr/bin/env python3
"""Public-only Flash import and additive timetable projection contracts."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import build_timetable_data as builder
import import_yesterday_flash as importer


class YesterdayFlashTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "worktree"
        self.source = Path(self.temporary.name) / "public"
        self.day = "2026-10-31"
        self.folder = self.source / self.day
        self.folder.mkdir(parents=True)
        self.manifest = {
            "source_date": "2026-10-30",
            "crystallization_day": self.day,
            "picked_title": "留下",
            "embedded_work": "index.html",
            "text_layer": "text-layer.md",
            "note": f"{self.day}-note.md",
            "not_free_roam": True,
        }
        self.files = {
            "index.html": "<!doctype html><html><body>留下 / Remain</body></html>",
            "text-layer.md": "# 昨日闪光 / Yesterday's Flash\n\n留下 / Remain\n",
            f"{self.day}-note.md": f"# 留下 / Remain\n\n- **Source Day / 源日**: 2026-10-30\n- **Crystallization Day / 结晶日**: {self.day}\n",
            "manifest.json": json.dumps(self.manifest, ensure_ascii=False),
        }
        for filename, text in self.files.items():
            (self.folder / filename).write_text(text, encoding="utf-8")

    def import_work(self):
        return importer.import_work(self.day, self.source, self.root)

    def test_allowlist_mirrors_and_idempotence_preserve_autonomous_work(self):
        autonomous = self.root / "docs/archive/2026/10/2026-10-31/live/index.html"
        autonomous.parent.mkdir(parents=True)
        autonomous.write_text("autonomous stays", encoding="utf-8")
        (self.folder / "private-packet.json").write_text("not public", encoding="utf-8")
        entry = self.import_work()
        self.assertEqual(entry["source_date"], "2026-10-30")
        self.assertEqual(entry["crystallization_date"], self.day)
        self.assertNotIn("bgm_url", entry)
        self.assertEqual((entry["start"], entry["end"]), ("08:10", "08:12"))
        for prefix in (self.root, self.root / "docs"):
            base = prefix / Path(entry["live_url"]).parent
            expected = {base / ("live" if name == "index.html" else "assets") / name for name in self.files}
            self.assertEqual({path for path in base.rglob("*") if path.is_file()}, expected)
            for path in expected:
                self.assertEqual(path.read_text(encoding="utf-8"), self.files[path.name])
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(self.import_work(), entry)
        after = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(autonomous.read_text(), "autonomous stays")
        self.assertEqual(list(importer.load_entries(self.root / "metadata/yesterday-flash-entries.json")), [self.day])

    def test_missing_public_files_fail_before_any_write(self):
        for filename, content in self.files.items():
            with self.subTest(filename=filename):
                (self.folder / filename).unlink()
                with self.assertRaisesRegex(ValueError, "Missing regular public file"):
                    self.import_work()
                self.assertFalse(self.root.exists())
                (self.folder / filename).write_text(content, encoding="utf-8")

    def test_unsafe_public_text_fails_closed_in_every_file(self):
        unsafe = (
            "https://example.invalid/private", "www.example.com", "example.org",
            "reader@example.invalid", "api_key = hidden-value", "Bearer hidden-value", "secret=hidden-value",
            "BTC", "Bitcoin", "ETH", "Solana", "稳定币", "Token经济", "DeFi", "加密资产",
            "https&#58;//example.invalid", "https%3A%2F%2Fexample.invalid",
        )
        for filename, original in self.files.items():
            for value in unsafe:
                with self.subTest(filename=filename, category=value):
                    (self.folder / filename).write_text(original + "\n" + value, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "Public source rejected"):
                        self.import_work()
                    self.assertFalse(self.root.exists())
            (self.folder / filename).write_text(original, encoding="utf-8")

    def test_rejected_update_preserves_previous_import(self):
        self.import_work()
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        (self.folder / "text-layer.md").write_text("Bitcoin", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.import_work()
        self.assertEqual(before, {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()})

    def test_missing_date_mismatched_manifest_and_symlink_are_rejected(self):
        with self.assertRaises(ValueError):
            importer.import_work("2026-10-29", self.source, self.root)
        self.assertFalse(self.root.exists())
        for day in ("../2026-10-31", "2026-02-30", "2026-1-01"):
            with self.assertRaises(ValueError):
                importer.import_work(day, self.source, self.root)
        manifest = {**self.manifest, "crystallization_day": "2026-10-30"}
        (self.folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(ValueError):
            self.import_work()
        (self.folder / "manifest.json").write_text(self.files["manifest.json"], encoding="utf-8")
        (self.folder / "index.html").unlink()
        (self.folder / "index.html").symlink_to(self.folder / "text-layer.md")
        with self.assertRaises(ValueError):
            self.import_work()
        self.assertFalse(self.root.exists())

    def test_timetable_adds_flash_only_on_crystallization_day(self):
        entry = self.import_work()
        arguments = (
            builder.read_json(builder.DEFAULT_PUBLIC_DAYS),
            builder.read_json(builder.DEFAULT_CONFIG),
            builder.load_legacy(builder.DEFAULT_LEGACY_OVERRIDES),
            builder.load_history(builder.DEFAULT_HISTORY),
            builder.load_pulses(builder.DEFAULT_PULSES),
        )
        original = builder.build_data(*arguments)
        output = builder.build_data(*arguments, {self.day: entry})
        for before, after in zip(original["days"], output["days"]):
            self.assertEqual(before["autonomous_work"], after["autonomous_work"])
            if after["date"] != self.day:
                self.assertEqual(before, after)
                continue
            flash = after["yesterday_flash"]
            self.assertEqual(flash["duration_minutes"], 2)
            self.assertEqual(flash["timezone"], "Asia/Shanghai")
            self.assertIn("/yesterday-flash/live/", flash["live_url"])
            self.assertNotEqual(flash["live_url"], after["autonomous_work"]["live_url"])
            self.assertIn(flash, after["timeline_events"])
            autonomous_index = next(index for index, item in enumerate(after["reading_items"]) if item["source"] == "autonomous")
            self.assertEqual(after["reading_items"][autonomous_index + 1]["source"], "yesterday_flash")
            self.assertEqual([item for item in after["timeline_events"] if item["origin"] != "flash"], before["timeline_events"])
            broken = copy.deepcopy(after)
            broken["yesterday_flash"]["start"] = "03:17"
            with self.assertRaises(SystemExit):
                builder.validate_day(broken, {day["date"] for day in output["days"]}, len(output["days"]), output["autonomous_hour"])
        self.assertEqual(original["bgm_playlist"], output["bgm_playlist"])
        self.assertIn("...(day.yesterday_flash ? [day.yesterday_flash] : [])", builder.render_javascript(output))


if __name__ == "__main__":
    unittest.main()
