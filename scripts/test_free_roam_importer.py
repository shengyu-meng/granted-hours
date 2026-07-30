#!/usr/bin/env python3
"""Focused tests for date-scoped public artifact imports."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import import_free_roam_artifacts as importer


class FreeRoamImporterTests(unittest.TestCase):
    def test_live_enhancement_adds_public_archive_dialog_and_separate_link(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            archive_directory = Path(temporary_directory) / "2026-07-29"
            live_html = archive_directory / "live" / "index.html"
            archive_html = archive_directory / "index.html"
            live_html.parent.mkdir(parents=True)
            archive_html.write_text(
                """<!doctype html>
<html>
<head>
  <meta name="private-decoy" content="DO_NOT_INJECT_METADATA">
  <style>.decoy { content: "DO_NOT_INJECT_STYLE"; }</style>
</head>
<body>
  <section class="two">
    <div>
      <h2>Intention</h2>
      <p>A public &amp; safe <em>&lt;glass&gt;</em> &quot;note&quot;.</p>
      <h2>Afterimage</h2>
      <p>First public afterimage.</p>
    </div>
    <div>
      <h2>发心</h2>
      <p>公开发心。</p>
      <h2>余像</h2>
      <p>公开余像。</p>
    </div>
  </section>
  <section class="two featured">
    <div>
      <h2>Creative Rationale</h2>
      <p>Public rationale only.</p>
    </div>
    <div>
      <h2>创作缘由</h2>
      <p>仅公开创作缘由。</p>
    </div>
  </section>
  <section class="two">
    <div>
      <h2>Interaction</h2>
      <p>DO_NOT_INJECT_INTERACTION</p>
      <a href="https://decoy.invalid/private">DO_NOT_INJECT_LINK</a>
      <button type="button">DO_NOT_INJECT_CONTROL</button>
      <audio controls src="./private-decoy.mp3"></audio>
      <img src="./private-decoy.png" alt="DO_NOT_INJECT_IMAGE">
      <script>window.DO_NOT_INJECT_SCRIPT = true;</script>
    </div>
  </section>
</body>
</html>
""",
                encoding="utf-8",
            )
            live_html.write_text(
                """<!doctype html>
<html>
<head>
  <style id="granted-hours-fold-style">stale style</style>
  <script id="granted-hours-fold-script">stale script</script>
</head>
<body><canvas></canvas><section class="panel"><h1>Artwork</h1><p>Statement</p></section></body>
</html>
""",
                encoding="utf-8",
            )

            importer.enhance_live_html(live_html)
            importer.enhance_live_html(live_html)
            refreshed = live_html.read_text(encoding="utf-8")

        self.assertEqual(refreshed.count('id="granted-hours-fold-style"'), 1)
        self.assertEqual(refreshed.count('id="granted-hours-fold-script"'), 1)
        self.assertEqual(refreshed.count('<meta charset="utf-8">'), 1)
        self.assertLess(
            refreshed.index('<meta charset="utf-8">'),
            refreshed.index(importer.LIVE_ENHANCEMENT_START),
        )
        self.assertEqual(refreshed.count('id="gh-work-note-dialog"'), 1)
        self.assertIn('role="dialog"', refreshed)
        self.assertIn('aria-modal="true"', refreshed)
        self.assertIn('aria-labelledby="gh-work-note-title"', refreshed)
        self.assertEqual(
            refreshed.count("const workNote = document.createElement('button');"),
            1,
        )
        self.assertIn("workNote.type = 'button';", refreshed)
        self.assertNotIn("workNote.href", refreshed)
        self.assertEqual(
            refreshed.count("workNote.textContent = 'Work note / 作品说明';"),
            1,
        )
        self.assertEqual(
            refreshed.count("const archiveLink = document.createElement('a');"),
            1,
        )
        self.assertEqual(refreshed.count("archiveLink.href = '../';"), 1)
        self.assertEqual(
            refreshed.count(
                "archiveLink.textContent = 'Artwork archive / 作品档案';"
            ),
            1,
        )
        self.assertEqual(
            refreshed.count(
                "workNote.setAttribute('aria-label', "
                "'Open the artwork intention and context note / 打开作品发心与创作语境说明');"
            ),
            1,
        )
        expected_copy = (
            ("Intention", "A public & safe <glass> \"note\"."),
            ("Afterimage", "First public afterimage."),
            ("发心", "公开发心。"),
            ("余像", "公开余像。"),
            ("Creative Rationale", "Public rationale only."),
            ("创作缘由", "仅公开创作缘由。"),
        )
        for heading, paragraph in expected_copy:
            self.assertEqual(
                refreshed.count(f"<h2>{heading}</h2>"),
                1,
                heading,
            )
            escaped_paragraph = (
                paragraph.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )
            self.assertEqual(
                refreshed.count(f"<p>{escaped_paragraph}</p>"),
                1,
                paragraph,
            )
        for excluded in (
            "DO_NOT_INJECT_METADATA",
            "DO_NOT_INJECT_STYLE",
            "DO_NOT_INJECT_INTERACTION",
            "DO_NOT_INJECT_LINK",
            "DO_NOT_INJECT_CONTROL",
            "DO_NOT_INJECT_IMAGE",
            "DO_NOT_INJECT_SCRIPT",
            "https://decoy.invalid/private",
            "private-decoy.mp3",
            "private-decoy.png",
        ):
            self.assertNotIn(excluded, refreshed)
        self.assertNotRegex(refreshed, r"\bfetch\s*\(")
        self.assertNotIn(".innerHTML", refreshed)
        self.assertIn("body.gh-chamber-embed .gh-work-note-actions", refreshed)
        self.assertIn("body.gh-chamber-embed .gh-work-note-modal", refreshed)
        self.assertRegex(
            refreshed,
            r"(?s)\.gh-work-note-close \{.*?pointer-events: auto;",
        )
        self.assertIn("function findWorkNoteHost()", refreshed)
        self.assertIn("actionRow.append(workNote, archiveLink);", refreshed)
        self.assertIn("workNoteHost.appendChild(actionRow);", refreshed)
        self.assertIn("workNoteHost.classList.add('gh-work-note-host');", refreshed)
        self.assertIn("position: static;", refreshed)
        self.assertNotIn("document.body.appendChild(workNote);", refreshed)

    def test_live_enhancement_fails_closed_without_valid_public_archive(self) -> None:
        fixtures = {
            "missing": None,
            "invalid": """<!doctype html>
<section class="two"><h2>Intention</h2><p>Incomplete.</p></section>
""",
        }
        for label, archive_source in fixtures.items():
            with self.subTest(label=label):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    archive_directory = Path(temporary_directory) / label
                    live_html = archive_directory / "live" / "index.html"
                    live_html.parent.mkdir(parents=True)
                    original = "<!doctype html><body><canvas></canvas></body>"
                    live_html.write_text(original, encoding="utf-8")
                    if archive_source is not None:
                        (archive_directory / "index.html").write_text(
                            archive_source,
                            encoding="utf-8",
                        )

                    with self.assertRaisesRegex(
                        SystemExit,
                        r"public sibling archive|public work-note archive",
                    ):
                        importer.enhance_live_html(live_html)

                    self.assertEqual(
                        live_html.read_text(encoding="utf-8"),
                        original,
                    )

    def test_latest_entries_are_declared_in_chronological_order(self) -> None:
        latest = importer.ENTRIES[-3:]
        self.assertEqual(
            [entry["date"] for entry in latest],
            ["2026-07-27", "2026-07-28", "2026-07-29"],
        )
        self.assertEqual(
            [(entry["title_en"], entry["title_zh"]) for entry in latest],
            [
                ("A Garden That Does Not Need a Gardener", "不需要园丁的花园"),
                ("The Map That Refuses to Arrive", "拒绝抵达的地图"),
                ("The Compass That Forgets North", "忘记北方的罗盘"),
            ],
        )
        for entry in latest:
            for field in (
                "intention_en",
                "intention_zh",
                "interaction_en",
                "interaction_zh",
                "after_en",
                "after_zh",
            ):
                self.assertTrue(entry[field].strip(), f"{entry['date']} missing {field}")

    def test_date_scoped_merge_preserves_existing_days(self) -> None:
        original_root = importer.ROOT
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                importer.ROOT = Path(temporary_directory)
                metadata = importer.ROOT / "metadata"
                metadata.mkdir()
                existing = [
                    {"date": entry["date"], "sentinel": entry["date"]}
                    for entry in importer.ENTRIES[:-3]
                ]
                (metadata / "days.json").write_text(
                    json.dumps(existing),
                    encoding="utf-8",
                )
                imported = [
                    {"date": entry["date"], "sentinel": "new"}
                    for entry in importer.ENTRIES[-3:]
                ]

                merged = importer.merge_date_scoped_days(imported)

            self.assertEqual(len(merged), len(importer.ENTRIES))
            self.assertEqual(merged[:-3], existing)
            self.assertEqual(merged[-3:], imported)
        finally:
            importer.ROOT = original_root

    def test_archive_dual_date_metadata_links_only_existing_public_source_days(self) -> None:
        config = json.loads(
            (Path(__file__).resolve().parents[1] / "metadata" / "timetable-calendar.json")
            .read_text(encoding="utf-8")
        )
        linked = importer.build_dual_date_metadata(
            "2026-07-29",
            {"2026-07-28", "2026-07-29"},
            config,
        )
        self.assertEqual(linked["source_date"], "2026-07-28")
        self.assertEqual(linked["crystallization_date"], "2026-07-29")
        self.assertEqual(
            (linked["start"], linked["end"]),
            ("03:17", "04:17"),
        )
        self.assertRegex(
            linked["source_day_url"],
            r"/timetable/\?date=2026-07-28$",
        )
        html = importer.render_archive_dual_date_html(linked)
        markdown = importer.render_archive_dual_date_markdown(linked)
        for copy in (
            "Source Day / 来源日",
            "Crystallization Day / 结晶日",
            "2026-07-28",
            "2026-07-29",
            "03:17–04:17",
        ):
            self.assertIn(copy, html)
            self.assertIn(copy, markdown)

        first = importer.build_dual_date_metadata(
            "2026-05-07",
            {"2026-05-07"},
            config,
        )
        self.assertEqual(first["source_date"], "2026-05-06")
        self.assertIsNone(first["source_day_url"])
        first_html = importer.render_archive_dual_date_html(first)
        self.assertIn("2026-05-06", first_html)
        self.assertNotIn("?date=2026-05-06", first_html)

    def test_checked_in_archive_explanations_have_dual_date_copy(self) -> None:
        root = Path(__file__).resolve().parents[1]
        public_days = json.loads(
            (root / "metadata" / "days.json").read_text(encoding="utf-8")
        )
        for day in public_days:
            with self.subTest(day=day["date"]):
                year, month, _ = day["date"].split("-")
                archive_page = (
                    root
                    / "docs"
                    / "archive"
                    / year
                    / month
                    / day["date"]
                    / "index.html"
                ).read_text(encoding="utf-8")
                self.assertIn("Source Day / 来源日", archive_page)
                self.assertIn(
                    "Crystallization Day / 结晶日",
                    archive_page,
                )


if __name__ == "__main__":
    unittest.main()
