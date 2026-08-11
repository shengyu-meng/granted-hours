#!/usr/bin/env python3
"""Validate one private free-roam artifact set and atomically write its ready receipt."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
DEFAULT_ARTIFACTS = WORKSPACE / "artifacts" / "free-roam"
DEFAULT_RECEIPTS = WORKSPACE / "tmp" / "granted-hours-free-roam-ready"
ASSET_SPECS = {
    "html": (".html", None),
    "note": ("-note.md", None),
    "bgm": ("-bgm.mp3", None),
    "preview_png_1600x900": ("-preview.png", (1600, 900, None)),
    "preview_gif_720x405_48frames": ("-preview.gif", (720, 405, 48)),
    "visual_preview_gif_400x225_48frames": ("-visual-preview.gif", (400, 225, 48)),
    "visual_preview_webp_960x540": ("-visual-preview.webp", (960, 540, None)),
}
NOTE_LABELS = (
    "Free variable / 自由变量",
    "Intention / 发心",
    "Interaction / 交互",
    "Afterimage / 余像",
    "Source Day / 源日",
    "Crystallization Day / 结晶日",
    "Granted duration / 授予时长",
    "Experience duration / 体验时长",
)


def parse_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise SystemExit("Receipt date must be YYYY-MM-DD") from error
    if parsed.isoformat() != value:
        raise SystemExit("Receipt date must be canonical YYYY-MM-DD")
    return value


def discover_basename(artifacts: Path, day: str, requested: str | None) -> str:
    if requested:
        if not requested.startswith(f"{day}-") or "/" in requested or "\\" in requested:
            raise SystemExit("Artwork basename must start with the receipt date")
        return requested
    matches = sorted(artifacts.glob(f"{day}-*.html"))
    if len(matches) != 1:
        raise SystemExit(f"Expected exactly one HTML artwork for {day}, found {len(matches)}")
    return matches[0].stem


def probe_media(path: Path) -> tuple[int, int, int | None]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,nb_read_frames",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"Could not inspect required visual asset: {path.name}")
    try:
        [stream] = json.loads(result.stdout)["streams"]
        frames_value = stream.get("nb_read_frames")
        frames = int(frames_value) if str(frames_value).isdigit() else None
        return int(stream["width"]), int(stream["height"]), frames
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"Invalid media probe result for {path.name}") from error


def validate_note(path: Path, day: str) -> None:
    text = path.read_text(encoding="utf-8")
    if not text.strip().startswith("# "):
        raise SystemExit("Artwork note needs a bilingual heading")
    for label in NOTE_LABELS:
        if f"**{label}**" not in text:
            raise SystemExit(f"Artwork note is missing {label}")
    if f"**Crystallization Day / 结晶日**: {day}" not in text:
        raise SystemExit("Artwork note crystallization date mismatch")
    if "**Granted duration / 授予时长**: 03:17–04:17 Asia/Shanghai" not in text:
        raise SystemExit("Artwork note granted duration mismatch")


def build_receipt(
    *,
    day: str,
    basename: str,
    artifacts: Path,
    updated_at: str | None = None,
    media_probe=probe_media,
) -> dict:
    required_assets = {}
    for key, (suffix, media_spec) in ASSET_SPECS.items():
        path = artifacts / f"{basename}{suffix}"
        if not path.is_file() or path.stat().st_size <= 0:
            raise SystemExit(f"Missing required free-roam asset: {path.name}")
        if key == "note":
            validate_note(path, day)
        elif key == "html" and "</html>" not in path.read_text(encoding="utf-8").lower():
            raise SystemExit("Artwork HTML is incomplete")
        if media_spec is not None:
            expected_width, expected_height, expected_frames = media_spec
            width, height, frames = media_probe(path)
            if (width, height) != (expected_width, expected_height):
                raise SystemExit(
                    f"{path.name} must be {expected_width}x{expected_height}, got {width}x{height}"
                )
            if expected_frames is not None and frames != expected_frames:
                raise SystemExit(f"{path.name} must have {expected_frames} frames, got {frames}")
        required_assets[key] = True
    timestamp = updated_at or datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    return {
        "schema": "granted-hours-free-roam-ready-v2",
        "date": day,
        "artwork_basename": basename,
        "assetsComplete": True,
        "required_assets": required_assets,
        "verification_status": "passed",
        "updated_at": timestamp,
    }


def atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--basename")
    parser.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--receipts", type=Path, default=DEFAULT_RECEIPTS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    day = parse_date(args.date)
    artifacts = args.artifacts.expanduser().resolve()
    if not artifacts.is_dir():
        raise SystemExit("Free-roam artifact directory does not exist")
    basename = discover_basename(artifacts, day, args.basename)
    payload = build_receipt(day=day, basename=basename, artifacts=artifacts)
    destination = args.receipts.expanduser().resolve() / f"{day}.json"
    atomic_write(destination, payload)
    print(json.dumps({"passed": True, "date": day, "schema": payload["schema"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
