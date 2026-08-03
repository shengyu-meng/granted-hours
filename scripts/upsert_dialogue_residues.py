#!/usr/bin/env python3
"""Validate and upsert public-safe dialogue residues into timetable history."""
from __future__ import annotations

import argparse
import errno
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from build_timetable_data import (
    EDUCATION_IDENTITY_RE,
    PRIVATE_OPERATIONAL_CONTEXT_RE,
    PROPOSAL_TITLE_CONTEXT_RE,
    REQUIRED_TAXONOMY,
    SENSITIVE_ASSIGNED_WORK_RE,
    SPOUSE_ACTIVITY_RE,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HISTORY = ROOT / "metadata" / "timetable-history.json"
DEFAULT_DAYS = ROOT / "metadata" / "days.json"
DEFAULT_ENTITY_DETECTOR = Path(__file__).resolve().with_name(
    "detect_reminder_entities.swift"
)
ENTITY_DETECTOR_TIMEOUT_SECONDS = 15

INPUT_SCHEMA = "granted-hours-dialogue-residues-v1"
HISTORY_SCHEMA = "granted-hours-timetable-history-v4"
LEGACY_HISTORY_SCHEMAS = {"granted-hours-timetable-history-v3"}
INPUT_KEYS = {"schema", "date", "provenance", "assigned_residues"}
INPUT_RESIDUE_KEYS = {"category", "en", "zh"}
OUTPUT_RESIDUE_KEYS = {
    "category",
    "en",
    "zh",
    "redaction_status",
    "redaction_count",
    "source_kind",
    "faithfulness",
}
FIXED_REDACTION_BLOCK = "████"
VANADIUM_TITANIUM_PROPER_NAME_RE = re.compile(r"(?:\b钒钛\b|钒钛)")
FIXED_PROPER_NAME_REDACTIONS = (
    (VANADIUM_TITANIUM_PROPER_NAME_RE, "vanadium-titanium proper name"),
)

URL_RE = re.compile(
    r"(?ix)"
    r"(?:\b(?:https?|ftp)://|\bwww\.)\S+"
    r"|\b(?:[A-Z0-9-]+\.)+(?:com|org|net|io|ai|cn|co|dev|app|edu|gov)"
    r"\b(?:/\S*)?"
)
LOCAL_PATH_RE = re.compile(
    r"""(?ix)
    (?<![A-Za-z0-9])/(?!/)[^\s'"`]+
    |(?:file://)
    |(?<![A-Za-z0-9])[A-Z]:[/\\][^\s'"`]+
    |(?<![A-Za-z0-9])(?:~[/\\]|\.[/\\]|\.\.[/\\])(?=\S)
    |(?<![A-Za-z0-9._~-])(?:[A-Za-z0-9._~-]+[/\\])+
        [A-Za-z0-9._~-]+(?![A-Za-z0-9._~-])
    |(?<![A-Za-z0-9])(?:\\\\|//)[^/\\\s'"`]+[/\\][^/\\\s'"`]+
    |(?:\$\{?HOME\}?|%USERPROFILE%)
    """
)
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_RE = re.compile(
    r"(?ix)"
    r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d(?:[- ]?\d){8}(?!\d)"
    r"|(?<!\w)\+\d(?:[- ]?\d){7,14}(?!\d)"
    r"|(?<!\w)(?:\+?1[- .]?)?(?:\(\d{3}\)|\d{3})"
    r"[- .]\d{3}[- .]\d{4}(?!\w)"
)
ACCOUNT_RE = re.compile(
    r"(?ix)"
    r"\b(?:account|acct|user)[ _-]?(?:id|number|no\.?)\b"
    r"|\baccount\b.{0,24}\b\d{4,}\b"
    r"|账户(?:号|ID|编号)|账号\s*[:：=]\s*[A-Za-z0-9_-]{4,}"
)
UUID_RE = re.compile(
    r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}\b"
)
OPAQUE_NUMERIC_ID_RE = re.compile(r"(?<!\d)\d{7,}(?!\d)")
SHORT_MIXED_ID_RE = re.compile(
    r"(?i)(?<![a-z0-9_-])(?=[a-z0-9_-]{4,19}(?![a-z0-9_-]))"
    r"(?=[a-z0-9_-]*[a-z])(?=[a-z0-9_-]*\d)[a-z0-9_-]+"
)
LABELED_ID_RE = re.compile(
    r"(?ix)\b(?:id|identifier|reference|session|message|chat|thread)"
    r"[ _:-]*[A-Za-z0-9_-]{4,}\b"
)
LONG_HASH_RE = re.compile(
    r"(?ix)"
    r"\b[0-9a-f]{16,}\b"
    r"|\b(?=[a-z0-9_-]{20,}\b)(?=[a-z0-9_-]*[a-z])"
    r"(?=[a-z0-9_-]*\d)[a-z0-9_-]+\b"
)
AWS_ACCESS_KEY_RE = re.compile(
    r"\b(?:AKIA|ASIA|AIDA|AROA|AIPA|ANPA|ANVA|ASCA)[A-Z0-9]{16}\b"
)
JWT_RE = re.compile(
    r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b"
)
PEM_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
)
TOKEN_RE = re.compile(
    r"(?ix)"
    r"\b(?:ghp_|github_pat_|sk-)[A-Za-z0-9_-]{8,}"
    r"|(?:api[_ -]?key|access[_ -]?token|aws[_ -]?secret[_ -]?access[_ -]?key|"
    r"token|password|secret|sk)"
    r"\s*[:：=]\s*[\"']?[A-Za-z0-9_./+~=-]{6,}"
)
AUTHORIZATION_RE = re.compile(
    r"(?ix)"
    r"\bauthorization\s*[:=]\s*(?=\S)\S+"
    r"|\b(?:bearer|basic|digest|token)\b\s*:?\s*"
    r"[A-Za-z0-9._~+/-]{8,}={0,2}(?![A-Za-z0-9._~+/-])"
)
HANDLE_RE = re.compile(r"(?<![\w@])@[A-Za-z0-9_]{2,}")
MARKET_TICKER_RE = re.compile(
    r"(?ix)"
    r"\b(?:ticker|stock\ symbol|security\ code)\b|股票代码|证券代码"
    r"|\$[A-Z]{1,6}\b"
    r"|\b[A-Z0-9]{1,10}\.(?:HK|SS|SH|SZ|US|NASDAQ|NYSE|AMEX)\b"
    r"|\b(?:NASDAQ|NYSE|AMEX|HKEX|SSE|SZSE|SH|SZ|HK|US):"
    r"[A-Z0-9.]{1,10}\b"
)
FINANCE_LABELED_SYMBOL_RE = re.compile(
    r"(?ix)"
    r"\b(?:ticker|stock(?:\ symbol)?|security(?:\ code)?|equity)"
    r"\s*[:=#-]?\s*[A-Z]{1,6}\b"
)
CN_STOCK_CODE_RE = re.compile(
    r"(?ix)"
    r"(?:finance|financial|market|stock|equity|security|portfolio|position|"
    r"holding|investment|trading|股票|证券|持仓|仓位|账户|投资|基金|市场)"
    r".{0,48}(?<!\d)\d{4,6}(?!\d)"
    r"|(?<!\d)\d{4,6}(?!\d).{0,48}"
    r"(?:finance|financial|market|stock|equity|security|portfolio|position|"
    r"holding|investment|trading|股票|证券|持仓|仓位|账户|投资|基金|市场)"
)
UPPERCASE_TICKER_RE = re.compile(r"\b[A-Z]{2,6}\b")
FINANCE_CONTEXT_RE = re.compile(
    r"(?ix)\b(?:finance|financial|market|stock|equity|security|portfolio|position|"
    r"holding|investment|trading)\b|股票|证券|持仓|仓位|账户|投资|基金|市场"
)
TECHNICAL_ACRONYM_ALLOWLIST = {
    "AI",
    "API",
    "CD",
    "CI",
    "CLI",
    "CPU",
    "CSV",
    "CSS",
    "DB",
    "DOM",
    "GIF",
    "GPU",
    "HTML",
    "HTTP",
    "HTTPS",
    "IDE",
    "JSON",
    "JS",
    "LLM",
    "NLP",
    "PDF",
    "PNG",
    "PR",
    "QA",
    "RAG",
    "SDK",
    "SQL",
    "SSH",
    "SVG",
    "TDD",
    "TLS",
    "TSV",
    "UI",
    "URL",
    "UTC",
    "UX",
    "XML",
}
EXCLUDED_SCOPE_RE = re.compile(
    r"(?ix)"
    r"\b(?:spouses?|wife|wives|husbands?|feishu|groups?|chats?|channels?|topics?|mba|"
    r"schools?|universit(?:y|ies)|holdings?|positions?)\b"
    r"|配偶|妻子|丈夫|飞书|群聊|频道|话题|群|学校|大学|持仓|账户"
)
FEISHU_F_MARKER_RE = re.compile(
    r"(?<![A-Za-z0-9])F(?![A-Za-z0-9])"
)
PRIVATE_OPS_SCOPE_RE = re.compile(
    r"(?i)\b(?:Hermes|OpenClaw)\b"
)
PRIVATE_IDENTIFIER_RE = re.compile(
    r"(?ix)"
    r"\b(?:openclaw|hermes)\b.{0,80}"
    r"\b(?:agent|skill|workflow|watchdog|host|state\.db|session|private|"
    r"credential|cron)\b"
    r"|(?:wechat|微信).{0,64}"
    r"(?:local\ history|本地历史|incremental\ messages|增量消息|"
    r"private\ chats|私聊)"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    """Atomically replace JSON without following the destination symlink."""
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = 0o644
    try:
        destination_stat = os.lstat(path)
    except FileNotFoundError:
        pass
    else:
        if stat.S_ISREG(destination_stat.st_mode):
            mode = stat.S_IMODE(destination_stat.st_mode)

    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(descriptor, mode)
        output_file = os.fdopen(descriptor, "w", encoding="utf-8")
        descriptor = -1
        with output_file:
            output_file.write(serialized)
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def _fsync_directory(directory: Path) -> None:
    """Persist a rename when directory fsync is available on this platform."""
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(directory, flags)
    except OSError as error:
        if error.errno in {errno.EINVAL, errno.ENOTSUP, errno.EACCES}:
            return
        raise
    try:
        try:
            os.fsync(descriptor)
        except OSError as error:
            if error.errno not in {errno.EINVAL, errno.ENOTSUP}:
                raise
    finally:
        os.close(descriptor)


def parse_iso_date(value: object, label: str) -> str:
    require(isinstance(value, str), f"{label} must be a string")
    require(
        re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is not None,
        f"{label} must use YYYY-MM-DD",
    )
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{label} is not a real calendar date: {value}") from error
    require(parsed.isoformat() == value, f"{label} must use canonical ISO format")
    return value


def load_days(path: Path) -> set[str]:
    source = read_json(path)
    require(isinstance(source, list), "days.json must contain a list")
    valid_dates = set()
    for index, entry in enumerate(source):
        require(isinstance(entry, dict), f"days.json entry {index + 1} must be an object")
        day_date = parse_iso_date(entry.get("date"), f"days.json entry {index + 1} date")
        require(day_date not in valid_dates, f"days.json contains duplicate date: {day_date}")
        valid_dates.add(day_date)
    return valid_dates


def load_history(path: Path) -> dict:
    """Load the current history document and migrate the supported legacy schema."""
    if not path.exists():
        return {"schema": HISTORY_SCHEMA, "days": []}
    source = read_json(path)
    require(isinstance(source, dict), "History must be an object")
    require(
        source.get("schema") in {HISTORY_SCHEMA, *LEGACY_HISTORY_SCHEMAS},
        f"History schema must be {HISTORY_SCHEMA} or a supported legacy schema",
    )
    days = source.get("days")
    require(isinstance(days, list), "History days must be a list")
    seen_dates = set()
    for index, entry in enumerate(days):
        require(isinstance(entry, dict), f"History entry {index + 1} must be an object")
        day_date = parse_iso_date(entry.get("date"), f"History entry {index + 1} date")
        require(day_date not in seen_dates, f"Duplicate history entry: {day_date}")
        seen_dates.add(day_date)
    return {**source, "schema": HISTORY_SCHEMA}


def save_history(path: Path, history: dict) -> None:
    """Write the full document with date-sorted entries."""
    document = {
        **history,
        "days": sorted(history["days"], key=lambda entry: entry["date"]),
    }
    write_json(path, document)


def _reject_sensitive_text(public_copy: str, label: str) -> None:
    direct_patterns = (
        (URL_RE, "URL"),
        (LOCAL_PATH_RE, "local path"),
        (EMAIL_RE, "email address"),
        (PHONE_RE, "phone number"),
        (ACCOUNT_RE, "account identifier"),
        (UUID_RE, "opaque identifier"),
        (OPAQUE_NUMERIC_ID_RE, "opaque identifier"),
        (SHORT_MIXED_ID_RE, "opaque identifier"),
        (LABELED_ID_RE, "opaque identifier"),
        (LONG_HASH_RE, "opaque hash"),
        (AWS_ACCESS_KEY_RE, "AWS credential"),
        (JWT_RE, "JWT credential"),
        (PEM_PRIVATE_KEY_RE, "private-key material"),
        (TOKEN_RE, "token or secret"),
        (AUTHORIZATION_RE, "authorization credential"),
        (HANDLE_RE, "social handle"),
        (MARKET_TICKER_RE, "security ticker"),
        (FINANCE_LABELED_SYMBOL_RE, "security ticker"),
        (CN_STOCK_CODE_RE, "security ticker"),
        (EXCLUDED_SCOPE_RE, "excluded-scope content"),
        (FEISHU_F_MARKER_RE, "excluded Feishu group marker"),
        (PRIVATE_OPS_SCOPE_RE, "private operational context"),
    )
    for pattern, description in direct_patterns:
        if pattern.search(public_copy):
            raise ValueError(f"{label} contains a prohibited {description}")

    all_uppercase_tokens = set(UPPERCASE_TICKER_RE.findall(public_copy))
    ticker_tokens = {
        token
        for token in all_uppercase_tokens
        if token not in TECHNICAL_ACRONYM_ALLOWLIST
    }
    if FINANCE_CONTEXT_RE.search(public_copy) and all_uppercase_tokens:
        ticker_tokens.update(all_uppercase_tokens)
    if ticker_tokens:
        raise ValueError(f"{label} contains a prohibited security ticker")

    guarded_patterns = (
        (SENSITIVE_ASSIGNED_WORK_RE, "holdings or position activity"),
        (PRIVATE_OPERATIONAL_CONTEXT_RE, "private operational context"),
        (PRIVATE_IDENTIFIER_RE, "private operational context"),
        (EDUCATION_IDENTITY_RE, "education or profession identity"),
        (PROPOSAL_TITLE_CONTEXT_RE, "proposal title or topic"),
        (SPOUSE_ACTIVITY_RE, "excluded private or education content"),
    )
    for pattern, description in guarded_patterns:
        if pattern.search(public_copy):
            raise ValueError(f"{label} exposes {description}")


def _redact_fixed_proper_names(value: str) -> str:
    """Mask exact private proper names without treating their component words as private."""
    redacted = value
    for pattern, _description in FIXED_PROPER_NAME_REDACTIONS:
        redacted = pattern.sub(FIXED_REDACTION_BLOCK, redacted)
    return redacted


def validate_residue(residue: object, index: int, day_date: str) -> dict:
    label = f"{day_date} residue {index + 1}"
    require(isinstance(residue, dict), f"{label} must be an object")
    require(
        set(residue) == INPUT_RESIDUE_KEYS,
        f"{label} must contain exactly category/en/zh",
    )

    category = residue["category"]
    en = residue["en"]
    zh = residue["zh"]
    require(isinstance(category, str), f"{label} category must be a string")
    require(category in REQUIRED_TAXONOMY, f"{label} has unknown category: {category}")
    require(isinstance(en, str), f"{label} en must be a string")
    require(isinstance(zh, str), f"{label} zh must be a string")
    en = en.strip()
    zh = zh.strip()
    require(en, f"{label} missing en")
    require(zh, f"{label} missing zh")
    en = _redact_fixed_proper_names(en)
    zh = _redact_fixed_proper_names(zh)
    require(len(en) <= 300, f"{label} English summary is too long")
    require(len(zh) <= 90, f"{label} Chinese summary is too long")

    public_copy = f"{en} {zh}"
    _reject_sensitive_text(public_copy, label)

    en_redactions = en.count(FIXED_REDACTION_BLOCK)
    zh_redactions = zh.count(FIXED_REDACTION_BLOCK)
    require(
        en_redactions == zh_redactions,
        f"{label} mask counts must match in both languages",
    )
    redaction_status = "partial" if en_redactions else "none"
    validated = {
        "category": category,
        "en": en,
        "zh": zh,
        "redaction_status": redaction_status,
        "redaction_count": en_redactions,
        "source_kind": "daily_record",
        "faithfulness": "faithful_summary",
    }
    require(set(validated) == OUTPUT_RESIDUE_KEYS, f"{label} output schema mismatch")
    return validated


def validate_input(data: object) -> tuple[str, str, list[dict]]:
    require(isinstance(data, dict), "Input must be an object")
    require(
        set(data) == INPUT_KEYS,
        "Input must contain exactly schema/date/provenance/assigned_residues",
    )
    require(data["schema"] == INPUT_SCHEMA, f"Invalid schema: {data['schema']}")
    day_date = parse_iso_date(data["date"], "date")
    provenance = data["provenance"]
    require(provenance == "dialogue_based", f"Invalid provenance: {provenance}")

    raw_residues = data["assigned_residues"]
    require(isinstance(raw_residues, list), "assigned_residues must be a list")
    require(
        2 <= len(raw_residues) <= 6,
        f"assigned_residues must have 2-6 items, got {len(raw_residues)}",
    )
    residues = [
        validate_residue(residue, index, day_date)
        for index, residue in enumerate(raw_residues)
    ]
    signatures = []
    for residue in residues:
        signature = (residue["category"], residue["en"], residue["zh"])
        require(signature not in signatures, f"{day_date} assigned residues must be unique")
        signatures.append(signature)
    return day_date, provenance, residues


def validate_public_entities(
    residues: list[dict],
    *,
    entity_detector_path: Path = DEFAULT_ENTITY_DETECTOR,
) -> None:
    """Fail closed when the Swift helper detects or cannot rule out entities."""
    public_strings = [
        residue[language]
        for residue in residues
        for language in ("en", "zh")
    ]
    detector_command = (
        [str(entity_detector_path)]
        if os.access(entity_detector_path, os.X_OK)
        else ["/usr/bin/xcrun", "swift", str(entity_detector_path)]
    )
    try:
        result = subprocess.run(
            detector_command,
            input=json.dumps(public_strings, ensure_ascii=False),
            capture_output=True,
            text=True,
            check=False,
            timeout=ENTITY_DETECTOR_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("Public entity detector failed closed") from error

    require(result.returncode == 0, "Public entity detector failed closed")
    try:
        detections = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ValueError("Public entity detector returned malformed data") from error

    require(
        isinstance(detections, list) and len(detections) == len(public_strings),
        "Public entity detector returned malformed data",
    )
    for detection in detections:
        require(
            isinstance(detection, dict)
            and set(detection) == {"PersonalName", "OrganizationName"},
            "Public entity detector returned malformed data",
        )
        for entity_type in ("PersonalName", "OrganizationName"):
            entities = detection[entity_type]
            require(
                isinstance(entities, list)
                and all(isinstance(entity, str) for entity in entities),
                "Public entity detector returned malformed data",
            )
            if any(entity.strip() for entity in entities):
                raise ValueError(
                    "Public text contains a detected personal or organization name"
                )


def upsert_dialogue_residues(
    input_path: Path,
    dry_run: bool = False,
    *,
    history_path: Path = DEFAULT_HISTORY,
    days_path: Path = DEFAULT_DAYS,
    entity_detector_path: Path = DEFAULT_ENTITY_DETECTOR,
) -> bool:
    """Upsert one date. Return True only when a write would occur."""
    day_date, provenance, residues = validate_input(read_json(input_path))
    validate_public_entities(
        residues,
        entity_detector_path=entity_detector_path,
    )
    require(day_date in load_days(days_path), f"Date {day_date} not found in days.json")
    history = load_history(history_path)

    new_entry = {
        "date": day_date,
        "provenance": provenance,
        "assigned_residues": residues,
    }
    existing = next(
        (entry for entry in history["days"] if entry["date"] == day_date),
        None,
    )
    if existing == new_entry:
        return False

    updated_days = [
        entry for entry in history["days"] if entry["date"] != day_date
    ]
    updated_days.append(new_entry)
    updated_history = {**history, "days": updated_days}
    if not dry_run:
        save_history(history_path, updated_history)
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Input JSON file")
    parser.add_argument(
        "--history",
        type=Path,
        default=DEFAULT_HISTORY,
        help="History JSON path",
    )
    parser.add_argument(
        "--days",
        type=Path,
        default=DEFAULT_DAYS,
        help="Public days JSON path",
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        return 1
    try:
        changed = upsert_dialogue_residues(
            args.input,
            history_path=args.history,
            days_path=args.days,
            entity_detector_path=DEFAULT_ENTITY_DETECTOR,
            dry_run=args.dry_run,
        )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Validation error: {error}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("Validated; dry run would update history" if changed else "Validated; no change")
    else:
        print("History updated" if changed else "History already identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
