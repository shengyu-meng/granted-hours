#!/usr/bin/env python3
"""Import an explicitly dated, public-only Yesterday's Flash work.

The source is a parent of sanitized YYYY-MM-DD directories, never private
residue packets. Only index.html, text-layer.md, the dated note, and manifest
are mirrored under yesterday-flash/live and yesterday-flash/assets. The
registry is separate from autonomous artwork; no music or preview is required.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METADATA = ROOT / "metadata" / "yesterday-flash-entries.json"
SCHEMA = "granted-hours-yesterday-flash-v1"
UNSAFE_PUBLIC_TEXT = {
    "URL": re.compile(
        r"(?i)(?:[a-z][a-z0-9+.-]*://|www\.|mailto:|(?<!:)//[\w.-]+\.[a-z]{2,})"
        r"|\b(?:[a-z0-9-]+\.)+(?:com|net|org|io|ai|cn|dev|app|xyz|edu|gov)\b"
    ),
    "email": re.compile(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", re.I),
    "credential": re.compile(
        r"(?i)\b(?:api[_ -]?key|access[_ -]?token|auth[_ -]?token|client[_ -]?secret|"
        r"password|passwd|authorization|bearer|secret[_ -]?key|private[_ -]?key)\b"
        r"|\b(?:token|secret|credentials?)\s*[\"']?\s*[:=]"
        r"|\b(?:sk-[a-z0-9_-]{12,}|gh[pousr]_[a-z0-9]{16,}|AKIA[A-Z0-9]{16})\b"
        r"|-----BEGIN .*PRIVATE KEY-----|密码|密钥|访问令牌"
    ),
    "cryptocurrency": re.compile(
        r"(?i)\b(?:crypto(?:currency|currencies)?|bitcoin|btc|ethereum|eth|solana|sol|"
        r"usdt|usdc|defi|nft|web3|blockchain|stablecoins?|altcoins?|tge|airdrop)\b"
        r"|\btoken\s*(?:economy|launch|radar)\b|加密货币|虚拟货币|数字货币|比特币|"
        r"以太坊|稳定币|区块链|新币狙击|币圈|代币|链上|加密资产|加密相关|加密币|Token[经济雷达]"
    ),
}


def checked_date(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("An explicit ISO civil date is required")
    date.fromisoformat(value)
    return value


def scan_public_text(text: str) -> None:
    normalized = unicodedata.normalize("NFKC", text)
    for _ in range(3):
        normalized = html.unescape(unquote(normalized))
    normalized = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", normalized)
    for category, pattern in UNSAFE_PUBLIC_TEXT.items():
        if pattern.search(normalized):
            raise ValueError(f"Public source rejected: {category}")


def flash_paths(day: str) -> dict[str, str]:
    checked_date(day)
    base = f"archive/{day[:4]}/{day[5:7]}/{day}/yesterday-flash"
    return {
        "live_url": f"{base}/live/",
        "note_url": f"{base}/assets/{day}-note.md",
        "text_layer_url": f"{base}/assets/text-layer.md",
    }


def validate_entry(entry: dict) -> None:
    day = checked_date(entry["date"])
    checked_date(entry["source_date"])
    required = {
        "crystallization_date": day,
        "label_zh": "昨日闪光",
        "label_en": "Yesterday's Flash",
        "start": "08:10",
        "end": "08:12",
        "timezone": "Asia/Shanghai",
        "duration_minutes": 2,
        "origin": "flash",
        "footprint_id": "yesterday-flash-001",
        **flash_paths(day),
    }
    if any(entry.get(key) != value for key, value in required.items()):
        raise ValueError("Invalid Yesterday's Flash date, slot, identity, or path")
    for field in ("title_zh", "title_en"):
        if not isinstance(entry.get(field), str) or not entry[field].strip():
            raise ValueError("Yesterday's Flash requires a bilingual picked title")
    scan_public_text(json.dumps(entry, ensure_ascii=False))


def load_entries(path: Path = DEFAULT_METADATA) -> dict[str, dict]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != SCHEMA or not isinstance(payload.get("entries"), list):
        raise ValueError("Invalid Yesterday's Flash registry")
    entries = {}
    for entry in payload["entries"]:
        validate_entry(entry)
        if entry["date"] in entries:
            raise ValueError("Duplicate Yesterday's Flash date")
        entries[entry["date"]] = entry
    return entries


def write_if_changed(path: Path, content: bytes) -> None:
    if path.exists() and path.read_bytes() == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def import_work(day: str, source: Path, root: Path = ROOT) -> dict:
    checked_date(day)
    source_day = source / day
    filenames = ("index.html", "text-layer.md", f"{day}-note.md", "manifest.json")
    contents = {}
    if source_day.is_symlink() or source_day.resolve() != source.resolve() / day:
        raise ValueError("Public source must not redirect outside its dated directory")
    for filename in filenames:
        path = source_day / filename
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Missing regular public file: {filename}")
        content = path.read_bytes()
        text = content.decode("utf-8")
        if not text.strip():
            raise ValueError(f"Empty public file: {filename}")
        scan_public_text(text)
        contents[filename] = content
    manifest = json.loads(contents["manifest.json"])
    if (
        manifest.get("crystallization_day") != day
        or manifest.get("not_free_roam") is not True
        or manifest.get("embedded_work") != "index.html"
        or manifest.get("text_layer") != "text-layer.md"
        or manifest.get("note") != f"{day}-note.md"
    ):
        raise ValueError("Public manifest does not describe this dated Flash work")
    note = contents[f"{day}-note.md"].decode("utf-8")
    title = re.match(r"# ([^\n]+?) / ([^\n]+)\n", note)
    if not title or title[1].strip() != manifest.get("picked_title"):
        raise ValueError("Public note must name the manifest's bilingual picked work")
    for label, expected in (("Source Day / 源日", manifest.get("source_date")), ("Crystallization Day / 结晶日", day)):
        if f"**{label}**: {expected}" not in note:
            raise ValueError("Public note and manifest dates disagree")
    entry = {
        "date": day,
        "source_date": checked_date(manifest.get("source_date")),
        "crystallization_date": day,
        "label_zh": "昨日闪光",
        "label_en": "Yesterday's Flash",
        "title_zh": title[1].strip(),
        "title_en": title[2].strip(),
        "start": "08:10",
        "end": "08:12",
        "timezone": "Asia/Shanghai",
        "duration_minutes": 2,
        "origin": "flash",
        "footprint_id": "yesterday-flash-001",
        **flash_paths(day),
    }
    validate_entry(entry)
    metadata = root / "metadata" / "yesterday-flash-entries.json"
    entries = load_entries(metadata)
    entries[day] = entry
    base = Path(entry["live_url"]).parent
    destinations = []
    for prefix in (root, root / "docs"):
        for filename, content in contents.items():
            directory = "live" if filename == "index.html" else "assets"
            destination = prefix / base / directory / filename
            if not destination.resolve().is_relative_to(root.resolve()):
                raise ValueError("Destination escapes the worktree")
            destinations.append((destination, content))
    for destination, content in destinations:
        write_if_changed(destination, content)
    write_if_changed(metadata, (json.dumps({"schema": SCHEMA, "entries": [entries[key] for key in sorted(entries)]}, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--source", required=True, type=Path, help="Parent of the sanitized dated public directories")
    args = parser.parse_args()
    try:
        entry = import_work(args.date, args.source)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"Yesterday's Flash import refused: {error}\n")
    print(f"Imported Yesterday's Flash for {entry['date']} (08:10–08:12 Asia/Shanghai).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
