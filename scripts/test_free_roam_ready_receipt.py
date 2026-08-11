#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import write_free_roam_ready_receipt as writer


class FreeRoamReadyReceiptTests(unittest.TestCase):
    def test_validated_v2_receipt_is_complete_and_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            day = "2099-01-02"
            basename = f"{day}-future-work"
            for _key, (suffix, _spec) in writer.ASSET_SPECS.items():
                path = root / f"{basename}{suffix}"
                if suffix == ".html":
                    path.write_text("<!doctype html><html></html>", encoding="utf-8")
                elif suffix == "-note.md":
                    labels = "\n".join(
                        f"- **{label}**: value" for label in writer.NOTE_LABELS
                    )
                    labels = labels.replace(
                        "**Crystallization Day / 结晶日**: value",
                        f"**Crystallization Day / 结晶日**: {day}",
                    ).replace(
                        "**Granted duration / 授予时长**: value",
                        "**Granted duration / 授予时长**: 03:17–04:17 Asia/Shanghai",
                    )
                    path.write_text(f"# Future Work / 未来作品\n{labels}\n", encoding="utf-8")
                else:
                    path.write_bytes(b"fixture")
            probes = {
                ".png": (1600, 900, 1),
                "-visual-preview.gif": (400, 225, 48),
                "-preview.gif": (720, 405, 48),
                ".webp": (960, 540, 1),
            }

            def probe(path: Path) -> tuple[int, int, int | None]:
                for suffix, result in probes.items():
                    if path.name.endswith(suffix):
                        return result
                raise AssertionError(path)

            receipt = writer.build_receipt(
                day=day,
                basename=basename,
                artifacts=root,
                updated_at="2099-01-02T05:10:00+08:00",
                media_probe=probe,
            )
            destination = root / "receipts" / f"{day}.json"
            writer.atomic_write(destination, receipt)
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            self.assertEqual(receipt["schema"], "granted-hours-free-roam-ready-v2")
            self.assertTrue(receipt["assetsComplete"])
            self.assertTrue(all(receipt["required_assets"].values()))
            self.assertEqual(receipt["verification_status"], "passed")

    def test_wrong_visual_geometry_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            day = "2099-01-02"
            basename = f"{day}-future-work"
            for _key, (suffix, _spec) in writer.ASSET_SPECS.items():
                path = root / f"{basename}{suffix}"
                if suffix == ".html":
                    path.write_text("<html></html>", encoding="utf-8")
                elif suffix == "-note.md":
                    path.write_text("# incomplete", encoding="utf-8")
                else:
                    path.write_bytes(b"fixture")
            with self.assertRaises(SystemExit):
                writer.build_receipt(
                    day=day,
                    basename=basename,
                    artifacts=root,
                    media_probe=lambda _path: (1, 1, 1),
                )


if __name__ == "__main__":
    unittest.main()
