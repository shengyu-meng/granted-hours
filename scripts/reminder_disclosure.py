#!/usr/bin/env python3
"""Semantic public projection for explicitly authorized reminders.

Private response sections are joined in source order and masked in memory.
Sensitive personal, commercial, and infrastructure blocks are abstracted
before identifying entities and structured technical secrets are masked. The
public projection contains only the curated public text, an extractive card
excerpt, language metadata, and non-identifying provenance.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from semantic_public_policy import abstract_sensitive_public_text

FIXED_REDACTION_BLOCK = "████"
DISCLOSURE_POLICY = "semantic_abstraction_entity_masked_reminder_v3"
DISCLOSURE_AUTHORIZATION = "explicit_user_authorization_2026-07-29"
REDACTION_POLICY = "semantic_abstraction_then_entity_mask_v3"
PROJECTION_PROVENANCE = "semantic_public_projection"

MAX_SOURCE_LENGTH = 50_000
MAX_EXCERPT_LENGTH = 260

TIME_LABELS = {
    "overnight": ("夜间提醒", "Overnight reminder"),
    "dawn": ("晨间提醒", "Morning reminder"),
    "morning": ("晨间提醒", "Morning reminder"),
    "midday": ("午间提醒", "Midday reminder"),
    "afternoon": ("午间提醒", "Midday reminder"),
    "evening": ("晚间提醒", "Evening reminder"),
}

HAN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
LATIN_RE = re.compile(r"[A-Za-z]")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\n]+)\)")
PLAIN_URL_RE = re.compile(r"(?i)\bhttps?://[^\s<>\])}]+")
EMAIL_RE = re.compile(r"(?i)(?<![\w.+-])[\w.+-]+@(?:[\w-]+\.)+[A-Za-z]{2,}(?![\w.-])")
LOCAL_PATH_RE = re.compile(
    r"""(?x)
    (?:
        /(?:Users|home)/[^\s，。；！？!?<>"'`]+
        |
        [A-Za-z]:\\[^\s，。；！？!?<>"'`]+
    )
    """
)
PRIVATE_STORAGE_RE = re.compile(
    r"(?i)(?:\.hermes|profiles?[/\\]heizhou|state\.db|cron[/\\](?:jobs\.json|output))"
)
CHINESE_MOBILE_RE = re.compile(
    r"(?<!\d)(?:\+?86[-.\s]?)?1[3-9]\d(?:[-.\s]?\d{4}){2}(?!\d)"
)
NORTH_AMERICAN_PHONE_RE = re.compile(
    r"(?<!\d)(?:\(\d{3}\)|\d{3})[-.\s]\d{3}[-.\s]\d{4}(?!\d)"
)
INTERNATIONAL_PHONE_RE = re.compile(
    r"(?<![\d-])\+\d{1,3}(?:[-.\s]?\(?\d{2,4}\)?){2,5}(?!\d)"
)
PHONE_CONTEXT_RE = re.compile(
    r"""(?ix)
    (?P<label>\b(?:phone|mobile|tel(?:ephone)?)\b|电话|手机|拨打)
    (?P<separator>\s*[:：=]?\s*)
    (?P<value>\+?[\d().\s-]{7,24})
    """
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"""(?ix)
    (?P<label>
        \b(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|token|
        password|passwd|secret)\b
        |API\s*密钥|访问令牌|刷新令牌|口令|密码
    )
    (?P<separator>\s*[:：=]\s*)
    (?P<value>["']?[^\s，。,；;]+["']?)
    """
)
IDENTIFIER_ASSIGNMENT_RE = re.compile(
    r"""(?ix)
    (?P<label>
        \b(?:account|user|chat|thread|session|conversation)[_ -]?id\b
        |账户ID|用户ID|聊天ID|会话ID
    )
    (?P<separator>\s*[:：=]\s*)
    (?P<value>["']?-?[A-Za-z0-9._:-]{4,}["']?)
    """
)
RAW_TOKEN_RE = re.compile(
    r"""(?ix)
    (?<![A-Za-z0-9_-])
    (?:
        sk-(?:proj-)?[A-Za-z0-9_-]{6,}
        |ghp_[A-Za-z0-9]{20,}
        |github_pat_[A-Za-z0-9_]{20,}
        |xox[baprs]-[A-Za-z0-9-]{10,}
        |(?:eyJ[A-Za-z0-9_-]{8,}\.){2}[A-Za-z0-9_-]{8,}
        |\d{6,}:[A-Za-z0-9_-]{20,}
    )
    (?![A-Za-z0-9_-])
    """
)
UUID_RE = re.compile(
    r"(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b"
)
BOOK_TITLE_RE = re.compile(r"《([^》\n]+)》")

QUOTE_PAIRS = (
    ("“", "”"),
    ("‘", "’"),
    ("「", "」"),
    ("『", "』"),
    ('"', '"'),
    ("'", "'"),
    ("`", "`"),
)
ENTITY_KEYWORD = (
    r"(?:作品|艺术品|项目|课题|计划|标题|题名|题为|名为|名称|叫|"
    r"做完了|完成了|做了一件|完成了一件|"
    r"artwork|work|project|programme|program|initiative|title|titled|named|called|"
    r"created|made|finished)"
)
KEYWORD_BEFORE_QUOTE_RES = tuple(
    re.compile(
        rf"(?i)(?P<prefix>{ENTITY_KEYWORD}(?:\s*(?:是|为|叫做|[:：-]))?\s*)"
        rf"{re.escape(opening)}(?P<entity>[^{re.escape(closing)}\n]+){re.escape(closing)}"
    )
    for opening, closing in QUOTE_PAIRS
)
QUOTE_BEFORE_KEYWORD_RES = tuple(
    re.compile(
        rf"(?i){re.escape(opening)}(?P<entity>[^{re.escape(closing)}\n]+)"
        rf"{re.escape(closing)}(?P<suffix>\s*(?:的\s*(?:那个\s*)?(?:Canvas\s*)?)?{ENTITY_KEYWORD})"
    )
    for opening, closing in QUOTE_PAIRS
)
KEYWORD_BEFORE_EMPHASIS_RE = re.compile(
    rf"(?i)(?P<prefix>{ENTITY_KEYWORD}(?:\s*(?:是|为|叫做|[:：-]))?\s*)"
    rf"(?P<mark>\*\*|__)(?P<entity>[^\n]+?)(?P=mark)"
)
EMPHASIS_BEFORE_KEYWORD_RE = re.compile(
    rf"(?i)(?P<mark>\*\*|__)(?P<entity>[^\n]+?)(?P=mark)"
    rf"(?P<suffix>\s*(?:的\s*(?:那个\s*)?(?:Canvas\s*)?)?{ENTITY_KEYWORD})"
)
ADJACENT_MASK_RE = re.compile(
    rf"{re.escape(FIXED_REDACTION_BLOCK)}(?:[ \t]*{re.escape(FIXED_REDACTION_BLOCK)})+"
)


class EntityDetectionError(RuntimeError):
    """Raised when authorized batch entity detection cannot complete safely."""


def projection_kind_for_counts(
    redaction_count: int,
    semantic_abstraction_count: int,
) -> str:
    if semantic_abstraction_count and redaction_count:
        return "semantic_abstracted_redacted"
    if semantic_abstraction_count:
        return "semantic_abstracted"
    if redaction_count:
        return "verbatim_redacted"
    return "verbatim"


def join_reminder_responses(responses: Iterable[str]) -> str:
    """Join final response sections once, preserving order and exact structure."""
    sections: list[str] = []
    seen: set[str] = set()
    for response in responses:
        section = str(response or "").strip()
        if not section or section == "[SILENT]" or section in seen:
            continue
        if is_delivery_report(section):
            continue
        seen.add(section)
        sections.append(section)
    return "\n\n".join(sections)


def is_delivery_report(text: str) -> bool:
    """True when a response is a JSON/delivery confirmation without reminder content."""
    if not text or len(text) > 800:
        return False
    report_pattern = re.compile(
        r"(?is)"
        r"验证完成[。.!]?\s*(?:json)?\s*结构完整|"
        r"json\s*结构完整|json\s*投递|投递完毕|投递完成|"
        r"交付物已在上一轮输出|无遗留问题|"
        r"json\s*(?:校验|结构)\s*(?:通过|验证通过)|已处理完毕|"
        r"无需(?:进一步验证|进一步操作|重复验证)|valid\s+json|"
        r"reminder\s+is\s+noted|this\s+edit\s+was\s+a\s+json|"
        r"(?:verification|delivery)\s+is\s+complete|"
        r"json\s+structure\s+is\s+(?:intact|complete)|"
        r"deliver(?:ed|y)\s+(?:of\s+)?(?:the\s+)?(?:reminder|message)\s+(?:successfully|complete)|"
        r"已投递|已发送完毕|新增条目字段齐全"
    )
    if not report_pattern.search(text):
        return False
    reminder_marker = re.compile(
        r"(?is)源泉|早安|早上好|晚安|晨间|提醒|日记|reflection|"
        r"wellspring|good\s+morning|good\s+night|remember|priority|计划|优先级"
    )
    return not reminder_marker.search(text)


def detect_original_language(text: str) -> str:
    has_han = HAN_RE.search(text) is not None
    has_latin = LATIN_RE.search(text) is not None
    if has_han and has_latin:
        return "mixed"
    if has_han:
        return "zh"
    if has_latin:
        return "en"
    return "mixed"


def _replacement(label: str = "", separator: str = "") -> str:
    return f"{label}{separator}{FIXED_REDACTION_BLOCK}"


def _mask_regex(
    text: str,
    pattern: re.Pattern[str],
    *,
    replacement: str = FIXED_REDACTION_BLOCK,
) -> tuple[str, int]:
    return pattern.subn(replacement, text)


def _mask_assignment(
    text: str,
    pattern: re.Pattern[str],
) -> tuple[str, int]:
    return pattern.subn(
        lambda match: _replacement(match.group("label"), match.group("separator")),
        text,
    )


def _mask_phone_context(text: str) -> tuple[str, int]:
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        value = match.group("value").strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) or re.fullmatch(
            r"\d{1,2}:\d{2}", value
        ):
            return match.group(0)
        digit_count = sum(character.isdigit() for character in value)
        if not 7 <= digit_count <= 15:
            return match.group(0)
        count += 1
        return _replacement(match.group("label"), match.group("separator"))

    return PHONE_CONTEXT_RE.sub(replace, text), count


def _mask_markdown_links(text: str) -> tuple[str, int]:
    """Keep visible link labels and discard private or identifying targets."""
    return MARKDOWN_LINK_RE.subn(lambda match: match.group(1), text)


def _mask_book_titles(text: str) -> tuple[str, int]:
    return BOOK_TITLE_RE.subn(
        lambda _match: f"《{FIXED_REDACTION_BLOCK}》",
        text,
    )


def _mask_keyword_bound_quoted_entities(text: str) -> tuple[str, int]:
    count = 0
    result = text
    for pattern, (opening, closing) in zip(KEYWORD_BEFORE_QUOTE_RES, QUOTE_PAIRS):
        result, replacements = pattern.subn(
            lambda match, left=opening, right=closing: (
                f"{match.group('prefix')}{left}{FIXED_REDACTION_BLOCK}{right}"
            ),
            result,
        )
        count += replacements
    for pattern, (opening, closing) in zip(QUOTE_BEFORE_KEYWORD_RES, QUOTE_PAIRS):
        result, replacements = pattern.subn(
            lambda match, left=opening, right=closing: (
                f"{left}{FIXED_REDACTION_BLOCK}{right}{match.group('suffix')}"
            ),
            result,
        )
        count += replacements
    result, replacements = KEYWORD_BEFORE_EMPHASIS_RE.subn(
        lambda match: (
            f"{match.group('prefix')}{match.group('mark')}"
            f"{FIXED_REDACTION_BLOCK}{match.group('mark')}"
        ),
        result,
    )
    count += replacements
    result, replacements = EMPHASIS_BEFORE_KEYWORD_RE.subn(
        lambda match: (
            f"{match.group('mark')}{FIXED_REDACTION_BLOCK}{match.group('mark')}"
            f"{match.group('suffix')}"
        ),
        result,
    )
    count += replacements
    return result, count


def _term_pattern(terms: Sequence[str]) -> re.Pattern[str] | None:
    unique = sorted(
        {
            str(term)
            for term in terms
            if str(term) and str(term) != FIXED_REDACTION_BLOCK
        },
        key=lambda term: (-len(term), term),
    )
    if not unique:
        return None
    return re.compile("|".join(re.escape(term) for term in unique), re.IGNORECASE)


def _mask_terms(text: str, terms: Sequence[str]) -> tuple[str, int]:
    pattern = _term_pattern(terms)
    if pattern is None:
        return text, 0
    return pattern.subn(FIXED_REDACTION_BLOCK, text)


def mask_reminder_entities(
    text: str,
    *,
    exact_terms: Sequence[str] = (),
    detected_entities: Sequence[str] = (),
) -> tuple[str, int]:
    """Mask targeted identifying spans without changing the surrounding prose."""
    result = text
    redaction_count = 0

    result, count = _mask_terms(result, (*exact_terms, *detected_entities))
    redaction_count += count

    result, count = _mask_markdown_links(result)
    redaction_count += count
    result, count = _mask_book_titles(result)
    redaction_count += count
    result, count = _mask_keyword_bound_quoted_entities(result)
    redaction_count += count

    for pattern in (
        EMAIL_RE,
        LOCAL_PATH_RE,
        PRIVATE_STORAGE_RE,
        CHINESE_MOBILE_RE,
        NORTH_AMERICAN_PHONE_RE,
        INTERNATIONAL_PHONE_RE,
        RAW_TOKEN_RE,
        UUID_RE,
        PLAIN_URL_RE,
    ):
        result, count = _mask_regex(result, pattern)
        redaction_count += count

    for pattern in (SECRET_ASSIGNMENT_RE, IDENTIFIER_ASSIGNMENT_RE):
        result, count = _mask_assignment(result, pattern)
        redaction_count += count

    result, _ = _mask_phone_context(result)
    result = ADJACENT_MASK_RE.sub(FIXED_REDACTION_BLOCK, result)
    redaction_count = result.count(FIXED_REDACTION_BLOCK)
    return result, redaction_count


def extractive_prefix(text: str, max_length: int = MAX_EXCERPT_LENGTH) -> str:
    """Return a literal prefix, preferring a sentence boundary, plus one ellipsis."""
    if len(text) <= max_length:
        return text
    prefix_limit = max_length - 1
    candidate = text[:prefix_limit]
    boundary = max(
        (
            candidate.rfind(marker)
            for marker in ("。", "！", "？", ".", "!", "?", "\n")
        ),
        default=-1,
    )
    if boundary >= max(40, prefix_limit // 3):
        candidate = candidate[: boundary + 1]
    else:
        whitespace = max(candidate.rfind(" "), candidate.rfind("\t"))
        if whitespace >= max(40, prefix_limit // 2):
            candidate = candidate[:whitespace]
    return f"{candidate.rstrip()}…"


def project_limited_reminder_response(
    responses: list[str],
    time_bucket: str,
    *,
    exact_terms: Sequence[str] = (),
    detected_entities: Sequence[str] = (),
) -> dict | None:
    """Create the v2 near-verbatim public projection from private responses."""
    original = join_reminder_responses(responses)
    if not original:
        return None
    masked, redaction_count = mask_reminder_entities(
        original,
        exact_terms=exact_terms,
        detected_entities=detected_entities,
    )
    public_text, semantic_tags = abstract_sensitive_public_text(masked)
    redaction_count = public_text.count(FIXED_REDACTION_BLOCK)
    summary = public_text[:MAX_SOURCE_LENGTH]
    if len(public_text) > MAX_SOURCE_LENGTH:
        summary = f"{summary[:-1]}…"
    label_zh, label_en = TIME_LABELS.get(time_bucket, ("提醒", "Reminder"))
    return {
        "public_label_zh": label_zh,
        "public_label_en": label_en,
        "summary_original": summary,
        "excerpt_original": extractive_prefix(summary),
        "original_language": detect_original_language(original),
        "projection_kind": projection_kind_for_counts(
            redaction_count,
            len(semantic_tags),
        ),
        "redaction_policy": REDACTION_POLICY,
        "redaction_count": redaction_count,
        "semantic_abstraction_count": len(semantic_tags),
        "projection_provenance": PROJECTION_PROVENANCE,
        "disclosure_policy": DISCLOSURE_POLICY,
        "disclosure_authorization": DISCLOSURE_AUTHORIZATION,
    }


def reminder_ownership_is_authorized(source: dict) -> bool:
    return (
        source.get("owner_scope") in {"self", "self_scheduler_residue"}
        and source.get("ownership_provenance")
        in {"explicit_user_authorization", "explicit_import_authorization"}
        and source.get("disclosure_policy") == DISCLOSURE_POLICY
        and source.get("disclosure_authorization") == DISCLOSURE_AUTHORIZATION
    )


def project_private_reminder(source: dict) -> dict | None:
    """Copy an already-masked v2 reminder; never reconstruct it from raw fields."""
    if not reminder_ownership_is_authorized(source):
        return None
    required = (
        "public_label_zh",
        "public_label_en",
        "summary_original",
        "excerpt_original",
        "original_language",
        "projection_kind",
        "redaction_policy",
        "redaction_count",
        "semantic_abstraction_count",
        "projection_provenance",
        "disclosure_policy",
        "disclosure_authorization",
    )
    if not all(field in source for field in required):
        return None
    return {field: source[field] for field in required}
