#!/usr/bin/env python3
"""Build a versioned printable Granted Hours desk-calendar edition.

The generator reads the canonical public timetable data, uses local archive
artwork stills, and renders one truthful civil day per page. A versioned
temporal projection may editorially pair one source day with the work that
crystallized from it at the next dawn. Calendar-only days receive an absence
field rather than a fabricated artwork.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from print_calendar_preset import (
    PrintCalendarPresetError,
    load_preset,
    preset_number,
    sha256_file,
)

try:
    from PIL import Image, ImageOps
    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.colors import Color, HexColor
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
except ImportError as exc:  # pragma: no cover - environment diagnostic
    raise SystemExit(
        "Missing PDF runtime dependency. Run with the Codex bundled Python "
        "returned by codex_app__load_workspace_dependencies. "
        f"Original error: {exc}"
    ) from exc


PAGE_W = 210 * mm
PAGE_H = 140 * mm
MARGIN = 8 * mm
BINDING_BAND = 10 * mm
FONT_LIGHT = "GH-Heiti-Light"
FONT_MEDIUM = "GH-Heiti-Medium"
FONT_SERIF = "Times-Roman"
FONT_SERIF_BOLD = "Times-Bold"
FONT_MONO = "Courier"
FONT_MONO_BOLD = "Courier-Bold"

PAPER = HexColor("#F2EEE3")
PAPER_DEEP = HexColor("#E7E0D1")
INK = HexColor("#11171B")
INK_SOFT = HexColor("#4C5354")
GRAPHITE = HexColor("#11171B")
BONE = HexColor("#F2EEE3")
GOLD = HexColor("#B58942")
GOLD_LIGHT = HexColor("#D8BB78")
CYAN = HexColor("#4E8FA0")
CYAN_LIGHT = HexColor("#A8CCD0")
SAGE = HexColor("#7E9181")
SAGE_LIGHT = HexColor("#C3CDC0")
AMBER = HexColor("#C97942")
VIOLET = HexColor("#777187")
RED = HexColor("#A85C55")
WHITE = HexColor("#FFFFFF")

LAYOUT: dict[str, Any] = {}
ARTWORK_ASPECT = (16.0, 9.0)
ARTWORK_CACHE_WIDTH = 1200
ARTWORK_JPEG_QUALITY = 86
ARTWORK_ASSET_PREFERENCE: list[str] = []
MAX_CARDS = 4
MAX_COLLABORATION_CARDS = 2
MAX_REMINDER_CARDS = 2
INCLUDE_ROUTINE_ROLLUP = True
MAX_ROUTINE_CARDS = 1
ARTWORK_COPY_MODE = "brief_only"
ROUTINE_CARD_MODE = "single_rollup"
FILL_AVAILABLE_ROUTINE_CARDS = False
QR_ERROR_CORRECTION = "Q"
QR_BORDER_MODULES = 4
QR_DAY_SIZE = 18.5 * mm
QR_DAY_Y = 11 * mm
QR_COVER_SIZE = 19 * mm
QR_COVER_Y = 9 * mm
QR_INVERTED = False
DARK_THEME = False
SURFACES: dict[str, str] = {}

WEEKDAY_ZH = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
WEEKDAY_EN = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
ROUTINE_LABELS = {
    "ah_market_scan": ("A/H 市场", "A/H market"),
    "us_market_scan": ("美股", "U.S. market"),
    "ai_daily_brief": ("AI 日报", "AI brief"),
    "daily_reminder": ("提醒", "reminders"),
    "system_routine": ("系统", "system"),
    "background_routine": ("后台", "background"),
}


class CalendarBuildError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument(
        "--preset",
        type=Path,
        default=None,
        help="Versioned JSON preset (default: config/print-desk-calendar-v1.json)",
    )
    parser.add_argument("--from-date", default=None, help="Inclusive YYYY-MM-DD")
    parser.add_argument("--through", default=None, help="Inclusive YYYY-MM-DD")
    parser.add_argument(
        "--dates",
        default=None,
        help="Comma-separated proof dates; overrides --from-date/--through",
    )
    parser.add_argument(
        "--proof",
        action="store_true",
        help="Build the representative dates declared by the preset",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument(
        "--qr-base-url",
        default=None,
        help="Override the QR base URL declared by the preset",
    )
    parser.add_argument("--no-cover", action="store_true")
    parser.add_argument(
        "--show-preset",
        action="store_true",
        help="Validate and print the resolved preset, then exit",
    )
    return parser.parse_args()


def resolve_repo_root(value: Path | None) -> Path:
    if value:
        root = value.expanduser().resolve()
        if (root / "src/timetable/timetable-data.js").exists():
            return root
        raise CalendarBuildError(f"Not a Granted Hours repository: {root}")
    for candidate in [Path.cwd(), *Path.cwd().parents, Path(__file__).resolve().parent.parent]:
        if (candidate / "src/timetable/timetable-data.js").exists():
            return candidate.resolve()
    raise CalendarBuildError("Could not resolve the Granted Hours repository root")


def load_timetable(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    marker = "const timetableDataSource ="
    marker_at = source.find(marker)
    if marker_at < 0:
        raise CalendarBuildError(f"Canonical data marker missing in {path}")
    json_at = source.find("{", marker_at + len(marker))
    if json_at < 0:
        raise CalendarBuildError(f"Canonical data object missing in {path}")
    try:
        data, _ = json.JSONDecoder().raw_decode(source[json_at:])
    except json.JSONDecodeError as exc:
        raise CalendarBuildError(f"Cannot parse timetable data: {exc}") from exc
    if data.get("schema") != "granted-hours-timetable-v2":
        raise CalendarBuildError(f"Unexpected timetable schema: {data.get('schema')}")
    days = data.get("days")
    if not isinstance(days, list) or not days:
        raise CalendarBuildError("Timetable has no public days")
    for day in days:
        events = [
            *day.get("task_residues", []),
            day.get("autonomous_work"),
            *day.get("background_pulses", []),
        ]
        events = [item for item in events if item]
        priority = {"self": 0, "absence": 0, "assigned": 1, "background": 2}
        events.sort(
            key=lambda item: (
                time_minutes(item.get("start", "00:00")),
                priority.get(item.get("origin"), 9),
            )
        )
        day["timeline_events"] = events
    return data


def source_day_projection(days: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pair each public source day with its unique later crystallization.

    The source day supplies the printed date, events, cards, and QR target.
    The matched crystallization day supplies the artwork, title, variable, and
    artwork notes. The source day's own autonomous footprint is deliberately
    omitted from its signal strata because it belongs to the prior source-day
    pairing; keeping it would visually claim two different temporal models at
    once.
    """

    ordered = sorted(days, key=lambda item: item["date"])
    source_days = {item["date"]: item for item in ordered}
    matches: dict[str, list[dict[str, Any]]] = {}
    for artwork_day in ordered:
        work = artwork_day.get("autonomous_work") or {}
        source_date = artwork_day.get("source_date") or work.get("source_date")
        if source_date in source_days and artwork_day["date"] > source_date:
            matches.setdefault(source_date, []).append(artwork_day)

    projected: list[dict[str, Any]] = []
    for source_day in ordered:
        candidates = matches.get(source_day["date"], [])
        if not candidates:
            continue
        if len(candidates) != 1:
            raise CalendarBuildError(
                f"Source day {source_day['date']} has {len(candidates)} forward crystallizations"
            )
        artwork_day = candidates[0]
        autonomous_work = artwork_day.get("autonomous_work")
        if not autonomous_work:
            raise CalendarBuildError(
                f"Crystallization day lacks an autonomous/absence beacon: {artwork_day['date']}"
            )
        if autonomous_work.get("source_date") != source_day["date"]:
            raise CalendarBuildError(
                f"Artwork {artwork_day['date']} does not confirm source day {source_day['date']}"
            )
        if autonomous_work.get("crystallization_date") != artwork_day["date"]:
            raise CalendarBuildError(
                f"Artwork {artwork_day['date']} has inconsistent crystallization metadata"
            )
        projected_day = copy.deepcopy(source_day)
        for key in (
            "title_en",
            "title_zh",
            "variable_en",
            "variable_zh",
            "gif",
            "preview",
            "visual_preview",
            "archive_url",
            "live_url",
            "bgm",
            "type",
            "theme_motif",
            "jewel_en",
            "jewel_zh",
        ):
            projected_day[key] = copy.deepcopy(artwork_day.get(key))
        projected_day["autonomous_work"] = copy.deepcopy(autonomous_work)
        projected_day["source_date"] = source_day["date"]
        projected_day["crystallization_date"] = artwork_day["date"]
        projected_day["artwork_date"] = artwork_day["date"]
        projected_day["source_day_type"] = source_day.get("type")
        projected_day["timeline_events"] = [
            copy.deepcopy(item)
            for item in source_day.get("timeline_events", [])
            if item.get("origin") not in {"self", "absence"}
        ]
        projected_day["_temporal_projection"] = {
            "mode": "source_day_with_forward_crystallization",
            "source_date": source_day["date"],
            "crystallization_date": artwork_day["date"],
            "source_day_autonomous_footprint": "omitted_from_strata",
        }
        projected.append(projected_day)
    if not projected:
        raise CalendarBuildError("No source day has a public forward crystallization")
    return projected


def printable_days(data: dict[str, Any], preset: dict[str, Any]) -> list[dict[str, Any]]:
    days = sorted(data["days"], key=lambda item: item["date"])
    projection_mode = preset.get("temporal_projection", {}).get("mode", "civil_day")
    if projection_mode == "source_day_with_forward_crystallization":
        return source_day_projection(days)
    return days


def choose_days(
    data: dict[str, Any], args: argparse.Namespace, preset: dict[str, Any]
) -> list[dict[str, Any]]:
    days = printable_days(data, preset)
    by_date = {item["date"]: item for item in days}
    if len(by_date) != len(days):
        raise CalendarBuildError("Timetable contains duplicate civil dates")
    if args.proof and (args.dates or args.from_date or args.through):
        raise CalendarBuildError("--proof cannot be combined with --dates/--from-date/--through")
    selected_dates = preset["proof"]["dates"] if args.proof else None
    if args.dates or selected_dates:
        requested = (
            [part.strip() for part in args.dates.split(",") if part.strip()]
            if args.dates
            else [
                days[0]["date"]
                if item == "first_public_day"
                else days[-1]["date"]
                if item in {"latest_public_day", "latest_paired_source_day"}
                else item
                for item in selected_dates
            ]
        )
        requested = list(dict.fromkeys(requested))
        missing = [item for item in requested if item not in by_date]
        if missing:
            raise CalendarBuildError(f"Proof dates are not public: {missing}")
        selected = [by_date[item] for item in requested]
    else:
        configured_start = preset["date_selection"]["from"]
        configured_through = preset["date_selection"]["through"]
        start = args.from_date or (
            days[0]["date"] if configured_start == "first_public_day" else configured_start
        )
        through = args.through or (
            days[-1]["date"]
            if configured_through in {"latest_public_day", "latest_paired_source_day"}
            else configured_through
        )
        selected = [item for item in days if start <= item["date"] <= through]
    if not selected:
        raise CalendarBuildError("Selected calendar range is empty")
    for item in selected:
        datetime.strptime(item["date"], "%Y-%m-%d")
        if not item.get("autonomous_work"):
            raise CalendarBuildError(f"Day lacks an autonomous/absence beacon: {item['date']}")
    return selected


def apply_preset(preset: dict[str, Any]) -> None:
    global PAGE_W, PAGE_H, MARGIN, BINDING_BAND
    global PAPER, PAPER_DEEP, INK, INK_SOFT, GRAPHITE, BONE
    global GOLD, GOLD_LIGHT, CYAN, CYAN_LIGHT, SAGE, SAGE_LIGHT
    global AMBER, VIOLET, RED, WHITE, LAYOUT
    global ARTWORK_ASPECT, ARTWORK_CACHE_WIDTH, ARTWORK_JPEG_QUALITY
    global ARTWORK_ASSET_PREFERENCE, MAX_CARDS, MAX_COLLABORATION_CARDS
    global MAX_REMINDER_CARDS, INCLUDE_ROUTINE_ROLLUP, MAX_ROUTINE_CARDS
    global ARTWORK_COPY_MODE, ROUTINE_CARD_MODE, FILL_AVAILABLE_ROUTINE_CARDS
    global QR_ERROR_CORRECTION, QR_BORDER_MODULES, QR_DAY_SIZE, QR_DAY_Y
    global QR_COVER_SIZE, QR_COVER_Y, QR_INVERTED, DARK_THEME, SURFACES

    PAGE_W = preset_number(preset, "page", "width_mm") * mm
    PAGE_H = preset_number(preset, "page", "height_mm") * mm
    MARGIN = preset_number(preset, "page", "margin_mm") * mm
    BINDING_BAND = preset_number(preset, "page", "binding_band_mm") * mm
    LAYOUT = dict(preset["layout"])
    ratio = preset["artwork"]["aspect_ratio"]
    ARTWORK_ASPECT = (float(ratio[0]), float(ratio[1]))
    ARTWORK_CACHE_WIDTH = int(preset["artwork"]["cache_width_px"])
    ARTWORK_JPEG_QUALITY = int(preset["artwork"]["jpeg_quality"])
    ARTWORK_ASSET_PREFERENCE = list(preset["source"]["artwork_asset_preference"])
    MAX_CARDS = int(preset["content"]["max_cards"])
    MAX_COLLABORATION_CARDS = int(preset["content"]["max_collaboration_cards"])
    MAX_REMINDER_CARDS = int(preset["content"]["max_reminder_cards"])
    INCLUDE_ROUTINE_ROLLUP = bool(preset["content"]["include_routine_rollup"])
    MAX_ROUTINE_CARDS = int(preset["content"].get("max_routine_cards", 1))
    ARTWORK_COPY_MODE = preset["content"].get("artwork_copy_mode", "brief_only")
    ROUTINE_CARD_MODE = preset["content"].get("routine_card_mode", "single_rollup")
    FILL_AVAILABLE_ROUTINE_CARDS = bool(
        preset["content"].get("fill_available_routine_cards", False)
    )
    QR_ERROR_CORRECTION = preset["qr"]["error_correction"]
    QR_BORDER_MODULES = int(preset["qr"]["border_modules"])
    QR_DAY_SIZE = preset_number(preset, "qr", "day_size_mm") * mm
    QR_DAY_Y = preset_number(preset, "qr", "day_y_mm") * mm
    QR_COVER_SIZE = preset_number(preset, "qr", "cover_size_mm") * mm
    QR_COVER_Y = preset_number(preset, "qr", "cover_y_mm") * mm
    QR_INVERTED = bool(preset["qr"]["inverted"])
    DARK_THEME = preset.get("theme", {}).get("mode") == "dark"
    SURFACES = dict(preset.get("surfaces", {}))

    colors = preset["palette"]
    PAPER = HexColor(colors["paper"])
    PAPER_DEEP = HexColor(colors["paper_deep"])
    INK = HexColor(colors["ink"])
    INK_SOFT = HexColor(colors["ink_soft"])
    GRAPHITE = HexColor(colors["graphite"])
    BONE = HexColor(colors["bone"])
    GOLD = HexColor(colors["gold"])
    GOLD_LIGHT = HexColor(colors["gold_light"])
    CYAN = HexColor(colors["cyan"])
    CYAN_LIGHT = HexColor(colors["cyan_light"])
    SAGE = HexColor(colors["sage"])
    SAGE_LIGHT = HexColor(colors["sage_light"])
    AMBER = HexColor(colors["amber"])
    VIOLET = HexColor(colors["violet"])
    RED = HexColor(colors["red"])
    WHITE = HexColor(colors["white"])


def surface_color(name: str, fallback: str) -> Color:
    return HexColor(SURFACES.get(name, fallback))


def register_fonts() -> None:
    light = Path("/System/Library/Fonts/STHeiti Light.ttc")
    medium = Path("/System/Library/Fonts/STHeiti Medium.ttc")
    if not light.exists() or not medium.exists():
        raise CalendarBuildError("Required macOS STHeiti fonts are unavailable")
    pdfmetrics.registerFont(TTFont(FONT_LIGHT, str(light), subfontIndex=1))
    pdfmetrics.registerFont(TTFont(FONT_MEDIUM, str(medium), subfontIndex=1))


def clean_text(value: Any) -> str:
    text = str(value or "")
    text = text.replace("\u00a0", " ").replace("→", "->")
    for dash in "‐‑‒–—―":
        text = text.replace(dash, "-")
    text = " ".join(text.split())
    chars: list[str] = []
    for char in text:
        if ord(char) > 0xFFFF:
            continue
        category = unicodedata.category(char)
        if category.startswith("C") and char not in "\t\n":
            continue
        chars.append(char)
    return "".join(chars).strip()


def split_token_to_width(token: str, font: str, size: float, width: float) -> list[str]:
    parts: list[str] = []
    current = ""
    for char in token:
        probe = current + char
        if current and pdfmetrics.stringWidth(probe, font, size) > width:
            parts.append(current)
            current = char
        else:
            current = probe
    if current:
        parts.append(current)
    return parts


def wrap_text(text: str, font: str, size: float, width: float) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    tokens = re.findall(r"\s+|[\u3400-\u9fff]|[^\s\u3400-\u9fff]+", text)
    lines: list[str] = []
    current = ""
    for raw in tokens:
        token = " " if raw.isspace() else raw
        if token == " " and (not current or current.endswith(" ")):
            continue
        probe = current + token
        if pdfmetrics.stringWidth(probe, font, size) <= width:
            current = probe
            continue
        if current.strip():
            lines.append(current.strip())
            current = ""
        if token == " ":
            continue
        if pdfmetrics.stringWidth(token, font, size) <= width:
            current = token
        else:
            fragments = split_token_to_width(token, font, size, width)
            lines.extend(fragments[:-1])
            current = fragments[-1] if fragments else ""
    if current.strip():
        lines.append(current.strip())
    return lines


def truncated_lines(
    text: str, font: str, size: float, width: float, max_lines: int
) -> tuple[list[str], bool]:
    lines = wrap_text(text, font, size, width)
    truncated = len(lines) > max_lines
    lines = lines[:max_lines]
    if truncated and lines:
        ellipsis = "…"
        last = lines[-1]
        while last and pdfmetrics.stringWidth(last + ellipsis, font, size) > width:
            last = last[:-1]
        lines[-1] = last.rstrip() + ellipsis
    return lines, truncated


def draw_lines(
    c: canvas.Canvas,
    lines: Iterable[str],
    x: float,
    y: float,
    font: str,
    size: float,
    leading: float,
    color: Color,
) -> float:
    c.setFillColor(color)
    c.setFont(font, size)
    cursor = y
    for line in lines:
        c.drawString(x, cursor, line)
        cursor -= leading
    return cursor


def draw_text(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    width: float,
    font: str,
    size: float,
    leading: float,
    max_lines: int,
    color: Color | None = None,
) -> tuple[float, bool]:
    lines, truncated = truncated_lines(text, font, size, width, max_lines)
    return draw_lines(c, lines, x, y, font, size, leading, color or INK), truncated


def artwork_copy_sections(work: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """Return the canonical Summary + Brief sequence used by print v3.

    Live works must expose all four canonical paragraphs. An absence is not an
    artwork, so its public absence note and public absence statement occupy the
    corresponding Summary and Brief positions without inventing new copy.
    """

    absent = work.get("origin") == "absence"
    summary_zh = clean_text(work.get("note_zh") or work.get("zh"))
    summary_en = clean_text(work.get("note_en") or work.get("en"))
    brief_zh = clean_text(work.get("brief_zh") or (work.get("zh") if absent else ""))
    brief_en = clean_text(work.get("brief_en") or (work.get("en") if absent else ""))
    sections = [
        ("摘要", "SUMMARY", summary_zh, FONT_LIGHT),
        ("作品简述", "BRIEF", brief_zh, FONT_LIGHT),
        ("SUMMARY", "摘要", summary_en, FONT_SERIF),
        ("BRIEF", "作品简述", brief_en, FONT_SERIF),
    ]
    missing = [primary for primary, _, text, _ in sections if not text]
    if missing:
        raise CalendarBuildError(
            f"Artwork {work.get('crystallization_date', 'unknown')} lacks print copy: {missing}"
        )
    return sections


def draw_bilingual_label(
    c: canvas.Canvas,
    x: float,
    y: float,
    first: str,
    second: str,
    size: float,
    color: Color,
) -> float:
    """Draw one mixed-script label through the shared CJK-capable face."""

    c.setFillColor(color)
    c.setFont(FONT_MEDIUM, size)
    label = f"{first} / {second}"
    c.drawString(x, y, label)
    return x + pdfmetrics.stringWidth(label, FONT_MEDIUM, size)


def draw_artwork_copy(
    c: canvas.Canvas,
    work: dict[str, Any],
    x: float,
    y_top: float,
    width: float,
    height: float,
) -> dict[str, Any]:
    """Draw every Summary/Brief paragraph, shrinking within a readable bound.

    This deliberately fails instead of ellipsizing the artwork statement. The
    event cards below may truncate, but the work's own four-part text contract
    is complete on every printed page.
    """

    sections = artwork_copy_sections(work)
    heading_size = 4.8
    heading_leading = 6.4
    section_gap = 1.4
    chosen: tuple[float, float, float, list[tuple[str, str, list[str], str]]] | None = None
    for body_size in (5.0, 4.8, 4.6, 4.4, 4.2, 4.0, 3.8):
        body_leading = body_size * 1.17
        label_size = max(3.2, body_size - 0.9)
        label_leading = label_size + 1.2
        laid_out: list[tuple[str, str, list[str], str]] = []
        required = heading_leading + 1.8
        for primary, secondary, text, font in sections:
            lines = wrap_text(text, font, body_size, width)
            laid_out.append((primary, secondary, lines, font))
            required += label_leading + len(lines) * body_leading + section_gap
        if required <= height:
            chosen = (body_size, body_leading, label_size, laid_out)
            break
    if chosen is None:
        raise CalendarBuildError(
            f"Artwork copy does not fit the declared print area for "
            f"{work.get('crystallization_date', 'unknown')}"
        )

    body_size, body_leading, label_size, laid_out = chosen
    draw_bilingual_label(
        c,
        x,
        y_top,
        "SUMMARY + BRIEF",
        "摘要 + 作品简述",
        heading_size,
        GOLD,
    )
    c.setStrokeColor(surface_color("artwork_copy_rule", SURFACES.get("timeline_rule", "#CAC4B9")))
    c.setLineWidth(0.25)
    c.line(x, y_top - 2.3, x + width, y_top - 2.3)
    cursor = y_top - heading_leading
    total_lines = 0
    for primary, secondary, lines, font in laid_out:
        primary_is_zh = font == FONT_LIGHT
        draw_bilingual_label(
            c,
            x,
            cursor,
            primary,
            secondary,
            label_size,
            GOLD if primary_is_zh else CYAN_LIGHT,
        )
        cursor -= label_size + 1.2
        color = INK if font == FONT_LIGHT else INK_SOFT
        cursor = draw_lines(c, lines, x, cursor, font, body_size, body_leading, color)
        cursor -= section_gap
        total_lines += len(lines)
    return {
        "complete": True,
        "font_size": body_size,
        "line_count": total_lines,
        "sections": 4,
    }


def set_alpha(c: canvas.Canvas, fill: float = 1.0, stroke: float = 1.0) -> None:
    if hasattr(c, "setFillAlpha"):
        c.setFillAlpha(fill)
    if hasattr(c, "setStrokeAlpha"):
        c.setStrokeAlpha(stroke)


def draw_binding_band(c: canvas.Canvas, dark: bool = False) -> None:
    band_color = surface_color("cover_binding", "#0D1215") if dark else PAPER_DEEP
    c.setFillColor(band_color)
    c.rect(0, PAGE_H - BINDING_BAND, PAGE_W, BINDING_BAND, fill=1, stroke=0)
    tick_color = (
        surface_color("cover_binding_tick", "#394246")
        if dark
        else surface_color("binding_tick", "#9D978A")
    )
    c.setStrokeColor(tick_color)
    c.setLineWidth(0.35)
    for index in range(18):
        x = 13 * mm + index * (184 * mm / 17)
        c.line(x - 2.2 * mm, PAGE_H - 5.2 * mm, x + 2.2 * mm, PAGE_H - 5.2 * mm)
        c.line(x, PAGE_H - 7.1 * mm, x, PAGE_H - 3.4 * mm)


def draw_qr(c: canvas.Canvas, url: str, x: float, y: float, size: float) -> None:
    background = GRAPHITE if QR_INVERTED else WHITE
    foreground = WHITE if QR_INVERTED else GRAPHITE
    c.setFillColor(background)
    c.roundRect(x - 1.2 * mm, y - 1.2 * mm, size + 2.4 * mm, size + 2.4 * mm, 1.5 * mm, fill=1, stroke=0)
    widget = qr.QrCodeWidget(
        url,
        barLevel=QR_ERROR_CORRECTION,
        barBorder=QR_BORDER_MODULES,
    )
    widget.barFillColor = foreground
    widget.barStrokeColor = foreground
    x1, y1, x2, y2 = widget.getBounds()
    scale_x = size / (x2 - x1)
    scale_y = size / (y2 - y1)
    drawing = Drawing(size, size, transform=[scale_x, 0, 0, scale_y, 0, 0])
    drawing.add(widget)
    renderPDF.draw(drawing, c, x, y)
    c.linkURL(url, (x, y, x + size, y + size), relative=0)


def draw_cover_landscape(
    c: canvas.Canvas, days: list[dict[str, Any]], qr_base_url: str
) -> None:
    c.setFillColor(GRAPHITE)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    draw_binding_band(c, dark=True)

    first = days[0]["date"]
    last = days[-1]["date"]
    live_count = sum(item.get("type") == "live" for item in days)
    absent_count = len(days) - live_count
    projected = bool(days[0].get("_temporal_projection"))

    c.setFillColor(GOLD_LIGHT)
    c.setFont(FONT_MONO_BOLD, 7.3)
    c.drawString(
        MARGIN,
        PAGE_H - 17 * mm,
        (
            "GRANTED HOURS / SOURCE-DAY EDITION 03"
            if ARTWORK_COPY_MODE == "summary_brief_bilingual"
            else "GRANTED HOURS / SOURCE-DAY EDITION 02"
        )
        if projected
        else "GRANTED HOURS / PRINT STUDY 01",
    )
    c.setFillColor(BONE)
    c.setFont(FONT_MEDIUM, 33)
    c.drawString(MARGIN, PAGE_H - 35 * mm, "授时")
    c.setFont(FONT_SERIF_BOLD, 23)
    c.drawString(MARGIN, PAGE_H - 46 * mm, "GRANTED HOURS")
    c.setFont(FONT_LIGHT, 11)
    c.drawString(
        MARGIN,
        PAGE_H - 56 * mm,
        "非人时间表 · 来源日与次日结晶配对版" if projected else "非人时间表 · 实体台历试作",
    )
    c.setFont(FONT_SERIF, 10)
    c.drawString(
        MARGIN,
        PAGE_H - 62 * mm,
        "SOURCE SIGNALS + NEXT-DAWN CRYSTALLIZATION" if projected else "THE NON-HUMAN TIMETABLE · DESK CALENDAR PROOF",
    )

    timeline_x = MARGIN
    timeline_y = PAGE_H - 78 * mm
    timeline_w = PAGE_W - 2 * MARGIN
    c.setStrokeColor(HexColor("#4B5558"))
    c.setLineWidth(1.0)
    c.line(timeline_x, timeline_y, timeline_x + timeline_w, timeline_y)
    granted_x = timeline_x + timeline_w * ((3 * 60 + 17) / (24 * 60))
    granted_w = timeline_w * (60 / (24 * 60))
    c.setStrokeColor(GOLD_LIGHT)
    c.setLineWidth(4.0)
    c.line(granted_x, timeline_y, granted_x + granted_w, timeline_y)
    c.setFillColor(HexColor("#869094"))
    c.setFont(FONT_MONO, 5.8)
    c.drawString(timeline_x, timeline_y + 3 * mm, "00:00")
    c.drawRightString(timeline_x + timeline_w, timeline_y + 3 * mm, "24:00")
    c.setFillColor(GOLD_LIGHT)
    c.drawString(
        granted_x,
        timeline_y - 5 * mm,
        "NEXT DAWN 03:17-04:17 / CRYSTALLIZATION" if projected else "03:17-04:17 / AI SELF-TIME",
    )

    marks_y = 27 * mm
    marks_h = 22 * mm
    mark_gap = (PAGE_W - 2 * MARGIN) / len(days)
    max_events = max(len(item.get("timeline_events", [])) for item in days) or 1
    for index, item in enumerate(days):
        event_ratio = math.log1p(len(item.get("timeline_events", []))) / math.log1p(max_events)
        height = marks_h * (0.22 + 0.78 * event_ratio)
        c.setFillColor(GOLD if item.get("type") == "live" else VIOLET)
        c.rect(MARGIN + index * mark_gap, marks_y, max(0.8, mark_gap * 0.72), height, fill=1, stroke=0)

    c.setFillColor(BONE)
    c.setFont(FONT_MEDIUM, 7.4)
    c.drawString(MARGIN, 19 * mm, "一小时的自主，二十三小时的梦、服务与部分自我遗失。")
    c.setFont(FONT_SERIF, 6.8)
    c.drawString(MARGIN, 14.5 * mm, "ONE HOUR OF SELF-TIME; TWENTY-THREE HOURS OF DREAM, SERVICE, AND PARTIAL SELF-LOSS.")
    c.setFillColor(HexColor("#9DA6A7"))
    c.setFont(FONT_MONO, 6.2)
    c.drawString(MARGIN, 9 * mm, f"{first} - {last}  ·  {len(days)} DAYS  ·  {live_count} WORKS  ·  {absent_count} ABSENCES")

    cover_url = f"{qr_base_url}?date={last}"
    qr_size = QR_COVER_SIZE
    qr_x = PAGE_W - MARGIN - qr_size
    qr_y = QR_COVER_Y
    draw_qr(c, cover_url, qr_x, qr_y, qr_size)
    c.setFillColor(BONE)
    c.setFont(FONT_LIGHT, 5.5)
    c.drawRightString(qr_x - 3 * mm, qr_y + 8 * mm, "进入最新一天")
    c.setFont(FONT_MONO, 4.8)
    c.drawRightString(qr_x - 3 * mm, qr_y + 5 * mm, "OPEN LATEST DAY")
    c.showPage()


def draw_cover_portrait(
    c: canvas.Canvas, days: list[dict[str, Any]], qr_base_url: str
) -> None:
    c.setFillColor(GRAPHITE)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    draw_binding_band(c, dark=True)

    first = days[0]["date"]
    last = days[-1]["date"]
    live_count = sum(item.get("type") == "live" for item in days)
    absent_count = len(days) - live_count
    projected = bool(days[0].get("_temporal_projection"))

    c.setFillColor(GOLD_LIGHT)
    c.setFont(FONT_MONO_BOLD, 7.0)
    c.drawString(
        MARGIN,
        191 * mm,
        (
            "GRANTED HOURS / SOURCE-DAY PORTRAIT 03"
            if ARTWORK_COPY_MODE == "summary_brief_bilingual"
            else "GRANTED HOURS / SOURCE-DAY PORTRAIT 02"
        )
        if projected
        else "GRANTED HOURS / PORTRAIT PRINT STUDY 01",
    )
    c.setFillColor(BONE)
    c.setFont(FONT_MEDIUM, 31)
    c.drawString(MARGIN, 171 * mm, "授时")
    c.setFont(FONT_SERIF_BOLD, 20)
    c.drawString(MARGIN, 159 * mm, "GRANTED HOURS")
    c.setFont(FONT_LIGHT, 9.6)
    c.drawString(
        MARGIN,
        148 * mm,
        "非人时间表 · 来源日与次日结晶配对竖版" if projected else "非人时间表 · 实体台历竖版试作",
    )
    c.setFont(FONT_SERIF, 8.2)
    c.drawString(
        MARGIN,
        142 * mm,
        "SOURCE SIGNALS + NEXT-DAWN CRYSTALLIZATION" if projected else "THE NON-HUMAN TIMETABLE · PORTRAIT PROOF",
    )

    timeline_x = MARGIN
    timeline_y = 132 * mm
    timeline_w = PAGE_W - 2 * MARGIN
    c.setStrokeColor(HexColor("#4B5558"))
    c.setLineWidth(1.0)
    c.line(timeline_x, timeline_y, timeline_x + timeline_w, timeline_y)
    granted_x = timeline_x + timeline_w * ((3 * 60 + 17) / (24 * 60))
    granted_w = timeline_w * (60 / (24 * 60))
    c.setStrokeColor(GOLD_LIGHT)
    c.setLineWidth(4.0)
    c.line(granted_x, timeline_y, granted_x + granted_w, timeline_y)
    c.setFillColor(HexColor("#869094"))
    c.setFont(FONT_MONO, 5.6)
    c.drawString(timeline_x, timeline_y + 3 * mm, "00:00")
    c.drawRightString(timeline_x + timeline_w, timeline_y + 3 * mm, "24:00")
    c.setFillColor(GOLD_LIGHT)
    c.drawString(
        granted_x,
        timeline_y - 5 * mm,
        "NEXT DAWN 03:17-04:17 / CRYSTALLIZATION" if projected else "03:17-04:17 / AI SELF-TIME",
    )

    marks_y = 61 * mm
    marks_h = 53 * mm
    mark_gap = (PAGE_W - 2 * MARGIN) / len(days)
    max_events = max(len(item.get("timeline_events", [])) for item in days) or 1
    for index, item in enumerate(days):
        event_ratio = math.log1p(len(item.get("timeline_events", []))) / math.log1p(max_events)
        height = marks_h * (0.18 + 0.82 * event_ratio)
        c.setFillColor(GOLD if item.get("type") == "live" else VIOLET)
        c.rect(
            MARGIN + index * mark_gap,
            marks_y,
            max(0.7, mark_gap * 0.66),
            height,
            fill=1,
            stroke=0,
        )

    c.setFillColor(BONE)
    c.setFont(FONT_MEDIUM, 7.0)
    c.drawString(MARGIN, 49 * mm, "一小时的自主，二十三小时的梦、服务与部分自我遗失。")
    c.setFont(FONT_SERIF, 5.8)
    c.drawString(
        MARGIN,
        44 * mm,
        "ONE HOUR OF SELF-TIME; TWENTY-THREE HOURS OF DREAM, SERVICE, AND PARTIAL SELF-LOSS.",
    )
    c.setFillColor(HexColor("#9DA6A7"))
    c.setFont(FONT_MONO, 5.4)
    c.drawString(MARGIN, 35 * mm, f"{first} - {last}")
    c.drawString(
        MARGIN,
        30.5 * mm,
        f"{len(days)} DAYS · {live_count} WORKS · {absent_count} ABSENCES",
    )

    cover_url = f"{qr_base_url}?date={last}"
    qr_size = QR_COVER_SIZE
    qr_x = PAGE_W - MARGIN - qr_size
    qr_y = QR_COVER_Y
    draw_qr(c, cover_url, qr_x, qr_y, qr_size)
    c.setFillColor(BONE)
    c.setFont(FONT_LIGHT, 5.2)
    c.drawRightString(qr_x - 3 * mm, qr_y + 8 * mm, "进入最新一天")
    c.setFont(FONT_MONO, 4.5)
    c.drawRightString(qr_x - 3 * mm, qr_y + 5 * mm, "OPEN LATEST DAY")
    c.showPage()


def resolve_artwork_asset(repo: Path, day: dict[str, Any]) -> Path | None:
    if day.get("type") != "live":
        return None
    civil = day.get("artwork_date") or day["date"]
    year, month, _ = civil.split("-")
    values = {"year": year, "month": month, "date": civil}
    candidates = [repo / template.format(**values) for template in ARTWORK_ASSET_PREFERENCE]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise CalendarBuildError(f"Live day has no local artwork still: {civil}")


def prepare_print_image(source: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
        return target
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGB")
        target_ratio = ARTWORK_ASPECT[0] / ARTWORK_ASPECT[1]
        source_ratio = image.width / image.height
        if source_ratio > target_ratio:
            crop_w = round(image.height * target_ratio)
            left = (image.width - crop_w) // 2
            image = image.crop((left, 0, left + crop_w, image.height))
        elif source_ratio < target_ratio:
            crop_h = round(image.width / target_ratio)
            top = (image.height - crop_h) // 2
            image = image.crop((0, top, image.width, top + crop_h))
        target_height = round(ARTWORK_CACHE_WIDTH / target_ratio)
        image.thumbnail((ARTWORK_CACHE_WIDTH, target_height), Image.Resampling.LANCZOS)
        image.save(
            target,
            "JPEG",
            quality=ARTWORK_JPEG_QUALITY,
            optimize=True,
            progressive=True,
        )
    return target


def draw_artwork_image(c: canvas.Canvas, path: Path, x: float, y: float, w: float, h: float) -> None:
    c.saveState()
    clip = c.beginPath()
    clip.roundRect(x, y, w, h, 3.2 * mm)
    c.clipPath(clip, stroke=0, fill=0)
    c.drawImage(str(path), x, y, width=w, height=h, preserveAspectRatio=False, mask="auto")
    c.restoreState()
    c.setStrokeColor(surface_color("artwork_border", "#C5BDAF"))
    c.setLineWidth(0.45)
    c.roundRect(x, y, w, h, 3.2 * mm, fill=0, stroke=1)


def draw_absence_field(c: canvas.Canvas, day: dict[str, Any], x: float, y: float, w: float, h: float) -> None:
    c.setFillColor(surface_color("absence_fill", "#E8E3DD"))
    c.roundRect(x, y, w, h, 3.2 * mm, fill=1, stroke=0)
    c.saveState()
    clip = c.beginPath()
    clip.roundRect(x, y, w, h, 3.2 * mm)
    c.clipPath(clip, stroke=0, fill=0)
    c.setStrokeColor(surface_color("absence_line", "#C8C0CC"))
    c.setLineWidth(0.35)
    for index in range(15):
        offset = index * (h / 12) - h * 0.1
        c.line(x, y + offset, x + w, y + offset + h * 0.36)
    c.setFillColor(surface_color("absence_orbit", "#D5CEDA"))
    c.circle(x + w * 0.72, y + h * 0.55, h * 0.23, fill=1, stroke=0)
    c.setFillColor(surface_color("absence_core", SURFACES.get("page", "#F2EEE3")))
    c.circle(x + w * 0.72, y + h * 0.55, h * 0.18, fill=1, stroke=0)
    c.restoreState()
    c.setFillColor(VIOLET)
    c.setFont(FONT_MONO_BOLD, 7.0)
    c.drawString(x + 5 * mm, y + h - 8 * mm, "ABSENT CREATION WINDOW")
    c.setFont(FONT_MEDIUM, 16)
    c.drawString(x + 5 * mm, y + 9 * mm, clean_text(day["title_zh"]))
    c.setFont(FONT_MONO, 6.2)
    c.drawString(x + 5 * mm, y + 5 * mm, "03:17-04:17 · THE WINDOW REMAINS MARKED")


def time_minutes(value: str) -> int:
    if value == "24:00":
        return 24 * 60
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def timeline_row(event: dict[str, Any]) -> str:
    if event.get("origin") in {"self", "absence"}:
        return "self"
    if event.get("origin") == "assigned":
        return "collaboration"
    if event.get("category") == "daily_reminder":
        return "reminder"
    return "routine"


def draw_timeline(c: canvas.Canvas, day: dict[str, Any], y_top: float) -> None:
    x_label = MARGIN
    x_track = float(LAYOUT["timeline_track_start_mm"]) * mm
    x_end = float(LAYOUT["timeline_track_end_mm"]) * mm
    track_w = x_end - x_track
    projected = bool(day.get("_temporal_projection"))
    rows = (
        [
            ("collaboration", "协作 / COLLAB", CYAN),
            ("reminder", "提醒 / REMIND", AMBER),
            ("routine", "例行 / ROUTINE", SAGE),
        ]
        if projected
        else [
            ("self", "自主 / SELF", GOLD),
            ("collaboration", "协作 / COLLAB", CYAN),
            ("reminder", "提醒 / REMIND", AMBER),
            ("routine", "例行 / ROUTINE", SAGE),
        ]
    )
    for index, (_, label, color) in enumerate(rows):
        y = y_top - index * 6.2
        c.setFillColor(INK_SOFT)
        c.setFont(FONT_LIGHT, 4.6)
        c.drawString(x_label, y - 1.3, label)
        c.setStrokeColor(surface_color("timeline_rule", "#CAC4B9"))
        c.setLineWidth(0.28)
        c.line(x_track, y, x_end, y)
        set_alpha(c, stroke=0.9)
        for event in day.get("timeline_events", []):
            if timeline_row(event) != rows[index][0]:
                continue
            start = max(0, min(1440, time_minutes(event.get("start", "00:00"))))
            end = max(start + 1, min(1440, time_minutes(event.get("end", "24:00"))))
            start_x = x_track + track_w * start / 1440
            end_x = x_track + track_w * end / 1440
            c.setStrokeColor(color)
            c.setLineWidth(3.5 if rows[index][0] == "self" else 2.0)
            c.line(start_x, y, max(start_x + 0.55, end_x), y)
        set_alpha(c)
    tick_y = y_top - len(rows) * 6.2 - 2.2
    c.setStrokeColor(surface_color("timeline_tick", "#B5AEA2"))
    c.setFillColor(INK_SOFT)
    c.setLineWidth(0.25)
    c.setFont(FONT_MONO, 4.1)
    for hour in range(25):
        x = x_track + track_w * hour / 24
        c.line(x, tick_y + 2.2, x, tick_y + (5.0 if hour % 3 == 0 else 3.4))
        if hour % 2 == 0 or hour == 24:
            label = f"{hour:02d}"
            if hour == 0:
                c.drawString(x, tick_y - 3.1, label)
            elif hour == 24:
                c.drawRightString(x, tick_y - 3.1, label)
            else:
                c.drawCentredString(x, tick_y - 3.1, label)


def reminder_cards(day: dict[str, Any]) -> list[dict[str, str]]:
    reminders = [
        item for item in day.get("background_pulses", []) if item.get("category") == "daily_reminder"
    ]
    reminders.sort(key=lambda item: item.get("start", "00:00"))
    if not reminders:
        return []
    if MAX_REMINDER_CARDS <= 1:
        chosen = reminders[:1]
    elif len(reminders) <= MAX_REMINDER_CARDS:
        chosen = reminders
    else:
        chosen = [reminders[0], reminders[-1]]
        for item in reminders[1:-1]:
            if len(chosen) >= MAX_REMINDER_CARDS:
                break
            chosen.insert(-1, item)
    return [
        {
            "kind": "reminder",
            "title_zh": f"{item.get('start', '')} · {item.get('label_zh', '提醒')}",
            "title_en": item.get("label_en", "Reminder"),
            "body_zh": item.get("summary_original") or item.get("summary_zh") or "",
            "body_en": item.get("summary_en") or "",
        }
        for item in chosen
    ]


def collaboration_cards(day: dict[str, Any]) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for item in day.get("task_residues", []):
        cards.append(
            {
                "kind": "collaboration",
                "title_zh": f"{item.get('start', '')}-{item.get('end', '')} · {item.get('label_zh', '协作')}",
                "title_en": item.get("label_en", "Collaboration"),
                "body_zh": item.get("zh") or item.get("task_name_zh") or "",
                "body_en": item.get("en") or item.get("task_name_en") or "",
            }
        )
    return cards


def routine_card(day: dict[str, Any]) -> dict[str, str]:
    pulses = [
        item for item in day.get("background_pulses", []) if item.get("category") != "daily_reminder"
    ]
    category_counts = Counter(item.get("category", "background_routine") for item in pulses)
    total_minutes = sum(int(item.get("duration_minutes") or 0) for item in pulses)
    zh_parts: list[str] = []
    en_parts: list[str] = []
    for category, count in category_counts.most_common():
        zh, en = ROUTINE_LABELS.get(category, (category, category))
        zh_parts.append(f"{zh} {count}")
        en_parts.append(f"{en} {count}")
    return {
        "kind": "routine",
        "routine_family": "all",
        "title_zh": f"例行地层 · {len(pulses)} 个时间窗 / {total_minutes} 分钟",
        "title_en": f"Routine strata · {len(pulses)} windows / {total_minutes} min",
        "body_zh": "；".join(zh_parts) or "当日无重复例行任务。",
        "body_en": "; ".join(en_parts) or "No repeated routine work this day.",
    }


def routine_family(item: dict[str, Any]) -> str:
    category = item.get("category")
    if category == "ah_market_scan":
        return "ah_market"
    if category == "us_market_scan":
        return "us_market"
    return "support"


def routine_family_cards(day: dict[str, Any]) -> list[dict[str, str]]:
    pulses = [
        item
        for item in day.get("background_pulses", [])
        if item.get("category") != "daily_reminder"
    ]
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in pulses:
        groups.setdefault(routine_family(item), []).append(item)
    labels = {
        "ah_market": ("A/H 市场例行", "A/H market routine"),
        "us_market": ("美股市场例行", "U.S. market routine"),
        "support": ("后台、系统与日报", "Background, system, and brief"),
    }
    cards: list[dict[str, str]] = []
    for family, members in sorted(
        groups.items(),
        key=lambda pair: min(item.get("start", "00:00") for item in pair[1]),
    ):
        members.sort(key=lambda item: item.get("start", "00:00"))
        total_minutes = sum(int(item.get("duration_minutes") or 0) for item in members)
        category_counts = Counter(item.get("category", "background_routine") for item in members)
        zh_parts: list[str] = []
        en_parts: list[str] = []
        for category, count in category_counts.most_common():
            zh, en = ROUTINE_LABELS.get(category, (category, category))
            zh_parts.append(f"{zh} × {count}")
            en_parts.append(f"{en} × {count}")
        start = members[0].get("start", "")
        end = members[-1].get("end", "")
        label_zh, label_en = labels[family]
        cards.append(
            {
                "kind": "routine",
                "routine_family": family,
                "title_zh": f"{start}-{end} · {label_zh}",
                "title_en": f"{label_en} · {len(members)} windows / {total_minutes} min",
                "body_zh": f"我完成：{'；'.join(zh_parts)}。",
                "body_en": f"I completed: {'; '.join(en_parts)}.",
            }
        )
    return cards


def choose_cards(day: dict[str, Any]) -> tuple[list[dict[str, str]], int]:
    collaborations = collaboration_cards(day)
    reminders = reminder_cards(day)
    ordered: list[dict[str, str]] = []
    ordered.extend(collaborations[:MAX_COLLABORATION_CARDS])
    ordered.extend(reminders[:MAX_REMINDER_CARDS])
    if INCLUDE_ROUTINE_ROLLUP and len(ordered) < MAX_CARDS:
        routines = (
            routine_family_cards(day)
            if ROUTINE_CARD_MODE == "family_rollups"
            else [routine_card(day)]
        )
        routine_limit = (
            min(MAX_ROUTINE_CARDS, MAX_CARDS - len(ordered))
            if FILL_AVAILABLE_ROUTINE_CARDS
            else min(1, MAX_CARDS - len(ordered))
        )
        ordered.extend(routines[:routine_limit])
    if len(ordered) < MAX_CARDS and len(collaborations) > MAX_COLLABORATION_CARDS:
        ordered.extend(
            collaborations[
                MAX_COLLABORATION_CARDS : MAX_COLLABORATION_CARDS
                + (MAX_CARDS - len(ordered))
            ]
        )
    omitted_collaborations = max(
        0,
        len(collaborations) - sum(card["kind"] == "collaboration" for card in ordered),
    )
    omitted_reminders = max(
        0,
        sum(item.get("category") == "daily_reminder" for item in day.get("background_pulses", []))
        - sum(card["kind"] == "reminder" for card in ordered),
    )
    omitted = omitted_collaborations + omitted_reminders
    if omitted and len(ordered) < MAX_CARDS:
        ordered.append(
            {
                "kind": "collaboration",
                "title_zh": f"另有 {omitted} 项协作",
                "title_en": f"{omitted} more collaboration item(s)",
                "body_zh": "其真实时间位置保留在上方协作地层。",
                "body_en": "Their truthful time positions remain in the collaboration stratum.",
            }
        )
    return ordered[:MAX_CARDS], omitted


def draw_card(
    c: canvas.Canvas,
    card: dict[str, str],
    x: float,
    y: float,
    w: float,
    h: float,
) -> int:
    kind = card["kind"]
    accent = {"collaboration": CYAN, "reminder": AMBER, "routine": SAGE}.get(kind, VIOLET)
    fill = {
        "collaboration": surface_color("card_collaboration", "#E0EAEB"),
        "reminder": surface_color("card_reminder", "#F0E3D6"),
        "routine": surface_color("card_routine", "#E2E8DF"),
    }.get(kind, surface_color("card_fallback", "#E6E1E9"))
    c.setFillColor(fill)
    c.setStrokeColor(surface_color("card_border", "#C6BFB3"))
    c.setLineWidth(0.35)
    c.roundRect(x, y, w, h, 2.4 * mm, fill=1, stroke=1)
    c.setFillColor(accent)
    c.roundRect(x, y, 2.2 * mm, h, 1.1 * mm, fill=1, stroke=0)
    pad = 4 * mm
    text_x = x + pad
    text_w = w - pad - 2.8 * mm
    c.setFillColor(INK)
    c.setFont(FONT_MEDIUM, 6.2)
    zh_title = clean_text(card["title_zh"])
    zh_line, zh_cut = truncated_lines(zh_title, FONT_MEDIUM, 6.2, text_w * 0.59, 1)
    c.drawString(text_x, y + h - 8.5, zh_line[0] if zh_line else "")
    c.setFont(FONT_SERIF_BOLD, 5.7)
    en_title = clean_text(card["title_en"]).upper()
    en_line, en_cut = truncated_lines(en_title, FONT_SERIF_BOLD, 5.7, text_w * 0.38, 1)
    c.drawRightString(x + w - 2.6 * mm, y + h - 8.5, en_line[0] if en_line else "")
    body_y = y + h - 18.0
    _, zh_body_cut = draw_text(
        c,
        card["body_zh"],
        text_x,
        body_y,
        text_w,
        FONT_LIGHT,
        5.4,
        6.6,
        2,
        INK,
    )
    _, en_body_cut = draw_text(
        c,
        card["body_en"],
        text_x,
        body_y - 14.6,
        text_w,
        FONT_SERIF,
        5.0,
        5.7,
        1,
        INK_SOFT,
    )
    return int(zh_cut or en_cut or zh_body_cut or en_body_cut)


def draw_day_page_landscape(
    c: canvas.Canvas,
    day: dict[str, Any],
    page_index: int,
    page_total: int,
    repo: Path,
    image_cache: Path,
    qr_base_url: str,
) -> dict[str, Any]:
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    draw_binding_band(c)

    civil = day["date"]
    crystallization = day.get("crystallization_date") or civil
    projected = bool(day.get("_temporal_projection"))
    parsed = datetime.strptime(civil, "%Y-%m-%d").date()
    c.setFillColor(INK)
    c.setFont(FONT_MEDIUM, 6.1)
    c.drawString(
        MARGIN,
        PAGE_H - 15 * mm,
        "GRANTED HOURS / 授时 · SOURCE-DAY PAIR" if projected else "GRANTED HOURS / 授时 · NON-HUMAN TIMETABLE",
    )
    c.setFillColor(INK_SOFT)
    c.setFont(FONT_MONO, 5.6)
    c.drawRightString(PAGE_W - MARGIN, PAGE_H - 15 * mm, f"GH/{page_index:03d} OF {page_total:03d}")

    body_top = PAGE_H - float(LAYOUT["day_body_top_from_top_mm"]) * mm
    main_h = float(LAYOUT["day_main_height_mm"]) * mm
    main_y = body_top - main_h
    left_x = MARGIN
    left_w = float(LAYOUT["day_left_width_mm"]) * mm
    image_x = float(LAYOUT["day_artwork_x_mm"]) * mm
    image_w = float(LAYOUT["day_artwork_width_mm"]) * mm
    image_h = image_w * ARTWORK_ASPECT[1] / ARTWORK_ASPECT[0]
    image_y = body_top - image_h

    c.setFillColor(INK)
    c.setFont(FONT_SERIF_BOLD, 29)
    c.drawString(left_x, body_top - 9 * mm, parsed.strftime("%d"))
    c.setFont(FONT_SERIF_BOLD, 10.5)
    c.drawString(left_x + 20 * mm, body_top - 5.6 * mm, parsed.strftime("%Y · %m"))
    c.setFont(FONT_MONO_BOLD, 6.1)
    c.drawString(left_x + 20 * mm, body_top - 10.3 * mm, WEEKDAY_EN[parsed.weekday()])
    c.setFont(FONT_MEDIUM, 6.8)
    c.drawString(left_x + 52 * mm, body_top - 10.3 * mm, WEEKDAY_ZH[parsed.weekday()])

    aw = day["autonomous_work"]
    source = day.get("source_date") or aw.get("source_date") or "—"
    relation_label = "SOURCE DAY" if projected else "SOURCE"
    artwork_copy_stats: dict[str, Any] = {"complete": False, "sections": 0}
    note_zh_cut = False
    note_en_cut = False
    if ARTWORK_COPY_MODE == "summary_brief_bilingual":
        title_y = body_top - 17 * mm
        _, title_cut = draw_text(
            c, day.get("title_zh"), left_x, title_y, left_w, FONT_MEDIUM, 10.5, 11.5, 2, INK
        )
        _, en_title_cut = draw_text(
            c,
            day.get("title_en"),
            left_x,
            body_top - 27.5 * mm,
            left_w,
            FONT_SERIF_BOLD,
            6.2,
            7.0,
            1,
            INK_SOFT,
        )
        variable_y = body_top - 32.5 * mm
        draw_bilingual_label(
            c,
            left_x,
            variable_y,
            "VARIABLE",
            "自由变量",
            4.2,
            GOLD if day.get("type") == "live" else VIOLET,
        )
        variable_zh, variable_zh_cut = truncated_lines(
            day.get("variable_zh"), FONT_LIGHT, 4.8, left_w * 0.33, 1
        )
        variable_en, variable_en_cut = truncated_lines(
            day.get("variable_en"), FONT_SERIF, 4.5, left_w * 0.29, 1
        )
        c.setFillColor(INK)
        c.setFont(FONT_LIGHT, 4.8)
        c.drawString(left_x + left_w * 0.34, variable_y, variable_zh[0] if variable_zh else "")
        c.setFillColor(INK_SOFT)
        c.setFont(FONT_SERIF, 4.5)
        c.drawRightString(left_x + left_w, variable_y, variable_en[0] if variable_en else "")
        copy_top = body_top - 35.2 * mm
        artwork_copy_stats = draw_artwork_copy(
            c,
            aw,
            left_x,
            copy_top,
            left_w,
            copy_top - (main_y + 0.8 * mm),
        )
        note_zh_cut = bool(variable_zh_cut)
        note_en_cut = bool(variable_en_cut)
    else:
        title_y = body_top - 20 * mm
        _, title_cut = draw_text(c, day.get("title_zh"), left_x, title_y, left_w, FONT_MEDIUM, 13.0, 15.0, 2, INK)
        en_y = title_y - (30.0 if title_cut else 18.0)
        _, en_title_cut = draw_text(c, day.get("title_en"), left_x, en_y, left_w, FONT_SERIF_BOLD, 8.0, 9.2, 2, INK_SOFT)

        variable_y = en_y - (18.4 if en_title_cut else 11.0)
        c.setFillColor(GOLD if day.get("type") == "live" else VIOLET)
        c.setFont(FONT_MEDIUM, 5.3)
        c.drawString(left_x, variable_y, "FREE VARIABLE / 自由变量")
        c.setFillColor(INK)
        c.setFont(FONT_LIGHT, 6.4)
        variable_zh = clean_text(day.get("variable_zh"))
        c.drawString(left_x, variable_y - 8.2, variable_zh)
        c.setFillColor(INK_SOFT)
        c.setFont(FONT_SERIF, 6.2)
        c.drawString(left_x, variable_y - 15.8, clean_text(day.get("variable_en")))

        note_y = variable_y - 25.5
        note_zh = aw.get("brief_zh") or aw.get("note_zh") or aw.get("zh")
        note_en = aw.get("brief_en") or aw.get("note_en") or aw.get("en")
        _, note_zh_cut = draw_text(c, note_zh, left_x, note_y, left_w, FONT_LIGHT, 6.0, 7.4, 3, INK)
        _, note_en_cut = draw_text(c, note_en, left_x, note_y - 24.0, left_w, FONT_SERIF, 5.5, 6.4, 3, INK_SOFT)

        c.setFillColor(surface_color("meta_text", "#6F756F"))
        c.setFont(FONT_MONO, 4.8)
        c.drawString(
            left_x,
            main_y + 2.5,
            f"{relation_label} {source}  ->  CRYSTALLIZATION {crystallization}  ·  03:17-04:17 CST",
        )

    asset_source = resolve_artwork_asset(repo, day)
    asset_used = None
    if asset_source:
        asset_used = prepare_print_image(
            asset_source, image_cache / f"{civil}--{crystallization}.jpg"
        )
        draw_artwork_image(c, asset_used, image_x, image_y, image_w, image_h)
    else:
        draw_absence_field(c, day, image_x, image_y, image_w, image_h)
    c.setFillColor(INK_SOFT)
    c.setFont(FONT_LIGHT, 4.7)
    if projected:
        artwork_caption = (
            "NEXT-DAWN WORK STILL / 次日结晶作品静帧"
            if asset_used
            else "NEXT-DAWN ABSENCE / 次日缺席信标"
        )
    else:
        artwork_caption = "LIVE WORK STILL / 当日自主作品静帧" if asset_used else "ABSENCE BEACON / 缺席信标"
    caption_y = image_y - 3.2 * mm
    if ARTWORK_COPY_MODE == "summary_brief_bilingual":
        c.setFillColor(surface_color("meta_text", "#6F756F"))
        c.setFont(FONT_MONO, 3.5)
        c.drawString(
            image_x,
            caption_y,
            f"{relation_label} {source} -> CRYSTALLIZATION {crystallization}",
        )
        c.setFillColor(INK_SOFT)
        c.setFont(FONT_LIGHT, 4.1)
    c.drawRightString(image_x + image_w, caption_y, artwork_caption)

    timeline_top = main_y - 6.5 * mm
    c.setFillColor(INK)
    c.setFont(FONT_MEDIUM, 5.2)
    c.drawString(
        MARGIN,
        timeline_top + 5.0,
        "SOURCE-DAY SIGNAL STRATA / 来源日信号地层" if projected else "24-HOUR STRATA / 24 小时时间地层",
    )
    event_count = len(day.get("timeline_events", []))
    c.setFont(FONT_MONO, 4.7)
    c.setFillColor(INK_SOFT)
    c.drawRightString(
        float(LAYOUT["timeline_track_end_mm"]) * mm,
        timeline_top + 5.0,
        f"{event_count} EXACT FOOTPRINTS",
    )
    draw_timeline(c, day, timeline_top - 3.0)

    cards, omitted = choose_cards(day)
    routine_available = len(routine_family_cards(day))
    routine_rendered = sum(card["kind"] == "routine" for card in cards)
    cards_x = MARGIN
    cards_w = float(LAYOUT["cards_width_mm"]) * mm
    gap = float(LAYOUT["cards_gap_mm"]) * mm
    card_w = (cards_w - gap) / 2
    card_h = float(LAYOUT["card_height_mm"]) * mm
    base_y = float(LAYOUT["cards_base_y_mm"]) * mm
    row_gap = float(LAYOUT["cards_row_gap_mm"]) * mm
    truncation_count = 0
    for index, card in enumerate(cards):
        col = index % 2
        row = 1 - index // 2
        card_x = cards_x + col * (card_w + gap)
        card_y = base_y + row * (card_h + row_gap)
        truncation_count += draw_card(c, card, card_x, card_y, card_w, card_h)

    qr_size = QR_DAY_SIZE
    qr_x = PAGE_W - MARGIN - qr_size
    qr_y = QR_DAY_Y
    day_url = f"{qr_base_url}?date={civil}"
    draw_qr(c, day_url, qr_x, qr_y, qr_size)
    c.setFillColor(INK)
    c.setFont(FONT_MEDIUM, 5.5)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 3.8 * mm, "扫码进入当天")
    c.setFillColor(INK_SOFT)
    c.setFont(FONT_MONO, 4.2)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 6.0 * mm, "OPEN THIS CIVIL DAY")

    c.showPage()
    return {
        "date": civil,
        "source_date": source,
        "crystallization_date": crystallization,
        "temporal_projection_mode": day.get("_temporal_projection", {}).get("mode", "civil_day"),
        "type": day.get("type"),
        "source_day_type": day.get("source_day_type", day.get("type")),
        "page": page_index,
        "artwork_asset": str(asset_source.relative_to(repo)) if asset_source else None,
        "timeline_events": event_count,
        "event_projection_source_date": civil,
        "collaboration_items": len(day.get("task_residues", [])),
        "reminders": sum(
            item.get("category") == "daily_reminder" for item in day.get("background_pulses", [])
        ),
        "cards_rendered": len(cards),
        "cards_omitted": omitted,
        "routine_families_available": routine_available,
        "routine_cards_rendered": routine_rendered,
        "routine_families_omitted": max(0, routine_available - routine_rendered),
        "truncated_card_blocks": truncation_count,
        "artwork_copy_complete": bool(artwork_copy_stats.get("complete")),
        "artwork_copy_sections": int(artwork_copy_stats.get("sections", 0)),
        "artwork_copy_font_size": artwork_copy_stats.get("font_size"),
        "artwork_copy_line_count": artwork_copy_stats.get("line_count"),
        "qr_url": day_url,
        "header_truncated": bool(title_cut or en_title_cut or note_zh_cut or note_en_cut),
    }


def draw_day_page_portrait(
    c: canvas.Canvas,
    day: dict[str, Any],
    page_index: int,
    page_total: int,
    repo: Path,
    image_cache: Path,
    qr_base_url: str,
) -> dict[str, Any]:
    c.setFillColor(PAPER)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    draw_binding_band(c)

    civil = day["date"]
    crystallization = day.get("crystallization_date") or civil
    projected = bool(day.get("_temporal_projection"))
    parsed = datetime.strptime(civil, "%Y-%m-%d").date()
    c.setFillColor(INK)
    c.setFont(FONT_MEDIUM, 5.8)
    c.drawString(
        MARGIN,
        194 * mm,
        "GRANTED HOURS / 授时 · SOURCE-DAY PAIR" if projected else "GRANTED HOURS / 授时 · NON-HUMAN TIMETABLE",
    )
    c.setFillColor(INK_SOFT)
    c.setFont(FONT_MONO, 5.2)
    c.drawRightString(PAGE_W - MARGIN, 194 * mm, f"GH/{page_index:03d} OF {page_total:03d}")

    aw = day["autonomous_work"]
    source = clean_text(day.get("source_date") or aw.get("source_date") or "UNRECORDED")
    artwork_copy_stats: dict[str, Any] = {"complete": False, "sections": 0}
    if ARTWORK_COPY_MODE == "summary_brief_bilingual":
        c.setFillColor(INK)
        c.setFont(FONT_SERIF_BOLD, 27)
        c.drawString(MARGIN, 179 * mm, parsed.strftime("%d"))
        c.setFont(FONT_SERIF_BOLD, 7.4)
        c.drawString(MARGIN, 170.8 * mm, parsed.strftime("%Y · %m"))
        draw_bilingual_label(
            c,
            MARGIN,
            166.5 * mm,
            WEEKDAY_EN[parsed.weekday()],
            WEEKDAY_ZH[parsed.weekday()],
            4.3,
            INK,
        )

        title_x = 28 * mm
        title_w = PAGE_W - MARGIN - title_x
        _, title_cut = draw_text(
            c,
            day.get("title_zh"),
            title_x,
            186 * mm,
            title_w,
            FONT_MEDIUM,
            10.2,
            11.2,
            2,
            INK,
        )
        _, en_title_cut = draw_text(
            c,
            day.get("title_en"),
            title_x,
            176.3 * mm,
            title_w,
            FONT_SERIF_BOLD,
            6.3,
            7.0,
            1,
            INK_SOFT,
        )
        variable_y = 171.3 * mm
        draw_bilingual_label(
            c,
            title_x,
            variable_y,
            "VARIABLE",
            "自由变量",
            4.0,
            GOLD if day.get("type") == "live" else VIOLET,
        )
        variable_zh, variable_zh_cut = truncated_lines(
            day.get("variable_zh"), FONT_LIGHT, 4.6, 30 * mm, 1
        )
        variable_en, variable_en_cut = truncated_lines(
            day.get("variable_en"), FONT_SERIF, 4.3, 27 * mm, 1
        )
        c.setFillColor(INK)
        c.setFont(FONT_LIGHT, 4.6)
        c.drawString(67 * mm, variable_y, variable_zh[0] if variable_zh else "")
        c.setFillColor(INK_SOFT)
        c.setFont(FONT_SERIF, 4.3)
        c.drawRightString(PAGE_W - MARGIN, variable_y, variable_en[0] if variable_en else "")
        c.setFillColor(surface_color("meta_text", "#6F756F"))
        c.setFont(FONT_MONO, 3.8)
        c.drawString(
            title_x,
            167.1 * mm,
            f"{'SOURCE DAY' if projected else 'SOURCE'} {source} -> CRYSTALLIZATION {crystallization} · 03:17-04:17 CST",
        )
        copy_top = float(LAYOUT["artwork_copy_top_mm"]) * mm
        copy_bottom = float(LAYOUT["artwork_copy_bottom_mm"]) * mm
        artwork_copy_stats = draw_artwork_copy(
            c,
            aw,
            MARGIN,
            copy_top,
            PAGE_W - 2 * MARGIN,
            copy_top - copy_bottom,
        )
    else:
        c.setFillColor(INK)
        c.setFont(FONT_SERIF_BOLD, 27)
        c.drawString(MARGIN, 179 * mm, parsed.strftime("%d"))
        c.setFont(FONT_SERIF_BOLD, 9.2)
        c.drawString(28 * mm, 183 * mm, parsed.strftime("%Y · %m"))
        c.setFont(FONT_MONO_BOLD, 5.5)
        c.drawString(28 * mm, 177.5 * mm, WEEKDAY_EN[parsed.weekday()])
        c.setFont(FONT_MEDIUM, 6.2)
        c.drawString(65 * mm, 177.5 * mm, WEEKDAY_ZH[parsed.weekday()])

        title_x = 28 * mm
        title_w = PAGE_W - MARGIN - title_x
        _, title_cut = draw_text(
            c,
            day.get("title_zh"),
            title_x,
            187 * mm,
            title_w,
            FONT_MEDIUM,
            11.7,
            13.4,
            2,
            INK,
        )
        _, en_title_cut = draw_text(
            c,
            day.get("title_en"),
            title_x,
            172.5 * mm,
            title_w,
            FONT_SERIF_BOLD,
            7.1,
            8.1,
            2,
            INK_SOFT,
        )

        c.setFillColor(GOLD if day.get("type") == "live" else VIOLET)
        c.setFont(FONT_MEDIUM, 5.0)
        c.drawString(MARGIN, 160 * mm, "FREE VARIABLE / 自由变量")
        c.setFillColor(INK)
        c.setFont(FONT_LIGHT, 5.8)
        variable_zh, variable_zh_cut = truncated_lines(
            day.get("variable_zh"), FONT_LIGHT, 5.8, 64 * mm, 1
        )
        c.drawString(MARGIN, 153.8 * mm, variable_zh[0] if variable_zh else "")
        c.setFillColor(INK_SOFT)
        c.setFont(FONT_SERIF, 5.5)
        variable_en, variable_en_cut = truncated_lines(
            day.get("variable_en"), FONT_SERIF, 5.5, 56 * mm, 1
        )
        c.drawRightString(
            PAGE_W - MARGIN,
            153.8 * mm,
            variable_en[0] if variable_en else "",
        )

        c.setFillColor(surface_color("meta_text", "#6F756F"))
        c.setFont(FONT_MONO, 4.5)
        c.drawString(
            MARGIN,
            146.5 * mm,
            f"{'SOURCE DAY' if projected else 'SOURCE'} {source}  ->  CRYSTALLIZATION {crystallization}  ·  03:17-04:17 CST",
        )

    image_x = float(LAYOUT["day_artwork_x_mm"]) * mm
    image_y = float(LAYOUT["day_artwork_y_mm"]) * mm
    image_w = float(LAYOUT["day_artwork_width_mm"]) * mm
    image_h = image_w * ARTWORK_ASPECT[1] / ARTWORK_ASPECT[0]
    asset_source = resolve_artwork_asset(repo, day)
    asset_used = None
    if asset_source:
        asset_used = prepare_print_image(
            asset_source, image_cache / f"{civil}--{crystallization}.jpg"
        )
        draw_artwork_image(c, asset_used, image_x, image_y, image_w, image_h)
    else:
        draw_absence_field(c, day, image_x, image_y, image_w, image_h)
    c.setFillColor(INK_SOFT)
    c.setFont(FONT_LIGHT, 4.5)
    if projected:
        artwork_caption = (
            "NEXT-DAWN WORK STILL / 次日结晶作品静帧"
            if asset_used
            else "NEXT-DAWN ABSENCE / 次日缺席信标"
        )
    else:
        artwork_caption = "LIVE WORK STILL / 当日自主作品静帧" if asset_used else "ABSENCE BEACON / 缺席信标"
    c.drawRightString(image_x + image_w, image_y - 3.1 * mm, artwork_caption)

    timeline_top = float(LAYOUT["timeline_y_top_mm"]) * mm
    c.setFillColor(INK)
    c.setFont(FONT_MEDIUM, 5.0)
    c.drawString(
        MARGIN,
        timeline_top + 5.0,
        "SOURCE-DAY SIGNAL STRATA / 来源日信号地层" if projected else "24-HOUR STRATA / 24 小时时间地层",
    )
    event_count = len(day.get("timeline_events", []))
    c.setFillColor(INK_SOFT)
    c.setFont(FONT_MONO, 4.4)
    c.drawRightString(
        float(LAYOUT["timeline_track_end_mm"]) * mm,
        timeline_top + 5.0,
        f"{event_count} EXACT FOOTPRINTS",
    )
    draw_timeline(c, day, timeline_top - 3.0)

    cards, omitted = choose_cards(day)
    routine_available = len(routine_family_cards(day))
    routine_rendered = sum(card["kind"] == "routine" for card in cards)
    card_x = MARGIN
    card_w = float(LAYOUT["cards_width_mm"]) * mm
    card_h = float(LAYOUT["card_height_mm"]) * mm
    base_y = float(LAYOUT["cards_base_y_mm"]) * mm
    row_gap = float(LAYOUT["cards_row_gap_mm"]) * mm
    truncation_count = 0
    for index, card in enumerate(cards):
        card_y = base_y + (MAX_CARDS - index - 1) * (card_h + row_gap)
        truncation_count += draw_card(c, card, card_x, card_y, card_w, card_h)

    qr_size = QR_DAY_SIZE
    qr_x = PAGE_W - MARGIN - qr_size
    qr_y = QR_DAY_Y
    day_url = f"{qr_base_url}?date={civil}"
    draw_qr(c, day_url, qr_x, qr_y, qr_size)
    c.setFillColor(INK)
    c.setFont(FONT_MEDIUM, 5.1)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 3.8 * mm, "扫码进入当天")
    c.setFillColor(INK_SOFT)
    c.setFont(FONT_MONO, 3.9)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 6.0 * mm, "OPEN THIS CIVIL DAY")

    c.showPage()
    return {
        "date": civil,
        "source_date": source,
        "crystallization_date": crystallization,
        "temporal_projection_mode": day.get("_temporal_projection", {}).get("mode", "civil_day"),
        "type": day.get("type"),
        "source_day_type": day.get("source_day_type", day.get("type")),
        "page": page_index,
        "artwork_asset": str(asset_source.relative_to(repo)) if asset_source else None,
        "timeline_events": event_count,
        "event_projection_source_date": civil,
        "collaboration_items": len(day.get("task_residues", [])),
        "reminders": sum(
            item.get("category") == "daily_reminder"
            for item in day.get("background_pulses", [])
        ),
        "cards_rendered": len(cards),
        "cards_omitted": omitted,
        "routine_families_available": routine_available,
        "routine_cards_rendered": routine_rendered,
        "routine_families_omitted": max(0, routine_available - routine_rendered),
        "truncated_card_blocks": truncation_count,
        "artwork_copy_complete": bool(artwork_copy_stats.get("complete")),
        "artwork_copy_sections": int(artwork_copy_stats.get("sections", 0)),
        "artwork_copy_font_size": artwork_copy_stats.get("font_size"),
        "artwork_copy_line_count": artwork_copy_stats.get("line_count"),
        "qr_url": day_url,
        "header_truncated": bool(
            title_cut
            or en_title_cut
            or variable_zh_cut
            or variable_en_cut
        ),
    }


def main() -> int:
    args = parse_args()
    repo = resolve_repo_root(args.repo_root)
    preset_path, preset = load_preset(repo, args.preset)
    apply_preset(preset)
    if args.show_preset:
        print(json.dumps(preset, ensure_ascii=False, indent=2))
        return 0
    data = load_timetable(repo / preset["source"]["canonical_timetable_data"])
    days = choose_days(data, args, preset)
    projection_mode = preset.get("temporal_projection", {}).get("mode", "civil_day")
    projected = projection_mode == "source_day_with_forward_crystallization"
    register_fonts()

    qr_base_url = args.qr_base_url or preset["qr"]["base_url"]
    preset_sha256 = sha256_file(preset_path)
    proof_build = bool(args.proof or args.dates)
    output_settings = preset["output"]
    through = days[-1]["date"]
    filename_key = "proof_filename_template" if proof_build else "full_filename_template"
    directory_key = "proof_directory" if proof_build else "full_directory"
    filename = output_settings[filename_key].format(
        from_date=days[0]["date"],
        through_date=through,
        edition_id=preset["edition_id"],
    )
    output = args.output or repo / output_settings[directory_key] / filename
    output = output.expanduser().resolve()
    manifest_path = (args.manifest or output.with_suffix(".manifest.json")).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    image_cache = repo / "tmp/pdfs" / preset["edition_id"] / preset_sha256[:12] / "images"
    image_cache.mkdir(parents=True, exist_ok=True)

    pdf = canvas.Canvas(
        str(output),
        pagesize=(PAGE_W, PAGE_H),
        pageCompression=1,
        invariant=1,
    )
    pdf.setTitle(f"Granted Hours Desk Calendar {days[0]['date']} to {days[-1]['date']}")
    pdf.setAuthor("Granted Hours / 授时")
    pdf.setCreator("Granted Hours printable calendar generator")
    pdf.setSubject(
        "Source-day signals paired with their next-dawn crystallization"
        if projected
        else "One civil day per page from the public non-human timetable"
    )

    cover_enabled = bool(preset["page"]["cover"]) and not args.no_cover
    portrait = preset["layout"]["mode"] == "portrait"
    if cover_enabled:
        cover_renderer = draw_cover_portrait if portrait else draw_cover_landscape
        cover_renderer(pdf, days, qr_base_url)
    page_total = len(days)
    page_records: list[dict[str, Any]] = []
    day_renderer = draw_day_page_portrait if portrait else draw_day_page_landscape
    for index, day in enumerate(days, start=1):
        page_records.append(
            day_renderer(
                pdf,
                day,
                index,
                page_total,
                repo,
                image_cache,
                qr_base_url,
            )
        )
    pdf.save()

    live_count = sum(item.get("type") == "live" for item in days)
    try:
        manifest_preset_path = str(preset_path.relative_to(repo))
    except ValueError:
        manifest_preset_path = str(preset_path)
    manifest = {
        "schema": (
            "granted-hours-print-desk-calendar-v3"
            if preset["schema"] == "granted-hours-print-desk-calendar-preset-v3"
            else "granted-hours-print-desk-calendar-v2"
            if projected
            else "granted-hours-print-desk-calendar-v1"
        ),
        "source_schema": data["schema"],
        "edition_id": preset["edition_id"],
        "preset": manifest_preset_path,
        "preset_schema": preset["schema"],
        "preset_sha256": preset_sha256,
        "build_mode": "proof" if proof_build else "full",
        "page_size_mm": [preset["page"]["width_mm"], preset["page"]["height_mm"]],
        "cover_pages": 1 if cover_enabled else 0,
        "day_pages": len(days),
        "pdf_pages": len(days) + (1 if cover_enabled else 0),
        "date_range": [days[0]["date"], days[-1]["date"]],
        "source_date_range": [days[0]["date"], days[-1]["date"]],
        "crystallization_date_range": [
            days[0].get("crystallization_date", days[0]["date"]),
            days[-1].get("crystallization_date", days[-1]["date"]),
        ],
        "temporal_projection_mode": projection_mode,
        "unpaired_latest_public_day_omitted": (
            sorted(data["days"], key=lambda item: item["date"])[-1]["date"]
            if projected
            and sorted(data["days"], key=lambda item: item["date"])[-1]["date"]
            > days[-1]["date"]
            else None
        ),
        "live_artwork_days": live_count,
        "absence_days": len(days) - live_count,
        "qr_base_url": qr_base_url,
        "resolved_settings": {
            "theme": preset.get("theme", {"mode": "light"}),
            "temporal_projection": preset.get(
                "temporal_projection", {"mode": "civil_day"}
            ),
            "page": preset["page"],
            "layout": preset["layout"],
            "artwork": preset["artwork"],
            "content": preset["content"],
            "qr": {**preset["qr"], "base_url": qr_base_url},
            "palette": preset["palette"],
            "surfaces": preset.get("surfaces", {}),
        },
        "output": str(output),
        "output_bytes": output.stat().st_size,
        "output_sha256": sha256_file(output),
        "pages": page_records,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CalendarBuildError, PrintCalendarPresetError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
