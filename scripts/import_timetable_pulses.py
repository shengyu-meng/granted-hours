#!/usr/bin/env python3
"""Build public-safe, evidence-rich calendar windows from real cron runs.

Operational runs are reduced to fixed public facts. Explicitly authorized
self-reminders retain their original wording once, with identifying entities
and technical secrets masked before serialization. Raw job names, IDs, prompts,
delivery targets, accounts, holdings, and source paths are never written to the
snapshot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from collections.abc import Callable, Sequence
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from reminder_disclosure import (
    DISCLOSURE_AUTHORIZATION,
    DISCLOSURE_POLICY,
    EntityDetectionError,
    PROJECTION_PROVENANCE,
    extractive_prefix,
    join_reminder_responses,
    projection_kind_for_counts,
    project_limited_reminder_response,
)
from public_projection_privacy import (
    assert_private_terms_absent,
    exclude_public_identity_terms,
    load_private_denylist,
    load_public_identity_allowlist,
    project_market_evidence,
    replace_private_terms,
)
from semantic_public_policy import (
    reminder_requires_routine_projection as reminder_text_requires_routine_projection,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_DAYS = ROOT / "metadata" / "days.json"
DEFAULT_SNAPSHOT = ROOT / "metadata" / "timetable-pulses.json"
DEFAULT_REMINDER_TRANSLATIONS = (
    ROOT / "metadata" / "timetable-reminder-translations.json"
)
DEFAULT_STATE_DB = Path.home() / ".hermes" / "profiles" / "heizhou" / "state.db"
DEFAULT_ENTITY_DETECTOR = ROOT / "scripts" / "detect_collaboration_entities.swift"
DEFAULT_HOLDINGS_DENYLIST = ROOT / ".private" / "holdings-denylist.json"
DEFAULT_SELF_MEDIA_DENYLIST = ROOT / ".private" / "self-media-denylist.json"
DEFAULT_PUBLIC_IDENTITY_ALLOWLIST = ROOT / "metadata" / "public-identity-allowlist.json"
TIMEZONE = ZoneInfo("Asia/Shanghai")
PULSE_SNAPSHOT_SCHEMA = "granted-hours-timetable-pulses-v6"
LEGACY_PULSE_SNAPSHOT_SCHEMAS = {
    "granted-hours-timetable-pulses-v3",
    "granted-hours-timetable-pulses-v4",
}
REMINDER_TRANSLATION_SCHEMA = (
    "granted-hours-timetable-reminder-translations-v1"
)
REMINDER_TRANSLATION_PROVENANCE = (
    "public_mask_preserving_translation_v1"
)
REMINDER_TRANSLATION_FIELDS = {
    "source_sha256",
    "summary_en",
    "excerpt_en",
    "translation_provenance",
}
FIXED_REDACTION_BLOCK = "████"
CJK_RE = re.compile(
    r"[\u3040-\u30ff\u3100-\u312f\u31a0-\u31bf\u31f0-\u31ff"
    r"\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uf900-\ufaff]"
)
LATIN_RE = re.compile(r"[A-Za-z]")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
GENERIC_REMINDER_TRANSLATIONS = {
    "A reminder was sent.",
    "A reminder was published.",
    "Reminder not published.",
}
ROUTINE_ONLY_REMINDER_SUMMARY = (
    "日常计划与优先级复核。",
    "Daily planning and priority review.",
)

NESTED_RUN_RE = re.compile(r"^(?P<stamp>\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.(?:md|txt)$")
FLAT_RUN_RE = re.compile(
    r"^(?P<job>.+)_(?P<stamp>\d{8}_\d{6})\.(?:md|txt)$"
)
PUBLIC_CATEGORIES = {
    "ah_market_scan",
    "us_market_scan",
    "ai_daily_brief",
    "daily_reminder",
    "system_routine",
    "background_routine",
}
MARKET_CATEGORIES = {"ah_market_scan", "us_market_scan"}

US_MARKET_RE = re.compile(
    r"(?i)(?:\bus\b|u\.s\.|nasdaq|nyse|premarket|overnight|wall.?street)"
)
AH_MARKET_RE = re.compile(
    r"(?i)(?:a[- ]?share|\bah\b|hong.?kong|\bhk\b|market|stock|portfolio|"
    r"investment|futu|qmt|sepa|quote|radar|lof|fund|holdings|capflow|"
    r"put|call|equity|allocation|市场|股票|投资|港股|美股|A股)"
)
AI_BRIEF_RE = re.compile(r"(?i)(?:ai[- ]?daily|daily[- ]?brief|AI日报)")
REMINDER_RE = re.compile(
    r"(?i)(?:remind|reminder|gentle|dispatch|回顾|提醒|晚安|日记|reflection)"
)
INTERNAL_REFLECTION_RE = re.compile(
    r"(?i)(?:redo[-_ ]?reflection|self[-_ ]?review|internal[-_ ]?scoreboard)"
)
SYSTEM_RE = re.compile(
    r"(?i)(?:backup|sync|health|update|maintenance|workspace|version|"
    r"full[- ]?loop|calibration|watchdog|archive)"
)
SESSION_ID_RE = re.compile(r"^cron_(?P<job>.+)_(?P<date>\d{8})_(?P<time>\d{6})$")
WARNING_RE = re.compile(r"(?i)(?:失败|异常|不可达|陈旧|新鲜度|警告|stale|warning|error|failed|unreachable)")
NO_ACTION_RE = re.compile(r"(?i)(?:\[SILENT\]|本周无|无直接|不产生直接|无公开动作|no\s+(?:direct\s+)?action)")
DEFENSIVE_RE = re.compile(r"(?i)(?:防守|风险收缩|risk[- ]?off|defensive)")
BALANCED_RE = re.compile(r"(?i)(?:均衡|中性|平衡|balanced|neutral)")
OFFENSIVE_RE = re.compile(r"(?i)(?:进攻|风险扩张|risk[- ]?on|offensive)")
AI_BRIEF_FAILURE_LINE_RE = re.compile(
    r"""(?ix)
    ^\s*(?:\#{1,6}\s*)?
    (?:
        (?:采集异常诊断|采集未达标|不发正常\s*AI\s*日报)
        |
        (?:状态|结论|采集状态)\s*[:：]\s*(?:失败|异常|未达标)
        |
        collection\s+failure
        |
        (?:status|result|collection\s+status)\s*[:：]\s*(?:collection\s+failure|failure|failed|insufficient)
    )
    (?:\s*[:：—-]\s*.*)?\s*$
    """
)
SAFE_MARKET_THEMES = (
    (re.compile(r"(?i)(?:AI\s*硬件|AI hardware|半导体|semiconductor|存储|memory cycle)"), "AI 硬件与半导体", "AI hardware and semiconductors"),
    (re.compile(r"(?i)(?:CPO|光互连|optical interconnect|光通信)"), "光互连", "optical interconnects"),
    (re.compile(r"(?i)(?:机器人|具身智能|robotics|embodied AI)"), "具身智能", "embodied AI"),
    (re.compile(r"(?i)(?:能源|资源|利率|energy|resources|rates|duration pressure)"), "资源与利率", "resources and rates"),
    (re.compile(r"(?i)(?:市场状态|market regime|波动|volatility)"), "市场状态与波动", "market regime and volatility"),
)


def fail(message: str) -> None:
    raise SystemExit(message)


def mask_token_count(value: str, context: str) -> int:
    """Count intact fixed masks and reject split or altered block runs."""
    runs = re.findall(r"█+", value)
    if any(len(run) % len(FIXED_REDACTION_BLOCK) for run in runs):
        fail(f"{context} contains a split or altered ████ token")
    return sum(len(run) // len(FIXED_REDACTION_BLOCK) for run in runs)


def validate_reminder_translation_record(
    source_sha256: str,
    record: object,
) -> dict[str, str]:
    context = f"Reminder translation {source_sha256}"
    if SHA256_RE.fullmatch(source_sha256) is None:
        fail("Reminder translation catalog contains an invalid SHA-256 key")
    if not isinstance(record, dict) or set(record) != REMINDER_TRANSLATION_FIELDS:
        fail(f"{context} has invalid fields")
    if record.get("source_sha256") != source_sha256:
        fail(f"{context} source_sha256 does not match its catalog key")
    if (
        record.get("translation_provenance")
        != REMINDER_TRANSLATION_PROVENANCE
    ):
        fail(f"{context} has invalid translation provenance")
    summary_en = record.get("summary_en")
    excerpt_en = record.get("excerpt_en")
    if (
        not isinstance(summary_en, str)
        or not summary_en.strip()
        or len(summary_en) > 100_000
    ):
        fail(f"{context} has invalid summary_en")
    if (
        not isinstance(excerpt_en, str)
        or not excerpt_en.strip()
        or len(excerpt_en) > 260
    ):
        fail(f"{context} has invalid excerpt_en")
    if summary_en.strip() in GENERIC_REMINDER_TRANSLATIONS:
        fail(f"{context} uses a generic placeholder translation")
    for field, value in (("summary_en", summary_en), ("excerpt_en", excerpt_en)):
        if CJK_RE.search(value):
            fail(f"{context} {field} contains CJK characters")
        if LATIN_RE.search(value) is None:
            fail(f"{context} {field} must contain Latin letters")
        mask_token_count(value, f"{context} {field}")
    if len(summary_en) <= 260:
        if excerpt_en != summary_en:
            fail(f"{context} short excerpt_en must equal summary_en")
    elif not (
        excerpt_en.endswith("…")
        and summary_en.startswith(excerpt_en[:-1])
    ):
        fail(f"{context} excerpt_en must be a clean summary_en prefix")
    return dict(record)


def load_reminder_translations(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        fail(f"Reminder translation catalog does not exist: {path}")
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        fail("Could not read reminder translation catalog")
    except json.JSONDecodeError:
        fail("Reminder translation catalog is not valid JSON")
    if not isinstance(source, dict) or set(source) != {
        "schema",
        "translation_provenance",
        "translations",
    }:
        fail("Reminder translation catalog has invalid top-level fields")
    if source.get("schema") != REMINDER_TRANSLATION_SCHEMA:
        fail(
            "Reminder translation catalog schema must be "
            f"{REMINDER_TRANSLATION_SCHEMA}"
        )
    if (
        source.get("translation_provenance")
        != REMINDER_TRANSLATION_PROVENANCE
    ):
        fail("Reminder translation catalog has invalid provenance")
    translations = source.get("translations")
    if not isinstance(translations, dict):
        fail("Reminder translation catalog translations must be an object")
    return {
        source_sha256: validate_reminder_translation_record(
            source_sha256,
            record,
        )
        for source_sha256, record in translations.items()
    }


def translation_for_reminder(
    projection: dict,
    translations: dict[str, dict[str, str]],
    *,
    holdings_terms: Sequence[str] = (),
    source_terms: Sequence[str] = (),
) -> dict:
    """Lookup by the pre-denylist source hash, then sanitize both languages."""
    summary_original = projection["summary_original"]
    source_sha256 = hashlib.sha256(
        summary_original.encode("utf-8")
    ).hexdigest()
    record = translations.get(source_sha256)
    if record is None:
        fail(
            "Missing reminder translation for source_sha256 "
            f"{source_sha256}"
        )
    if not all(
        isinstance(projection.get(field), str)
        for field in ("summary_original", "excerpt_original")
    ):
        fail("Reminder source projection is incomplete")
    record = validate_reminder_translation_record(source_sha256, record)
    initial_source_mask_count = mask_token_count(
        summary_original,
        f"Reminder source {source_sha256}",
    )
    if initial_source_mask_count != projection.get("redaction_count"):
        fail(
            "Reminder source mask count disagrees with redaction_count for "
            f"source_sha256 {source_sha256}"
        )
    mask_token_count(record["summary_en"], "Reminder translation summary")
    mask_token_count(record["excerpt_en"], "Reminder translation excerpt")
    result = {
        **projection,
        "summary_en": record["summary_en"],
        "excerpt_en": record["excerpt_en"],
        "translation_provenance": record["translation_provenance"],
    }
    for field in (
        "summary_original",
        "excerpt_original",
        "summary_en",
        "excerpt_en",
    ):
        result[field] = replace_private_terms(
            result[field],
            holdings_terms,
            FIXED_REDACTION_BLOCK,
            contextual_ambiguous=True,
        )
        result[field] = replace_private_terms(
            result[field],
            source_terms,
            FIXED_REDACTION_BLOCK,
        )
        assert_private_terms_absent(
            result[field],
            holdings_terms=holdings_terms,
            source_terms=source_terms,
        )
    source_mask_count = mask_token_count(
        result["summary_original"],
        f"Sanitized reminder source {source_sha256}",
    )
    translation_mask_count = mask_token_count(
        result["summary_en"],
        f"Sanitized reminder translation {source_sha256}",
    )
    if translation_mask_count != source_mask_count:
        fail("Sanitized reminder summary mask parity mismatch")
    (
        result["summary_original"],
        result["summary_en"],
        result["excerpt_original"],
        result["excerpt_en"],
    ) = parity_preserving_reminder_fields(
            result["summary_original"],
            result["summary_en"],
    )
    source_mask_count = mask_token_count(
        result["summary_original"],
        "Balanced reminder source summary",
    )
    source_excerpt_masks = mask_token_count(
        result["excerpt_original"],
        "Sanitized reminder source excerpt",
    )
    translation_excerpt_masks = mask_token_count(
        result["excerpt_en"],
        "Sanitized reminder translation excerpt",
    )
    if source_excerpt_masks != translation_excerpt_masks:
        fail("Sanitized reminder excerpt mask parity mismatch")
    result["redaction_count"] = source_mask_count
    result["projection_kind"] = projection_kind_for_counts(
        source_mask_count,
        int(result.get("semantic_abstraction_count", 0)),
    )
    return result


def _prefix_with_at_most_masks(value: str, target_masks: int) -> str:
    excerpt = extractive_prefix(value)
    if mask_token_count(excerpt, "Reminder extractive prefix") <= target_masks:
        return excerpt
    starts = [
        match.start()
        for match in re.finditer(re.escape(FIXED_REDACTION_BLOCK), value)
    ]
    if target_masks >= len(starts):
        fail("Reminder excerpt parity could not be represented")
    prefix = value[: starts[target_masks]].rstrip()
    if not prefix:
        fail("Reminder excerpt parity could not be represented")
    return f"{prefix[:259].rstrip()}…"


def _summary_with_at_most_masks(value: str, target_masks: int) -> str:
    starts = [
        match.start()
        for match in re.finditer(re.escape(FIXED_REDACTION_BLOCK), value)
    ]
    if len(starts) <= target_masks:
        return value
    prefix = value[: starts[target_masks]].rstrip()
    if not prefix:
        fail("Reminder parity could not be represented as an extractive prefix")
    return f"{prefix}…"


def parity_preserving_reminder_fields(
    summary_original: str,
    summary_en: str,
) -> tuple[str, str, str, str]:
    """Balance summaries/excerpts using only faithful deterministic prefixes."""
    original_summary_masks = mask_token_count(
        summary_original,
        "Reminder original summary",
    )
    english_summary_masks = mask_token_count(
        summary_en,
        "Reminder English summary",
    )
    if original_summary_masks != english_summary_masks:
        fail("Reminder summary mask parity mismatch")
    original = extractive_prefix(summary_original)
    english = extractive_prefix(summary_en)
    original_masks = mask_token_count(original, "Reminder original excerpt")
    english_masks = mask_token_count(english, "Reminder English excerpt")
    target_masks = min(original_masks, english_masks)
    if original_masks != english_masks:
        summary_original = _summary_with_at_most_masks(
            summary_original,
            target_masks,
        )
        summary_en = _summary_with_at_most_masks(summary_en, target_masks)
        original = extractive_prefix(summary_original)
        english = extractive_prefix(summary_en)
    original = _prefix_with_at_most_masks(summary_original, target_masks)
    english = _prefix_with_at_most_masks(summary_en, target_masks)
    if (
        mask_token_count(original, "Reminder original excerpt")
        != mask_token_count(english, "Reminder English excerpt")
    ):
        fail("Reminder excerpt mask parity mismatch")
    for summary, excerpt, language in (
        (summary_original, original, "original"),
        (summary_en, english, "English"),
    ):
        if len(excerpt) > 260 or not (
            excerpt == summary
            or (excerpt.endswith("…") and summary.startswith(excerpt[:-1]))
        ):
            fail(f"Reminder {language} excerpt is not a faithful extractive prefix")
    return summary_original, summary_en, original, english


def load_private_redaction_terms(
    path: Path | None,
    public_identity_allowlist: Path = DEFAULT_PUBLIC_IDENTITY_ALLOWLIST,
) -> tuple[str, ...]:
    """Load exact terms from an ignored .private JSON file without retaining it."""
    if path is None:
        return ()
    resolved = path.resolve()
    if ".private" not in resolved.parts:
        fail("Private redaction terms must be stored under an ignored .private directory")
    try:
        source = json.loads(resolved.read_text(encoding="utf-8"))
    except OSError:
        fail("Could not read private redaction terms")
    except json.JSONDecodeError:
        fail("Private redaction terms are not valid JSON")
    values = source.get("terms") if isinstance(source, dict) else source
    if not isinstance(values, list) or not all(
        isinstance(value, str) for value in values
    ):
        fail("Private redaction terms JSON must be a string list or a terms string list")
    private_terms = tuple(
        sorted(
            {value for value in values if value},
            key=lambda value: (-len(value), value),
        )
    )
    return exclude_public_identity_terms(
        private_terms,
        load_public_identity_allowlist(public_identity_allowlist),
    )


def detect_reminder_entities_batch(
    texts: list[str],
    helper_path: Path = DEFAULT_ENTITY_DETECTOR,
) -> list[dict[str, list[str]]]:
    """Call the Apple NaturalLanguage helper once for a batch of reminders."""
    if not texts:
        return []
    if sys.platform != "darwin":
        raise EntityDetectionError("Apple NaturalLanguage is unavailable")
    clang_cache = ROOT / ".private" / "swift-cache" / "reminder-clang"
    swift_cache = ROOT / ".private" / "swift-cache" / "reminder-swift"
    clang_cache.mkdir(parents=True, exist_ok=True)
    swift_cache.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment.setdefault("CLANG_MODULE_CACHE_PATH", str(clang_cache))
    environment.setdefault("SWIFT_MODULECACHE_PATH", str(swift_cache))
    if helper_path.suffix == ".swift":
        compiled_helper = ROOT / ".private" / "swift-cache" / "detect-collaboration-entities"
        try:
            if (
                not compiled_helper.exists()
                or compiled_helper.stat().st_mtime < helper_path.stat().st_mtime
            ):
                compilation = subprocess.run(
                    ["/usr/bin/xcrun", "swiftc", str(helper_path), "-o", str(compiled_helper)],
                    capture_output=True,
                    text=True,
                    timeout=600,
                    check=False,
                    env=environment,
                )
                if compilation.returncode != 0:
                    raise EntityDetectionError("Apple NaturalLanguage helper failed")
                compiled_helper.chmod(0o700)
            command = [str(compiled_helper)]
        except (OSError, subprocess.SubprocessError) as error:
            raise EntityDetectionError("Apple NaturalLanguage helper failed") from error
    else:
        command = [str(helper_path)] if os.access(helper_path, os.X_OK) else [sys.executable, str(helper_path)]
    try:
        result = subprocess.run(
            command,
            input=json.dumps(texts, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=environment,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise EntityDetectionError("Apple NaturalLanguage helper failed") from error
    if result.returncode != 0:
        raise EntityDetectionError("Apple NaturalLanguage helper failed")
    try:
        detections = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise EntityDetectionError("Apple NaturalLanguage helper returned invalid JSON") from error
    if not isinstance(detections, list) or len(detections) != len(texts):
        raise EntityDetectionError("Apple NaturalLanguage helper returned the wrong batch size")
    normalized: list[dict[str, list[str]]] = []
    for detection in detections:
        if isinstance(detection, dict) and set(detection) == {"PrivateEntityTerms"}:
            values = detection["PrivateEntityTerms"]
            if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
                raise EntityDetectionError("Apple NaturalLanguage helper returned invalid entities")
            normalized.append({"PersonalName": list(values), "OrganizationName": []})
        elif isinstance(detection, dict) and set(detection) == {"PersonalName", "OrganizationName"}:
            if not all(
                isinstance(values, list)
                and all(isinstance(value, str) for value in values)
                for values in detection.values()
            ):
                raise EntityDetectionError("Apple NaturalLanguage helper returned invalid entities")
            normalized.append(
                {
                    "PersonalName": list(detection["PersonalName"]),
                    "OrganizationName": list(detection["OrganizationName"]),
                }
            )
        else:
            raise EntityDetectionError("Apple NaturalLanguage helper returned invalid fields")
    return normalized


def parse_jobs(path: Path) -> dict[str, str]:
    if not path.exists():
        fail("Cron jobs source does not exist")
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        fail("Could not read cron jobs source")
    except json.JSONDecodeError:
        fail("Cron jobs source is not valid JSON")
    jobs = source.get("jobs") if isinstance(source, dict) else source
    if not isinstance(jobs, list):
        fail("Cron jobs source must contain a jobs list")
    result = {}
    for job in jobs:
        if not isinstance(job, dict):
            continue
        job_id = str(job.get("id", "")).strip()
        if job_id:
            result[job_id] = str(job.get("name", ""))
    return result


def public_dates(path: Path) -> set[str]:
    if not path.exists():
        fail("Public days source does not exist")
    try:
        source = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        fail("Could not read public days source")
    except json.JSONDecodeError:
        fail("Public days source is not valid JSON")
    if not isinstance(source, list):
        fail("Public days source must be a list")
    dates = {str(item.get("date", "")) for item in source if isinstance(item, dict)}
    if not dates or "" in dates:
        fail("Every public day must have a date")
    return dates


def parse_run_file(path: Path, output_dir: Path) -> tuple[str, datetime] | None:
    relative = path.relative_to(output_dir)
    if len(relative.parts) == 2:
        match = NESTED_RUN_RE.fullmatch(relative.name)
        if not match:
            return None
        return relative.parts[0], datetime.strptime(match.group("stamp"), "%Y-%m-%d_%H-%M-%S")
    if len(relative.parts) == 1:
        match = FLAT_RUN_RE.fullmatch(relative.name)
        if not match:
            return None
        return match.group("job"), datetime.strptime(match.group("stamp"), "%Y%m%d_%H%M%S")
    return None


def categorize_job(name: str) -> str:
    """Map private job metadata to one of six intentionally coarse labels."""
    if AI_BRIEF_RE.search(name):
        return "ai_daily_brief"
    if US_MARKET_RE.search(name):
        return "us_market_scan"
    if AH_MARKET_RE.search(name):
        return "ah_market_scan"
    if INTERNAL_REFLECTION_RE.search(name):
        return "background_routine"
    if REMINDER_RE.search(name):
        return "daily_reminder"
    if SYSTEM_RE.search(name):
        return "system_routine"
    return "background_routine"


def reminder_requires_routine_projection(projection: dict) -> bool:
    """Keep only empty or pure delivery/verification chatter out of reminder cards.

    Sensitive paragraphs have already been replaced by bounded public-safe
    abstractions in ``project_limited_reminder_response``. Demoting every such
    projection erased the surrounding safe reminder prose and caused real
    morning/evening reminders to disappear from the public calendar.
    """
    summary = projection.get("summary_original")
    return reminder_text_requires_routine_projection(summary)


def time_bucket(timestamp: datetime) -> tuple[str, str]:
    """Return a four-hour bucket and a 15-minute coarse display time."""
    buckets = (
        (0, "overnight"),
        (4, "dawn"),
        (7, "morning"),
        (11, "midday"),
        (14, "afternoon"),
        (18, "evening"),
    )
    bucket = max((entry for entry in buckets if timestamp.hour >= entry[0]), key=lambda entry: entry[0])
    coarse_minute = (timestamp.minute // 15) * 15
    return bucket[1], f"{timestamp.hour:02d}:{coarse_minute:02d}"


def deduplicate_runs(runs: list[tuple[str, datetime, Path]]) -> list[tuple[str, datetime, Path]]:
    """Collapse .md/.txt companion receipts emitted within two seconds."""
    result: list[tuple[str, datetime, Path]] = []
    for run in sorted(runs, key=lambda item: (item[0], item[1], -item[2].stat().st_size)):
        if result and result[-1][0] == run[0] and (run[1] - result[-1][1]).total_seconds() <= 2:
            if run[2].stat().st_size > result[-1][2].stat().st_size:
                result[-1] = run
            continue
        result.append(run)
    return result


def load_session_records(path: Path | None) -> dict[str, list[dict]]:
    """Read cron session identities, retaining invalid runs for safe matching.

    Invalid/null sessions remain in the local matching set so that a receipt
    cannot skip over its own failed run and borrow a nearby valid window.
    Session identifiers never enter the public snapshot.
    """
    if path is None or not path.exists():
        return {}
    try:
        with closing(sqlite3.connect(path)) as connection:
            rows = connection.execute(
                "SELECT id, started_at, ended_at FROM sessions WHERE source = 'cron'"
            ).fetchall()
    except sqlite3.Error as error:
        fail(f"Could not read cron session windows: {error}")
    records: dict[str, list[dict]] = defaultdict(list)
    for session_id, started_at, ended_at in rows:
        match = SESSION_ID_RE.fullmatch(str(session_id))
        if match is None or started_at is None:
            continue
        start = datetime.fromtimestamp(float(started_at), TIMEZONE).replace(tzinfo=None)
        end = None
        if ended_at is not None:
            candidate_end = datetime.fromtimestamp(float(ended_at), TIMEZONE).replace(tzinfo=None)
            if start < candidate_end <= start + timedelta(hours=6):
                end = candidate_end
        records[match.group("job")].append({"start": start, "end": end})
    for entries in records.values():
        entries.sort(key=lambda entry: entry["start"])
    return dict(records)


def match_run_windows(
    runs: list[tuple[str, datetime, Path]],
    session_records: dict[str, list[dict]],
) -> dict[Path, tuple[datetime, datetime, str]]:
    """Match each receipt to at most one same-job session in run order.

    The latest unmatched session that actually started before the receipt is
    treated as that receipt's run identity. If that session has a null or
    invalid end, the receipt remains an estimate even when another valid
    same-job session happens to end nearby.
    """
    matches: dict[Path, tuple[datetime, datetime, str]] = {}
    runs_by_job: dict[str, list[tuple[datetime, Path]]] = defaultdict(list)
    for job_id, receipt_time, path in runs:
        runs_by_job[job_id].append((receipt_time, path))

    for job_id, job_runs in runs_by_job.items():
        records = session_records.get(job_id, [])
        used: set[int] = set()
        for receipt_time, path in sorted(job_runs, key=lambda item: (item[0], str(item[1]))):
            eligible = [
                (index, record)
                for index, record in enumerate(records)
                if index not in used
                and record["start"] <= receipt_time
                and receipt_time - record["start"] <= timedelta(hours=6)
            ]
            if not eligible:
                matches[path] = (
                    receipt_time - timedelta(minutes=1),
                    receipt_time,
                    "receipt_fallback",
                )
                continue
            index, record = max(eligible, key=lambda item: item[1]["start"])
            # Any older unmatched session has already been superseded by this
            # receipt's latest pre-receipt identity. Retire all of them now so
            # a later receipt cannot borrow a stale valid window that belonged
            # before an invalid/null run.
            used.update(candidate_index for candidate_index, _ in eligible)
            end = record["end"]
            if end is not None and abs((end - receipt_time).total_seconds()) <= 30 * 60:
                matches[path] = (record["start"], end, "observed_session")
            else:
                matches[path] = (
                    receipt_time - timedelta(minutes=1),
                    receipt_time,
                    "receipt_fallback",
                )
    return matches


def ai_brief_failed(text: str) -> bool:
    """Recognize only explicit line-level failure markers, never prose negation."""
    return any(AI_BRIEF_FAILURE_LINE_RE.fullmatch(line) for line in text.splitlines())


def final_response(path: Path) -> str:
    """Return only the explicit final-response section; prompts are never parsed."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    marker = "\n## Response\n"
    if marker not in text:
        return ""
    return text.rsplit(marker, 1)[-1].strip()[:50_000]


def public_summary(
    category: str,
    responses: list[str],
    count: int,
    *,
    holdings_terms: Sequence[str] = (),
    source_terms: Sequence[str] = (),
) -> tuple[str, str]:
    """Reduce private outputs to fixed-vocabulary, public-safe operational facts."""
    texts = [text for text in responses if text]
    combined = "\n".join(texts)
    silent_count = sum(text.strip() == "[SILENT]" for text in texts)
    warning_count = sum(bool(WARNING_RE.search(text)) for text in texts)
    no_action_count = sum(bool(NO_ACTION_RE.search(text)) for text in texts)

    if category in {"ah_market_scan", "us_market_scan"}:
        label_zh = "A/H 市场扫描" if category == "ah_market_scan" else "美股市场扫描"
        label_en = "A/H market scans" if category == "ah_market_scan" else "U.S. market scans"
        facts = project_market_evidence(
            texts,
            holdings_terms=holdings_terms,
            source_terms=source_terms,
            maximum_facts=3,
        )
        safe_combined = "\n".join(facts)
        state_candidates = [
            (sum(bool(DEFENSIVE_RE.search(text)) for text in facts), "防守 / 风险收缩", "defensive / risk-contraction"),
            (sum(bool(OFFENSIVE_RE.search(text)) for text in facts), "进攻 / 风险扩张", "offensive / risk-expansion"),
            (sum(bool(BALANCED_RE.search(text)) for text in facts), "均衡 / 中性", "balanced / neutral"),
        ]
        state_score, state_zh, state_en = max(state_candidates, key=lambda item: item[0])
        if state_score == 0:
            state_zh, state_en = "扫描证据未收敛为单一状态标签", "scan evidence did not converge on one regime label"
        themes = [(zh, en) for pattern, zh, en in SAFE_MARKET_THEMES if pattern.search(safe_combined)][:2]
        theme_zh = "、".join(item[0] for item in themes) if themes else "见公开标的与事件"
        theme_en = ", ".join(item[1] for item in themes) if themes else "see the retained public instruments and events"
        evidence = "；".join(facts)
        if not evidence:
            evidence = "未保留公开事实"
        evidence = evidence[:210].rstrip("，,；; ")
        action_zh = f"{max(silent_count, no_action_count)} 次未形成公开动作信号" if max(silent_count, no_action_count) else "存在公开报告输出"
        action_en = f"{max(silent_count, no_action_count)} run(s) produced no public action signal" if max(silent_count, no_action_count) else "public report output was produced"
        warning_zh = "；存在数据或链路新鲜度警告" if warning_count else "；未检测到链路警告"
        warning_en = "; data or pipeline-freshness warnings were present" if warning_count else "; no pipeline warning was detected"
        summary_zh = (
            f"本窗口完成 {count} 次{label_zh}；状态：{state_zh}；"
            f"主题：{theme_zh}；公开事实：{evidence}。{action_zh}{warning_zh}。"
        )
        summary_en = (
            f"{count} {label_en} completed; regime: {state_en}; themes: "
            f"{theme_en}. Retained public evidence: {evidence}. "
            f"{action_en}{warning_en}."
        )
        assert_private_terms_absent(
            f"{summary_zh}\n{summary_en}",
            holdings_terms=holdings_terms,
            source_terms=source_terms,
        )
        return summary_zh[:360], summary_en[:520]

    if category == "ai_daily_brief":
        if ai_brief_failed(combined):
            return (
                "AI 日报流程报告采集未达发布闸门，因此没有生成常规日报。",
                "The AI-brief workflow reported that collection did not pass its publication gate, so no normal brief was generated.",
            )
        return (
            f"完成 {count} 次 AI 日报流程；{silent_count} 次静默，{warning_count} 次含公开级别采集警告。",
            f"{count} AI-brief run(s) completed; {silent_count} stayed silent and {warning_count} contained a public-level collection warning.",
        )

    if category == "daily_reminder":
        return (
            "提醒残留。",
            "Reminder residue.",
        )

    if category == "system_routine":
        return (
            f"完成 {count} 次系统例行检查；{silent_count} 次静默正常，{warning_count} 次出现公开级别异常或新鲜度提示。",
            f"{count} system checks completed; {silent_count} were silently healthy and {warning_count} exposed a public-level anomaly or freshness warning.",
        )

    return (
        f"完成 {count} 次后台流程；{silent_count} 次静默，{warning_count} 次出现公开级别异常提示；私有内容未进入日程。",
        f"{count} background run(s) completed; {silent_count} stayed silent and {warning_count} exposed a public-level warning; private content was not imported into the timetable.",
    )


def format_clock(timestamp: datetime, *, end: bool = False) -> str:
    if end and timestamp.hour == 0 and timestamp.minute == 0:
        return "24:00"
    return timestamp.strftime("%H:%M")


def build_snapshot(
    jobs_path: Path,
    output_dir: Path,
    public_days_path: Path,
    state_db_path: Path | None = DEFAULT_STATE_DB,
    *,
    authorize_self_reminders: bool = False,
    authorize_authentic_reminder_disclosure: bool = False,
    private_redaction_terms: Sequence[str] = (),
    holdings_terms: Sequence[str] = (),
    source_terms: Sequence[str] = (),
    entity_detector: (
        Callable[[list[str]], list[dict[str, list[str]]]] | None
    ) = None,
    allow_entity_detector_bypass_for_tests: bool = False,
    authorize_limited_reminder_disclosure: bool | None = None,
    reminder_translations_path: Path = DEFAULT_REMINDER_TRANSLATIONS,
    reminder_translations: dict[str, dict[str, str]] | None = None,
    allow_missing_reminder_translations_for_candidates: bool = False,
    translation_required_dates: set[str] | None = None,
) -> dict:
    if authorize_limited_reminder_disclosure:
        authorize_authentic_reminder_disclosure = True
    if authorize_authentic_reminder_disclosure and not authorize_self_reminders:
        fail(
            "Authentic reminder disclosure also requires explicit self-reminder authorization"
        )
    translations = (
        reminder_translations
        if reminder_translations is not None
        else load_reminder_translations(reminder_translations_path)
        if authorize_authentic_reminder_disclosure
        else {}
    )
    job_names = parse_jobs(jobs_path)
    if not output_dir.exists() or not output_dir.is_dir():
        fail("Cron output source does not exist")
    dates = public_dates(public_days_path)
    session_records = load_session_records(state_db_path)
    parsed_runs: list[tuple[str, datetime, Path]] = []
    source_file_count = 0
    for path in sorted(candidate for candidate in output_dir.rglob("*") if candidate.is_file()):
        parsed = parse_run_file(path, output_dir)
        if parsed is None or parsed[1].date().isoformat() not in dates:
            continue
        source_file_count += 1
        parsed_runs.append((*parsed, path))
    runs = deduplicate_runs(parsed_runs)
    run_windows = match_run_windows(runs, session_records)

    evidence_by_day_category: dict[tuple[str, str], list[dict]] = defaultdict(list)
    observed_count = 0
    for job_id, timestamp, path in runs:
        day_date = timestamp.date().isoformat()
        category = categorize_job(job_names.get(job_id, ""))
        start, end, provenance = run_windows[path]
        if provenance == "observed_session":
            observed_count += 1
        day_start = datetime.strptime(day_date, "%Y-%m-%d")
        day_end = day_start + timedelta(days=1)
        start = max(start, day_start)
        end = min(max(end, start + timedelta(minutes=1)), day_end)
        evidence_by_day_category[(day_date, category)].append(
            {
                "start_at": start,
                "end_at": end,
                "category": category,
                "count": 1,
                "execution_seconds": max(60.0, (end - start).total_seconds()),
                "responses": [final_response(path)],
                "observed_count": int(provenance == "observed_session"),
            }
        )

    grouped: dict[str, list[dict]] = defaultdict(list)
    for (day_date, _category), evidence in evidence_by_day_category.items():
        current = None
        for run in sorted(evidence, key=lambda item: (item["start_at"], item["end_at"])):
            if current is not None and run["start_at"] <= current["end_at"] + timedelta(minutes=2):
                current["end_at"] = max(current["end_at"], run["end_at"])
                current["count"] += 1
                current["execution_seconds"] += run["execution_seconds"]
                current["responses"].extend(run["responses"])
                current["observed_count"] += run["observed_count"]
                continue
            current = dict(run)
            grouped[day_date].append(current)

    detected_entities_by_group: dict[int, tuple[str, ...]] = {}
    if authorize_authentic_reminder_disclosure:
        reminder_groups = [
            group
            for day_groups in grouped.values()
            for group in day_groups
            if group["category"] == "daily_reminder"
            and join_reminder_responses(group["responses"])
        ]
        reminder_texts = [
            join_reminder_responses(group["responses"]) for group in reminder_groups
        ]
        if allow_entity_detector_bypass_for_tests:
            detections = [
                {"PersonalName": [], "OrganizationName": []}
                for _text in reminder_texts
            ]
        else:
            detector = entity_detector or detect_reminder_entities_batch
            try:
                detections = detector(reminder_texts)
            except Exception:
                fail("Authorized reminder entity detection failed closed")
        if len(detections) != len(reminder_groups):
            fail("Authorized reminder entity detection failed closed")
        for group, detection in zip(reminder_groups, detections):
            if not isinstance(detection, dict) or set(detection) != {
                "PersonalName",
                "OrganizationName",
            }:
                fail("Authorized reminder entity detection failed closed")
            values = [
                *detection["PersonalName"],
                *detection["OrganizationName"],
            ]
            if not all(isinstance(value, str) for value in values):
                fail("Authorized reminder entity detection failed closed")
            detected_entities_by_group[id(group)] = tuple(values)

    days = []
    for day_date in sorted(dates):
        pulses = []
        for group in grouped.get(day_date, []):
            public_category = group["category"]
            display_start = group["start_at"].replace(second=0, microsecond=0)
            display_end = group["end_at"].replace(second=0, microsecond=0)
            if group["end_at"] > display_end:
                display_end += timedelta(minutes=1)
            next_midnight = datetime.combine(
                display_start.date() + timedelta(days=1),
                datetime.min.time(),
            )
            display_end = min(display_end, next_midnight)
            display_end = max(display_end, display_start + timedelta(minutes=1))
            duration_minutes = int((display_end - display_start).total_seconds() // 60)
            bucket, _coarse_time = time_bucket(display_start)
            reminder_projection = None
            if (
                group["category"] == "daily_reminder"
                and authorize_self_reminders
                and authorize_authentic_reminder_disclosure
            ):
                reminder_projection = project_limited_reminder_response(
                    group["responses"],
                    bucket,
                    exact_terms=private_redaction_terms,
                    detected_entities=detected_entities_by_group.get(id(group), ()),
                )
                if reminder_projection is None:
                    continue
                if reminder_requires_routine_projection(reminder_projection):
                    public_category = "background_routine"
                    reminder_projection = None
                    summary_zh, summary_en = ROUTINE_ONLY_REMINDER_SUMMARY
            elif group["category"] != "daily_reminder":
                summary_zh, summary_en = public_summary(
                    group["category"],
                    group["responses"],
                    group["count"],
                    holdings_terms=holdings_terms,
                    source_terms=source_terms,
                )
            pulse = {
                "start": format_clock(display_start),
                "end": format_clock(display_end, end=display_end.date() > display_start.date()),
                "duration_minutes": duration_minutes,
                "execution_minutes": max(1, math.ceil(group["execution_seconds"] / 60)),
                "time_bucket": bucket,
                "category": public_category,
                "count": group["count"],
                "time_provenance": (
                    "observed_session_window"
                    if group["observed_count"] == group["count"]
                    else "receipt_timestamp_estimate"
                    if group["observed_count"] == 0
                    else "mixed_observed_and_receipt"
                ),
            }
            if reminder_projection is None:
                if public_category == "daily_reminder":
                    pulse.update(
                        {
                            "summary_zh": "提醒未公开。",
                            "summary_en": "Reminder not published.",
                            "summary_provenance": "withheld_unverified",
                        }
                    )
                else:
                    pulse.update(
                        {
                            "summary_zh": summary_zh,
                            "summary_en": summary_en,
                            "summary_provenance": "derived_public_safe",
                        }
                    )
            if public_category == "daily_reminder":
                pulse.update(
                    {
                        "owner_scope": (
                            "self"
                            if authorize_self_reminders
                            else "unknown"
                        ),
                        "ownership_provenance": (
                            "explicit_import_authorization"
                            if authorize_self_reminders
                            else "unverified"
                        ),
                    }
                )
                if reminder_projection is not None:
                    pulse.update(reminder_projection)
                    if (
                        not allow_missing_reminder_translations_for_candidates
                        and (
                            translation_required_dates is None
                            or day_date in translation_required_dates
                        )
                    ):
                        pulse.update(
                            translation_for_reminder(
                                reminder_projection,
                                translations,
                                holdings_terms=holdings_terms,
                                source_terms=source_terms,
                            )
                        )
                    pulse["summary_provenance"] = PROJECTION_PROVENANCE
            pulses.append(pulse)
        pulses.sort(key=lambda pulse: (pulse["start"], pulse["category"]))
        days.append({"date": day_date, "pulses": pulses})

    return {
        "schema": PULSE_SNAPSHOT_SCHEMA,
        "timezone": "Asia/Shanghai",
        "source_file_count": source_file_count,
        "deduplicated_run_count": len(runs),
        "observed_session_window_count": observed_count,
        "days": days,
    }


def _state_market_groups(
    state_db_path: Path,
    public_day_dates: set[str],
) -> dict[str, list[dict]]:
    """Read completed market cron sessions without retaining private identities."""
    if not state_db_path.exists():
        fail("Hermes state database does not exist")
    if not public_day_dates:
        return {}
    first_date = datetime.strptime(min(public_day_dates), "%Y-%m-%d").replace(
        tzinfo=TIMEZONE
    )
    last_date = (
        datetime.strptime(max(public_day_dates), "%Y-%m-%d").replace(
            tzinfo=TIMEZONE
        )
        + timedelta(days=1)
    )
    try:
        with closing(sqlite3.connect(state_db_path)) as connection:
            rows = connection.execute(
                """
                SELECT s.id, COALESCE(s.title, ''), s.started_at, s.ended_at,
                       COALESCE(m.content, ''), m.timestamp
                FROM sessions AS s
                JOIN messages AS m ON m.session_id = s.id
                WHERE s.source = 'cron'
                  AND s.started_at >= ? AND s.started_at < ?
                  AND COALESCE(m.active, 1) = 1
                  AND m.role = 'assistant'
                  AND COALESCE(m.content, '') <> ''
                ORDER BY s.started_at, s.id, m.timestamp, m.id
                """,
                (first_date.timestamp(), last_date.timestamp()),
            ).fetchall()
    except sqlite3.Error as error:
        fail(f"Could not read market evidence from session state: {error}")

    sessions: dict[str, dict] = {}
    for session_id, title, started_at, ended_at, content, _timestamp in rows:
        category = categorize_job(str(title))
        if category not in {"ah_market_scan", "us_market_scan"}:
            continue
        start = datetime.fromtimestamp(float(started_at), TIMEZONE).replace(
            tzinfo=None
        )
        day_date = start.date().isoformat()
        if day_date not in public_day_dates:
            continue
        end = None
        if ended_at is not None:
            candidate = datetime.fromtimestamp(float(ended_at), TIMEZONE).replace(
                tzinfo=None
            )
            if start < candidate <= start + timedelta(hours=6):
                end = candidate
        record = sessions.setdefault(
            str(session_id),
            {
                "day_date": day_date,
                "category": category,
                "start_at": start,
                "end_at": end or start + timedelta(minutes=1),
                "observed_count": int(end is not None),
                "responses": [],
            },
        )
        record["responses"].append(str(content))

    grouped: dict[str, list[dict]] = defaultdict(list)
    by_day_category: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in sessions.values():
        by_day_category[(record["day_date"], record["category"])].append(record)
    for (day_date, category), records in sorted(by_day_category.items()):
        current = None
        for record in sorted(records, key=lambda item: item["start_at"]):
            if (
                current is not None
                and record["start_at"] <= current["end_at"] + timedelta(minutes=2)
            ):
                current["end_at"] = max(current["end_at"], record["end_at"])
                current["count"] += 1
                current["observed_count"] += record["observed_count"]
                current["responses"].extend(record["responses"])
                continue
            current = {
                "category": category,
                "start_at": record["start_at"],
                "end_at": record["end_at"],
                "count": 1,
                "observed_count": record["observed_count"],
                "responses": list(record["responses"]),
            }
            grouped[day_date].append(current)
    return dict(grouped)


def _market_pulse_from_state_group(
    day_date: str,
    group: dict,
    *,
    holdings_terms: Sequence[str],
    source_terms: Sequence[str],
) -> dict:
    day_start = datetime.strptime(day_date, "%Y-%m-%d")
    day_end = day_start + timedelta(days=1)
    start = max(day_start, group["start_at"]).replace(second=0, microsecond=0)
    raw_end = min(day_end, max(group["end_at"], start + timedelta(minutes=1)))
    end = raw_end.replace(second=0, microsecond=0)
    if raw_end > end:
        end += timedelta(minutes=1)
    end = min(day_end, max(end, start + timedelta(minutes=1)))
    summary_zh, summary_en = public_summary(
        group["category"],
        group["responses"],
        group["count"],
        holdings_terms=holdings_terms,
        source_terms=source_terms,
    )
    bucket, _coarse_time = time_bucket(start)
    duration_minutes = int((end - start).total_seconds() // 60)
    return {
        "start": format_clock(start),
        "end": format_clock(end, end=end.date() > start.date()),
        "duration_minutes": duration_minutes,
        "execution_minutes": duration_minutes,
        "time_bucket": bucket,
        "category": group["category"],
        "count": group["count"],
        "time_provenance": (
            "observed_session_window"
            if group["observed_count"] == group["count"]
            else "receipt_timestamp_estimate"
            if group["observed_count"] == 0
            else "mixed_observed_and_receipt"
        ),
        "summary_provenance": "derived_public_safe",
        "summary_zh": summary_zh,
        "summary_en": summary_en,
    }


def refresh_market_snapshot_from_state(
    *,
    snapshot_path: Path,
    state_db_path: Path,
    holdings_terms: Sequence[str],
    source_terms: Sequence[str],
) -> dict:
    """Replace market pulses only where the state DB has direct session evidence."""
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except OSError:
        fail("Could not read existing pulse snapshot")
    except json.JSONDecodeError:
        fail("Existing pulse snapshot is not valid JSON")
    if snapshot.get("schema") != PULSE_SNAPSHOT_SCHEMA:
        fail("Market refresh requires the current pulse snapshot schema")
    days = snapshot.get("days")
    if not isinstance(days, list):
        fail("Pulse snapshot must contain days")
    dates = {
        str(entry.get("date", ""))
        for entry in days
        if isinstance(entry, dict)
    }
    groups_by_date = _state_market_groups(state_db_path, dates)
    refreshed_days = []
    for entry in days:
        day_date = entry["date"]
        direct_groups = groups_by_date.get(day_date, [])
        if direct_groups:
            pulses = [
                pulse
                for pulse in entry["pulses"]
                if pulse.get("category")
                not in {"ah_market_scan", "us_market_scan"}
            ]
            pulses.extend(
                _market_pulse_from_state_group(
                    day_date,
                    group,
                    holdings_terms=holdings_terms,
                    source_terms=source_terms,
                )
                for group in direct_groups
            )
            pulses.sort(key=lambda pulse: (clock_minutes(pulse["start"]), pulse["category"]))
        else:
            pulses = list(entry["pulses"])
        public_market_copy = " ".join(
            f"{pulse.get('summary_zh', '')} {pulse.get('summary_en', '')}"
            for pulse in pulses
            if pulse.get("category") in {"ah_market_scan", "us_market_scan"}
        )
        assert_private_terms_absent(
            public_market_copy,
            holdings_terms=holdings_terms,
            source_terms=source_terms,
        )
        refreshed_days.append({"date": day_date, "pulses": pulses})
    return {**snapshot, "days": refreshed_days}


def merge_market_receipt_reprojection(
    existing: dict,
    rebuilt: dict,
    *,
    holdings_terms: Sequence[str],
    source_terms: Sequence[str],
) -> tuple[dict, dict[str, int]]:
    """Replace every historical market pulse while preserving other categories.

    ``rebuilt`` may intentionally withhold reminder wording. Only its market
    projections are admitted; reminder, Agent, artwork, and other public pulses
    remain byte-for-byte equivalent as JSON values to the existing snapshot.
    """
    if existing.get("schema") != PULSE_SNAPSHOT_SCHEMA:
        fail("Market receipt re-projection requires the current pulse snapshot schema")
    if rebuilt.get("schema") != PULSE_SNAPSHOT_SCHEMA:
        fail("Rebuilt market evidence has an invalid pulse snapshot schema")
    existing_days = existing.get("days")
    rebuilt_days = rebuilt.get("days")
    if not isinstance(existing_days, list) or not isinstance(rebuilt_days, list):
        fail("Market receipt re-projection requires day lists")

    rebuilt_by_date = {
        entry.get("date"): entry
        for entry in rebuilt_days
        if isinstance(entry, dict) and isinstance(entry.get("date"), str)
    }
    if len(rebuilt_by_date) != len(rebuilt_days):
        fail("Rebuilt market evidence contains invalid or duplicate dates")

    refreshed_days = []
    replaced = 0
    added = 0
    legacy_normalized = 0
    refreshed_dates = 0
    for entry in existing_days:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("date"), str)
            or not isinstance(entry.get("pulses"), list)
        ):
            fail("Existing pulse snapshot contains an invalid day")
        day_date = entry["date"]
        rebuilt_entry = rebuilt_by_date.get(day_date)
        if rebuilt_entry is None or not isinstance(rebuilt_entry.get("pulses"), list):
            fail("Rebuilt market evidence does not cover every public date")
        existing_market = [
            pulse
            for pulse in entry["pulses"]
            if pulse.get("category") in MARKET_CATEGORIES
        ]
        rebuilt_market = [
            pulse
            for pulse in rebuilt_entry["pulses"]
            if pulse.get("category") in MARKET_CATEGORIES
        ]
        if existing_market and not rebuilt_market:
            rebuilt_market = [
                normalize_legacy_market_pulse(pulse)
                for pulse in existing_market
            ]
            legacy_normalized += len(rebuilt_market)
        non_market = [
            pulse
            for pulse in entry["pulses"]
            if pulse.get("category") not in MARKET_CATEGORIES
        ]
        pulses = [*non_market, *rebuilt_market]
        pulses.sort(
            key=lambda pulse: (
                clock_minutes(pulse["start"]),
                str(pulse.get("category", "")),
            )
        )
        public_market_copy = " ".join(
            f"{pulse.get('summary_zh', '')} {pulse.get('summary_en', '')}"
            for pulse in rebuilt_market
        )
        assert_private_terms_absent(
            public_market_copy,
            holdings_terms=holdings_terms,
            source_terms=source_terms,
        )
        replaced += len(existing_market)
        added += max(0, len(rebuilt_market) - len(existing_market))
        refreshed_dates += int(bool(existing_market or rebuilt_market))
        refreshed_days.append({**entry, "pulses": pulses})

    return (
        {**existing, "days": refreshed_days},
        {
            "replaced": replaced,
            "added": added,
            "legacy_normalized": legacy_normalized,
            "date_coverage": refreshed_dates,
        },
    )


def normalize_legacy_market_pulse(pulse: dict) -> dict:
    """Remove obsolete no-information copy when raw receipts are unavailable."""
    category = pulse.get("category")
    if category not in MARKET_CATEGORIES:
        fail("Legacy market normalization received a non-market pulse")
    count = pulse.get("count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        fail("Legacy market normalization requires a positive count")
    combined = f"{pulse.get('summary_zh', '')} {pulse.get('summary_en', '')}"
    label_zh = "A/H 市场扫描" if category == "ah_market_scan" else "美股市场扫描"
    label_en = "A/H market scan" if category == "ah_market_scan" else "U.S. market scan"
    states = (
        (DEFENSIVE_RE, "防守 / 风险收缩", "defensive / risk-contraction"),
        (OFFENSIVE_RE, "进攻 / 风险扩张", "offensive / risk-expansion"),
        (BALANCED_RE, "均衡 / 中性", "balanced / neutral"),
    )
    state = next(
        ((zh, en) for pattern, zh, en in states if pattern.search(combined)),
        None,
    )
    themes = [
        (zh, en)
        for pattern, zh, en in SAFE_MARKET_THEMES
        if pattern.search(combined)
    ][:2]
    clues_zh = []
    clues_en = []
    if state is not None:
        clues_zh.append(f"状态 {state[0]}")
        clues_en.append(f"regime {state[1]}")
    if themes:
        clues_zh.append("主题 " + "、".join(theme[0] for theme in themes))
        clues_en.append("themes " + ", ".join(theme[1] for theme in themes))
    if WARNING_RE.search(combined):
        clues_zh.append("数据或链路新鲜度提示")
        clues_en.append("a data or pipeline-freshness warning")
    if not clues_zh:
        clues_zh.append("市场扫描足迹")
        clues_en.append("a public market-scan footprint")
    summary_zh = f"{count} 次{label_zh}；{'；'.join(clues_zh)}。"
    summary_en = f"{count} {label_en} run(s); {'; '.join(clues_en)}."
    return {
        **pulse,
        "summary_zh": summary_zh,
        "summary_en": summary_en,
        "summary_provenance": "derived_public_safe",
    }


def aggregate_public_market_copy(snapshot: dict) -> dict:
    """Keep routine market cards useful without exposing instruments or terminals."""
    days = snapshot.get("days")
    if not isinstance(days, list):
        fail("Market aggregation requires a pulse day list")
    aggregated_days = []
    for entry in days:
        if not isinstance(entry, dict) or not isinstance(entry.get("pulses"), list):
            fail("Market aggregation received an invalid pulse day")
        pulses = [
            normalize_legacy_market_pulse(pulse)
            if isinstance(pulse, dict) and pulse.get("category") in MARKET_CATEGORIES
            else pulse
            for pulse in entry["pulses"]
        ]
        aggregated_days.append({**entry, "pulses": pulses})
    return {**snapshot, "days": aggregated_days}


def refresh_market_snapshot_from_receipts(
    *,
    snapshot_path: Path,
    jobs_path: Path,
    output_dir: Path,
    public_days_path: Path,
    state_db_path: Path | None,
    holdings_terms: Sequence[str],
    source_terms: Sequence[str],
) -> tuple[dict, dict[str, int]]:
    """Re-project the full receipt history without rebuilding reminder copy."""
    try:
        existing = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except OSError:
        fail("Could not read existing pulse snapshot")
    except json.JSONDecodeError:
        fail("Existing pulse snapshot is not valid JSON")
    rebuilt = build_snapshot(
        jobs_path,
        output_dir,
        public_days_path,
        state_db_path,
        holdings_terms=holdings_terms,
        source_terms=source_terms,
    )
    return merge_market_receipt_reprojection(
        existing,
        rebuilt,
        holdings_terms=holdings_terms,
        source_terms=source_terms,
    )


def resanitize_existing_reminders(
    *,
    snapshot_path: Path,
    translations: dict[str, dict[str, str]],
    holdings_terms: Sequence[str],
    source_terms: Sequence[str],
) -> tuple[dict, dict[str, int]]:
    """Apply current private denylists to authorized reminder projections.

    Only already-public projection fields are consumed. An already-sanitized
    record may no longer hash to its pre-sanitization sidecar key; it is accepted
    only when it has no denied terms and still satisfies summary mask parity.
    """
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except OSError:
        fail("Could not read existing pulse snapshot")
    except json.JSONDecodeError:
        fail("Existing pulse snapshot is not valid JSON")
    if snapshot.get("schema") != PULSE_SNAPSHOT_SCHEMA:
        fail("Reminder re-sanitization requires the current pulse snapshot schema")
    days = snapshot.get("days")
    if not isinstance(days, list):
        fail("Pulse snapshot must contain days")

    stats = {"checked": 0, "changed": 0, "already_sanitized": 0}
    required = (
        "summary_original",
        "excerpt_original",
        "summary_en",
        "excerpt_en",
        "redaction_count",
        "projection_kind",
        "semantic_abstraction_count",
    )
    for day in days:
        if not isinstance(day, dict) or not isinstance(day.get("pulses"), list):
            fail("Pulse snapshot contains an invalid day")
        for pulse in day["pulses"]:
            if (
                not isinstance(pulse, dict)
                or pulse.get("category") != "daily_reminder"
                or pulse.get("summary_provenance")
                != PROJECTION_PROVENANCE
            ):
                continue
            stats["checked"] += 1
            if not all(field in pulse for field in required):
                fail("Authorized reminder projection is incomplete")
            if (
                not all(
                    isinstance(pulse[field], str)
                    for field in (
                        "summary_original",
                        "excerpt_original",
                        "summary_en",
                        "excerpt_en",
                        "projection_kind",
                    )
                )
                or not isinstance(pulse["redaction_count"], int)
                or isinstance(pulse["redaction_count"], bool)
                or pulse["redaction_count"] < 0
            ):
                fail("Authorized reminder projection has invalid public fields")
            source_sha256 = hashlib.sha256(
                pulse["summary_original"].encode("utf-8")
            ).hexdigest()
            before = tuple(pulse[field] for field in required)
            if source_sha256 not in translations:
                for field in (
                    "summary_original",
                    "excerpt_original",
                    "summary_en",
                    "excerpt_en",
                ):
                    pulse[field] = replace_private_terms(
                        pulse[field],
                        holdings_terms,
                        FIXED_REDACTION_BLOCK,
                        contextual_ambiguous=True,
                    )
                    pulse[field] = replace_private_terms(
                        pulse[field],
                        source_terms,
                        FIXED_REDACTION_BLOCK,
                    )
                    assert_private_terms_absent(
                        pulse[field],
                        holdings_terms=holdings_terms,
                        source_terms=source_terms,
                    )
                source_masks = mask_token_count(
                    pulse["summary_original"],
                    "Previously sanitized reminder source",
                )
                translation_masks = mask_token_count(
                    pulse["summary_en"],
                    "Previously sanitized reminder translation",
                )
                if source_masks != translation_masks:
                    fail("Previously sanitized reminder summary mask parity mismatch")
                (
                    pulse["summary_original"],
                    pulse["summary_en"],
                    pulse["excerpt_original"],
                    pulse["excerpt_en"],
                ) = parity_preserving_reminder_fields(
                        pulse["summary_original"],
                        pulse["summary_en"],
                )
                source_masks = mask_token_count(
                    pulse["summary_original"],
                    "Balanced previously sanitized reminder source",
                )
                pulse["redaction_count"] = source_masks
                pulse["projection_kind"] = projection_kind_for_counts(
                    source_masks,
                    pulse["semantic_abstraction_count"],
                )
            else:
                sanitized = translation_for_reminder(
                    {field: pulse[field] for field in required},
                    translations,
                    holdings_terms=holdings_terms,
                    source_terms=source_terms,
                )
                pulse.update(sanitized)
            after = tuple(pulse[field] for field in required)
            stats["changed"] += int(before != after)
            stats["already_sanitized"] += int(before == after)

    assert_private_terms_absent(
        json.dumps(snapshot, ensure_ascii=False),
        holdings_terms=holdings_terms,
        source_terms=source_terms,
    )
    return snapshot, stats


def validate_snapshot_reminder_parity(snapshot: dict) -> None:
    """Fail before serialization unless all four reminder fields are in parity."""
    for day in snapshot.get("days", []):
        for pulse in day.get("pulses", []):
            if (
                not isinstance(pulse, dict)
                or pulse.get("category") != "daily_reminder"
                or pulse.get("summary_provenance")
                != PROJECTION_PROVENANCE
            ):
                continue
            try:
                summary_original = pulse["summary_original"]
                summary_en = pulse["summary_en"]
                excerpt_original = pulse["excerpt_original"]
                excerpt_en = pulse["excerpt_en"]
            except KeyError:
                fail("Authorized reminder projection is incomplete")
            summary_masks = mask_token_count(
                summary_original,
                "Reminder original summary",
            )
            if summary_masks != mask_token_count(
                summary_en,
                "Reminder English summary",
            ):
                fail("Reminder summary mask parity mismatch")
            if mask_token_count(
                excerpt_original,
                "Reminder original excerpt",
            ) != mask_token_count(excerpt_en, "Reminder English excerpt"):
                fail("Reminder excerpt mask parity mismatch")
            if pulse.get("redaction_count") != summary_masks:
                fail("Reminder redaction metadata mismatch")
            if pulse.get("projection_kind") != projection_kind_for_counts(
                summary_masks,
                int(pulse.get("semantic_abstraction_count", 0)),
            ):
                fail("Reminder semantic projection metadata mismatch")
            for summary, excerpt in (
                (summary_original, excerpt_original),
                (summary_en, excerpt_en),
            ):
                if len(summary) <= 260 and excerpt != summary:
                    fail("Short reminder excerpt must equal its summary")
                if not (
                    excerpt == summary
                    or (
                        isinstance(excerpt, str)
                        and excerpt.endswith("…")
                        and summary.startswith(excerpt[:-1])
                    )
                ):
                    fail("Reminder excerpt is not a faithful extractive prefix")


def sanitize_reminder_translation_catalog(
    translations: dict[str, dict[str, str]],
    *,
    holdings_terms: Sequence[str],
    source_terms: Sequence[str],
) -> tuple[dict[str, dict[str, str]], int]:
    """Sanitize the tracked translation sidecar without changing lookup keys."""
    sanitized: dict[str, dict[str, str]] = {}
    changed = 0
    for source_sha256, source_record in translations.items():
        record = dict(source_record)
        for field in ("summary_en", "excerpt_en"):
            value = replace_private_terms(
                record[field],
                holdings_terms,
                FIXED_REDACTION_BLOCK,
                contextual_ambiguous=True,
            )
            value = replace_private_terms(
                value,
                source_terms,
                FIXED_REDACTION_BLOCK,
            )
            assert_private_terms_absent(
                value,
                holdings_terms=holdings_terms,
                source_terms=source_terms,
            )
            changed += int(value != record[field])
            record[field] = value
        sanitized[source_sha256] = validate_reminder_translation_record(
            source_sha256,
            record,
        )
    return sanitized, changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--public-days", type=Path, default=DEFAULT_PUBLIC_DAYS)
    parser.add_argument("--state-db", type=Path, default=DEFAULT_STATE_DB)
    parser.add_argument(
        "--no-session-state",
        action="store_true",
        help="Do not read a session-state database; use receipt timestamp estimates.",
    )
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument(
        "--holdings-denylist",
        type=Path,
        default=DEFAULT_HOLDINGS_DENYLIST,
        help="Ignored private holdings/company/ticker denylist.",
    )
    parser.add_argument(
        "--self-media-denylist",
        type=Path,
        default=DEFAULT_SELF_MEDIA_DENYLIST,
        help="Ignored private source-attribution denylist.",
    )
    parser.add_argument(
        "--reminder-translations",
        type=Path,
        default=DEFAULT_REMINDER_TRANSLATIONS,
        help=(
            "Versioned public-safe English translation catalog for authentic "
            "reminders. Missing or invalid records fail closed."
        ),
    )
    parser.add_argument(
        "--date",
        dest="dates",
        action="append",
        help=(
            "Replace only this YYYY-MM-DD day in an existing snapshot while "
            "preserving every other public day; repeat for multiple dates."
        ),
    )
    parser.add_argument(
        "--authorize-self-reminders",
        action="store_true",
        help=(
            "Explicitly authorize the reminder runs as self-owned. Without this "
            "flag their wording is not published."
        ),
    )
    parser.add_argument(
        "--authorize-authentic-reminder-disclosure",
        action="store_true",
        help=(
            "Preserve reminder wording and order while masking only identifying "
            "entities and technical secrets. Requires --authorize-self-reminders "
            "and fails closed if batch entity detection fails."
        ),
    )
    parser.add_argument(
        "--authorize-self-reminder-residues",
        dest="authorize_self_reminders",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--authorize-limited-reminder-disclosure",
        dest="authorize_authentic_reminder_disclosure",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--private-redaction-terms",
        type=Path,
        help=(
            "Ignored .private JSON string list of exact identifying terms to mask "
            "longest-first. Terms are never serialized."
        ),
    )
    parser.add_argument(
        "--public-identity-allowlist",
        type=Path,
        default=DEFAULT_PUBLIC_IDENTITY_ALLOWLIST,
        help="Tracked explicit owner-name authorization applied to identity masking.",
    )
    parser.add_argument(
        "--test-only-bypass-entity-detector",
        action="store_true",
        help=(
            "TEST ONLY: deliberately bypass Apple entity detection for synthetic "
            "fixtures; never use for an authentic import."
        ),
    )
    parser.add_argument(
        "--refresh-reminders-only",
        action="store_true",
        help=(
            "Replace reminder evidence from the current receipts while "
            "preserving matching existing public footprints and all "
            "non-reminder pulses."
        ),
    )
    parser.add_argument(
        "--refresh-markets-from-state",
        action="store_true",
        help=(
            "Replace only market pulses backed by direct cron-session evidence "
            "in the Hermes state database."
        ),
    )
    parser.add_argument(
        "--reproject-markets-from-receipts",
        action="store_true",
        help=(
            "Re-project all historical A/H and U.S. market receipt evidence "
            "while preserving every existing non-market pulse."
        ),
    )
    parser.add_argument(
        "--resanitize-existing-reminders",
        action="store_true",
        help=(
            "Re-apply current private denylists to already-authorized public "
            "reminder projections without ingesting newer receipt content."
        ),
    )
    return parser.parse_args()


def merge_date_scoped_snapshot(
    existing_path: Path,
    rebuilt_snapshot: dict,
    requested_dates: set[str],
) -> dict:
    """Merge selected rebuilt days without rewriting older public evidence."""
    if not existing_path.exists():
        fail("Date-scoped pulse import requires an existing snapshot")
    try:
        existing_snapshot = json.loads(existing_path.read_text(encoding="utf-8"))
    except OSError:
        fail("Could not read existing pulse snapshot")
    except json.JSONDecodeError:
        fail("Existing pulse snapshot is not valid JSON")
    if existing_snapshot.get("schema") != PULSE_SNAPSHOT_SCHEMA:
        fail(
            "Date-scoped import requires a current v6 snapshot; perform one full "
            "authentic reminder import to migrate older snapshots"
        )
    existing_days = existing_snapshot.get("days")
    rebuilt_days = rebuilt_snapshot.get("days")
    if not isinstance(existing_days, list) or not isinstance(rebuilt_days, list):
        fail("Pulse snapshots must contain day lists")
    existing_by_date = {
        entry.get("date"): entry
        for entry in existing_days
        if isinstance(entry, dict)
    }
    rebuilt_by_date = {
        entry.get("date"): entry
        for entry in rebuilt_days
        if isinstance(entry, dict)
    }
    if len(existing_by_date) != len(existing_days):
        fail("Existing pulse snapshot contains an invalid or duplicate date")
    if len(rebuilt_by_date) != len(rebuilt_days):
        fail("Rebuilt pulse snapshot contains an invalid or duplicate date")
    unknown_dates = requested_dates.difference(rebuilt_by_date)
    if unknown_dates:
        fail(f"Requested pulse dates are not public: {', '.join(sorted(unknown_dates))}")
    merged_by_date = dict(existing_by_date)
    for day_date in requested_dates:
        merged_by_date[day_date] = rebuilt_by_date[day_date]
    extra_dates = set(merged_by_date).difference(rebuilt_by_date)
    if extra_dates:
        fail(
            "Date-scoped pulse merge contains dates outside the public day set: "
            f"extra={sorted(extra_dates)}"
        )
    # A newly published artwork day is intentionally allowed to have no pulse
    # entry yet.  The morning closure publishes the artwork first; that day's
    # routine/collaboration evidence is imported by the next civil-day closure.
    # Requiring every rebuilt public day here made a scoped update for yesterday
    # fail as soon as today's artwork entered days.json.
    return {
        **rebuilt_snapshot,
        "days": [merged_by_date[day_date] for day_date in sorted(merged_by_date)],
    }


def clock_minutes(value: str) -> int:
    if value == "24:00":
        return 24 * 60
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def merge_reminder_refresh(
    existing_path: Path,
    rebuilt_snapshot: dict,
) -> tuple[dict, dict[str, int]]:
    """Replace reminder evidence while preserving matching public footprints.

    Existing non-reminder pulses are retained exactly. A fresh reminder may
    reuse an existing public timing window only when date, bucket, run count,
    and receipt-adjacent end time all agree. Unmatched fresh reminders keep
    their truthful receipt-timestamp estimate. Unmatched old reminders remain
    because receipt history and the current job catalog are partial indexes.
    """
    if not existing_path.exists():
        fail("Reminder refresh requires an existing public snapshot")
    try:
        existing_snapshot = json.loads(existing_path.read_text(encoding="utf-8"))
    except OSError:
        fail("Could not read existing pulse snapshot")
    except json.JSONDecodeError:
        fail("Existing pulse snapshot is not valid JSON")
    existing_days = existing_snapshot.get("days")
    rebuilt_days = rebuilt_snapshot.get("days")
    if not isinstance(existing_days, list) or not isinstance(rebuilt_days, list):
        fail("Pulse snapshots must contain day lists")
    existing_by_date = {
        entry.get("date"): entry
        for entry in existing_days
        if isinstance(entry, dict)
    }
    rebuilt_by_date = {
        entry.get("date"): entry
        for entry in rebuilt_days
        if isinstance(entry, dict)
    }
    if (
        len(existing_by_date) != len(existing_days)
        or len(rebuilt_by_date) != len(rebuilt_days)
        or set(existing_by_date) != set(rebuilt_by_date)
    ):
        fail("Reminder refresh snapshots must have the same unique public dates")
    existing_reminder_count = sum(
        1
        for day in existing_days
        for pulse in day.get("pulses", [])
        if pulse.get("category") == "daily_reminder"
    )
    fresh_reminder_count = sum(
        1
        for day in rebuilt_days
        for pulse in day.get("pulses", [])
        if pulse.get("category") == "daily_reminder"
    )
    if existing_reminder_count and not fresh_reminder_count:
        fail("Reminder refresh found no fresh reminder evidence")

    stats = {
        "preserved_footprints": 0,
        "receipt_estimate_footprints": 0,
        "removed_stale_reminders": 0,
        "preserved_unmatched_reminders": 0,
    }
    observed_session_window_count = int(
        existing_snapshot.get("observed_session_window_count", 0)
    )
    merged_days = []
    for day_date in sorted(rebuilt_by_date):
        old_pulses = existing_by_date[day_date].get("pulses", [])
        fresh_pulses = rebuilt_by_date[day_date].get("pulses", [])
        if not isinstance(old_pulses, list) or not isinstance(fresh_pulses, list):
            fail(f"{day_date} pulse lists are invalid")
        non_reminders = [
            dict(pulse)
            for pulse in old_pulses
            if pulse.get("category") != "daily_reminder"
        ]
        old_reminders = [
            pulse
            for pulse in old_pulses
            if pulse.get("category") == "daily_reminder"
        ]
        fresh_reminders = [
            dict(pulse)
            for pulse in fresh_pulses
            if pulse.get("category") == "daily_reminder"
        ]
        used_old: set[int] = set()
        preserved_fields = (
            "start",
            "end",
            "duration_minutes",
            "execution_minutes",
            "time_provenance",
        )
        for fresh in fresh_reminders:
            eligible = []
            for index, old in enumerate(old_reminders):
                if index in used_old:
                    continue
                if (
                    old.get("time_bucket") != fresh.get("time_bucket")
                    or old.get("count") != fresh.get("count")
                ):
                    continue
                try:
                    end_delta = abs(
                        clock_minutes(str(old["end"]))
                        - clock_minutes(str(fresh["end"]))
                    )
                except (KeyError, TypeError, ValueError):
                    continue
                if end_delta <= 30:
                    eligible.append((end_delta, index, old))
            if eligible:
                _, index, old = min(eligible, key=lambda item: (item[0], item[1]))
                used_old.add(index)
                for field in preserved_fields:
                    fresh[field] = old[field]
                stats["preserved_footprints"] += 1
            else:
                stats["receipt_estimate_footprints"] += 1
                if (
                    fresh.get("time_provenance")
                    == "observed_session_window"
                ):
                    observed_session_window_count += int(
                        fresh.get("count", 0)
                    )
        # Receipt history and the current jobs catalog are not a complete
        # historical index: renamed/retired reminder jobs may still have valid,
        # already-authorized public projections. Preserve unmatched old
        # reminders instead of treating absence from a partial refresh as proof
        # that the public record is stale.
        preserved_old = [
            dict(old)
            for index, old in enumerate(old_reminders)
            if index not in used_old
        ]
        stats["preserved_unmatched_reminders"] = (
            stats.get("preserved_unmatched_reminders", 0)
            + len(preserved_old)
        )

        combined = [*non_reminders, *preserved_old, *fresh_reminders]
        combined.sort(
            key=lambda pulse: (
                clock_minutes(str(pulse.get("start", "00:00"))),
                str(pulse.get("category", "")),
            )
        )
        merged_days.append({"date": day_date, "pulses": combined})

    return (
        {
            **rebuilt_snapshot,
            "observed_session_window_count": observed_session_window_count,
            "days": merged_days,
        },
        stats,
    )


def main() -> int:
    args = parse_args()
    refresh_markets = getattr(args, "refresh_markets_from_state", False)
    reproject_markets = getattr(args, "reproject_markets_from_receipts", False)
    resanitize_reminders = getattr(
        args,
        "resanitize_existing_reminders",
        False,
    )
    if args.refresh_reminders_only and args.dates:
        fail("--refresh-reminders-only cannot be combined with --date")
    if refresh_markets and reproject_markets:
        fail("Market refresh modes cannot be combined")
    if (refresh_markets or reproject_markets) and (
        args.refresh_reminders_only or args.dates
    ):
        fail("Market refresh cannot be combined with reminder/date refresh")
    if resanitize_reminders and (
        refresh_markets
        or reproject_markets
        or args.refresh_reminders_only
        or args.dates
    ):
        fail(
            "--resanitize-existing-reminders cannot be combined with another "
            "refresh mode"
        )
    holdings_path = getattr(args, "holdings_denylist", None)
    sources_path = getattr(args, "self_media_denylist", None)
    holdings_terms = (
        load_private_denylist(holdings_path, "holdings")
        if holdings_path is not None
        else ()
    )
    source_terms = (
        load_private_denylist(sources_path, "self_media_sources")
        if sources_path is not None
        else ()
    )
    reminder_resanitize_stats = None
    sanitized_translation_catalog = None
    sanitized_translation_change_count = 0
    market_receipt_refresh_stats = None
    if refresh_markets:
        snapshot = refresh_market_snapshot_from_state(
            snapshot_path=args.snapshot,
            state_db_path=args.state_db,
            holdings_terms=holdings_terms,
            source_terms=source_terms,
        )
    elif reproject_markets:
        if args.jobs is None or args.output_dir is None:
            fail("--jobs and --output-dir are required for receipt re-projection")
        snapshot, market_receipt_refresh_stats = (
            refresh_market_snapshot_from_receipts(
                snapshot_path=args.snapshot,
                jobs_path=args.jobs,
                output_dir=args.output_dir,
                public_days_path=args.public_days,
                state_db_path=(
                    None if args.no_session_state else args.state_db
                ),
                holdings_terms=holdings_terms,
                source_terms=source_terms,
            )
        )
    elif resanitize_reminders:
        sanitized_translation_catalog, sanitized_translation_change_count = (
            sanitize_reminder_translation_catalog(
                load_reminder_translations(args.reminder_translations),
                holdings_terms=holdings_terms,
                source_terms=source_terms,
            )
        )
        snapshot, reminder_resanitize_stats = resanitize_existing_reminders(
            snapshot_path=args.snapshot,
            translations=sanitized_translation_catalog,
            holdings_terms=holdings_terms,
            source_terms=source_terms,
        )
    else:
        if args.jobs is None or args.output_dir is None:
            fail("--jobs and --output-dir are required for a receipt import")
        snapshot = build_snapshot(
            args.jobs,
            args.output_dir,
            args.public_days,
            None if args.no_session_state else args.state_db,
            authorize_self_reminders=args.authorize_self_reminders,
            authorize_authentic_reminder_disclosure=(
                args.authorize_authentic_reminder_disclosure
            ),
            private_redaction_terms=load_private_redaction_terms(
                args.private_redaction_terms,
                getattr(
                    args,
                    "public_identity_allowlist",
                    DEFAULT_PUBLIC_IDENTITY_ALLOWLIST,
                ),
            ),
            holdings_terms=holdings_terms,
            source_terms=source_terms,
            allow_entity_detector_bypass_for_tests=(
                args.test_only_bypass_entity_detector
            ),
            reminder_translations_path=args.reminder_translations,
            translation_required_dates=(
                set(args.dates) if args.dates else None
            ),
        )
    reminder_refresh_stats = None
    if args.refresh_reminders_only:
        snapshot, reminder_refresh_stats = merge_reminder_refresh(
            args.snapshot,
            snapshot,
        )
    if args.dates:
        snapshot = merge_date_scoped_snapshot(
            args.snapshot,
            snapshot,
            set(args.dates),
        )
    snapshot = aggregate_public_market_copy(snapshot)
    validate_snapshot_reminder_parity(snapshot)
    empty_dates = [entry["date"] for entry in snapshot["days"] if not entry["pulses"]]
    if empty_dates:
        fail(f"Public dates without cron run evidence: {', '.join(empty_dates)}")
    if sanitized_translation_catalog is not None and sanitized_translation_change_count:
        args.reminder_translations.write_text(
            json.dumps(
                {
                    "schema": REMINDER_TRANSLATION_SCHEMA,
                    "translation_provenance": REMINDER_TRANSLATION_PROVENANCE,
                    "translations": sanitized_translation_catalog,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    args.snapshot.parent.mkdir(parents=True, exist_ok=True)
    args.snapshot.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "Wrote public timetable pulses: "
        f"{snapshot['source_file_count']} files -> "
        f"{snapshot['deduplicated_run_count']} runs -> "
        f"{sum(len(day['pulses']) for day in snapshot['days'])} pulses across "
        f"{len(snapshot['days'])} dates."
    )
    if reminder_refresh_stats is not None:
        projection_counts: dict[str, int] = defaultdict(int)
        reminder_dates = set()
        for day in snapshot["days"]:
            for pulse in day["pulses"]:
                if pulse["category"] != "daily_reminder":
                    continue
                reminder_dates.add(day["date"])
                projection_counts[pulse.get("projection_kind", "withheld")] += (
                    pulse["count"]
                )
        print(
            "Reminder projection aggregates: "
            f"verbatim={projection_counts['verbatim']}, "
            f"verbatim-redacted={projection_counts['verbatim_redacted']}, "
            f"semantic-abstracted={projection_counts['semantic_abstracted']}, "
            f"semantic-abstracted-redacted="
            f"{projection_counts['semantic_abstracted_redacted']}, "
            f"withheld={projection_counts['withheld']}, "
            f"date-coverage={len(reminder_dates)}, "
            f"preserved-footprints={reminder_refresh_stats['preserved_footprints']}, "
            f"receipt-estimates={reminder_refresh_stats['receipt_estimate_footprints']}, "
            f"preserved-unmatched="
            f"{reminder_refresh_stats['preserved_unmatched_reminders']}, "
            f"removed-stale={reminder_refresh_stats['removed_stale_reminders']}."
        )
    if reminder_resanitize_stats is not None:
        print(
            "Reminder re-sanitization: "
            f"{reminder_resanitize_stats['checked']} checked, "
            f"{reminder_resanitize_stats['changed']} changed, "
            f"{reminder_resanitize_stats['already_sanitized']} already safe, "
            f"{sanitized_translation_change_count} sidecar field(s) changed."
        )
    if market_receipt_refresh_stats is not None:
        print(
            "Market receipt re-projection: "
            f"{market_receipt_refresh_stats['replaced']} replaced, "
            f"{market_receipt_refresh_stats['added']} newly evidenced, "
            f"{market_receipt_refresh_stats['legacy_normalized']} legacy-only normalized, "
            f"date-coverage={market_receipt_refresh_stats['date_coverage']}."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
