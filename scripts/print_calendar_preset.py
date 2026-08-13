#!/usr/bin/env python3
"""Shared preset loading and validation for the printable calendar tools."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_PRESET = Path("config/print-desk-calendar-v1.json")
EXPECTED_SCHEMA = "granted-hours-print-desk-calendar-preset-v1"


class PrintCalendarPresetError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require(
    mapping: dict[str, Any], path: str, expected_type: type | tuple[type, ...]
) -> Any:
    value: Any = mapping
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            raise PrintCalendarPresetError(f"Preset is missing required value: {path}")
        value = value[part]
    if not isinstance(value, expected_type):
        expected_name = (
            " or ".join(item.__name__ for item in expected_type)
            if isinstance(expected_type, tuple)
            else expected_type.__name__
        )
        raise PrintCalendarPresetError(
            f"Preset value {path} must be {expected_name}, got {type(value).__name__}"
        )
    return value


def validate_preset(preset: dict[str, Any]) -> None:
    if preset.get("schema") != EXPECTED_SCHEMA:
        raise PrintCalendarPresetError(
            f"Unexpected preset schema: {preset.get('schema')!r}; expected {EXPECTED_SCHEMA!r}"
        )
    _require(preset, "edition_id", str)
    _require(preset, "source.canonical_timetable_data", str)
    assets = _require(preset, "source.artwork_asset_preference", list)
    if not assets or not all(isinstance(item, str) for item in assets):
        raise PrintCalendarPresetError("source.artwork_asset_preference must contain path templates")
    width = float(_require(preset, "page.width_mm", (int, float)))
    height = float(_require(preset, "page.height_mm", (int, float)))
    if width <= 0 or height <= 0:
        raise PrintCalendarPresetError("Page dimensions must be positive")
    max_cards = int(_require(preset, "content.max_cards", int))
    if not 1 <= max_cards <= 4:
        raise PrintCalendarPresetError("The v1 two-by-two card layout supports 1 to 4 cards")
    ratio = _require(preset, "artwork.aspect_ratio", list)
    if len(ratio) != 2 or any(float(item) <= 0 for item in ratio):
        raise PrintCalendarPresetError("artwork.aspect_ratio must contain two positive numbers")
    error_level = _require(preset, "qr.error_correction", str)
    if error_level not in {"L", "M", "Q", "H"}:
        raise PrintCalendarPresetError("qr.error_correction must be L, M, Q, or H")
    proof_dates = _require(preset, "proof.dates", list)
    if not proof_dates or not all(isinstance(item, str) for item in proof_dates):
        raise PrintCalendarPresetError("proof.dates must contain civil dates")
    palette = _require(preset, "palette", dict)
    required_colors = {
        "paper",
        "paper_deep",
        "ink",
        "ink_soft",
        "graphite",
        "bone",
        "gold",
        "gold_light",
        "cyan",
        "cyan_light",
        "sage",
        "sage_light",
        "amber",
        "violet",
        "red",
        "white",
    }
    missing_colors = sorted(required_colors - palette.keys())
    if missing_colors:
        raise PrintCalendarPresetError(f"Preset palette is missing: {missing_colors}")


def load_preset(repo: Path, value: Path | None = None) -> tuple[Path, dict[str, Any]]:
    path = value.expanduser() if value else DEFAULT_PRESET
    if not path.is_absolute():
        path = repo / path
    path = path.resolve()
    if not path.exists():
        raise PrintCalendarPresetError(f"Printable calendar preset is missing: {path}")
    try:
        preset = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PrintCalendarPresetError(f"Cannot parse printable calendar preset: {exc}") from exc
    if not isinstance(preset, dict):
        raise PrintCalendarPresetError("Printable calendar preset must be a JSON object")
    validate_preset(preset)
    return path, preset


def preset_number(preset: dict[str, Any], section: str, key: str) -> float:
    return float(preset[section][key])
