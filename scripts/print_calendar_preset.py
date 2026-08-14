#!/usr/bin/env python3
"""Shared preset loading and validation for the printable calendar tools."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_PRESET = Path("config/print-desk-calendar-v1.json")
EXPECTED_SCHEMAS = {
    "granted-hours-print-desk-calendar-preset-v1",
    "granted-hours-print-desk-calendar-preset-v2",
    "granted-hours-print-desk-calendar-preset-v3",
}


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
    schema = preset.get("schema")
    if schema not in EXPECTED_SCHEMAS:
        raise PrintCalendarPresetError(
            f"Unexpected preset schema: {schema!r}; expected one of {sorted(EXPECTED_SCHEMAS)!r}"
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
    _require(preset, "qr.inverted", bool)
    orientation = _require(preset, "page.orientation", str)
    mode = _require(preset, "layout.mode", str)
    if orientation not in {"landscape", "portrait"} or mode != orientation:
        raise PrintCalendarPresetError(
            "page.orientation and layout.mode must match: landscape or portrait"
        )
    theme_mode = preset.get("theme", {}).get("mode", "light")
    if theme_mode not in {"light", "dark"}:
        raise PrintCalendarPresetError("theme.mode must be light or dark")
    if theme_mode == "dark":
        surfaces = _require(preset, "surfaces", dict)
        required_surfaces = {
            "binding_tick",
            "artwork_border",
            "absence_fill",
            "absence_line",
            "absence_orbit",
            "absence_core",
            "timeline_rule",
            "timeline_tick",
            "card_collaboration",
            "card_reminder",
            "card_routine",
            "card_fallback",
            "card_border",
            "meta_text",
        }
        missing_surfaces = sorted(required_surfaces - surfaces.keys())
        if missing_surfaces:
            raise PrintCalendarPresetError(
                f"Dark preset surfaces are missing: {missing_surfaces}"
            )
    projection = preset.get("temporal_projection", {"mode": "civil_day"})
    if not isinstance(projection, dict):
        raise PrintCalendarPresetError("temporal_projection must be an object")
    projection_mode = projection.get("mode", "civil_day")
    if projection_mode not in {"civil_day", "source_day_with_forward_crystallization"}:
        raise PrintCalendarPresetError(
            f"Unsupported temporal_projection.mode: {projection_mode!r}"
        )
    if projection_mode == "source_day_with_forward_crystallization":
        if schema not in {
            "granted-hours-print-desk-calendar-preset-v2",
            "granted-hours-print-desk-calendar-preset-v3",
        }:
            raise PrintCalendarPresetError(
                "Source-day projection requires the v2 or v3 preset schema"
            )
        if projection.get("unpaired_source_day") != "omit":
            raise PrintCalendarPresetError(
                "Source-day projection currently requires unpaired_source_day=omit"
            )
        if projection.get("source_day_autonomous_footprint") != "omit_from_strata":
            raise PrintCalendarPresetError(
                "Source-day projection requires source_day_autonomous_footprint=omit_from_strata"
            )
    if schema == "granted-hours-print-desk-calendar-preset-v3":
        if _require(preset, "content.artwork_copy_mode", str) != "summary_brief_bilingual":
            raise PrintCalendarPresetError(
                "The v3 print contract requires content.artwork_copy_mode=summary_brief_bilingual"
            )
        if _require(preset, "content.routine_card_mode", str) != "family_rollups":
            raise PrintCalendarPresetError(
                "The v3 print contract requires content.routine_card_mode=family_rollups"
            )
        _require(preset, "content.fill_available_routine_cards", bool)
        max_routine_cards = int(_require(preset, "content.max_routine_cards", int))
        if not 1 <= max_routine_cards <= 3:
            raise PrintCalendarPresetError("content.max_routine_cards must be between 1 and 3")
        if mode == "portrait":
            copy_top = float(_require(preset, "layout.artwork_copy_top_mm", (int, float)))
            copy_bottom = float(
                _require(preset, "layout.artwork_copy_bottom_mm", (int, float))
            )
            if copy_top <= copy_bottom:
                raise PrintCalendarPresetError(
                    "Portrait artwork-copy top must be above its bottom"
                )
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
